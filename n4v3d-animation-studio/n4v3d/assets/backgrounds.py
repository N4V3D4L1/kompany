"""Background plates. Rendered once per episode and cached as PNG."""
from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFilter

from .. import config
from ..gfx import Pen, hex2rgba, mix

W, H = config.WIDTH, config.HEIGHT
INK = config.INK
GROUND_Y = 1560  # where characters stand


def _vgrad(w, h, top, bottom):
    img = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        d.line([(0, y), (w, y)], fill=mix(top, bottom, y / max(1, h - 1)))
    return img


def kitchen_day() -> Image.Image:
    base = _vgrad(W, H, hex2rgba("#FFF3DC"), hex2rgba("#FAD9A8"))
    p = Pen(W, H, origin=(0, 0))
    # wallpaper: soft vertical stripes
    for x in range(0, W, 90):
        p.rrect(x, 0, x + 34, 1180, 0, fill=(255, 255, 255, 60), width=0)

    # window with sky
    p.rrect(110, 300, 570, 790, 24, fill=hex2rgba("#8FD3FF"))
    p.circle(450, 420, 60, fill=hex2rgba("#FFE36E"), width=0)
    for cx, cy, s in ((230, 520, 1.0), (420, 640, 0.75)):
        for dx, dy, r in ((-40, 10, 38), (0, -10, 50), (45, 8, 36)):
            p.circle(cx + dx * s, cy + dy * s, r * s, fill=(255, 255, 255, 235), width=0)
    p.rrect(110, 300, 570, 790, 24, fill=None, width=16, outline=WHITE_INK())
    p.rrect(110, 300, 570, 790, 24, fill=None)
    p.stroke([(340, 300), (340, 790)], WHITE_INK(), 14, caps=False)
    p.stroke([(110, 545), (570, 545)], WHITE_INK(), 14, caps=False)
    # curtains
    for x0, x1 in ((70, 190), (490, 610)):
        p.poly([(x0, 270), (x1, 270), (x1 - 10, 830), (x0 + 10, 830)], fill=hex2rgba("#FF8FA3"))
        for k in range(1, 3):
            xx = x0 + (x1 - x0) * k / 3
            p.stroke([(xx, 300), (xx, 810)], hex2rgba("#E66F87"), 6)
    p.rrect(50, 250, 630, 285, 14, fill=hex2rgba("#8C5A3C"))

    # wall clock reading 3:00 (plot point!)
    cx, cy = 840, 470
    p.circle(cx, cy, 120, fill=hex2rgba("#2EC4B6"), width=10)
    p.circle(cx, cy, 98, fill=(255, 255, 255, 255), width=6)
    for k in range(12):
        a = k / 12 * 2 * math.pi
        p.stroke([(cx + 80 * math.cos(a), cy + 80 * math.sin(a)), (cx + 90 * math.cos(a), cy + 90 * math.sin(a))], INK, 6, caps=False)
    p.stroke([(cx, cy), (cx, cy - 74)], INK, 9)
    p.stroke([(cx, cy), (cx + 52, cy)], INK, 11)
    p.circle(cx, cy, 9, fill=INK, width=0)

    # shelf with plant + jar
    p.rrect(690, 760, 1010, 786, 8, fill=hex2rgba("#8C5A3C"))
    p.poly([(730, 760), (800, 760), (790, 690), (740, 690)], fill=hex2rgba("#E07A5F"))
    for ang in (-60, -20, 20, 60):
        a = math.radians(ang - 90)
        p.curve([(765, 690), (765 + 40 * math.cos(a), 690 + 30 * math.sin(a)), (765 + 70 * math.cos(a), 680 + 70 * math.sin(a))],
                hex2rgba("#3FA34D"), 16)
    p.rrect(860, 670, 950, 760, 18, fill=(200, 235, 255, 200))
    p.rrect(850, 652, 960, 680, 8, fill=hex2rgba("#E63946"))

    # counter + cabinets
    p.rrect(-20, 1170, W + 20, 1215, 10, fill=hex2rgba("#C08552"))
    p.rrect(-20, 1210, W + 20, 1440, 0, fill=hex2rgba("#3BAFA2"))
    for x in range(0, W, 270):
        p.rrect(x + 16, 1232, x + 254, 1420, 16, fill=hex2rgba("#45C2B4"), width=7)
        p.rrect(x + 118, 1252, x + 152, 1266, 6, fill=hex2rgba("#F4E3C1"), width=5)
    # toaster on counter (a nod to the morning theme)
    p.rrect(110, 1060, 300, 1172, 30, fill=hex2rgba("#D9DEE5"))
    p.rrect(150, 1050, 200, 1066, 5, fill=INK, width=0)
    p.rrect(215, 1050, 265, 1066, 5, fill=INK, width=0)

    # checkered floor with perspective
    horizon, vx = 1440, W / 2
    rows = [horizon]
    y, h = horizon, 34
    while y < H:
        y += h
        rows.append(y)
        h *= 1.32
    cols = 9
    for r in range(len(rows) - 1):
        ya, yb = rows[r], rows[r + 1]
        for c in range(-cols, cols + 1):
            def xat(yv, cc):
                spread = (yv - 1000) / (horizon - 1000)
                return vx + (cc * 150) * spread
            pts = [(xat(ya, c), ya), (xat(ya, c + 1), ya), (xat(yb, c + 1), yb), (xat(yb, c), yb)]
            col = hex2rgba("#F6E7CB") if (r + c) % 2 == 0 else hex2rgba("#E8B08A")
            p.poly(pts, fill=col, outline=None, width=0)
    p.stroke([(-20, horizon), (W + 20, horizon)], INK, 9, caps=False)

    layer = p.finish()
    base.alpha_composite(layer)

    # soft contact shadow band where characters stand + vignette
    vign = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vign)
    vd.ellipse([-300, -200, W + 300, H + 200], fill=255)
    vign = vign.filter(ImageFilter.GaussianBlur(160))
    dark = Image.new("RGBA", (W, H), (60, 30, 40, 255))
    base = Image.composite(base, dark, vign.point(lambda v: int(150 + v * 105 / 255)))
    return base.convert("RGB")


def WHITE_INK():
    return (255, 255, 255, 255)


BACKGROUNDS = {"kitchen_day": kitchen_day}
