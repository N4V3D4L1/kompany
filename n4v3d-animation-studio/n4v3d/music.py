"""Procedural background music: a light, bouncy ukulele-style loop.

Original composition generated from a chord progression, so there are no
licensing questions. Swap in a licensed track later via the episode's
`music.file` field.
"""
from __future__ import annotations

import numpy as np

from . import config
from .sfx import pluck

SR = config.SAMPLE_RATE

NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
CHORDS = {
    "C": ("C", "E", "G"), "G": ("G", "B", "D"), "Am": ("A", "C", "E"), "F": ("F", "A", "C"),
    "Dm": ("D", "F", "A"), "Em": ("E", "G", "B"),
}


def freq(name: str, octave: int) -> float:
    return 440.0 * 2 ** ((NOTE[name] + 12 * (octave - 4) - 9) / 12)


def bouncy_loop(duration: float, bpm: float = 118, progression=("C", "Am", "F", "G")) -> np.ndarray:
    beat = 60.0 / bpm
    n = int(duration * SR)
    out = np.zeros(n + SR * 2, np.float32)
    cache: dict = {}

    def add(f, start, dur, gain):
        key = (round(f, 2), dur)
        if key not in cache:
            cache[key] = pluck(f, dur)
        seg = cache[key] * gain
        i = int(start * SR)
        out[i:i + len(seg)] += seg[: max(0, len(out) - i)]

    bar = 0
    t = 0.0
    while t < duration:
        ch = CHORDS[progression[bar % len(progression)]]
        root = ch[0]
        # bass on beats 1 and 3
        add(freq(root, 2), t, 0.9, 0.55)
        add(freq(ch[2], 2), t + 2 * beat, 0.9, 0.45)
        # ukulele strum pattern: down, down-up, up-down-up
        for k, (pos, g) in enumerate(((0, .5), (1, .4), (1.5, .3), (2.5, .3), (3, .4), (3.5, .3))):
            for j, nm in enumerate(ch):
                add(freq(nm, 4), t + pos * beat + j * 0.012, 0.5, g * 0.28)
        # little melody hook every other bar
        if bar % 2 == 1:
            for k, nm in enumerate((ch[2], ch[1], ch[0], ch[1])):
                add(freq(nm, 5), t + (0.5 + k * 0.5) * beat, 0.35, 0.16)
        # shaker
        for k in range(8):
            i = int((t + k * beat / 2) * SR)
            m = int(0.04 * SR)
            if i + m < len(out):
                out[i:i + m] += np.random.default_rng(i).uniform(-1, 1, m).astype(np.float32) * np.linspace(0.05, 0, m)
        t += 4 * beat
        bar += 1
    out = out[:n]
    # fade in/out
    f = int(0.4 * SR)
    out[:f] *= np.linspace(0, 1, f)
    out[-f * 2:] *= np.linspace(1, 0, f * 2)
    return out / (np.max(np.abs(out)) or 1) * 0.8
