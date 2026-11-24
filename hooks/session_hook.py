#!/usr/bin/env python3
"""Claude Code hook: writes one state file per session for the widget.

Reads the hook event JSON on stdin. Writes
    $XDG_RUNTIME_DIR/claude-session-bots/sessions/<session_id>.json
(or ~/.cache/claude-session-bots/sessions/ when XDG_RUNTIME_DIR is unset).

Rules (DESIGN.md §9): standard library only, always exit 0, print nothing,
write atomically (temp file + rename).
"""
import json
import os
import re
import sys
import tempfile
import time

STATES_FOR_NOTIFICATION = {
    "permission_prompt", "elicitation_dialog", "elicitation_url_dialog", "agent_needs_input",
}
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


def sessions_dir():
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        return os.path.join(runtime, "claude-session-bots", "sessions")
    return os.path.join(os.path.expanduser("~"), ".cache", "claude-session-bots", "sessions")


def claude_pid():
    """Find the Claude Code process: walk up from our parent, looking for 'claude'.

    Hook commands may run through a short-lived shell, so the immediate parent
    can exit early and the widget would drop the session. Falls back to the parent.
    """
    parent = os.getppid()
    pid = parent
    for _ in range(8):
        if pid <= 1:
            break
        try:
            with open(f"/proc/{pid}/comm", encoding="utf-8") as fh:
                comm = fh.read().strip()
            if "claude" in comm.lower():
                return pid
            with open(f"/proc/{pid}/cmdline", "rb") as fh:
                argv0 = fh.read().split(b"\0", 1)[0].decode("utf-8", "replace")
            if "claude" in os.path.basename(argv0).lower():
                return pid
            with open(f"/proc/{pid}/stat", encoding="utf-8") as fh:
                stat = fh.read()
            pid = int(stat.rsplit(")", 1)[1].split()[1])  # ppid is field 4
        except (OSError, ValueError, IndexError):
            break
    return parent


def short_input(tool_input):
    """A short, one-line summary of a tool's input for the message."""
    if not isinstance(tool_input, dict):
        return ""
    for key in ("command", "file_path", "path", "pattern", "url", "description", "prompt"):
        val = tool_input.get(key)
        if isinstance(val, str) and val.strip():
            text = " ".join(val.split())
            return text[:60] + ("…" if len(text) > 60 else "")
    for val in tool_input.values():
        if isinstance(val, str) and val.strip():
            return " ".join(val.split())[:60]
    return ""


def read_existing(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def write_atomic(path, data):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def decide(event):
    """Map a hook event to (state, message) or None for 'no change'."""
    name = event.get("hook_event_name", "")
    if name == "SessionStart":
        return "idle", "Session open, nothing new"
    if name == "UserPromptSubmit":
        return "work", "Claude is working on your prompt"
    if name in ("PreToolUse", "PostToolUse"):
        tool = event.get("tool_name") or "a tool"
        detail = short_input(event.get("tool_input"))
        return "work", f"Running {tool}: {detail}" if detail else f"Running {tool}"
    if name == "PermissionRequest":
        return "needs", f"Permission needed: {event.get('tool_name') or 'a tool'}"
    if name == "Notification":
        if event.get("notification_type") in STATES_FOR_NOTIFICATION:
            return "needs", str(event.get("message") or "Claude needs your input")
        return None
    if name == "Stop":
        return "done", "Done. Waiting for your next prompt."
    if name == "StopFailure":
        return "needs", f"Stopped: {event.get('error') or 'unknown error'}"
    return None


def handle(event, now=None, pid=None, base=None):
    """Apply one event. Returns the path written or removed, or None."""
    now = time.time() if now is None else now
    sid = str(event.get("session_id") or "")
    if not SESSION_ID_RE.match(sid):
        return None
    base = base or sessions_dir()
    path = os.path.join(base, f"{sid}.json")

    if event.get("hook_event_name") == "SessionEnd":
        try:
            os.unlink(path)
        except OSError:
            pass
        return path

    decision = decide(event)
    if decision is None:
        return None
    state, message = decision
    old = read_existing(path) or {}
    since = old.get("since") if old.get("state") == state and old.get("since") else now
    cwd = str(event.get("cwd") or old.get("cwd") or "")
    project = os.path.basename(cwd.rstrip("/")) or old.get("project") or "session"
    data = {
        "session_id": sid,
        "state": state,
        "project": project,
        "cwd": cwd,
        "message": message,
        "since": since,
        "updated": now,
        "claude_pid": pid if pid is not None else claude_pid(),
    }
    write_atomic(path, data)
    return path


def main():
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
        if isinstance(event, dict):
            handle(event)
    except Exception:  # never disturb Claude Code
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
