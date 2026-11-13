"""Narration: per-segment neural TTS with persona presets and caching.

Personas (consistent voice identity per channel):
  health  — calm, knowledgeable, reassuring  -> Kokoro af_heart, speed 0.98
  history — curious, cinematic, authoritative -> Kokoro bm_george, speed 1.04
  general — energetic, approachable           -> Kokoro am_puck,  speed 1.08
A recorded human take always wins: productions/<id>/voice/seg_<n>.wav.
Falls back to the offline flite placeholder if Kokoro is unavailable (flagged in QC).
"""
from __future__ import annotations

from pathlib import Path

from . import VAR  # noqa: F401  (ensures studio path is registered)
from n4v3d import voice as V

PERSONAS = {
    "health": {"provider": "kokoro", "voice": "af_heart", "speed": 0.98},
    "history": {"provider": "kokoro", "voice": "bm_george", "speed": 1.04},
    "general": {"provider": "kokoro", "voice": "am_puck", "speed": 1.08},
}


def synth_segments(prod: dict, work: Path):
    """Return list of (wav_path, samples, provider) for every segment."""
    cfg = dict(PERSONAS.get(prod.get("persona", "general"), PERSONAS["general"]))
    cfg.update(prod.get("narrator", {}))
    rec_dir = Path(prod["_dir"]) / "voice"
    out = []
    for i, seg in enumerate(prod["segments"]):
        sid = f"seg_{i:02d}"
        wav, provider = V.synth_line(sid, seg.get("tts", seg["text"]), cfg, work / "voice_cache", rec_dir)
        out.append((wav, V.read_wav(wav), provider))
    return out
