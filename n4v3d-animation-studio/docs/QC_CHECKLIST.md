# Quality-Control Checklist

Every episode must pass this list **before** any upload is even proposed. Items marked 🤖 are
checked automatically by `python -m n4v3d qc <video>` (also run at the end of every render),
which writes `qc_report.md` / `qc_report.json` next to the video. Everything else is a human pass.

## 1. Technical delivery
- [ ] 🤖 1080×1920, 9:16 vertical
- [ ] 🤖 H.264 High, yuv420p, 30 fps constant
- [ ] 🤖 Duration ≤ 60 s and within ±1 s of target
- [ ] 🤖 AAC 48 kHz stereo audio track
- [ ] 🤖 Fast-start MP4 (moov atom first)
- [ ] 🤖 File size < 100 MB
- [ ] Plays correctly on a phone (YouTube app preview or local player)

## 2. Picture
- [ ] 🤖 No black frames > 0.4 s
- [ ] 🤖 No frozen picture > 2.5 s
- [ ] Key action and faces stay clear of the Shorts UI zones (top ~220 px, bottom ~420 px, right ~150 px)
- [ ] Characters stay on model (check against `assets/character_sheets/`)
- [ ] No sprite clipping, popping or wrong z-order (glove in front of faces, etc.)
- [ ] Every hit has a visible contact frame that lines up with its SFX
- [ ] Hook within the first 2 seconds (title plus first motion)
- [ ] Thumbnail frame (`thumbnail.jpg`) is readable at small size

## 3. Sound
- [ ] 🤖 Integrated loudness −14 LUFS ± 1.5
- [ ] 🤖 True peak ≤ −1 dBTP
- [ ] 🤖 No dead air > 1.2 s
- [ ] Dialogue clearly intelligible over music and SFX
- [ ] SFX are in sync with the action (±2 frames)
- [ ] Music ducks under dialogue and ends cleanly on the sting

## 4. Dialogue & captions
- [ ] 🤖 Every line has voice audio
- [ ] 🤖 Every line has captions, inside the safe area, ending before the video ends
- [ ] 🤖 Reading speed ≤ 22 chars/sec; caption chunks are short
- [ ] 🤖 No overlapping dialogue
- [ ] Captions match the spoken words exactly (TTS pronunciation overrides can drift)
- [ ] Lip-sync reads naturally (mouth moves only while that character speaks)
- [ ] 🤖⚠️ Final voices are recorded performances. Placeholder TTS is flagged as a warning.

## 5. Story & comedy
- [ ] Clear setup → escalation → button within ~45 s
- [ ] Each beat gets a laugh or moves the story
- [ ] Characters behave in voice (see `docs/CHARACTERS.md`)
- [ ] The ending lands. Ideally it is loopable or has a clear CTA.

## 6. Rights, safety & platform policy
- [ ] All characters, art, music and SFX are original. This pipeline generates them procedurally, so no third-party assets are used.
- [ ] Fonts are licensed for video use (Inter, SIL OFL, bundled with license)
- [ ] No resemblance to existing IP (characters, names, catchphrases)
- [ ] Content suits the intended audience. Decide the "made for kids" setting deliberately.
- [ ] YouTube "altered or synthetic content" disclosure reviewed (placeholder TTS voices)
- [ ] Title, description and tags reviewed in `youtube_metadata_DRAFT.json`

## 7. Approval gate (mandatory)
- [ ] Owner has watched the final MP4 end to end
- [ ] Owner has explicitly approved upload (set `"approved": true` in the metadata draft)
- [ ] **Upload is done manually by the owner.** The pipeline contains no upload code by design.
