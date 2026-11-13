"""YouTube Data API v3 publishing (official API, OAuth 2.0) — gated and private-by-default.

Status: implemented against the documented resumable-upload protocol but NOT tested live:
no channel credentials are available in this environment. Use `dry_run=True` to validate.

Setup (owner, once): create an OAuth client (Desktop) in Google Cloud with the YouTube Data
API v3 enabled, obtain a refresh token for the channel (scope youtube.upload, and
yt-analytics.readonly for analytics), then store in var/youtube_credentials.json:
    {"client_id": "...", "client_secret": "...", "refresh_token": "..."}
(file permissions 600; never commit it — var/ is git-ignored).

Hard gates before any upload (all must pass, checked here AND in the worker):
  * owner approval recorded (approved_by) AND metadata draft approved=true
  * emergency stop off
  * fact gate publish_ok (incl. medical expert review), technical QC passed
Uploads default to privacyStatus=private; switching to public is a manual Studio action
unless the owner sets "privacy": "public" in the approved metadata.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

from . import VAR

CRED = VAR / "youtube_credentials.json"
TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"


class PublishBlocked(RuntimeError):
    pass


def configured() -> bool:
    return CRED.exists() or bool(os.environ.get("YOUTUBE_REFRESH_TOKEN"))


def _creds():
    if CRED.exists():
        return json.loads(CRED.read_text())
    return {"client_id": os.environ["YOUTUBE_CLIENT_ID"], "client_secret": os.environ["YOUTUBE_CLIENT_SECRET"],
            "refresh_token": os.environ["YOUTUBE_REFRESH_TOKEN"]}


def _access_token():
    c = _creds()
    data = urllib.parse.urlencode({"client_id": c["client_id"], "client_secret": c["client_secret"],
                                   "refresh_token": c["refresh_token"], "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=data), timeout=30) as r:
        return json.loads(r.read())["access_token"]


def check_gates(release: Path, approved_by: str | None):
    from .orchestrator import db
    meta = json.loads((release / "youtube_metadata_DRAFT.json").read_text())
    rep = json.loads((release / "production_report.json").read_text())
    reasons = []
    if not approved_by:
        reasons.append("no owner approval recorded")
    if not meta.get("approved"):
        reasons.append("metadata draft not approved (approved=false)")
    if db.emergency_stopped(db.connect()):
        reasons.append("emergency stop engaged")
    if not rep["fact_gate"]["publish_ok"]:
        reasons.append("fact gate: " + "; ".join(rep["fact_gate"]["publish_blockers"] + rep["fact_gate"]["blockers"]))
    if not rep["qc_passed"]:
        reasons.append("technical QC failed")
    if reasons:
        raise PublishBlocked("; ".join(reasons))
    return meta, rep


def build_request(release: Path, meta: dict):
    video = next(release.glob("N4V3D_*_1080x1920.mp4"))
    body = {
        "snippet": {"title": meta["title"][:100], "description": meta["description"][:5000],
                    "tags": meta.get("tags", [])[:30], "categoryId": "27"},  # 27 = Education
        "status": {"privacyStatus": meta.get("privacy", "private"),
                   "selfDeclaredMadeForKids": bool(meta.get("made_for_kids")),
                   "containsSyntheticMedia": bool(meta.get("contains_synthetic_media", False))},
    }
    return video, body


def upload_release(release: Path, approved_by: str | None, dry_run: bool = False):
    meta, rep = check_gates(release, approved_by)
    video, body = build_request(release, meta)
    if dry_run:
        return {"dry_run": True, "file": video.name, "bytes": video.stat().st_size, "body": body}
    token = _access_token()
    size = video.stat().st_size
    init = urllib.request.Request(UPLOAD_URL, data=json.dumps(body).encode(), method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Length": str(size), "X-Upload-Content-Type": "video/mp4"})
    with urllib.request.urlopen(init, timeout=60) as r:
        session = r.headers["Location"]
    with open(video, "rb") as f:
        put = urllib.request.Request(session, data=f.read(), method="PUT",
                                     headers={"Content-Type": "video/mp4", "Content-Length": str(size)})
        with urllib.request.urlopen(put, timeout=600) as r:
            res = json.loads(r.read())
    out = {"video_id": res.get("id"), "privacy": body["status"]["privacyStatus"], "approved_by": approved_by}
    (release / "youtube_upload.json").write_text(json.dumps(out, indent=2))
    return out


def fetch_analytics(job):
    """YouTube Analytics API v2 — requires yt-analytics.readonly scope. Not tested live."""
    raise NotImplementedError("Connect YouTube Analytics (docs/YOUTUBE.md); no metrics are fabricated.")
