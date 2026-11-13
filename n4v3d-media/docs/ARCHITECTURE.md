# N4V3D MEDIA v2 — Architecture

## Design principles
1. **Facts before frames.** Nothing renders until every claim is verified (or explicitly hedged) by an agent other than the author. Medical content additionally needs a clinician's sign-off before it can be approved or published.
2. **Human gates where judgment matters.** Automation runs IDEA → QUALITY_REVIEW unattended. APPROVAL and PUBLISH always need a person.
3. **One commercial platform is never a single point of failure.** The complete pipeline runs locally on CPU with no paid APIs. InVideo and YouTube are optional edges.
4. **Everything is code.** Characters, scenes, music and SFX are generated procedurally, so they stay consistent, can be reviewed as diffs, and carry no licensing questions.
5. **Honest scoring.** Automated checks measure what can be measured. Subjective scores are labelled provisional until a human records them.

## System map
```
productions/<id>/production.json   ← script + claims + sources + direction + SEO (the single source of truth)
        │
        ▼
┌───────────────────────────── orchestrator (SQLite + worker, systemd/cron) ─────────────────────────────┐
│ IDEA → RESEARCH → FACT_CHECK → SCRIPT → STORYBOARD → ASSETS → ANIMATION → VOICE → EDIT → QUALITY_REVIEW │
│      → APPROVAL (human) → PUBLISH (gated, private-by-default) → ANALYTICS → IMPROVEMENT                 │
│ retries with backoff · stale-job recovery · emergency stop · notifications (log + optional webhook)    │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
        │ uses
        ▼
 story.py ── narrative rules (6-stage shorts / 6-chapter long-form, hook rules, pace, claim links, title ranking)
 research.py ── source record + fact gate (author ≠ fact-checker, hedging rules, medical expert gate)
 narration.py ── Kokoro-82M neural TTS personas (+ recorded-take override, flite fallback)
 visual/ ── science.py (health), history.py (world), kit.py (typography, callouts, glows, camera)
 soundscape.py ── music beds + documentary SFX (procedural)
 production.py ── timing fit, captions (ASS + SRT), mix, parallel render, mux, QC
 scorecard.py ── 100-point evaluation, blockers, revision plan, bounded revision loop
 packaging.py ── SEO draft, thumbnail, storyboard, compliance report, InVideo export package
 youtube.py ── official Data API v3 upload (gated; untested until the owner connects a channel)
 dashboard/ ── N4V3D MEDIA CONTROL CENTER (auth, CSRF, emergency stop, approvals, reports, ledger)
        │ reuses
        ▼
 ../n4v3d-animation-studio/n4v3d ── vector drawing (gfx), easing/tracks, audio loudness, technical QC, cartoon rigs
```

## Tool selection (what was chosen, and what wasn't)
| Need | Chosen | Why | Alternatives considered |
|---|---|---|---|
| Orchestration / scheduling | Built-in SQLite worker + systemd/cron | Zero infrastructure, crash-safe, fully tested (`tests/`) | Paperclip, Ruflo and PraisonAI aren't installed; adding an agent framework would add moving parts without a clear gain at this scale |
| Programmatic motion graphics, captions, infographics | Python + Pillow vector engine (2× supersampled) + libass | Already installed, native 1080×1920, deterministic, renders in parallel on CPU | **Remotion**: excellent, but needs a paid company licence above its free threshold (owner decision) and a Chrome render farm |
| 2D characters | Procedural rigs (studio) | Consistent model sheets, lip-sync from audio, versionable | OpenToonz/Synfig: GUI-centric, not installed, weaker automation |
| 3D (anatomy, architecture) | *Not yet* | No GPU on this host; CPU Cycles renders would take hours per Short | **Blender** is the right tool once a GPU host exists: scenes slot in as `Scene` subclasses that play back pre-rendered PNG sequences |
| Interactive maps / Three.js | *Not yet* | Offline MP4 output doesn't need a browser runtime | Three.js via headless Chrome is possible later for 3D maps |
| Narration | Kokoro-82M (Apache-2.0) via kokoro-onnx (MIT) | Natural voices, offline, $0, no voice cloning | ElevenLabs/Azure: paid, needs owner authorisation; flite: robotic (fallback only) |
| Music & SFX | Procedural synthesis | No licensing risk | Licensed libraries (Artlist, Epidemic) are drop-in replacements via the episode's `music.file` |
| Final processing | FFmpeg (libx264, AAC, libass, loudnorm, ebur128, blackdetect, freezedetect, silencedetect) | Industry standard, already installed | — |
| AI video drafts | InVideo AI, **manual export package** | Official MCP exists but needs a paid seat, owner auth, and network access this environment blocks | Fully local pipeline remains the primary path |
| Publishing | YouTube Data API v3 (official OAuth) | Only supported method | No scraping or unofficial uploaders |

## Formats
* **Shorts:** 1080×1920, 30 fps, H.264 High 4.2 yuv420p, AAC 192 kbps 48 kHz stereo, −14 LUFS / ≤ −1 dBTP, faststart, ≤ 60 s. Both pilots are implemented and validated.
* **Long-form (5–12 min, 1920×1080):** the storytelling engine (6-chapter structure) and the render/QC/mux core are orientation-agnostic, but the current scene libraries are laid out for 9:16. **16:9 scene layouts aren't built yet**; that's the next build item before the first long-form episode.

## Data & secrets
* `var/` (git-ignored): SQLite database, logs, notifications, render workspace, `auth.json` (PBKDF2 hash), `secret.key`, optional `youtube_credentials.json` (chmod 600).
* `.models/` (git-ignored): Kokoro model files (checksums are in `deploy/setup.sh`).
* No credentials are ever written to production files, reports or the dashboard.
