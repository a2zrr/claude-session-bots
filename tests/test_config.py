from csb.config import Config


def test_defaults_when_file_missing(tmp_path):
    cfg = Config.load(tmp_path / "nope.json")
    assert (cfg.corner, cfg.vertical, cfg.notifications) == ("top-right", False, False)


def test_round_trip(tmp_path):
    p = tmp_path / "c.json"
    Config(corner="bottom-left", vertical=True, notifications=False).save(p)
    cfg = Config.load(p)
    assert (cfg.corner, cfg.vertical, cfg.notifications) == ("bottom-left", True, False)


def test_bad_corner_falls_back(tmp_path):
    p = tmp_path / "c.json"
    p.write_text('{"corner": "middle"}')
    assert Config.load(p).corner == "top-right"


def test_notifications_default_off(tmp_path):
    assert Config.load(tmp_path / "missing.json").notifications is False
