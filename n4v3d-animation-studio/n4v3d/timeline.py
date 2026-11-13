"""Compile an episode script into an absolute-time timeline.

Pipeline: dialogue is synthesised first, so scene timing is driven by real
audio lengths; the gaps are then auto-fitted to the episode's target duration.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import config, sfx as sfxlib, voice
from .anim import FX, Track
from .assets.characters import CHARACTERS
from .assets.props import PROPS

DEFAULT_DUR = {
    "move": 0.5, "tilt": 0.3, "scale": 0.3, "pose": 0.22, "look": 0.12, "hop": 0.45,
    "squash": 0.5, "shake": 0.5, "flail": 1.0, "spin": 0.6, "punch": 0.6, "ring": 1.2,
    "press": 0.25, "zoom": 0.4, "tween": 0.3, "reset": 0.3,
}
LINE_GAP = 0.22


def _pose_vec(cls, name):
    p = cls.POSES[name]
    return (*p["L"], *p["R"])


@dataclass
class Entity:
    id: str
    kind: str                      # character | prop | camera
    asset: str
    tracks: dict = field(default_factory=dict)
    fx: list = field(default_factory=list)

    def tr(self, name, default=None) -> Track:
        if name not in self.tracks:
            self.tracks[name] = Track(default)
        return self.tracks[name]

    def val(self, name, t, default=None):
        tr = self.tracks.get(name)
        return tr.value(t) if tr else default


@dataclass
class Clip:
    id: str
    who: str
    text: str
    t0: float
    dur: float
    wav: str
    provider: str
    env: np.ndarray = None

    @property
    def t1(self):
        return self.t0 + self.dur


@dataclass
class Timeline:
    episode: dict
    entities: dict
    camera: Entity
    clips: list
    sfx: list                      # (t, name, gain, pan)
    overlays: list                 # (kind, t0, t1, params)
    scenes: list                   # dicts with id, name, t0, t1, background
    duration: float
    fit_report: dict

    def clip_at(self, who, t):
        for c in self.clips:
            if c.who == who and c.t0 <= t < c.t1:
                return c
        return None


def _make_entities(ep):
    ents = {}
    for eid, e in ep["entities"].items():
        asset = e.get("asset", eid)
        kind = "character" if asset in CHARACTERS else "prop"
        ent = Entity(eid, kind, asset)
        ent.tr("pos", tuple(e.get("pos", (540, 1560))))
        ent.tr("rot", float(e.get("rot", 0.0)))
        ent.tr("scale", float(e.get("scale", 1.0)))
        ent.tr("flip", bool(e.get("flip", False)))
        ent.tr("visible", bool(e.get("visible", True)))
        ent.tr("z", float(e.get("z", 1)))
        if kind == "character":
            cls = CHARACTERS[asset]
            ent.tr("emotion", e.get("emotion", "neutral"))
            ent.tr("arms", _pose_vec(cls, e.get("pose", "rest")))
            ent.tr("look", tuple(e.get("look", (0.0, 0.0))))
            ent.tr("hold", e.get("hold"))
        else:
            for k, v in e.get("state", {}).items():
                ent.tr(k, tuple(v) if isinstance(v, list) else v)
        ents[eid] = ent
    cam = Entity("camera", "camera", "camera")
    cam.tr("zoom", 1.0)
    cam.tr("center", (config.WIDTH / 2, config.HEIGHT / 2))
    return ents, cam


def _aim(ent: Entity, b: dict, t: float, ents: dict):
    """Auto-aim the Snooze-O-Matic glove: compute angle + reach to hit a named target."""
    from .assets.props import SnoozeOMatic as Box
    bx, by = ent.val("pos", t)
    sc = ent.val("scale", t, 1.0)
    mx, my = bx + Box.MOUNT[0] * sc, by + Box.MOUNT[1] * sc
    tgt = b["target"]
    if tgt == "self_button":
        tx, ty = bx - 98 * sc, by - 175 * sc
    else:
        te = ents[tgt]
        px, py = te.val("pos", t)
        ts = te.val("scale", t, 1.0)
        if te.kind == "character":
            cls = CHARACTERS[te.asset]
            tx, ty = px, py + (cls.head_y + 60) * ts
            # hit the side of the face that points at the box
            tx += (1 if mx > px else -1) * 60 * ts
        else:
            tx, ty = px, py - 88 * ts
    ox, oy = b.get("aim_offset", (0, 0))
    tx, ty = tx + ox, ty + oy
    dist = math.hypot(tx - mx, ty - my) / sc
    b = dict(b)
    b["angle"] = math.degrees(math.atan2(ty - my, tx - mx))
    b["reach"] = max(0.1, (dist - 46) / Box.REACH) + float(b.get("overshoot", 0.0))
    return b


def _apply(ent: Entity, b: dict, t: float, dur: float, ents: dict | None = None):
    act = b["do"]
    if act == "punch" and "target" in b:
        b = _aim(ent, b, t, ents)
    ease_name = b.get("ease")
    if act == "move":
        if "to" in b:
            target = tuple(b["to"])
        else:
            cur = ent.val("pos", t)
            dx, dy = b.get("by", (0, 0))
            target = (cur[0] + dx, cur[1] + dy)
        ent.tr("pos").tween(t, dur, target, ease_name or "in_out")
    elif act == "tilt":
        ent.tr("rot").tween(t, dur, float(b.get("angle", 0)), ease_name or "out_back")
    elif act == "scale":
        ent.tr("scale").tween(t, dur, float(b["value"]), ease_name or "out_back")
    elif act == "face":
        ent.tr("flip").set(t, b.get("dir", "right") == "left")
    elif act in ("show", "hide"):
        ent.tr("visible").set(t, act == "show")
    elif act == "set":
        v = b["value"]
        ent.tr(b["prop"]).set(t, tuple(v) if isinstance(v, list) else v)
    elif act == "tween":
        v = b["value"]
        ent.tr(b["prop"]).tween(t, dur, tuple(v) if isinstance(v, list) else v, ease_name or "in_out")
    elif act == "emotion":
        ent.tr("emotion").set(t, b["value"])
    elif act == "pose":
        ent.tr("arms").tween(t, dur, _pose_vec(CHARACTERS[ent.asset], b["value"]), ease_name or "out_back")
    elif act == "look":
        ent.tr("look").tween(t, dur, tuple(b.get("at", (0, 0))), ease_name or "out")
    elif act == "hold":
        ent.tr("hold").set(t, b.get("value"))
    elif act == "ring":
        ent.tr("ringing").set(t, True)
        ent.tr("ringing").set(t + dur, False)
    elif act == "press":
        ent.tr("press").tween(t, dur / 2, 1.0, "out")
        ent.tr("press").tween(t + dur / 2, dur / 2, 0.0, "in_out")
    elif act == "zoom":  # camera
        ent.tr("zoom").tween(t, dur, float(b.get("scale", 1.0)), ease_name or "out")
        if "center" in b:
            ent.tr("center").tween(t, dur, tuple(b["center"]), ease_name or "out")
    elif act == "reset":
        ent.tr("zoom").tween(t, dur, 1.0, ease_name or "in_out")
        ent.tr("center").tween(t, dur, (config.WIDTH / 2, config.HEIGHT / 2), ease_name or "in_out")
    else:  # procedural FX: hop, squash, shake, flail, spin, punch
        params = {k: v for k, v in b.items() if k not in ("do", "who", "dur", "delay", "wait", "sfx", "sfx_delay", "target", "aim_offset", "overshoot")}
        ent.fx.append(FX(act, t, t + dur, params))


def build(ep: dict, work_dir: Path, gap_extra: float = 0.0, tail_extra: float = 0.0, verbose=False) -> Timeline:
    ents, cam = _make_entities(ep)
    ep_dir = Path(ep["_dir"])
    cache = work_dir / "voice_cache"
    recorded = ep_dir / "voice"
    clips, cues, overlays, scenes = [], [], [], []
    gap = max(0.06, LINE_GAP + gap_extra)
    t = 0.0
    line_no = 0
    for si, sc in enumerate(ep["scenes"]):
        s0 = t
        for eid, st in sc.get("setup", {}).items():
            target = cam if eid == "camera" else ents[eid]
            for prop, v in st.items():
                if prop == "pose":
                    target.tr("arms").set(t, _pose_vec(CHARACTERS[target.asset], v))
                else:
                    target.tr(prop).set(t, tuple(v) if isinstance(v, list) else v)
        for b in sc.get("beats", []):
            start = t + float(b.get("delay", 0.0))
            if "line" in b:
                line_no += 1
                lid = b.get("id") or f"L{line_no:02d}"
                who = b["line"]
                wav, prov = voice.synth_line(lid, b.get("tts", b["text"]), ep["cast"][who], cache, recorded)
                samples = voice.read_wav(wav)
                dur = len(samples) / config.SAMPLE_RATE
                ent = ents[who]
                if "emotion" in b:
                    ent.tr("emotion").set(start, b["emotion"])
                if "pose" in b:
                    ent.tr("arms").tween(start, 0.22, _pose_vec(CHARACTERS[ent.asset], b["pose"]), "out_back")
                if "look" in b:
                    ent.tr("look").tween(start, 0.12, tuple(b["look"]), "out")
                clips.append(Clip(lid, who, b["text"], start, dur, str(wav), prov, voice.envelope(samples)))
                if b.get("wait", True):
                    t = start + dur + gap + float(b.get("hold", 0.0))
            elif "pause" in b:
                t = start + float(b["pause"])
            elif "overlay" in b:
                dur = float(b.get("dur", 0.8))
                prm = {k: v for k, v in b.items() if k not in ("overlay", "dur", "delay", "wait")}
                overlays.append((b["overlay"], start, start + dur, prm))
                if b.get("wait", False):
                    t = start + dur
            elif "do" in b:
                dur = float(b.get("dur", DEFAULT_DUR.get(b["do"], 0.0)))
                whos = b.get("who")
                for who in (whos if isinstance(whos, list) else [whos]):
                    _apply(cam if who == "camera" else ents[who], b, start, dur, ents)
                if "sfx" in b:
                    cues.append((start + float(b.get("sfx_delay", 0.0)), b["sfx"], float(b.get("gain", 0.8)), 0.0))
                if b.get("wait", False):
                    t = start + dur
            elif "sfx" in b:
                cues.append((start, b["sfx"], float(b.get("gain", 0.8)), float(b.get("pan", 0.0))))
                if b.get("wait", False):
                    t = start + len(sfxlib.get(b["sfx"])) / config.SAMPLE_RATE
        t += float(sc.get("tail", 0.35)) + tail_extra
        scenes.append({"id": sc.get("id", f"s{si+1}"), "name": sc.get("name", ""), "t0": s0, "t1": t,
                       "background": sc.get("background", ep.get("background", "kitchen_day"))})
    # anything (overlays/clips) running past the last scene extends the duration
    end = max([t] + [c.t1 for c in clips] + [o[2] for o in overlays])
    scenes[-1]["t1"] = end
    return Timeline(ep, ents, cam, clips, cues, overlays, scenes, end, {})


def build_fitted(ep: dict, work_dir: Path) -> Timeline:
    """Build, then adjust line gaps / scene tails so the cut lands on target_duration."""
    target = float(ep.get("target_duration", 45.0))
    natural = build(ep, work_dir)
    n_lines = max(1, len(natural.clips))
    n_scenes = max(1, len(ep["scenes"]))
    diff = target - natural.duration
    if diff >= 0:
        gap_extra = min(0.25, 0.5 * diff / n_lines)
    else:
        gap_extra = max(-(LINE_GAP - 0.06), diff / n_lines)
    tl = build(ep, work_dir, gap_extra=gap_extra)
    rem = target - tl.duration
    tail_extra = rem / n_scenes if rem > 0 else max(-0.3, rem / n_scenes)
    tl = build(ep, work_dir, gap_extra=gap_extra, tail_extra=tail_extra)
    tl.fit_report = {
        "target": target, "natural": round(natural.duration, 3), "final": round(tl.duration, 3),
        "gap_extra": round(gap_extra, 3), "tail_extra": round(tail_extra, 3),
    }
    return tl
