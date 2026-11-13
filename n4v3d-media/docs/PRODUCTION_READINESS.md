# Production-Readiness Report — N4V3D MEDIA v2.0

*2026-11-13 · status labels: ✅ built & tested · 🟡 built, not tested live / partial · ⛔ blocked on owner action · ⏭ not built yet*

## Executive summary
N4V3D MEDIA v2 is a working, tested production system. It takes a researched script to a fact-gated, narrated, animated, captioned, loudness-normalised, QC'd 1080×1920 Short. That runs unattended through a background worker, which stops at human gates. It produced **two original educational pilots** and a **natively re-rendered Director's Cut** of the Snooze-O-Matic cartoon, all passing automated technical QC.

**It isn't ready to publish yet, and that's by design.** Before any upload:
- a dermatologist must review the acne pilot;
- a human must record quality scores (both pilots score **85** and **83/100** provisionally, below the 90 target);
- you must connect and authorise the YouTube channel.

Visual quality is clean, labelled 2D illustration. It isn't yet "premium 3D" (no GPU here). This is the main gap to the creative references.

## Deliverables
| Video | File | Duration | Technical QC | Score (provisional) | Release status |
|---|---|---|---|---|---|
| Pilot A — *What Actually Causes Acne?* | `n4v3d-media/releases/hs001_what_actually_causes_acne/` | 59.6 s | ✅ 0 errors / 0 warnings | 85/100 | ⛔ dermatologist review + human review + approval |
| Pilot B — *How Did Humans Invent Money?* | `n4v3d-media/releases/w001_how_did_humans_invent_money/` | 57.4 s | ✅ 0 / 0 | 83/100 | ⛔ human review + approval (historian spot-check recommended) |
| *The Snooze-O-Matic — Director's Cut* | `n4v3d-animation-studio/releases/ep001_directors_cut/` | 53.3 s | ✅ 0 errors / 1 warning (caption speed 23.6 cps) | — (benchmark) | ⛔ approval |

Every release includes: MP4 (1080×1920, 30 fps, H.264 High, AAC 48 kHz, −14 LUFS), burned captions plus SRT, thumbnail, storyboard, source record (`SOURCES.md`), compliance report, 100-point scorecard with revision plan, YouTube metadata draft (`approved: false`), and the InVideo package.

## Status by requirement
| # | Requirement | Status | Evidence / notes |
|---|---|---|---|
| 1 | Environment audit | ✅ | `docs/ENVIRONMENT_AUDIT.md`. This is the cloud build container; your local PC couldn't be audited |
| 2 | Production architecture & tool selection | ✅ | `docs/ARCHITECTURE.md` |
| 3–4 | Storytelling engine (shorts 6-stage, long-form 6-chapter) | ✅ | `story.py` + tests: banned openers, stage order, hook length, pace, claim links |
| 5 | Health channel + medical safety | ✅ / ⛔ | Fact gate, hedging, expert-review gate, disclaimer; **expert not yet engaged** |
| 6 | World channel + labelled reconstructions | ✅ | Badges on every reconstruction; hedged debate |
| 7 | Virtual director (treatment, storyboard, camera, transitions, typography…) | ✅ | `direction` block per production → `STORYBOARD.md`, scene library |
| 8 | Narration & audio | ✅ | Kokoro neural voices per persona, ducked music, licence-free SFX, −14 LUFS. Not a human performance |
| 9 | Character & visual consistency, asset library | ✅ | `docs/STYLE_GUIDE.md`, reusable rigs and scene assets |
| 10 | Snooze-O-Matic analysis & upgrade | ✅ | `docs/SNOOZE_UPGRADE.md`. **The 512×910 claim was false**; rebuilt natively, not upscaled |
| 11 | Technical standards (Shorts) | ✅ | Automated QC on every render |
| 11 | Long-form 1920×1080 | ⏭ | Engine is orientation-agnostic; **16:9 scene layouts not built yet** |
| 12 | 100-point evaluation, blockers, revision loop | ✅ | `scorecard.py`; subjective scores provisional until a human reviews; max 2 revisions then escalate |
| 13 | SEO (3 titles, ranking, description, hashtags, thumbnail) | ✅ | Clickbait filter; **no fabricated keyword volumes** |
| 14 | Retention analysis | ⛔ | Needs YouTube Analytics authorisation; nothing is estimated |
| 15 | Originality & YPP compliance report | ✅ | `COMPLIANCE.md` per video; policies checked (inauthentic-content rename, July 2025; synthetic disclosure) |
| 16 | Automation (queue, scheduler, DB, retries, health, notifications, emergency stop) | ✅ | Live end-to-end run reached APPROVAL unattended; 19 tests incl. failure recovery |
| 17 | InVideo integration | 🟡 | Manual export package ✅; official MCP exists but is ⛔ (paid seat + auth + network) |
| 18 | Two educational pilots | ✅ | See the deliverables table |
| 19 | Control Center dashboard | ✅ | Auth, CSRF, emergency stop, approvals, reports, ledger, health; desktop and phone verified with a headless browser |
| 20 | YouTube publishing | 🟡 ⛔ | Gated, private-by-default upload implemented; **untested live** (no credentials) |
| — | Paperclip / Blender / OpenToonz / Synfig / Remotion / Three.js | ⏭ | Not installed. Reasons are in ARCHITECTURE.md (GPU, licence, no clear gain) |

## Human actions required (genuine blockers)
1. **Medical review:** a board-certified dermatologist reviews `hs001` (script, visuals, claims C1–C12), then set `expert_review.status = "approved"`.
2. **Quality review:** watch all three videos and record scores (`python -m n4v3d_media review ...`).
3. **YouTube:** create the OAuth client, authorise the channel, and add `var/youtube_credentials.json` (docs/OPERATIONS.md).
4. **Dashboard password:** `python -m n4v3d_media.dashboard.app --set-password`.
5. **Decisions on paid upgrades** (none activated): a GPU host for Blender, a human narrator or premium TTS, an InVideo seat, a Remotion company licence, licensed music.
6. **Made-for-kids setting and synthetic-content disclosure** are your choices in YouTube Studio.

## Known limitations (honest list)
* Visuals are procedural 2D. They're clear and on-brand but not photoreal or 3D; this is the largest quality gap.
* Narration is neural TTS (natural, but no human acting). The 4-shape lip-sync is cartoon-grade.
* Subjective scores (story, visual, originality) are self-assessed until a human reviews. The same pipeline wrote the scripts, so its storytelling scores carry no independent weight.
* The fact-checker is a separate step and agent role within this build, not an independent human expert.
* The YouTube upload, analytics and notification-webhook paths are implemented but unexercised against live services.
* The money hook runs 5.6 s against the 4 s house target (flagged; editing score −2).
* The render host is 4 vCPU with no GPU: about 2–2.5 min per 60 s Short.
* Financial outcomes, retention and monetisation are unknown until real data exists. No projections are made.

## Recommended next steps
1. Complete the human reviews and the dermatologist sign-off, then publish both pilots **privately**, then unlisted, before anything goes public.
2. Build 16:9 layouts for the first long-form episode (a 6-chapter template is already enforced).
3. Add a GPU render host and a Blender scene type for hero shots (pore macro, coin strike).
4. Connect YouTube Analytics and let the IMPROVEMENT stage compare drop-off timestamps against the scene timelines.
