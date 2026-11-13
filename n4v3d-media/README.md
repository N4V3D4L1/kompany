# N4V3D MEDIA — v2.0

An AI-assisted production system for **original, fact-checked educational YouTube videos**, covering two channels:

* **N4V3D HEALTH & SCIENCE:** calm, accurate scientific animation (medical-safety gated)
* **N4V3D WORLD:** cinematic history and general knowledge with labelled reconstructions

It takes a researched script through verification, narration, animation, sound design, captions, QC, scoring and packaging, all run by a background worker that stops at human gates. **Nothing is uploaded without your approval.**

| | |
|---|---|
| Pilot A | `releases/hs001_what_actually_causes_acne/` — *What Actually Causes Acne?* (59.6 s, 1080×1920) |
| Pilot B | `releases/w001_how_did_humans_invent_money/` — *How Did Humans Invent Money?* (57.4 s) |
| Cartoon benchmark | `../n4v3d-animation-studio/releases/ep001_directors_cut/` |
| Readiness report | [`docs/PRODUCTION_READINESS.md`](docs/PRODUCTION_READINESS.md) |
| Environment audit | [`docs/ENVIRONMENT_AUDIT.md`](docs/ENVIRONMENT_AUDIT.md) |
| Architecture & tool choices | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Operations (daily use, YouTube, InVideo, recovery) | [`docs/OPERATIONS.md`](docs/OPERATIONS.md) |
| Brand & style guide | [`docs/STYLE_GUIDE.md`](docs/STYLE_GUIDE.md) |
| Snooze-O-Matic analysis | [`docs/SNOOZE_UPGRADE.md`](docs/SNOOZE_UPGRADE.md) |

## Quick start
```bash
./deploy/setup.sh                                          # Python deps + Kokoro voice model (checksummed)
python3 -m n4v3d_media.dashboard.app --set-password        # Control Center password
python3 -m n4v3d_media enqueue productions/hs001_what_causes_acne
python3 -m n4v3d_media worker --once                       # or: systemd unit in deploy/
python3 -m n4v3d_media dashboard                           # http://127.0.0.1:8787
python3 -m unittest discover -s tests
```
Requires Python ≥ 3.10, FFmpeg with libx264 and libass, plus the sibling `n4v3d-animation-studio/` folder (shared render core).

## Pipeline
`IDEA → RESEARCH → FACT CHECK → SCRIPT → STORYBOARD → ASSETS → ANIMATION → VOICE → EDIT → QUALITY REVIEW → APPROVAL (human) → PUBLISH (gated, private) → ANALYTICS → IMPROVEMENT`

## Each release contains
MP4 · `captions.srt`/`.ass` · `thumbnail.jpg` · `storyboard.jpg` + `STORYBOARD.md` · `SOURCES.md` (claim-by-claim evidence) · `COMPLIANCE.md` · `SCORECARD.md` (100-point evaluation and revision plan) · `qc_report.md` · `youtube_metadata_DRAFT.json` (3 ranked titles, `approved: false`) · `invideo_package/`.
