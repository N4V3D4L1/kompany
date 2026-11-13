"""Storytelling engine: narrative structures + script validation.

Short-form (<= 60 s) follows six stages:
    hook -> question -> discovery -> surprise -> payoff -> final
Long-form (5-12 min) follows six chapters:
    mystery -> background -> discovery -> complication -> implications -> conclusion

`check_story()` enforces the structure and the house rules (no generic
openers, a fast hook, a sane speaking rate, every factual sentence tied to a
verified claim) and returns a list of findings. Errors block production.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

SHORT_STAGES = ["hook", "question", "discovery", "surprise", "payoff", "final"]
LONG_CHAPTERS = ["mystery", "background", "discovery", "complication", "implications", "conclusion"]

BANNED_OPENERS = [
    r"^welcome back", r"^today we('| a)re going to", r"^did you know", r"^hey guys", r"^in this video",
    r"^what's up", r"^hello everyone",
]
CLICKBAIT = [r"you won'?t believe", r"shocking", r"doctors hate", r"\bsecret\b", r"mind[- ]?blowing", r"!!+"]

# Comfortable narration rates (words per minute) per persona
WPM_RANGE = {"health": (130, 175), "history": (135, 180), "general": (145, 195)}


@dataclass
class Finding:
    level: str      # error | warning | info
    rule: str
    detail: str

    def __str__(self):
        return f"[{self.level.upper()}] {self.rule}: {self.detail}"


def words(s: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", s))


def check_story(prod: dict, durations: dict | None = None) -> list[Finding]:
    """Validate a production's narrative. `durations` maps segment index -> seconds (after TTS)."""
    out: list[Finding] = []
    fmt = prod.get("format", "short")
    segs = prod.get("segments", [])
    order = SHORT_STAGES if fmt == "short" else LONG_CHAPTERS
    present = [s.get("stage") for s in segs]
    for st in order:
        if st not in present:
            out.append(Finding("error", "structure", f"missing stage '{st}'"))
    # stages must appear in narrative order (a stage may span several segments)
    idx = [order.index(s) for s in present if s in order]
    if idx != sorted(idx):
        out.append(Finding("error", "structure", f"stages out of order: {present}"))

    if segs:
        hook = segs[0]["text"].strip()
        low = hook.lower()
        for pat in BANNED_OPENERS:
            if re.search(pat, low):
                out.append(Finding("error", "hook", f"generic opener '{hook[:40]}…'"))
        if fmt == "short" and words(hook) > 18:
            out.append(Finding("warning", "hook", f"hook is {words(hook)} words; aim for <= 18 (≈3 s)"))
        if durations and fmt == "short" and durations.get(0, 0) > 4.5:
            out.append(Finding("warning", "hook", f"hook narration lasts {durations[0]:.1f}s; aim for <= 4 s"))

    claim_ids = {c["id"] for c in prod.get("claims", [])}
    for i, s in enumerate(segs):
        for cid in s.get("claims", []):
            if cid not in claim_ids:
                out.append(Finding("error", "claims", f"segment {i} cites unknown claim {cid}"))
        if s.get("factual", True) and not s.get("claims") and s.get("stage") not in ("question",):
            out.append(Finding("warning", "claims", f"segment {i} ({s.get('stage')}) states facts but cites no claim"))

    total_words = sum(words(s["text"]) for s in segs)
    if durations:
        total = sum(durations.values())
        wpm = total_words / (total / 60) if total else 0
        lo, hi = WPM_RANGE.get(prod.get("persona", "general"), (130, 190))
        lvl = "info" if lo <= wpm <= hi else "warning"
        out.append(Finding(lvl, "pace", f"{wpm:.0f} words/min (target {lo}-{hi})"))
        if fmt == "short" and total > prod.get("target_duration", 60) + 0.5:
            out.append(Finding("error", "length", f"narration {total:.1f}s exceeds target {prod.get('target_duration', 60)}s"))
    return out


def check_titles(titles: list[str], keywords: list[str]) -> list[dict]:
    """Score candidate titles on accuracy-safety, clarity, curiosity and relevance (0-10 each)."""
    res = []
    for t in titles:
        low = t.lower()
        clickbait = any(re.search(p, low) for p in CLICKBAIT)
        clarity = 10 - max(0, len(t) - 60) // 4 - (3 if len(t) < 20 else 0)
        curiosity = 6 + (2 if "?" in t else 0) + (2 if re.search(r"\b(how|why|what)\b", low) else 0)
        relevance = 4 + 3 * sum(1 for k in keywords if k.lower() in low)
        safety = 0 if clickbait else 10
        sc = {"accuracy_safety": safety, "clarity": max(0, min(10, clarity)),
              "curiosity": min(10, curiosity), "relevance": min(10, relevance)}
        res.append({"title": t, "scores": sc, "total": sum(sc.values()), "clickbait": clickbait})
    res.sort(key=lambda r: (not r["clickbait"], r["total"]), reverse=True)
    return res
