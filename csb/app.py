"""Application entry: window (layer-shell on Niri, plain window elsewhere), timers, menu wiring."""
import argparse
import os
import sys
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
# gtk4-layer-shell must be loaded before GTK initialises its Wayland display.
from gi.repository import Gtk4LayerShell as LayerShell  # noqa: E402
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from . import model  # noqa: E402
from .config import Config  # noqa: E402
from .demo import DemoSource  # noqa: E402
from .panel import ContextMenu, Panel, install_css  # noqa: E402
from .sessions import Store, load_session_file, pid_alive  # noqa: E402
from .sprites import SpriteSheet  # noqa: E402

APP_ID = "io.github.ClaudeSessionBots"
MARGIN = 16
SWEEP_S = 30
POLL_MS = 1000

CORNER_EDGES = {
    "top-left": (LayerShell.Edge.TOP, LayerShell.Edge.LEFT),
    "top-right": (LayerShell.Edge.TOP, LayerShell.Edge.RIGHT),
    "bottom-left": (LayerShell.Edge.BOTTOM, LayerShell.Edge.LEFT),
    "bottom-right": (LayerShell.Edge.BOTTOM, LayerShell.Edge.RIGHT),
}


def sessions_dir():
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        return os.path.join(runtime, "claude-session-bots", "sessions")
    return os.path.expanduser("~/.cache/claude-session-bots/sessions")


def visible_split(sessions):
    """Return (shown sessions, overflow count) for the cell count rule."""
    cells, overflow = model.visible_cells(len(sessions))
    shown = sessions[: cells - 1] if overflow else sessions[:cells]
    return shown, overflow


class Controller:
    def __init__(self, app, demo, render_dir=None):
        self.app = app
        self.cfg = Config.load()
        self.store = Store()
        self.sprites = SpriteSheet()
        self.demo = None
        self.render_dir = render_dir
        self.anim_id = 0
        self.menu = None
        self.window = None
        self.panel = None
        self.is_layer = False
        self.demo_mode = demo

        install_css()
        self.window = Gtk.Window(application=app)
        self.window.set_title("Claude sessions")
        self.window.set_decorated(False)
        self.window.set_resizable(False)
        self.window.set_default_size(1, 1)
        if not render_dir and LayerShell.is_supported():
            self.is_layer = True
            LayerShell.init_for_window(self.window)
            LayerShell.set_layer(self.window, LayerShell.Layer.OVERLAY)
            LayerShell.set_keyboard_mode(self.window, LayerShell.KeyboardMode.NONE)
            LayerShell.set_exclusive_zone(self.window, 0)
            LayerShell.set_namespace(self.window, "claude-session-bots")
        self.panel = Panel(self.sprites, {
            "on_activate": self.on_activate,
            "on_menu": self.on_menu,
        })
        self.window.set_child(self.panel)
        self.apply_corner()

        if demo:
            self.demo = DemoSource(self.store, self.on_store_changed)
            self.demo.tick()
            GLib.timeout_add(1000, self._demo_tick)
        else:
            self._poll()
            GLib.timeout_add(POLL_MS, self._poll_tick)
        GLib.timeout_add_seconds(SWEEP_S, self._sweep_tick)
        self.relayout()

    # ----- layout ---------------------------------------------------------

    def apply_corner(self):
        if not self.is_layer:
            return
        edges = CORNER_EDGES[self.cfg.corner]
        for edge in (LayerShell.Edge.TOP, LayerShell.Edge.BOTTOM,
                     LayerShell.Edge.LEFT, LayerShell.Edge.RIGHT):
            LayerShell.set_anchor(self.window, edge, edge in edges)
            LayerShell.set_margin(self.window, edge, MARGIN if edge in edges else 0)

    def relayout(self):
        ordered = self.store.ordered()
        shown, overflow = visible_split(ordered)
        self.panel.set_data(shown, self.cfg.vertical, self.cfg.corner, overflow)
        self.window.set_visible(bool(ordered))
        self.ensure_anim()

    def ensure_anim(self):
        if len(self.store) and not self.anim_id:
            self.anim_id = GLib.timeout_add(model.TICK_MS, self._anim_tick)
        elif not len(self.store) and self.anim_id:
            GLib.source_remove(self.anim_id)
            self.anim_id = 0

    def _anim_tick(self):
        self.panel.queue_draw()
        return GLib.SOURCE_CONTINUE

    def on_store_changed(self):
        self.relayout()

    # ----- sources --------------------------------------------------------

    def _demo_tick(self):
        self.demo.tick()
        self.panel.refresh_tooltip()
        return GLib.SOURCE_CONTINUE

    def _poll(self):
        d = sessions_dir()
        if not os.path.isdir(d):
            return
        changed = False
        now = time.time()
        for name in sorted(os.listdir(d)):
            if not name.endswith(".json"):
                continue
            sess = load_session_file(os.path.join(d, name))
            if sess is None:
                continue
            changed |= self.store.upsert(sess, now)
        if changed:
            self.on_store_changed()

    def _poll_tick(self):
        self._poll()
        self.panel.refresh_tooltip()
        return GLib.SOURCE_CONTINUE

    def _sweep_tick(self):
        if self.store.sweep(time.time(), pid_alive):
            self.on_store_changed()
        return GLib.SOURCE_CONTINUE

    # ----- actions --------------------------------------------------------

    def on_activate(self, session_id):
        s = self.store.get(session_id)
        if s is None:
            return
        if s.state == model.DONE:
            self.store.set_state(session_id, model.IDLE, time.time())
            self.on_store_changed()

    def on_menu(self, x, y):
        if self.menu is not None:
            self.menu.unparent()
        state = {"corner": self.cfg.corner, "vertical": self.cfg.vertical,
                 "notifications": self.cfg.notifications}
        self.menu = ContextMenu(self.panel, state, {
            "set_corner": self.set_corner,
            "toggle_vertical": self.toggle_vertical,
            "set_notifications": self.set_notifications,
            "quit": self.app.quit,
        })
        self.menu.connect("closed", lambda *_: self._menu_closed())
        self.menu.open_at(x, y)

    def _menu_closed(self):
        if self.menu is not None:
            self.menu.unparent()
            self.menu = None

    def set_corner(self, corner):
        self.cfg.corner = corner
        self.cfg.save()
        self.apply_corner()
        self.relayout()

    def toggle_vertical(self):
        self.cfg.vertical = not self.cfg.vertical
        self.cfg.save()
        self.relayout()

    def set_notifications(self, on):
        self.cfg.notifications = on
        self.cfg.save()


class App(Gtk.Application):
    def __init__(self, demo, render_dir=None):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.demo = demo
        self.render_dir = render_dir
        self.controller = None

    def do_activate(self):
        if self.controller is None:
            self.controller = Controller(self, self.demo, self.render_dir)
            if self.render_dir:
                GLib.idle_add(render_snapshots, self.controller, self.render_dir)
        self.controller.window.present()


def render_snapshots(app_controller, out_dir):
    """Write PNGs of the panel for the pixel check. Always quits the app afterwards."""
    try:
        _render(app_controller, out_dir)
    finally:
        app_controller.app.quit()
    return False


def _render(app_controller, out_dir):
    from .sessions import Session
    now = time.time()
    samples = [
        Session("r1", model.NEEDS, "flappy-bird", since=now),
        Session("r2", model.DONE, "portfolio-site", since=now),
        Session("r3", model.WORK, "api-server", since=now),
        Session("r4", model.IDLE, "dotfiles", since=now),
    ]
    cases = [("horizontal-4", False, samples), ("vertical-4", True, samples),
             ("horizontal-1", False, samples[:1]), ("vertical-1", True, samples[:1])]
    panel = app_controller.panel
    window = app_controller.window
    window.set_visible(True)
    window.present()
    ctx = GLib.MainContext.default()
    for _ in range(200):  # wait until the window is mapped and has a renderer
        if window.get_native() is not None and window.get_native().get_surface() is not None:
            break
        ctx.iteration(False)
        time.sleep(0.01)
    for name, vertical, sess in cases:
        panel.set_data(sess, vertical, "top-right")
        for _ in range(20):
            GLib.MainContext.default().iteration(False)
        paintable = Gtk.WidgetPaintable.new(panel)
        w, h = panel.content_size()
        snap = Gtk.Snapshot()
        scale = float(os.environ.get("CSB_RENDER_SCALE", "1"))
        snap.scale(scale, scale)
        paintable.snapshot(snap, w, h)
        node = snap.to_node()
        texture = window.get_native().get_renderer().render_texture(node, None)
        path = os.path.join(out_dir, f"{name}@{scale:g}x.png")
        texture.save_to_png(path)
        print(path, texture.get_width(), texture.get_height())


def main(argv=None):
    parser = argparse.ArgumentParser(prog="claude-session-bots")
    parser.add_argument("--demo", action="store_true", help="show 4 fake sessions cycling through states")
    parser.add_argument("--render", metavar="DIR", help="write panel PNGs to DIR for the pixel check and exit")
    args = parser.parse_args(argv)
    if args.render:
        os.makedirs(args.render, exist_ok=True)
    app = App(demo=args.demo, render_dir=args.render)
    return app.run(sys.argv[:1])
