"""Episode script format (JSON) + validation.

An episode is a list of scenes; each scene is a list of *beats* executed in
order on a running clock:

  {"line": "nuggo", "text": "...", "emotion": "excited", "pose": "up"}   dialogue (waits for audio)
  {"do": "move", "who": "nuggo", "to": [x, y], "dur": 0.5, "wait": true} action (non-blocking by default)
  {"sfx": "bonk", "delay": 0.1}                                          sound cue
  {"overlay": "burst", "text": "BONK!", "at": [x, y], "dur": 0.8}        comic overlay
  {"pause": 0.4}                                                         hold

Every beat accepts "delay" (seconds after the clock) and "wait" (advance clock).
See docs/EPISODE_FORMAT.md for the full action vocabulary.
"""
from __future__ import annotations

import json
from pathlib import Path

from .assets.characters import CHARACTERS
from .assets.props import PROPS
from .assets.backgrounds import BACKGROUNDS
from .assets.overlays import OVERLAYS
from . import sfx as sfxlib

ACTIONS = {
    "move", "tilt", "scale", "face", "show", "hide", "set", "tween", "emotion", "pose",
    "look", "hold", "hop", "squash", "shake", "flail", "spin", "punch", "ring", "press",
    "zoom", "reset",
}


class EpisodeError(ValueError):
    pass


def load(path) -> dict:
    path = Path(path)
    if path.is_dir():
        path = path / "episode.json"
    ep = json.loads(path.read_text())
    ep["_dir"] = str(path.parent)
    validate(ep)
    return ep


def validate(ep: dict) -> list[str]:
    """Raise EpisodeError on fatal problems; return a list of warnings."""
    errs, warns = [], []
    for k in ("id", "title", "entities", "scenes"):
        if k not in ep:
            errs.append(f"missing top-level key '{k}'")
    ents = ep.get("entities", {})
    for eid, e in ents.items():
        a = e.get("asset", eid)
        if a not in CHARACTERS and a not in PROPS:
            errs.append(f"entity '{eid}': unknown asset '{a}'")
    cast = ep.get("cast", {})
    seen_ids = set()
    for si, sc in enumerate(ep.get("scenes", [])):
        where = f"scene {sc.get('id', si)}"
        bg = sc.get("background")
        if bg and bg not in BACKGROUNDS:
            errs.append(f"{where}: unknown background '{bg}'")
        for bi, b in enumerate(sc.get("beats", [])):
            w = f"{where} beat {bi}"
            kinds = [k for k in ("line", "do", "sfx", "overlay", "pause") if k in b]
            if "do" in kinds:
                kinds = ["do"]  # an action may carry an attached "sfx"
            if len(kinds) != 1:
                errs.append(f"{w}: beat must have exactly one of line/do/sfx/overlay/pause, got {kinds}")
                continue
            kind = kinds[0]
            if kind == "line":
                if b["line"] not in ents:
                    errs.append(f"{w}: speaker '{b['line']}' is not an entity")
                if b["line"] not in cast:
                    errs.append(f"{w}: speaker '{b['line']}' has no cast/voice entry")
                if not b.get("text", "").strip():
                    errs.append(f"{w}: empty line text")
                if b.get("id"):
                    if b["id"] in seen_ids:
                        errs.append(f"{w}: duplicate line id {b['id']}")
                    seen_ids.add(b["id"])
                if len(b.get("text", "")) > 90:
                    warns.append(f"{w}: long line ({len(b['text'])} chars) — consider splitting for Shorts pacing")
            elif kind == "do":
                if b["do"] not in ACTIONS:
                    errs.append(f"{w}: unknown action '{b['do']}'")
                whos = b.get("who")
                whos = whos if isinstance(whos, list) else [whos]
                for who in whos:
                    if who != "camera" and who not in ents:
                        errs.append(f"{w}: unknown target '{who}'")
                if "sfx" in b and b["sfx"] not in sfxlib.LIBRARY:
                    errs.append(f"{w}: unknown sfx '{b['sfx']}'")
            elif kind == "sfx":
                if b["sfx"] not in sfxlib.LIBRARY:
                    errs.append(f"{w}: unknown sfx '{b['sfx']}'")
            elif kind == "overlay":
                if b["overlay"] not in OVERLAYS:
                    errs.append(f"{w}: unknown overlay '{b['overlay']}'")
    if errs:
        raise EpisodeError("Episode validation failed:\n  - " + "\n  - ".join(errs))
    return warns
