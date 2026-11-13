"""Small anti-aliased vector drawing layer on top of Pillow.

Every asset in the studio is drawn with a `Pen`: a supersampled RGBA canvas
with a local coordinate system (origin = the asset's pivot, usually its feet).
Shapes are drawn at SUPERSAMPLE x resolution and downsampled on `finish()`.
"""
from __future__ import annotations

import math
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from . import config

Color = tuple


def hex2rgba(h: str, a: int = 255) -> Color:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def mix(c1: Color, c2: Color, t: float) -> Color:
    return tuple(int(round(a + (b - a) * t)) for a, b in zip(c1, c2))


@lru_cache(maxsize=64)
def font(size: int, weight: str = "Black") -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(config.font_path(weight), size)


def bezier(pts, n: int = 24):
    """Sample a quadratic or cubic bezier curve."""
    out = []
    for i in range(n + 1):
        t = i / n
        if len(pts) == 3:
            (x0, y0), (x1, y1), (x2, y2) = pts
            x = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * x1 + t * t * x2
            y = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * y1 + t * t * y2
        else:
            (x0, y0), (x1, y1), (x2, y2), (x3, y3) = pts
            mt = 1 - t
            x = mt**3 * x0 + 3 * mt * mt * t * x1 + 3 * mt * t * t * x2 + t**3 * x3
            y = mt**3 * y0 + 3 * mt * mt * t * y1 + 3 * mt * t * t * y2 + t**3 * y3
        out.append((x, y))
    return out


class Pen:
    """Supersampled drawing canvas with a local origin.

    w, h      : canvas size in local units (1 unit = 1 output px at scale 1)
    origin    : where local (0, 0) sits inside the canvas, in local units
    scale     : multiplier applied to everything (character size)
    """

    def __init__(self, w: float, h: float, origin, scale: float = 1.0, ss: int = config.SUPERSAMPLE):
        self.scale = scale
        self.ss = ss
        self.k = scale * ss
        self.ox, self.oy = origin
        self.img = Image.new("RGBA", (max(1, int(w * self.k)), max(1, int(h * self.k))), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    # coordinate transform ------------------------------------------------
    def P(self, x, y):
        return ((x + self.ox) * self.k, (y + self.oy) * self.k)

    def W(self, w):
        return max(1, int(round(w * self.k)))

    # primitives -----------------------------------------------------------
    def ellipse(self, cx, cy, rx, ry, fill=None, outline=config.INK, width=config.OUTLINE):
        x0, y0 = self.P(cx - rx, cy - ry)
        x1, y1 = self.P(cx + rx, cy + ry)
        self.d.ellipse([x0, y0, x1, y1], fill=fill, outline=outline if width else None,
                       width=self.W(width) if width else 0)

    def circle(self, cx, cy, r, **kw):
        self.ellipse(cx, cy, r, r, **kw)

    def rrect(self, x0, y0, x1, y1, r, fill=None, outline=config.INK, width=config.OUTLINE):
        a, b = self.P(x0, y0)
        c, d = self.P(x1, y1)
        self.d.rounded_rectangle([a, b, c, d], radius=r * self.k, fill=fill,
                                 outline=outline if width else None, width=self.W(width) if width else 0)

    def poly(self, pts, fill=None, outline=config.INK, width=config.OUTLINE):
        pp = [self.P(x, y) for x, y in pts]
        self.d.polygon(pp, fill=fill)
        if width and outline:
            self.stroke(list(pts) + [pts[0]], outline, width)

    def stroke(self, pts, color=config.INK, width=config.OUTLINE, caps=True):
        pp = [self.P(x, y) for x, y in pts]
        wpx = self.W(width)
        if len(pp) > 1:
            self.d.line(pp, fill=color, width=wpx)
        r = wpx / 2
        # round joints (and caps): fill every vertex with a dot
        verts = pp if caps else pp[1:-1]
        if wpx >= 4:
            for (x, y) in verts:
                self.d.ellipse([x - r, y - r, x + r, y + r], fill=color)

    def curve(self, ctrl, color=config.INK, width=config.OUTLINE, n=24):
        self.stroke(bezier(ctrl, n), color, width)

    def limb(self, ctrl, color, width, outline=config.INK, ow=config.OUTLINE):
        """A tube (arm/leg) with an ink outline: thick ink stroke + coloured core."""
        pts = bezier(ctrl, 20)
        self.stroke(pts, outline, width + 2 * ow)
        self.stroke(pts, color, width)

    def text(self, x, y, s, size, fill=config.INK, weight="Black", anchor="mm",
             stroke=0, stroke_fill=config.INK, angle=0.0):
        f = font(int(size * self.k), weight)
        if not angle:
            self.d.text(self.P(x, y), s, font=f, fill=fill, anchor=anchor,
                        stroke_width=self.W(stroke) if stroke else 0, stroke_fill=stroke_fill)
            return
        # rotated text: render on its own layer
        tmp = Image.new("RGBA", (int(len(s) * size * self.k * 1.2) + 40, int(size * self.k * 2) + 40), (0, 0, 0, 0))
        td = ImageDraw.Draw(tmp)
        td.text((tmp.width / 2, tmp.height / 2), s, font=f, fill=fill, anchor="mm",
                stroke_width=self.W(stroke) if stroke else 0, stroke_fill=stroke_fill)
        tmp = tmp.rotate(angle, resample=Image.BICUBIC, expand=True)
        px, py = self.P(x, y)
        self.img.alpha_composite(tmp, (int(px - tmp.width / 2), int(py - tmp.height / 2)))

    def paste(self, other: "Image.Image", x, y):
        """Composite an already-supersampled RGBA image centered at local (x, y)."""
        px, py = self.P(x, y)
        self.img.alpha_composite(other, (int(px - other.width / 2), int(py - other.height / 2)))

    # output ---------------------------------------------------------------
    def finish(self) -> Image.Image:
        if self.ss == 1:
            return self.img
        w, h = self.img.size
        return self.img.resize((max(1, w // self.ss), max(1, h // self.ss)), Image.LANCZOS)

    def origin_px(self):
        """Pixel position of local (0,0) in the finished (downsampled) image."""
        return (self.ox * self.scale, self.oy * self.scale)


def star_points(cx, cy, r_out, r_in, n=5, rot=-90.0):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(rot + i * 180.0 / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts
