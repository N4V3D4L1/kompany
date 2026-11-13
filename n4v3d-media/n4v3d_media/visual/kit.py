"""Shared visual toolkit for educational scenes (native-resolution, anti-aliased)."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from n4v3d.anim import ease
from n4v3d.gfx import Pen, font, hex2rgba, mix  # noqa: F401  (re-exported)

INK = (12, 18, 34, 255)


def clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def ramp(u, a, b):
    """0 before a, 1 after b, eased in between."""
    if b <= a:
        return 1.0 if u >= b else 0.0
    return ease("in_out", clamp01((u - a) / (b - a)))


def vgrad(w, h, top, bottom):
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    a = np.array(top, np.float32)
    b = np.array(bottom, np.float32)
    rows = (a + (b - a) * t)[:, None, :].repeat(w, axis=1)
    return Image.fromarray(rows.astype(np.uint8), "RGBA" if len(top) == 4 else "RGB").convert("RGBA")


@lru_cache(maxsize=64)
def glow(radius: int, color: tuple, strength: float = 1.0) -> Image.Image:
    """Soft radial glow sprite (cached)."""
    size = radius * 2
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    d = np.sqrt((xx - radius) ** 2 + (yy - radius) ** 2) / radius
    a = np.clip(1 - d, 0, 1) ** 2.2 * 255 * strength
    arr = np.zeros((size, size, 4), np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = color[0], color[1], color[2]
    arr[..., 3] = np.clip(a, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def paste_glow(img, x, y, radius, color, alpha=1.0):
    g = glow(int(radius), tuple(color[:3]))
    if alpha < 0.999:
        g = g.copy()
        g.putalpha(g.getchannel("A").point(lambda v: int(v * alpha)))
    img.alpha_composite(g, (int(x - radius), int(y - radius)))


def vignette(w, h, strength=0.55):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    a = np.clip((d - 0.55) / 0.9, 0, 1) ** 1.6 * 255 * strength
    arr = np.zeros((h, w, 4), np.uint8)
    arr[..., 3] = a.astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def with_alpha(img, a):
    if a >= 0.999:
        return img
    out = img.copy()
    out.putalpha(out.getchannel("A").point(lambda v: int(v * max(0.0, a))))
    return out


def zoom(img, scale, cx, cy, out_size):
    """Ken-Burns crop: return `out_size` view of img scaled by `scale` around (cx, cy) in img coords."""
    W, H = out_size
    cw = img.width / scale
    ch = cw * H / W
    x0 = min(max(cx - cw / 2, 0), img.width - cw)
    y0 = min(max(cy - ch / 2, 0), img.height - ch)
    return img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))


def text(img, x, y, s, size, fill=(255, 255, 255, 255), weight="ExtraBold", anchor="mm", alpha=1.0,
         shadow=True, stroke=0, stroke_fill=(10, 14, 28, 255)):
    if alpha <= 0.01 or not s:
        return
    d = ImageDraw.Draw(img)
    f = font(int(size), weight)
    fill = (*fill[:3], int(fill[3] * alpha) if len(fill) == 4 else int(255 * alpha))
    if shadow:
        d.text((x + 3, y + 4), s, font=f, fill=(0, 0, 0, int(110 * alpha)), anchor=anchor,
               stroke_width=stroke, stroke_fill=(0, 0, 0, int(110 * alpha)))
    d.text((x, y), s, font=f, fill=fill, anchor=anchor, stroke_width=stroke,
           stroke_fill=(*stroke_fill[:3], int(255 * alpha)))


def text_width(s, size, weight="ExtraBold"):
    return font(int(size), weight).getlength(s)


def kinetic_title(img, cx, cy, s, size, u, color=(255, 255, 255, 255), accent=None, weight="Black",
                  max_w=940, line_gap=1.12, stagger=0.06):
    """Word-by-word rise-in title, wrapped to max_w. `accent` = (word_set, color)."""
    words = s.split()
    lines, cur = [], []
    for w in words:
        if cur and text_width(" ".join(cur + [w]), size, weight) > max_w:
            lines.append(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(cur)
    total_h = len(lines) * size * line_gap
    y = cy - total_h / 2 + size * line_gap / 2
    k = 0
    for ln in lines:
        lw = text_width(" ".join(ln), size, weight)
        x = cx - lw / 2
        for w in ln:
            ww = text_width(w, size, weight)
            p = clamp01((u - k * stagger) / 0.18)
            e = ease("out_back", p)
            col = color
            if accent and w.strip("?.,!").upper() in accent[0]:
                col = accent[1]
            text(img, x + ww / 2, y + (1 - e) * 40, w, size, fill=col, weight=weight, alpha=p)
            x += ww + text_width(" ", size, weight)
            k += 1
        y += size * line_gap


def pill(img, x, y, s, size=30, fg=(255, 255, 255, 255), bg=(255, 255, 255, 40), alpha=1.0, anchor="mm",
         outline=None, weight="ExtraBold", pad=(22, 12)):
    if alpha <= 0.01:
        return (0, 0)
    w = text_width(s, size, weight) + pad[0] * 2
    h = size + pad[1] * 2
    if anchor == "mm":
        x0, y0 = x - w / 2, y - h / 2
    elif anchor == "lm":
        x0, y0 = x, y - h / 2
    else:
        x0, y0 = x - w, y - h / 2
    layer = Image.new("RGBA", (int(w) + 4, int(h) + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([1, 1, w + 1, h + 1], radius=h / 2, fill=(*bg[:3], int(bg[3] * alpha)),
                        outline=(*outline[:3], int(outline[3] * alpha)) if outline else None, width=2 if outline else 0)
    d.text((w / 2 + 1, h / 2 + 1), s, font=font(size, weight), fill=(*fg[:3], int(fg[3] * alpha)), anchor="mm")
    img.alpha_composite(layer, (int(x0), int(y0)))
    return (w, h)


def callout(img, px, py, lx, ly, label, u, color=(255, 255, 255, 255), size=32, sub=None):
    """Animated leader line from point (px,py) to label at (lx,ly). u: 0..1 reveal."""
    if u <= 0.01:
        return
    d = ImageDraw.Draw(img)
    a = int(255 * clamp01(u * 2))
    r = 7
    d.ellipse([px - r, py - r, px + r, py + r], fill=(*color[:3], a))
    d.ellipse([px - r * 2.2, py - r * 2.2, px + r * 2.2, py + r * 2.2], outline=(*color[:3], a // 2), width=2)
    lu = clamp01((u - 0.1) / 0.5)
    ex, ey = px + (lx - px) * lu, py + (ly - py) * lu
    d.line([(px, py), (ex, ey)], fill=(*color[:3], a), width=3)
    if u > 0.45:
        al = clamp01((u - 0.45) / 0.3)
        tw = max(text_width(label, size), text_width(sub, int(size * 0.66)) if sub else 0)
        if lx >= px:  # label to the right of its leader line; keep inside the frame
            tx = min(lx + 14, img.width - 40 - tw)
            anchor = "lm"
        else:
            tx = max(lx - 14, 40 + tw)
            anchor = "rm"
        text(img, tx, ly - (12 if sub else 0), label, size, fill=color, anchor=anchor, alpha=al)
        if sub:
            text(img, tx, ly + size * 0.75, sub, int(size * 0.66), fill=(220, 230, 245, 255),
                 weight="ExtraBold", anchor=anchor, alpha=al * 0.9)


def badge(img, s, x=540, y=300, alpha=1.0):
    pill(img, x, y, s, size=24, fg=(255, 255, 255, 230), bg=(10, 10, 20, 150), alpha=alpha,
         outline=(255, 255, 255, 90), pad=(18, 9))


def rng(seed):
    return np.random.default_rng(seed)


def noise_texture(w, h, seed, scales=((8, 0.5), (32, 0.3), (128, 0.2))):
    """Smooth value-noise in 0..1 (sum of upsampled random grids)."""
    r = rng(seed)
    acc = np.zeros((h, w), np.float32)
    for cell, amp in scales:
        gw, gh = max(2, w // cell + 2), max(2, h // cell + 2)
        g = Image.fromarray((r.random((gh, gw)) * 255).astype(np.uint8), "L").resize((w, h), Image.BICUBIC)
        acc += np.asarray(g, np.float32) / 255 * amp
    acc -= acc.min()
    return acc / (acc.max() or 1)


def blur(img, r):
    return img.filter(ImageFilter.GaussianBlur(r))
