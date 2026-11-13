# Environment Audit — N4V3D MEDIA v2

*Audited 2026-11-13 by Claude Code. Every entry below was checked with a command in this session; nothing is assumed.*

> **Important scope note.** This session runs in a **managed cloud container** (Claude Code on the web),
> **not on the owner's own computer**. I could not inspect the owner's local machine, local apps or local
> folders. Re-run the checks in `deploy/setup.sh` on the production host.

## Hardware & OS
| Item | Finding |
|---|---|
| OS | Ubuntu 24.04.5 LTS (Linux 6.18, x86_64) |
| CPU | 4 vCPU, Intel Xeon @ 2.10 GHz |
| GPU | **None** (no `nvidia-smi`, no `/dev/dri`) — CPU rendering only |
| RAM | 15 GiB |
| Storage | ~30 GB writable session allowance (ephemeral container) |

## Runtimes & core tools
| Tool | Status | Notes |
|---|---|---|
| Python | 3.13.18 | Pillow 12.3, NumPy 2.5, Jinja2 3.1, PyYAML, requests, uvicorn present |
| Node.js / npm | v22.23 / 10.9 | npm registry reachable (Remotion 4.0.543 visible) |
| Docker | 29.9.2 | present, not required |
| FFmpeg / ffprobe | 6.1.1 | libx264, AAC, **libass** (subtitles), **libflite** (offline TTS), loudnorm/ebur128 |
| Git / gh | 2.43 / 2.89 | GitHub access via the session's integration |
| Redis / PostgreSQL client | 7.0 / 16 | present; not used (SQLite chosen — zero-ops) |
| Chrome for Testing / Playwright Chromium | 153 / 1243 | available for headless tooling |
| Claude Code | 2.1.323 | the build/supervision tool (not a runtime dependency) |

## Requested production tools
| Tool | Installed? | Decision |
|---|---|---|
| Paperclip | not found | Not installed. Replaced by a small built-in orchestrator (SQLite + worker + systemd/cron) — fewer moving parts, fully tested. |
| Ruflo | not found | Not needed. |
| PraisonAI | not found | Not needed. |
| MiroFish | not found | Not needed for this scope. |
| Blender | **not found** | Not installed: 3D needs a GPU host to be practical; no GPU here. Integration point documented (ARCHITECTURE.md). |
| OpenToonz | not found | Not installed: the procedural 2D rig system already covers character animation with versionable code. |
| Synfig | not found | Not installed (same reason). |
| Remotion | not installed (reachable on npm) | Not installed: Remotion's licence requires a paid company licence for companies above its free-tier threshold — owner decision; the Python engine covers typography/captions/infographics today. |
| Theatre.js / Three.js / GSAP | not installed | Web-animation tools; not needed for offline MP4 rendering at this stage. |
| InVideo AI | web service | Official MCP server exists (`mcp.invideo.io/mcp`) but needs a paid seat + account auth; **invideo.io is blocked by this environment's network policy**. Manual export package implemented instead. |
| YouTube Data API | reachable (googleapis.com 200) | Upload module implemented; **no channel credentials** — untested live by design until the owner authorises. |

## AI & API configuration
* `ANTHROPIC_BASE_URL` set (Claude Code session); no other AI/API keys present (no InVideo, YouTube, ElevenLabs, OpenAI keys).
* No paid service was activated.

## Network reachability (this container)
| Destination | Result |
|---|---|
| PyPI, npm registry | ✅ |
| GitHub release downloads | ✅ (used for Kokoro model files) |
| Hugging Face | ❌ blocked (403 from proxy) |
| invideo.io | ❌ blocked |
| googleapis.com | ✅ |

## Installed during this session (with justification)
| Package | Licence | Why |
|---|---|---|
| `kokoro-onnx 0.6.1` (+ `onnxruntime`, `espeakng-loader`, `phonemizer-fork`) | MIT (kokoro-onnx, onnxruntime) | Natural neural narration offline on CPU. espeak-ng (GPL-3) is used only as a phonemizer tool; it is not distributed with the videos. |
| Kokoro-82M int8 model + voices (`.models/kokoro/`, 118 MB) | Apache-2.0 | Voice model; SHA-256 recorded in `deploy/setup.sh`. Not committed to git. |

## Existing N4V3D assets found
* `n4v3d-animation-studio/` — procedural 2D cartoon pipeline + EP001 *The Snooze-O-Matic* (reused as the render/audio/QC core).
* `website kk run 01/` — unrelated website files (untouched).

## Verification of the reported resolution problem
The earlier review claimed `N4V3D_ep001_the_snooze_o_matic_1080x1920.mp4` was encoded at ~512×910.
Independent ffprobe of both copies in the repository:

```
h264, 1080x1920, 30/1 fps, ~2.07 Mb/s · aac 48 kHz stereo 196 kb/s
```

**The source file is genuinely 1080×1920.** The 512×910 figure most likely came from a downscaled
preview/transcode produced by a viewer or chat app, not from the file itself. The upgraded edition was
still rebuilt natively from the episode source (see `docs/SNOOZE_UPGRADE.md`), not upscaled.
