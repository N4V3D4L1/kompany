"""N4V3D MEDIA v2 — AI-assisted educational video production system."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT.parent / "n4v3d-animation-studio"   # reuse the proven render/audio/QC core
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

PRODUCTIONS = ROOT / "productions"
RELEASES = ROOT / "releases"
VAR = ROOT / "var"            # runtime state: database, logs, render workspace
__version__ = "2.0.0"
