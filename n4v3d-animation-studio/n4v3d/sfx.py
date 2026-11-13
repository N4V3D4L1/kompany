"""Procedurally synthesised sound effects (royalty-free by construction).

Every effect is a function returning float32 mono samples at 48 kHz.
`export_library()` writes them all to assets/sfx/ for reuse in other tools.
"""
from __future__ import annotations

import numpy as np

from . import config

SR = config.SAMPLE_RATE
_rng = np.random.default_rng(7)


def _t(dur):
    return np.arange(int(dur * SR)) / SR


def _env(n, a=0.005, r=0.1, shape=4.0):
    t = np.arange(n) / SR
    att = np.clip(t / max(a, 1e-4), 0, 1)
    dec = np.exp(-shape * np.maximum(0, t - a) / max(r, 1e-4))
    return att * dec


def _noise(n):
    return _rng.uniform(-1, 1, n).astype(np.float32)


def _lowpass(x, alpha):
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += alpha * (v - acc)
        y[i] = acc
    return y


def _sweep_lp(x, a0, a1):
    """One-pole low-pass whose cutoff sweeps from a0 to a1 (vectorised in blocks)."""
    y = np.empty_like(x)
    acc = 0.0
    n = len(x)
    alphas = np.linspace(a0, a1, n)
    for i in range(n):
        acc += alphas[i] * (x[i] - acc)
        y[i] = acc
    return y


def _norm(x, peak=0.9):
    m = np.max(np.abs(x)) or 1.0
    return (x / m * peak).astype(np.float32)


def whoosh(dur=0.45):
    n = int(dur * SR)
    x = _noise(n)
    a = np.sin(np.linspace(0, np.pi, n)) ** 2
    y = _sweep_lp(x, 0.02, 0.25) - _sweep_lp(x, 0.005, 0.05)
    return _norm(y * a, 0.7)


def boing(dur=0.6, f0=180, f1=520):
    t = _t(dur)
    f = f0 + (f1 - f0) * (1 - np.exp(-t * 9)) + 40 * np.sin(2 * np.pi * 14 * t) * np.exp(-t * 3)
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(ph) + 0.3 * np.sin(2 * ph)
    return _norm(y * _env(len(t), 0.004, dur * 0.7, 3.0), 0.75)


def bonk(dur=0.35):
    t = _t(dur)
    f = 140 * np.exp(-t * 18) + 70
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.001, 0.18, 4)
    knock = np.sin(2 * np.pi * 900 * t) * _env(len(t), 0.0005, 0.03, 5) * 0.6
    click = _noise(len(t)) * _env(len(t), 0.0003, 0.012, 6) * 0.5
    return _norm(body + knock + click, 0.95)


def thud(dur=0.4):
    t = _t(dur)
    f = 90 * np.exp(-t * 10) + 45
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.002, 0.25, 4)
    y += _lowpass(_noise(len(t)), 0.05) * _env(len(t), 0.001, 0.08, 4) * 2
    return _norm(y, 0.95)


def alarm(dur=1.6):
    t = _t(dur)
    gate = (np.sin(2 * np.pi * 14 * t) > 0).astype(np.float32)
    bell = sum(np.sin(2 * np.pi * f * t) / (k + 1) for k, f in enumerate((2100, 2630, 3170, 4200)))
    y = bell * gate * (0.6 + 0.4 * np.abs(np.sin(2 * np.pi * 3 * t)))
    fade = np.minimum(1, (dur - t) / 0.08)
    return _norm(y * fade, 0.55)


def click(dur=0.08):
    t = _t(dur)
    y = np.sin(2 * np.pi * 2400 * t) * _env(len(t), 0.0003, 0.01, 6) + _noise(len(t)) * _env(len(t), 0.0002, 0.006, 6)
    return _norm(y, 0.6)


def ding(dur=1.0):
    t = _t(dur)
    y = sum(np.sin(2 * np.pi * f * t) * a for f, a in ((1320, 1), (2640, .4), (3960, .2)))
    return _norm(y * _env(len(t), 0.002, 0.6, 3), 0.6)


def pop(dur=0.12):
    t = _t(dur)
    f = 300 + 900 * np.exp(-t * 40)
    return _norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.001, 0.06, 4), 0.7)


def snore(dur=1.6):
    t = _t(dur)
    breath = np.sin(np.pi * t / dur) ** 2
    rasp = _lowpass(_noise(len(t)), 0.03) * (0.6 + 0.4 * np.sin(2 * np.pi * 38 * t))
    tone = np.sin(2 * np.pi * (90 + 20 * t / dur) * t) * 0.4
    return _norm((rasp * 4 + tone) * breath, 0.5)


def slurp(dur=0.5):
    t = _t(dur)
    y = _sweep_lp(_noise(len(t)), 0.05, 0.4) * (np.sin(2 * np.pi * 9 * t) > 0) * np.sin(np.pi * t / dur)
    return _norm(y, 0.4)


def skid(dur=0.35):
    t = _t(dur)
    f = 1500 - 700 * t / dur
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.5 + 0.5 * _noise(len(t)))
    return _norm(y * np.minimum(1, (dur - t) / 0.08) * np.minimum(1, t / 0.01), 0.35)


def sting(dur=1.4):
    """Short upbeat end-card jingle (C major arpeggio + chord)."""
    out = np.zeros(int(dur * SR), np.float32)
    notes = [(0.00, 523.25), (0.11, 659.25), (0.22, 783.99), (0.36, 1046.5)]
    for st, f in notes:
        seg = pluck(f, 0.9)
        i = int(st * SR)
        out[i:i + len(seg)] += seg[: len(out) - i]
    return _norm(out, 0.7)


def pluck(freq, dur=0.6, decay=0.996):
    """Karplus-Strong plucked string (block-vectorised: one period per step)."""
    n = int(dur * SR)
    p = max(2, int(SR / freq))
    buf = np.random.default_rng(int(freq * 10)).uniform(-1, 1, p).astype(np.float32)
    blocks = []
    for _ in range(n // p + 1):
        blocks.append(buf)
        buf = decay * 0.5 * (buf + np.roll(buf, -1))
    return np.concatenate(blocks)[:n].astype(np.float32)


LIBRARY = {
    "whoosh": whoosh, "boing": boing, "bonk": bonk, "thud": thud, "alarm": alarm,
    "click": click, "ding": ding, "pop": pop, "snore": snore, "slurp": slurp,
    "skid": skid, "sting": sting,
}

_cache: dict = {}


def get(name: str) -> np.ndarray:
    if name not in _cache:
        if name not in LIBRARY:
            raise KeyError(f"unknown sfx '{name}'. available: {sorted(LIBRARY)}")
        _cache[name] = LIBRARY[name]()
    return _cache[name]


def export_library(out_dir=None):
    from .voice import write_wav
    out_dir = out_dir or (config.ASSETS / "sfx")
    out_dir.mkdir(parents=True, exist_ok=True)
    for k in LIBRARY:
        write_wav(out_dir / f"{k}.wav", get(k))
    return out_dir
