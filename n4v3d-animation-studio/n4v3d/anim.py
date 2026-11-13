"""Easing curves and keyframe tracks used by the animator."""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field
from typing import Any


def _out_back(u, s=1.70158):
    u -= 1
    return u * u * ((s + 1) * u + s) + 1


def _out_elastic(u):
    if u in (0.0, 1.0):
        return u
    return 2 ** (-10 * u) * math.sin((u * 10 - 0.75) * (2 * math.pi) / 3) + 1


def _out_bounce(u):
    n, d = 7.5625, 2.75
    if u < 1 / d:
        return n * u * u
    if u < 2 / d:
        u -= 1.5 / d
        return n * u * u + 0.75
    if u < 2.5 / d:
        u -= 2.25 / d
        return n * u * u + 0.9375
    u -= 2.625 / d
    return n * u * u + 0.984375


EASES = {
    "linear": lambda u: u,
    "in": lambda u: u * u * u,
    "out": lambda u: 1 - (1 - u) ** 3,
    "in_out": lambda u: 4 * u * u * u if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2,
    "out_back": _out_back,
    "out_elastic": _out_elastic,
    "out_bounce": _out_bounce,
    "step": lambda u: 1.0 if u >= 1 else 0.0,
}


def ease(name: str, u: float) -> float:
    u = 0.0 if u < 0 else 1.0 if u > 1 else u
    return EASES.get(name, EASES["in_out"])(u)


def lerp(a, b, u):
    if isinstance(a, (tuple, list)):
        return tuple(lerp(x, y, u) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a + (b - a) * u
    return b if u >= 1 else a  # discrete values switch at the end


@dataclass
class _Seg:
    t0: float
    t1: float
    v1: Any
    ease: str


@dataclass
class Track:
    """A property animated over time with `set` (instant) and `tween` operations.

    Segments are evaluated in start order; each segment tweens from the value
    the track had at its start time to its target value.
    """
    default: Any
    segs: list = field(default_factory=list)

    def set(self, t: float, v):
        self.tween(t, 0.0, v, "step")

    def tween(self, t: float, dur: float, v, ease_name: str = "in_out"):
        seg = _Seg(t, t + max(0.0, dur), v, ease_name)
        idx = bisect.bisect_right([s.t0 for s in self.segs], t)
        self.segs.insert(idx, seg)

    def value(self, t: float):
        v = self.default
        for s in self.segs:
            if s.t0 > t:
                break
            if t >= s.t1:
                v = s.v1
            else:
                u = (t - s.t0) / (s.t1 - s.t0) if s.t1 > s.t0 else 1.0
                v = lerp(v, s.v1, ease(s.ease, u))
        return v


@dataclass
class FX:
    """A time-boxed procedural effect (hop, shake, punch, ...)."""
    name: str
    t0: float
    t1: float
    params: dict

    def active(self, t: float) -> bool:
        return self.t0 <= t < self.t1

    def u(self, t: float) -> float:
        return 0.0 if self.t1 <= self.t0 else min(1.0, max(0.0, (t - self.t0) / (self.t1 - self.t0)))
