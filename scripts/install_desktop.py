#!/usr/bin/env python3
"""Install the .desktop entry and icon for the current user (no sudo).

Writes to ~/.local/share/applications and ~/.local/share/icons. The app id
matches the .desktop name so notifications are accepted by the daemon.
  python3 scripts/install_desktop.py
  python3 scripts/install_desktop.py --uninstall
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
APP_ID = "io.github.ClaudeSessionBots"
LAUNCHER = os.path.join(ROOT, "bin", "claude-session-bots")
TEMPLATE = os.path.join(ROOT, "packaging", f"{APP_ID}.desktop.in")
DATA = os.path.join(os.path.expanduser("~"), ".local", "share")


def paths():
    return {
        "desktop": os.path.join(DATA, "applications", f"{APP_ID}.desktop"),
        "icon": os.path.join(DATA, "icons", "hicolor", "48x48", "apps", f"{APP_ID}.png"),
    }


def make_icon(dest):
    """Export the needs-0 robot at 3x (48 px) using the project's sprite code."""
    sys.path.insert(0, ROOT)
    from csb.sprites import SpriteSheet  # imports GTK; run with the project venv
    png = SpriteSheet().icon_png("needs-0", scale=3)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as fh:
        fh.write(png)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args(argv)
    p = paths()
    if args.uninstall:
        for f in p.values():
            if os.path.exists(f):
                os.remove(f)
                print(f"Removed {f}")
    else:
        with open(TEMPLATE, encoding="utf-8") as fh:
            text = fh.read().replace("@LAUNCHER@", LAUNCHER)
        os.makedirs(os.path.dirname(p["desktop"]), exist_ok=True)
        with open(p["desktop"], "w", encoding="utf-8") as fh:
            fh.write(text)
        make_icon(p["icon"])
        print(f"Wrote {p['desktop']}")
        print(f"Wrote {p['icon']}")
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", os.path.dirname(p["desktop"])], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
