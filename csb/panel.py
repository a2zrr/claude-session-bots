"""The panel: drawing, hit-testing, hover tooltip and right-click menu.

Sizes are logical px (DESIGN.md §4). The panel draws itself with Gtk.Snapshot.
Sprites use nearest-neighbour scaling at integer positions only.
"""
import math
import os
import time

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Graphene, Gsk, Gtk, Pango, GLib  # noqa: E402

from . import model  # noqa: E402
from .config import CORNERS  # noqa: E402
from .sprites import SpriteSheet  # noqa: E402

PANEL_FILL = "rgba(21, 18, 29, 0.90)"
PANEL_BORDER = "rgba(255, 255, 255, 0.08)"
HOVER_FILL = "rgba(255, 255, 255, 0.07)"
TEXT_PRIMARY = "#ECEAF4"
TEXT_SECONDARY = "#9D98B1"
TOOLTIP_FILL = "#221D30"
MENU_FILL = "#1E1A2A"
TOOLTIP_DELAY_MS = 400

# Cell geometry (logical px).
PANEL_INSET = 6
GAP = 4
H_CELL = (72, 76)
H_ROBOT = (20, 8)
H_IND = (48, 4)
H_LABEL_Y = 43
H_NAME_Y = 57
H_NAME_MAX = 68
V_ROW = (164, 44)
V_ROBOT = (12, 8)
V_IND = (40, 4)
V_TEXT_X = 58
V_TEXT_W = 100
PANEL_RADIUS = 12
CELL_RADIUS = 8

# Font sizes are CSS px; Pango wants points at 96 dpi.
def _font(family, px, weight=Pango.Weight.NORMAL):
    fd = Pango.FontDescription()
    fd.set_family(family)
    fd.set_size(int(round(px * 0.75 * Pango.SCALE)))
    fd.set_weight(weight)
    return fd


FONT_LABEL = _font("Inter", 11, Pango.Weight.SEMIBOLD)
FONT_NAME = _font("JetBrains Mono", 10)
FONT_PLUS = _font("Inter", 16, Pango.Weight.SEMIBOLD)


def rgba(value):
    c = Gdk.RGBA()
    if not c.parse(value):
        raise ValueError(value)
    return c


def rrect(x, y, w, h, r):
    rr = Gsk.RoundedRect()
    rr.init_from_rect(Graphene.Rect().init(x, y, w, h), r)
    return rr


def panel_size(cells, vertical):
    if vertical:
        return 176, 8 + 48 * cells
    return 8 + 76 * cells, 88


class Panel(Gtk.Widget):
    """Draws the robot cells. Owns the hover state and the tooltip popover."""

    __gtype_name__ = "CsbPanel"

    def __init__(self, sprites, callbacks):
        super().__init__()
        self.sprites = sprites
        self.cb = callbacks  # on_activate(session_id), on_menu(x, y)
        self.sessions = []
        self.overflow = 0
        self.vertical = False
        self.corner = "top-right"
        self.hover = None  # index into self.cells
        self._tip_timer = 0
        self._tip = None
        self._tip_session_id = None
        self.set_hexpand(False)
        self.set_vexpand(False)

        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", self._on_leave)
        self.add_controller(motion)

        click = Gtk.GestureClick()
        click.set_button(0)
        click.connect("released", self._on_click)
        self.add_controller(click)

    # ----- data -----------------------------------------------------------

    @property
    def cells(self):
        cells = [("s", s) for s in self.sessions]
        if self.overflow:
            cells.append(("more", self.overflow))
        return cells

    def set_data(self, sessions, vertical, corner, overflow=0):
        self.sessions = list(sessions)
        self.overflow = overflow
        self.vertical = vertical
        self.corner = corner
        if self.hover is not None and self.hover >= len(self.cells):
            self.hover = None
        w, h = self.content_size()
        self.set_size_request(w, h)
        self.queue_resize()
        self.queue_draw()
        self.refresh_tooltip()

    def content_size(self):
        return panel_size(len(self.cells), self.vertical)

    # ----- geometry -------------------------------------------------------

    def cell_rect(self, i):
        if self.vertical:
            return PANEL_INSET, PANEL_INSET + i * 48, V_ROW[0], V_ROW[1]
        return PANEL_INSET + i * (H_CELL[0] + GAP), PANEL_INSET, H_CELL[0], H_CELL[1]

    def index_at(self, x, y):
        for i in range(len(self.cells)):
            cx, cy, cw, ch = self.cell_rect(i)
            if cx <= x < cx + cw and cy <= y < cy + ch:
                return i
        return None

    # ----- drawing --------------------------------------------------------

    def do_measure(self, orientation, for_size):
        w, h = self.content_size()
        size = w if orientation == Gtk.Orientation.HORIZONTAL else h
        return size, size, -1, -1

    def do_snapshot(self, snap):
        w, h = self.content_size()
        bounds = Graphene.Rect().init(0, 0, w, h)
        panel = rrect(0, 0, w, h, PANEL_RADIUS)
        snap.push_rounded_clip(panel)
        snap.append_color(rgba(PANEL_FILL), bounds)
        snap.pop()
        border = rgba(PANEL_BORDER)
        snap.append_border(panel, [1, 1, 1, 1], [border] * 4)

        now = time.time()
        for i, (kind, data) in enumerate(self.cells):
            x, y, cw, ch = self.cell_rect(i)
            if self.hover == i:
                snap.push_rounded_clip(rrect(x, y, cw, ch, CELL_RADIUS))
                snap.append_color(rgba(HOVER_FILL), Graphene.Rect().init(x, y, cw, ch))
                snap.pop()
            if kind == "more":
                self._draw_more(snap, i, data)
            else:
                self._draw_session(snap, i, data, now)

    def _draw_session(self, snap, i, s, now):
        elapsed_ms = (now - s.since) * 1000
        key, dy = model.robot_frame(s.state, elapsed_ms)
        ind = model.indicator_frame(s.state, elapsed_ms)
        x, y, cw, ch = self.cell_rect(i)
        if self.vertical:
            rx, ry = x + V_ROBOT[0], y + V_ROBOT[1] + dy
            ix, iy = x + V_IND[0], y + V_IND[1]
            tx = x + V_TEXT_X
            # +1 px over the spec's 8/22: matches the reference's text baseline.
            label_y, name_y = y + 9, y + 23
            label_w, name_w = V_TEXT_W, V_TEXT_W
            align_center = False
        else:
            rx, ry = x + H_ROBOT[0], y + H_ROBOT[1] + dy
            ix, iy = x + H_IND[0], y + H_IND[1]
            tx = x
            label_y, name_y = y + H_LABEL_Y, y + H_NAME_Y
            label_w, name_w = cw, H_NAME_MAX
            align_center = True
        self.sprites.draw(snap, key, rx, ry)
        if ind:
            self.sprites.draw(snap, ind, ix, iy)
        label_x = tx if not align_center else x
        self._text(snap, model.LABELS[s.state], FONT_LABEL, model.LABEL_COLOURS[s.state],
                   label_x, label_y, label_w, center=align_center)
        self._text(snap, s.project, FONT_NAME, model.PROJECT_COLOURS[s.state],
                   tx if not align_center else x + (cw - name_w) // 2, name_y, name_w,
                   center=align_center, ellipsize=True)

    def _draw_more(self, snap, i, n):
        x, y, cw, ch = self.cell_rect(i)
        layout = self._layout(f"+{n}", FONT_PLUS, width=cw)
        lw, lh = layout.get_pixel_size()
        self._text(snap, f"+{n}", FONT_PLUS, TEXT_SECONDARY, x, y + (ch - lh) // 2, cw, center=True)

    def _layout(self, text, font, width=None, center=False, ellipsize=False):
        layout = self.create_pango_layout(text)
        layout.set_font_description(font)
        if width is not None:
            layout.set_width(int(width) * Pango.SCALE)
        if center:
            layout.set_alignment(Pango.Alignment.CENTER)
        if ellipsize:
            layout.set_ellipsize(Pango.EllipsizeMode.END)
        return layout

    def _text(self, snap, text, font, colour, x, y, width=None, center=False, ellipsize=False):
        layout = self._layout(text, font, width, center, ellipsize)
        snap.save()
        snap.translate(Graphene.Point().init(int(x), int(y)))
        snap.append_layout(layout, rgba(colour))
        snap.restore()

    # ----- pointer --------------------------------------------------------

    def _on_motion(self, _ctrl, x, y):
        idx = self.index_at(x, y)
        if idx != self.hover:
            self.hover = idx
            self.queue_draw()
            self._cancel_tip()
            if idx is not None and self.cells[idx][0] == "s":
                self._tip_timer = GLib.timeout_add(TOOLTIP_DELAY_MS, self._show_tip_timeout, idx)

    def _on_leave(self, _ctrl):
        self.hover = None
        self._cancel_tip()
        self.queue_draw()

    def _on_click(self, gesture, n_press, x, y):
        button = gesture.get_current_button()
        if button == Gdk.BUTTON_SECONDARY:
            self.cb["on_menu"](x, y)
            return
        if button != Gdk.BUTTON_PRIMARY:
            return
        idx = self.index_at(x, y)
        if idx is None or self.cells[idx][0] != "s":
            return
        self.cb["on_activate"](self.cells[idx][1].session_id)

    # ----- tooltip --------------------------------------------------------

    def _cancel_tip(self):
        if self._tip_timer:
            GLib.source_remove(self._tip_timer)
            self._tip_timer = 0
        self._hide_tip()

    def _hide_tip(self):
        if self._tip is not None:
            self._tip.popdown()
            self._tip.unparent()
            self._tip = None
            self._tip_session_id = None

    def _show_tip_timeout(self, idx):
        self._tip_timer = 0
        if self.hover != idx or idx >= len(self.cells):
            return GLib.SOURCE_REMOVE
        kind, s = self.cells[idx]
        if kind != "s":
            return GLib.SOURCE_REMOVE
        self._hide_tip()
        self._tip = Gtk.Popover()
        self._tip.set_parent(self)
        self._tip.set_has_arrow(False)
        self._tip.set_autohide(False)
        self._tip.set_can_focus(False)
        self._tip.add_css_class("csb-tooltip")
        self._tip_session_id = s.session_id
        self._tip.set_child(self._tooltip_content(s))
        self._place_tip(idx)
        self._tip.popup()
        return GLib.SOURCE_REMOVE

    def _place_tip(self, idx):
        x, y, cw, ch = self.cell_rect(idx)
        rect = Gdk.Rectangle()
        top = self.corner.startswith("top")
        if self.vertical:
            rect.x, rect.y, rect.width, rect.height = x, y, cw, ch
            right = self.corner.endswith("right")
            self._tip.set_position(Gtk.PositionType.LEFT if right else Gtk.PositionType.RIGHT)
        else:
            w, h = self.content_size()
            rect.x, rect.y, rect.width, rect.height = x, y, cw, ch
            if top:
                self._tip.set_position(Gtk.PositionType.BOTTOM)
            else:
                rect.x, rect.y, rect.width, rect.height = 0, 0, w, h
                self._tip.set_position(Gtk.PositionType.TOP)
        self._tip.set_pointing_to(rect)

    def refresh_tooltip(self):
        """Rebuild the open tooltip so its time and text stay current."""
        if self._tip is None or self._tip_session_id is None:
            return
        s = next((x for x in self.sessions if x.session_id == self._tip_session_id), None)
        if s is None:
            self._hide_tip()
            return
        self._tip.set_child(self._tooltip_content(s))

    def _tooltip_content(self, s):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_size_request(208, -1)

        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label=s.project, xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END)
        title.add_css_class("csb-tip-title")
        when = Gtk.Label(label=model.elapsed_text(s.state, s.since, time.time()), xalign=1)
        when.add_css_class("csb-tip-time")
        head.append(title)
        head.append(when)
        box.append(head)

        state_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        dot = Gtk.DrawingArea()
        dot.set_content_width(6)
        dot.set_content_height(6)
        colour = rgba(model.LABEL_COLOURS[s.state])
        dot.set_draw_func(lambda _a, cr, w, h, c=colour: _fill_rect(cr, c, w, h))
        dot.set_valign(Gtk.Align.CENTER)
        state = Gtk.Label(label=model.LABELS[s.state], xalign=0)
        state.add_css_class("csb-tip-state")
        state.add_css_class(f"csb-state-{s.state}")
        state_row.append(dot)
        state_row.append(state)
        box.append(state_row)

        msg = Gtk.Label(label=s.message or model.LABELS[s.state], xalign=0, wrap=True)
        msg.set_max_width_chars(34)
        msg.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        msg.add_css_class("csb-tip-msg")
        box.append(msg)

        path = Gtk.Label(label=_tilde(s.cwd) or "", xalign=0, ellipsize=Pango.EllipsizeMode.MIDDLE)
        path.add_css_class("csb-tip-path")
        box.append(path)

        divider = Gtk.Box()
        divider.add_css_class("csb-divider")
        divider.set_margin_top(2)
        divider.set_margin_bottom(6)
        box.append(divider)

        hint = Gtk.Label(label="Click: open the terminal · Right-click: options", xalign=0)
        hint.add_css_class("csb-tip-hint")
        box.append(hint)
        return box


def _fill_rect(cr, colour, w, h):
    cr.set_source_rgba(colour.red, colour.green, colour.blue, colour.alpha)
    cr.rectangle(0, 0, w, h)
    cr.fill()


def _tilde(path):
    home = os.path.expanduser("~")
    if path == home or path.startswith(home + os.sep):
        return "~" + path[len(home):]
    return path


CSS = f"""
popover.csb-tooltip > contents {{
  background: {TOOLTIP_FILL};
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 8px;
  padding: 10px 12px;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.5);
}}
popover.csb-menu > contents {{
  background: {MENU_FILL};
  border: 1px solid rgba(255, 255, 255, 0.10);
  border-radius: 10px;
  padding: 4px;
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.55);
}}
label.csb-tip-title {{ font-family: Inter; font-size: 12px; font-weight: 600; color: {TEXT_PRIMARY}; }}
label.csb-tip-time {{ font-family: Inter; font-size: 10px; color: {TEXT_SECONDARY}; }}
label.csb-tip-state {{ font-family: Inter; font-size: 11px; font-weight: 600; }}
label.csb-tip-msg {{ font-family: Inter; font-size: 11px; color: #C9C5D9; }}
label.csb-tip-path {{ font-family: "JetBrains Mono"; font-size: 10px; color: #8A85A0; }}
label.csb-tip-hint {{ font-family: Inter; font-size: 10px; color: {TEXT_SECONDARY}; }}
box.csb-divider {{ min-height: 1px; background: rgba(255, 255, 255, 0.08); }}
label.csb-state-needs {{ color: #FF7A88; }}
label.csb-state-done {{ color: #FFC24D; }}
label.csb-state-work {{ color: #4FE08F; }}
label.csb-state-idle {{ color: #A7A3B6; }}
button.csb-item {{
  min-height: 28px; padding: 0 8px 0 6px; border-radius: 6px; background: none;
  box-shadow: none; color: {TEXT_PRIMARY}; font-family: Inter; font-size: 12px; font-weight: 500;
}}
button.csb-item:hover {{ background: rgba(255, 255, 255, 0.08); }}
label.csb-check {{ min-width: 14px; color: {TEXT_PRIMARY}; font-size: 12px; }}
switch.csb-switch {{ min-width: 26px; min-height: 14px; }}
box.csb-menu-sep {{ min-height: 1px; background: rgba(255, 255, 255, 0.08); margin: 4px 6px; }}
"""


def install_css():
    provider = Gtk.CssProvider()
    provider.load_from_string(CSS)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


# ----- right-click menu -------------------------------------------------------

CORNER_NAMES = {
    "top-left": "Top left", "top-right": "Top right",
    "bottom-left": "Bottom left", "bottom-right": "Bottom right",
}


def _corner_glyph(corner):
    area = Gtk.DrawingArea()
    area.set_content_width(14)
    area.set_content_height(14)

    def draw(_a, cr, w, h):
        cr.set_source_rgba(0.93, 0.92, 0.96, 0.7)
        cr.set_line_width(1)
        r = 3
        x, y, s = 0.5, 0.5, 13
        cr.new_sub_path()
        cr.arc(x + s - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + s - r, y + s - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + s - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()
        cr.stroke()
        qx = 0 if corner.endswith("left") else 7
        qy = 0 if corner.startswith("top") else 7
        cr.set_source_rgba(0.93, 0.92, 0.96, 0.9)
        cr.rectangle(qx + 3, qy + 3, 4, 4)
        cr.fill()

    area.set_draw_func(draw)
    return area


def _item(text, check=False, right=None):
    btn = Gtk.Button()
    btn.add_css_class("csb-item")
    btn.set_has_frame(False)
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    lead = Gtk.Label(label="✓" if check else "")
    lead.add_css_class("csb-check")
    row.append(lead)
    label = Gtk.Label(label=text, xalign=0, hexpand=True)
    row.append(label)
    if right is not None:
        row.append(right)
    btn.set_child(row)
    return btn


class ContextMenu(Gtk.Popover):
    """Right-click menu. Built with GTK widgets so it can hold a switch and glyphs."""

    def __init__(self, parent, state, actions):
        super().__init__()
        self.set_parent(parent)
        self.set_has_arrow(False)
        self.add_css_class("csb-menu")
        self.state = state  # dict: corner, vertical, notifications
        self.actions = actions  # dict of callables: set_corner, toggle_vertical, set_notifications, quit
        self.set_size_request(184, -1)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(box)

        self.corner_btn = _item("Move to corner", right=Gtk.Label(label="▸"))
        box.append(self.corner_btn)
        self.sub = Gtk.Popover()
        self.sub.set_parent(self.corner_btn)
        self.sub.set_has_arrow(False)
        self.sub.set_position(Gtk.PositionType.RIGHT)
        self.sub.set_offset(-4, 0)
        self.sub.add_css_class("csb-menu")
        self.sub.set_size_request(148, -1)
        subbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.sub.set_child(subbox)
        for corner in CORNERS:
            b = _item(CORNER_NAMES[corner], check=(state["corner"] == corner), right=_corner_glyph(corner))
            b.connect("clicked", self._pick_corner, corner)
            subbox.append(b)
        self.corner_btn.connect("clicked", lambda *_: self.sub.popup())

        vert = _item("Vertical layout", check=state["vertical"])
        vert.connect("clicked", lambda *_: self._run(actions["toggle_vertical"]))
        box.append(vert)

        sw = Gtk.Switch()
        sw.add_css_class("csb-switch")
        sw.set_active(state["notifications"])
        sw.set_valign(Gtk.Align.CENTER)
        sw.set_can_target(False)  # the row button toggles it, so clicks don't double-fire
        notif = _item("Notifications", right=sw)
        notif.connect("clicked", lambda *_: sw.set_active(not sw.get_active()))
        sw.connect("notify::active", lambda s, _p: actions["set_notifications"](s.get_active()))
        box.append(notif)

        sep = Gtk.Box()
        sep.add_css_class("csb-menu-sep")
        box.append(sep)
        quit_btn = _item("Quit")
        quit_btn.connect("clicked", lambda *_: self._run(actions["quit"]))
        box.append(quit_btn)

    def _pick_corner(self, _btn, corner):
        self.sub.popdown()
        self._run(lambda: self.actions["set_corner"](corner))

    def _run(self, fn):
        self.popdown()
        fn()

    def open_at(self, x, y):
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        self.set_pointing_to(rect)
        self.set_position(Gtk.PositionType.BOTTOM)
        self.popup()
