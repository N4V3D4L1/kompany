"""AI-assisted episode drafting.

`draft_episode(premise)` asks Claude to write a new episode in the studio's
JSON episode format, using the character bible and the pilot as a style
reference, then validates the result with the same validator the renderer uses.

* With the `anthropic` SDK installed and credentials available
  (`ANTHROPIC_API_KEY` or `ant auth login`), the draft is generated directly.
* Otherwise the full prompt is written to a file so it can be pasted into any
  Claude interface, and the reply saved as episode.json by hand.

A human always reviews the draft (and renders a --preview) before production.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .. import config
from ..episode import ACTIONS, EpisodeError, validate
from ..assets.characters import CHARACTERS
from ..assets.overlays import OVERLAYS
from ..sfx import LIBRARY as SFX

MODEL = "claude-opus-5-5"


def build_prompt(premise: str, episode_id: str) -> str:
    bible = (config.ROOT / "docs" / "CHARACTERS.md").read_text()
    fmt = (config.ROOT / "docs" / "EPISODE_FORMAT.md").read_text()
    pilot = (config.EPISODES / "ep001_snooze_o_matic" / "episode.json").read_text()
    poses = {k: sorted(v.POSES) for k, v in CHARACTERS.items()}
    return f"""You are a staff writer and animation director at N4V3D Animation Studio, which makes
original 45-second 2D comedy cartoons for YouTube Shorts (vertical 1080x1920).

Write a NEW episode with id "{episode_id}" from this premise:
<premise>
{premise}
</premise>

Requirements:
- Original jokes and dialogue; a clear setup -> escalation -> button/punchline structure.
- 40-50 seconds when performed: about 10-15 short lines (under 60 characters each).
- Keep the characters in voice (see the character bible). Brickley is always deadpan.
- Use ONLY these assets/actions:
  actions: {sorted(ACTIONS)}
  poses: {json.dumps(poses)}
  sfx: {sorted(SFX)}
  overlays: {sorted(OVERLAYS)}
  props: box (Snooze-O-Matic), clock — or no props at all.
- Positions: ground y = 1640; keep characters between x = 180 and x = 920.
- Output the complete episode as a single JSON object and nothing else.

<character_bible>
{bible}
</character_bible>

<episode_format>
{fmt}
</episode_format>

<reference_episode>
{pilot}
</reference_episode>
"""


def _extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise EpisodeError("no JSON object in model reply")
    return json.loads(m.group(0))


def draft_episode(premise: str, episode_id: str = "ep_draft", out: str | None = None) -> str:
    out_dir = Path(out) if out else config.EPISODES / f"{episode_id}_draft"
    out_dir.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(premise, episode_id)
    try:
        import anthropic
    except ImportError:
        anthropic = None
    if anthropic is None:
        p = out_dir / "PROMPT.md"
        p.write_text(prompt)
        return (f"anthropic SDK not installed — prompt written to {p}.\n"
                f"Paste it into Claude and save the JSON reply as {out_dir / 'episode.json'},\n"
                f"or `pip install anthropic` and re-run.")

    client = anthropic.Anthropic()
    try:
        with client.beta.messages.stream(
            model=MODEL,
            max_tokens=32000,
            output_config={"effort": "high"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",  # re-route automatically if the request is declined
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            msg = stream.get_final_message()
    except anthropic.AuthenticationError:
        p = out_dir / "PROMPT.md"
        p.write_text(prompt)
        return f"No Anthropic credentials found — prompt written to {p} for manual use."
    if msg.stop_reason == "refusal":
        return "The model declined this premise; try rephrasing it."
    text = "".join(b.text for b in msg.content if b.type == "text")
    ep = _extract_json(text)
    ep["id"] = episode_id
    ep["_dir"] = str(out_dir)
    warnings = validate(ep)  # raises EpisodeError with details if invalid
    ep.pop("_dir")
    (out_dir / "episode.json").write_text(json.dumps(ep, indent=2))
    lines = sum(1 for sc in ep["scenes"] for b in sc["beats"] if "line" in b)
    msg_out = f"Draft written to {out_dir / 'episode.json'} ({len(ep['scenes'])} scenes, {lines} lines)."
    if warnings:
        msg_out += "\nWarnings:\n  " + "\n  ".join(warnings)
    return msg_out + f"\nReview it, then: python -m n4v3d render {out_dir} --preview"
