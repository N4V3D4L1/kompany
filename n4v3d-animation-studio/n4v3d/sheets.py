"""Export reusable asset reference sheets: character model sheets, props, backgrounds, SFX."""
from __future__ import annotations

from PIL import Image, ImageDraw

from . import config, sfx
from .assets.backgrounds import BACKGROUNDS
from .assets.characters import CHARACTERS
from .assets.props import PROPS
from .gfx import font, hex2rgba

BG = (250, 242, 226)
INK = (43, 29, 46)


def _label(d, x, y, s, size=30, weight="ExtraBold", fill=INK):
    d.text((x, y), s, font=font(size, weight), fill=fill, anchor="mm")


def character_sheet(name: str):
    cls = CHARACTERS[name]
    emotions = ["neutral", "excited", "proud", "smug", "worried", "annoyed", "shocked", "dizzy", "deadpan", "sleepy"]
    poses = list(cls.POSES)
    cell_w, cell_h = 360, 560 if name == "nuggo" else 680
    cols = 5
    rows_e = (len(emotions) + cols - 1) // cols
    rows_p = (len(poses) + cols - 1) // cols
    mouth_row = 1
    H = 160 + (rows_e + rows_p + mouth_row) * (cell_h + 50) + 80
    sheet = Image.new("RGBA", (cols * cell_w + 40, H), BG + (255,))
    d = ImageDraw.Draw(sheet)
    _label(d, sheet.width / 2, 60, f"{cls.display.upper()} — MODEL SHEET", 56, "Black")
    _label(d, sheet.width / 2, 115, "N4V3D Animation Studio · procedural rig · emotions / poses / mouth chart", 26)
    y = 160
    sc = 0.75

    def put(state, x, y, caption):
        img, (px, py) = cls.render({"t": 1.3, **state}, sc)
        sheet.alpha_composite(img, (int(x + cell_w / 2 - px), int(y + cell_h - 30 - py)))
        _label(d, x + cell_w / 2, y + cell_h + 10, caption, 26)

    for i, e in enumerate(emotions):
        put({"emotion": e, "hold": "mug" if name == "brickley" else None,
             "arms": cls.POSES["hold" if name == "brickley" else "rest"]},
            20 + (i % cols) * cell_w, y + (i // cols) * (cell_h + 50), e)
    y += rows_e * (cell_h + 50)
    for i, p in enumerate(poses):
        put({"emotion": "neutral", "arms": cls.POSES[p]}, 20 + (i % cols) * cell_w, y + (i // cols) * (cell_h + 50), f"pose: {p}")
    y += rows_p * (cell_h + 50)
    for i, m in enumerate((0.0, 0.34, 0.67, 1.0)):
        put({"emotion": "excited" if name == "nuggo" else "deadpan", "mouth": m}, 20 + i * cell_w, y, f"mouth {m:.2f}")
    return sheet.convert("RGB")


def props_sheet():
    sheet = Image.new("RGBA", (1500, 900), BG + (255,))
    d = ImageDraw.Draw(sheet)
    _label(d, 750, 60, "PROPS — SNOOZE-O-MATIC & ALARM CLOCK", 52, "Black")
    variants = [
        ("box", {"mood": "happy"}, "box: happy"),
        ("box", {"mood": "angry", "active": True, "punch": 0.45, "angle": -20}, "box: angry, punching"),
        ("box", {"mood": "asleep"}, "box: asleep"),
        ("clock", {}, "clock"),
        ("clock", {"ringing": True, "t": 0.3}, "clock: ringing"),
    ]
    x = 40
    for asset, st, cap in variants:
        img, (px, py) = PROPS[asset].render({"t": 0.0, **st}, 0.8)
        sheet.alpha_composite(img, (int(x + 140 - px), int(700 - py)))
        _label(d, x + 140, 760, cap, 26)
        x += 290
    return sheet.convert("RGB")


def export_all():
    out = config.ASSETS / "character_sheets"
    out.mkdir(parents=True, exist_ok=True)
    for name in CHARACTERS:
        p = out / f"{name}_model_sheet.png"
        character_sheet(name).save(p)
        print(p)
    p = out / "props_sheet.png"
    props_sheet().save(p)
    print(p)
    bg_out = config.ASSETS / "backgrounds"
    bg_out.mkdir(parents=True, exist_ok=True)
    for k, fn in BACKGROUNDS.items():
        p = bg_out / f"{k}.png"
        fn().save(p)
        print(p)
    print(sfx.export_library(), "(sfx library)")
