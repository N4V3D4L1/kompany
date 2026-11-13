"""Command line interface.

  python -m n4v3d render  episodes/ep001_snooze_o_matic [--preview] [--workers N]
  python -m n4v3d validate episodes/ep001_snooze_o_matic
  python -m n4v3d still   episodes/ep001_snooze_o_matic --t 12.5 --out frame.png
  python -m n4v3d qc      output/.../video.mp4
  python -m n4v3d assets  # export character sheets + SFX library
  python -m n4v3d draft   "premise text"   # AI-assisted script draft
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config


def main(argv=None):
    ap = argparse.ArgumentParser(prog="n4v3d", description="N4V3D Animation Studio pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("render", help="render an episode to MP4")
    r.add_argument("episode")
    r.add_argument("--preview", action="store_true", help="first 6 seconds only")
    r.add_argument("--workers", type=int)
    r.add_argument("--skip-qc", action="store_true")

    v = sub.add_parser("validate", help="validate an episode script")
    v.add_argument("episode")

    s = sub.add_parser("still", help="render a single frame")
    s.add_argument("episode")
    s.add_argument("--t", type=float, nargs="+", default=[5.0])
    s.add_argument("--out", default="still.png")

    q = sub.add_parser("qc", help="run automated QC on a video")
    q.add_argument("video")

    sub.add_parser("assets", help="export character sheets, backgrounds and SFX library")

    d = sub.add_parser("draft", help="AI-assisted episode draft from a premise")
    d.add_argument("premise")
    d.add_argument("--id", default="ep_draft")
    d.add_argument("--out")

    a = ap.parse_args(argv)
    if a.cmd == "render":
        from .render import render_episode
        rep = render_episode(a.episode, workers=a.workers, preview=a.preview, skip_qc=a.skip_qc)
        return 0 if rep.get("qc_passed", True) else 2
    if a.cmd == "validate":
        from .episode import load, validate
        ep = load(a.episode)
        for w in validate(ep):
            print("warn:", w)
        n_lines = sum(1 for sc in ep["scenes"] for b in sc["beats"] if "line" in b)
        print(f"OK: {ep['title']} — {len(ep['scenes'])} scenes, {n_lines} lines")
        return 0
    if a.cmd == "still":
        from .episode import load
        from .timeline import build_fitted
        from .animator import Renderer
        ep = load(a.episode)
        work = config.OUTPUT / "_stills"
        tl = build_fitted(ep, work)
        rd = Renderer(tl, work / "bg")
        for i, t in enumerate(a.t):
            out = Path(a.out)
            if len(a.t) > 1:
                out = out.with_name(f"{out.stem}_{t:05.2f}{out.suffix}")
            rd.frame(t).save(out)
            print(out)
        return 0
    if a.cmd == "qc":
        from .qc import run_qc
        return 0 if run_qc(Path(a.video))["passed"] else 2
    if a.cmd == "assets":
        from .sheets import export_all
        export_all()
        return 0
    if a.cmd == "draft":
        from .ai.writer import draft_episode
        print(draft_episode(a.premise, a.id, a.out))
        return 0


if __name__ == "__main__":
    sys.exit(main())
