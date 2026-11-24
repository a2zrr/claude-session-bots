"""Session records and the store the widget renders from.

The store is pure Python. The GTK layer reads it and the hook files feed it.
Rules from DESIGN.md §9: remove sessions whose Claude process is gone, and
turn Finished into Idle after 10 minutes.
"""
import json
import os
from dataclasses import dataclass, field, replace

from . import model

FINISHED_TO_IDLE_S = 10 * 60


@dataclass(frozen=True)
class Session:
    session_id: str
    state: str
    project: str
    cwd: str = ""
    message: str = ""
    since: float = 0.0
    updated: float = 0.0
    claude_pid: int = 0


@dataclass
class Store:
    """Sessions keyed by id, kept in first-seen order (oldest first)."""

    _items: dict = field(default_factory=dict)

    def __len__(self):
        return len(self._items)

    def ordered(self):
        return list(self._items.values())

    def get(self, session_id):
        return self._items.get(session_id)

    def upsert(self, session, now=None):
        """Add or update a session. `since` moves only when the state changes."""
        old = self._items.get(session.session_id)
        if old is None:
            self._items[session.session_id] = session
            return True
        if old.state != session.state:
            since = session.since or now or old.since
        else:
            since = old.since
        new = replace(session, since=since)
        changed = new != old
        self._items[session.session_id] = new
        return changed

    def remove(self, session_id):
        return self._items.pop(session_id, None) is not None

    def set_state(self, session_id, state, now):
        old = self._items.get(session_id)
        if old is None or old.state == state:
            return False
        self._items[session_id] = replace(old, state=state, since=now)
        return True

    def sweep(self, now, pid_alive):
        """Drop dead sessions and age Finished into Idle. Returns True if changed."""
        changed = False
        for sid, s in list(self._items.items()):
            if s.claude_pid and not pid_alive(s.claude_pid):
                del self._items[sid]
                changed = True
            elif s.state == model.DONE and now - s.since >= FINISHED_TO_IDLE_S:
                self._items[sid] = replace(s, state=model.IDLE, since=now)
                changed = True
        return changed


def load_session_file(path):
    """Parse one hook-written session file. Returns a Session or None if invalid."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        state = data["state"]
        if state not in model.STATES:
            return None
        return Session(
            session_id=str(data["session_id"]),
            state=state,
            project=str(data.get("project") or "?"),
            cwd=str(data.get("cwd") or ""),
            message=str(data.get("message") or ""),
            since=float(data.get("since") or 0.0),
            updated=float(data.get("updated") or 0.0),
            claude_pid=int(data.get("claude_pid") or 0),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def pid_alive(pid):
    """True if a process with this pid exists (signal 0 probe)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
