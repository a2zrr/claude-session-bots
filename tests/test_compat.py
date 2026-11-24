import os

from csb import compat


def test_finds_library_in_first_matching_dir(tmp_path):
    a = tmp_path / "lib64"
    b = tmp_path / "debian"
    a.mkdir()
    b.mkdir()
    (b / compat.LIB_NAME).write_text("")
    assert compat.find_layer_shell([str(a), str(b)], use_ldconfig=False) == str(b / compat.LIB_NAME)


def test_prefers_earlier_dir(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / compat.LIB_NAME).write_text("")
    (b / compat.LIB_NAME).write_text("")
    assert compat.find_layer_shell([str(a), str(b)], use_ldconfig=False) == str(a / compat.LIB_NAME)


def test_missing_returns_none(tmp_path):
    assert compat.find_layer_shell([str(tmp_path)], use_ldconfig=False) is None


def test_env_override_replaces_search_dirs(tmp_path, monkeypatch):
    (tmp_path / compat.LIB_NAME).write_text("")
    monkeypatch.setenv("CSB_LIBDIRS", str(tmp_path))
    assert compat.find_layer_shell(use_ldconfig=False) == str(tmp_path / compat.LIB_NAME)
    monkeypatch.setenv("CSB_LIBDIRS", "/nonexistent-dir")
    assert compat.find_layer_shell(use_ldconfig=False) is None


def test_ldconfig_output_is_parsed(monkeypatch):
    sample = ("\tlibgtk4-layer-shell.so.0 (libc6,x86-64) => /usr/lib/x86_64-linux-gnu/libgtk4-layer-shell.so.0\n"
              "\tlibfoo.so.1 (libc6) => /usr/lib/libfoo.so.1\n")

    class Done:
        stdout = sample

    monkeypatch.setattr(compat.subprocess, "run", lambda *a, **k: Done())
    assert compat._ldconfig_lookup() == "/usr/lib/x86_64-linux-gnu/libgtk4-layer-shell.so.0"


def test_main_exit_codes(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CSB_LIBDIRS", str(tmp_path))
    assert compat.main(["--find-layer-shell"]) == 1
    (tmp_path / compat.LIB_NAME).write_text("")
    assert compat.main(["--find-layer-shell"]) == 0
    assert capsys.readouterr().out.strip().endswith(compat.LIB_NAME)
