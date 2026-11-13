"""End-to-end render: script -> voices -> timeline -> captions -> audio -> frames -> MP4 -> QC."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image

from . import audio, config, episode as episode_mod, subtitles, timeline as timeline_mod
from .animator import Renderer
from .voice import run

_TL = None
_R = None


def _worker_init(tl, bg_dir):
    global _TL, _R
    _TL = tl
    _R = Renderer(tl, bg_dir)


def _render_segment(args):
    idx, f0, f1, out = args
    cmd = [config.FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{config.WIDTH}x{config.HEIGHT}", "-r", str(config.FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p",
           "-r", str(config.FPS), str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    for f in range(f0, f1):
        proc.stdin.write(_R.frame(f / config.FPS).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(proc.stderr.read().decode()[-2000:])
    return idx, f1 - f0


def slug(s: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in s).strip("_").replace("__", "_")


def render_episode(ep_path, out_root: Path = config.OUTPUT, workers: int | None = None,
                   preview: bool = False, skip_qc: bool = False) -> dict:
    t_start = time.time()
    ep = episode_mod.load(ep_path)
    warns = episode_mod.validate(ep)
    for w in warns:
        print("  warn:", w)
    out_dir = Path(out_root) / f"{ep['id']}_{slug(ep['title'])}"
    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)

    print(f"[1/6] voices + timeline   ({ep['title']})")
    tl = timeline_mod.build_fitted(ep, work)
    print(f"      duration {tl.duration:.2f}s  fit={tl.fit_report}")

    print("[2/6] captions")
    ass = subtitles.write_ass(tl, out_dir / "captions.ass")
    srt = subtitles.write_srt(tl, out_dir / "captions.srt")

    print("[3/6] audio mix")
    mix_wav = work / "mix.wav"
    mix_info = audio.mix(tl, mix_wav)
    loud = audio.measure_loudness(mix_wav)

    n_frames = int(round(tl.duration * config.FPS))
    if preview:
        n_frames = min(n_frames, config.FPS * 6)
    workers = workers or max(1, min(8, os.cpu_count() or 2))
    print(f"[4/6] animation: {n_frames} frames @ {config.FPS}fps on {workers} workers")
    seg_dir = work / "segments"
    if seg_dir.exists():
        shutil.rmtree(seg_dir)
    seg_dir.mkdir()
    n_seg = workers * 2
    bounds = [round(i * n_frames / n_seg) for i in range(n_seg + 1)]
    jobs = [(i, bounds[i], bounds[i + 1], seg_dir / f"seg_{i:03d}.mp4") for i in range(n_seg) if bounds[i + 1] > bounds[i]]
    bg_dir = work / "bg"
    Renderer(tl, bg_dir)  # warm background cache before forking
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=workers, initializer=_worker_init, initargs=(tl, bg_dir)) as ex:
        done = 0
        for idx, n in ex.map(_render_segment, jobs):
            done += n
            print(f"      segment {idx + 1}/{len(jobs)}  ({done}/{n_frames} frames)", flush=True)
    print(f"      rendered in {time.time() - t0:.1f}s")
    concat = seg_dir / "list.txt"
    concat.write_text("".join(f"file '{j[3].name}'\n" for j in jobs))
    silent = work / "video_silent.mp4"
    run([config.FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(silent)])

    print("[5/6] final mux (burned captions, loudness-normalised AAC, faststart)")
    name = f"N4V3D_{ep['id']}_{slug(ep['title'])}_1080x1920{'_preview' if preview else ''}.mp4"
    final = out_dir / name
    ass_esc = str(ass).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    fonts = str(config.FONT_DIR).replace(":", r"\:")
    run([config.FFMPEG, "-y", "-loglevel", "error", "-i", str(silent), "-i", str(mix_wav),
         "-vf", f"subtitles='{ass_esc}':fontsdir='{fonts}'",
         "-af", audio.loudnorm_filter(loud) + f",aresample={config.SAMPLE_RATE}",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high", "-level", "4.2",
         "-pix_fmt", "yuv420p", "-r", str(config.FPS), "-g", str(config.FPS * 2),
         "-c:a", "aac", "-b:a", "192k", "-ar", str(config.SAMPLE_RATE), "-ac", "2",
         "-movflags", "+faststart", "-shortest",
         "-metadata", f"title={ep['title']}", "-metadata", "artist=N4V3D Animation Studio",
         str(final)])

    # thumbnail + contact sheet for review
    thumb_t = float(ep.get("thumbnail_time", tl.duration * 0.4))
    thumb = out_dir / "thumbnail.jpg"
    run([config.FFMPEG, "-y", "-loglevel", "error", "-ss", f"{thumb_t:.2f}", "-i", str(final), "-frames:v", "1", "-q:v", "2", str(thumb)])
    sheet = out_dir / "contact_sheet.jpg"
    _contact_sheet(final, tl.duration if not preview else n_frames / config.FPS, sheet)

    report = {
        "episode": ep["id"], "title": ep["title"], "output": str(final), "duration": tl.duration,
        "fit": tl.fit_report, "frames": n_frames, "mix": mix_info, "loudness_pre_norm": loud,
        "lines": [{"id": c.id, "who": c.who, "t0": round(c.t0, 2), "dur": round(c.dur, 2),
                   "voice": c.provider, "text": c.text} for c in tl.clips],
        "sfx": [{"t": round(t, 2), "name": n} for t, n, *_ in tl.sfx],
        "scenes": [{**s, "t0": round(s["t0"], 2), "t1": round(s["t1"], 2)} for s in tl.scenes],
        "render_seconds": round(time.time() - t_start, 1),
        "warnings": warns,
    }
    (out_dir / "production_report.json").write_text(json.dumps(report, indent=2))
    _write_metadata_draft(ep, out_dir)

    if not skip_qc:
        print("[6/6] automated QC")
        from . import qc
        res = qc.run_qc(final, tl, out_dir, expect_duration=None if preview else float(ep.get("target_duration", tl.duration)))
        report["qc_passed"] = res["passed"]
    print(f"done in {time.time() - t_start:.1f}s -> {final}")
    return report


def _contact_sheet(video: Path, duration: float, out: Path, n: int = 12):
    tmp = out.parent / "work" / "sheet"
    tmp.mkdir(parents=True, exist_ok=True)
    thumbs = []
    for i in range(n):
        t = (i + 0.5) * duration / n
        f = tmp / f"{i:02d}.jpg"
        run([config.FFMPEG, "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
             "-vf", "scale=270:480", str(f)])
        thumbs.append((t, f))
    from PIL import ImageDraw
    from .gfx import font
    cols = 6
    rows = (n + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 280 + 10, rows * 520 + 10), (30, 20, 34))
    d = ImageDraw.Draw(sheet)
    for i, (t, f) in enumerate(thumbs):
        im = Image.open(f)
        x, y = 10 + (i % cols) * 280, 10 + (i // cols) * 520
        sheet.paste(im, (x, y))
        d.text((x + 4, y + 484), f"{t:05.2f}s", font=font(26, "ExtraBold"), fill=(255, 255, 255))
    sheet.save(out, quality=88)


def _write_metadata_draft(ep, out_dir: Path):
    meta = ep.get("publish", {})
    draft = {
        "_note": "DRAFT ONLY. Nothing is uploaded automatically. Set approved=true only after human review.",
        "approved": False,
        "platform": "YouTube Shorts",
        "title": meta.get("title", ep["title"]),
        "description": meta.get("description", ""),
        "tags": meta.get("tags", []),
        "made_for_kids": meta.get("made_for_kids", None),
        "altered_or_synthetic_content_disclosure": meta.get("synthetic_disclosure", "Animated; placeholder synthetic voices"),
        "captions_file": "captions.srt",
    }
    (out_dir / "youtube_metadata_DRAFT.json").write_text(json.dumps(draft, indent=2))
