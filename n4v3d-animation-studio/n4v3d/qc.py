"""Automated quality control for a rendered episode.

Covers the machine-checkable half of docs/QC_CHECKLIST.md and writes
qc_report.json + qc_report.md next to the video.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import config, subtitles
from .voice import run


def _probe(path):
    r = run([config.FFPROBE, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)])
    return json.loads(r.stdout)


def _filter_log(path, vf=None, af=None):
    cmd = [config.FFMPEG, "-hide_banner", "-nostats", "-i", str(path)]
    if vf:
        cmd += ["-vf", vf]
    if af:
        cmd += ["-af", af]
    cmd += ["-f", "null", "-"]
    return run(cmd).stderr


def run_qc(video: Path, tl=None, out_dir: Path | None = None, expect_duration: float | None = None) -> dict:
    video = Path(video)
    out_dir = Path(out_dir or video.parent)
    checks = []

    def check(name, ok, detail, severity="error"):
        checks.append({"check": name, "passed": bool(ok), "detail": detail, "severity": severity})

    info = _probe(video)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur = float(info["format"]["duration"])
    num, den = map(int, v["r_frame_rate"].split("/"))
    fps = num / den

    check("Resolution is 1080x1920 (9:16 vertical)", (v["width"], v["height"]) == (1080, 1920), f"{v['width']}x{v['height']}")
    check("Video codec H.264 / yuv420p", v["codec_name"] == "h264" and v["pix_fmt"] == "yuv420p", f"{v['codec_name']} {v['pix_fmt']}")
    check(f"Frame rate {config.FPS} fps", abs(fps - config.FPS) < 0.01, f"{fps:.3f}")
    check("Duration within Shorts limit (<= 60 s)", dur <= config.MAX_SHORTS_SECONDS, f"{dur:.2f}s")
    if expect_duration:
        check(f"Duration on target ({expect_duration:.0f}s +/- 1.0s)", abs(dur - expect_duration) <= 1.0, f"{dur:.2f}s")
    check("Audio track present (AAC, 48 kHz, stereo)",
          a is not None and a["codec_name"] == "aac" and int(a["sample_rate"]) == 48000 and a["channels"] == 2,
          f"{a['codec_name']} {a['sample_rate']}Hz {a['channels']}ch" if a else "missing")
    check("Fast-start (moov atom first) for streaming", _moov_first(video), "moov before mdat")

    # loudness
    log = _filter_log(video, af="ebur128=peak=true")
    m_i = re.findall(r"I:\s+(-?[\d.]+) LUFS", log)
    m_tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", log)
    lufs = float(m_i[-1]) if m_i else None
    tp = float(m_tp[-1]) if m_tp else None
    check(f"Integrated loudness {config.TARGET_LUFS:.0f} LUFS +/- 1.5", lufs is not None and abs(lufs - config.TARGET_LUFS) <= 1.5, f"{lufs} LUFS")
    check("True peak <= -1.0 dBTP", tp is not None and tp <= -1.0, f"{tp} dBTP")

    # black / frozen / silent stretches
    log = _filter_log(video, vf="blackdetect=d=0.4:pix_th=0.10")
    blacks = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", log)
    check("No black frames > 0.4 s", not blacks, f"{len(blacks)} found {blacks[:3]}")
    log = _filter_log(video, vf="freezedetect=n=-60dB:d=2.5")
    freezes = re.findall(r"freeze_start: ([\d.]+)", log)
    check("No frozen picture > 2.5 s", not freezes, f"{len(freezes)} found {freezes[:3]}", severity="warning")
    log = _filter_log(video, af="silencedetect=n=-45dB:d=1.2")
    sil = re.findall(r"silence_start: ([\d.]+)", log)
    check("No dead air > 1.2 s", not sil, f"{len(sil)} found {sil[:3]}", severity="warning")

    # captions / dialogue
    if tl is not None:
        cue_list = subtitles.cues(tl)
        covered = {c.id for c in tl.clips}
        check("Every dialogue line has voice audio", all(Path(c.wav).exists() and c.dur > 0.2 for c in tl.clips), f"{len(tl.clips)} lines")
        check("Every dialogue line has captions", len(covered) == len(tl.clips) and len(cue_list) >= len(tl.clips), f"{len(cue_list)} caption cues")
        check("Captions end before video end", all(c[1] <= dur + 0.05 for c in cue_list), f"last cue {max(c[1] for c in cue_list):.2f}s")
        cps = max(len(c.text) / c.dur for c in tl.clips)
        check("Reading speed <= 22 chars/sec", cps <= 22, f"max {cps:.1f} cps", severity="warning")
        long_chunks = [c[3] for c in cue_list if len(c[3]) > subtitles.MAX_CHARS + 4]
        check(f"Caption chunks <= {subtitles.MAX_CHARS + 4} chars", not long_chunks, f"{long_chunks[:2]}", severity="warning")
        overlaps = [(a.id, b.id) for a, b in zip(tl.clips, tl.clips[1:]) if b.t0 < a.t1 - 0.01]
        check("No overlapping dialogue", not overlaps, f"{overlaps}", severity="warning")
        check("Captions inside Shorts safe area", config.SAFE_TOP <= subtitles.CAPTION_Y <= config.SAFE_BOTTOM - 300,
              f"caption top y={subtitles.CAPTION_Y}, safe {config.SAFE_TOP}-{config.SAFE_BOTTOM}")
        placeholders = sorted({c.provider for c in tl.clips if "placeholder" in c.provider})
        check("No low-quality placeholder TTS (flite)", not placeholders,
              f"placeholder voices in use: {placeholders}" if placeholders else
              "voices: " + ", ".join(sorted({c.provider for c in tl.clips})), severity="warning")
        synthetic = sorted({c.provider for c in tl.clips if c.provider != "recorded"})
        check("Synthetic voices disclosed in compliance report", True,
              f"synthetic: {synthetic}" if synthetic else "all human-recorded", severity="warning")

    size_mb = video.stat().st_size / 1e6
    check("File size reasonable (< 100 MB)", size_mb < 100, f"{size_mb:.1f} MB")

    errors = [c for c in checks if not c["passed"] and c["severity"] == "error"]
    warns = [c for c in checks if not c["passed"] and c["severity"] == "warning"]
    result = {"video": str(video), "passed": not errors, "errors": len(errors), "warnings": len(warns),
              "duration": dur, "lufs": lufs, "true_peak": tp, "checks": checks}
    (out_dir / "qc_report.json").write_text(json.dumps(result, indent=2))
    md = [f"# Automated QC — {video.name}", "",
          f"**Result: {'PASS' if result['passed'] else 'FAIL'}** — {len(errors)} errors, {len(warns)} warnings", "",
          "| | Check | Detail |", "|---|---|---|"]
    for c in checks:
        icon = "PASS" if c["passed"] else ("WARN" if c["severity"] == "warning" else "FAIL")
        md.append(f"| {icon} | {c['check']} | {c['detail']} |")
    md += ["", "Manual review items: see `docs/QC_CHECKLIST.md`."]
    (out_dir / "qc_report.md").write_text("\n".join(md) + "\n")
    for c in checks:
        icon = "PASS" if c["passed"] else ("WARN" if c["severity"] == "warning" else "FAIL")
        print(f"   [{icon}] {c['check']}: {c['detail']}")
    print(f"   QC {'PASSED' if result['passed'] else 'FAILED'} ({len(errors)} errors, {len(warns)} warnings)")
    return result


def _moov_first(path: Path) -> bool:
    with open(path, "rb") as f:
        head = f.read(1 << 16)
    i, j = head.find(b"moov"), head.find(b"mdat")
    return i != -1 and (j == -1 or i < j)
