# Episode Format

An episode is one JSON file: `episodes/<id>_<slug>/episode.json`. Its timing is **automatic**.
Every line's length comes from its synthesised (or recorded) audio. The pipeline then stretches
the gaps between lines and the scene tails so the cut lands on `target_duration`.

## Top level

```jsonc
{
  "id": "ep001",
  "title": "The Snooze-O-Matic",
  "target_duration": 45.0,          // seconds (Shorts max is 60)
  "thumbnail_time": 24.6,
  "background": "kitchen_day",
  "music": {"bpm": 118, "gain_db": -16, "duck_db": -9},   // or {"file": "music.wav"}
  "cast": {"nuggo": {"provider": "flite", "voice": "slt", "pitch": 1.28, "tempo": 1.12}},
  "entities": {                      // everything on screen
    "nuggo": {"asset": "nuggo", "pos": [235, 1640], "scale": 1.2, "z": 2, "emotion": "excited"},
    "box":   {"asset": "box", "pos": [585, -420], "state": {"punch": 0.08, "angle": -90}}
  },
  "scenes": [ { "id": "s1", "name": "...", "tail": 0.3, "setup": {}, "beats": [ ... ] } ],
  "publish": { "title": "...", "description": "...", "tags": [] }   // draft metadata only
}
```

Coordinates are output pixels (1080×1920). The floor line is y = 1640.

## Beats

Beats run in order on a scene clock. Every beat accepts `delay` (seconds after the clock, can be
negative to overlap the previous line) and `wait` (whether the clock advances by the beat's duration).

| Beat | Example | Blocks by default? |
|---|---|---|
| Dialogue | `{"line": "nuggo", "text": "Behold!", "emotion": "excited", "pose": "up", "look": [0,-1], "tts": "pronunciation override"}` | yes (audio length) |
| Action | `{"do": "move", "who": "nuggo", "to": [300, 1640], "dur": 0.5, "ease": "out", "sfx": "whoosh"}` | no |
| Sound | `{"sfx": "bonk", "gain": 0.9}` | no |
| Overlay | `{"overlay": "burst", "text": "BONK!", "at": [470, 1060], "dur": 0.7}` | no |
| Hold | `{"pause": 0.5}` | yes |

`who` may be a list (`["nuggo", "brickley"]`) or `"camera"`.

## Actions

| Action | Params | Notes |
|---|---|---|
| `move` | `to` or `by`, `dur`, `ease` | eases: linear, in, out, in_out, out_back, out_elastic, out_bounce |
| `tilt` | `angle` | rotation around the feet |
| `scale` | `value` | |
| `face` | `dir`: left/right | |
| `show` / `hide` | | |
| `emotion` | `value` | |
| `pose` | `value` | blends over `dur` (0.22 s) |
| `look` | `at: [x, y]` | |
| `hold` | `value` | e.g. `"mug"` |
| `set` / `tween` | `prop`, `value` | any state property (`mood`, `active`, …) |
| `hop` | `height` | procedural FX |
| `squash` | `amount` | squash-and-stretch on impact |
| `shake` | `amp` | entity or camera |
| `spin` | `turns` | rotates around the body centre |
| `flail` | `speed` | arms wave |
| `punch` | `target` (+`aim_offset`, `overshoot`) or `angle` + `reach` | Snooze-O-Matic glove; `target` auto-aims at an entity or `"self_button"` |
| `ring` | `dur` | alarm clock |
| `press` | `dur` | box button |
| `zoom` | `scale`, `center` | camera |
| `reset` | | camera back to full frame |

## Overlays
`title`, `endcard`, `burst`, `zzz`, `speedlines`, `flash`. Title, endcard and flash are screen-space
(the camera doesn't affect them); the rest live in the world.

## Sound effects
`whoosh boing bonk thud alarm click ding pop snore slurp skid sting`, all synthesised in `n4v3d/sfx.py`.

## Voices
* `provider: "flite"`: offline placeholder TTS.
* **Recorded takes override TTS automatically**: put `L01.wav`, `L02.wav`, … (or a line's explicit
  `"id"`) into `episodes/<episode>/voice/`. Line ids are listed in `production_report.json`.
