"""Fast unit tests (no full render). Run: python -m unittest discover tests"""
import copy
import math
import tempfile
import unittest
from pathlib import Path

from n4v3d import config, subtitles
from n4v3d.anim import Track, ease
from n4v3d.episode import EpisodeError, load, validate
from n4v3d.timeline import build_fitted

EP = config.EPISODES / "ep001_snooze_o_matic"


class TestAnim(unittest.TestCase):
    def test_track_tween(self):
        tr = Track((0.0, 0.0))
        tr.tween(1.0, 1.0, (10.0, 20.0), "linear")
        self.assertEqual(tr.value(0.5), (0.0, 0.0))
        self.assertEqual(tr.value(1.5), (5.0, 10.0))
        self.assertEqual(tr.value(3.0), (10.0, 20.0))

    def test_discrete_set(self):
        tr = Track("neutral")
        tr.set(2.0, "dizzy")
        self.assertEqual(tr.value(1.9), "neutral")
        self.assertEqual(tr.value(2.0), "dizzy")

    def test_ease_bounds(self):
        for name in ("in", "out", "in_out", "out_back", "out_bounce", "out_elastic"):
            self.assertAlmostEqual(ease(name, 0.0), 0.0, places=6)
            self.assertAlmostEqual(ease(name, 1.0), 1.0, places=6)


class TestEpisode(unittest.TestCase):
    def test_pilot_validates(self):
        ep = load(EP)
        self.assertEqual(ep["id"], "ep001")

    def test_unknown_action_rejected(self):
        ep = load(EP)
        bad = copy.deepcopy(ep)
        bad["scenes"][0]["beats"].append({"do": "teleport", "who": "nuggo"})
        with self.assertRaises(EpisodeError):
            validate(bad)

    def test_unknown_speaker_rejected(self):
        bad = copy.deepcopy(load(EP))
        bad["scenes"][0]["beats"].append({"line": "ghost", "text": "boo"})
        with self.assertRaises(EpisodeError):
            validate(bad)


class TestTimeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.tl = build_fitted(load(EP), Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_fits_target_duration(self):
        self.assertAlmostEqual(self.tl.duration, 45.0, delta=0.5)
        self.assertLessEqual(self.tl.duration, config.MAX_SHORTS_SECONDS)

    def test_dialogue_ordered_and_non_overlapping(self):
        for a, b in zip(self.tl.clips, self.tl.clips[1:]):
            self.assertLessEqual(a.t1, b.t0 + 0.01)

    def test_lipsync_envelope(self):
        for c in self.tl.clips:
            self.assertGreater(c.env.max(), 0.3, c.id)
            self.assertLessEqual(c.env.max(), 1.0)

    def test_punch_auto_aim_reaches_nuggo(self):
        from n4v3d.assets.props import SnoozeOMatic as Box
        punches = [f for f in self.tl.entities["box"].fx if f.name == "punch"]
        self.assertGreaterEqual(len(punches), 4)
        f = punches[1]  # first hit on Nuggo
        box = self.tl.entities["box"]
        bx, by = box.val("pos", f.t0)
        sc = box.val("scale", f.t0)
        gx, gy = Box.glove_pos(f.params["angle"], f.params["reach"])
        nx, ny = self.tl.entities["nuggo"].val("pos", f.t0)
        self.assertLess(math.hypot(bx + gx * sc - nx, by + gy * sc - (ny - 250)), 180)

    def test_caption_chunks(self):
        cues = subtitles.cues(self.tl)
        self.assertGreaterEqual(len(cues), len(self.tl.clips))
        self.assertTrue(all(len(c[3]) <= subtitles.MAX_CHARS + 4 for c in cues))

    def test_frame_renders(self):
        from n4v3d.animator import Renderer
        r = Renderer(self.tl, Path(self.tmp.name) / "bg")
        img = r.frame(24.0)
        self.assertEqual(img.size, (config.WIDTH, config.HEIGHT))


if __name__ == "__main__":
    unittest.main()
