"""Sprite sheet access. Sprites are drawn with nearest-neighbour scaling only."""
import json
import os

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import Gdk, GdkPixbuf, Graphene, Gsk  # noqa: E402

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# One sprite pixel is 2 logical px on the widget (DESIGN.md §3).
PIXEL = 2


class SpriteSheet:
    """Each sprite is cut out of the sheet once, into its own texture."""

    def __init__(self, sheet_path=None, json_path=None):
        sheet_path = sheet_path or os.path.join(ASSETS, "spritesheet.png")
        json_path = json_path or os.path.join(ASSETS, "sprites.json")
        sheet = GdkPixbuf.Pixbuf.new_from_file(sheet_path)
        with open(json_path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.textures = {}
        self.pixbufs = {}
        self.sizes = {}
        for key, s in data["sprites"].items():
            sub = sheet.new_subpixbuf(s["x"], s["y"], s["w"], s["h"])
            self.pixbufs[key] = sub
            self.textures[key] = Gdk.Texture.new_for_pixbuf(sub)
            self.sizes[key] = (s["w"] * PIXEL, s["h"] * PIXEL)

    def size(self, key):
        """Logical size of a sprite at the widget's 2 px-per-pixel scale."""
        return self.sizes[key]

    def icon_png(self, key, scale=3):
        """PNG bytes of one sprite at an integer scale (nearest-neighbour), for notifications."""
        pb = self.pixbufs[key]
        big = pb.scale_simple(pb.get_width() * scale, pb.get_height() * scale, GdkPixbuf.InterpType.NEAREST)
        ok, data = big.save_to_bufferv("png", [], [])
        return bytes(data) if ok else b""

    def draw(self, snapshot, key, x, y):
        """Draw sprite `key` with its top-left at integer logical (x, y)."""
        w, h = self.sizes[key]
        bounds = Graphene.Rect().init(int(x), int(y), w, h)
        snapshot.append_scaled_texture(self.textures[key], Gsk.ScalingFilter.NEAREST, bounds)
