"""Focus a session's terminal on Niri.

Find the window whose pid is an ancestor of the Claude process, then focus it
with `niri msg`. On other desktops this does nothing.
"""
import json
import os
import shutil
import subprocess


def parent_chain(pid, read_ppid=None, limit=64):
    """Yield pid, then its ancestors, nearest first. Stops at init or unknown pids."""
    read_ppid = read_ppid or _proc_ppid
    seen = set()
    while pid and pid > 1 and pid not in seen and len(seen) < limit:
        seen.add(pid)
        yield pid
        pid = read_ppid(pid)


def _proc_ppid(pid):
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as fh:
            stat = fh.read()
        return int(stat.rsplit(")", 1)[1].split()[1])
    except (OSError, ValueError, IndexError):
        return 0


def find_window(windows, chain):
    """Return the window id whose pid is nearest to the Claude process, or None.

    `windows` is the list from `niri msg --json windows`; `chain` is parent_chain().
    """
    by_pid = {}
    for w in windows:
        pid = w.get("pid")
        if isinstance(pid, int) and "id" in w:
            by_pid.setdefault(pid, w["id"])
    for pid in chain:  # nearest ancestor first
        if pid in by_pid:
            return by_pid[pid]
    return None


def focus_session(claude_pid, run=None):
    """Focus the terminal window of this Claude process. Returns True if focused."""
    if not claude_pid or not os.environ.get("NIRI_SOCKET") or not shutil.which("niri"):
        return False
    run = run or subprocess.run
    try:
        out = run(["niri", "msg", "--json", "windows"], capture_output=True, text=True, timeout=3)
        windows = json.loads(out.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return False
    win_id = find_window(windows, parent_chain(claude_pid))
    if win_id is None:
        return False
    try:
        run(["niri", "msg", "action", "focus-window", "--id", str(win_id)],
            capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return False
    return True
