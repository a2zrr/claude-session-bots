"""`--list`: print the sessions the widget currently sees. No GTK needed."""
import os
import time

from . import model
from .sessions import load_session_file, pid_alive


def current_sessions(folder, alive=pid_alive):
    """Sessions in the folder that the widget would show, oldest first.

    Same rule as the widget's sweep: a session whose Claude process is gone is skipped.
    """
    out = []
    if not os.path.isdir(folder):
        return out
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".json"):
            continue
        sess = load_session_file(os.path.join(folder, name))
        if sess is None:
            continue
        if sess.claude_pid and not alive(sess.claude_pid):
            continue
        out.append(sess)
    return sorted(out, key=lambda s: (s.since, s.session_id))


def format_table(sessions, now=None):
    now = time.time() if now is None else now
    if not sessions:
        return "No sessions."
    rows = [("PROJECT", "STATE", "SINCE")]
    for s in sessions:
        since = time.strftime("%H:%M:%S", time.localtime(s.since)) if s.since else "-"
        ago = model.elapsed_text(s.state, s.since, now) if s.since else "-"
        rows.append((s.project, model.LABELS[s.state], f"{since}  ({ago})"))
    widths = [max(len(r[i]) for r in rows) for i in range(3)]
    return "\n".join("  ".join(c.ljust(widths[i]) for i, c in enumerate(r)).rstrip() for r in rows)


def run_list(folder=None):
    from .app import sessions_dir
    print(format_table(current_sessions(folder or sessions_dir())))
    return 0
