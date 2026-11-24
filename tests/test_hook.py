import importlib.util
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK_PATH = os.path.join(ROOT, "hooks", "session_hook.py")
spec = importlib.util.spec_from_file_location("session_hook", HOOK_PATH)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def ev(name, **kw):
    base = {"hook_event_name": name, "session_id": "abc-123", "cwd": "/home/u/projects/flappy-bird"}
    base.update(kw)
    return base


@pytest.fixture
def base(tmp_path):
    return str(tmp_path / "sessions")


def read(base, sid="abc-123"):
    with open(os.path.join(base, f"{sid}.json"), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.mark.parametrize("event, state", [
    (ev("SessionStart"), "idle"),
    (ev("UserPromptSubmit"), "work"),
    (ev("PreToolUse", tool_name="Bash", tool_input={"command": "npm test"}), "work"),
    (ev("PostToolUse", tool_name="Read", tool_input={"file_path": "/a.py"}), "work"),
    (ev("PermissionRequest", tool_name="Bash"), "needs"),
    (ev("Notification", notification_type="permission_prompt", message="Needs OK"), "needs"),
    (ev("Notification", notification_type="elicitation_dialog", message="Pick one"), "needs"),
    (ev("Stop"), "done"),
    (ev("StopFailure", error="rate_limit"), "needs"),
])
def test_event_maps_to_state(base, event, state):
    hook.handle(event, now=100.0, pid=4242, base=base)
    data = read(base)
    assert data["state"] == state
    assert data["project"] == "flappy-bird"
    assert data["claude_pid"] == 4242


def test_idle_prompt_notification_changes_nothing(base):
    hook.handle(ev("Stop"), now=1.0, pid=1, base=base)
    hook.handle(ev("Notification", notification_type="idle_prompt", message="x"), now=2.0, pid=1, base=base)
    assert read(base)["state"] == "done"


def test_message_text(base):
    hook.handle(ev("PreToolUse", tool_name="Bash", tool_input={"command": "npm   test\n-w"}), now=1, pid=1, base=base)
    assert read(base)["message"] == "Running Bash: npm test -w"
    hook.handle(ev("PermissionRequest", tool_name="Edit"), now=2, pid=1, base=base)
    assert read(base)["message"] == "Permission needed: Edit"
    hook.handle(ev("StopFailure", error="server_error"), now=3, pid=1, base=base)
    assert read(base)["message"] == "Stopped: server_error"


def test_since_moves_only_when_state_changes(base):
    hook.handle(ev("UserPromptSubmit"), now=100.0, pid=1, base=base)
    hook.handle(ev("PreToolUse", tool_name="Bash", tool_input={"command": "ls"}), now=150.0, pid=1, base=base)
    data = read(base)
    assert data["since"] == 100.0 and data["updated"] == 150.0
    hook.handle(ev("Stop"), now=200.0, pid=1, base=base)
    assert read(base)["since"] == 200.0


def test_session_end_deletes_file(base):
    hook.handle(ev("SessionStart"), now=1, pid=1, base=base)
    assert os.path.exists(os.path.join(base, "abc-123.json"))
    hook.handle(ev("SessionEnd"), now=2, pid=1, base=base)
    assert not os.path.exists(os.path.join(base, "abc-123.json"))


def test_unknown_event_and_bad_session_id_write_nothing(base):
    assert hook.handle(ev("SomethingNew"), now=1, pid=1, base=base) is None
    assert hook.handle(ev("Stop", session_id="../evil"), now=1, pid=1, base=base) is None
    assert not os.path.exists(base) or os.listdir(base) == []


def test_no_temp_files_left_behind(base):
    hook.handle(ev("Stop"), now=1, pid=1, base=base)
    assert [n for n in os.listdir(base) if n.startswith(".tmp")] == []


def test_long_input_is_cut(base):
    hook.handle(ev("PreToolUse", tool_name="Bash", tool_input={"command": "x" * 200}), now=1, pid=1, base=base)
    assert len(read(base)["message"]) <= len("Running Bash: ") + 61


def test_cli_always_exits_zero_and_prints_nothing(tmp_path):
    env = dict(os.environ, XDG_RUNTIME_DIR=str(tmp_path))
    for stdin in ["", "not json", json.dumps(ev("Stop")), json.dumps(["list"])]:
        proc = subprocess.run([sys.executable, HOOK_PATH], input=stdin, capture_output=True, text=True, env=env)
        assert proc.returncode == 0
        assert proc.stdout == "" and proc.stderr == ""
    assert os.path.exists(tmp_path / "claude-session-bots" / "sessions" / "abc-123.json")
