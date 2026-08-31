/**
 * Chashitsu — menus, reveals, and sumi ink that tracks Style Settings tokens.
 * Light-only: no theme toggle, no season picker.
 */
(function () {
  'use strict';

  document.documentElement.classList.add('js');

  document.addEventListener('DOMContentLoaded', () => {
    initMobileMenu();
    initDropdownMenus();
    initReveals();
    initInk();
  });

  function initMobileMenu() {
    const menuToggle = document.getElementById('mobile-menu-toggle');
    const navMenu = document.getElementById('nav-menu');
    if (!menuToggle || !navMenu) return;

    menuToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      const open = navMenu.classList.toggle('active');
      menuToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      menuToggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    });

    document.addEventListener('click', (e) => {
      if (navMenu.classList.contains('active') && !navMenu.contains(e.target) && e.target !== menuToggle) {
        navMenu.classList.remove('active');
        menuToggle.setAttribute('aria-expanded', 'false');
        menuToggle.setAttribute('aria-label', 'Open menu');
        navMenu.querySelectorAll('.nav-item.has-children.open').forEach((item) => {
          item.classList.remove('open');
        });
      }
    });
  }

  function initDropdownMenus() {
    const navMenu = document.getElementById('nav-menu');
    if (!navMenu) return;

    navMenu.querySelectorAll('.nav-item.has-children').forEach((item) => {
      let mouseleaveTimer = null;

      item.addEventListener('mouseenter', () => {
        if (mouseleaveTimer) {
          clearTimeout(mouseleaveTimer);
          mouseleaveTimer = null;
        }
        item.classList.add('open');
      });

      item.addEventListener('mouseleave', () => {
        mouseleaveTimer = setTimeout(() => {
          item.classList.remove('open');
        }, 200);
      });

      const trigger = item.querySelector('.nav-trigger');
      if (trigger) {
        trigger.addEventListener('click', (e) => {
          if (window.matchMedia('(max-width: 820px)').matches) {
            e.preventDefault();
            e.stopPropagation();
            item.classList.toggle('open');
          }
        });
      }
    });
  }

  function initReveals() {
    const mqReduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (mqReduced.matches) {
      document.querySelectorAll('[data-reveal]').forEach((el) => el.classList.add('is-in'));
      return;
    }
    const nodes = document.querySelectorAll('[data-reveal]');
    if (!nodes.length || !('IntersectionObserver' in window)) {
      nodes.forEach((el) => el.classList.add('is-in'));
      return;
    }
    const obs = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (en.isIntersecting) {
          en.target.classList.add('is-in');
          obs.unobserve(en.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
    nodes.forEach((el) => obs.observe(el));
  }

  function hexToRgb(hex) {
    if (!hex) return null;
    const h = hex.trim();
    const m3 = /^#([0-9a-f]{3})$/i.exec(h);
    if (m3) {
      const n = m3[1];
      return [
        parseInt(n[0] + n[0], 16),
        parseInt(n[1] + n[1], 16),
        parseInt(n[2] + n[2], 16)
      ];
    }
    const m6 = /^#([0-9a-f]{6})$/i.exec(h);
    if (m6) {
      const n = m6[1];
      return [
        parseInt(n.slice(0, 2), 16),
        parseInt(n.slice(2, 4), 16),
        parseInt(n.slice(4, 6), 16)
      ];
    }
    const rgb = /^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i.exec(h);
    if (rgb) return [Number(rgb[1]), Number(rgb[2]), Number(rgb[3])];
    return null;
  }

  function cssColorToRgb(value, fallback) {
    const direct = hexToRgb(value);
    if (direct) return direct;
    const probe = document.createElement('span');
    probe.style.color = value;
    document.body.appendChild(probe);
    const computed = getComputedStyle(probe).color;
    document.body.removeChild(probe);
    return hexToRgb(computed) || fallback;
  }

  function inkTokens() {
    const cs = getComputedStyle(document.documentElement);
    const ink = cssColorToRgb(cs.getPropertyValue('--color-text').trim(), [33, 30, 27]);
    const accent = cssColorToRgb(cs.getPropertyValue('--color-accent').trim(), [78, 122, 92]);
    const bg = cs.getPropertyValue('--color-bg').trim() || '#F5F1E6';
    const deep = [
      Math.round(accent[0] * 0.72 + ink[0] * 0.28),
      Math.round(accent[1] * 0.72 + ink[1] * 0.28),
      Math.round(accent[2] * 0.72 + ink[2] * 0.28)
    ];
    const mist = [
      Math.round(accent[0] * 0.35 + 245 * 0.65),
      Math.round(accent[1] * 0.35 + 241 * 0.65),
      Math.round(accent[2] * 0.35 + 230 * 0.65)
    ];
    return { ink: ink, accent: accent, deep: deep, mist: mist, paper: bg };
  }

  function ridgePts(x0, x1, yBase, yPeak, extra, rng) {
    const n = 6 + extra;
    const pts = [];
    for (let i = 0; i < n; i++) {
      const t = i / (n - 1);
      const arch = Math.sin(Math.PI * t);
      const y = yBase - arch * (yBase - yPeak) + (rng() - 0.5) * 8;
      pts.push({ x: x0 + (x1 - x0) * t, y: y });
    }
    return pts;
  }

  function yAt(pts, x) {
    for (let i = 0; i < pts.length - 1; i++) {
      if (x >= pts[i].x && x <= pts[i + 1].x) {
        const t = (x - pts[i].x) / (pts[i + 1].x - pts[i].x || 1);
        return pts[i].y + (pts[i + 1].y - pts[i].y) * t;
      }
    }
    return pts[pts.length - 1].y;
  }

  function heroComposer(w, h, rng) {
    const T = inkTokens();
    const ink = T.ink;
    const mob = w < 700;
    const left = w * 0.04;
    const right = w * 0.96;
    const strokes = [];

    /* 1. Distant atmospheric mist wash along the lower valley */
    strokes.push({
      pts: [
        { x: left, y: h * (mob ? 0.72 : 0.74) },
        { x: w * 0.5, y: h * (mob ? 0.60 : 0.62) },
        { x: right, y: h * (mob ? 0.70 : 0.72) }
      ],
      width: h * (mob ? 0.18 : 0.22), ink: 0.22, color: T.mist,
      wash: true, dry: 0.4, speed: 900, delay: 40
    });

    /* 2. Distant mountain ridge (soft lower horizon silhouette) */
    const fBase = h * (mob ? 0.86 : 0.88);
    const fPeak = h * (mob ? 0.70 : 0.72);
    strokes.push({
      pts: ridgePts(left, right, fBase, fPeak, 1, rng),
      width: Math.max(9, w * (mob ? 0.012 : 0.010)), ink: 0.28, color: ink,
      dry: 0.85, speed: 520, delay: 180, bleedP: 0.004
    });

    /* 3. Near mountain ridge (full-width panorama cresting below the title) */
    const nBase = h * (mob ? 0.82 : 0.84);
    const nPeak = h * (mob ? 0.56 : 0.58);
    const nx0 = left + w * (mob ? 0.08 : 0.05);
    const nearW = Math.max(12, w * (mob ? 0.022 : 0.014));
    const nearPts = ridgePts(nx0, right, nBase, nPeak, 2, rng);
    strokes.push({
      pts: nearPts, width: nearW, ink: 0.76, color: ink,
      dry: 0.75, speed: 460, delay: 380, bleedP: 0.006
    });

    /* 4. Valley tea-green accent wash */
    strokes.push({
      pts: [
        { x: left + w * 0.14, y: nBase - h * 0.006 },
        { x: (left + right) / 2, y: nBase + h * 0.012 },
        { x: right - w * 0.08, y: nBase - h * 0.004 }
      ],
      width: h * (mob ? 0.02 : 0.038), ink: 0.38, color: T.accent,
      wash: true, dry: 0.35, speed: 1100, delay: 200
    });

    /* 5. Mountain tea hut / pavilion on the right ridge slope */
    const span = right - nx0;
    const hx = nx0 + span * 0.70;
    const hy = yAt(nearPts, hx) - nearW * 0.9;
    const hs = mob ? 0.7 : 1;
    strokes.push({
      pts: [{ x: hx - 26 * hs, y: hy + 14 * hs }, { x: hx + 30 * hs, y: hy + 15 * hs }],
      width: 7 * hs, ink: 0.7, color: ink, dry: 0.9, speed: 300, delay: 340, bleedP: 0.004, bristles: 7
    });
    strokes.push({
      pts: [{ x: hx - 14 * hs, y: hy + 5 * hs }, { x: hx + 14 * hs, y: hy + 6 * hs }],
      width: 13 * hs, ink: 0.9, color: ink, dab: true, dry: 0.4, speed: 150, delay: 260, bleedP: 0.012, bristles: 6
    });
    strokes.push({
      pts: [
        { x: hx - 35 * hs, y: hy - 1 * hs },
        { x: hx - 2 * hs, y: hy - 20 * hs },
        { x: hx + 33 * hs, y: hy }
      ],
      width: 15 * hs, ink: 0.95, color: ink, dab: true, dry: 0.25, speed: 210, delay: 240, bleedP: 0.014, bristles: 8
    });

    /* 6. Wild birds soaring in the open upper sky */
    const n = mob ? 1 : 2;
    for (let i = 0; i < n; i++) {
      const cx = w * (mob ? 0.65 + rng() * 0.20 : 0.65 + rng() * 0.20);
      const cy = h * (mob ? 0.08 + rng() * 0.05 : 0.12 + rng() * 0.08);
      const sp = 17 + rng() * 6;
      strokes.push({
        pts: [{ x: cx - sp, y: cy + 3 }, { x: cx - sp * 0.4, y: cy - 6 }, { x: cx, y: cy }],
        width: 5, ink: 0.8, color: ink, dry: 0.5, speed: 260, delay: i === 0 ? 250 : 160, bleedP: 0, bristles: 4
      });
      strokes.push({
        pts: [{ x: cx, y: cy }, { x: cx + sp * 0.6, y: cy - 6 }, { x: cx + sp, y: cy + 3.5 }],
        width: 5, ink: 0.8, color: ink, dry: 0.85, speed: 260, delay: 90, bleedP: 0, bristles: 4
      });
    }

    /* 7. Carved hanko seal stamped along lower right horizon */
    strokes.push({
      type: 'seal',
      x: mob ? w * 0.88 : w * 0.905,
      y: mob ? h * 0.82 : h * 0.80,
      size: mob ? 26 : 34,
      rot: -0.07, glyph: '茶', color: T.deep, paper: T.paper, delay: 550
    });

    return strokes;
  }

  function dividerComposer(w, h, rng) {
    const T = inkTokens();
    const y = h * (0.42 + rng() * 0.2);
    const len = Math.min(w - 4, w * (0.68 + rng() * 0.3));
    const n = 5;
    const pts = [];
    for (let i = 0; i < n; i++) {
      const t = i / (n - 1);
      const edge = (i === 0 || i === n - 1) ? 0.4 : 1;
      pts.push({ x: 2 + (len - 4) * t, y: y + (rng() - 0.5) * h * 0.5 * edge });
    }
    const strokes = [{
      pts: pts, width: h * 0.36, ink: 0.92, color: T.ink,
      dry: 0.75 + rng() * 0.3, speed: 720, delay: 80, bleedP: 0.004
    }];
    if (rng() < 0.55) {
      const ex0 = len * (0.45 + rng() * 0.2);
      const ex1 = Math.min(len - 2, ex0 + len * (0.22 + rng() * 0.2));
      const ey = y + (rng() < 0.5 ? -1 : 1) * h * (0.16 + rng() * 0.1);
      strokes.push({
        pts: [
          { x: ex0, y: ey },
          { x: (ex0 + ex1) / 2, y: ey + (rng() - 0.5) * h * 0.12 },
          { x: ex1, y: ey + (rng() - 0.5) * h * 0.1 }
        ],
        width: h * 0.1, ink: 0.45, color: T.ink,
        dry: 1.1, speed: 640, delay: 260, bleedP: 0.002, bristles: 8
      });
    }
    return strokes;
  }

  function sealComposer(w, h) {
    const T = inkTokens();
    return [{
      type: 'seal',
      x: w / 2,
      y: h / 2,
      size: Math.min(w, h) * 0.92,
      rot: -0.06,
      glyph: '茶',
      color: T.deep,
      paper: T.paper,
      delay: 80
    }];
  }

  function initInk() {
    const SumiPainter = window.Sumi && window.Sumi.SumiPainter;
    if (!SumiPainter) return;
    if (document.fonts && document.fonts.load) {
      document.fonts.load('500 40px "Noto Serif JP"', '茶間霧');
    }

    const mqReduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    const painters = [];
    const canvasToPainter = new Map();

    function addPainter(canvas, composer, seedBase) {
      const p = new SumiPainter(canvas, composer, { seedBase: seedBase });
      p.instant = mqReduced.matches;
      painters.push(p);
      canvasToPainter.set(canvas, p);
      return p;
    }

    const heroCanvas = document.getElementById('heroInk');
    if (heroCanvas) addPainter(heroCanvas, heroComposer, 11);

    document.querySelectorAll('[data-ink="divider"]').forEach(function (c, i) {
      addPainter(c, dividerComposer, 41 + i * 17);
    });

    const footSeal = document.getElementById('footSeal');
    if (footSeal) addPainter(footSeal, sealComposer, 311);

    if (!('IntersectionObserver' in window)) {
      painters.forEach(function (p) { p.play(); });
      return;
    }

    const inViewSet = new Set();
    const paintObs = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        const p = canvasToPainter.get(en.target);
        if (!p) return;
        p.setInView(en.isIntersecting);
        if (en.isIntersecting) { inViewSet.add(en.target); p.play(); }
        else inViewSet.delete(en.target);
      });
    }, { rootMargin: '60px 0px 60px 0px', threshold: 0.02 });
    painters.forEach(function (p) { paintObs.observe(p.canvas); });

    document.addEventListener('visibilitychange', function () {
      const v = !document.hidden;
      painters.forEach(function (p) { p.setPageVisible(v); });
    });

    const onMotionPref = function () {
      painters.forEach(function (p) { p.instant = mqReduced.matches; });
    };
    if (mqReduced.addEventListener) mqReduced.addEventListener('change', onMotionPref);
    else if (mqReduced.addListener) mqReduced.addListener(onMotionPref);

    let lastW = window.innerWidth, lastH = window.innerHeight, resizeT = 0;
    window.addEventListener('resize', function () {
      clearTimeout(resizeT);
      resizeT = setTimeout(function () {
        const dw = Math.abs(window.innerWidth - lastW);
        const dh = Math.abs(window.innerHeight - lastH);
        if (dw < 24 && dh < 140) return;
        lastW = window.innerWidth; lastH = window.innerHeight;
        painters.forEach(function (p) { p.resize(); });
      }, 220);
    });
  }
})();
