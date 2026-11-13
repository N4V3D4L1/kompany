"""Global studio configuration: output format, paths, palette."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
EPISODES = ROOT / "episodes"
OUTPUT = ROOT / "output"
FONT_DIR = ASSETS / "fonts"

# --- Delivery format (YouTube Shorts) -------------------------------------
WIDTH, HEIGHT = 1080, 1920
FPS = 30
SAMPLE_RATE = 48000
SUPERSAMPLE = 2            # vector shapes are drawn at 2x and downsampled (anti-aliasing)
MAX_SHORTS_SECONDS = 60.0

# Target loudness for YouTube (integrated LUFS / true-peak dBTP)
TARGET_LUFS = -14.0
TARGET_TP = -1.5

# Areas covered by the Shorts player UI (approximate, in output pixels).
# Captions and key action must avoid these bands.
SAFE_TOP = 220
SAFE_BOTTOM = 1920 - 420
SAFE_RIGHT = 1080 - 150

# --- House style ----------------------------------------------------------
INK = (43, 29, 46, 255)        # outline colour used by every asset
OUTLINE = 9                    # outline width in output pixels

FFMPEG = os.environ.get("N4V3D_FFMPEG") or shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = os.environ.get("N4V3D_FFPROBE") or shutil.which("ffprobe") or "ffprobe"


def font_path(weight: str = "Black") -> str:
    """Return a bundled font path (falls back to system DejaVu)."""
    p = FONT_DIR / f"Inter-{weight}.otf"
    if p.exists():
        return str(p)
    for cand in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",):
        if Path(cand).exists():
            return cand
    raise FileNotFoundError("No usable font found")
