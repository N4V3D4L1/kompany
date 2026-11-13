"""Caption generation: Shorts-style chunked ASS (burned in) + full-line SRT sidecar."""
from __future__ import annotations

import re
from pathlib import Path

from . import config
from .timeline import Timeline

CAPTION_Y = 845   # top edge of the caption block: clear wall between window and heads
MAX_WORDS = 4
MAX_CHARS = 18

# ASS colours are &HAABBGGRR
SPEAKER_COLOURS = {"nuggo": "&H003CC9FF", "brickley": "&H00F5EEDC"}


def _ts_ass(t):
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _ts_srt(t):
    t = max(0.0, t)
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def chunk(text: str):
    words = text.split()
    out, cur = [], []
    for w in words:
        cand = " ".join(cur + [w])
        if cur and (len(cur) >= MAX_WORDS or len(cand) > MAX_CHARS):
            out.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
        if re.search(r"[.!?]$", w) and len(cur) >= 2:
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def cues(tl: Timeline):
    """Yield (t0, t1, who, chunk_text) with chunk timing weighted by characters."""
    res = []
    for c in tl.clips:
        parts = chunk(c.text)
        total = sum(len(p) for p in parts) or 1
        t = c.t0
        for p in parts:
            d = c.dur * len(p) / total
            res.append((t, t + d, c.who, p))
            t += d
    return res


def write_ass(tl: Timeline, path: Path):
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {config.WIDTH}
PlayResY: {config.HEIGHT}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Inter Black,84,&H00FFFFFF,&H00FFFFFF,&H002E1D2B,&H64000000,0,0,0,0,100,100,2,0,1,8,4,8,110,170,{CAPTION_Y},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for t0, t1, who, text in cues(tl):
        col = SPEAKER_COLOURS.get(who, "&H00FFFFFF")
        pop = r"{\fscx70\fscy70\t(0,90,\fscx106\fscy106)\t(90,160,\fscx100\fscy100)" + rf"\1c{col}" + "}"
        lines.append(f"Dialogue: 0,{_ts_ass(t0)},{_ts_ass(t1)},Caption,{who},0,0,0,,{pop}{text.upper()}")
    path.write_text(hdr + "\n".join(lines) + "\n")
    return path


def write_srt(tl: Timeline, path: Path):
    out = []
    for i, c in enumerate(tl.clips, 1):
        speaker = c.who.capitalize()
        out.append(f"{i}\n{_ts_srt(c.t0)} --> {_ts_srt(c.t1)}\n{speaker}: {c.text}\n")
    path.write_text("\n".join(out))
    return path
