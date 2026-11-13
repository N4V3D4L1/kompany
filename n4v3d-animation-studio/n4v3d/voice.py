"""Voice generation.

Providers (chosen per cast member in the episode file):

* ``flite``     – offline placeholder TTS via FFmpeg's built-in libflite,
                  pitch/tempo-shifted into a cartoon voice. Always available.
* ``recorded``  – real voice-actor takes. Drop ``<line_id>.wav`` into the
                  episode's ``voice/`` folder and it replaces the TTS take
                  automatically (any provider falls back to this first).

Adding a cloud TTS later = one more class with ``synth(text, out_path)``.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import wave
from pathlib import Path

import numpy as np

from . import config


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(map(str, cmd))}\n{r.stderr[-2000:]}")
    return r


def read_wav(path) -> np.ndarray:
    """Read a wav as float32 mono at the studio sample rate (resampling via ffmpeg if needed)."""
    path = Path(path)
    with wave.open(str(path), "rb") as w:
        sr, ch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if sr != config.SAMPLE_RATE or sw != 2:
        tmp = path.with_suffix(".48k.wav")
        run([config.FFMPEG, "-y", "-loglevel", "error", "-i", str(path), "-ac", "1",
             "-ar", str(config.SAMPLE_RATE), "-sample_fmt", "s16", str(tmp)])
        return read_wav(tmp)
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    return a


def write_wav(path, data: np.ndarray, sr: int = config.SAMPLE_RATE):
    data = np.asarray(data, dtype=np.float32)
    ch = 1 if data.ndim == 1 else data.shape[1]
    pcm = (np.clip(data, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


class FliteVoice:
    """Offline placeholder voice: flite TTS + pitch/tempo shift + light EQ."""

    def __init__(self, voice="rms", pitch=1.0, tempo=1.0, eq="", **_):
        self.voice, self.pitch, self.tempo, self.eq = voice, float(pitch), float(tempo), eq

    def key(self, text):
        return hashlib.sha1(json.dumps([text, self.voice, self.pitch, self.tempo, self.eq]).encode()).hexdigest()[:16]

    def synth(self, text: str, out_path: Path):
        out_path = Path(out_path)
        txt = out_path.with_suffix(".txt")
        txt.write_text(text)
        base_sr = 8000 if self.voice == "kal" else 16000
        a = self.tempo / self.pitch
        tempo_chain = []
        while a < 0.5:
            tempo_chain.append("atempo=0.5")
            a /= 0.5
        tempo_chain.append(f"atempo={a:.4f}")
        trim = "silenceremove=start_periods=1:start_threshold=-50dB"
        af = ",".join([
            f"asetrate={int(base_sr * self.pitch)}", f"aresample={config.SAMPLE_RATE}", *tempo_chain,
            "highpass=f=90", "lowpass=f=9000",
            trim, "areverse", trim, "areverse",
            "acompressor=threshold=-18dB:ratio=3:attack=5:release=80",
        ] + ([self.eq] if self.eq else []))
        run([config.FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi",
             "-i", f"flite=textfile='{txt}':voice={self.voice}", "-af", af,
             "-ac", "1", "-ar", str(config.SAMPLE_RATE), "-sample_fmt", "s16", str(out_path)])
        txt.unlink(missing_ok=True)
        a = read_wav(out_path)
        pad = np.zeros(int(0.03 * config.SAMPLE_RATE), np.float32)
        write_wav(out_path, np.concatenate([pad, a / (np.max(np.abs(a)) or 1) * 0.85, pad]))
        return out_path


PROVIDERS = {"flite": FliteVoice}


def synth_line(line_id: str, text: str, cast_cfg: dict, cache_dir: Path, recorded_dir: Path | None) -> tuple[Path, str]:
    """Return (wav path, provider used) for one line, with caching."""
    if recorded_dir is not None:
        rec = Path(recorded_dir) / f"{line_id}.wav"
        if rec.exists():
            return rec, "recorded"
    prov = cast_cfg.get("provider", "flite")
    cls = PROVIDERS.get(prov)
    if cls is None:
        print(f"  ! voice provider '{prov}' unavailable, falling back to flite placeholder")
        cls = FliteVoice
        prov = "flite"
    v = cls(**cast_cfg)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"{line_id}_{v.key(text)}.wav"
    if not out.exists():
        v.synth(text, out)
    return out, f"{prov}-placeholder"


def envelope(samples: np.ndarray, fps: int = config.FPS, sr: int = config.SAMPLE_RATE) -> np.ndarray:
    """Per-video-frame mouth openness (0..1) from audio loudness — automatic lip-sync."""
    hop = sr // fps
    n = int(np.ceil(len(samples) / hop))
    out = np.zeros(n, dtype=np.float32)
    for i in range(n):
        seg = samples[max(0, i * hop - hop // 2): i * hop + hop + hop // 2]
        out[i] = np.sqrt(np.mean(seg * seg)) if len(seg) else 0.0
    ref = np.percentile(out, 92) if np.any(out > 0) else 1.0
    out = np.clip(out / max(ref, 1e-4), 0, 1)
    out[out < 0.18] = 0.0
    # snappier cartoon mouth: quantise into 4 shapes and lightly smooth
    out = np.round(out * 3) / 3
    sm = out.copy()
    for i in range(1, n - 1):
        sm[i] = 0.25 * out[i - 1] + 0.5 * out[i] + 0.25 * out[i + 1]
    return sm
