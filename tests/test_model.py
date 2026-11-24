from csb import model


def test_needs_robot_alternates_every_600ms():
    assert model.robot_frame(model.NEEDS, 0) == ("needs-0", 0)
    assert model.robot_frame(model.NEEDS, 599) == ("needs-0", 0)
    assert model.robot_frame(model.NEEDS, 600) == ("needs-1", 0)
    assert model.robot_frame(model.NEEDS, 1200) == ("needs-0", 0)


def test_needs_indicator_is_bang_300ms():
    assert model.indicator_frame(model.NEEDS, 0) == "bang-0"
    assert model.indicator_frame(model.NEEDS, 300) == "bang-1"


def test_work_bounces_up_two_px_on_work1():
    assert model.robot_frame(model.WORK, 0) == ("work-0", 0)
    assert model.robot_frame(model.WORK, 500) == ("work-1", -2)
    assert model.robot_frame(model.WORK, 1000) == ("work-0", 0)
    assert model.robot_frame(model.WORK, 1500) == ("work-1", -2)
    assert model.robot_frame(model.WORK, 2000) == ("work-2", 0)
    assert model.robot_frame(model.WORK, 2150) == ("work-0", 0)


def test_work_has_no_indicator():
    assert model.indicator_frame(model.WORK, 0) is None


def test_done_robot_is_still_and_spark_alternates():
    assert model.robot_frame(model.DONE, 0)[0] == "done-0"
    assert model.robot_frame(model.DONE, 5000)[0] == "done-0"
    assert model.indicator_frame(model.DONE, 0) == "spark-0"
    assert model.indicator_frame(model.DONE, 450) == "spark-1"


def test_idle_zz_alternates_every_900ms():
    assert model.indicator_frame(model.IDLE, 0) == "zz-0"
    assert model.indicator_frame(model.IDLE, 900) == "zz-1"


def test_negative_elapsed_does_not_crash():
    assert model.robot_frame(model.NEEDS, -50)[0] in ("needs-0", "needs-1")


def test_elapsed_text():
    now = 10_000.0
    assert model.elapsed_text(model.NEEDS, now - 30, now) == "just now"
    assert model.elapsed_text(model.NEEDS, now - 120, now) == "waiting 2 min"
    assert model.elapsed_text(model.DONE, now - 300, now) == "5 min ago"
    assert model.elapsed_text(model.WORK, now - 60, now) == "working 1 min"
    assert model.elapsed_text(model.IDLE, now - 2400, now) == "idle 40 min"


def test_visible_cells_plus_n_cell():
    assert model.visible_cells(0) == (0, 0)
    assert model.visible_cells(8) == (8, 0)
    assert model.visible_cells(9) == (8, 2)  # 7 sessions + "+2"
    assert model.visible_cells(12) == (8, 5)


def test_drag_threshold_and_hint_text():
    assert model.DRAG_THRESHOLD_PX == 4
    assert model.ALWAYS_ON_TOP_HINT == "Alt+Space → Always on Top to keep it above other windows"
