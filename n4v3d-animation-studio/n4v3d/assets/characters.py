"""Original character rigs: NUGGO and BRICKLEY.

Each rig is a pure function of a state dict, so the same character can be
re-used in any episode, posed, emoted and lip-synced without hand drawing:

    state = {
        "emotion": "excited",        # see EMOTIONS
        "mouth": 0.0..1.0,           # lip-sync openness (driven by voice audio)
        "blink": 0.0..1.0,           # 1 = eyes closed
        "look": (dx, dy),            # pupil direction, -1..1
        "arms": {"L": (x, y), "R": (x, y)},   # hand offsets from shoulders
        "hold": None | "mug",
        "t": seconds,                # for secondary motion (steam, dizzy stars)
    }

`render(state, scale)` returns (RGBA image, (pivot_x, pivot_y)) where the pivot
is the point between the character's feet.
"""
from __future__ import annotations

import math

from ..gfx import Pen, hex2rgba, mix, star_points
from .. import config

INK = config.INK
WHITE = (255, 255, 255, 255)
MOUTH_DARK = hex2rgba("#5A1A2A")
TONGUE = hex2rgba("#FF7A8A")
BLUSH = hex2rgba("#FF8FA3", 120)

EMOTIONS = ("neutral", "excited", "proud", "worried", "annoyed", "deadpan",
            "shocked", "dizzy", "sleepy", "smug", "angry")


def _ellipse_pts(cx, cy, rx, ry, n=48):
    return [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]


def _eye(p: Pen, cx, cy, rx, ry, look, blink, pupil_r, lid=0.0, lid_color=None, emotion="neutral", t=0.0):
    """Generic cartoon eye with optional heavy upper lid (0..1 coverage)."""
    if emotion == "dizzy":
        p.ellipse(cx, cy, rx, ry, fill=WHITE)
        # rotating spiral
        pts = []
        for i in range(60):
            a = i * 0.32 + t * 9
            r = i / 60 * min(rx, ry) * 0.85
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        p.stroke(pts, INK, 5)
        return
    if emotion == "sleepy" or blink >= 0.85:
        # closed eye: a soft arc
        p.curve([(cx - rx, cy), (cx, cy + ry * 0.55), (cx + rx, cy)], INK, 7)
        return
    ry_eff = ry * (1.0 - 0.8 * blink)
    if emotion == "shocked":
        rx, ry_eff, pupil_r = rx * 1.12, ry_eff * 1.12, pupil_r * 0.6
    p.ellipse(cx, cy, rx, ry_eff, fill=WHITE)
    lx, ly = look
    px = cx + lx * (rx - pupil_r - 4)
    py = cy + ly * (ry_eff - pupil_r - 4) * 0.8
    p.circle(px, py, pupil_r, fill=INK, width=0)
    p.circle(px - pupil_r * 0.35, py - pupil_r * 0.4, pupil_r * 0.32, fill=WHITE, width=0)
    if lid > 0.01:
        y_l = cy - ry_eff + 2 * ry_eff * lid
        pts = [(x, min(y, y_l)) for x, y in _ellipse_pts(cx, cy, rx, ry_eff)]
        p.poly(pts, fill=lid_color, outline=None, width=0)
        # lid edge
        half = rx * math.sqrt(max(0.0, 1 - ((y_l - cy) / ry_eff) ** 2))
        p.stroke([(cx - half, y_l), (cx + half, y_l)], INK, 6)
        p.ellipse(cx, cy, rx, ry_eff, fill=None)


def _dizzy_stars(p: Pen, cx, cy, rx, t):
    for i in range(3):
        a = t * 4 + i * 2 * math.pi / 3
        x = cx + rx * math.cos(a)
        y = cy + rx * 0.28 * math.sin(a)
        p.poly(star_points(x, y, 22, 10), fill=hex2rgba("#FFE14D"), width=5)


# ---------------------------------------------------------------------------
# NUGGO — a small, round, endlessly over-confident "life-hacker" bean.
# ---------------------------------------------------------------------------
class Nuggo:
    name = "nuggo"
    display = "Nuggo"
    BODY = hex2rgba("#FFC93C")
    BELLY = hex2rgba("#FFE38F")
    FEET = hex2rgba("#E0782E")
    HAIR = hex2rgba("#6B3E26")
    shoulder = {"L": (-128, -215), "R": (128, -215)}
    head_y = -265            # eye line (used for camera targets / punch aiming)
    height = 440

    POSES = {
        "rest":    {"L": (-45, 105), "R": (45, 105)},
        "up":      {"L": (-95, -150), "R": (95, -150)},
        "present": {"L": (-45, 105), "R": (175, -45)},
        "point":   {"L": (-45, 105), "R": (195, -90)},
        "shrug":   {"L": (-120, -35), "R": (120, -35)},
        "hips":    {"L": (25, 35), "R": (-25, 35)},
        "press":   {"L": (-45, 105), "R": (75, 54)},
        "think":   {"L": (-45, 105), "R": (-95, 25)},
        "flat":    {"L": (-150, 20), "R": (150, 20)},
    }

    @classmethod
    def render(cls, s: dict, scale: float = 1.0):
        p = Pen(760, 680, origin=(380, 600), scale=scale)
        emo = s.get("emotion", "neutral")
        t = s.get("t", 0.0)
        arms = s.get("arms") or cls.POSES["rest"]

        # feet
        for fx in (-62, 62):
            p.ellipse(fx, -14, 50, 24, fill=cls.FEET)
        # body
        p.ellipse(0, -205, 152, 185, fill=cls.BODY)
        p.ellipse(0, -140, 96, 80, fill=cls.BELLY, width=0)
        # hair tuft
        for dx, bend in ((-14, -40), (0, 0), (14, 40)):
            p.curve([(dx, -386), (dx + bend * 0.4, -430), (dx + bend, -446)], cls.HAIR, 13)
        # cheeks
        for cx in (-102, 102):
            p.ellipse(cx, -200, 26, 15, fill=BLUSH, width=0)

        # eyes
        look = s.get("look", (0.0, 0.0))
        blink = s.get("blink", 0.0)
        lid = {"deadpan": 0.45, "annoyed": 0.4, "smug": 0.35, "angry": 0.3}.get(emo, 0.0)
        for ex in (-58, 58):
            _eye(p, ex, -265, 44, 54, look, blink, 21, lid=lid, lid_color=cls.BODY, emotion=emo, t=t)
        # brows: (inner_y, outer_y) per emotion
        by = {
            "excited": (-352, -352), "shocked": (-356, -356), "worried": (-348, -326),
            "annoyed": (-318, -342), "angry": (-314, -346), "dizzy": (-340, -330),
        }.get(emo, (-336, -336))
        for side, ex in ((-1, -58), (1, 58)):
            yi, yo = by
            if emo in ("proud", "smug") and side == 1:
                yi, yo = -356, -360
            xi, xo = ex - side * 28, ex + side * 32
            p.curve([(xi, yi), ((xi + xo) / 2, min(yi, yo) - 8), (xo, yo)], INK, 10)

        # mouth
        m = s.get("mouth", 0.0)
        cls._mouth(p, emo, m)

        # dizzy stars
        if emo == "dizzy":
            _dizzy_stars(p, 0, -430, 110, t)

        # arms (drawn over the body edge)
        for side in ("L", "R"):
            sx, sy = cls.shoulder[side]
            hx, hy = arms[side]
            ex, ey = sx + hx, sy + hy
            sgn = -1 if side == "L" else 1
            mid = ((sx + ex) / 2 + sgn * 26, (sy + ey) / 2 + 22)
            p.limb([(sx, sy), mid, (ex, ey)], cls.BODY, 26)
            p.circle(ex, ey, 23, fill=cls.BODY)
        return p.finish(), p.origin_px()

    @staticmethod
    def _mouth(p: Pen, emo, m):
        cx, cy = 0, -182
        if m < 0.12:
            if emo in ("worried", "dizzy", "shocked"):
                if emo == "shocked":
                    p.ellipse(cx, cy, 16, 20, fill=MOUTH_DARK)
                else:
                    p.curve([(cx - 36, cy + 10), (cx, cy - 10), (cx + 36, cy + 10)], INK, 8)
            elif emo in ("deadpan", "annoyed", "sleepy"):
                p.stroke([(cx - 30, cy), (cx + 30, cy)], INK, 8)
            elif emo == "smug":
                p.curve([(cx - 34, cy), (cx + 6, cy + 10), (cx + 40, cy - 14)], INK, 8)
            else:  # smile
                p.curve([(cx - 46, cy - 6), (cx, cy + 28), (cx + 46, cy - 6)], INK, 8)
            return
        w = 40 + 36 * m
        h = 14 + 62 * m
        if emo in ("excited", "proud", "smug", "neutral", "angry"):
            # "D" shaped grin: flat top, round bottom
            top = cy - 10
            pts = [(cx - w, top)] + [(cx - w * math.cos(i * math.pi / 20), top + h * math.sin(i * math.pi / 20)) for i in range(1, 20)] + [(cx + w, top)]
            p.poly(pts, fill=MOUTH_DARK, width=7)
            p.ellipse(cx, top + h * 0.72, w * 0.5, h * 0.25, fill=TONGUE, width=0)
        else:
            p.ellipse(cx, cy + 6, w * 0.7, h * 0.55, fill=MOUTH_DARK, width=7)
            p.ellipse(cx, cy + 6 + h * 0.28, w * 0.38, h * 0.18, fill=TONGUE, width=0)


# ---------------------------------------------------------------------------
# BRICKLEY — a tall, terracotta brick of a man. Deadpan. Always has tea.
# ---------------------------------------------------------------------------
class Brickley:
    name = "brickley"
    display = "Brickley"
    BODY = hex2rgba("#C9654C")
    BODY_DARK = hex2rgba("#A54E3A")
    BODY_LIGHT = hex2rgba("#DD8268")
    TIE = hex2rgba("#2EC4B6")
    SHOE = hex2rgba("#3A2B3D")
    shoulder = {"L": (-108, -300), "R": (108, -300)}
    head_y = -430
    height = 580

    POSES = {
        "rest":     {"L": (-22, 190), "R": (22, 190)},
        "hold":     {"L": (-22, 190), "R": (-30, 60)},
        "sip":      {"L": (-22, 190), "R": (-92, -16)},
        "shrug":    {"L": (-110, -10), "R": (110, -10)},
        "point":    {"L": (-22, 190), "R": (150, -60)},
        "palm":     {"L": (-22, 190), "R": (-150, -132)},
        "lean":     {"L": (-40, 175), "R": (-30, 60)},
        "wave":     {"L": (-22, 190), "R": (80, -170)},
    }

    @classmethod
    def render(cls, s: dict, scale: float = 1.0):
        p = Pen(700, 860, origin=(350, 760), scale=scale)
        emo = s.get("emotion", "deadpan")
        t = s.get("t", 0.0)
        arms = s.get("arms") or cls.POSES["rest"]

        # legs + shoes
        for lx in (-48, 48):
            p.limb([(lx, -90), (lx, -50), (lx, -22)], cls.BODY_DARK, 22)
            p.ellipse(lx + (8 if lx > 0 else -8), -14, 40, 18, fill=cls.SHOE)
        # body (the brick)
        p.rrect(-118, -585, 118, -78, 70, fill=cls.BODY)
        # brick texture
        for (x0, y0, x1, y1) in ((-88, -540, -40, -522), (30, -500, 84, -482),
                                 (-90, -170, -30, -152), (40, -132, 92, -114)):
            p.rrect(x0, y0, x1, y1, 8, fill=cls.BODY_LIGHT, width=0)
        p.rrect(-118, -585, 118, -78, 70, fill=None)

        look = s.get("look", (0.0, 0.0))
        blink = s.get("blink", 0.0)
        lid = {"deadpan": 0.48, "annoyed": 0.56, "sleepy": 0.75, "neutral": 0.35,
               "smug": 0.5, "worried": 0.2, "shocked": 0.0, "excited": 0.1}.get(emo, 0.4)
        for ex in (-46, 46):
            _eye(p, ex, -432, 30, 34, look, blink, 13, lid=lid, lid_color=cls.BODY_DARK, emotion=emo, t=t)
        # round glasses
        for ex in (-46, 46):
            p.circle(ex, -432, 44, fill=None, width=7)
        p.curve([(-4, -436), (0, -444), (4, -436)], INK, 7)
        # brows: flat, unimpressed. (inner_dy, outer_dy) per emotion
        bd = {"shocked": (-24, -24), "worried": (-14, 2), "annoyed": (8, -6),
              "angry": (12, -8), "smug": (-2, -8), "excited": (-14, -14)}.get(emo, (0, 0))
        for side, ex in ((-1, -46), (1, 46)):
            xi, xo = ex - side * 30, ex + side * 30
            p.stroke([(xi, -494 + bd[0]), (xo, -494 + bd[1])], INK, 11)

        # mouth
        m = s.get("mouth", 0.0)
        my = -352
        if m < 0.12:
            if emo == "smug":
                p.curve([(-28, my), (6, my + 6), (30, my - 10)], INK, 7)
            elif emo == "shocked":
                p.ellipse(0, my, 13, 17, fill=MOUTH_DARK, width=6)
            elif emo == "worried":
                p.curve([(-26, my + 6), (0, my - 6), (26, my + 6)], INK, 7)
            else:
                p.stroke([(-26, my), (26, my)], INK, 7)
        else:
            w, h = 22 + 10 * m, 8 + 34 * m
            p.rrect(-w, my - h * 0.4, w, my + h * 0.6, min(w, h) * 0.5, fill=MOUTH_DARK, width=6)

        # bow tie
        p.poly([(0, -290), (-46, -312), (-46, -266)], fill=cls.TIE, width=6)
        p.poly([(0, -290), (46, -312), (46, -266)], fill=cls.TIE, width=6)
        p.circle(0, -290, 11, fill=cls.TIE, width=6)

        if emo == "dizzy":
            _dizzy_stars(p, 0, -610, 100, t)

        # arms
        hold = s.get("hold")
        for side in ("L", "R"):
            sx, sy = cls.shoulder[side]
            hx, hy = arms[side]
            ex, ey = sx + hx, sy + hy
            sgn = -1 if side == "L" else 1
            mid = ((sx + ex) / 2 + sgn * 30, (sy + ey) / 2 + 10)
            p.limb([(sx, sy), mid, (ex, ey)], cls.BODY, 20)
            if side == "R" and hold == "mug":
                cls._mug(p, ex - 4, ey - 6, t)
            p.circle(ex, ey, 18, fill=cls.BODY)
        return p.finish(), p.origin_px()

    @staticmethod
    def _mug(p: Pen, x, y, t):
        # steam
        for i, dx in enumerate((-12, 12)):
            ph = t * 2.4 + i * 1.7
            pts = [(x + dx + 8 * math.sin(ph + k * 0.6), y - 54 - k * 9) for k in range(7)]
            p.stroke(pts, (255, 255, 255, 170), 6)
        p.rrect(x - 30, y - 44, x + 30, y + 26, 10, fill=WHITE)
        p.rrect(x - 30, y - 18, x + 30, y - 6, 0, fill=hex2rgba("#2EC4B6"), width=0)
        p.rrect(x - 30, y - 44, x + 30, y + 26, 10, fill=None)
        p.curve([(x + 30, y - 30), (x + 56, y - 22), (x + 30, y + 8)], INK, 8)


CHARACTERS = {"nuggo": Nuggo, "brickley": Brickley}
