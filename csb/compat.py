"""Finds gtk4-layer-shell on Fedora and Debian/Ubuntu. Standard library only.

The launcher calls `python3 -m csb.compat --find-layer-shell` before GTK starts,
so the library can be preloaded. Prints the path and exits 0, or exits 1.
CSB_LIBDIRS (colon-separated) replaces the search directories; used by tests.
"""
import os
import re
import subprocess
import sys

LIB_NAME = "libgtk4-layer-shell.so.0"
SEARCH_DIRS = [
    "/usr/lib64",                  # Fedora
    "/usr/lib/x86_64-linux-gnu",   # Debian / Ubuntu, amd64
    "/usr/lib/aarch64-linux-gnu",  # Debian / Ubuntu, arm64
    "/usr/lib",
]


def _ldconfig_lookup():
    try:
        out = subprocess.run(["ldconfig", "-p"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"^\s*" + re.escape(LIB_NAME) + r" .*=> (\S+)$", out, re.MULTILINE)
    return m.group(1) if m else None


def find_layer_shell(dirs=None, use_ldconfig=True):
    """Return the full path of libgtk4-layer-shell.so.0, or None if it is not installed.

    With CSB_LIBDIRS set, only those directories are searched (no ldconfig).
    """
    if dirs is None:
        env = os.environ.get("CSB_LIBDIRS")
        if env is not None:
            dirs, use_ldconfig = env.split(":"), False
        else:
            dirs = SEARCH_DIRS
    for d in dirs:
        candidate = os.path.join(d, LIB_NAME)
        if os.path.exists(candidate):
            return candidate
    if use_ldconfig:
        return _ldconfig_lookup()
    return None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv != ["--find-layer-shell"]:
        print("usage: python3 -m csb.compat --find-layer-shell", file=sys.stderr)
        return 2
    path = find_layer_shell()
    if path:
        print(path)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
