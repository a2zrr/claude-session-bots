import importlib.util
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("install", os.path.join(ROOT, "scripts", "install.py"))
install = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install)


def user_hook():
    return {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo mine"}]}


def test_merge_keeps_existing_settings_and_hooks():
    before = {"model": "x", "hooks": {"Stop": [user_hook()]}}
    after = install.merge(before)
    assert after["model"] == "x"
    assert after["hooks"]["Stop"][0] == user_hook()
    assert len(after["hooks"]["Stop"]) == 2
    for event in install.EVENTS:
        assert any(install.is_ours(g) for g in after["hooks"][event])


def test_hooks_are_async_command_type():
    after = install.merge({})
    cmd = after["hooks"]["PreToolUse"][0]["hooks"][0]
    assert cmd["type"] == "command" and cmd["async"] is True
    assert "session_hook.py" in cmd["command"]


def test_merge_is_idempotent():
    once = install.merge({"hooks": {"Stop": [user_hook()]}})
    twice = install.merge(once)
    assert once == twice


def test_uninstall_removes_only_ours():
    installed = install.merge({"model": "x", "hooks": {"Stop": [user_hook()]}})
    removed = install.merge(installed, uninstall=True)
    assert removed == {"model": "x", "hooks": {"Stop": [user_hook()]}}


def test_uninstall_on_clean_file_is_noop():
    assert install.merge({"model": "x"}, uninstall=True) == {"model": "x"}


def test_main_dry_run_writes_nothing(tmp_path, capsys):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"model": "x"}))
    rc = install.main(["--settings", str(path)])
    assert rc == 0
    assert json.loads(path.read_text()) == {"model": "x"}
    assert "Dry run" in capsys.readouterr().out


def test_main_apply_backs_up_then_writes(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"model": "x"}))
    assert install.main(["--settings", str(path), "--apply"]) == 0
    backups = [p for p in os.listdir(tmp_path) if p.startswith("settings.json.bak-")]
    assert len(backups) == 1
    assert json.loads((tmp_path / backups[0]).read_text()) == {"model": "x"}
    assert "SessionStart" in json.loads(path.read_text())["hooks"]


def test_main_apply_creates_missing_file(tmp_path):
    path = tmp_path / "new" / "settings.json"
    assert install.main(["--settings", str(path), "--apply"]) == 0
    assert "hooks" in json.loads(path.read_text())
