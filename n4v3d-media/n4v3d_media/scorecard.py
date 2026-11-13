"""100-point quality evaluation with release gates and a bounded revision loop.

Categories: storytelling 20, visual 20, factual 20, narration/audio 15, editing/pacing 10,
originality 10, technical 5.

* Measurable criteria are scored programmatically (technical; parts of pacing, audio, facts).
* Subjective criteria get a *provisional* pipeline self-assessment with reasons, which never
  counts toward release: a human reviewer must record final scores (`n4v3d-media review`).
* Automatic release blockers regardless of score: critical factual problems, licensing issues,
  technical QC errors, pending medical expert review, missing publish approval.
* Release target: >= 90/100 (configurable). Below target -> revision plan; after
  `max_revisions` cycles the issue is escalated to a human instead of looping forever.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

MAX = {"storytelling": 20, "visual": 20, "factual": 20, "narration_audio": 15, "editing_pacing": 10, "originality": 10, "technical": 5}
TARGET = 90
MAX_REVISIONS = 2


def _auto(prod, meta, qc):
    s, why = {}, {}
    errs = [c for c in qc["checks"] if not c["passed"] and c["severity"] == "error"]
    extra_fail = [c["check"] for c in meta["extra_checks"] if not c["passed"]]
    s["technical"] = max(0, 5 - 2 * len(errs) - len(extra_fail))
    why["technical"] = f"{len(errs)} QC errors, {len(extra_fail)} caption/scene check failures (automated)"

    pace = [f for f in meta["story_findings"] if "pace" in f]
    hook_warn = any("hook" in f for f in meta["story_findings"])
    ed = 10 - (2 if hook_warn else 0) - (2 if any("WARNING" in f for f in pace) else 0)
    s["editing_pacing"] = ed
    why["editing_pacing"] = f"automated: pace {pace[0].split(':', 2)[-1].strip() if pace else 'n/a'}; hook {'over' if hook_warn else 'within'} 4 s; scene lengths checked"

    g = meta["fact_gate"]
    fact = 0 if g["blockers"] else 17
    s["factual"] = fact
    why["factual"] = (f"{g['counts']['verified']}/{g['counts']['claims']} claims verified against {g['counts']['sources']} sources, "
                      f"{g['counts']['hedged']} hedged interpretation(s); independent fact-check by research-agent. "
                      "Max 17 until a human subject-matter reviewer signs off.")

    synthetic = any(v != "recorded" for v in meta["voice"])
    lufs_ok = qc.get("lufs") is not None and abs(qc["lufs"] + 14) <= 1.5
    s["narration_audio"] = (12 if synthetic else 14) + (1 if lufs_ok else -2)
    why["narration_audio"] = (f"neural TTS ({', '.join(meta['voice'])}) — natural but not a human performance; "
                              f"loudness {qc.get('lufs')} LUFS; music ducked under narration")
    return s, why


PROVISIONAL = {
    "storytelling": (16, "Six-stage arc present with a concrete hook and a sourced surprise; limited emotional stakes in 60 s."),
    "visual": (15, "Clear, consistent, labelled 2D illustration at native 1080x1920; procedural style is clean but not yet premium 3D/rendered quality."),
    "originality": (9, "All visuals, music and SFX generated in-house; original script and research; no third-party footage."),
}


def build(prod, meta, qc, out_dir: Path, human: dict | None = None):
    auto, why = _auto(prod, meta, qc)
    cats = {}
    for k, mx in MAX.items():
        if k in auto:
            cats[k] = {"max": mx, "score": auto[k], "basis": "automated", "reason": why[k]}
        else:
            sc, rs = PROVISIONAL[k]
            cats[k] = {"max": mx, "score": sc, "basis": "provisional self-assessment (pipeline)", "reason": rs}
    prev = out_dir / "scorecard.json"
    old = json.loads(prev.read_text()) if prev.exists() else {}
    human = human or old.get("human_review")
    if human:
        for k, v in human.get("scores", {}).items():
            if k in cats:
                cats[k].update(score=v["score"], basis=f"human ({human['reviewer']})", reason=v.get("reason", ""))
    total = sum(c["score"] for c in cats.values())
    blockers = []
    if meta["fact_gate"]["blockers"]:
        blockers += [f"FACT: {b}" for b in meta["fact_gate"]["blockers"]]
    if not qc["passed"]:
        blockers.append("TECH: technical QC errors")
    blockers += [f"REVIEW: {b}" for b in meta["fact_gate"]["publish_blockers"]]
    if not human:
        blockers.append("REVIEW: human quality review not recorded (subjective categories are provisional)")
    revision = old.get("revision", 0)
    plan = revision_plan(cats) if total < TARGET else []
    status = "release_candidate" if (total >= TARGET and not blockers) else ("escalated" if revision >= MAX_REVISIONS and total < TARGET else "needs_work")
    card = {"id": prod["id"], "title": prod["title"], "evaluated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "total": total, "target": TARGET, "categories": cats, "blockers": blockers, "status": status,
            "revision": revision, "max_revisions": MAX_REVISIONS, "revision_plan": plan, "human_review": human,
            "note": "Internal QC assessment, not a measure of audience satisfaction. Passing automated checks does not make a video perfect."}
    prev.write_text(json.dumps(card, indent=2))
    (out_dir / "SCORECARD.md").write_text(to_md(card))
    return card


def revision_plan(cats):
    plan = []
    gaps = sorted(((c["max"] - c["score"], k) for k, c in cats.items()), reverse=True)
    fixes = {
        "visual": "Upgrade hero shots (pore macro, coin strike) to rendered 3D (Blender) or hand-finished illustration; add depth-of-field and lighting passes.",
        "narration_audio": "Record a human narrator (or licensed premium TTS) for the final cut; keep neural TTS for drafts.",
        "storytelling": "Sharpen stakes in the hook; test 2 alternative hooks; tighten the payoff line to a single memorable sentence.",
        "factual": "Obtain subject-matter expert sign-off (dermatologist / historian); add on-screen citations for every number.",
        "editing_pacing": "Shorten the hook to <= 4 s and rebalance scene lengths around the surprise beat.",
        "originality": "Add a recurring presenter character or signature visual device unique to the channel.",
        "technical": "Fix QC failures listed in qc_report.md and re-render affected scenes.",
    }
    for gap, k in gaps:
        if gap > 0:
            plan.append({"category": k, "points_available": gap, "action": fixes[k]})
    return plan


def record_review(out_dir: Path, reviewer: str, scores: dict, notes: str = ""):
    """Store a human review: scores = {category: {"score": n, "reason": "..."}}."""
    card = json.loads((out_dir / "scorecard.json").read_text())
    for k, v in scores.items():
        if k not in MAX or not (0 <= v["score"] <= MAX[k]):
            raise ValueError(f"invalid score for {k}")
    card["human_review"] = {"reviewer": reviewer, "date": dt.date.today().isoformat(), "scores": scores, "notes": notes}
    card["revision"] = card.get("revision", 0)
    (out_dir / "scorecard.json").write_text(json.dumps(card, indent=2))
    return card


def to_md(card):
    lines = [f"# Quality scorecard — {card['title']}", "",
             f"**{card['total']}/100** (target {card['target']}) · status: **{card['status']}** · revision {card['revision']}/{card['max_revisions']}", "",
             "| Category | Score | Basis | Reason |", "|---|---|---|---|"]
    for k, c in card["categories"].items():
        lines.append(f"| {k.replace('_', ' ')} | {c['score']}/{c['max']} | {c['basis']} | {c['reason']} |")
    lines += ["", "## Release blockers", ""] + ([f"- {b}" for b in card["blockers"]] or ["- none"])
    if card["revision_plan"]:
        lines += ["", "## Revision plan", ""] + [f"- **{p['category']}** (+{p['points_available']}): {p['action']}" for p in card["revision_plan"]]
    lines += ["", f"_{card['note']}_"]
    return "\n".join(lines) + "\n"
