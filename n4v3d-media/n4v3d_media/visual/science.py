"""N4V3D HEALTH & SCIENCE scene library — stylised scientific illustration.

All visuals are simplified educational diagrams (labelled as illustrations),
drawn natively at 1080x1920 with 2x-supersampled vector shapes.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from . import kit
from .kit import Pen, clamp01, hex2rgba, ramp

W, H = 1080, 1920
NAVY_TOP, NAVY_BOT = hex2rgba("#0B1630"), hex2rgba("#060B1A")
EPI, DERMIS, SEBUM = hex2rgba("#F2C4A8"), hex2rgba("#E9A7A3"), hex2rgba("#F5C85C")
BACT, IMMUNE, INFL, ACCENT = hex2rgba("#B266FF"), hex2rgba("#9FE7FF"), hex2rgba("#FF5A5A"), hex2rgba("#5CE1E6")
WHITE = (255, 255, 255, 255)
SURF = 560          # skin surface line in the cross-section
NOOUT = dict(outline=None, width=0)


def lab_background(seed=3):
    bg = kit.vgrad(W, H, NAVY_TOP, NAVY_BOT)
    r = kit.rng(seed)
    for _ in range(26):  # soft bokeh specks
        kit.paste_glow(bg, r.uniform(0, W), r.uniform(0, H), r.uniform(20, 70), (90, 140, 220), alpha=r.uniform(0.05, 0.18))
    return bg


ZC, ZY, ZK = 540, 820, 1.28     # cross-section framing: centre x, centre y, zoom


def S(x, y):
    """Diagram coords -> screen coords under the cross-section camera."""
    return ZC + (x - ZC) * ZK, ZY + (y - ZY) * ZK


def frame_diagram(img, push=0.0):
    k = ZK * (1 + push)
    return kit.zoom(img, k, ZC, ZY, (W, H))


class Scene:
    sfx: list = []

    def __init__(self, dur, seg, prod):
        self.dur, self.seg, self.prod = dur, seg, prod
        self.setup()

    def setup(self):
        pass

    def frame(self, t):  # -> RGBA W x H
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Cross-section of skin with a hair follicle + sebaceous glands (shared asset)
# ---------------------------------------------------------------------------
CANAL_L = [(500, SURF), (512, 640), (516, 760), (518, 900), (520, 1060)]
CANAL_R = [(580, SURF), (568, 640), (564, 760), (562, 900), (560, 1060)]
GLAND_R = [(640, 790, 50), (692, 828, 42), (652, 862, 40), (706, 772, 34)]
GLAND_L = [(438, 842, 36), (400, 876, 30), (430, 900, 28)]
SEBUM_PATH = [(690, 815), (640, 805), (600, 798), (560, 790), (548, 700), (544, 620), (540, 575)]


def _path_point(path, p):
    seglens = [math.dist(a, b) for a, b in zip(path, path[1:])]
    total = sum(seglens)
    d = p * total
    for (a, b), L in zip(zip(path, path[1:]), seglens):
        if d <= L:
            k = d / L if L else 0
            return a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k
        d -= L
    return path[-1]


def cross_section(plugged=0.0):
    """Static cross-section plate (RGBA, full frame)."""
    img = lab_background()
    p = Pen(W, H, origin=(0, 0))
    # dermis + epidermis bands with soft fade at the bottom
    der = kit.vgrad(W, 620, (*DERMIS[:3], 235), (*kit.mix(DERMIS, (60, 20, 40, 255), 0.55)[:3], 0))
    img.alpha_composite(der, (0, 700))
    epi = kit.vgrad(W, 140, (*EPI[:3], 255), (*kit.mix(EPI, DERMIS, 0.6)[:3], 255))
    img.alpha_composite(epi, (0, SURF + 20))
    p.rrect(-20, SURF - 6, W + 20, SURF + 22, 6, fill=hex2rgba("#F8DCC8"), **NOOUT)
    # epidermal cell texture
    r = kit.rng(11)
    for _ in range(170):
        x, y = r.uniform(0, W), r.uniform(SURF + 30, 690)
        if 470 < x < 610:
            continue
        p.ellipse(x, y, r.uniform(12, 20), r.uniform(7, 11), fill=(255, 235, 220, 70), outline=(200, 140, 120, 60), width=1.5)
    # collagen fibres + capillaries
    for k in range(14):
        y0 = 760 + k * 34 + r.uniform(-10, 10)
        pts = [(x, y0 + 10 * math.sin(x / 70 + k)) for x in range(-20, W + 40, 40)]
        p.stroke(pts, (255, 220, 220, 45), 3)
    for cx, cy in ((200, 960), (880, 1010), (330, 1120), (780, 1150)):
        pts = [(cx + 120 * math.cos(a) * 0.9, cy + 26 * math.sin(a * 2)) for a in np.linspace(-1.6, 1.6, 20)]
        p.stroke(pts, hex2rgba("#C0394B", 200), 7)
    # glands
    for (gx, gy, gr) in GLAND_L + GLAND_R:
        p.circle(gx, gy, gr, fill=SEBUM, outline=hex2rgba("#B8862E"), width=5)
        p.circle(gx - gr * 0.25, gy - gr * 0.25, gr * 0.45, fill=(255, 236, 170, 150), **NOOUT)
    p.stroke([(604, 800), (562, 792)], hex2rgba("#B8862E"), 26)
    p.stroke([(604, 800), (562, 792)], SEBUM, 16)
    p.stroke([(468, 850), (520, 830)], hex2rgba("#B8862E"), 20)
    p.stroke([(468, 850), (520, 830)], SEBUM, 11)
    # follicle canal + bulb
    canal = CANAL_L + CANAL_R[::-1]
    p.poly(canal, fill=hex2rgba("#FBE6D6"), **NOOUT)
    p.ellipse(540, 1100, 58, 48, fill=hex2rgba("#E9B7A0"), outline=hex2rgba("#B9735E"), width=6)
    p.stroke(CANAL_L, hex2rgba("#B9735E"), 7)
    p.stroke(CANAL_R, hex2rgba("#B9735E"), 7)
    # hair shaft
    p.curve([(540, 1095), (546, 820), (546, 600), (590, 380)], hex2rgba("#3A2418"), 13, n=40)
    img.alpha_composite(p.finish())
    img.alpha_composite(kit.vignette(W, H, 0.5))
    return img


def draw_sebum(img, t, rate=1.0, n=26, stop_at=None, seed=5):
    d = ImageDraw.Draw(img)
    r = kit.rng(seed)
    phases = r.random(n)
    speeds = r.uniform(0.18, 0.28, n)
    for i in range(int(n * min(1.0, rate))):
        ph = (phases[i] + t * speeds[i] * (0.6 + 0.4 * rate)) % 1.0
        if stop_at is not None:
            ph = min(ph, stop_at + 0.02 * (i % 5))
        x, y = _path_point(SEBUM_PATH, ph)
        x += 3 * math.sin(t * 3 + i)
        s = 7 + 3 * math.sin(i)
        d.ellipse([x - s, y - s, x + s, y + s], fill=(*SEBUM[:3], 235), outline=(190, 140, 40, 255), width=2)


# ---------------------------------------------------------------------------
class PoreZoom(Scene):
    """Macro skin surface, slow push into one pore, iris into the pore."""
    sfx = [(0.0, "whoosh", 0.35)]

    def setup(self):
        tw, th = int(W * 1.5), int(H * 1.5)
        n = kit.noise_texture(tw // 2, th // 2, 21, ((6, 0.35), (24, 0.35), (90, 0.3)))
        n = np.asarray(Image.fromarray((n * 255).astype(np.uint8)).resize((tw, th), Image.BICUBIC), np.float32) / 255
        base = np.array([236, 182, 150], np.float32)
        dark = np.array([196, 128, 104], np.float32)
        yy, xx = np.mgrid[0:th, 0:tw].astype(np.float32)
        light = 1.05 - 0.25 * (xx / tw * 0.6 + yy / th * 0.4)
        rgb = (dark + (base - dark) * n[..., None]) * light[..., None]
        tex = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
        p = Pen(tw, th, origin=(0, 0), ss=1)
        r = kit.rng(4)
        for _ in range(420):
            x, y = r.uniform(0, tw), r.uniform(0, th)
            s = r.uniform(3, 7)
            p.ellipse(x, y, s * 1.3, s, fill=(120, 60, 50, 120), **NOOUT)
        for _ in range(900):  # fine skin lines
            x, y = r.uniform(0, tw), r.uniform(0, th)
            a = r.uniform(0, math.pi)
            L = r.uniform(30, 90)
            p.stroke([(x, y), (x + L * math.cos(a), y + L * math.sin(a))], (170, 100, 85, 40), 2, caps=False)
        tex.alpha_composite(p.finish())
        self.cx, self.cy = tw / 2, th / 2 - 60
        hero = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
        hp = Pen(300, 300, origin=(150, 150))
        hp.ellipse(0, 0, 46, 38, fill=(150, 80, 66, 255), **NOOUT)
        hp.ellipse(0, 4, 30, 24, fill=(70, 30, 30, 255), **NOOUT)
        hp.ellipse(-12, -14, 22, 8, fill=(255, 230, 210, 110), **NOOUT)
        tex.alpha_composite(kit.blur(hp.finish(), 1.2), (int(self.cx - 150), int(self.cy - 150)))
        self.tex = tex

    def frame(self, t):
        u = t / self.dur
        s = 1.0 + 3.6 * kit.ease("in_out", u) ** 1.4
        img = kit.zoom(self.tex, s, self.cx, self.cy, (W, H))
        img.alpha_composite(kit.vignette(W, H, 0.65))
        kit.badge(img, "SKIN SURFACE · MAGNIFIED ILLUSTRATION", y=300, alpha=1 - ramp(u, 0.7, 0.85))
        if u > 0.82:  # iris into the pore
            k = ramp(u, 0.82, 1.0)
            m = Image.new("L", (W, H), 255)
            rr = max(1, int(1300 * (1 - k)))
            ImageDraw.Draw(m).ellipse([W / 2 - rr, H / 2 - rr, W / 2 + rr, H / 2 + rr], fill=0)
            dark = Image.new("RGBA", (W, H), NAVY_BOT)
            img = Image.composite(dark, img, m)
        return img


class QuestionCard(Scene):
    sfx = [(0.02, "whoosh", 0.25)]

    def setup(self):
        bg = lab_background(9)
        self.bg = bg

    def frame(self, t):
        u = t / self.dur
        img = self.bg.copy()
        kit.paste_glow(img, 540, 760, 420, ACCENT, alpha=0.18)
        txt = self.seg.get("onscreen", "WHAT ACTUALLY CAUSES ACNE?")
        kit.kinetic_title(img, 540, 760, txt, 118, u * 1.6, accent=({"ACNE?", "ACNE"}, ACCENT))
        kit.pill(img, 540, 1060, "ONE OF THE MOST COMMON SKIN CONDITIONS", 28, alpha=ramp(u, 0.35, 0.55),
                 bg=(255, 255, 255, 28), outline=(255, 255, 255, 60))
        return img


class FollicleSebum(Scene):
    sfx = [(0.05, "whoosh", 0.3), (0.58, "swell", 0.35)]

    def setup(self):
        self.base = cross_section()

    def frame(self, t):
        u = t / self.dur
        img = self.base.copy()
        boost = ramp(u, 0.55, 0.7)
        for (gx, gy, gr) in GLAND_R + GLAND_L:
            kit.paste_glow(img, gx, gy, gr * 2.2, SEBUM, alpha=0.25 + 0.5 * boost)
        draw_sebum(img, t, rate=0.45 + 0.55 * boost)
        img = frame_diagram(img)
        kit.callout(img, *S(540, SURF + 4), 250, 380, "Pore", ramp(u, 0.02, 0.15))
        kit.callout(img, *S(518, 960), 250, 1100, "Hair follicle", ramp(u, 0.12, 0.27))
        kit.callout(img, *S(700, 830), 800, 1080, "Oil gland", ramp(u, 0.25, 0.42), sub="makes sebum", color=SEBUM)
        kit.pill(img, 540, 300, "ANDROGENS ↑  →  MORE SEBUM", 32, alpha=boost, fg=(20, 20, 30, 255),
                 bg=(*SEBUM[:3], 235))
        kit.badge(img, "SIMPLIFIED CROSS-SECTION · ILLUSTRATION", y=300, alpha=1 - boost)
        return img


class PlugForms(Scene):
    sfx = [(0.1, "whoosh", 0.2), (0.62, "pop", 0.25)]

    def setup(self):
        self.base = cross_section()
        r = kit.rng(31)
        n = 70
        self.flakes = [(r.choice([514, 566]) + r.uniform(-4, 4), r.uniform(620, 1020), r.uniform(0, 180),
                        r.uniform(0.0, 0.75), 545 + r.uniform(-26, 26), r.uniform(580, 690)) for _ in range(n)]

    def frame(self, t):
        u = t / self.dur
        img = self.base.copy()
        fill = ramp(u, 0.35, 0.95)
        # sebum backs up behind the forming plug
        if fill > 0:
            back = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            bp = Pen(W, H, origin=(0, 0))
            ytop = 640
            ybot = 640 + 260 * fill
            bp.poly([(514, ytop), (566, ytop), (564, ybot), (516, ybot)], fill=(*SEBUM[:3], 170), **NOOUT)
            back.alpha_composite(bp.finish())
            img.alpha_composite(back)
        draw_sebum(img, t, rate=0.6, stop_at=0.80 if u > 0.4 else None)
        p = Pen(W, H, origin=(0, 0))
        for (x0, y0, a0, start, x1, y1) in self.flakes:
            k = ramp(u, start, start + 0.3)
            x = x0 + (x1 - x0) * k
            y = y0 + (y1 - y0) * k
            a = math.radians(a0 + 200 * k)
            pts = [(x + 14 * math.cos(a + q) * (1 if i % 2 else 0.5), y + 14 * math.sin(a + q) * (1 if i % 2 else 0.5))
                   for i, q in enumerate(np.linspace(0, 2 * math.pi, 6, endpoint=False))]
            p.poly(pts, fill=(240, 228, 206, 240), outline=(150, 120, 90, 255), width=2.5)
        img.alpha_composite(p.finish())
        cap = ramp(u, 0.55, 0.8)
        if cap > 0:
            kit.paste_glow(img, 540, 600, 120, SEBUM, alpha=0.35 * cap)
        img = frame_diagram(img)
        kit.callout(img, *S(516, 800), 250, 960, "Dead skin cells", ramp(u, 0.05, 0.2), color=(245, 235, 215, 255))
        kit.callout(img, *S(560, 610), 780, 380, "Plug forms", ramp(u, 0.6, 0.78), sub="cells + oil", color=SEBUM)
        return img


class Bacteria(Scene):
    sfx = [(0.03, "whoosh", 0.3), (0.55, "whoosh", 0.25)]

    def setup(self):
        n = kit.noise_texture(380, 380, 41, ((10, 0.5), (40, 0.5)))
        a = np.array([248, 214, 120], np.float32)
        b = np.array([226, 168, 96], np.float32)
        rgb = b + (a - b) * n[..., None]
        self.matrix = Image.fromarray(rgb.astype(np.uint8), "RGB").convert("RGBA").resize((760, 760), Image.BICUBIC)
        r = kit.rng(7)
        self.bugs = [(r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(0, math.pi), r.uniform(0.6, 1.2)) for _ in range(90)]
        self.bg = lab_background(13)

    def lens(self, img, cx, cy, rad, count, t, label=None, lab_alpha=1.0):
        rad = int(rad)
        m = self.matrix.resize((rad * 2, rad * 2), Image.BICUBIC)
        lay = Image.new("RGBA", (rad * 2, rad * 2), (0, 0, 0, 0))
        lay.alpha_composite(m)
        lp = Pen(rad * 2, rad * 2, origin=(rad, rad))
        k = rad / 380
        shown = 0
        for (bx, by, ang, sc) in self.bugs:
            if bx * bx + by * by > 0.82:
                continue
            if shown >= count:
                break
            shown += 1
            x, y = bx * rad * 0.9, by * rad * 0.9
            a = ang + 0.25 * math.sin(t * 2 + bx * 5)
            L = 34 * sc * k
            x += 4 * k * math.sin(t * 1.7 + by * 9)
            p0 = (x - L * math.cos(a), y - L * math.sin(a))
            p1 = (x + L * math.cos(a), y + L * math.sin(a))
            lp.stroke([p0, p1], (70, 20, 110, 255), 26 * k + 4)
            lp.stroke([p0, p1], BACT, 26 * k)
            lp.stroke([(p0[0] * 0.7 + x * 0.3, p0[1] * 0.7 + y * 0.3), (x, y)], (220, 180, 255, 160), 7 * k, caps=True)
        lay.alpha_composite(lp.finish())
        mask = Image.new("L", lay.size, 0)
        ImageDraw.Draw(mask).ellipse([0, 0, rad * 2 - 1, rad * 2 - 1], fill=255)
        lay.putalpha(Image.fromarray(np.minimum(np.asarray(lay.getchannel("A")), np.asarray(mask))))
        kit.paste_glow(img, cx, cy, rad * 1.35, BACT, alpha=0.35)
        img.alpha_composite(lay, (int(cx - rad), int(cy - rad)))
        ring = Pen(rad * 2 + 40, rad * 2 + 40, origin=(rad + 20, rad + 20))
        ring.circle(0, 0, rad, fill=None, outline=(230, 240, 255, 230), width=8)
        img.alpha_composite(ring.finish(), (int(cx - rad - 20), int(cy - rad - 20)))
        if label:
            kit.text(img, cx, cy + rad + 50, label, 36, alpha=lab_alpha)

    def frame(self, t):
        u = t / self.dur
        img = self.bg.copy()
        split = ramp(u, 0.5, 0.66)
        count = int(10 + 70 * ramp(u, 0.05, 0.45))
        if split < 1:
            cx = 540 - 250 * split
            rad = 390 - 160 * split
            self.lens(img, cx, 780, rad, count, t)
            kit.text(img, 540, 300, "Cutibacterium acnes", 52, weight="Black", alpha=(1 - split) * ramp(u, 0.05, 0.15))
            kit.badge(img, "MICROSCOPE VIEW · ILLUSTRATION", y=1230, alpha=1 - split)
        if split > 0:
            self.lens(img, 290, 760, 230, 34, t, "ACNE-PRONE SKIN", split)
            self.lens(img, 790, 760, 230, 30, t + 1.3, "HEALTHY SKIN", split)
            kit.text(img, 540, 330, "Most common bacterium", 54, weight="Black", alpha=ramp(u, 0.62, 0.75))
            kit.text(img, 540, 400, "on healthy skin, too", 54, weight="Black", fill=(*BACT[:3], 255), alpha=ramp(u, 0.66, 0.8))
        return img


class Inflammation(Scene):
    sfx = [(0.1, "swell", 0.45)]

    def setup(self):
        self.base = cross_section()
        r = kit.rng(17)
        self.cells = [((r.choice([200, 880, 330, 780]) + r.uniform(-60, 60), r.uniform(950, 1150)),
                       (540 + r.uniform(-120, 120), r.uniform(600, 820)), r.uniform(0.05, 0.45)) for _ in range(16)]

    def frame(self, t):
        u = t / self.dur
        img = self.base.copy()
        heat = ramp(u, 0.15, 0.75)
        kit.paste_glow(img, 540, 680, 120 + 260 * heat, INFL, alpha=0.75 * heat)
        p = Pen(W, H, origin=(0, 0))
        # plug
        p.rrect(514, 575, 566, 690, 20, fill=(236, 214, 170, 255), outline=(150, 110, 70, 255), width=3)
        # immune cells migrating
        for (a, b, st) in self.cells:
            k = ramp(u, st, st + 0.4)
            x = a[0] + (b[0] - a[0]) * k + 6 * math.sin(t * 3 + st * 20)
            y = a[1] + (b[1] - a[1]) * k
            p.circle(x, y, 17, fill=(*IMMUNE[:3], 230), outline=(40, 110, 140, 255), width=3)
            p.circle(x + 4, y - 3, 7, fill=(60, 120, 170, 255), **NOOUT)
        # swelling dome on the surface
        dome = 80 * heat
        if dome > 1:
            pts = [(540 + 190 * math.cos(a), SURF - dome * math.sin(a)) for a in np.linspace(0, math.pi, 40)]
            p.poly(pts + [(350, SURF + 4), (730, SURF + 4)], fill=kit.mix(hex2rgba("#F2B5A6"), INFL, 0.45 * heat), **NOOUT)
            p.ellipse(500, SURF - dome * 0.7, 40, 12, fill=(255, 240, 235, 90), **NOOUT)
        img.alpha_composite(p.finish())
        img = frame_diagram(img)
        kit.callout(img, *S(430, 990), 230, 1150, "Immune cells", ramp(u, 0.1, 0.3), color=IMMUNE)
        kit.callout(img, *S(640, SURF - dome * 0.6), 790, 330, "Inflammation", ramp(u, 0.45, 0.65), sub="red, swollen pimple", color=hex2rgba("#FF8A8A"))
        return img


def _icon(kind, size=150):
    p = Pen(size * 2, size * 2, origin=(size, size))
    if kind == "oil":
        pts = [(0, -70)] + [(52 * math.cos(a), 20 + 52 * math.sin(a)) for a in np.linspace(-0.35, math.pi + 0.35, 24)]
        p.poly(pts, fill=SEBUM, outline=hex2rgba("#B8862E"), width=6)
        p.ellipse(-18, 10, 12, 18, fill=(255, 240, 190, 200), **NOOUT)
    elif kind == "clog":
        p.rrect(-30, -80, 30, 80, 24, fill=hex2rgba("#FBE6D6"), outline=hex2rgba("#B9735E"), width=6)
        p.rrect(-28, -78, 28, -20, 18, fill=(236, 214, 170, 255), outline=(150, 110, 70, 255), width=4)
    elif kind == "bacteria":
        for (x, y, a) in ((-30, -20, 0.4), (25, 10, -0.6), (-10, 40, 1.4)):
            p0 = (x - 34 * math.cos(a), y - 34 * math.sin(a))
            p1 = (x + 34 * math.cos(a), y + 34 * math.sin(a))
            p.stroke([p0, p1], (70, 20, 110, 255), 34)
            p.stroke([p0, p1], BACT, 26)
    elif kind == "inflammation":
        pts = [(0, -80), (40, -10), (30, 50), (0, 70), (-30, 50), (-40, -10)]
        p.poly(pts, fill=INFL, outline=hex2rgba("#8A1C1C"), width=6)
        p.poly([(0, -20), (18, 20), (0, 50), (-18, 20)], fill=hex2rgba("#FFC36B"), **NOOUT)
    return p.finish()


class FourFactors(Scene):
    sfx = [(0.25, "tick", 0.3), (0.33, "tick", 0.3), (0.41, "tick", 0.3), (0.49, "tick", 0.3), (0.68, "ding", 0.25)]

    def setup(self):
        self.bg = lab_background(19)
        self.icons = {k: _icon(k) for k in ("oil", "clog", "bacteria", "inflammation")}

    def frame(self, t):
        u = t / self.dur
        img = self.bg.copy()
        a0 = 1 - ramp(u, 0.2, 0.28)
        if a0 > 0:
            kit.text(img, 540, 760, "DIRTY SKIN?", 110, weight="Black", alpha=a0)
            k = ramp(u, 0.06, 0.16)
            d = ImageDraw.Draw(img)
            d.line([(230, 770), (230 + 620 * k, 750)], fill=(*INFL[:3], int(255 * a0)), width=14)
        cards = [("oil", "OIL", 290, 700), ("clog", "CLOGGING", 790, 700),
                 ("bacteria", "BACTERIA", 290, 1010), ("inflammation", "INFLAMMATION", 790, 1010)]
        for i, (k, label, x, y) in enumerate(cards):
            a = ramp(u, 0.24 + i * 0.08, 0.32 + i * 0.08)
            if a <= 0:
                continue
            card = Image.new("RGBA", (440, 280), (0, 0, 0, 0))
            ImageDraw.Draw(card).rounded_rectangle([0, 0, 439, 279], 36, fill=(255, 255, 255, 22), outline=(255, 255, 255, 70), width=2)
            img.alpha_composite(kit.with_alpha(card, a), (x - 220, int(y - 140 + (1 - a) * 30)))
            ic = self.icons[k].resize((180, 180), Image.LANCZOS)
            img.alpha_composite(kit.with_alpha(ic, a), (x - 90, int(y - 120 + (1 - a) * 30)))
            kit.text(img, x, y + 95, label, 40, weight="Black", alpha=a)
        tr = ramp(u, 0.66, 0.8)
        kit.pill(img, 290, 1190, "BENZOYL PEROXIDE", 28, alpha=tr, fg=(20, 20, 30, 255), bg=(*ACCENT[:3], 240))
        kit.pill(img, 790, 1190, "TOPICAL RETINOIDS", 28, alpha=tr, fg=(20, 20, 30, 255), bg=(*ACCENT[:3], 240))
        d = ImageDraw.Draw(img)
        if tr > 0:
            al = int(200 * tr)
            d.line([(290, 1165), (290, 1135)], fill=(*ACCENT[:3], al), width=4)
            d.line([(790, 1165), (790, 1135)], fill=(*ACCENT[:3], al), width=4)
        kit.pill(img, 540, 330, "AAD GUIDELINE 2024 · STRONG RECOMMENDATION", 26, alpha=tr,
                 bg=(255, 255, 255, 30), outline=(255, 255, 255, 80))
        kit.pill(img, 540, 430, "4 FACTORS, WORKING TOGETHER", 34, alpha=ramp(u, 0.3, 0.4) * (1 - tr),
                 bg=(255, 255, 255, 0))
        return img


class HealthEnd(Scene):
    sfx = [(0.05, "whoosh", 0.2)]

    def setup(self):
        self.bg = lab_background(23)

    def frame(self, t):
        u = t / self.dur
        img = self.bg.copy()
        kit.paste_glow(img, 540, 640, 300, ACCENT, alpha=0.2)
        p = Pen(260, 260, origin=(130, 130))
        p.circle(0, 0, 100, fill=(255, 255, 255, 30), outline=(*ACCENT[:3], 255), width=6)
        p.rrect(-20, -62, 20, 62, 6, fill=WHITE, **NOOUT)
        p.rrect(-62, -20, 62, 20, 6, fill=WHITE, **NOOUT)
        a = ramp(u, 0.0, 0.15)
        img.alpha_composite(kit.with_alpha(p.finish(), a), (410, 510))
        kit.text(img, 540, 830, "Painful, scarring,", 62, weight="Black", alpha=ramp(u, 0.05, 0.2))
        kit.text(img, 540, 905, "or not improving?", 62, weight="Black", alpha=ramp(u, 0.1, 0.25))
        kit.text(img, 540, 1000, "See a dermatologist.", 58, fill=(*ACCENT[:3], 255), weight="Black", alpha=ramp(u, 0.2, 0.35))
        kit.text(img, 540, 1110, "Educational content · not medical advice", 28, fill=(200, 210, 230, 255), alpha=ramp(u, 0.3, 0.45))
        kit.text(img, 540, 1160, "Sources in the description", 28, fill=(200, 210, 230, 255), alpha=ramp(u, 0.3, 0.45))
        return img


SCENES = {
    "pore_zoom": PoreZoom, "question_card": QuestionCard, "follicle_sebum": FollicleSebum,
    "plug_forms": PlugForms, "bacteria": Bacteria, "inflammation": Inflammation,
    "four_factors": FourFactors, "health_end": HealthEnd,
}
