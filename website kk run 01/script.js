/* ═══════════════════════════════════════════════════════════════
   KÖMPANIE — script.js
   Precision in Motion — White Minimal Edition

   FIX LOG:
   1. preSplitHeroTitle() runs SYNCHRONOUSLY before anything else
      → No font-of-unstyled / title drop. Chars start at translateY(110%)
      clipped by overflow:hidden. Invisible until GSAP reveals them.
   2. Lenis v1.0.42 correct API (no deprecated 'smooth', 'direction')
   3. Three.js objects are dark on transparent — barely visible on white
   4. GSAP initial states match CSS exactly — no position flash
   5. heroEntrance() called after loader exits (not before)
   6. ScrollTrigger.refresh() deferred to after fonts load
   7. Engineering horizontal scroll properly sized & pinned
   8. All animations degrade gracefully if library fails to load
═══════════════════════════════════════════════════════════════ */

'use strict';

/* ─────────────────────────────────────────────────────────────
   SAFETY: guard every library before use
───────────────────────────────────────────────────────────── */
const hasGSAP   = typeof gsap !== 'undefined';
const hasST     = hasGSAP && typeof ScrollTrigger !== 'undefined';
const hasLenis  = typeof Lenis !== 'undefined';
const hasTHREE  = typeof THREE !== 'undefined';

if (hasGSAP && hasST) {
  gsap.registerPlugin(ScrollTrigger, ScrollToPlugin);
}

/* ═══════════════════════════════════════════════════════════════
   STEP 0 — PRE-SPLIT HERO TITLE
   Must run SYNCHRONOUSLY at parse time (not in DOMContentLoaded)
   so the title chars are in the DOM before any paint occurs.
   Chars start at translateY(110%) via CSS .char rule —
   hidden by overflow:hidden on .hero-title.
═══════════════════════════════════════════════════════════════ */
function preSplitHeroTitle() {
  const titleEl = document.getElementById('hero-title');
  if (!titleEl) return;

  const raw = titleEl.textContent.trim();
  titleEl.innerHTML = '';
  titleEl.setAttribute('aria-label', raw);

  raw.split('').forEach(ch => {
    if (ch === ' ') {
      // Non-breaking space — preserves gap between words
      titleEl.appendChild(document.createTextNode('\u00a0'));
    } else {
      const span = document.createElement('span');
      span.className = 'char';
      span.textContent = ch;
      span.setAttribute('aria-hidden', 'true');
      titleEl.appendChild(span);
    }
  });
}

// Run immediately — before anything else
preSplitHeroTitle();

/* ═══════════════════════════════════════════════════════════════
   1. LOADER
   Fake progress bar 0→100 then slides up and triggers hero
═══════════════════════════════════════════════════════════════ */
function initLoader() {
  const loader  = document.getElementById('loader');
  const bar     = document.getElementById('loader-bar');
  const label   = document.getElementById('loader-label');

  if (!loader || !bar || !label) return;

  let progress = 0;

  // Non-linear increment — fast start, slows near 100
  const interval = setInterval(() => {
    const inc = progress < 60 ? 4 : progress < 85 ? 1.8 : 0.7;
    progress = Math.min(progress + inc, 100);

    bar.style.width    = progress + '%';
    label.textContent  = Math.round(progress) + '%';

    if (progress >= 100) {
      clearInterval(interval);
      setTimeout(exitLoader, 400);
    }
  }, 30);

  function exitLoader() {
    if (!hasGSAP) {
      // Fallback: CSS transition
      loader.style.transition = 'opacity 0.6s';
      loader.style.opacity    = '0';
      setTimeout(() => {
        loader.style.display = 'none';
        heroEntrance();
      }, 650);
      return;
    }

    gsap.timeline()
      .to(loader, {
        yPercent: -100,
        duration: 1.2,
        ease: 'power4.inOut',
        onComplete: () => {
          loader.style.display = 'none';
          heroEntrance();           // Trigger hero AFTER loader exits
        }
      });
  }
}

/* ═══════════════════════════════════════════════════════════════
   2. LENIS SMOOTH SCROLL
   v1.0.42 — correct constructor options (no deprecated keys)
═══════════════════════════════════════════════════════════════ */
function initLenis() {
  if (!hasLenis) {
    console.warn('KÖMPANIE: Lenis not loaded — using native scroll');
    return null;
  }

  const lenis = new Lenis({
    duration:        1.4,
    easing:          t => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
    smoothTouch:     false,
    touchMultiplier: 2.2,
  });

  // Sync Lenis RAF with GSAP ticker for perfect ScrollTrigger integration
  if (hasGSAP) {
    gsap.ticker.add(time => lenis.raf(time * 1000));
    gsap.ticker.lagSmoothing(0);
  } else {
    // Fallback RAF if no GSAP
    function raf(time) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    }
    requestAnimationFrame(raf);
  }

  window._lenis = lenis;
  return lenis;
}

/* ═══════════════════════════════════════════════════════════════
   3. THREE.JS — FLOATING 3D BACKGROUND
   Dark metallic objects on a transparent canvas.
   Canvas opacity is 0.07 in CSS — barely visible on white.
   Creates subtle depth without competing with content.
═══════════════════════════════════════════════════════════════ */
function initThreeJS() {
  if (!hasTHREE) return;

  const canvas   = document.getElementById('bg-canvas');
  if (!canvas) return;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(0x000000, 0);          // fully transparent bg

  const scene  = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 100);
  camera.position.set(0, 0, 8);

  /* ── Lighting — warm key + cool fill for brushed-metal look ── */
  const keyLight = new THREE.DirectionalLight(0x4a3c2a, 2.5);   // warm gold-brown key
  keyLight.position.set(5, 5, 5);
  scene.add(keyLight);

  const fillLight = new THREE.DirectionalLight(0x2a3040, 0.8);  // cool blue fill
  fillLight.position.set(-5, -3, 3);
  scene.add(fillLight);

  const ambientLight = new THREE.AmbientLight(0x1a1a1a, 1.5);   // dark ambient
  scene.add(ambientLight);

  /* ── Material — dark polished metal ── */
  const metalMat = new THREE.MeshStandardMaterial({
    color:     0x2a2520,           // very dark brown-charcoal
    metalness: 0.95,
    roughness: 0.25,
  });

  const wireMat = new THREE.MeshStandardMaterial({
    color:     0x3a3530,
    metalness: 0.85,
    roughness: 0.4,
    wireframe: true,
  });

  /* ── Create objects ── */
  const objects = [];

  function addObject(geometry, material, x, y, z, scale = 1) {
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(x, y, z);
    mesh.scale.setScalar(scale);
    mesh.rotation.set(
      Math.random() * Math.PI,
      Math.random() * Math.PI,
      Math.random() * Math.PI
    );
    scene.add(mesh);
    objects.push({
      mesh,
      rotX:        (Math.random() - 0.5) * 0.0025,
      rotY:        (Math.random() - 0.5) * 0.0035,
      rotZ:        (Math.random() - 0.5) * 0.0018,
      floatSpeed:  0.3 + Math.random() * 0.4,
      floatAmp:    0.06 + Math.random() * 0.10,
      floatOffset: Math.random() * Math.PI * 2,
      baseY:       y,
    });
    return mesh;
  }

  // Torus — abstracted hinge / ring
  addObject(new THREE.TorusGeometry(1.2, 0.04, 32, 128),         metalMat,  3.5,  1.2, -2,   1.0);
  // TorusKnot — precision mechanism
  addObject(new THREE.TorusKnotGeometry(0.5, 0.07, 120, 16, 2, 3), metalMat, -3.5, -0.5, -3, 0.8);
  // Large wireframe torus — background
  addObject(new THREE.TorusGeometry(1.8, 0.02, 16, 120),         wireMat,  -2.0,  2.0, -5,   1.0);
  // Icosahedron — geometric precision
  addObject(new THREE.IcosahedronGeometry(0.5, 0),               metalMat,  0.8, -2.5, -2,   1.0);
  // Thin cylinders — abstracted profile / bar
  addObject(new THREE.CylinderGeometry(0.02, 0.02, 3.5, 8),      metalMat,  2.0, -1.0, -1.5, 1.0);
  addObject(new THREE.CylinderGeometry(0.02, 0.02, 2.5, 8),      metalMat, -1.5,  1.5, -2.5, 1.0);
  // Octahedron — angular precision
  addObject(new THREE.OctahedronGeometry(0.4, 0),                wireMat,  -4.0, -2.5, -4,   1.0);
  // Small torus — hinge detail
  addObject(new THREE.TorusGeometry(0.35, 0.06, 16, 64),         metalMat,  4.5, -2.0, -3,   1.0);

  /* ── Scroll-driven parallax ── */
  let scrollProg = 0;
  if (hasST) {
    ScrollTrigger.create({
      trigger: 'body',
      start: 'top top',
      end: 'bottom bottom',
      onUpdate: s => { scrollProg = s.progress; }
    });
  }

  /* ── Render loop ── */
  const clock = new THREE.Clock();
  let   animId;

  function animate() {
    animId = requestAnimationFrame(animate);
    const t = clock.getElapsedTime();

    objects.forEach(obj => {
      obj.mesh.rotation.x += obj.rotX;
      obj.mesh.rotation.y += obj.rotY;
      obj.mesh.rotation.z += obj.rotZ;
      // Gentle sine float
      obj.mesh.position.y = obj.baseY
        + Math.sin(t * obj.floatSpeed + obj.floatOffset) * obj.floatAmp
        - scrollProg * 1.5;        // subtle upward drift on scroll
    });

    camera.position.y = Math.sin(t * 0.18) * 0.06;
    renderer.render(scene, camera);
  }

  animate();

  /* ── Responsive ── */
  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });
}

/* ═══════════════════════════════════════════════════════════════
   4. CUSTOM CURSOR
   Dot snaps, ring lerps with lag. Hidden on touch devices.
═══════════════════════════════════════════════════════════════ */
function initCursor() {
  const cursorEl = document.getElementById('cursor');
  if (!cursorEl) return;

  // Hide on touch devices
  if ('ontouchstart' in window || navigator.maxTouchPoints > 0) {
    cursorEl.style.display = 'none';
    document.body.style.cursor = 'auto';
    return;
  }

  const dot  = cursorEl.querySelector('.cursor-dot');
  const ring = cursorEl.querySelector('.cursor-ring');

  let mx = -100, my = -100;   // start offscreen
  let rx = -100, ry = -100;

  window.addEventListener('mousemove', e => {
    mx = e.clientX;
    my = e.clientY;
    if (hasGSAP) gsap.set(dot, { x: mx, y: my });
    else {
      dot.style.transform = `translate(${mx}px, ${my}px) translate(-50%,-50%)`;
    }
  });

  // Ring lerps behind dot
  if (hasGSAP) {
    gsap.ticker.add(() => {
      rx += (mx - rx) * 0.11;
      ry += (my - ry) * 0.11;
      gsap.set(ring, { x: rx, y: ry });
    });
  }
}

/* ═══════════════════════════════════════════════════════════════
   5. NAVIGATION
   Compact on scroll + smooth anchor links via Lenis
═══════════════════════════════════════════════════════════════ */
function initNav() {
  if (!hasST) return;

  const nav = document.getElementById('nav');
  if (!nav) return;

  ScrollTrigger.create({
    start:       'top -80px',
    onEnter:     () => nav.classList.add('scrolled'),
    onLeaveBack: () => nav.classList.remove('scrolled'),
  });

  // Smooth anchor scrolling
  document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', e => {
      const href   = link.getAttribute('href');
      const target = document.querySelector(href);
      if (!target) return;
      e.preventDefault();
      if (window._lenis) {
        window._lenis.scrollTo(target, { offset: -80, duration: 1.6 });
      } else {
        target.scrollIntoView({ behavior: 'smooth' });
      }
    });
  });
}

/* ═══════════════════════════════════════════════════════════════
   6a. HERO ENTRANCE
   Runs AFTER loader exits. Chars were pre-split at parse time.
   Animates: chars ↑, eyebrow fade, tagline, body, CTAs, scroll-cue, shapes.
═══════════════════════════════════════════════════════════════ */
function heroEntrance() {
  if (!hasGSAP) {
    // Simple CSS fallback
    document.querySelectorAll('.char').forEach((c, i) => {
      c.style.transition   = `transform 0.8s ${i * 0.04}s cubic-bezier(0.16,1,0.3,1)`;
      c.style.transform    = 'translateY(0)';
    });
    ['.hero-eyebrow','#hero-tagline','#hero-body','#hero-ctas','#scroll-cue'].forEach(sel => {
      const el = document.querySelector(sel);
      if (el) { el.style.transition = 'opacity 0.9s, transform 0.9s'; el.style.opacity = '1'; el.style.transform = 'none'; }
    });
    return;
  }

  const chars = document.querySelectorAll('.hero-title .char');
  const tl    = gsap.timeline({ defaults: { ease: 'power4.out' } });

  /* ── 1. Chars reveal upward from behind overflow clip ── */
  tl.to(chars, {
    y:        0,
    duration: 1.1,
    stagger:  0.038,
  })

  /* ── 2. Eyebrow (already opacity:0 in CSS) ── */
  .to('.hero-eyebrow', {
    opacity:  1,
    duration: 0.9,
    ease:     'power3.out',
  }, '-=0.65')

  /* ── 3. Tagline (opacity:0, y:20px in CSS) ── */
  .to('#hero-tagline', {
    opacity:  1,
    y:        0,
    duration: 0.9,
  }, '-=0.65')

  /* ── 4. Body copy ── */
  .to('#hero-body', {
    opacity:  1,
    y:        0,
    duration: 0.8,
  }, '-=0.55')

  /* ── 5. CTAs ── */
  .to('#hero-ctas', {
    opacity:  1,
    y:        0,
    duration: 0.7,
  }, '-=0.45')

  /* ── 6. Scroll cue ── */
  .to('#scroll-cue', {
    opacity:  1,
    duration: 0.8,
    ease:     'power2.out',
  }, '-=0.3')

  /* ── 7. Hero shapes fade in at staggered opacities ── */
  .to('.hshape', {
    opacity:  (i) => [0.18, 0.14, 0.12, 0.08, 0.16, 0.07][i % 6],
    stagger:  0.1,
    duration: 1.4,
    ease:     'power2.out',
  }, '-=1.2');
}

/* ═══════════════════════════════════════════════════════════════
   6b. HERO SHAPES — mouse parallax depth
═══════════════════════════════════════════════════════════════ */
function initHeroParallax() {
  if (!hasGSAP) return;
  const shapes = document.querySelectorAll('.hshape[data-parallax]');

  window.addEventListener('mousemove', e => {
    const cx = (e.clientX / window.innerWidth  - 0.5) * 2;
    const cy = (e.clientY / window.innerHeight - 0.5) * 2;

    shapes.forEach(shape => {
      const depth = parseFloat(shape.dataset.parallax) || 0.2;
      gsap.to(shape, {
        x:        cx * depth * 35,
        y:        cy * depth * 25,
        duration: 2.2,
        ease:     'power2.out',
      });
    });
  });
}

/* ═══════════════════════════════════════════════════════════════
   6c. PHILOSOPHY SECTION
   Clip-path line wipes + staggered column reveal
═══════════════════════════════════════════════════════════════ */
function initPhilosophy() {
  if (!hasST) return;

  const lines = document.querySelectorAll('.phil-line');
  const cols  = document.querySelectorAll('.phil-col');
  const ring  = document.getElementById('phil-ring');

  /* Line wipe: clip-path from right → fully revealed */
  lines.forEach((line, i) => {
    gsap.to(line, {
      clipPath:  'inset(0 0% 0 0)',
      duration:  1.2,
      ease:      'power4.out',
      delay:     i * 0.14,
      scrollTrigger: {
        trigger:     line,
        start:       'top 88%',
        toggleActions: 'play none none none',
      }
    });
  });

  /* Column stagger rise */
  gsap.to(cols, {
    opacity:  1,
    y:        0,
    stagger:  0.18,
    duration: 1.1,
    ease:     'power3.out',
    scrollTrigger: {
      trigger:     '.phil-cols',
      start:       'top 80%',
      toggleActions: 'play none none none',
    }
  });

  /* Ring parallax drift */
  if (ring) {
    gsap.to(ring, {
      y:    -130,
      ease: 'none',
      scrollTrigger: {
        trigger: '#philosophy',
        start:   'top bottom',
        end:     'bottom top',
        scrub:   1.5,
      }
    });
  }
}

/* ═══════════════════════════════════════════════════════════════
   6d. PRODUCTS CARDS — staggered reveal from bottom
═══════════════════════════════════════════════════════════════ */
function initProducts() {
  if (!hasST) return;

  gsap.to('.pcard', {
    opacity:  1,
    y:        0,
    stagger:  0.14,
    duration: 1.0,
    ease:     'power3.out',
    scrollTrigger: {
      trigger:     '.products-grid',
      start:       'top 80%',
      toggleActions: 'play none none none',
    }
  });
}

/* ═══════════════════════════════════════════════════════════════
   6e. ENGINEERING — HORIZONTAL SCROLL PIN
   Pins the section and translates the track left on scroll.
   Height of section = viewport width + track overflow.
═══════════════════════════════════════════════════════════════ */
function initEngineering() {
  if (!hasST) return;

  const section  = document.getElementById('engineering');
  const track    = document.getElementById('eng-track');
  const fill     = document.getElementById('eng-progress-fill');

  if (!section || !track) return;

  /* Total horizontal distance to scroll */
  function scrollDist() {
    return Math.max(0, track.scrollWidth - window.innerWidth);
  }

  /* Section height = viewport height + scroll distance
     This creates the "virtual" vertical scroll space for the pin */
  function updateHeight() {
    section.style.height = (window.innerHeight + scrollDist()) + 'px';
  }

  updateHeight();

  /* Create pin + scrub */
  const st = ScrollTrigger.create({
    trigger:      section,
    start:        'top top',
    end:          () => '+=' + scrollDist(),
    pin:          '.eng-sticky',
    anticipatePin: 1,
    scrub:        1.0,
    onUpdate:     self => {
      gsap.set(track, { x: -(self.progress * scrollDist()) });
      if (fill) fill.style.width = (self.progress * 100) + '%';
    }
  });

  /* Counter animation — runs when stat numbers scroll into view */
  document.querySelectorAll('.eng-stat-num').forEach(el => {
    const target    = parseFloat(el.dataset.target);
    const isDecimal = target < 1;
    const isBig     = target >= 1000;

    ScrollTrigger.create({
      trigger: el,
      start:   'top 90%',
      once:    true,
      onEnter: () => {
        gsap.to({ val: 0 }, {
          val:      target,
          duration: 2.2,
          ease:     'power2.out',
          onUpdate: function () {
            const v = this.targets()[0].val;
            el.textContent = isDecimal
              ? v.toFixed(3)
              : isBig
                ? Math.round(v).toLocaleString()
                : Math.round(v);
          }
        });
      }
    });
  });

  window.addEventListener('resize', () => {
    updateHeight();
    if (st) st.refresh();
  });
}

/* ═══════════════════════════════════════════════════════════════
   6f. SIGNATURE TYPOGRAPHY
   Per-char scroll-driven reveal — ghost outline → solid stroke
═══════════════════════════════════════════════════════════════ */
function initSignature() {
  if (!hasST) return;

  const brandEl   = document.getElementById('sig-brand');
  const taglineEl = document.getElementById('sig-tagline');
  const subEl     = document.getElementById('sig-sub');
  const lineEl    = document.getElementById('sig-line');

  if (!brandEl) return;

  /* Split brand text into per-char spans */
  const rawText = brandEl.textContent.trim();
  brandEl.innerHTML = '';
  brandEl.setAttribute('aria-label', rawText);

  rawText.split('').forEach(ch => {
    if (ch === ' ') {
      brandEl.appendChild(document.createTextNode('\u00a0'));
    } else {
      const span       = document.createElement('span');
      span.className   = 'sig-char';
      span.textContent = ch;
      span.setAttribute('aria-hidden', 'true');
      brandEl.appendChild(span);
    }
  });

  const chars = brandEl.querySelectorAll('.sig-char');

  /* Scrub: as you scroll, chars shift from pale outline → dark stroke */
  gsap.timeline({
    scrollTrigger: {
      trigger: '#signature',
      start:   'top 75%',
      end:     'center 30%',
      scrub:   1.2,
    }
  })
  .to(chars, {
    '-webkit-text-stroke': '1.5px rgba(0, 0, 0, 0.80)',
    color:   'transparent',
    stagger: 0.05,
    ease:    'power2.out',
  });

  /* Tagline slide up */
  if (taglineEl) {
    gsap.to(taglineEl, {
      y:        0,
      duration: 1.3,
      ease:     'power4.out',
      scrollTrigger: {
        trigger:     '.sig-tagline-wrap',
        start:       'top 82%',
        toggleActions: 'play none none none',
      }
    });
  }

  /* Sub fade in */
  if (subEl) {
    gsap.to(subEl, {
      opacity:  1,
      y:        0,
      duration: 1.0,
      ease:     'power3.out',
      scrollTrigger: {
        trigger:     subEl,
        start:       'top 88%',
        toggleActions: 'play none none none',
      }
    });
  }

  /* Accent line expand */
  if (lineEl) {
    gsap.to(lineEl, {
      width:    '200px',
      duration: 1.6,
      ease:     'power4.out',
      scrollTrigger: {
        trigger:     '#signature',
        start:       'center 60%',
        toggleActions: 'play none none none',
      }
    });
  }
}

/* ═══════════════════════════════════════════════════════════════
   6g. PROJECTS — parallax image panels + text reveals
═══════════════════════════════════════════════════════════════ */
function initProjects() {
  if (!hasST) return;

  /* Parallax: image moves slower than scroll — depth effect */
  document.querySelectorAll('.proj-panel-img').forEach(img => {
    gsap.fromTo(img,
      { y: '-8%' },
      {
        y:    '8%',
        ease: 'none',
        scrollTrigger: {
          trigger: img.closest('.proj-panel'),
          start:   'top bottom',
          end:     'bottom top',
          scrub:   1.5,
        }
      }
    );
  });

  /* Panel info text stagger in */
  document.querySelectorAll('.proj-panel-info').forEach(info => {
    const kids = Array.from(info.children);
    gsap.fromTo(kids,
      { opacity: 0, y: 28 },
      {
        opacity:  1,
        y:        0,
        stagger:  0.12,
        duration: 1.0,
        ease:     'power3.out',
        scrollTrigger: {
          trigger:     info,
          start:       'top 78%',
          toggleActions: 'play none none none',
        }
      }
    );
  });
}

/* ═══════════════════════════════════════════════════════════════
   6h. FOOTER FADE IN — dark footer fades/rises into view
═══════════════════════════════════════════════════════════════ */
function initFooter() {
  if (!hasST) return;

  gsap.to('#contact', {
    opacity:  1,
    y:        0,
    duration: 1.3,
    ease:     'power3.out',
    scrollTrigger: {
      trigger:     '#contact',
      start:       'top 88%',
      toggleActions: 'play none none none',
    }
  });
}

/* ═══════════════════════════════════════════════════════════════
   6i. SECTION LABELS — slide in from left
═══════════════════════════════════════════════════════════════ */
function initSectionLabels() {
  if (!hasST) return;

  document.querySelectorAll('.section-label').forEach(label => {
    gsap.fromTo(label,
      { opacity: 0, x: -24 },
      {
        opacity:  1,
        x:        0,
        duration: 0.9,
        ease:     'power3.out',
        scrollTrigger: {
          trigger:     label,
          start:       'top 90%',
          toggleActions: 'play none none none',
        }
      }
    );
  });
}

/* ═══════════════════════════════════════════════════════════════
   6j. SECTION TITLES — opacity + y rise
═══════════════════════════════════════════════════════════════ */
function initSectionTitles() {
  if (!hasST) return;

  const titleSels = '.products-title, .projects-title';

  document.querySelectorAll(titleSels).forEach(title => {
    gsap.fromTo(title,
      { opacity: 0, y: 45 },
      {
        opacity:  1,
        y:        0,
        duration: 1.1,
        ease:     'power4.out',
        scrollTrigger: {
          trigger:     title,
          start:       'top 87%',
          toggleActions: 'play none none none',
        }
      }
    );
  });
}

/* ═══════════════════════════════════════════════════════════════
   6½. DOOR HANDLES — CINEMATIC SCROLL STORY
   ─────────────────────────────────────────────────────────────
   Architecture:
   • #dh-canvas  — dedicated WebGL renderer (separate from bg-canvas)
   • 4 groups    — leverGroup, roseGroup, spindleGroup, mechGroup
   • All groups start at pos(0,0,0). Explosion = animating groups
     toward EXPLODED targets; reassembly = returning to origin.
   • ScrollTrigger drives dhProgress (0→1) which maps to:
       0.00–0.22  Scene 1  floating auto-rotation
       0.22–0.48  Scene 2  explosion (explodeT 0→1)
       0.48–0.70  Scene 3  reassembly (explodeT 1→0)
       0.70–1.00  Scene 4  gallery
   • Mouse → keyLight position (smooth lerp) → live specular shift
   • IntersectionObserver pauses render when section off-screen
═══════════════════════════════════════════════════════════════ */
function initDoorHandles() {
  if (!hasTHREE || !hasST) return;

  const section = document.getElementById('door-handles');
  if (!section) return;

  /* ── Section needs 5× viewport height of scroll space ── */
  const setHeight = () => { section.style.height = (window.innerHeight * 5) + 'px'; };
  setHeight();
  window.addEventListener('resize', setHeight);

  /* ─────────────────────────────────────────────────────────
     THREE.JS RENDERER
  ───────────────────────────────────────────────────────── */
  const canvas   = document.getElementById('dh-canvas');
  if (!canvas) return;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(0x000000, 0);      // transparent — white page shows through

  const scene  = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(44, window.innerWidth / window.innerHeight, 0.1, 50);
  camera.position.set(0, 0, 6.8);

  /* ─────────────────────────────────────────────────────────
     LIGHTING
     Four-light rig. keyLight follows mouse for live specular.
  ───────────────────────────────────────────────────────── */
  const ambLight  = new THREE.AmbientLight(0xffffff, 0.55);
  scene.add(ambLight);

  // Warm key — main specular highlight, follows mouse
  const keyLight  = new THREE.DirectionalLight(0xfff6e8, 4.0);
  keyLight.position.set(3, 3.5, 4);
  scene.add(keyLight);

  // Cool fill — prevents shadow side going jet black on white bg
  const fillLight = new THREE.DirectionalLight(0xd8e8ff, 1.4);
  fillLight.position.set(-4, -2, 2);
  scene.add(fillLight);

  // Rim light — from behind, separates handle from white background
  const rimLight  = new THREE.DirectionalLight(0xffffff, 2.2);
  rimLight.position.set(0, 1, -5);
  scene.add(rimLight);

  // Accent bounce — warm low-angle (mimics ground bounce on polished metal)
  const bounceLight = new THREE.DirectionalLight(0xffe4b0, 0.9);
  bounceLight.position.set(0, -4, 1);
  scene.add(bounceLight);

  /* ── Mouse → key light tracking ── */
  let targetLX = 3, targetLY = 3.5;
  let currentLX = 3, currentLY = 3.5;

  const onDHMouse = (e) => {
    targetLX = ((e.clientX / window.innerWidth)  * 2 - 1) * 7;
    targetLY = (-(e.clientY / window.innerHeight) * 2 + 1) * 5;
  };
  window.addEventListener('mousemove', onDHMouse);

  /* ─────────────────────────────────────────────────────────
     MATERIALS
     MeshPhysicalMaterial — clearcoat gives lacquered-metal look
     even without an env map (clearcoat responds to direct lights).
  ───────────────────────────────────────────────────────── */
  const matSteel = new THREE.MeshPhysicalMaterial({
    color: 0x8a8278, metalness: 0.92, roughness: 0.16,
    clearcoat: 0.55, clearcoatRoughness: 0.08,
  });
  const matBrass = new THREE.MeshPhysicalMaterial({
    color: 0xb89b72, metalness: 0.90, roughness: 0.20,
    clearcoat: 0.40, clearcoatRoughness: 0.12,
  });
  const matDark = new THREE.MeshPhysicalMaterial({
    color: 0x2c2420, metalness: 0.85, roughness: 0.28,
    clearcoat: 0.20, clearcoatRoughness: 0.18,
  });
  const matSpring = new THREE.MeshStandardMaterial({
    color: 0x3c3a42, metalness: 0.88, roughness: 0.32,
  });

  /* ─────────────────────────────────────────────────────────
     HANDLE GEOMETRY
     L-shaped lever:  horizontal grip + vertical neck + rose disc
     All child geometry positioned WITHIN each group so that
     groups at pos(0,0,0) = assembled state.
  ───────────────────────────────────────────────────────── */

  /* ── leverGroup — grip bar + neck + caps + grip texture bands ── */
  const leverGroup = new THREE.Group();

  // Horizontal grip bar
  const gripGeo = new THREE.CylinderGeometry(0.057, 0.057, 2.10, 64, 1);
  const grip    = new THREE.Mesh(gripGeo, matSteel);
  grip.rotation.z = Math.PI / 2;
  grip.position.set(0.55, 1.05, 0);
  leverGroup.add(grip);

  // Left end cap (at neck junction)
  const capSphere = new THREE.SphereGeometry(0.059, 32, 32);
  const capL = new THREE.Mesh(capSphere, matSteel);
  capL.position.set(-0.50, 1.05, 0);
  leverGroup.add(capL);

  // Right end cap
  const capR = new THREE.Mesh(new THREE.SphereGeometry(0.059, 32, 32), matSteel);
  capR.position.set(1.60, 1.05, 0);
  leverGroup.add(capR);

  // Vertical neck
  const neckGeo = new THREE.CylinderGeometry(0.057, 0.057, 0.82, 64, 1);
  const neck    = new THREE.Mesh(neckGeo, matSteel);
  neck.position.set(-0.50, 0.625, 0);
  leverGroup.add(neck);

  // Junction sphere — smooths the 90° L-bend
  const junc = new THREE.Mesh(new THREE.SphereGeometry(0.068, 32, 32), matSteel);
  junc.position.set(-0.50, 1.05, 0);
  leverGroup.add(junc);

  // Grip texture rings (subtle ridges along the grip zone)
  for (let i = 0; i < 5; i++) {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(0.059, 0.007, 8, 32),
      matSteel
    );
    ring.rotation.z = Math.PI / 2;
    ring.position.set(0.22 + i * 0.22, 1.05, 0);
    leverGroup.add(ring);
  }

  /* ── roseGroup — escutcheon disc + decorative ring + boss ── */
  const roseGroup = new THREE.Group();

  // Main disc (CylinderGeometry as flat disc, rotated to face camera)
  const roseDisc = new THREE.Mesh(
    new THREE.CylinderGeometry(0.41, 0.41, 0.10, 128, 1),
    matBrass
  );
  roseDisc.rotation.x = Math.PI / 2;
  roseDisc.position.set(-0.50, 0.20, 0);
  roseGroup.add(roseDisc);

  // Decorative inner ring
  const innerRing = new THREE.Mesh(
    new THREE.TorusGeometry(0.275, 0.019, 16, 80),
    matBrass
  );
  innerRing.position.set(-0.50, 0.20, 0.058);
  roseGroup.add(innerRing);

  // Center boss
  const boss = new THREE.Mesh(
    new THREE.CylinderGeometry(0.066, 0.066, 0.14, 32, 1),
    matBrass
  );
  boss.rotation.x = Math.PI / 2;
  boss.position.set(-0.50, 0.20, 0.062);
  roseGroup.add(boss);

  /* ── spindleGroup — square-section spindle bar + brass clip ── */
  const spindleGroup = new THREE.Group();

  const spindleBar = new THREE.Mesh(
    new THREE.BoxGeometry(0.086, 0.086, 1.42),
    matDark
  );
  spindleBar.position.set(-0.50, 0.20, 0);
  spindleGroup.add(spindleBar);

  // Retention clip at front end
  const clip = new THREE.Mesh(
    new THREE.BoxGeometry(0.18, 0.055, 0.055),
    matBrass
  );
  clip.position.set(-0.50, 0.20, 0.74);
  spindleGroup.add(clip);

  /* ── mechGroup — spring housing box + stacked coils ── */
  const mechGroup = new THREE.Group();

  const housing = new THREE.Mesh(
    new THREE.BoxGeometry(0.52, 0.52, 0.27),
    matDark
  );
  housing.position.set(-0.50, 0.20, -0.62);
  mechGroup.add(housing);

  // Spring coils stacked inside housing
  for (let i = 0; i < 7; i++) {
    const coil = new THREE.Mesh(
      new THREE.TorusGeometry(0.114, 0.015, 8, 24),
      matSpring
    );
    coil.rotation.x = Math.PI / 2;
    coil.position.set(-0.50, -0.10 + i * 0.033 + 0.20, -0.62);
    mechGroup.add(coil);
  }

  /* ── Assemble master group ── */
  const handleGroup = new THREE.Group();
  handleGroup.add(leverGroup, roseGroup, spindleGroup, mechGroup);
  handleGroup.scale.setScalar(1.18);
  handleGroup.position.set(0.22, -0.28, 0);   // visually centre in frame
  scene.add(handleGroup);

  /* ─────────────────────────────────────────────────────────
     EXPLODED TARGET POSITIONS
     When explodeT = 1, each group moves to its exploded pos/rot.
     When explodeT = 0, groups are at (0,0,0) = assembled.
  ───────────────────────────────────────────────────────── */
  const EXPLODED = {
    lever:    { x:  1.8, y:  1.4, z:  0.7,  rx: 0,     ry: 0.26,  rz: 0.20  },
    rose:     { x:  0.1, y:  0.1, z:  1.05, rx: 0,     ry: 0.32,  rz: 0     },
    spindle:  { x: -0.3, y: -1.9, z:  0.3,  rx: 0.14,  ry: 0,     rz: 0.16  },
    mechanism:{ x: -1.9, y: -0.5, z: -0.75, rx:-0.18,  ry:-0.26,  rz: 0     },
  };

  /* ── Smooth ease ── */
  function eioC(t) {   // cubic ease-in-out
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  }

  /* ── Linear range map, clamped ── */
  function rmap(iMin, iMax, oMin, oMax, v) {
    const t = Math.max(0, Math.min(1, (v - iMin) / (iMax - iMin)));
    return oMin + t * (oMax - oMin);
  }

  /* ── Apply one group's explosion state ── */
  function applyExplosion(group, target, rawT) {
    const t = eioC(rawT);
    group.position.set(t * target.x, t * target.y, t * target.z);
    group.rotation.set(t * target.rx, t * target.ry, t * target.rz);
  }

  /* ─────────────────────────────────────────────────────────
     SCROLL STATE
  ───────────────────────────────────────────────────────── */
  let dhProg      = 0;       // 0→1 overall section progress
  let explodeT    = 0;       // 0=assembled, 1=fully exploded
  let cardsShown  = false;

  /* ── Scene overlay opacity controller ── */
  function updateOverlays(p) {
    const s1 = p < 0.18 ? 1 : rmap(0.18, 0.23, 1, 0, p);
    const s2 = p < 0.22 ? 0 : p < 0.27 ? rmap(0.22, 0.27, 0, 1, p)
                             : p < 0.48 ? 1
                             : rmap(0.48, 0.53, 1, 0, p);
    const s3 = p < 0.52 ? 0 : p < 0.57 ? rmap(0.52, 0.57, 0, 1, p)
                             : p < 0.70 ? 1
                             : rmap(0.70, 0.75, 1, 0, p);
    const s4 = p < 0.74 ? 0 : rmap(0.74, 0.79, 0, 1, p);

    const o1 = document.getElementById('dh-overlay-1');
    const o2 = document.getElementById('dh-overlay-2');
    const o3 = document.getElementById('dh-overlay-3');
    const o4 = document.getElementById('dh-overlay-4');

    if (o1) o1.style.opacity = Math.max(0, Math.min(1, s1));
    if (o2) o2.style.opacity = Math.max(0, Math.min(1, s2));
    if (o3) o3.style.opacity = Math.max(0, Math.min(1, s3));
    if (o4) {
      const clamped = Math.max(0, Math.min(1, s4));
      o4.style.opacity      = clamped;
      o4.style.pointerEvents = clamped > 0.5 ? 'auto' : 'none';
    }

    // Fade canvas when gallery fully dominates
    canvas.style.opacity = p > 0.86 ? rmap(0.86, 0.96, 1, 0, p) : 1;

    // Scene nav pips
    const activeIdx = p < 0.23 ? 0 : p < 0.52 ? 1 : p < 0.74 ? 2 : 3;
    document.querySelectorAll('.dh-nav-pip').forEach((pip, i) => {
      pip.classList.toggle('active', i === activeIdx);
    });

    // Stagger gallery cards in on first appearance
    if (s4 > 0.35 && !cardsShown && hasGSAP) {
      cardsShown = true;
      gsap.to('.dh-hcard', {
        opacity: 1, y: 0,
        stagger: 0.09, duration: 0.75, ease: 'power3.out',
      });
    }
  }

  /* ─────────────────────────────────────────────────────────
     SCROLLTRIGGER — drives everything
  ───────────────────────────────────────────────────────── */
  ScrollTrigger.create({
    trigger: section,
    start:   'top top',
    end:     'bottom bottom',
    scrub:   1.0,
    onUpdate: self => {
      dhProg = self.progress;

      // Explosion progress: 0→1 from 0.22→0.48, 1→0 from 0.48→0.70
      if      (dhProg < 0.22) explodeT = 0;
      else if (dhProg < 0.48) explodeT = rmap(0.22, 0.48, 0, 1, dhProg);
      else if (dhProg < 0.70) explodeT = rmap(0.48, 0.70, 1, 0, dhProg);
      else                    explodeT = 0;

      updateOverlays(dhProg);
    },
  });

  /* ─────────────────────────────────────────────────────────
     RENDER LOOP
  ───────────────────────────────────────────────────────── */
  const clock  = new THREE.Clock();
  let visible  = false;

  // Pause render when section off-screen
  const obs = new IntersectionObserver(
    entries => { visible = entries[0].isIntersecting; },
    { threshold: 0.01 }
  );
  obs.observe(section);

  (function animate() {
    requestAnimationFrame(animate);
    if (!visible) return;

    const t = clock.getElapsedTime();

    /* Smooth key light chases mouse → live specular */
    currentLX += (targetLX - currentLX) * 0.055;
    currentLY += (targetLY - currentLY) * 0.055;
    keyLight.position.set(currentLX, currentLY, 4.5);

    /* Scene 1: gentle auto-rotation + sine float */
    if (dhProg < 0.22) {
      handleGroup.rotation.y += 0.003;
      handleGroup.position.y  = -0.28 + Math.sin(t * 0.62) * 0.065;
    }

    /* Scenes 2 & 3: apply explosion / reassembly to each group */
    applyExplosion(leverGroup,   EXPLODED.lever,     explodeT);
    applyExplosion(roseGroup,    EXPLODED.rose,       explodeT);
    applyExplosion(spindleGroup, EXPLODED.spindle,    explodeT);
    applyExplosion(mechGroup,    EXPLODED.mechanism,  explodeT);

    /* Very subtle camera breathing */
    camera.position.y = Math.sin(t * 0.22) * 0.028;

    renderer.render(scene, camera);
  })();

  /* ── Resize ── */
  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    setHeight();
  });

  /* ── Gallery drag ── */
  initDHGallery();
}

/* ─────────────────────────────────────────────────────────────
   GALLERY DRAG — pointer-based drag with momentum glide
   Works inside the pinned sticky container (no native scroll).
───────────────────────────────────────────────────────────── */
function initDHGallery() {
  const track = document.getElementById('dh-gallery-track');
  if (!track) return;

  let isDown   = false;
  let startX   = 0;
  let curX     = 0;
  let velX     = 0;
  let lastX    = 0;
  let rafId;

  const maxDrag = () => -(track.scrollWidth - track.parentElement.offsetWidth + 60);

  track.addEventListener('pointerdown', e => {
    isDown = true;
    startX = e.clientX - curX;
    lastX  = e.clientX;
    velX   = 0;
    track.setPointerCapture(e.pointerId);
    cancelAnimationFrame(rafId);
  });

  track.addEventListener('pointermove', e => {
    if (!isDown) return;
    velX = e.clientX - lastX;
    lastX = e.clientX;
    curX  = Math.max(maxDrag(), Math.min(0, e.clientX - startX));
    track.style.transform = `translateX(${curX}px)`;
  });

  const endDrag = () => {
    if (!isDown) return;
    isDown = false;

    // Momentum glide
    const glide = () => {
      velX *= 0.92;
      curX  = Math.max(maxDrag(), Math.min(0, curX + velX));
      track.style.transform = `translateX(${curX}px)`;
      if (Math.abs(velX) > 0.25) rafId = requestAnimationFrame(glide);
    };
    rafId = requestAnimationFrame(glide);
  };

  track.addEventListener('pointerup',     endDrag);
  track.addEventListener('pointercancel', endDrag);
  // Prevent page scroll while dragging
  track.addEventListener('touchmove', e => e.preventDefault(), { passive: false });
}

/* ═══════════════════════════════════════════════════════════════
   6f. DOOR HANDLES — CINEMATIC SCROLL STORY
   4 scenes driven by ScrollTrigger scrub:
   S1: Handle floats & auto-rotates
   S2: Components explode outward (leverGroup, roseGroup, spindleGroup, mechGroup)
   S3: Components reassemble
   S4: Gallery fades in, 3D canvas fades out
   Mouse position → live key-light movement → metallic specular shift
═══════════════════════════════════════════════════════════════ */
function initDoorHandles() {
  if (!hasTHREE || !hasST) return;

  const section = document.getElementById('door-handles');
  if (!section) return;

  /* ── Section height: 5 × viewport = scroll budget for all 4 scenes ── */
  const setH = () => { section.style.height = (window.innerHeight * 5) + 'px'; };
  setH();
  window.addEventListener('resize', setH);

  /* ── Dedicated WebGL renderer ── */
  const canvas = document.getElementById('dh-canvas');
  if (!canvas) return;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(0x000000, 0);

  const scene  = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(44, window.innerWidth / window.innerHeight, 0.1, 50);
  camera.position.set(0, 0, 6.5);

  /* ── Lighting ── */
  // Ambient — low, so metalness & clearcoat show through
  scene.add(new THREE.AmbientLight(0xffffff, 0.35));

  // Key light — warm, follows mouse in real time → live metallic reflection
  const keyLight = new THREE.DirectionalLight(0xfff6e8, 4.0);
  keyLight.position.set(3, 3, 4);
  scene.add(keyLight);

  // Cool fill — from lower-left for depth
  const fillLight = new THREE.DirectionalLight(0xc8dff8, 1.0);
  fillLight.position.set(-4, -2, 2);
  scene.add(fillLight);

  // Rim — from behind, separates handle edge from white background
  const rimLight = new THREE.DirectionalLight(0xffffff, 2.2);
  rimLight.position.set(0, 1, -6);
  scene.add(rimLight);

  /* ── Mouse → key light (smooth lerp so it glides, not snaps) ── */
  let targetLX = 3, targetLY = 3, curLX = 3, curLY = 3;
  const dhMouse = (e) => {
    const nx = (e.clientX / window.innerWidth)  * 2 - 1;
    const ny = -(e.clientY / window.innerHeight) * 2 + 1;
    targetLX = nx * 6.5;
    targetLY = ny * 4.5;
  };
  window.addEventListener('mousemove', dhMouse);

  /* ── Materials ── */
  // Polished warm steel — clearcoat layer catches every light shift
  const matSteel = new THREE.MeshPhysicalMaterial({
    color: 0x8c8278, metalness: 1.0, roughness: 0.13,
    clearcoat: 0.55, clearcoatRoughness: 0.07,
  });
  // Brass rose & accents — brand gold
  const matBrass = new THREE.MeshPhysicalMaterial({
    color: 0xb89b72, metalness: 0.95, roughness: 0.20,
    clearcoat: 0.35, clearcoatRoughness: 0.14,
  });
  // Dark charcoal — spindle & mechanism housing
  const matDark = new THREE.MeshPhysicalMaterial({
    color: 0x282220, metalness: 0.88, roughness: 0.28,
    clearcoat: 0.20,
  });
  // Spring steel — blue-grey coils
  const matSpring = new THREE.MeshPhysicalMaterial({
    color: 0x3c3a42, metalness: 0.90, roughness: 0.32,
  });

  /* ═══════════════════════════════════════
     BUILD HANDLE GEOMETRY
     All groups start at position (0,0,0) = assembled state.
     Geometry within each group forms the complete handle shape.
     Explosion animates group.position away from origin.
  ═══════════════════════════════════════ */

  // ── Lever Group: grip bar + neck + end caps + grip bands ──
  const leverGroup = new THREE.Group();

  const grip = new THREE.Mesh(new THREE.CylinderGeometry(0.058, 0.058, 2.1, 64), matSteel);
  grip.rotation.z = Math.PI / 2;
  grip.position.set(0.55, 1.05, 0);
  leverGroup.add(grip);

  const capSphere = new THREE.SphereGeometry(0.062, 32, 32);
  const capL = new THREE.Mesh(capSphere, matSteel);
  capL.position.set(-0.50, 1.05, 0);
  leverGroup.add(capL);

  const capR = new THREE.Mesh(capSphere.clone(), matSteel);
  capR.position.set(1.60, 1.05, 0);
  leverGroup.add(capR);

  // Vertical neck descending from grip-left to rose
  const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.058, 0.058, 0.80, 64), matSteel);
  neck.position.set(-0.50, 0.64, 0);
  leverGroup.add(neck);

  // Fillet sphere at the L-bend
  const junc = new THREE.Mesh(new THREE.SphereGeometry(0.070, 32, 32), matSteel);
  junc.position.set(-0.50, 1.05, 0);
  leverGroup.add(junc);

  // Grip-zone texture rings (5 subtle torus bands)
  for (let i = 0; i < 5; i++) {
    const band = new THREE.Mesh(new THREE.TorusGeometry(0.062, 0.009, 8, 32), matSteel);
    band.rotation.z = Math.PI / 2;
    band.position.set(0.28 + i * 0.21, 1.05, 0);
    leverGroup.add(band);
  }

  // ── Rose Group: escutcheon disc + inner ring + center boss ──
  const roseGroup = new THREE.Group();

  const roseDisc = new THREE.Mesh(new THREE.CylinderGeometry(0.40, 0.40, 0.10, 128), matBrass);
  roseDisc.rotation.x = Math.PI / 2;
  roseDisc.position.set(-0.50, 0.18, 0);
  roseGroup.add(roseDisc);

  const innerRing = new THREE.Mesh(new THREE.TorusGeometry(0.27, 0.021, 16, 80), matBrass);
  innerRing.position.set(-0.50, 0.18, 0.056);
  roseGroup.add(innerRing);

  const boss = new THREE.Mesh(new THREE.CylinderGeometry(0.065, 0.065, 0.14, 32), matBrass);
  boss.rotation.x = Math.PI / 2;
  boss.position.set(-0.50, 0.18, 0.062);
  roseGroup.add(boss);

  // ── Spindle Group: square-section bar + brass retention clip ──
  const spindleGroup = new THREE.Group();

  const bar = new THREE.Mesh(new THREE.BoxGeometry(0.085, 0.085, 1.40), matDark);
  bar.position.set(-0.50, 0.18, 0);
  spindleGroup.add(bar);

  const clip = new THREE.Mesh(new THREE.BoxGeometry(0.17, 0.055, 0.055), matBrass);
  clip.position.set(-0.50, 0.18, 0.73);
  spindleGroup.add(clip);

  // ── Mechanism Group: spring housing + 6 coil tori ──
  const mechGroup = new THREE.Group();

  const housing = new THREE.Mesh(new THREE.BoxGeometry(0.50, 0.50, 0.26), matDark);
  housing.position.set(-0.50, 0.18, -0.60);
  mechGroup.add(housing);

  for (let i = 0; i < 6; i++) {
    const coil = new THREE.Mesh(new THREE.TorusGeometry(0.11, 0.016, 8, 24), matSpring);
    coil.rotation.x = Math.PI / 2;
    coil.position.set(-0.50, -0.088 + i * 0.036 + 0.18, -0.60);
    mechGroup.add(coil);
  }

  // ── Master handle group — shift so handle is centred in frame ──
  const handleGroup = new THREE.Group();
  handleGroup.add(leverGroup, roseGroup, spindleGroup, mechGroup);
  handleGroup.scale.setScalar(1.12);
  handleGroup.position.set(0.2, -0.22, 0);
  scene.add(handleGroup);

  /* ── Exploded target offsets from each group's 0,0,0 ── */
  const EX = {
    lever:  { x: 1.6,  y: 1.3,  z: 0.6,  rx: 0,     ry: 0.22, rz: 0.20 },
    rose:   { x: 0.1,  y: 0.1,  z: 1.0,  rx: 0,     ry: 0.32, rz: 0 },
    spin:   { x:-0.35, y:-1.9,  z: 0.3,  rx: 0.14,  ry: 0,    rz: 0.16 },
    mech:   { x:-1.8,  y:-0.5,  z:-0.7,  rx:-0.18,  ry:-0.25, rz: 0 },
  };

  /* ── Cubic ease in-out ── */
  const ease3 = t => t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t+2,3)/2;

  /* ── Apply explosion/reassembly to one group ── */
  function applyExplode(group, target, t) {
    const te = ease3(Math.max(0, Math.min(1, t)));
    group.position.x = te * target.x;
    group.position.y = te * target.y;
    group.position.z = te * target.z;
    group.rotation.x = te * target.rx;
    group.rotation.y = te * target.ry;
    group.rotation.z = te * target.rz;
  }

  /* ── Scroll state ── */
  let dhP = 0, explodeT = 0, galleryDone = false;

  /* ── Linear map clamped ── */
  function cmap(i0, i1, o0, o1, v) {
    return o0 + (o1 - o0) * Math.max(0, Math.min(1, (v - i0) / (i1 - i0)));
  }

  /* ── Update scene overlays & nav pips ── */
  function updateOverlays(p) {
    // Scene 1: 0 → 0.22, fade out 0.18–0.23
    const s1 = p < 0.18 ? 1 : cmap(0.18, 0.23, 1, 0, p);
    // Scene 2: fade in 0.22–0.27, visible to 0.48, fade out 0.48–0.53
    const s2 = cmap(0.22, 0.27, 0, 1, p) * (p < 0.48 ? 1 : cmap(0.48, 0.53, 1, 0, p));
    // Scene 3: fade in 0.52–0.57, visible to 0.70, fade out 0.70–0.75
    const s3 = cmap(0.52, 0.57, 0, 1, p) * (p < 0.70 ? 1 : cmap(0.70, 0.75, 1, 0, p));
    // Scene 4: fade in 0.74–0.80
    const s4 = cmap(0.74, 0.80, 0, 1, p);

    const o1 = document.getElementById('dh-overlay-1');
    const o2 = document.getElementById('dh-overlay-2');
    const o3 = document.getElementById('dh-overlay-3');
    const o4 = document.getElementById('dh-overlay-4');
    if (o1) o1.style.opacity = Math.max(0, s1);
    if (o2) o2.style.opacity = Math.max(0, Math.min(1, s2));
    if (o3) o3.style.opacity = Math.max(0, Math.min(1, s3));
    if (o4) {
      o4.style.opacity = Math.max(0, s4);
      o4.style.pointerEvents = s4 > 0.5 ? 'auto' : 'none';
    }

    // Canvas fades toward 0 once gallery is dominant
    canvas.style.opacity = p > 0.85 ? cmap(0.85, 0.96, 1, 0, p) : 1;

    // Nav pips
    const active = p < 0.23 ? 0 : p < 0.53 ? 1 : p < 0.74 ? 2 : 3;
    document.querySelectorAll('.dh-nav-pip').forEach((pip, i) => {
      pip.classList.toggle('active', i === active);
    });

    // Animate gallery cards in once (stagger)
    if (s4 > 0.35 && !galleryDone && hasGSAP) {
      galleryDone = true;
      gsap.to('.dh-hcard', { opacity: 1, y: 0, stagger: 0.12, duration: 0.9, ease: 'power3.out' });
      const hint = document.getElementById('dh-drag-hint');
      if (hint) gsap.to(hint, { opacity: 1, duration: 0.6, delay: 0.7 });
    }
  }

  /* ── ScrollTrigger: drives everything ── */
  ScrollTrigger.create({
    trigger: section,
    start:   'top top',
    end:     'bottom bottom',
    scrub:   1.2,
    onUpdate: self => {
      dhP = self.progress;

      // explodeT: 0→1 from 0.22–0.48, 1→0 from 0.48–0.70
      if      (dhP < 0.22) explodeT = 0;
      else if (dhP < 0.48) explodeT = cmap(0.22, 0.48, 0, 1, dhP);
      else if (dhP < 0.70) explodeT = cmap(0.48, 0.70, 1, 0, dhP);
      else                 explodeT = 0;

      updateOverlays(dhP);
    }
  });

  /* ── Animation clock ── */
  const clock = new THREE.Clock();

  /* ── Pause when section off-screen (performance) ── */
  let dhVisible = false;
  new IntersectionObserver(e => { dhVisible = e[0].isIntersecting; }, { threshold: 0.01 })
    .observe(section);

  /* ── Render loop ── */
  (function animate() {
    requestAnimationFrame(animate);
    if (!dhVisible) return;

    const t = clock.getElapsedTime();

    // Smooth key light follows mouse → live metallic specular shift
    curLX += (targetLX - curLX) * 0.055;
    curLY += (targetLY - curLY) * 0.055;
    keyLight.position.set(curLX, curLY, 4.5);

    // Scene 1: gentle Y-axis rotation + sinusoidal float
    if (dhP < 0.22) {
      handleGroup.rotation.y += 0.0035;
      handleGroup.position.y = -0.22 + Math.sin(t * 0.55) * 0.065;
    }

    // Scenes 2 & 3: apply explosion state to each component group
    applyExplode(leverGroup,   EX.lever, explodeT);
    applyExplode(roseGroup,    EX.rose,  explodeT);
    applyExplode(spindleGroup, EX.spin,  explodeT);
    applyExplode(mechGroup,    EX.mech,  explodeT);

    // Subtle camera float (always)
    camera.position.y = Math.sin(t * 0.22) * 0.035;

    renderer.render(scene, camera);
  })();

  /* ── Resize ── */
  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    setH();
  });

  /* ── Gallery drag (called after Three.js setup) ── */
  initDHGallery();
}

/* ── Gallery drag-to-scroll with momentum glide ─────────────── */
function initDHGallery() {
  const track = document.getElementById('dh-gallery-track');
  if (!track || !hasGSAP) return;

  let isDown = false, startX = 0, curX = 0, velX = 0, lastX = 0;
  let glideId;

  const maxDrag = () => -(track.scrollWidth - track.parentElement.offsetWidth + 40);

  track.addEventListener('pointerdown', e => {
    isDown = true;
    startX = e.clientX - curX;
    lastX  = e.clientX;
    velX   = 0;
    cancelAnimationFrame(glideId);
    track.setPointerCapture(e.pointerId);
  });

  track.addEventListener('pointermove', e => {
    if (!isDown) return;
    velX  = e.clientX - lastX;
    lastX = e.clientX;
    curX  = Math.max(maxDrag(), Math.min(0, e.clientX - startX));
    gsap.set(track, { x: curX });
  });

  const endDrag = () => {
    if (!isDown) return;
    isDown = false;
    // Momentum glide
    (function glide() {
      velX *= 0.92;
      curX  = Math.max(maxDrag(), Math.min(0, curX + velX));
      gsap.set(track, { x: curX });
      if (Math.abs(velX) > 0.4) glideId = requestAnimationFrame(glide);
    })();
  };

  track.addEventListener('pointerup',     endDrag);
  track.addEventListener('pointercancel', endDrag);
  // Block native scroll inside gallery while dragging
  track.addEventListener('touchmove', e => e.preventDefault(), { passive: false });
}

/* ═══════════════════════════════════════════════════════════════
   7. MARQUEE — infinite smooth ticker
   Uses GSAP modifiers for seamless loop
═══════════════════════════════════════════════════════════════ */
function initMarquee() {
  if (!hasGSAP) return;

  const track = document.getElementById('marquee-track');
  if (!track) return;

  const inner = track.querySelector('.marquee-inner');
  if (!inner) return;

  const innerW = inner.offsetWidth + 32;   // +gap

  gsap.to(track, {
    x:        -innerW,
    ease:     'none',
    duration: 30,
    repeat:   -1,
    modifiers: {
      x: gsap.utils.unitize(x => parseFloat(x) % innerW)
    }
  });
}

/* ═══════════════════════════════════════════════════════════════
   8. FONT-LOAD REFRESH
   ScrollTrigger positions are calculated before Google Fonts
   may have fully swapped in (causing layout shift / wrong heights).
   We refresh after fonts promise resolves.
═══════════════════════════════════════════════════════════════ */
function refreshAfterFonts() {
  if (!hasST) return;

  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(() => {
      ScrollTrigger.refresh();
    });
  } else {
    // Fallback: refresh after 500ms
    setTimeout(() => ScrollTrigger.refresh(), 500);
  }
}

/* ═══════════════════════════════════════════════════════════════
   9. INIT — tie everything together
═══════════════════════════════════════════════════════════════ */
function init() {

  /* 1. Loader — kicks off sequence */
  initLoader();

  /* 2. Smooth scroll engine */
  initLenis();

  /* 3. Three.js ambient 3D background */
  initThreeJS();

  /* 4. UI systems */
  initCursor();
  initNav();
  initHeroParallax();

  /* 5. Scroll-triggered section animations */
  initPhilosophy();
  initProducts();
  initEngineering();
  initSignature();
  initProjects();
  initFooter();
  initSectionLabels();
  initSectionTitles();
  initDoorHandles();      // ← cinematic handle story

  /* 6. Marquee ticker */
  initMarquee();

  /* 7. Refresh triggers after fonts settle */
  refreshAfterFonts();
}

/* ── Boot when DOM is ready ─────────────────────────────────── */
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
