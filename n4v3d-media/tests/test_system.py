"""System tests (fast; no full renders). Run: python -m unittest discover -s tests"""
import copy
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import n4v3d_media  # noqa: E402
from n4v3d_media import research, story
from n4v3d_media.orchestrator import db, worker

PROD = json.loads((n4v3d_media.PRODUCTIONS / "hs001_what_causes_acne" / "production.json").read_text())
WORLD = json.loads((n4v3d_media.PRODUCTIONS / "w001_how_humans_invented_money" / "production.json").read_text())


class TestResearchGate(unittest.TestCase):
    def test_pilots_pass_render_gate(self):
        self.assertTrue(research.gate(PROD)["render_ok"])
        self.assertTrue(research.gate(WORLD)["render_ok"])

    def test_medical_needs_expert_before_publish(self):
        g = research.gate(PROD)
        self.assertFalse(g["publish_ok"])
        self.assertTrue(any("expert" in b for b in g["publish_blockers"]))
        p = copy.deepcopy(PROD)
        p["review"]["expert_review"]["status"] = "approved"
        self.assertTrue(research.gate(p)["publish_ok"])

    def test_unverified_claim_blocks(self):
        p = copy.deepcopy(WORLD)
        p["claims"][0]["status"] = "unverified"
        self.assertFalse(research.gate(p)["render_ok"])

    def test_unhedged_interpretation_blocks(self):
        p = copy.deepcopy(WORLD)
        h5 = next(c for c in p["claims"] if c["status"] == "interpretation")
        h5["hedged"] = False
        self.assertFalse(research.gate(p)["render_ok"])

    def test_author_cannot_be_sole_fact_checker(self):
        p = copy.deepcopy(PROD)
        p["review"]["fact_checker"] = p["review"]["author"]
        self.assertFalse(research.gate(p)["render_ok"])


class TestStory(unittest.TestCase):
    def test_pilot_structure_ok(self):
        self.assertFalse([f for f in story.check_story(PROD) if f.level == "error"])

    def test_generic_opener_rejected(self):
        p = copy.deepcopy(PROD)
        p["segments"][0]["text"] = "Welcome back to our channel, today we talk about acne."
        self.assertTrue(any(f.rule == "hook" and f.level == "error" for f in story.check_story(p)))

    def test_missing_stage_rejected(self):
        p = copy.deepcopy(PROD)
        p["segments"] = [s for s in p["segments"] if s["stage"] != "surprise"]
        self.assertTrue(any(f.rule == "structure" for f in story.check_story(p)))

    def test_clickbait_titles_ranked_last(self):
        r = story.check_titles(["You WON'T BELIEVE what causes acne!!!", "What Actually Causes Acne?"], ["acne"])
        self.assertEqual(r[0]["title"], "What Actually Causes Acne?")
        self.assertTrue(r[-1]["clickbait"])


class TestOrchestrator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["N4V3D_NOTIFY_LOG"] = str(Path(self.tmp.name) / "notify.log")
        self.con = db.connect(Path(self.tmp.name) / "t.db")
        db.set_setting(self.con, "emergency_stop", False)
        self.jid = db.enqueue(self.con, "productions/x")

    def tearDown(self):
        os.environ.pop("N4V3D_NOTIFY_LOG", None)
        self.tmp.cleanup()

    def job(self):
        return dict(self.con.execute("SELECT * FROM jobs WHERE id=?", (self.jid,)).fetchone())

    def test_advances_and_waits_at_gate(self):
        hs = {s: (lambda j: ("next", {})) for s in db.STAGES}
        hs["APPROVAL"] = lambda j: ("wait", "owner publish approval missing")
        while worker.step(self.con, self.job(), hs) == "advanced":
            pass
        j = self.job()
        self.assertEqual((j["stage"], j["status"]), ("APPROVAL", "waiting"))
        self.assertIn("approval", j["wait_reason"])

    def test_retry_then_fail_with_notification(self):
        def boom(j):
            raise RuntimeError("render crashed")
        hs = {"IDEA": boom}
        self.assertEqual(worker.step(self.con, self.job(), hs), "retry")
        self.assertEqual(self.job()["attempts"], 1)
        self.assertIsNotNone(self.job()["next_run_at"])   # backoff scheduled
        worker.step(self.con, self.job(), hs)
        self.assertEqual(worker.step(self.con, self.job(), hs), "failed")
        self.assertEqual(self.job()["status"], "failed")
        self.assertTrue(any(e["level"] == "error" for e in db.events(self.con, job_id=self.jid)))

    def test_recovers_after_transient_failure(self):
        calls = {"n": 0}

        def flaky(j):
            calls["n"] += 1
            if calls["n"] == 1:
                raise IOError("disk hiccup")
            return "next", {}
        hs = {"IDEA": flaky}
        worker.step(self.con, self.job(), hs)
        self.assertEqual(worker.step(self.con, self.job(), hs), "advanced")
        self.assertEqual(self.job()["stage"], "RESEARCH")

    def test_stale_running_job_recovered(self):
        db.update(self.con, self.jid, status="running", heartbeat="2000-01-01T00:00:00+00:00")
        worker.recover_stale(self.con)
        self.assertEqual(self.job()["status"], "pending")

    def test_emergency_stop_blocks_all_stages(self):
        db.set_setting(self.con, "emergency_stop", True)
        hs = {s: (lambda j: ("next", {})) for s in db.STAGES}
        self.assertEqual(worker.step(self.con, self.job(), hs), "stopped")
        self.assertEqual(self.job()["stage"], "IDEA")

    def test_block_on_content_problem(self):
        self.assertEqual(worker.step(self.con, self.job(), {"IDEA": lambda j: ("block", "facts unverified")}), "blocked")
        self.assertEqual(self.job()["status"], "blocked")


class TestPublishingGates(unittest.TestCase):
    def test_upload_refused_without_approval(self):
        from n4v3d_media import youtube
        rel = next((n4v3d_media.RELEASES).glob("hs001_*"), None)
        if rel is None or not (rel / "youtube_metadata_DRAFT.json").exists():
            self.skipTest("pilot not rendered")
        with self.assertRaises(youtube.PublishBlocked) as cm:
            youtube.upload_release(rel, approved_by=None, dry_run=True)
        self.assertIn("approval", str(cm.exception))
        self.assertIn("expert", str(cm.exception))


class TestDashboardSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from n4v3d_media.dashboard import app
        cls.app = app
        cls.tmp = tempfile.TemporaryDirectory()
        app.AUTH = Path(cls.tmp.name) / "auth.json"
        app.SECRET = Path(cls.tmp.name) / "secret.key"
        app.set_password("correct horse battery")
        from http.server import ThreadingHTTPServer
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.tmp.cleanup()

    def opener(self):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None
        jar = CookieJar()
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect), jar

    def test_requires_login(self):
        op, _ = self.opener()
        with self.assertRaises(urllib.error.HTTPError) as cm:
            op.open(self.base + "/pipeline")
        self.assertEqual(cm.exception.code, 303)
        self.assertEqual(cm.exception.headers["Location"], "/login")

    def test_wrong_password_and_files_protected(self):
        op, _ = self.opener()
        with self.assertRaises(urllib.error.HTTPError) as cm:
            op.open(self.base + "/login", data=b"password=nope")
        self.assertEqual(cm.exception.code, 401)
        with self.assertRaises(urllib.error.HTTPError) as cm:
            op.open(self.base + "/files/../var/auth.json")
        self.assertIn(cm.exception.code, (303, 404))

    def test_login_and_csrf(self):
        op, jar = self.opener()
        try:
            op.open(self.base + "/login", data=b"password=correct+horse+battery")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 303)
            cookie = e.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        tok = cookie.split(";")[0]
        req = urllib.request.Request(self.base + "/", headers={"Cookie": tok})
        html = urllib.request.urlopen(req).read().decode()
        self.assertIn("EMERGENCY STOP", html)
        # POST without CSRF token is refused
        req = urllib.request.Request(self.base + "/stop", data=b"csrf=bad", headers={"Cookie": tok})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 403)
        h = json.loads(urllib.request.urlopen(self.base + "/health.json").read())
        self.assertIn("ffmpeg", h)


if __name__ == "__main__":
    unittest.main()
