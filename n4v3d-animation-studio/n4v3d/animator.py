"""Frame renderer: evaluates the timeline at time t and composites a frame."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from . import config
from .anim import ease
from .assets.backgrounds import BACKGROUNDS
from .assets.characters import CHARACTERS
from .assets.overlays import OVERLAYS
from .assets.props import PROPS, SnoozeOMatic
from .timeline import Timeline

W, H = config.WIDTH, config.HEIGHT
SCREEN_SPACE = {"title", "endcard", "flash"}
SHADOW_W = {"nuggo": 170, "brickley": 150, "box": 175, "clock": 70, "mug": 40}


def _blink(t, phase):
    period = 3.3 + phase
    x = (t + phase * 7) % period
    if x < 0.14:
        return 1.0 - abs(x / 0.07 - 1.0)
    return 0.0


def _punch_curve(u):
    if u < 0.22:
        return ease("out", u / 0.22)
    if u < 0.55:
        return 1.0
    return 1.0 - ease("in_out", (u - 0.55) / 0.45)


class Renderer:
    def __init__(self, tl: Timeline, bg_cache_dir: Path):
        self.tl = tl
        self.bg = {}
        bg_cache_dir.mkdir(parents=True, exist_ok=True)
        for sc in tl.scenes:
            name = sc["background"]
            if name not in self.bg:
                f = bg_cache_dir / f"{name}.png"
                if not f.exists():
                    BACKGROUNDS[name]().save(f)
                self.bg[name] = Image.open(f).convert("RGBA")
        self.phase = {eid: (i * 0.37) % 1.0 for i, eid in enumerate(tl.entities)}

    # ------------------------------------------------------------------
    def scene_at(self, t):
        for sc in self.tl.scenes:
            if sc["t0"] <= t < sc["t1"]:
                return sc
        return self.tl.scenes[-1]

    def entity_state(self, ent, t):
        x, y = ent.val("pos", t)
        st = {
            "x": x, "y": y, "ground": y, "rot": ent.val("rot", t, 0.0), "scale": ent.val("scale", t, 1.0),
            "flip": ent.val("flip", t, False), "visible": ent.val("visible", t, True), "z": ent.val("z", t, 1),
            "sx": 1.0, "sy": 1.0, "t": t,
        }
        for k, tr in ent.tracks.items():
            if k not in st:
                st[k] = tr.value(t)
        ph = self.phase.get(ent.id, 0.0)
        if ent.kind == "character":
            cls = CHARACTERS[ent.asset]
            a = st["arms"]
            st["arms"] = {"L": (a[0], a[1]), "R": (a[2], a[3])}
            st["blink"] = _blink(t, ph)
            clip = self.tl.clip_at(ent.id, t)
            m = 0.0
            if clip is not None and clip.env is not None and len(clip.env):
                i = min(len(clip.env) - 1, int((t - clip.t0) * config.FPS))
                m = float(clip.env[i])
            st["mouth"] = m
            # idle breathing + talk bob
            st["sy"] *= 1.0 + 0.014 * math.sin(2 * math.pi * t / 2.3 + ph * 6)
            st["y"] -= 7 * m
        for fx in ent.fx:
            if not fx.active(t):
                continue
            u = fx.u(t)
            p = fx.params
            if fx.name == "hop":
                st["y"] -= p.get("height", 120) * math.sin(math.pi * u)
            elif fx.name == "squash":
                a = p.get("amount", 0.25) * math.exp(-4 * u) * math.cos(6 * math.pi * u)
                st["sy"] *= 1 - a
                st["sx"] *= 1 + 0.7 * a
            elif fx.name == "shake":
                amp = p.get("amp", 12) * (1 - u)
                st["x"] += amp * math.sin(t * 71)
                st["y"] += amp * 0.4 * math.cos(t * 53)
            elif fx.name == "spin":
                st["rot"] += 360 * p.get("turns", 1) * ease("out", u)
                st["rot_center"] = True
            elif fx.name == "flail" and ent.kind == "character":
                k = p.get("speed", 24)
                st["arms"] = {"L": (-120 + 45 * math.sin(t * k), -90 + 70 * math.cos(t * k * 0.9)),
                              "R": (120 + 45 * math.sin(t * k + 2), -90 + 70 * math.cos(t * k * 0.9 + 1))}
            elif fx.name == "punch":
                st["punch"] = 0.08 + (p.get("reach", 0.8) - 0.08) * _punch_curve(u)
                st["angle"] = p.get("angle", st.get("angle", -90))
        return st

    # ------------------------------------------------------------------
    def _sprite(self, ent, st):
        if ent.kind == "character":
            img, (px, py) = CHARACTERS[ent.asset].render(st, st["scale"])
        else:
            img, (px, py) = PROPS[ent.asset].render(st, st["scale"])
        if abs(st["sx"] - 1) > 1e-3 or abs(st["sy"] - 1) > 1e-3:
            nw, nh = max(1, int(img.width * st["sx"])), max(1, int(img.height * st["sy"]))
            img = img.resize((nw, nh), Image.BILINEAR)
            px, py = px * st["sx"], py * st["sy"]
        if st["flip"]:
            img = ImageOps.mirror(img)
            px = img.width - px
        if abs(st["rot"]) > 0.05:
            cx, cy = img.width / 2, img.height / 2
            r = math.radians(st["rot"])
            vx, vy = px - cx, py - cy
            img = img.rotate(-st["rot"], resample=Image.BICUBIC, expand=True)
            px = img.width / 2 + vx * math.cos(r) - vy * math.sin(r)
            py = img.height / 2 + vx * math.sin(r) + vy * math.cos(r)
        return img, px, py

    def frame(self, t: float) -> Image.Image:
        sc = self.scene_at(t)
        frame = self.bg[sc["background"]].copy()
        states = []
        for ent in self.tl.entities.values():
            st = self.entity_state(ent, t)
            if st["visible"]:
                states.append((st["z"], ent, st))
        states.sort(key=lambda s: s[0])

        # contact shadows
        sh = ImageDraw.Draw(frame, "RGBA")
        for _, ent, st in states:
            if st.get("no_shadow") or st["ground"] < 1300 or st["ground"] > 1900:
                continue
            lift = max(0.0, st["ground"] - st["y"])
            w = SHADOW_W.get(ent.asset, 120) * st["scale"] * max(0.4, 1 - lift / 500)
            gx = st["x"]
            sh.ellipse([gx - w, st["ground"] - w * 0.16, gx + w, st["ground"] + w * 0.16], fill=(70, 35, 30, 70))

        for _, ent, st in states:
            img, px, py = self._sprite(ent, st)
            x, y = st["x"], st["y"]
            if st.get("rot_center") and ent.kind == "character":
                # spin around the body's centre instead of the feet
                h2 = CHARACTERS[ent.asset].height * st["scale"] / 2
                r = math.radians(st["rot"])
                x -= h2 * math.sin(r)
                y -= h2 - h2 * math.cos(r)
            frame.alpha_composite(img, (int(round(x - px)), int(round(y - py))))

        world = [o for o in self.tl.overlays if o[0] not in SCREEN_SPACE and o[1] <= t < o[2]]
        for kind, t0, t1, prm in world:
            OVERLAYS[kind](frame, prm, (t - t0) / (t1 - t0), t)

        frame = self._camera(frame, t)

        for kind, t0, t1, prm in self.tl.overlays:
            if kind in SCREEN_SPACE and t0 <= t < t1:
                OVERLAYS[kind](frame, prm, (t - t0) / (t1 - t0), t)
        return frame.convert("RGB")

    def _camera(self, frame, t):
        cam = self.tl.camera
        z = cam.val("zoom", t, 1.0)
        cx, cy = cam.val("center", t)
        dx = dy = 0.0
        for fx in cam.fx:
            if fx.name == "shake" and fx.active(t):
                amp = fx.params.get("amp", 18) * (1 - fx.u(t))
                dx += amp * math.sin(t * 83)
                dy += amp * math.cos(t * 61)
        if abs(z - 1) < 1e-3 and abs(dx) < 0.5 and abs(dy) < 0.5:
            return frame
        z = max(z, 1.0)
        # a shake needs a little headroom so no borders show
        if abs(dx) + abs(dy) > 0:
            z = max(z, 1.0 + (abs(dx) + abs(dy)) * 2.2 / W)
        cw, ch = W / z, H / z
        x0 = min(max(cx + dx - cw / 2, 0), W - cw)
        y0 = min(max(cy + dy - ch / 2, 0), H - ch)
        return frame.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))
