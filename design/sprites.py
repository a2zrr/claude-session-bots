"""Pixel robot sprites for the Claude Code session widget.

Single source of truth: rows of characters + a palette per sprite.
Outputs: spritesheet.png (64x64), spritesheet@2x.png, sprites.json, preview.png
"""
import json, sys
from PIL import Image

OUT = sys.argv[1] if len(sys.argv) > 1 else "."

SHARED = {"f": "#221C2E"}

STATES = {
    "needs": {"o": "#5C1426", "b": "#F2445A", "l": "#FF8A96", "d": "#B02341", "e": "#FFE1E4", "m": "#7A1028"},
    "done":  {"o": "#5E3208", "b": "#FFB02E", "l": "#FFD97A", "d": "#D97A1E", "e": "#FFF4D6", "k": "#FF8B6A"},
    "work":  {"o": "#0E4A2A", "b": "#34D27B", "l": "#8EF0B6", "d": "#1C9454", "e": "#E2FFEE"},
    "idle":  {"o": "#34313F", "b": "#7E7A8E", "l": "#A6A2B5", "d": "#565266", "e": "#C9C6D4"},
}

# 16x16 robot body. Face plate (f) = cols 4-11, rows 5-9; faces are drawn on it.
BASE = [
    ".......oo.......",
    "......oaao......",
    ".......oo.......",
    ".....oooooo.....",
    "...oolllbbboo...",
    "..olffffffffbo..",
    "ooolffffffffbooo",
    "odolffffffffbodo",
    "ooobffffffffdooo",
    "..obffffffffdo..",
    "..obdddddddddo..",
    "...oooooooooo...",
    "....olbbbbbo....",
    "....oddddddo....",
    "....obbbbbdo....",
    "....oooooooo....",
]

# 8x5 faces (plate-local). '.' keeps the plate colour.
FACES = {
    "needs-0": ["..e..e..", ".ee..ee.", ".ee..ee.", "..eeee..", "..emme.."],
    "needs-1": ["..e..e..", ".ee..ee.", ".ee..ee.", ".eeeeee.", ".emmmme."],
    "done-0":  ["........", ".e....e.", "e.e..e.e", "k.e..e.k", "...ee..."],
    "work-0":  ["........", "ee..ee..", "ee..ee..", "........", "...ee..."],
    "work-1":  ["........", "..ee..ee", "..ee..ee", "........", "...ee..."],
    "work-2":  ["........", "........", ".ee..ee.", "........", "...ee..."],
    "idle-0":  ["........", ".bb..bb.", ".ee..ee.", "........", "....e..."],
}

# antenna tip colour per robot frame
ANTENNA = {
    "needs-0": "#FF8A96", "needs-1": "#FFF3B0",
    "done-0": "#FFF4D6",
    "work-0": "#CFFFE3", "work-1": "#CFFFE3", "work-2": "#1C9454",
    "idle-0": "#565266",
}

INDICATORS = {
    "bang-0": ([
        "........",
        "..hhrr..",
        "..hrrx..",
        "..hrrx..",
        "...rx...",
        "...rx...",
        "........",
        "...hr...",
        "...rx...",
        "........",
    ], {"r": "#FF3D52", "h": "#FFA0A9", "x": "#C21F3A"}),
    "spark-0": ([
        "........",
        "........",
        "...yy...",
        "...yy...",
        ".yywwyy.",
        ".yywwyy.",
        "...yy...",
        "...yy...",
        "........",
        "........",
    ], {"y": "#FFC93C", "w": "#FFF8DC"}),
    "spark-1": ([
        "........",
        "........",
        ".k....k.",
        "..k..k..",
        "...ww...",
        "...ww...",
        "..k..k..",
        ".k....k.",
        "........",
        "........",
    ], {"k": "#FFE08A", "w": "#FFF8DC"}),
    "zz-0": ([
        "....zzzz",
        "......z.",
        ".....z..",
        "....zzzz",
        "........",
        "ZZZZZ...",
        "...Z....",
        "..Z.....",
        ".Z......",
        "ZZZZZ...",
    ], {"Z": "#C9C6D4", "z": "#6E6A80"}),
}
# bang-1 / zz-1 = same art one pixel higher
def shift_up(rows):
    return rows[1:] + ["." * len(rows[0])]
INDICATORS["bang-1"] = (shift_up(INDICATORS["bang-0"][0]), INDICATORS["bang-0"][1])
INDICATORS["zz-1"] = (INDICATORS["zz-0"][0], {"Z": "#6E6A80", "z": "#C9C6D4"})

# position on the 64x64 sheet
LAYOUT = {
    "needs-0": (0, 0), "needs-1": (16, 0), "bang-0": (48, 0), "bang-1": (56, 0),
    "done-0": (0, 16), "spark-0": (48, 16), "spark-1": (56, 16),
    "work-0": (0, 32), "work-1": (16, 32), "work-2": (32, 32),
    "idle-0": (0, 48), "zz-0": (48, 48), "zz-1": (56, 48),
}
ORDER = list(LAYOUT.keys())


def robot(key):
    state = key.split("-")[0]
    rows = [list(r) for r in BASE]
    for py, frow in enumerate(FACES[key]):
        for px, ch in enumerate(frow):
            if ch != ".":
                rows[5 + py][4 + px] = ch
    rows = ["".join(r) for r in rows]
    pal = dict(SHARED)
    pal.update(STATES[state])
    pal["a"] = ANTENNA[key]
    used = sorted({c for r in rows for c in r if c != "."}, key="ofbldeamk".index)
    return rows, {c: pal[c] for c in used}


def build():
    sprites = {}
    for key in ORDER:
        if key in FACES:
            rows, pal = robot(key)
        else:
            rows, p = INDICATORS[key]
            used = []
            for r in rows:
                for c in r:
                    if c != "." and c not in used:
                        used.append(c)
            pal = {c: p[c] for c in used}
        for r in rows:
            assert len(r) == len(rows[0]), (key, r)
        x, y = LAYOUT[key]
        sprites[key] = {"x": x, "y": y, "w": len(rows[0]), "h": len(rows), "rows": rows, "palette": pal}
    return sprites


def hex2rgba(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)


def sheet(sprites, scale=1):
    img = Image.new("RGBA", (64 * scale, 64 * scale), (0, 0, 0, 0))
    for s in sprites.values():
        for ry, row in enumerate(s["rows"]):
            for rx, ch in enumerate(row):
                if ch == ".":
                    continue
                c = hex2rgba(s["palette"][ch])
                for dy in range(scale):
                    for dx in range(scale):
                        img.putpixel(((s["x"] + rx) * scale + dx, (s["y"] + ry) * scale + dy), c)
    return img


if __name__ == "__main__":
    sp = build()
    sheet(sp, 1).save(f"{OUT}/spritesheet.png")
    sheet(sp, 2).save(f"{OUT}/spritesheet@2x.png")
    prev = Image.new("RGBA", (64 * 10, 64 * 10), (21, 18, 29, 255))
    big = sheet(sp, 10)
    prev.alpha_composite(big)
    prev.save(f"{OUT}/preview.png")
    meta = {
        "image": "spritesheet.png",
        "size": [64, 64],
        "note": "rows: one string per pixel row, '.' = transparent; palette maps each character to a hex colour",
        "sprites": sp,
    }
    with open(f"{OUT}/sprites.json", "w") as fh:
        json.dump(meta, fh, indent=1)
    # compact JS for the canvas
    js = {k: {"x": v["x"], "y": v["y"], "w": v["w"], "h": v["h"]} for k, v in sp.items()}
    print(json.dumps(js, separators=(",", ":")))
