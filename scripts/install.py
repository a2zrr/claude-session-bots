#!/usr/bin/env python3
"""Merge the widget's hooks into ~/.claude/settings.json (or uninstall them).

Default is a dry run: it prints the exact change as a diff and writes nothing.
Pass --apply to write. Before any write the file is backed up next to it.

  python3 scripts/install.py              # show the change
  python3 scripts/install.py --apply      # back up, then write
  python3 scripts/install.py --uninstall  # show the removal
  python3 scripts/install.py --uninstall --apply
"""
import argparse
import copy
import difflib
import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.normpath(os.path.join(HERE, "..", "hooks", "session_hook.py"))
MARK = "session_hook.py"  # identifies our entries (survives moving the folder)

EVENTS = [
    "SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PermissionRequest",
    "Notification", "Stop", "StopFailure", "SessionEnd",
]


def default_settings_path():
    return os.path.expanduser("~/.claude/settings.json")


def our_command():
    # The hook is stdlib-only, so use the system python3 rather than the project venv:
    # deleting .venv must not break every Claude session's hook.
    return f"{shutil.which('python3') or 'python3'} {HOOK}"


def is_ours(entry):
    """True if a hook matcher group contains one of our commands."""
    for hook in entry.get("hooks", []) if isinstance(entry, dict) else []:
        if isinstance(hook, dict) and MARK in str(hook.get("command", "")):
            return True
    return False


def merge(settings, uninstall=False):
    """Return a new settings dict with our hooks added or removed. Other keys are untouched."""
    out = copy.deepcopy(settings)
    hooks = out.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
    for event in EVENTS:
        groups = [g for g in hooks.get(event, []) if not is_ours(g)]
        if not uninstall:
            groups.append({"hooks": [{"type": "command", "command": our_command(), "async": True}]})
        if groups:
            hooks[event] = groups
        else:
            hooks.pop(event, None)
    if hooks:
        out["hooks"] = hooks
    else:
        out.pop("hooks", None)
    return out


BOTS_FUNCTION = 'bots() { systemctl --user "${1:-start}" claude-session-bots; }'
BOTS_BLOCK = "# claude-session-bots: bots [start|stop|restart|status]\n" + BOTS_FUNCTION + "\n"
BOTS_DEFINED = re.compile(r"^\s*(function\s+bots\b|bots\s*\(\)|alias\s+bots=)", re.MULTILINE)


def shell_rc_path(home=None, shell=None):
    """Pick the rc file for the user's login shell: zsh gets ~/.zshrc, everything else ~/.bashrc."""
    home = home or os.path.expanduser("~")
    shell = os.environ.get("SHELL", "") if shell is None else shell
    name = ".zshrc" if os.path.basename(shell) == "zsh" else ".bashrc"
    return os.path.join(home, name)


def add_shell_shortcut(home=None, shell=None):
    """Append the bots() function to the user's rc file. Returns the path, or None if already defined."""
    path = shell_rc_path(home, shell)
    text = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    if BOTS_DEFINED.search(text):
        return None
    if text:
        text = text if text.endswith("\n") else text + "\n"
        text += "\n"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text + BOTS_BLOCK)
    return path


def load(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if not text.strip():
        return {}
    return json.loads(text)


def render(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def write_with_backup(path, new_text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = f"{path}.bak-{stamp}"
        shutil.copy2(path, backup)
        print(f"Backup written: {backup}")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(new_text)
    os.replace(tmp, path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--settings", default=default_settings_path(), help="settings file to edit")
    parser.add_argument("--uninstall", action="store_true", help="remove only our entries")
    parser.add_argument("--apply", action="store_true", help="write the change (default: dry run)")
    parser.add_argument("--shell-shortcut", action="store_true",
                        help="add the bots() command to ~/.bashrc or ~/.zshrc")
    args = parser.parse_args(argv)

    if args.shell_shortcut:
        path = add_shell_shortcut()
        if path is None:
            print(f"A bots command is already defined in {shell_rc_path()}. Nothing changed.")
        else:
            print(f"Added bots() to {path}. Open a new terminal, or run: source {path}")
        return 0

    if not args.uninstall and not os.path.exists(HOOK):
        print(f"Hook script not found: {HOOK}", file=sys.stderr)
        return 1

    path = args.settings
    before_data = load(path)
    after_data = merge(before_data, uninstall=args.uninstall)
    before = render(before_data) if os.path.exists(path) else ""
    after = render(after_data)

    if before == after:
        print("No change: our hooks are already in the desired state.")
        return 0

    diff = difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile=path + " (current)", tofile=path + " (new)",
    )
    sys.stdout.writelines(diff)
    print()

    if not args.apply:
        print("Dry run. Nothing was written. Re-run with --apply to write.")
        return 0

    write_with_backup(path, after)
    action = "removed from" if args.uninstall else "merged into"
    print(f"Hooks {action} {path}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
