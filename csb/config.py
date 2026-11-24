"""User settings, saved to ~/.config/claude-session-bots/config.json."""
import json
import os
from dataclasses import asdict, dataclass

CORNERS = ("top-left", "top-right", "bottom-left", "bottom-right")


def config_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "claude-session-bots", "config.json")


@dataclass
class Config:
    corner: str = "top-right"
    vertical: bool = False
    notifications: bool = True

    @classmethod
    def load(cls, path=None):
        path = str(path or config_path())
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return cls()
        cfg = cls()
        if data.get("corner") in CORNERS:
            cfg.corner = data["corner"]
        cfg.vertical = bool(data.get("vertical", cfg.vertical))
        cfg.notifications = bool(data.get("notifications", cfg.notifications))
        return cfg

    def save(self, path=None):
        path = str(path or config_path())
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh, indent=2)
        os.replace(tmp, path)
