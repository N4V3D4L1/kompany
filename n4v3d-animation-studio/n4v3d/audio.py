"""Audio mix: dialogue + SFX + ducked music -> stereo WAV, then loudness measurement."""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

from . import config, music, sfx as sfxlib, voice
from .timeline import Timeline

SR = config.SAMPLE_RATE


def _place(buf, samples, t, gain, pan):
    i = int(round(t * SR))
    if i >= len(buf):
        return
    seg = samples[: len(buf) - i] * gain
    l = np.cos((pan + 1) * np.pi / 4)
    r = np.sin((pan + 1) * np.pi / 4)
    buf[i:i + len(seg), 0] += seg * l * 1.41
    buf[i:i + len(seg), 1] += seg * r * 1.41


def mix(tl: Timeline, out_path: Path) -> dict:
    n = int(np.ceil(tl.duration * SR))
    dlg = np.zeros((n, 2), np.float32)
    fx = np.zeros((n, 2), np.float32)
    for c in tl.clips:
        x = tl.entities[c.who].val("pos", c.t0)[0]
        pan = float(np.clip((x - config.WIDTH / 2) / (config.WIDTH / 2), -1, 1)) * 0.3
        _place(dlg, voice.read_wav(c.wav), c.t0, 1.0, pan)
    for t, name, gain, pan in tl.sfx:
        _place(fx, sfxlib.get(name), t, gain, pan)

    mcfg = tl.episode.get("music", {})
    if mcfg.get("file"):
        bed = voice.read_wav(Path(tl.episode["_dir"]) / mcfg["file"])[:n]
        bed = np.pad(bed, (0, max(0, n - len(bed))))
    else:
        bed = music.bouncy_loop(tl.duration, bpm=mcfg.get("bpm", 118))
    # sidechain-style ducking under dialogue
    presence = np.zeros(n, np.float32)
    for c in tl.clips:
        a, b = int(c.t0 * SR), min(n, int(c.t1 * SR))
        presence[a:b] = 1.0
    k = int(0.15 * SR)
    kern = np.ones(k, np.float32) / k
    presence = np.clip(np.convolve(presence, kern, mode="same") * 1.5, 0, 1)
    duck_db = mcfg.get("duck_db", -9.0)
    bed_gain = 10 ** (mcfg.get("gain_db", -15.0) / 20) * (1 - presence * (1 - 10 ** (duck_db / 20)))
    bed = bed[:n] * bed_gain
    mus = np.stack([bed, bed], axis=1)

    master = dlg * 1.0 + fx * 0.75 + mus
    peak_pre = float(np.max(np.abs(master)))
    master = np.tanh(master * 1.1) / np.tanh(1.1)   # gentle soft-clip safety
    voice.write_wav(out_path, master)
    return {"peak_pre_limiter": round(peak_pre, 3), "samples": n}


def measure_loudness(path: Path) -> dict:
    """First pass of EBU R128 loudnorm; returns measured stats for the linear second pass."""
    r = voice.run([config.FFMPEG, "-hide_banner", "-nostats", "-i", str(path), "-af",
                   f"loudnorm=I={config.TARGET_LUFS}:TP={config.TARGET_TP}:LRA=11:print_format=json",
                   "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    return json.loads(m.group(0))


def loudnorm_filter(stats: dict) -> str:
    return (f"loudnorm=I={config.TARGET_LUFS}:TP={config.TARGET_TP}:LRA=11:"
            f"measured_I={stats['input_i']}:measured_TP={stats['input_tp']}:"
            f"measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}:"
            f"offset={stats['target_offset']}:linear=true")
