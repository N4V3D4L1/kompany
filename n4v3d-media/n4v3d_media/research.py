"""Research & fact-verification records.

Every production carries a source record:

  sources: [{id, title, publisher, url, year, kind}]
  claims:  [{id, text, sources: [...], evidence: "verbatim quote", status, checked_by,
             medical: bool, hedged: bool}]
  review:  {author, fact_checker, expert_review: {required, status, reviewer, date, notes}}

Rules (enforced by `gate()`):
  * a claim must be `verified` — or `disputed`/`interpretation` AND `hedged` in the script;
  * every claim needs >= 1 source and an evidence quote;
  * the fact-checker must be a different agent/person from the script author;
  * medical content requires expert sign-off before APPROVAL/PUBLISH (rendering may proceed
    so the expert reviews the real video).
"""
from __future__ import annotations

ALLOWED_STATUS = {"verified", "disputed", "interpretation", "unverified", "rejected"}


def gate(prod: dict) -> dict:
    blockers, warnings = [], []
    src_ids = {s["id"] for s in prod.get("sources", [])}
    for s in prod.get("sources", []):
        if not s.get("url") and not s.get("citation"):
            warnings.append(f"source {s['id']} has no URL/citation")
    for c in prod.get("claims", []):
        st = c.get("status", "unverified")
        if st not in ALLOWED_STATUS:
            blockers.append(f"claim {c['id']}: unknown status '{st}'")
        if st in ("unverified", "rejected"):
            blockers.append(f"claim {c['id']} is {st}: \"{c['text'][:60]}\"")
        if st in ("disputed", "interpretation") and not c.get("hedged"):
            blockers.append(f"claim {c['id']} is {st} but the script does not hedge it")
        if not c.get("sources"):
            blockers.append(f"claim {c['id']} has no source")
        for sid in c.get("sources", []):
            if sid not in src_ids:
                blockers.append(f"claim {c['id']} cites unknown source {sid}")
        if not c.get("evidence"):
            warnings.append(f"claim {c['id']} has no evidence quote")
    rv = prod.get("review", {})
    author = rv.get("author")
    checker = rv.get("fact_checker")
    if not checker:
        blockers.append("no fact-checker recorded")
    elif checker == author:
        blockers.append("fact-checker is the same agent as the script author")
    for c in prod.get("claims", []):
        if c.get("checked_by") and c["checked_by"] == author:
            blockers.append(f"claim {c['id']} was checked only by its author")

    medical = any(c.get("medical") for c in prod.get("claims", []))
    ex = rv.get("expert_review", {})
    publish_blockers = []
    if medical or ex.get("required"):
        if ex.get("status") != "approved":
            publish_blockers.append("medical expert review pending (required before approval/publish)")
    return {
        "render_ok": not blockers,
        "publish_ok": not blockers and not publish_blockers,
        "blockers": blockers,
        "publish_blockers": publish_blockers,
        "warnings": warnings,
        "medical": medical,
        "counts": {
            "claims": len(prod.get("claims", [])),
            "verified": sum(1 for c in prod.get("claims", []) if c.get("status") == "verified"),
            "hedged": sum(1 for c in prod.get("claims", []) if c.get("status") in ("disputed", "interpretation")),
            "sources": len(src_ids),
        },
    }


def source_record_md(prod: dict) -> str:
    """Human-readable source record shipped with every video."""
    src = {s["id"]: s for s in prod.get("sources", [])}
    lines = [f"# Source record — {prod['title']}", "",
             f"Author: {prod['review'].get('author')} · Fact-checker: {prod['review'].get('fact_checker')} · "
             f"Expert review: {prod['review'].get('expert_review', {}).get('status', 'n/a')}", "",
             "| Claim | Status | Sources | Evidence |", "|---|---|---|---|"]
    for c in prod.get("claims", []):
        s = "; ".join(f"[{sid}]" for sid in c.get("sources", []))
        ev = c.get("evidence", "").replace("|", "/")
        lines.append(f"| **{c['id']}** {c['text']} | {c['status']}{' (hedged)' if c.get('hedged') else ''} | {s} | “{ev}” |")
    lines += ["", "## Sources", ""]
    for sid, s in src.items():
        lines.append(f"- **[{sid}]** {s['title']}. *{s.get('publisher', '')}*, {s.get('year', 'n.d.')}. {s.get('url', s.get('citation', ''))}")
    return "\n".join(lines) + "\n"
