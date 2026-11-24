import json

from csb import listing, model
from csb.sessions import Session


def write(folder, sid, **kw):
    data = {"session_id": sid, "state": "work", "project": sid, "since": 100.0, "claude_pid": 0}
    data.update(kw)
    (folder / f"{sid}.json").write_text(json.dumps(data))


def test_lists_oldest_first_and_skips_dead_claude(tmp_path):
    write(tmp_path, "new", since=300.0, claude_pid=2)
    write(tmp_path, "old", since=100.0, claude_pid=1)
    write(tmp_path, "dead", since=50.0, claude_pid=99)
    got = listing.current_sessions(str(tmp_path), alive=lambda pid: pid != 99)
    assert [s.project for s in got] == ["old", "new"]


def test_ignores_bad_files(tmp_path):
    (tmp_path / "junk.json").write_text("{nope")
    (tmp_path / "note.txt").write_text("x")
    write(tmp_path, "ok")
    assert [s.session_id for s in listing.current_sessions(str(tmp_path), alive=lambda p: True)] == ["ok"]


def test_missing_folder_is_empty(tmp_path):
    assert listing.current_sessions(str(tmp_path / "nope")) == []


def test_table_has_project_state_since():
    sessions = [Session("a", model.NEEDS, "flappy-bird", since=1000.0),
                Session("b", model.IDLE, "dotfiles", since=1000.0)]
    text = listing.format_table(sessions, now=1000.0 + 120)
    lines = text.splitlines()
    assert lines[0].split()[:3] == ["PROJECT", "STATE", "SINCE"]
    assert "flappy-bird" in lines[1] and "Needs you" in lines[1] and "waiting 2 min" in lines[1]
    assert "dotfiles" in lines[2] and "Idle" in lines[2]


def test_empty_table():
    assert listing.format_table([]) == "No sessions."
