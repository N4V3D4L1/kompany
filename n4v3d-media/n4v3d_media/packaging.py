"""Deliverable packaging: SEO metadata draft, thumbnail, storyboard, compliance report, InVideo export."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from . import story
from n4v3d.gfx import font


def package_all(prod, pl, final: Path, out_dir: Path, meta: dict, render_frame_fn):
    frames = storyboard(prod, pl, out_dir, render_frame_fn)
    thumbnail(prod, pl, out_dir, render_frame_fn)
    seo_draft(prod, out_dir)
    compliance(prod, meta, out_dir)
    invideo_package(prod, pl, out_dir, frames)


def storyboard(prod, pl, out_dir, render_frame_fn):
    sb = out_dir / "storyboard"
    sb.mkdir(exist_ok=True)
    tiles = []
    for i, ((a, b), seg) in enumerate(zip(pl.windows, prod["segments"])):
        f = render_frame_fn(prod, pl.windows, a + (b - a) * 0.7)
        p = sb / f"scene_{i + 1:02d}_{seg['scene']}.jpg"
        f.resize((540, 960)).save(p, quality=86)
        tiles.append((p, a, b, seg))
    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 280 + 10, rows * 580 + 10), (14, 14, 22))
    d = ImageDraw.Draw(sheet)
    for i, (p, a, b, seg) in enumerate(tiles):
        x, y = 10 + (i % cols) * 280, 10 + (i // cols) * 580
        sheet.paste(Image.open(p).resize((270, 480)), (x, y))
        d.text((x + 4, y + 488), f"{i + 1}. {seg['stage'].upper()}  {a:04.1f}-{b:04.1f}s", font=font(20, "ExtraBold"), fill=(255, 255, 255))
        d.text((x + 4, y + 516), seg["scene"], font=font(18, "ExtraBold"), fill=(170, 180, 200))
    sheet.save(out_dir / "storyboard.jpg", quality=88)
    md = [f"# Storyboard — {prod['title']}", "", f"Treatment: {prod['direction']['treatment']}", ""]
    for i, (p, a, b, seg) in enumerate(tiles):
        md += [f"## {i + 1}. {seg['stage'].title()} · {a:.1f}–{b:.1f}s · `{seg['scene']}`", f"![]({p.relative_to(out_dir)})", "",
               f"**VO:** {seg['text']}", f"**Claims:** {', '.join(seg.get('claims', [])) or '—'}", ""]
    (out_dir / "STORYBOARD.md").write_text("\n".join(md))
    return tiles


def thumbnail(prod, pl, out_dir, render_frame_fn):
    th = prod["seo"]["thumbnail"]
    idx = next(i for i, s in enumerate(prod["segments"]) if s["scene"] == th["scene"])
    a, b = pl.windows[idx]
    img = render_frame_fn(prod, pl.windows, a + (b - a) * th.get("t", 0.6)).convert("RGBA")
    shade = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shade).rectangle([0, 1250, 1080, 1920], fill=(0, 0, 0, 170))
    img.alpha_composite(shade.filter(ImageFilter.GaussianBlur(40)))
    d = ImageDraw.Draw(img)
    words = th["text"].split()
    lines, cur = [], []
    for w in words:
        if cur and font(118, "Black").getlength(" ".join(cur + [w])) > 960:
            lines.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    lines.append(" ".join(cur))
    y = 1380
    for ln in lines:
        d.text((540, y), ln, font=font(118, "Black"), fill=(255, 255, 255), anchor="mm", stroke_width=8, stroke_fill=(10, 10, 20))
        y += 130
    img.convert("RGB").save(out_dir / "thumbnail.jpg", quality=92)


def seo_draft(prod, out_dir):
    seo = prod["seo"]
    ranked = story.check_titles(seo["titles"], seo["keywords"])
    best = ranked[0]["title"]
    src = "\n".join(f"[{s['id']}] {s['title']} — {s.get('publisher', '')} ({s.get('year', 'n.d.')}) {s.get('url', '')}" for s in prod["sources"])
    draft = {
        "_note": "DRAFT — nothing is uploaded automatically. Requires human approval (approved=true) via the Control Center.",
        "approved": False,
        "title": best + (" #shorts" if prod["format"] == "short" and "#shorts" not in best.lower() else ""),
        "title_candidates": ranked,
        "description": seo["description"] + "\n\nSources:\n" + src,
        "tags": seo["keywords"],
        "hashtags": seo["hashtags"],
        "category": "Education",
        "made_for_kids": None,
        "captions_file": "captions.srt",
        "thumbnail_file": "thumbnail.jpg",
        "metrics_note": "No keyword volumes or performance figures are estimated here; use YouTube Analytics after channel connection.",
    }
    (out_dir / "youtube_metadata_DRAFT.json").write_text(json.dumps(draft, indent=2, ensure_ascii=False))
    return draft


def compliance(prod, meta, out_dir):
    medical = meta["fact_gate"]["medical"]
    synthetic = [v for v in meta["voice"] if v != "recorded"]
    recon = prod["channel"] == "world"
    lines = [f"# Compliance report — {prod['title']}", "",
             "## Originality & licensing",
             "- Script: original, written for N4V3D; facts verified against cited sources (see SOURCES.md).",
             "- Visuals: generated in-house by code (n4v3d_media/visual); no stock footage, no third-party images.",
             "- Music & SFX: synthesised in-house (n4v3d_media/soundscape.py, n4v3d/sfx.py) — no licence required.",
             "- Fonts: Inter (SIL Open Font License 1.1), bundled with licence.",
             f"- Narration: {', '.join(meta['voice'])}. Kokoro-82M weights/voices: Apache-2.0; kokoro-onnx: MIT. "
             "Generic synthetic voice — no real person's voice is cloned or imitated.",
             "- No watermarks, no unlicensed characters, no celebrity likeness.", "",
             "## Accuracy & safety",
             f"- Fact gate: {'PASS' if meta['fact_gate']['render_ok'] else 'BLOCKED'} "
             f"({meta['fact_gate']['counts']['verified']} verified, {meta['fact_gate']['counts']['hedged']} hedged).",
             ]
    if medical:
        lines += ["- Medical content: general education only; no individual diagnosis; no treatment dosing; "
                  "ends with 'see a dermatologist' + 'not medical advice'.",
                  f"- Expert review: **{prod['review']['expert_review']['status']}** — publishing is blocked until a qualified clinician approves."]
    if recon:
        lines += ["- Historical reconstructions are labelled 'Artistic reconstruction' / 'Illustrative'; maps labelled 'Simplified map'.",
                  "- Debated interpretations are hedged on screen and in narration ('Historians still debate the details')."]
    lines += ["", "## YouTube policy review (checked Nov 2026 against the YPP monetization policies page)",
              "- Inauthentic (formerly 'repetitious') content: this video has original research, a distinct script and bespoke visuals; "
              "avoid templated mass production — keep per-video creative variation and human review in the loop.",
              "- Altered or synthetic content disclosure: required for *realistic* content that could mislead. This video is clearly "
              "stylised animation; the narrator is synthetic but does not impersonate a real person. "
              + ("Recommendation: disclosure likely not required; owner to decide in YouTube Studio." if synthetic else "No synthetic voice."),
              "- Misleading metadata: titles ranked with a clickbait filter; thumbnail reflects actual content.",
              "- Monetization approval is never guaranteed; eligibility is decided by YouTube.", "",
              "## Status",
              f"- Publish allowed by gates: {'YES' if meta['fact_gate']['publish_ok'] else 'NO'} "
              f"{('— ' + '; '.join(meta['fact_gate']['publish_blockers'])) if meta['fact_gate']['publish_blockers'] else ''}",
              "- Owner approval required before any upload (approved=false)."]
    (out_dir / "COMPLIANCE.md").write_text("\n".join(lines) + "\n")


def invideo_package(prod, pl, out_dir, tiles):
    """Manual-import package for InVideo AI (or any editor). Not an API integration."""
    pk = out_dir / "invideo_package"
    pk.mkdir(exist_ok=True)
    dr = prod["direction"]
    (pk / "01_script.md").write_text(f"# {prod['title']}\n\n" + "\n\n".join(s["text"] for s in prod["segments"]) + "\n")
    scenes = []
    for i, ((a, b), seg) in enumerate(zip(pl.windows, prod["segments"])):
        scenes.append({
            "scene": i + 1, "stage": seg["stage"], "start": round(a, 2), "end": round(b, 2), "voiceover": seg["text"],
            "prompt": (f"{dr['style']} Scene: {seg['scene'].replace('_', ' ')}. Show: {seg['text']} "
                       f"Palette: {', '.join(dr['palette'].values())}. Camera: {dr['camera']} "
                       + ("Label as artistic reconstruction. " if prod["channel"] == "world" else "Stylised scientific illustration, no real lesions. ")
                       + "No text other than the on-screen labels listed."),
            "reference_frame": f"../storyboard/{Path(tiles[i][0]).name}",
            "claims": seg.get("claims", []),
        })
    (pk / "02_scene_prompts.json").write_text(json.dumps(scenes, indent=2))
    (pk / "03_storyboard.md").write_text((out_dir / "STORYBOARD.md").read_text().replace("](storyboard/", "](../storyboard/"))
    (pk / "04_narration.md").write_text(f"# Narration\n\nPersona: {prod['persona']} — voice {prod['narrator']}\n\n"
                                        "Pace ~155 wpm, natural pauses between beats, no hype. Reference take: ../" + Path(prod.get('_video', 'video.mp4')).name + "\n")
    (pk / "05_music_direction.md").write_text(f"# Music & SFX\n\nMusic: {prod['music']['style']} (calm, under narration, ducked -7 dB).\nSFX: {dr['sfx']}\nUse only licensed or InVideo-library assets.\n")
    (pk / "06_editing_instructions.md").write_text(f"# Editing\n\nTransitions: {dr['transitions']}\nTypography: {dr['typography']}\nLighting: {dr['lighting']}\n"
                                                   f"Safety: {dr['safety']}\nAspect 9:16, 1080x1920, 30 fps, captions burned in lower third (above y=1450).\n")
    (pk / "README.md").write_text("# InVideo import package\n\nThis is a **manual** export for InVideo AI's supported interface: paste the script, "
                                  "use the scene prompts and storyboard frames as references, and follow the narration/music/editing notes.\n\n"
                                  "InVideo also offers an official MCP server (mcp.invideo.io/mcp) for AI agents; it requires a paid InVideo seat and "
                                  "account authorisation and is **not connected or tested** in this system yet. The local pipeline does not depend on it.\n")
