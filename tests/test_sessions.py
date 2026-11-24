import json

from csb import model
from csb.sessions import FINISHED_TO_IDLE_S, Session, Store, load_session_file


def make(sid, state=model.WORK, since=100.0, pid=0):
    return Session(session_id=sid, state=state, project=sid, since=since, updated=since, claude_pid=pid)


def test_order_is_first_seen():
    st = Store()
    st.upsert(make("b"), 1)
    st.upsert(make("a"), 2)
    st.upsert(make("b", state=model.DONE), 3)
    assert [s.session_id for s in st.ordered()] == ["b", "a"]


def test_since_moves_only_on_state_change():
    st = Store()
    st.upsert(make("a", since=100.0), 100)
    st.upsert(make("a", state=model.WORK, since=150.0), 150)  # same state: keep 100
    assert st.get("a").since == 100.0
    st.upsert(make("a", state=model.NEEDS, since=200.0), 200)
    assert st.get("a").since == 200.0


def test_set_state_changes_since():
    st = Store()
    st.upsert(make("a", state=model.DONE, since=1.0), 1)
    assert st.set_state("a", model.IDLE, 50.0)
    assert st.get("a").state == model.IDLE and st.get("a").since == 50.0
    assert not st.set_state("a", model.IDLE, 60.0)


def test_sweep_removes_dead_claude_process():
    st = Store()
    st.upsert(make("dead", pid=111), 0)
    st.upsert(make("alive", pid=222), 0)
    changed = st.sweep(10, lambda pid: pid == 222)
    assert changed
    assert [s.session_id for s in st.ordered()] == ["alive"]


def test_sweep_turns_finished_into_idle_after_10_min():
    st = Store()
    st.upsert(make("a", state=model.DONE, since=0.0), 0)
    st.sweep(FINISHED_TO_IDLE_S - 1, lambda pid: True)
    assert st.get("a").state == model.DONE
    st.sweep(FINISHED_TO_IDLE_S, lambda pid: True)
    assert st.get("a").state == model.IDLE


def test_load_session_file_valid_and_invalid(tmp_path):
    good = tmp_path / "s1.json"
    good.write_text(json.dumps({"session_id": "s1", "state": "needs", "project": "p",
                                "since": 5, "claude_pid": 42}))
    s = load_session_file(good)
    assert s.state == model.NEEDS and s.claude_pid == 42

    bad_state = tmp_path / "s2.json"
    bad_state.write_text(json.dumps({"session_id": "s2", "state": "nope"}))
    assert load_session_file(bad_state) is None

    broken = tmp_path / "s3.json"
    broken.write_text("{not json")
    assert load_session_file(broken) is None
    assert load_session_file(tmp_path / "missing.json") is None
