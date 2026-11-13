# Operations Guide

## Daily use
```bash
cd n4v3d-media
python3 -m n4v3d_media enqueue productions/<id>        # add a production
python3 -m n4v3d_media worker --once                   # run one pass now (or run the systemd service)
python3 -m n4v3d_media status                          # where every job is, and why it's waiting
python3 -m n4v3d_media dashboard                       # Control Center on http://127.0.0.1:8787
python3 -m n4v3d_media stop    | resume                # EMERGENCY STOP (or create var/STOP)
python3 -m n4v3d_media produce productions/<id> [--preview]   # direct render, bypassing the queue
python3 -m n4v3d_media review releases/<dir> --reviewer "Name" --scores storytelling=18,visual=17,originality=9
python3 -m unittest discover -s tests
```

## Making a new video
1. **Idea → research.** Create `productions/<id>/production.json` (copy a pilot). Add sources (≥ 2 authoritative ones) and atomic claims, each with a verbatim evidence quote.
2. **Fact check.** A *different* agent or person from the author verifies each claim (`checked_by`, `review.fact_checker`). Debated points are marked `interpretation`/`disputed` and must be **hedged in the narration** (`hedged: true`). Medical topics set `expert_review.required`.
3. **Script.** Write the segments to the six-stage structure. `python -m n4v3d_media gate productions/<id>` and the SCRIPT stage enforce the rules.
4. **Queue it.** The worker narrates, plans timing, renders, mixes, captions, runs QC, scores it and builds every package, then stops at APPROVAL.
5. **Human review.** Watch the MP4. Record scores with `review`. For medical content, get the clinician's sign-off: set `review.expert_review.status = "approved"` along with reviewer and date.
6. **Approve.** Use *Approve publish* on the Pipeline page and set `approved: true` in `youtube_metadata_DRAFT.json`. Only then will PUBLISH run, and it uploads as **private**.

## What stops the pipeline (by design)
| Condition | Stage | What you'll see |
|---|---|---|
| Missing sources / claims | RESEARCH | `blocked` + notification |
| Unverified, rejected or unhedged-disputed claim; author = fact-checker | FACT_CHECK | `blocked` |
| Story-structure error (missing stage, generic opener, too long) | SCRIPT / STORYBOARD | `blocked` |
| Render or QC exception | ANIMATION / QUALITY_REVIEW | retried 3× with backoff (60 s, 120 s, 240 s), then `failed` |
| Medical expert review pending, human review missing, score < 90, owner approval missing | APPROVAL | `waiting` — rechecked every 10 min |
| YouTube not connected | PUBLISH / ANALYTICS | `waiting` |
| Emergency stop | any | nothing runs |

The worker writes notifications to `var/notifications.log`. Set `N4V3D_WEBHOOK_URL` to push them to Slack, Discord or ntfy (this path is implemented but untested).

## Failure recovery (tested)
* **Transient error:** the stage is retried with exponential backoff (`tests/test_system.py::test_recovers_after_transient_failure`).
* **Persistent error:** after 3 attempts the job is `failed`, an error notification is sent, and a dashboard *Retry* button appears.
* **Worker crash mid-stage:** on restart, jobs whose heartbeat is more than 45 min old are reset to `pending` (`test_stale_running_job_recovered`).
* **Render cache:** narration is cached by content hash, so retries don't re-synthesise voices.

## Scheduling
* systemd: `deploy/n4v3d-worker.service` (runs continuously, restarts on failure) and `deploy/n4v3d-dashboard.service`.
* cron alternative: `deploy/crontab.example` (`flock` prevents overlapping runs).
* Claude Code is **not** needed at runtime; it built and tested the system.

## YouTube connection (owner action)
1. Google Cloud Console: create a project, enable **YouTube Data API v3** (plus **YouTube Analytics API** for metrics), and create an OAuth client of type *Desktop app*.
2. Authorise once with the channel's Google account (scopes `youtube.upload`, `yt-analytics.readonly`) and keep the refresh token.
3. Write `var/youtube_credentials.json` with `{"client_id", "client_secret", "refresh_token"}` and run `chmod 600`.
4. Dry run: `python3 -c "from n4v3d_media import youtube; from pathlib import Path; print(youtube.upload_release(Path('releases/<dir>'), 'you', dry_run=True))"`. It refuses until every gate passes.

**Status:** the upload code follows the documented resumable-upload protocol but **hasn't been exercised against a live channel**. Test with one private upload first.

## InVideo (manual workflow)
Each release contains `invideo_package/` (script, scene prompts, storyboard references, narration, music and editing notes) for use in InVideo's normal interface. InVideo's official MCP server (`mcp.invideo.io/mcp`) could automate this once you have a paid seat and authorise it. It is **not connected or tested**, and invideo.io was unreachable from this build environment.

## Cost
Running cost today: **$0**. There are no paid APIs and it runs on CPU. A 60 s Short renders in about 2–2.5 min on 4 vCPUs. Optional paid upgrades (each needs your authorisation): a GPU host for Blender 3D, premium TTS or a human narrator, a Remotion company licence, an InVideo seat, and licensed music.
