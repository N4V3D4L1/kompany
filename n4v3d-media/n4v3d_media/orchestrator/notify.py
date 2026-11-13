"""Notifications: always appended to var/notifications.log; optionally POSTed to a webhook.

Set N4V3D_WEBHOOK_URL to a Slack/Discord/ntfy-compatible JSON webhook to get pushes.
(The webhook path is implemented but has not been tested against a live endpoint.)
"""
from __future__ import annotations

import json
import os
import urllib.request

from .. import VAR


def _log_path():
    return os.environ.get("N4V3D_NOTIFY_LOG") or str(VAR / "notifications.log")


def send(level, message, job_id=None, stage=None):
    VAR.mkdir(parents=True, exist_ok=True)
    from .db import now
    line = {"ts": now(), "level": level, "job": job_id, "stage": stage, "message": message}
    with open(_log_path(), "a") as f:
        f.write(json.dumps(line) + "\n")
    url = os.environ.get("N4V3D_WEBHOOK_URL")
    if url:
        try:
            req = urllib.request.Request(url, data=json.dumps({"text": f"[N4V3D {level}] job {job_id} {stage}: {message}"}).encode(),
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:  # never let notification failure break the pipeline
            with open(_log_path(), "a") as f:
                f.write(json.dumps({"ts": now(), "level": "warn", "message": f"webhook failed: {e}"}) + "\n")
