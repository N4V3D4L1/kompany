"""N4V3D MEDIA command line.

  python -m n4v3d_media produce productions/hs001_what_causes_acne [--preview]
  python -m n4v3d_media gate    productions/hs001_what_causes_acne
  python -m n4v3d_media review  releases/hs001_... --reviewer NAME --scores storytelling=18,visual=16,...
  python -m n4v3d_media worker  [--once]          # orchestrator worker
  python -m n4v3d_media enqueue productions/...   # add a production to the pipeline
  python -m n4v3d_media status                    # pipeline state
  python -m n4v3d_media stop | resume             # emergency stop
  python -m n4v3d_media dashboard [--port 8787]   # Control Center
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser(prog="n4v3d_media")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("produce"); p.add_argument("path"); p.add_argument("--preview", action="store_true"); p.add_argument("--workers", type=int)
    g = sub.add_parser("gate"); g.add_argument("path")
    r = sub.add_parser("review"); r.add_argument("release"); r.add_argument("--reviewer", required=True); r.add_argument("--scores", required=True); r.add_argument("--notes", default="")
    w = sub.add_parser("worker"); w.add_argument("--once", action="store_true"); w.add_argument("--interval", type=float, default=30)
    e = sub.add_parser("enqueue"); e.add_argument("path")
    sub.add_parser("status"); sub.add_parser("stop"); sub.add_parser("resume")
    a = sub.add_parser("approve"); a.add_argument("job_id", type=int); a.add_argument("--by", required=True)
    d = sub.add_parser("dashboard"); d.add_argument("--port", type=int, default=8787); d.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args(argv)

    if args.cmd == "produce":
        from .production import produce
        produce(args.path, workers=args.workers, preview=args.preview)
    elif args.cmd == "gate":
        from .production import load
        from .research import gate
        print(json.dumps(gate(load(args.path)), indent=2))
    elif args.cmd == "review":
        from .scorecard import record_review
        scores = {}
        for kv in args.scores.split(","):
            k, v = kv.split("=")
            scores[k.strip()] = {"score": int(v), "reason": "human review"}
        card = record_review(Path(args.release), args.reviewer, scores, args.notes)
        print(f"recorded review by {args.reviewer}; re-run QC/scoring via the worker or `produce` to update totals")
    elif args.cmd in ("worker", "enqueue", "status", "stop", "resume", "approve"):
        from .orchestrator import worker as wk
        return wk.cli(args)
    elif args.cmd == "dashboard":
        from .dashboard.app import serve
        serve(args.host, args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
