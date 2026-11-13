# Brand & Visual Consistency Guide

## Channel identities
| | N4V3D HEALTH & SCIENCE | N4V3D WORLD |
|---|---|---|
| Promise | Calm, accurate explanations of the body | Cinematic stories of how humans built the world |
| Narrator persona | Calm, knowledgeable, reassuring — Kokoro `af_heart`, speed 0.98 | Curious, cinematic, authoritative — Kokoro `bm_george`, speed 1.04 |
| Palette | Navy lab `#0B1630` · epidermis `#F2C4A8` · sebum `#F5C85C` · bacteria `#B266FF` · immune `#9FE7FF` · inflammation `#FF5A5A` (only hot colour) · accent cyan `#5CE1E6` | Dusk `#1B1033 → #E9854A` · sand `#C9A26B` · clay `#B98A5E` · silver `#D9DDE3` · electrum `#E3C15C` · accent gold `#FFD27A` |
| Imagery | Stylised scientific diagrams; translucent layers; **no photos of real lesions or gore** | Painterly flat reconstruction, parallax silhouettes, simplified maps |
| Mandatory labels | "Illustration" / "Simplified cross-section"; closing "Educational content · not medical advice" | "Artistic reconstruction" / "Illustrative" / "Simplified map"; on-screen hedge for debated points |
| Music | `science_pad` — cool minor-9 pad + soft pulse | `ancient_pad` — warm modal pad + lyre-like plucks |
| SFX | soft whoosh, bubble pop, low swell, UI tick | wind, stylus on clay, stamp, metallic coin strike |

## Shared rules
* **Typography:** Inter Black for titles; Inter ExtraBold for captions and labels. Captions sit in the lower third with their bottom edge at y = 1450, always above the Shorts UI zone (y > 1500). They show at most 5 words or 28 characters per chunk.
* **Callouts:** dot, thin leader line, label. They animate in one at a time and stay inside a 40 px margin.
* **Camera:** slow, deliberate push-ins (2–4 % per scene). There's one signature move per video (the pore iris; the coin strike). No shake on educational channels.
* **Transitions:** 0.35 s cross-dissolves. Every scene adds information, and scenes run 2.5–15 s.
* **Source chips:** any number shown on screen carries its source (e.g. "AAD GUIDELINE 2024", "BANK OF ENGLAND, 2014").
* **Safe area:** key content sits between y = 220 and y = 1450, and x ≤ 930 for anything important near the right edge.

## Asset library (reuse, don't regenerate)
* Science: `cross_section()` plate, gland/follicle geometry, bacteria lens, immune cells, factor icons — `n4v3d_media/visual/science.py`
* History: layered Mesopotamian city, clay tablet generator, balance scale, credit web, simplified Aegean map, original lion-head electrum coin — `n4v3d_media/visual/history.py`
* Recurring characters (cartoon line): Nuggo & Brickley rigs and model sheets — `n4v3d-animation-studio/docs/CHARACTERS.md`
