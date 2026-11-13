"""N4V3D WORLD scene library — painterly historical reconstruction (always labelled)."""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from . import kit
from .kit import Pen, hex2rgba, ramp
from .science import Scene  # shared base class

W, H = 1080, 1920
NO = dict(outline=None, width=0)
GOLD, SILVER, CLAY = hex2rgba("#FFD27A"), hex2rgba("#D9DDE3"), hex2rgba("#B98A5E")
WHITE = (255, 255, 255, 255)
RECON = "ARTISTIC RECONSTRUCTION"


def sky(top="#1B1033", mid="#7A2F5C", low="#F09A55", horizon=1180):
    a = kit.vgrad(W, horizon // 2, hex2rgba(top), hex2rgba(mid))
    b = kit.vgrad(W, H - horizon // 2, hex2rgba(mid), hex2rgba(low))
    img = Image.new("RGBA", (W, H))
    img.paste(a, (0, 0))
    img.paste(b, (0, horizon // 2))
    return img


def dusk_bg(seed=1):
    img = kit.vgrad(W, H, hex2rgba("#24162E"), hex2rgba("#0D0812"))
    r = kit.rng(seed)
    for _ in range(18):
        kit.paste_glow(img, r.uniform(0, W), r.uniform(0, H), r.uniform(40, 120), (255, 170, 90), alpha=r.uniform(0.04, 0.12))
    return img


def clay_tablet(w, h, seed=3, marks=0, rows=7):
    """Clay tablet sprite with `marks` cuneiform-style wedge impressions (illustrative)."""
    n = kit.noise_texture(w // 2, h // 2, seed, ((6, 0.5), (24, 0.5)))
    n = np.asarray(Image.fromarray((n * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255
    a = np.array([196, 150, 104], np.float32)
    b = np.array([150, 108, 72], np.float32)
    rgb = b + (a - b) * n[..., None]
    tex = Image.fromarray(rgb.astype(np.uint8), "RGB").convert("RGBA")
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=min(w, h) * 0.12, fill=255)
    tex.putalpha(mask)
    p = Pen(w, h, origin=(0, 0))
    p.rrect(4, 4, w - 4, h - 4, min(w, h) * 0.12, fill=None, outline=(110, 74, 46, 255), width=6)
    p.rrect(14, 14, w - 14, h * 0.3, min(w, h) * 0.08, fill=(255, 235, 200, 30), **NO)
    r = kit.rng(seed + 9)
    per_row = 9
    k = 0
    for row in range(rows):
        y = h * 0.12 + row * (h * 0.78 / rows)
        p.stroke([(w * 0.06, y + h * 0.05), (w * 0.94, y + h * 0.05)], (120, 84, 56, 160), 3, caps=False)
        x = w * 0.1
        for _ in range(per_row):
            if k >= marks:
                break
            s = r.uniform(0.7, 1.1) * w * 0.03
            if r.random() < 0.6:
                p.poly([(x, y), (x + s * 1.6, y + s * 0.5), (x, y + s)], fill=(92, 60, 38, 255), **NO)
                p.stroke([(x + s * 0.4, y + s * 0.5), (x + s * 2.4, y + s * 0.5)], (92, 60, 38, 255), 4)
            else:
                p.poly([(x, y), (x + s, y), (x + s * 0.5, y + s * 1.6)], fill=(92, 60, 38, 255), **NO)
            x += r.uniform(0.07, 0.1) * w
            k += 1
    tex.alpha_composite(p.finish())
    return tex


class MesopotamiaCity(Scene):
    sfx = [(0.0, "wind", 0.35), (0.6, "chime", 0.25)]

    def setup(self):
        self.sky = sky()
        kit.paste_glow(self.sky, 690, 1110, 420, (255, 190, 110), alpha=0.55)
        sp = Pen(W, H, origin=(0, 0))
        sp.circle(690, 1120, 70, fill=(255, 226, 160, 255), **NO)
        self.sky.alpha_composite(sp.finish())
        # far: ziggurat + city wall
        far = Pen(W, H, origin=(0, 0))
        base_y = 1200
        col = hex2rgba("#4A2647")
        for i, (w_, h_) in enumerate(((560, 70), (430, 70), (310, 66), (200, 60))):
            y1 = base_y - sum(x[1] for x in ((560, 70), (430, 70), (310, 66), (200, 60))[:i])
            far.poly([(560 - w_ / 2, y1), (560 + w_ / 2, y1), (560 + w_ / 2 - 18, y1 - h_), (560 - w_ / 2 + 18, y1 - h_)], fill=col, **NO)
            far.poly([(560 + w_ / 2 - 18, y1 - h_), (560 + w_ / 2, y1), (560 + w_ / 2 - 30, y1)], fill=(255, 170, 110, 70), **NO)
        far.rrect(540, base_y - 296, 580, base_y - 266, 4, fill=hex2rgba("#3A1D38"), **NO)
        far.poly([(530, base_y), (590, base_y), (575, base_y - 266), (545, base_y - 266)], fill=hex2rgba("#5A3052"), **NO)
        far.rrect(-20, base_y - 40, W + 20, base_y + 10, 0, fill=hex2rgba("#3B1F3A"), **NO)
        for x in range(0, W, 54):
            far.rrect(x, base_y - 58, x + 30, base_y - 38, 2, fill=hex2rgba("#3B1F3A"), **NO)
        self.far = far.finish()
        # mid: houses + palms
        mid = Pen(W, H, origin=(0, 0))
        r = kit.rng(5)
        x = -40
        while x < W + 40:
            w_ = r.uniform(90, 170)
            h_ = r.uniform(90, 170)
            y = 1290
            mid.rrect(x, y - h_, x + w_, y, 6, fill=hex2rgba("#6E3C35"), **NO)
            mid.rrect(x + w_ * 0.65, y - h_, x + w_, y, 4, fill=hex2rgba("#A9603F"), **NO)  # sunlit side
            mid.rrect(x + w_ * 0.25, y - 52, x + w_ * 0.42, y, 8, fill=hex2rgba("#2A1520"), **NO)
            if r.random() < 0.6:
                mid.rrect(x + w_ * 0.12, y - h_ + 26, x + w_ * 0.24, y - h_ + 44, 3, fill=hex2rgba("#2A1520"), **NO)
            x += w_ + r.uniform(-10, 12)
        for px in (90, 330, 860, 1010):
            trunk = [(px, 1300), (px + 10, 1150), (px + 24, 1010)]
            mid.curve(trunk, hex2rgba("#2A1830"), 16)
            for a in np.linspace(-2.8, -0.3, 7):
                tip = (px + 24 + 110 * math.cos(a), 1010 + 60 * math.sin(a) + 40)
                mid.curve([(px + 24, 1010), (px + 24 + 60 * math.cos(a), 990 + 40 * math.sin(a)), tip], hex2rgba("#2A1830"), 12)
        self.mid = mid.finish()
        # fore: river + reeds + bank
        fore = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        river = kit.vgrad(W, 170, hex2rgba("#C8724A"), hex2rgba("#3B4E6E"))
        fore.alpha_composite(river, (0, 1290))
        fp = Pen(W, H, origin=(0, 0))
        for k in range(14):
            y = 1300 + k * 11
            fp.stroke([(640 - 60 + k * 4, y), (740 + 40 - k * 4, y)], (255, 215, 150, 150 - k * 8), 4, caps=False)
        fp.poly([(-20, 1460), (W + 20, 1440), (W + 20, H + 10), (-20, H + 10)], fill=hex2rgba("#1A0F1F"), **NO)
        for x in range(0, W, 26):
            hgt = 60 + 50 * math.sin(x * 0.13)
            fp.curve([(x, 1470), (x + 6, 1470 - hgt * 0.5), (x + 14, 1470 - hgt)], hex2rgba("#1A0F1F"), 6)
        fore.alpha_composite(fp.finish())
        self.fore = fore
        self.tablet = clay_tablet(300, 380, seed=8, marks=26, rows=5)

    def frame(self, t):
        u = t / self.dur
        e = kit.ease("in_out", u)
        img = kit.zoom(self.sky, 1.0 + 0.02 * e, 540, 1000, (W, H))
        for layer, k in ((self.far, 0.05), (self.mid, 0.09), (self.fore, 0.15)):
            img.alpha_composite(kit.zoom(layer, 1.0 + k * e, 560, 1150, (W, H)))
        r = kit.rng(2)
        d = ImageDraw.Draw(img)
        for i in range(40):  # drifting dust in the light
            x = (r.uniform(0, W) + t * 18 * r.uniform(0.5, 1.5)) % W
            y = r.uniform(500, 1300) + 10 * math.sin(t + i)
            s = r.uniform(1.5, 3.5)
            d.ellipse([x - s, y - s, x + s, y + s], fill=(255, 220, 170, int(90 * r.uniform(0.3, 1))))
        img.alpha_composite(kit.vignette(W, H, 0.55))
        kit.pill(img, 540, 300, "MESOPOTAMIA · c. 1800 BCE", 32, alpha=ramp(u, 0.03, 0.15), bg=(0, 0, 0, 110), outline=(255, 210, 140, 120))
        kit.badge(img, RECON, y=362, alpha=ramp(u, 0.05, 0.18))
        a = ramp(u, 0.45, 0.6)
        if a > 0:
            tab = kit.with_alpha(self.tablet, a)
            img.alpha_composite(tab, (390, int(560 + (1 - a) * 40)))
            kit.text(img, 540, 760, "20%", 120, fill=GOLD, weight="Black", alpha=a, stroke=4)
            kit.pill(img, 540, 990, "INTEREST ON SILVER LOANS · SET BY LAW", 28, alpha=ramp(u, 0.55, 0.7), bg=(0, 0, 0, 140))
        return img


class NoCoinsTimeline(Scene):
    sfx = [(0.08, "tick", 0.25), (0.55, "chime", 0.3)]

    def setup(self):
        self.bg = dusk_bg(4)

    def frame(self, t):
        u = t / self.dur
        img = self.bg.copy()
        fade = 1 - ramp(u, 0.62, 0.72)
        if fade > 0:
            lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(lay)
            y0, y1 = 430, 1120
            g = ramp(u, 0.05, 0.5)
            yy = y0 + (y1 - y0) * g
            for y in range(y0, int(yy), 24):
                d.line([(300, y), (300, min(yy, y + 14))], fill=(255, 210, 140, 200), width=6)
            d.ellipse([280, y0 - 20, 320, y0 + 20], fill=GOLD)
            kit.text(lay, 350, y0 - 18, "c. 1800 BCE", 44, fill=GOLD, weight="Black", anchor="lm")
            kit.text(lay, 350, y0 + 32, "Loans in silver & barley", 32, anchor="lm")
            kit.text(lay, 350, (y0 + y1) / 2, "1,100+ years", 58, weight="Black", anchor="lm", alpha=ramp(u, 0.25, 0.4))
            kit.text(lay, 350, (y0 + y1) / 2 + 56, "and still no coins", 36, anchor="lm", fill=(230, 210, 200, 255), alpha=ramp(u, 0.3, 0.45))
            c = ramp(u, 0.48, 0.58)
            if c > 0:
                cp = Pen(140, 140, origin=(70, 70), scale=kit.ease("out_back", c))
                cp.circle(0, 0, 44, fill=hex2rgba("#E3C15C"), outline=hex2rgba("#8A6A1E"), width=5)
                cp.circle(0, 0, 30, fill=None, outline=(255, 240, 180, 200), width=3)
                lay.alpha_composite(cp.finish(), (230, y1 - 70))
                kit.text(lay, 350, y1 - 18, "c. 630 BCE", 44, fill=GOLD, weight="Black", anchor="lm", alpha=c)
                kit.text(lay, 350, y1 + 32, "First coins (Lydia)", 32, anchor="lm", alpha=c)
            img.alpha_composite(kit.with_alpha(lay, fade))
        q = ramp(u, 0.66, 0.9)
        if q > 0:
            kit.kinetic_title(img, 540, 780, "So how did money begin?", 108, (u - 0.66) * 3.2, accent=({"MONEY"}, GOLD))
        return img


def _person(p, x, y, col, flip=1, hold=None):
    p.circle(x, y - 210, 42, fill=col, **NO)
    p.poly([(x - 58, y), (x + 58, y), (x + 40, y - 160), (x - 40, y - 160)], fill=col, **NO)
    p.stroke([(x + 30 * flip, y - 140), (x + 90 * flip, y - 90)], col, 26)


class BarterMyth(Scene):
    sfx = [(0.1, "whoosh", 0.25), (0.52, "stamp", 0.7)]

    def setup(self):
        self.bg = dusk_bg(7)
        p = Pen(W, H, origin=(0, 0))
        c1, c2 = hex2rgba("#E9A15F"), hex2rgba("#8FB7C9")
        _person(p, 230, 1000, c1, 1)
        _person(p, 850, 1000, c2, -1)
        # goat
        p.ellipse(380, 920, 70, 40, fill=hex2rgba("#E8E1D6"), outline=(90, 70, 60, 255), width=4)
        for lx in (335, 360, 400, 425):
            p.stroke([(lx, 950), (lx, 1000)], (90, 70, 60, 255), 9)
        p.ellipse(455, 880, 26, 22, fill=hex2rgba("#E8E1D6"), outline=(90, 70, 60, 255), width=4)
        p.curve([(450, 860), (440, 830), (420, 825)], (90, 70, 60, 255), 6)
        # grain sack
        p.poly([(650, 1000), (760, 1000), (775, 900), (735, 850), (675, 850), (635, 900)], fill=hex2rgba("#D8B47A"), outline=(110, 80, 40, 255), width=5)
        p.stroke([(680, 860), (730, 860)], (110, 80, 40, 255), 7)
        for k in range(6):
            p.ellipse(675 + k * 10, 845 - (k % 2) * 8, 6, 10, fill=hex2rgba("#F0D58A"), **NO)
        self.scene = p.finish()

    def frame(self, t):
        u = t / self.dur
        img = self.bg.copy()
        dim = ramp(u, 0.5, 0.6)
        sc = kit.with_alpha(self.scene, 1 - 0.55 * dim)
        img.alpha_composite(sc, (0, -60))
        kit.pill(img, 540, 330, "THE TEXTBOOK STORY", 32, alpha=ramp(u, 0.02, 0.12) * (1 - dim), bg=(255, 255, 255, 30))
        sw = ramp(u, 0.12, 0.4)
        if sw > 0 and dim < 1:
            d = ImageDraw.Draw(img)
            a = int(230 * (1 - dim))
            pts1 = [(420 + 220 * k, 760 - 70 * math.sin(math.pi * k)) for k in np.linspace(0, sw, 20)]
            pts2 = [(660 - 220 * k, 1000 + 60 * math.sin(math.pi * k)) for k in np.linspace(0, sw, 20)]
            d.line(pts1, fill=(255, 220, 160, a), width=7)
            d.line(pts2, fill=(255, 220, 160, a), width=7)
        st = ramp(u, 0.52, 0.58)
        if st > 0:
            sp = Pen(620, 300, origin=(310, 150), scale=1.6 - 0.6 * kit.ease("out_back", st))
            sp.rrect(-240, -80, 240, 80, 20, fill=None, outline=hex2rgba("#E5484D"), width=12)
            sp.text(0, 4, "MYTH?", 120, fill=hex2rgba("#E5484D"))
            stamp = sp.finish().rotate(-10, resample=Image.BICUBIC, expand=True)
            img.alpha_composite(kit.with_alpha(stamp, st), (int(540 - stamp.width / 2), int(820 - stamp.height / 2)))
        q = ramp(u, 0.62, 0.75)
        if q > 0:
            card = Image.new("RGBA", (900, 230), (0, 0, 0, 0))
            ImageDraw.Draw(card).rounded_rectangle([0, 0, 899, 229], 30, fill=(10, 8, 16, 200), outline=(255, 210, 140, 120), width=2)
            img.alpha_composite(kit.with_alpha(card, q), (90, 1010))
            kit.text(img, 540, 1065, "“No example of a barter economy, pure and", 32, alpha=q, shadow=False)
            kit.text(img, 540, 1108, "simple, has ever been described.”", 32, alpha=q, shadow=False)
            kit.text(img, 540, 1172, "— Caroline Humphrey, anthropologist (1985)", 26, fill=GOLD, alpha=q, shadow=False)
        return img


class ClayLedger(Scene):
    sfx = [(0.12, "stylus", 0.35), (0.22, "stylus", 0.35), (0.32, "stylus", 0.35), (0.6, "chime", 0.25)]

    def setup(self):
        self.bg = dusk_bg(11)
        self.frames = {}

    def tablet(self, marks):
        key = marks // 3 * 3
        if key not in self.frames:
            self.frames[key] = clay_tablet(500, 640, seed=12, marks=key, rows=7)
        return self.frames[key]

    def frame(self, t):
        u = t / self.dur
        img = self.bg.copy()
        kit.paste_glow(img, 380, 760, 420, (255, 180, 110), alpha=0.25)
        marks = int(60 * ramp(u, 0.05, 0.75))
        tab = self.tablet(marks).rotate(4, resample=Image.BICUBIC, expand=True)
        img.alpha_composite(tab, (110, 420))
        # reed stylus
        sx = 160 + (marks % 9) * 44
        sy = 500 + (marks // 9) * 82
        p = Pen(W, H, origin=(0, 0))
        p.stroke([(sx + 20, sy - 10), (sx + 210, sy - 220)], hex2rgba("#C8B07A"), 14)
        p.stroke([(sx + 20, sy - 10), (sx + 30, sy - 22)], hex2rgba("#5E4A2A"), 14)
        # balance scale (silver vs barley)
        a = ramp(u, 0.45, 0.6)
        sway = 4 * math.sin(t * 1.6) * (1 - ramp(u, 0.7, 0.9))
        cx, cy = 820, 760
        p.stroke([(cx, cy), (cx, cy + 330)], (200, 170, 120, int(255 * a)), 12)
        p.rrect(cx - 80, cy + 320, cx + 80, cy + 345, 8, fill=(200, 170, 120, int(255 * a)), **NO)
        ang = math.radians(sway)
        L = 170
        lx, ly = cx - L * math.cos(ang), cy - L * math.sin(ang)
        rx, ry = cx + L * math.cos(ang), cy + L * math.sin(ang)
        p.stroke([(lx, ly), (rx, ry)], (220, 190, 130, int(255 * a)), 10)
        for (px, py, kind) in ((lx, ly, "silver"), (rx, ry, "barley")):
            p.stroke([(px, py), (px - 50, py + 110)], (220, 190, 130, int(200 * a)), 3, caps=False)
            p.stroke([(px, py), (px + 50, py + 110)], (220, 190, 130, int(200 * a)), 3, caps=False)
            p.ellipse(px, py + 115, 70, 16, fill=(160, 120, 70, int(255 * a)), **NO)
            if kind == "silver":
                for k in range(3):
                    p.ellipse(px - 22 + k * 22, py + 100 - (k % 2) * 8, 18, 9, fill=(*SILVER[:3], int(255 * a)), outline=(120, 125, 135, int(255 * a)), width=2)
            else:
                for k in range(14):
                    p.ellipse(px - 36 + (k % 7) * 12, py + 100 - (k // 7) * 10, 6, 9, fill=(240, 205, 120, int(255 * a)), **NO)
        img.alpha_composite(p.finish())
        kit.pill(img, 820, 680, "SILVER  ·  BARLEY", 28, alpha=a, bg=(0, 0, 0, 120))
        kit.pill(img, 540, 1190, "1 SHEKEL ≈ 8.3 g OF SILVER", 34, alpha=ramp(u, 0.68, 0.8), fg=(20, 16, 10, 255), bg=(*GOLD[:3], 240))
        kit.badge(img, "ILLUSTRATIVE · CUNEIFORM-STYLE MARKS", y=300, alpha=ramp(u, 0.02, 0.15))
        kit.text(img, 360, 385, "Debts recorded on clay", 38, weight="Black", alpha=ramp(u, 0.1, 0.25))
        return img


class CreditWeb(Scene):
    sfx = [(0.1, "tick", 0.2), (0.25, "tick", 0.2), (0.4, "tick", 0.2)]

    def setup(self):
        self.bg = dusk_bg(13)
        self.tab = clay_tablet(150, 190, seed=3, marks=14, rows=4)

    def frame(self, t):
        u = t / self.dur
        img = self.bg.copy()
        cx, cy, R = 540, 780, 320
        nodes = [(cx + R * math.cos(a), cy + R * math.sin(a) * 0.95) for a in np.linspace(-math.pi / 2, 1.5 * math.pi, 7)[:-1]]
        pairs = [(0, 2), (1, 4), (3, 5), (2, 4), (5, 1), (0, 3), (4, 0)]
        d = ImageDraw.Draw(img)
        for i, (a_, b_) in enumerate(pairs):
            k = ramp(u, 0.05 + i * 0.07, 0.2 + i * 0.07)
            if k <= 0:
                continue
            (x1, y1), (x2, y2) = nodes[a_], nodes[b_]
            mx, my = (x1 + x2) / 2 + (cy - (y1 + y2) / 2) * 0.25, (y1 + y2) / 2 + ((x1 + x2) / 2 - cx) * 0.25
            pts = [((1 - s) ** 2 * x1 + 2 * (1 - s) * s * mx + s * s * x2, (1 - s) ** 2 * y1 + 2 * (1 - s) * s * my + s * s * y2) for s in np.linspace(0, k, 24)]
            d.line(pts, fill=(255, 210, 140, 200), width=4)
        kit.paste_glow(img, cx, cy, 200, (255, 190, 110), alpha=0.35)
        img.alpha_composite(self.tab, (cx - 75, cy - 95))
        p = Pen(W, H, origin=(0, 0))
        for (x, y) in nodes:
            p.rrect(x - 44, y - 30, x + 44, y + 34, 6, fill=hex2rgba("#A9603F"), outline=(60, 30, 20, 255), width=4)
            p.poly([(x - 52, y - 28), (x, y - 62), (x + 52, y - 28)], fill=hex2rgba("#6E3C35"), outline=(60, 30, 20, 255), width=4)
            p.rrect(x - 10, y + 2, x + 10, y + 34, 4, fill=(40, 20, 20, 255), **NO)
        img.alpha_composite(p.finish())
        kit.text(img, 540, 330, "Credit before coins?", 64, weight="Black", alpha=ramp(u, 0.15, 0.3))
        kit.pill(img, 540, 1190, "HISTORIANS STILL DEBATE THE DETAILS", 30, alpha=ramp(u, 0.5, 0.65), bg=(0, 0, 0, 150), outline=(255, 210, 140, 140))
        return img


ANATOLIA = [(470, 760), (560, 700), (680, 690), (800, 660), (930, 690), (1080, 650), (1080, 980), (930, 1010),
            (800, 1000), (690, 1040), (600, 1010), (520, 990), (480, 930), (450, 860)]
GREECE = [(0, 700), (140, 720), (250, 780), (300, 860), (260, 960), (210, 1060), (150, 1000), (90, 1080), (0, 1060)]
ISLANDS = [(360, 800, 22), (330, 900, 18), (390, 960, 26), (420, 1060, 30), (300, 1120, 70)]


def lion_coin(size, glint=0.0):
    p = Pen(size, size, origin=(size / 2, size / 2))
    r = size * 0.42
    pts = [(r * (1 + 0.06 * math.sin(a * 5)) * math.cos(a), r * (1 + 0.05 * math.cos(a * 3)) * math.sin(a) * 0.92) for a in np.linspace(0, 2 * math.pi, 40, endpoint=False)]
    p.poly(pts, fill=hex2rgba("#D9B653"), outline=hex2rgba("#7E6118"), width=6)
    p.poly([(x * 0.86, y * 0.86) for x, y in pts], fill=hex2rgba("#E6C766"), **NO)
    # stylised lion head in profile (original design)
    s = r / 100
    head = [(-40 * s, -10 * s), (-10 * s, -40 * s), (30 * s, -36 * s), (58 * s, -12 * s), (62 * s, 8 * s), (40 * s, 12 * s),
            (54 * s, 26 * s), (30 * s, 34 * s), (0, 26 * s), (-30 * s, 30 * s)]
    p.poly(head, fill=hex2rgba("#C9A440"), outline=hex2rgba("#7E6118"), width=4)
    for a in np.linspace(1.4, 4.6, 9):
        p.stroke([(-20 * s + 40 * s * math.cos(a), -2 * s + 44 * s * math.sin(a)), (-20 * s + 66 * s * math.cos(a), -2 * s + 70 * s * math.sin(a))], hex2rgba("#7E6118"), 5)
    p.circle(22 * s, -16 * s, 5 * s, fill=hex2rgba("#5A4410"), **NO)
    p.ellipse(-30 * s, -50 * s, 40 * s, 12 * s, fill=(255, 250, 220, int(120 + 120 * glint)), **NO)
    return p.finish()


class LydiaCoin(Scene):
    sfx = [(0.05, "whoosh", 0.25), (0.56, "coin", 0.8)]

    def setup(self):
        sea = kit.vgrad(W, H, hex2rgba("#16324A"), hex2rgba("#0B1A2A"))
        p = Pen(W, H, origin=(0, 0))
        land = hex2rgba("#C9A26B")
        p.poly(ANATOLIA, fill=land, outline=hex2rgba("#7C5E36"), width=4)
        p.poly(GREECE, fill=land, outline=hex2rgba("#7C5E36"), width=4)
        for (x, y, r) in ISLANDS:
            p.ellipse(x, y, r, r * 0.6, fill=land, outline=hex2rgba("#7C5E36"), width=3)
        sea.alpha_composite(p.finish())
        kit.text(sea, 820, 860, "ANATOLIA", 34, fill=(90, 60, 30, 230), weight="Black", shadow=False)
        kit.text(sea, 560, 1170, "Aegean Sea", 28, fill=(160, 200, 230, 200), shadow=False)
        self.map = sea
        self.dark = dusk_bg(17)
        self.coin = lion_coin(520)

    def frame(self, t):
        u = t / self.dur
        if u < 0.47:
            img = kit.zoom(self.map, 1.0 + 0.25 * kit.ease("in_out", u / 0.47), 600, 860, (W, H))
            k = ramp(u, 0.08, 0.2)
            mx, my = 540 + (590 - 600) * 1.1, 860
            for rr in (1, 2):
                ph = (t * 1.2 + rr * 0.5) % 1.0
                kit.paste_glow(img, mx, my, 40 + 80 * ph, GOLD, alpha=(1 - ph) * k)
            d = ImageDraw.Draw(img)
            d.ellipse([mx - 12, my - 12, mx + 12, my + 12], fill=(*GOLD[:3], int(255 * k)))
            kit.text(img, mx, my - 60, "LYDIA", 56, weight="Black", fill=GOLD, alpha=k, stroke=3)
            kit.text(img, mx, my + 56, "Sardis", 30, alpha=k)
            kit.badge(img, "SIMPLIFIED MAP · LATE 7TH CENTURY BCE", y=300, alpha=ramp(u, 0.02, 0.12))
            return img
        img = self.dark.copy()
        kit.paste_glow(img, 540, 800, 460, (255, 200, 120), alpha=0.35)
        strike = ramp(u, 0.53, 0.58)
        die_y = 300 + 300 * strike - 420 * ramp(u, 0.6, 0.7)
        p = Pen(W, H, origin=(0, 0))
        p.rrect(470, die_y - 260, 610, die_y, 14, fill=hex2rgba("#6C6F78"), outline=(30, 30, 36, 255), width=5)
        if strike < 1:  # rough electrum lump before the strike
            p.ellipse(540, 800, 190, 150, fill=hex2rgba("#D8B84E"), outline=hex2rgba("#7E6118"), width=6)
            img.alpha_composite(p.finish())
        else:
            img.alpha_composite(p.finish())
            pop = kit.ease("out_back", ramp(u, 0.58, 0.68))
            c = self.coin.resize((int(520 * (0.85 + 0.15 * pop)),) * 2, Image.LANCZOS)
            img.alpha_composite(c, (540 - c.width // 2, 800 - c.height // 2))
            if u < 0.64:
                img.alpha_composite(Image.new("RGBA", (W, H), (255, 245, 220, int(200 * (1 - ramp(u, 0.58, 0.64))))))
        kit.pill(img, 540, 1130, "ELECTRUM · NATURAL GOLD-SILVER ALLOY", 30, alpha=ramp(u, 0.6, 0.72), fg=(20, 16, 10, 255), bg=(*GOLD[:3], 240))
        kit.text(img, 540, 380, "The first coins", 70, weight="Black", alpha=ramp(u, 0.68, 0.8))
        kit.badge(img, RECON + " · ORIGINAL DESIGN", y=300, alpha=ramp(u, 0.6, 0.7))
        return img


class ModernLedger(Scene):
    sfx = [(0.08, "whoosh", 0.25), (0.4, "tick", 0.25), (0.82, "sting", 0.55)]

    def setup(self):
        self.bg = dusk_bg(19)
        self.tab = clay_tablet(360, 460, seed=21, marks=40, rows=6)

    def frame(self, t):
        u = t / self.dur
        img = self.bg.copy()
        m = ramp(u, 0.1, 0.35)
        img.alpha_composite(kit.with_alpha(self.tab, 1 - m), (360, 520))
        if m > 0:
            ph = Image.new("RGBA", (420, 800), (0, 0, 0, 0))
            d = ImageDraw.Draw(ph)
            d.rounded_rectangle([0, 0, 419, 799], 56, fill=(18, 20, 28, 255), outline=(200, 205, 215, 255), width=6)
            d.rounded_rectangle([22, 60, 397, 760], 30, fill=(240, 236, 228, 255))
            kit.text(ph, 210, 130, "Balance", 30, fill=(90, 90, 100, 255), shadow=False)
            bal = 1000 + int(2480 * ramp(u, 0.35, 0.75))
            kit.text(ph, 210, 190, f"£{bal:,}.00", 54, fill=(20, 20, 28, 255), weight="Black", shadow=False)
            rows = [("Wages", "+2,400"), ("Rent", "−950"), ("Groceries", "−64"), ("Transfer in", "+120"), ("Coffee", "−3")]
            for i, (a, b) in enumerate(rows):
                y = 300 + i * 82
                kit.text(ph, 60, y, a, 28, fill=(60, 60, 70, 255), anchor="lm", shadow=False)
                kit.text(ph, 360, y, b, 28, fill=(20, 120, 70, 255) if b.startswith("+") else (170, 50, 50, 255), anchor="rm", shadow=False, weight="Black")
                d.line([(50, y + 38), (370, y + 38)], fill=(210, 205, 195, 255), width=2)
            img.alpha_composite(kit.with_alpha(ph, m), (330, 470))
        s = ramp(u, 0.4, 0.55)
        kit.text(img, 540, 330, "≈97%", 96, fill=GOLD, weight="Black", alpha=s, stroke=3)
        kit.text(img, 540, 410, "of UK money is bank deposits", 36, alpha=s)
        kit.pill(img, 540, 1325 - 125, "BANK OF ENGLAND, 2014", 26, alpha=s, bg=(0, 0, 0, 140), outline=(255, 210, 140, 120))
        b = ramp(u, 0.82, 0.95)
        if b > 0:
            img.alpha_composite(Image.new("RGBA", (W, H), (10, 6, 14, int(200 * b))))
            kit.text(img, 540, 800, "N4V3D", 140, fill=GOLD, weight="Black", alpha=b)
            kit.text(img, 540, 900, "W O R L D", 48, alpha=b)
        return img


SCENES = {
    "mesopotamia_city": MesopotamiaCity, "no_coins_timeline": NoCoinsTimeline, "barter_myth": BarterMyth,
    "clay_ledger": ClayLedger, "credit_web": CreditWeb, "lydia_coin": LydiaCoin, "modern_ledger": ModernLedger,
}
