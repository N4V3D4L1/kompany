"""Production engine: production.json -> verified, narrated, animated, captioned, QC'd MP4.

Stages (each callable on its own, used by the orchestrator):
    load -> fact_gate -> story_check -> narrate -> plan -> captions -> mix -> render -> mux -> qc -> package
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from . import RELEASES, VAR, narration, research, soundscape, story
from .visual import history, science
from n4v3d import audio as studio_audio
from n4v3d import config as studio_config
from n4v3d import qc as studio_qc
from n4v3d import sfx as sfxlib
from n4v3d import voice as V
from n4v3d.anim import ease

W, H, FPS, SR = 1080, 1920, 30, 48000
SCENES = {**science.SCENES, **history.SCENES}
LEAD, GAP, TAIL, XFADE = 0.25, 0.32, 1.6, 0.35
CAPTION_BOTTOM = 1450      # caption block bottom edge (Shorts UI starts ~1500)


class ProductionError(RuntimeError):
    pass


def load(path) -> dict:
    path = Path(path)
    if path.is_dir():
        path = path / "production.json"
    prod = json.loads(path.read_text())
    prod["_dir"] = str(path.parent)
    for s in prod["segments"]:
        if s["scene"] not in SCENES:
            raise ProductionError(f"unknown scene '{s['scene']}'")
    return prod


@dataclass
class Plan:
    prod: dict
    windows: list          # (t0, t1) per segment (scene time windows)
    narr: list             # (t_start, samples, wav, provider) per segment
    duration: float
    cues: list = field(default_factory=list)  # (t0, t1, text) caption chunks
    sfx: list = field(default_factory=list)   # (t, name, gain)


def plan(prod: dict, work: Path) -> Plan:
    segs = narration.synth_segments(prod, work)
    # fit pauses so the cut lands safely inside the target (Shorts hard limit 60 s)
    n = len(segs)
    speech = sum(len(s[1]) / SR for s in segs)
    limit = float(prod.get("target_duration", 60)) - 0.35
    gap, tail = GAP, TAIL
    over = (speech + LEAD + 0.12 * (n - 1) + GAP * (n - 1) + TAIL) - limit
    if over > 0:
        cut_tail = min(over, TAIL - 1.0)
        tail -= cut_tail
        over -= cut_tail
        if over > 0:
            gap = max(0.1, GAP - over / max(1, n - 1))
    windows, narr = [], []
    t = 0.0
    for i, (wav, samples, provider) in enumerate(segs):
        d = len(samples) / SR
        start = t + (LEAD if i == 0 else 0.12)
        end = start + d + (tail if i == len(segs) - 1 else gap)
        windows.append((t, end))
        narr.append((start, samples, str(wav), provider))
        t = end
    pl = Plan(prod, windows, narr, t)
    for i, (w0, w1) in enumerate(windows):
        for (u, name, gain) in SCENES[prod["segments"][i]["scene"]].sfx:
            pl.sfx.append((w0 + u * (w1 - w0), name, gain))
    pl.cues = caption_cues(prod, narr)
    return pl


def chunk_words(text, max_words=5, max_chars=28):
    words, out, cur = text.split(), [], []
    for w in words:
        cand = " ".join(cur + [w])
        if cur and (len(cur) >= max_words or len(cand) > max_chars):
            out.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
        if w[-1] in ".?!" and len(cur) >= 2:
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def caption_cues(prod, narr):
    cues = []
    for seg, (start, samples, _, _) in zip(prod["segments"], narr):
        d = len(samples) / SR
        parts = chunk_words(seg["text"])
        total = sum(len(p) for p in parts) or 1
        t = start
        for p in parts:
            dd = d * len(p) / total
            cues.append((t, t + dd, p))
            t += dd
    return cues


def write_captions(pl: Plan, out_dir: Path):
    def ts(t):
        h, r = divmod(max(0.0, t), 3600)
        m, s = divmod(r, 60)
        return f"{int(h)}:{int(m):02d}:{s:05.2f}"

    def ts_srt(t):
        ms = int(round(max(0.0, t) * 1000))
        h, ms = divmod(ms, 3_600_000)
        m, ms = divmod(ms, 60_000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    accent = pl.prod.get("direction", {}).get("palette", {}).get("accent", "#FFFFFF").lstrip("#")
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Inter ExtraBold,70,&H00FFFFFF,&H00FFFFFF,&H00241008,&H78000000,0,0,0,0,100,100,0.5,0,1,5,3,2,90,150,{H - CAPTION_BOTTOM},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    for t0, t1, txt in pl.cues:
        ev.append(f"Dialogue: 0,{ts(t0)},{ts(t1)},Caption,,0,0,0,,{{\\fad(50,40)}}{txt}")
    ass = out_dir / "captions.ass"
    ass.write_text(hdr + "\n".join(ev) + "\n")
    srt = []
    for i, (seg, (start, samples, _, _)) in enumerate(zip(pl.prod["segments"], pl.narr), 1):
        srt.append(f"{i}\n{ts_srt(start)} --> {ts_srt(start + len(samples) / SR)}\n{seg['text']}\n")
    (out_dir / "captions.srt").write_text("\n".join(srt))
    return ass


def mix(pl: Plan, out: Path):
    n = int(np.ceil(pl.duration * SR))
    dlg = np.zeros(n, np.float32)
    for start, samples, _, _ in pl.narr:
        i = int(start * SR)
        dlg[i:i + len(samples)] += samples[: n - i]
    fx = np.zeros(n, np.float32)
    for t, name, gain in pl.sfx:
        s = sfxlib.get(name) * gain
        i = int(t * SR)
        if i < n:
            fx[i:i + len(s)] += s[: n - i]
    mcfg = pl.prod.get("music", {})
    bed = soundscape.pad_bed(pl.duration + 0.1, mcfg.get("style", "science_pad"))[:n]
    bed = np.pad(bed, (0, max(0, n - len(bed))))
    pres = np.zeros(n, np.float32)
    for start, samples, _, _ in pl.narr:
        pres[int(start * SR): int(start * SR) + len(samples)] = 1
    k = int(0.25 * SR)
    pres = np.clip(np.convolve(pres, np.ones(k, np.float32) / k, mode="same") * 1.4, 0, 1)
    bed_gain = 10 ** (mcfg.get("gain_db", -21) / 20) * (1 - pres * (1 - 10 ** (-7 / 20)))
    mono = dlg + fx * 0.55 + bed * bed_gain
    # gentle stereo: dialogue centred, music/fx slightly widened
    left = mono + np.roll(bed * bed_gain, 240) * 0.15
    right = mono + np.roll(bed * bed_gain, -240) * 0.15
    st = np.stack([left, right], axis=1)
    peak = float(np.max(np.abs(st)))
    st = np.tanh(st * 1.05) / np.tanh(1.05)
    V.write_wav(out, st)
    return {"peak_pre_limiter": round(peak, 3)}


# --------------------------------------------------------------------------- rendering
_STATE = {}


def _init_worker(prod, windows):
    _STATE["prod"] = prod
    _STATE["windows"] = windows
    _STATE["scenes"] = {}


def _scene(i):
    sc = _STATE["scenes"].get(i)
    if sc is None:
        w0, w1 = _STATE["windows"][i]
        seg = _STATE["prod"]["segments"][i]
        sc = SCENES[seg["scene"]](w1 - w0, seg, _STATE["prod"])
        _STATE["scenes"][i] = sc
    return sc


def render_frame(t):
    windows = _STATE["windows"]
    i = next((k for k, (a, b) in enumerate(windows) if a <= t < b), len(windows) - 1)
    w0, w1 = windows[i]
    img = _scene(i).frame(min(t - w0, w1 - w0 - 1e-3))
    if i > 0 and t - w0 < XFADE:  # cross-dissolve from the previous scene
        p0, p1 = windows[i - 1]
        prev = _scene(i - 1).frame(p1 - p0 - 1e-3)
        a = ease("in_out", (t - w0) / XFADE)
        img = Image.blend(prev.convert("RGB"), img.convert("RGB"), a)
    return img.convert("RGB")


def _render_chunk(args):
    idx, f0, f1, out = args
    cmd = [studio_config.FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    for f in range(f0, f1):
        proc.stdin.write(render_frame(f / FPS).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise ProductionError(proc.stderr.read().decode()[-1500:])
    return idx


def render_video(pl: Plan, work: Path, workers=None, max_seconds=None, log=print):
    n_frames = int(round(pl.duration * FPS))
    if max_seconds:
        n_frames = min(n_frames, int(max_seconds * FPS))
    workers = workers or max(1, min(8, os.cpu_count() or 2))
    seg_dir = work / "segments"
    shutil.rmtree(seg_dir, ignore_errors=True)
    seg_dir.mkdir(parents=True)
    n_chunks = workers * 2
    b = [round(i * n_frames / n_chunks) for i in range(n_chunks + 1)]
    jobs = [(i, b[i], b[i + 1], seg_dir / f"c{i:03d}.mp4") for i in range(n_chunks) if b[i + 1] > b[i]]
    t0 = time.time()
    with ProcessPoolExecutor(workers, initializer=_init_worker, initargs=(pl.prod, pl.windows)) as ex:
        for k, _ in enumerate(ex.map(_render_chunk, jobs), 1):
            log(f"      chunk {k}/{len(jobs)}")
    (seg_dir / "list.txt").write_text("".join(f"file '{j[3].name}'\n" for j in jobs))
    silent = work / "video_silent.mp4"
    V.run([studio_config.FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(seg_dir / "list.txt"), "-c", "copy", str(silent)])
    log(f"      {n_frames} frames in {time.time() - t0:.1f}s")
    return silent, n_frames


def mux(silent: Path, mix_wav: Path, ass: Path, out: Path, title: str, brand: str):
    loud = studio_audio.measure_loudness(mix_wav)
    esc = str(ass).replace(":", r"\:").replace("'", r"\'")
    fonts = str(studio_config.FONT_DIR).replace(":", r"\:")
    V.run([studio_config.FFMPEG, "-y", "-loglevel", "error", "-i", str(silent), "-i", str(mix_wav),
           "-vf", f"subtitles='{esc}':fontsdir='{fonts}'",
           "-af", studio_audio.loudnorm_filter(loud) + f",aresample={SR}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-profile:v", "high", "-level", "4.2",
           "-pix_fmt", "yuv420p", "-r", str(FPS), "-g", str(FPS * 2), "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2",
           "-movflags", "+faststart", "-shortest", "-metadata", f"title={title}", "-metadata", f"artist={brand}", str(out)])
    return loud


# --------------------------------------------------------------------------- full run
def produce(path, workers=None, preview=False, log=print) -> dict:
    from . import packaging, scorecard
    t_start = time.time()
    prod = load(path)
    out_dir = RELEASES / f"{prod['id']}_{_slug(prod['title'])}"
    work = VAR / "work" / prod["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)

    log(f"[1/8] fact gate — {prod['title']}")
    gate = research.gate(prod)
    if not gate["render_ok"]:
        raise ProductionError("fact gate blocked rendering:\n  - " + "\n  - ".join(gate["blockers"]))
    (out_dir / "SOURCES.md").write_text(research.source_record_md(prod))

    log("[2/8] narration + timing")
    pl = plan(prod, work)
    durs = {i: len(n[1]) / SR for i, n in enumerate(pl.narr)}
    findings = story.check_story(prod, durs)
    for f in findings:
        log(f"      {f}")
    if any(f.level == "error" for f in findings):
        raise ProductionError("story check failed: " + "; ".join(str(f) for f in findings if f.level == "error"))
    log(f"      duration {pl.duration:.2f}s, {len(pl.windows)} scenes, voice={pl.narr[0][3]}")

    log("[3/8] captions")
    ass = write_captions(pl, out_dir)
    log("[4/8] sound design + mix")
    mix_wav = work / "mix.wav"
    mix_info = mix(pl, mix_wav)

    log("[5/8] animation")
    silent, n_frames = render_video(pl, work, workers, max_seconds=6 if preview else None, log=log)

    log("[6/8] final mux")
    name = f"N4V3D_{prod['id']}_{_slug(prod['title'])}_1080x1920{'_preview' if preview else ''}.mp4"
    final = out_dir / name
    loud = mux(silent, mix_wav, ass, final, prod["title"], prod.get("brand", "N4V3D MEDIA"))

    log("[7/8] technical QC")
    qc = studio_qc.run_qc(final, None, out_dir, expect_duration=None if preview else pl.duration)
    extra = _extra_checks(pl, final)
    log("[8/8] scorecard, SEO, compliance, InVideo package")
    meta = {
        "id": prod["id"], "title": prod["title"], "channel": prod["channel"], "video": final.name,
        "duration": round(pl.duration, 2), "frames": n_frames, "voice": sorted({n[3] for n in pl.narr}),
        "fact_gate": gate, "story_findings": [str(f) for f in findings], "mix": mix_info,
        "loudness_pre_norm": loud, "qc_passed": qc["passed"], "extra_checks": extra,
        "scenes": [{"scene": s["scene"], "stage": s["stage"], "t0": round(w[0], 2), "t1": round(w[1], 2)}
                   for s, w in zip(prod["segments"], pl.windows)],
        "render_seconds": round(time.time() - t_start, 1),
    }
    (out_dir / "production_report.json").write_text(json.dumps(meta, indent=2))
    prod["_video"] = final.name
    if not preview:
        packaging.package_all(prod, pl, final, out_dir, meta, render_frame_fn=_frame_for_package)
        scorecard.build(prod, meta, qc, out_dir)
    log(f"done in {time.time() - t_start:.1f}s -> {final}")
    return meta


def _frame_for_package(prod, windows, t):
    _init_worker(prod, windows)
    return render_frame(t)


def _extra_checks(pl, final):
    checks = []
    checks.append({"check": "Every segment has narration audio", "passed": all(len(n[1]) > SR * 0.3 for n in pl.narr)})
    checks.append({"check": "Every segment has captions", "passed": len(pl.cues) >= len(pl.narr)})
    checks.append({"check": "Captions end before video end", "passed": max(c[1] for c in pl.cues) <= pl.duration})
    checks.append({"check": "Caption chunks <= 32 chars", "passed": all(len(c[2]) <= 32 for c in pl.cues)})
    checks.append({"check": "Captions above Shorts UI zone", "passed": CAPTION_BOTTOM <= studio_config.SAFE_BOTTOM})
    checks.append({"check": "Scene lengths 2.5-15 s", "passed": all(2.5 <= b - a <= 15 for a, b in pl.windows)})
    return checks


def _slug(s):
    return "".join(c.lower() if c.isalnum() else "_" for c in s).strip("_").replace("__", "_")
