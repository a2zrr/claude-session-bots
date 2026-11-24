"""Pure state logic: colours, labels, animation frames, elapsed text.

No GTK imports here, so this module is unit-tested directly.
Timings and colours come from design/DESIGN.md §2 and §6.
"""

NEEDS = "needs"
DONE = "done"
WORK = "work"
IDLE = "idle"
STATES = (NEEDS, DONE, WORK, IDLE)

LABELS = {NEEDS: "Needs you", DONE: "Finished", WORK: "Working", IDLE: "Idle"}
LABEL_COLOURS = {NEEDS: "#FF7A88", DONE: "#FFC24D", WORK: "#4FE08F", IDLE: "#A7A3B6"}
PROJECT_COLOURS = {NEEDS: "#9D98B1", DONE: "#9D98B1", WORK: "#9D98B1", IDLE: "#8A85A0"}

# Each step: (robot sprite key, duration ms, vertical offset in logical px).
# Frames are looped; the offset lifts the robot 2 px on the bounce frames.
ROBOT_FRAMES = {
    NEEDS: [("needs-0", 600, 0), ("needs-1", 600, 0)],
    DONE: [("done-0", 1000, 0)],
    WORK: [
        ("work-0", 500, 0),
        ("work-1", 500, -2),
        ("work-0", 500, 0),
        ("work-1", 500, -2),
        ("work-2", 150, 0),
    ],
    IDLE: [("idle-0", 1000, 0)],
}

# Indicator sprite loop, or None for no indicator.
INDICATOR_FRAMES = {
    NEEDS: [("bang-0", 300), ("bang-1", 300)],
    DONE: [("spark-0", 450), ("spark-1", 450)],
    WORK: None,
    IDLE: [("zz-0", 900), ("zz-1", 900)],
}

TICK_MS = 100
MAX_CELLS = 8


def _pick(frames, elapsed_ms):
    """Return the frame tuple active at elapsed_ms. Each frame's duration is item[1]."""
    total = sum(item[1] for item in frames)
    t = int(elapsed_ms) % total
    for item in frames:
        if t < item[1]:
            return item
        t -= item[1]
    return frames[-1]


def robot_frame(state, elapsed_ms):
    """Return (sprite key, dy) for the robot at this time since the state began."""
    item = _pick(ROBOT_FRAMES[state], elapsed_ms)
    return item[0], item[2]


def indicator_frame(state, elapsed_ms):
    """Return the indicator sprite key, or None."""
    frames = INDICATOR_FRAMES[state]
    if not frames:
        return None
    return _pick(frames, elapsed_ms)[0]


def click_result(state):
    """What a left click does on a robot: a Finished robot becomes Idle, nothing else."""
    return IDLE if state == DONE else None


def elapsed_text(state, since, now):
    """Human text for the tooltip's time column."""
    secs = max(0, now - since)
    if secs < 60:
        return "just now"
    mins = int(secs // 60)
    if state == NEEDS:
        return f"waiting {mins} min"
    if state == WORK:
        return f"working {mins} min"
    if state == IDLE:
        return f"idle {mins} min"
    return f"{mins} min ago"


def visible_cells(count):
    """How many robot cells to draw for `count` sessions, and how many overflow.

    Returns (cells, overflow). When count > MAX_CELLS the last cell is the
    "+N" cell, so 7 sessions are drawn and overflow = count - 7.
    """
    if count <= MAX_CELLS:
        return count, 0
    return MAX_CELLS, count - (MAX_CELLS - 1)
