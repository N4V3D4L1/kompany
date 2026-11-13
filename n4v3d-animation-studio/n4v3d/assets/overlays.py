"""Full-frame overlay effects: comic bursts, Zzz, title card, end card.

Each overlay is `draw(frame: RGBA Image, params: dict, u: float, t: float)`
where u is 0..1 progress through the overlay's lifetime.
"""
from __future__ import annotations

import math

from PIL import Image

from .. import config
from ..anim import ease
from ..gfx import Pen, hex2rgba, star_points

INK = config.INK
W, H = config.WIDTH, config.HEIGHT


def _fade(u, fin=0.08, fout=0.15):
    if u < fin:
        return u / fin
    if u > 1 - fout:
        return max(0.0, (1 - u) / fout)
    return 1.0


def _composite(frame, img, cx, cy, alpha=1.0):
    if alpha < 1.0:
        a = img.getchannel("A").point(lambda v: int(v * alpha))
        img.putalpha(a)
    frame.alpha_composite(img, (int(cx - img.width / 2), int(cy - img.height / 2)))


def burst(frame, prm, u, t):
    """Comic 'BONK!' style burst."""
    text = prm.get("text", "BONK!")
    x, y = prm.get("at", (540, 900))
    color = hex2rgba(prm.get("color", "#FFE14D"))
    s = ease("out_back", min(1.0, u / 0.25)) * (1.0 + 0.04 * math.sin(t * 30))
    if s <= 0.01:
        return
    size = prm.get("size", 1.0) * s
    p = Pen(520, 360, origin=(260, 180), scale=size)
    p.poly(star_points(0, 0, 230, 150, n=12, rot=prm.get("rot", -8)), fill=color, width=10)
    p.poly(star_points(0, 0, 175, 120, n=12, rot=prm.get("rot", -8) + 15), fill=(255, 255, 255, 255), width=0)
    p.text(0, 4, text, 92, fill=hex2rgba(prm.get("text_color", "#E63946")), stroke=7, stroke_fill=INK,
           angle=prm.get("rot", -8))
    _composite(frame, p.finish(), x, y, _fade(u, 0.01, 0.2))


def zzz(frame, prm, u, t):
    x, y = prm.get("at", (600, 1200))
    for k in range(3):
        ph = (t * 0.6 + k / 3) % 1.0
        sz = 50 + 50 * ph
        a = math.sin(ph * math.pi) * _fade(u, 0.1, 0.1)
        p = Pen(200, 200, origin=(100, 100))
        p.text(0, 0, "Z", sz, fill=(255, 255, 255, 255), stroke=6, stroke_fill=INK, angle=-12)
        _composite(frame, p.finish(), x + 70 * ph + 18 * math.sin(ph * 8), y - 260 * ph, a)


def title(frame, prm, u, t):
    """Opening title: studio tag + bouncing episode title on a ribbon."""
    a = _fade(u, 0.06, 0.18)
    cy = prm.get("y", 700)
    p = Pen(W, 560, origin=(W / 2, 280))
    # ribbon
    s = ease("out_back", min(1.0, u / 0.18))
    p.poly([(-500 * s, -95), (500 * s, -120), (520 * s, 105), (-520 * s, 120)], fill=hex2rgba("#E63946"), width=11)
    p.text(0, -190, prm.get("kicker", "N4V3D ANIMATION STUDIO PRESENTS"), 38, fill=(255, 255, 255, 255),
           stroke=6, stroke_fill=INK, weight="ExtraBold")
    words = prm.get("text", "TITLE")
    n = len(words)
    f_size = min(104, int(900 / max(1, n) * 1.7))
    # per-letter bounce-in
    from ..gfx import font
    fnt = font(int(f_size), "Black")
    total_w = fnt.getlength(words)
    x = -total_w / 2
    for i, ch in enumerate(words):
        cw = fnt.getlength(ch)
        li = min(1.0, max(0.0, (u - 0.04 - i * 0.012) / 0.12))
        dy = (1 - ease("out_back", li)) * 120 + math.sin(t * 6 + i * 0.7) * 6
        if li > 0:
            p.text(x + cw / 2, 4 + dy, ch, f_size, fill=hex2rgba("#FFE14D"), stroke=8, stroke_fill=INK)
        x += cw
    p.text(0, 175, prm.get("sub", ""), 40, fill=(255, 255, 255, 255), stroke=6, stroke_fill=INK, weight="ExtraBold")
    _composite(frame, p.finish(), W / 2, cy, a)


def endcard(frame, prm, u, t):
    a = _fade(u, 0.12, 0.02)
    # dim scene
    dim = Image.new("RGBA", (W, H), (30, 18, 36, int(150 * a)))
    frame.alpha_composite(dim)
    s = ease("out_back", min(1.0, u / 0.25))
    p = Pen(980, 760, origin=(490, 380), scale=max(0.01, s))
    p.rrect(-440, -300, 440, 300, 60, fill=hex2rgba("#2B1D2E"), width=12, outline=(255, 255, 255, 255))
    p.text(0, -190, "N4V3D", 150, fill=hex2rgba("#FFC93C"), stroke=9, stroke_fill=INK)
    p.text(0, -75, "ANIMATION STUDIO", 58, fill=(255, 255, 255, 255), weight="ExtraBold")
    p.rrect(-250, 10, 250, 120, 55, fill=hex2rgba("#E63946"), width=8, outline=(255, 255, 255, 255))
    p.text(0, 66, prm.get("cta", "SUBSCRIBE"), 58, fill=(255, 255, 255, 255))
    p.text(0, 210, prm.get("sub", ""), 38, fill=hex2rgba("#B9F3EC"), weight="ExtraBold")
    _composite(frame, p.finish(), W / 2, prm.get("y", 860), a)


def speedlines(frame, prm, u, t):
    x, y = prm.get("at", (300, 1300))
    d = prm.get("dir", 1)
    p = Pen(700, 500, origin=(350, 250))
    a = int(220 * _fade(u, 0.05, 0.5))
    for k in range(6):
        yy = -180 + k * 70 + (k % 2) * 18
        ln = 160 + 90 * ((k * 37) % 3)
        x0 = -d * (120 + 60 * (k % 3))
        p.stroke([(x0, yy), (x0 - d * ln, yy)], (255, 255, 255, a), 10)
    _composite(frame, p.finish(), x, y)


def flash(frame, prm, u, t):
    a = int(200 * (1 - u))
    frame.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, a)))


OVERLAYS = {"burst": burst, "zzz": zzz, "title": title, "endcard": endcard,
            "speedlines": speedlines, "flash": flash}
