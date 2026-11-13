"""Documentary sound design: extra procedural SFX + calm music beds (licence-free by construction)."""
from __future__ import annotations

import numpy as np

from . import VAR  # noqa: F401
from n4v3d import sfx as base
from n4v3d.sfx import SR, _env, _lowpass, _noise, _norm, _sweep_lp, _t, pluck


def swell(dur=1.6):
    t = _t(dur)
    env = np.sin(np.pi * t / dur) ** 2
    y = sum(np.sin(2 * np.pi * f * t) for f in (110, 165, 220.5)) / 3
    y += _sweep_lp(_noise(len(t)), 0.002, 0.03) * 3
    return _norm(y * env, 0.5)


def tick(dur=0.06):
    t = _t(dur)
    return _norm(np.sin(2 * np.pi * 1800 * t) * _env(len(t), 0.0005, 0.02, 5), 0.4)


def chime(dur=1.8):
    t = _t(dur)
    y = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t * d) for f, a, d in ((880, 1, 2.5), (1320, .5, 3), (1760, .3, 4), (2637, .15, 5)))
    return _norm(y * np.minimum(1, t / 0.005), 0.45)


def wind(dur=4.0):
    t = _t(dur)
    y = _sweep_lp(_noise(len(t)), 0.004, 0.012) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.3 * t))
    fade = np.minimum(1, t / 0.8) * np.minimum(1, (dur - t) / 1.0)
    return _norm(y * fade, 0.35)


def stamp(dur=0.35):
    return base.thud(dur)


def stylus(dur=0.12):
    t = _t(dur)
    y = _lowpass(_noise(len(t)), 0.25) * _env(len(t), 0.001, 0.05, 5) + np.sin(2 * np.pi * 420 * t) * _env(len(t), 0.001, 0.03, 6) * 0.4
    return _norm(y, 0.5)


def coin(dur=1.4):
    t = _t(dur)
    partials = ((2350, 1.0, 3.0), (3610, .7, 4.0), (5240, .45, 5.0), (6890, .3, 6.5))
    y = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t * d) for f, a, d in partials)
    hit = _noise(len(t)) * _env(len(t), 0.0003, 0.01, 6)
    return _norm(y + hit * 0.8 + base.thud(dur)[: len(t)] * 0.5, 0.8)


EXTRA = {"swell": swell, "tick": tick, "chime": chime, "wind": wind, "stamp": stamp, "stylus": stylus, "coin": coin}
for k, fn in EXTRA.items():  # register with the shared SFX library
    base.LIBRARY.setdefault(k, fn)


def pad_bed(duration, style="science_pad"):
    """Slow evolving chord pad; 'science_pad' (cool, minor-9) or 'ancient_pad' (warm, modal + lyre plucks)."""
    n = int(duration * SR)
    t = np.arange(n) / SR
    if style == "ancient_pad":
        chords = [(146.83, 220.0, 293.66, 349.23), (130.81, 196.0, 261.63, 329.63), (116.54, 174.61, 233.08, 293.66), (130.81, 196.0, 261.63, 311.13)]
    else:
        chords = [(110.0, 164.81, 261.63, 329.63), (98.0, 146.83, 246.94, 293.66), (87.31, 130.81, 220.0, 261.63), (98.0, 146.83, 233.08, 293.66)]
    seg = 6.0
    out = np.zeros(n, np.float32)
    for i in range(int(np.ceil(duration / seg)) + 1):
        ch = chords[i % len(chords)]
        a, b = int(max(0, (i * seg - 1.5)) * SR), int(min(duration, (i + 1) * seg + 1.5) * SR)
        if a >= n:
            break
        tt = t[a:b]
        env = np.minimum(1, (tt - tt[0]) / 1.5) * np.minimum(1, (tt[-1] - tt) / 1.5)
        y = sum(np.sin(2 * np.pi * f * tt + 0.3 * np.sin(2 * np.pi * 0.2 * tt)) * (0.6 if f > 200 else 1.0) for f in ch)
        y += 0.25 * sum(np.sin(2 * np.pi * f * 2.003 * tt) for f in ch[:2])
        out[a:b] += (y * env).astype(np.float32)
    out = _lowpass(out, 0.08) if n < SR * 2 else _block_lowpass(out)
    if style == "ancient_pad":  # sparse lyre-like plucks
        notes = [293.66, 349.23, 440.0, 392.0, 349.23, 293.66, 261.63, 293.66]
        for k, st in enumerate(np.arange(2.0, duration - 2, 1.5)):
            p = pluck(notes[k % len(notes)], 1.4) * 0.35
            i = int(st * SR)
            out[i:i + len(p)] += p[: max(0, n - i)]
    else:  # soft pulse
        for st in np.arange(0.0, duration, 0.75):
            i = int(st * SR)
            m = int(0.25 * SR)
            if i + m < n:
                out[i:i + m] += np.sin(2 * np.pi * 55 * t[:m]) * np.exp(-t[:m] * 14) * 0.6
    f = int(1.0 * SR)
    out[:f] *= np.linspace(0, 1, f)
    out[-int(2.0 * SR):] *= np.linspace(1, 0, int(2.0 * SR))
    return out / (np.max(np.abs(out)) or 1) * 0.8


def _block_lowpass(x, k=64):
    """Cheap smoothing for long buffers (moving average)."""
    ker = np.ones(k, np.float32) / k
    return np.convolve(x, ker, mode="same").astype(np.float32)
