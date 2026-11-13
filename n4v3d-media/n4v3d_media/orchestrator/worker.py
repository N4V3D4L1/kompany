"""Pipeline worker: advances jobs through the production stages.

    IDEA → RESEARCH → FACT_CHECK → SCRIPT → STORYBOARD → ASSETS → ANIMATION → VOICE → EDIT
    → QUALITY_REVIEW → APPROVAL → PUBLISH → ANALYTICS → IMPROVEMENT → DONE

Each handler returns one of:
    ("next", artifacts)  continue automatically to the next stage
    ("wait", reason)     needs a human (approval, expert review, credentials) — notified, re-checked each tick
    ("block", reason)    content/safety problem — stops until the production file is fixed

Exceptions are retried with exponential backoff (max_attempts, default 3), then the job fails
with a notification. A job whose heartbeat is stale (worker crashed mid-stage) is reset to
pending on the next start. The emergency stop (dashboard, `stop` command or var/STOP file)
halts every stage before it starts. The worker is designed to run as a background service
(systemd/cron templates in deploy/), not inside Claude Code.
"""
from __future__ import annotations

import datetime as dt
import json
import time
import traceback
from pathlib import Path

from .. import RELEASES, ROOT, VAR
from . import db

MAX_ATTEMPTS = 3
STALE_MINUTES = 45
HANDLERS = {}


def handler(stage):
    def deco(fn):
        HANDLERS[stage] = fn
        return fn
    return deco


def _prod(job):
    from ..production import load
    p = Path(job["path"])
    return load(p if p.is_absolute() else ROOT / p)


def _release_dir(prod):
    from ..production import _slug
    return RELEASES / f"{prod['id']}_{_slug(prod['title'])}"


@handler("IDEA")
def h_idea(job):
    prod = _prod(job)
    return "next", {"prod_id": prod["id"], "title": prod["title"]}


@handler("RESEARCH")
def h_research(job):
    prod = _prod(job)
    if len(prod.get("sources", [])) < 2 or not prod.get("claims"):
        return "block", "research incomplete: need >= 2 sources and a claim list"
    return "next", {"sources": len(prod["sources"])}


@handler("FACT_CHECK")
def h_fact(job):
    from ..research import gate
    g = gate(_prod(job))
    if not g["render_ok"]:
        return "block", "facts unverified: " + "; ".join(g["blockers"][:3])
    return "next", {"verified": g["counts"]["verified"], "claims": g["counts"]["claims"]}


@handler("SCRIPT")
def h_script(job):
    from ..story import check_story
    errs = [str(f) for f in check_story(_prod(job)) if f.level == "error"]
    return ("block", "; ".join(errs)) if errs else ("next", {})


@handler("STORYBOARD")
def h_storyboard(job):
    from ..production import plan
    prod = _prod(job)
    pl = plan(prod, VAR / "work" / prod["id"])     # narration synthesised + scene timing fixed
    if pl.duration > prod.get("target_duration", 60) + 0.01:
        return "block", f"planned duration {pl.duration:.1f}s exceeds target"
    return "next", {"planned_duration": round(pl.duration, 2), "scenes": len(pl.windows)}


@handler("ASSETS")
def h_assets(job):
    from ..production import SCENES
    from n4v3d import voice as V
    prod = _prod(job)
    missing = [s["scene"] for s in prod["segments"] if s["scene"] not in SCENES]
    if missing:
        return "block", f"missing scene assets: {missing}"
    return "next", {"neural_voice": V.kokoro_available()}


@handler("ANIMATION")
def h_animation(job):
    from ..production import produce
    meta = produce(job["path"] if Path(job["path"]).is_absolute() else ROOT / job["path"], log=lambda *a: None)
    return "next", {"video": meta["video"], "duration": meta["duration"], "qc_passed": meta["qc_passed"]}


@handler("VOICE")
def h_voice(job):
    rep = json.loads((_release_dir(_prod(job)) / "production_report.json").read_text())
    if not rep["voice"]:
        return "block", "no narration recorded"
    return "next", {"voice": rep["voice"]}


@handler("EDIT")
def h_edit(job):
    d = _release_dir(_prod(job))
    for f in ("captions.srt", "captions.ass", "thumbnail.jpg"):
        if not (d / f).exists():
            raise RuntimeError(f"edit artefact missing: {f}")
    return "next", {}


@handler("QUALITY_REVIEW")
def h_quality(job):
    d = _release_dir(_prod(job))
    qc = json.loads((d / "qc_report.json").read_text())
    card = json.loads((d / "scorecard.json").read_text())
    if not qc["passed"]:
        raise RuntimeError("technical QC failed")  # retried (re-render) up to MAX_ATTEMPTS
    return "next", {"score": card["total"], "score_status": card["status"]}


@handler("APPROVAL")
def h_approval(job):
    from ..research import gate
    prod = _prod(job)
    d = _release_dir(prod)
    card = json.loads((d / "scorecard.json").read_text())
    g = gate(prod)
    reasons = list(g["publish_blockers"])
    if not card.get("human_review"):
        reasons.append("human quality review not recorded")
    elif card["total"] < card["target"]:
        reasons.append(f"score {card['total']} below target {card['target']} (revision plan in SCORECARD.md)")
    if not job.get("approved_by"):
        reasons.append("owner publish approval missing")
    if reasons:
        return "wait", "; ".join(reasons)
    return "next", {"approved_by": job["approved_by"]}


@handler("PUBLISH")
def h_publish(job):
    from .. import youtube
    prod = _prod(job)
    if not youtube.configured():
        return "wait", "YouTube account not connected (see docs/YOUTUBE.md)"
    res = youtube.upload_release(_release_dir(prod), approved_by=job["approved_by"])
    return "next", {"youtube": res}


@handler("ANALYTICS")
def h_analytics(job):
    from .. import youtube
    if not youtube.configured():
        return "wait", "YouTube Analytics not connected"
    return "next", {"analytics": youtube.fetch_analytics(job)}


@handler("IMPROVEMENT")
def h_improve(job):
    return "next", {"note": "recommendations written to the dashboard analytics page"}


# ---------------------------------------------------------------------------
def recover_stale(con):
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=STALE_MINUTES)).isoformat(timespec="seconds")
    for j in con.execute("SELECT * FROM jobs WHERE status='running' AND (heartbeat IS NULL OR heartbeat < ?)", (cutoff,)):
        db.update(con, j["id"], status="pending")
        db.log(con, j["id"], j["stage"], "warn", "recovered stale running job (worker crash?) — will retry stage")


def due(con):
    t = db.now()
    return [dict(r) for r in con.execute(
        "SELECT * FROM jobs WHERE status IN ('pending','waiting') AND (next_run_at IS NULL OR next_run_at <= ?) ORDER BY id", (t,))]


def step(con, job, handlers=None):
    """Run one stage of one job. Returns the new status."""
    handlers = handlers or HANDLERS
    stage = job["stage"]
    if db.emergency_stopped(con):
        return "stopped"
    if stage == "DONE":
        db.update(con, job["id"], status="done")
        return "done"
    db.update(con, job["id"], status="running", heartbeat=db.now())
    try:
        kind, payload = handlers[stage](job)
    except Exception as e:
        attempts = job["attempts"] + 1
        err = f"{type(e).__name__}: {e}"
        if attempts >= get_max_attempts(con):
            db.update(con, job["id"], status="failed", attempts=attempts, last_error=err)
            db.log(con, job["id"], stage, "error", f"failed after {attempts} attempts: {err}")
            return "failed"
        delay = 30 * 2 ** attempts
        nxt = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=delay)).isoformat(timespec="seconds")
        db.update(con, job["id"], status="pending", attempts=attempts, last_error=err, next_run_at=nxt)
        db.log(con, job["id"], stage, "warn", f"attempt {attempts} failed ({err}); retry in {delay}s\n{traceback.format_exc(limit=3)}")
        return "retry"
    if kind == "next":
        arts = json.loads(job.get("artifacts") or "{}")
        arts[stage] = payload
        nxt_stage = db.STAGES[db.STAGES.index(stage) + 1]
        extra = {k: payload[k] for k in ("prod_id", "title") if k in payload}
        db.update(con, job["id"], stage=nxt_stage, status="pending" if nxt_stage != "DONE" else "done", attempts=0,
                  last_error=None, wait_reason=None, next_run_at=None, artifacts=json.dumps(arts), **extra)
        db.log(con, job["id"], stage, "info", f"{stage} complete → {nxt_stage}")
        return "advanced"
    if kind == "wait":
        recheck = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10)).isoformat(timespec="seconds")
        changed = job.get("wait_reason") != payload
        db.update(con, job["id"], status="waiting", wait_reason=payload, next_run_at=recheck)
        if changed:
            db.log(con, job["id"], stage, "action", f"human action needed: {payload}")
        return "waiting"
    db.update(con, job["id"], status="blocked", wait_reason=payload)
    db.log(con, job["id"], stage, "blocked", payload)
    return "blocked"


def get_max_attempts(con):
    return int(db.get_setting(con, "max_attempts", MAX_ATTEMPTS))


def run(once=False, interval=30.0, con=None):
    con = con or db.connect()
    recover_stale(con)
    db.set_setting(con, "worker_heartbeat", db.now())
    while True:
        db.set_setting(con, "worker_heartbeat", db.now())
        if not db.emergency_stopped(con):
            for job in due(con):
                # keep advancing a job while stages complete automatically
                while True:
                    st = step(con, job)
                    if st != "advanced":
                        break
                    job = dict(con.execute("SELECT * FROM jobs WHERE id=?", (job["id"],)).fetchone())
                    if db.emergency_stopped(con):
                        break
        if once:
            return
        time.sleep(interval)


def cli(args):
    con = db.connect()
    if args.cmd == "enqueue":
        p = Path(args.path).resolve()
        rel = p.relative_to(ROOT) if str(p).startswith(str(ROOT)) else p
        jid = db.enqueue(con, rel)
        print(f"job {jid} enqueued: {rel}")
    elif args.cmd == "worker":
        run(once=args.once, interval=args.interval, con=con)
    elif args.cmd == "status":
        print(f"emergency stop: {db.emergency_stopped(con)}")
        for j in db.jobs(con):
            print(f"#{j['id']:<3} {j['prod_id'] or '-':<6} {j['stage']:<15} {j['status']:<8} {j['wait_reason'] or j['last_error'] or ''}")
    elif args.cmd == "stop":
        db.set_setting(con, "emergency_stop", True)
        db.log(con, None, "-", "action", "EMERGENCY STOP engaged from CLI")
        print("emergency stop engaged")
    elif args.cmd == "resume":
        db.set_setting(con, "emergency_stop", False)
        (VAR / "STOP").unlink(missing_ok=True)
        db.log(con, None, "-", "info", "emergency stop released from CLI")
        print("resumed")
    elif args.cmd == "approve":
        db.update(con, args.job_id, approved_by=args.by, approved_at=db.now(), next_run_at=None)
        db.log(con, args.job_id, "APPROVAL", "info", f"publish approval recorded by {args.by}")
        print("approval recorded")
    return 0
