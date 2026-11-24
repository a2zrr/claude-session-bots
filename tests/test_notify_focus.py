from csb import focus, model, notify
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


def test_parent_chain_nearest_first_and_stops_at_init():
    parents = {300: 200, 200: 100, 100: 1}
    assert list(focus.parent_chain(300, parents.get)) == [300, 200, 100]


def test_parent_chain_survives_cycles():
    parents = {5: 6, 6: 5}
    assert list(focus.parent_chain(5, parents.get)) == [5, 6]


def test_find_window_prefers_nearest_ancestor():
    windows = [{"id": 1, "pid": 100}, {"id": 2, "pid": 200}, {"id": 3, "pid": 999}]
    assert focus.find_window(windows, [300, 200, 100]) == 2
    assert focus.find_window(windows, [300]) is None


def test_focus_session_runs_niri_with_window_id(monkeypatch):
    calls = []

    class Out:
        stdout = '[{"id": 7, "pid": 50}]'

    def fake_run(argv, **kw):
        calls.append(argv)
        return Out()

    monkeypatch.setenv("NIRI_SOCKET", "/tmp/fake.sock")
    monkeypatch.setattr(focus.shutil, "which", lambda name: "/usr/bin/niri")
    monkeypatch.setattr(focus, "parent_chain", lambda pid, **kw: iter([60, 50]))
    assert focus.focus_session(60, run=fake_run) is True
    assert calls[-1] == ["niri", "msg", "action", "focus-window", "--id", "7"]


def test_focus_does_nothing_off_niri(monkeypatch):
    monkeypatch.delenv("NIRI_SOCKET", raising=False)
    assert focus.focus_session(60) is False
