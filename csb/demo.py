"""Fake sessions for --demo: four projects, each cycling through the states."""
import time

from . import model
from .sessions import Session

# (session id, project, cwd, state sequence with seconds per state)
SCRIPT = [
    ("demo-1", "flappy-bird", "~/projects/flappy-bird",
     [(model.NEEDS, 6, "Claude needs your permission to use Bash"), (model.WORK, 8, "Running Bash: npm test"),
      (model.DONE, 6, "Done. Waiting for your next prompt.")]),
    ("demo-2", "portfolio-site", "~/projects/portfolio-site",
     [(model.DONE, 6, "Done. Waiting for your next prompt."), (model.WORK, 6, "Running Edit: index.html"),
      (model.IDLE, 6, "Session open, nothing new")]),
    ("demo-3", "api-server", "~/projects/api-server",
     [(model.WORK, 10, "Running Bash: pytest -q"), (model.NEEDS, 5, "Claude needs your permission to use Bash"),
      (model.WORK, 6, "Running Read: app.py")]),
    ("demo-4", "dotfiles", "~/projects/dotfiles",
     [(model.IDLE, 12, "Session open, nothing new"), (model.WORK, 5, "Running Write: .zshrc"),
      (model.DONE, 6, "Done. Waiting for your next prompt.")]),
]


class DemoSource:
    """Feeds the store with fake sessions. Call `tick(now)` every second or so."""

    def __init__(self, store, on_change):
        self.store = store
        self.on_change = on_change
        self.start = time.time()
        self._started = False

    def _state_at(self, steps, t):
        total = sum(s[1] for s in steps)
        t = t % total
        for state, dur, msg in steps:
            if t < dur:
                return state, msg
            t -= dur
        return steps[-1][0], steps[-1][2]

    def tick(self, now=None):
        now = now or time.time()
        changed = False
        for idx, (sid, project, cwd, steps) in enumerate(SCRIPT):
            # Stagger the start so the four cells are not in lockstep.
            t = now - self.start + idx * 2.5
            state, msg = self._state_at(steps, t)
            if self.store.get(sid) is None:
                sess = Session(session_id=sid, state=state, project=project, cwd=cwd,
                               message=msg, since=now, updated=now, claude_pid=0)
                self.store.upsert(sess, now)
                changed = True
            else:
                cur = self.store.get(sid)
                if cur.state != state:
                    self.store.upsert(Session(session_id=sid, state=state, project=project, cwd=cwd,
                                              message=msg, since=now, updated=now, claude_pid=0), now)
                    changed = True
        if changed:
            self.on_change()
