from csb import model, notify
from csb.sessions import Session


def s(sid, state, project="p", msg=""):
    return Session(session_id=sid, state=state, project=project, message=msg)


def test_entering_needs_or_done_only():
    prev = {"a": model.WORK, "b": model.NEEDS, "c": model.IDLE}
    sessions = [s("a", model.NEEDS), s("b", model.NEEDS), s("c", model.DONE), s("d", model.WORK)]
    assert [x.session_id for x in notify.entering(prev, sessions)] == ["a", "c"]


def test_new_session_starting_in_needs_notifies():
    assert [x.session_id for x in notify.entering({}, [s("n", model.NEEDS)])] == ["n"]


def test_same_state_twice_does_not_notify_again():
    prev = notify.snapshot_states([s("a", model.DONE)])
    assert notify.entering(prev, [s("a", model.DONE)]) == []


def test_text_and_priority():
    title, body, prio = notify.text_for(s("a", model.NEEDS, "flappy-bird", "Claude needs your permission"))
    assert title == "flappy-bird needs you" and body == "Claude needs your permission"
    title, body, prio = notify.text_for(s("a", model.DONE, "portfolio"))
    assert title == "portfolio is finished" and body == "Done. Waiting for your next prompt."


def test_notification_id_changes_with_state():
    assert notify.notification_id(s("a", model.NEEDS)) != notify.notification_id(s("a", model.DONE))


def test_click_only_finished_becomes_idle():
    assert model.click_result(model.DONE) == model.IDLE
    for state in (model.NEEDS, model.WORK, model.IDLE):
        assert model.click_result(state) is None


def test_notification_has_no_buttons_or_actions():
    import inspect
    src = inspect.getsource(notify.build)
    assert "add_button" not in src and "default_action" not in src
