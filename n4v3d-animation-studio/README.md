# N4V3D Animation Studio

A modular, AI-assisted production pipeline for **original 2D animated YouTube Shorts**:
a script goes in and a finished **1080×1920 MP4** comes out, with voices, lip-sync, captions,
sound effects, music, loudness normalisation and automated QC.

**Pilot:** *EP001 "The Snooze-O-Matic"*. This is a 45-second comedy starring two original characters,
**Nuggo** (an over-confident inventor bean) and **Brickley** (a deadpan brick with tea).

| | |
|---|---|
| Script | [`episodes/ep001_snooze_o_matic/SCRIPT.md`](episodes/ep001_snooze_o_matic/SCRIPT.md) |
| Characters | [`docs/CHARACTERS.md`](docs/CHARACTERS.md) · model sheets in `assets/character_sheets/` |
| Episode format | [`docs/EPISODE_FORMAT.md`](docs/EPISODE_FORMAT.md) |
| QC checklist | [`docs/QC_CHECKLIST.md`](docs/QC_CHECKLIST.md) |
| Rendered pilot | `releases/ep001/` (MP4, captions, thumbnail, QC report) |

> ⚠️ **Nothing is ever uploaded automatically.** The pipeline has no upload code. Each render writes
> a `youtube_metadata_DRAFT.json` with `"approved": false` for the owner to review, and the owner
> uploads manually.

---

## Quick start

Requirements: Python ≥ 3.10, **FFmpeg built with libx264, libass and libflite** (most distro builds
include all three), Pillow and NumPy. Nothing else is needed: no GPU, no network, no API keys.

```bash
pip install -r requirements.txt          # pillow, numpy (anthropic is optional)
python -m n4v3d validate episodes/ep001_snooze_o_matic
python -m n4v3d render   episodes/ep001_snooze_o_matic            # full render + QC (about 2–3 min on 4 cores)
python -m n4v3d render   episodes/ep001_snooze_o_matic --preview  # first 6 s only
python -m n4v3d still    episodes/ep001_snooze_o_matic --t 12 25  # single frames for review
python -m n4v3d qc       output/ep001_the_snooze_o_matic/*.mp4    # re-run QC on any video
python -m n4v3d assets                                            # export model sheets, BG plates, SFX
python -m n4v3d draft "Nuggo tries to teach a houseplant to fetch" --id ep002   # AI script draft
python -m unittest discover tests
```

## Pipeline

```
episode.json ──► validate ──► voices (TTS or recorded takes) ──► timeline (auto-timed + fitted to 45 s)
                                                                   │
           ┌───────────────────────┬───────────────────────────────┼────────────────────────┐
           ▼                       ▼                               ▼                        ▼
   captions (.ass/.srt)   audio mix (dialogue+SFX+       frame renderer (parallel       lip-sync from
                          ducked music) → EBU R128        workers → H.264 segments)      voice envelope
           └───────────────────────┴──────────────► FFmpeg final mux ◄─────────────────────┘
                                                (burned captions, −14 LUFS AAC, faststart)
                                                          │
                                       QC report · thumbnail · contact sheet · metadata draft
```

| Module | Role |
|---|---|
| `n4v3d/assets/characters.py` | Character rigs: emotions, poses, eyes, 4-shape mouths, idle blink and breathing |
| `n4v3d/assets/props.py` | Snooze-O-Matic (auto-aiming glove) and alarm clock |
| `n4v3d/assets/backgrounds.py` | Kitchen background plate (cached) |
| `n4v3d/assets/overlays.py` | Title card, end card, comic bursts, Zzz, speed lines |
| `n4v3d/gfx.py`, `anim.py` | Anti-aliased vector drawing (2× supersampling), easing, keyframe tracks |
| `n4v3d/episode.py` | Script format and validator |
| `n4v3d/timeline.py` | Compiles beats into timed tracks; auto-fits to the target duration |
| `n4v3d/animator.py` | Per-frame evaluation: FX, lip-sync, shadows, camera |
| `n4v3d/voice.py` | Voice providers (offline flite placeholder, recorded-take override) and lip-sync envelope |
| `n4v3d/sfx.py`, `music.py` | Procedurally synthesised SFX library and an original music loop |
| `n4v3d/audio.py` | Mix, ducking, two-pass loudness normalisation |
| `n4v3d/subtitles.py` | Shorts-style chunked, speaker-coloured captions plus an SRT sidecar |
| `n4v3d/render.py` | Orchestration, parallel rendering, final mux, reports |
| `n4v3d/qc.py` | Automated QC (format, loudness, black/freeze/silence, captions, safe areas) |
| `n4v3d/ai/writer.py` | AI-assisted episode drafting with Claude, validated against the format |

### What's "AI-assisted"
* **Script drafting**: `n4v3d draft` sends the character bible, format spec and pilot to Claude
  and validates the returned episode. Without the `anthropic` package or credentials it writes the
  prompt to a file instead.
* **Automatic lip-sync** from voice loudness envelopes.
* **Automatic timing**: scenes are timed from the real audio and fitted to the target length.
* **Auto-aimed action**: punches compute their own angle and reach from character positions.
* **Automated QC** on every render.

### Placeholders (swap for production)
| Placeholder | How to replace |
|---|---|
| Voices: offline flite TTS, pitch-shifted | Drop recorded takes as `episodes/<ep>/voice/L01.wav …` and they're used automatically. Or add a cloud TTS provider class in `voice.py`. |
| Music: procedural ukulele loop | Set `"music": {"file": "track.wav"}` in the episode. |
| SFX: synthesised | Replace a function in `sfx.py` or load files instead. |

## Tooling decisions
The existing environment was inspected before anything was installed. FFmpeg already had
`libx264`, `libass` and `libflite`, and Python already had Pillow and NumPy. That covers rendering,
encoding, captions and offline TTS, so **no new dependencies were installed**. Heavier tools
(Blender, Synfig, OpenToonz) weren't needed for this flat-vector style. Because every asset is
code, characters stay on model in every episode and changes can be reviewed as diffs.

## Repository layout
```
n4v3d/                 pipeline package
episodes/ep001_…/      episode.json (machine script) + SCRIPT.md (screenplay) + voice/ (optional takes)
assets/                fonts (OFL), character sheets, background plates, SFX library
docs/                  character bible, episode format, QC checklist
releases/ep001/        the rendered pilot and its reports
output/                render workspace (git-ignored)
tests/                 unit tests
```
