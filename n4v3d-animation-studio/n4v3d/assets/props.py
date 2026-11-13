"""Reusable props. Same contract as characters: render(state, scale) -> (img, pivot)."""
from __future__ import annotations

import math

from ..gfx import Pen, hex2rgba, star_points
from .. import config

INK = config.INK
WHITE = (255, 255, 255, 255)


def _rot(x, y, a):
    c, s = math.cos(a), math.sin(a)
    return (x * c - y * s, x * s + y * c)


class SnoozeOMatic:
    """A cardboard box with googly eyes and a spring-loaded boxing glove.

    state: punch (0..1 extension), angle (deg, 0 = right, -90 = up),
           mood: happy | angry | sleepy | asleep, active (bool), press (0..1), t
    """
    name = "box"
    CARD = hex2rgba("#C99A66")
    CARD_DARK = hex2rgba("#A87B4C")
    TAPE = hex2rgba("#E8C990")
    GLOVE = hex2rgba("#E63946")
    MOUNT = (0, -262)
    REACH = 400

    @classmethod
    def glove_pos(cls, angle_deg, punch):
        a = math.radians(angle_deg)
        L = 46 + cls.REACH * punch
        return cls.MOUNT[0] + L * math.cos(a), cls.MOUNT[1] + L * math.sin(a)

    @classmethod
    def render(cls, s: dict, scale: float = 1.0):
        punch = max(0.0, s.get("punch", 0.08))
        ang = s.get("angle", -90.0)
        gx, gy = cls.glove_pos(ang, punch)
        x0 = min(-180, gx - 90)
        x1 = max(180, gx + 90)
        y0 = min(-380, gy - 90)
        y1 = max(30, gy + 90)
        p = Pen(x1 - x0, y1 - y0, origin=(-x0, -y0), scale=scale)
        mood = s.get("mood", "happy")
        t = s.get("t", 0.0)

        # antenna (blinks while active)
        p.stroke([(118, -262), (128, -340)], INK, 7)
        on = s.get("active") and (int(t * 6) % 2 == 0)
        p.circle(128, -348, 14, fill=hex2rgba("#FF3B3B") if on else hex2rgba("#8A3B3B"))

        # spring arm (zigzag) then glove — drawn behind the box top edge
        a = math.radians(ang)
        mx, my = cls.MOUNT
        L = math.hypot(gx - mx, gy - my)
        n = 9
        pts = []
        for i in range(n + 1):
            d = L * i / n
            off = (18 if i % 2 else -18) if 0 < i < n else 0
            px, py = _rot(d, off, a)
            pts.append((mx + px, my + py))
        p.stroke(pts, INK, 15)
        p.stroke(pts, hex2rgba("#B8C2CC"), 7)
        # glove
        cx, cy = gx, gy
        tx, ty = _rot(-30, -34, a)
        cuff = [_rot(-58, -30, a), _rot(-28, -30, a), _rot(-28, 30, a), _rot(-58, 30, a)]
        p.poly([(cx + x, cy + y) for x, y in cuff], fill=WHITE, width=7)
        p.circle(cx, cy, 50, fill=cls.GLOVE, width=8)
        p.circle(cx + tx, cy + ty, 21, fill=cls.GLOVE, width=7)
        hx, hy = _rot(14, -18, a)
        p.circle(cx + hx, cy + hy, 10, fill=(255, 255, 255, 140), width=0)

        # box body
        p.poly([(-150, -262), (150, -262), (164, 0), (-164, 0)], fill=cls.CARD)
        p.poly([(-150, -262), (-120, -300), (120, -300), (150, -262)], fill=cls.CARD_DARK)  # top flap
        p.rrect(-20, -262, 20, -120, 0, fill=cls.TAPE, width=0)
        p.poly([(-150, -262), (150, -262), (164, 0), (-164, 0)], fill=None)

        # label
        p.rrect(-120, -110, 120, -52, 10, fill=WHITE, width=6)
        p.text(0, -81, "SNOOZE-O-MATIC", 27, fill=INK)

        # big red button on the left face
        press = s.get("press", 0.0)
        p.ellipse(-98, -175, 34, 34, fill=hex2rgba("#5A5A66"), width=7)
        p.ellipse(-98, -175 + 4 * press, 25 - 4 * press, 25 - 4 * press, fill=hex2rgba("#FF3B3B"), width=6)

        # googly eyes / mood
        for ex in (42, 102):
            ey = -190
            if mood in ("asleep", "sleepy"):
                p.ellipse(ex, ey, 24, 24, fill=WHITE, width=6)
                lid = 0.92 if mood == "asleep" else 0.55
                y_l = ey - 24 + 48 * lid
                pts = [(ex + 24 * math.cos(k / 24 * 2 * math.pi), min(ey + 24 * math.sin(k / 24 * 2 * math.pi), y_l)) for k in range(24)]
                p.poly(pts, fill=cls.CARD_DARK, outline=None, width=0)
                p.ellipse(ex, ey, 24, 24, fill=None, width=6)
                continue
            p.ellipse(ex, ey, 24, 24, fill=WHITE, width=6)
            jig = math.sin(t * 13 + ex) * 4 if s.get("active") else 0
            p.circle(ex + 6 + jig, ey + 6, 10, fill=INK, width=0)
            if mood == "angry":
                side = -1 if ex < 72 else 1
                p.stroke([(ex - 26, ey - 30 - 10 * side), (ex + 26, ey - 30 + 10 * side)], INK, 9)
        return p.finish(), p.origin_px()


class AlarmClock:
    """Classic twin-bell alarm clock. state: ringing (bool), t."""
    name = "clock"
    BODY = hex2rgba("#3D7DD8")

    @classmethod
    def render(cls, s: dict, scale: float = 1.0):
        p = Pen(320, 300, origin=(160, 270), scale=scale)
        t = s.get("t", 0.0)
        ringing = s.get("ringing", False)
        # legs
        p.stroke([(-36, -30), (-50, -4)], INK, 9)
        p.stroke([(36, -30), (50, -4)], INK, 9)
        # bells + hammer
        wob = math.sin(t * 60) * 6 if ringing else 0
        for bx in (-48, 48):
            p.ellipse(bx + wob * (1 if bx > 0 else -1), -158, 34, 26, fill=hex2rgba("#F4C430"), width=7)
        p.stroke([(0, -150), (0, -176)], INK, 7)
        p.circle(0, -180 + abs(wob), 8, fill=INK, width=0)
        # body + face
        p.circle(0, -88, 72, fill=cls.BODY)
        p.circle(0, -88, 54, fill=WHITE, width=6)
        for k in range(12):
            a = k / 12 * 2 * math.pi
            p.stroke([(44 * math.cos(a), -88 + 44 * math.sin(a)), (50 * math.cos(a), -88 + 50 * math.sin(a))], INK, 4, caps=False)
        p.stroke([(0, -88), (0, -124)], INK, 7)       # minute hand -> 12
        p.stroke([(0, -88), (-22, -76)], INK, 8)       # hour hand -> ~8
        p.circle(0, -88, 7, fill=INK, width=0)
        if ringing:
            for side in (-1, 1):
                for k in range(3):
                    a = math.radians(-60 + k * 30) if side > 0 else math.radians(-120 - k * 30)
                    r0, r1 = 92 + 6 * math.sin(t * 30), 118 + 6 * math.sin(t * 30)
                    p.stroke([(r0 * math.cos(a), -110 + r0 * math.sin(a)), (r1 * math.cos(a), -110 + r1 * math.sin(a))], INK, 7)
        return p.finish(), p.origin_px()


PROPS = {"box": SnoozeOMatic, "clock": AlarmClock}
