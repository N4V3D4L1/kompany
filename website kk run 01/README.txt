╔══════════════════════════════════════════════════════════════╗
║          KÖMPANIE — Precision in Motion                      ║
║          Website Source — White Minimal Edition              ║
╚══════════════════════════════════════════════════════════════╝

HOW TO RUN
──────────
Open index.html directly in Chrome, Firefox, or Edge.
No build step. No server needed. No npm install.


FILE STRUCTURE
──────────────
index.html  — Complete HTML (67KB)
style.css   — Design system + all section styles (42KB)
script.js   — GSAP + Three.js animations (62KB)
README.txt  — This file


SECTIONS
────────
01  Hero           — Full-viewport with Three.js ambient objects
02  Philosophy     — Clip-path line wipes + column reveal
03  Products       — 4-card grid (Door Hardware, Windows, Fittings, Lighting)
04  Door Handles   — 4-scene cinematic story (NEW)
                     · Scene 1: Handle floats & auto-rotates on white stage
                     · Scene 2: Components explode apart (lever, rose, spindle, mechanism)
                     · Scene 3: Components reassemble
                     · Scene 4: 5-handle gallery (drag to explore)
05  Engineering    — Horizontal-scroll pin, animated counters
06  Signature      — Per-char ghost-to-solid KÖMPANIE reveal
07  Projects       — 4 editorial panels with parallax (Villas, Hotels, Commercial, Joinery)
08  Marquee        — Infinite ticker strip
09  Footer         — Dark, gold brand, 4-column links


REPLACING PLACEHOLDER IMAGES
─────────────────────────────
Project panels (Sections 07) use SVG architectural illustrations.
To swap in real photos, replace each <svg> block inside .proj-panel-img
with an <img> tag:

  <img src="your-photo.jpg" alt="..." 
       style="width:100%;height:100%;object-fit:cover;object-position:center;">

Do the same for product card SVGs (.pcard-svg) if desired.


DEPLOY (FREE)
─────────────
→ Netlify Drop: drag this folder to https://app.netlify.com/drop
→ GitHub Pages: push to repo → Settings → Pages → main / root
→ Vercel:       drag folder to https://vercel.com/new


LIBRARIES (CDN, auto-loaded)
─────────────────────────────
Lenis v1.0.42     — smooth scroll
GSAP 3.12         — animations + ScrollTrigger + ScrollToPlugin
Three.js r128     — 3D WebGL (bg canvas + door handles canvas)
Google Fonts      — Bebas Neue, DM Serif Display, Barlow, DM Mono


CREDITS
───────
Design & code: KÖMPANIE brand concept
Built with Claude (Anthropic) — April 2026
