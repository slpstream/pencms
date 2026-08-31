/* ============================================================
   Seifū-an — sumi.js
   A self-painting ink engine. Canvas 2D, no libraries.
   Strokes are Catmull-Rom centerlines stamped by a bristle
   model: ink load decays along the stroke so bristles drop out
   (kasure, "flying white"); low-alpha blots pool where the
   brush touches down or lingers (nijimi bleed); washes lay
   mist; a carved hanko seal stamps itself last.
   ============================================================ */
'use strict';
(function () {

  /* ---------- seeded randomness ---------- */
  function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function hashSeed() {
    let h = 2166136261 >>> 0;
    for (let i = 0; i < arguments.length; i++) {
      h ^= arguments[i] >>> 0;
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  const clamp = (v, a, b) => v < a ? a : v > b ? b : v;
  const smooth = (a, b, t) => {
    const x = clamp((t - a) / (b - a), 0, 1);
    return x * x * (3 - 2 * x);
  };

  const STEP = 2.2; /* px between stamps along a stroke */

  /* ---------- centerline sampling (Catmull-Rom) ---------- */
  function catmullRom(pts, step) {
    if (!pts || pts.length < 2) return (pts || []).slice();
    const out = [];
    const P = i => pts[Math.max(0, Math.min(pts.length - 1, i))];
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = P(i - 1), p1 = P(i), p2 = P(i + 1), p3 = P(i + 2);
      const d = Math.hypot(p2.x - p1.x, p2.y - p1.y);
      const n = Math.max(2, Math.ceil(d / step));
      for (let j = 0; j < n; j++) {
        const t = j / n, t2 = t * t, t3 = t2 * t;
        out.push({
          x: 0.5 * ((2 * p1.x) + (-p0.x + p2.x) * t + (2 * p0.x - 5 * p1.x + 4 * p2.x - p3.x) * t2 + (-p0.x + 3 * p1.x - 3 * p2.x + p3.x) * t3),
          y: 0.5 * ((2 * p1.y) + (-p0.y + p2.y) * t + (2 * p0.y - 5 * p1.y + 4 * p2.y - p3.y) * t2 + (-p0.y + 3 * p1.y - 3 * p2.y + p3.y) * t3)
        });
      }
    }
    out.push({ x: pts[pts.length - 1].x, y: pts[pts.length - 1].y });
    return out;
  }

  /* ---------- stroke preparation ---------- */
  function prepStroke(d, rng) {
    if (d.type === 'seal') {
      return {
        kind: 'seal', x: d.x, y: d.y, size: d.size, rot: d.rot != null ? d.rot : -0.06,
        color: d.color || [150, 71, 93], paper: d.paper || '#F5F1E6',
        glyph: d.glyph || '茶', delay: d.delay != null ? d.delay : 500, prog: 0, _bmp: null
      };
    }
    const samples = catmullRom(d.pts, STEP);
    const n = samples.length;
    const press = new Float32Array(n);
    const load = new Float32Array(n);
    const halfW = new Float32Array(n);
    const dry = d.dry != null ? d.dry : 0.8;
    let wob = 0;
    for (let i = 0; i < n; i++) {
      const t = n === 1 ? 1 : i / (n - 1);
      wob = wob * 0.9 + (rng() - 0.5) * 0.13;
      if (d.dab) {
        /* a dab is one touch: bellied, wet, both tips tapered */
        press[i] = Math.max(0.1, (0.3 + 0.7 * Math.sin(Math.PI * t)) * (0.9 + wob * 0.5));
        load[i] = clamp(0.92 - dry * t * 0.35 + wob * 0.2, 0, 1);
      } else if (d.wash) {
        /* a wash is one long exhale: a slow bell, no plateau, so the
           band swells in the middle and vanishes into the paper at
           both ends instead of stopping at a cigar edge */
        press[i] = Math.max(0.04, Math.pow(Math.sin(Math.PI * t), 0.6) * (0.85 + wob * 0.3));
        load[i] = clamp(1 - dry * t * 0.5 + wob * 0.3, 0, 1);
      } else {
        const entry = smooth(0, 0.055, t);
        const exit = 1 - 0.9 * smooth(0.8, 1, t);
        press[i] = Math.max(0.05, entry * exit * (0.8 + wob));
        load[i] = clamp(1 - dry * Math.pow(t, 1.12) + wob * 0.55, 0, 1);
      }
      halfW[i] = (d.width / 2) * (0.42 + 0.66 * press[i]);
    }
    const bristles = [];
    if (!d.wash) {
      const count = d.bristles || Math.max(12, Math.round(14 + d.width * 0.8));
      for (let i = 0; i < count; i++) {
        bristles.push({
          u: (rng() * 2 - 1) * 0.92,
          a: 0.08 + rng() * 0.45,
          r: 0.55 + rng() * 1.6,
          thr: Math.pow(rng(), 1.4) * 0.85
        });
      }
    }
    return {
      kind: d.wash ? 'wash' : 'stroke',
      dab: !!d.dab,
      samples: samples, press: press, load: load, halfW: halfW, bristles: bristles,
      color: d.color || [33, 30, 27],
      ink: d.ink != null ? d.ink : 0.85,
      speed: d.speed || 500,
      delay: d.delay != null ? d.delay : 200,
      bleedP: d.bleedP != null ? d.bleedP : 0.005,
      prog: 0, idx: 0
    };
  }

  /* ---------- carved seal bitmap ---------- */
  function sealBitmap(s) {
    const px = Math.max(64, Math.round(s.size * 3));
    const c = document.createElement('canvas');
    c.width = c.height = px;
    const g = c.getContext('2d');
    const rng = mulberry32(hashSeed(Math.round(s.x * 13) | 0, Math.round(s.y * 7) | 0, 77));
    const m = px * 0.07;
    /* hand-cut square: jittered perimeter */
    g.beginPath();
    const corners = [[m, m], [px - m, m], [px - m, px - m], [m, px - m]];
    const per = 6;
    let first = true;
    for (let side = 0; side < 4; side++) {
      const a = corners[side], b = corners[(side + 1) % 4];
      for (let j = 0; j < per; j++) {
        const t = j / per;
        const x = a[0] + (b[0] - a[0]) * t + (rng() - 0.5) * px * 0.025;
        const y = a[1] + (b[1] - a[1]) * t + (rng() - 0.5) * px * 0.025;
        if (first) { g.moveTo(x, y); first = false; } else { g.lineTo(x, y); }
      }
    }
    g.closePath();
    g.fillStyle = 'rgb(' + s.color[0] + ',' + s.color[1] + ',' + s.color[2] + ')';
    g.fill();
    /* the character, knocked out in paper */
    g.fillStyle = s.paper;
    g.font = '500 ' + Math.round(px * 0.60) + 'px "Noto Serif JP", serif';
    g.textAlign = 'center';
    g.textBaseline = 'middle';
    g.fillText(s.glyph, px / 2, px * 0.55);
    /* stone distress */
    g.globalCompositeOperation = 'destination-out';
    for (let i = 0; i < 80; i++) {
      const x = rng() * px, y = rng() * px;
      const edgeDist = Math.min(x, y, px - x, px - y);
      if (edgeDist > px * 0.16 && rng() < 0.72) continue; /* bias wear to edges */
      g.globalAlpha = 0.10 + rng() * 0.28;
      g.beginPath();
      g.arc(x, y, (0.5 + rng() * 1.7) * px / 60, 0, 6.2832);
      g.fill();
    }
    g.globalAlpha = 1;
    g.globalCompositeOperation = 'source-over';
    return c;
  }

  /* ---------- the painter ---------- */
  function SumiPainter(canvas, composer, opts) {
    opts = opts || {};
    this.canvas = canvas;
    this.composer = composer;
    this.seedBase = opts.seedBase != null ? opts.seedBase : 7;
    this.season = opts.season || 'summer';
    this.gen = 0;
    this.instant = false;
    this.state = 'idle';           /* idle | playing | done */
    this.pageVisible = !document.hidden;
    this.inView = true;
    this.onDone = null;
    this._raf = 0;
    this._last = 0;
    this._wait = 0;
    this._strokes = [];
    this._cur = 0;
    this._rng = Math.random;
    this._snap = null;
    this._tickBound = this._tick.bind(this);
    this.ctx = null;
    try { this.ctx = canvas.getContext('2d'); } catch (e) { /* designed fallback: paper stays paper */ }
    if (!this.ctx) canvas.style.display = 'none';
  }

  SumiPainter.prototype._seasonIndex = function () {
    return { spring: 1, summer: 2, autumn: 3, winter: 4 }[this.season] || 0;
  };

  SumiPainter.prototype._size = function () {
    const r = this.canvas.getBoundingClientRect();
    this.w = Math.max(2, Math.round(r.width));
    this.h = Math.max(2, Math.round(r.height));
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    this.dpr = dpr;
    this.canvas.width = Math.round(this.w * dpr);
    this.canvas.height = Math.round(this.h * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  };

  SumiPainter.prototype.setSeason = function (season) {
    this.season = season;
    this.gen++;
    this._stopLoop();
    this._snap = null;
    this.state = 'idle';
    if (this.ctx) this._size(); /* resizing clears the canvas */
  };

  SumiPainter.prototype._compose = function () {
    const seed = hashSeed(this.seedBase * 2654435761, this._seasonIndex() * 40503, this.gen * 2246822519);
    const rng = mulberry32(seed);
    this._rng = rng;
    const defs = this.composer(this.w, this.h, rng, this.season) || [];
    this._strokes = defs.map(d => prepStroke(d, rng));
    this._cur = 0;
  };

  SumiPainter.prototype.play = function () {
    if (!this.ctx || this.state !== 'idle') return;
    this._size();
    this._compose();
    this.state = 'playing';
    if (this.instant) { this._renderAll(); return; }
    this._wait = this._strokes.length ? this._strokes[0].delay : 0;
    this._last = 0;
    this._startLoop();
  };

  SumiPainter.prototype._renderAll = function () {
    const strokes = this._strokes;
    for (let k = 0; k < strokes.length; k++) {
      const s = strokes[k];
      if (s.kind === 'seal') {
        if (!s._bmp) s._bmp = sealBitmap(s);
        this._drawSeal(s, 1, 1);
      } else {
        for (let i = 0; i < s.samples.length; i++) this._stamp(s, i);
        s.idx = s.samples.length;
      }
    }
    this._cur = strokes.length;
    this.state = 'done';
    this._snap = null;
    if (this.onDone) this.onDone();
  };

  SumiPainter.prototype._tick = function (ts) {
    this._raf = 0;
    if (this.state !== 'playing') return;
    if (this._last === 0) { this._last = ts; this._startLoop(); return; }
    let dt = Math.min(48, ts - this._last);
    this._last = ts;

    while (dt > 0 && this._cur < this._strokes.length) {
      if (this._wait > 0) {
        const used = Math.min(this._wait, dt);
        this._wait -= used; dt -= used;
        continue;
      }
      const s = this._strokes[this._cur];
      if (s.kind === 'seal') {
        this._sealFrame(s, dt);
        dt = 0;
      } else {
        s.prog += s.speed * dt / 1000;
        const target = Math.min(s.samples.length - 1, Math.floor(s.prog / STEP));
        while (s.idx <= target) this._stamp(s, s.idx++);
        if (s.idx >= s.samples.length) this._nextStroke();
        dt = 0;
      }
    }

    if (this._cur >= this._strokes.length) {
      this.state = 'done';
      this._snap = null;
      if (this.onDone) this.onDone();
      return;
    }
    this._startLoop();
  };

  SumiPainter.prototype._nextStroke = function () {
    this._cur++;
    const nxt = this._strokes[this._cur];
    this._wait = nxt ? nxt.delay : 0;
  };

  SumiPainter.prototype._sealFrame = function (s, dt) {
    if (!s._bmp) s._bmp = sealBitmap(s);
    if (!this._snap) {
      this._snap = document.createElement('canvas');
      this._snap.width = this.canvas.width;
      this._snap.height = this.canvas.height;
      this._snap.getContext('2d').drawImage(this.canvas, 0, 0);
    }
    s.prog += dt;
    const p = clamp(s.prog / 450, 0, 1);
    const e = 1 - Math.pow(1 - p, 3);
    const ctx = this.ctx;
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.drawImage(this._snap, 0, 0);
    ctx.restore();
    this._drawSeal(s, e, p);
    if (p >= 1) { this._snap = null; this._nextStroke(); }
  };

  SumiPainter.prototype._drawSeal = function (s, e, alphaP) {
    if (!s._bmp) s._bmp = sealBitmap(s);
    const ctx = this.ctx;
    ctx.save();
    ctx.translate(s.x, s.y);
    ctx.rotate(s.rot + (1 - e) * -0.10);
    const k = 1.12 - 0.12 * e;
    ctx.scale(k, k);
    ctx.globalAlpha = Math.pow(alphaP, 1.5);
    ctx.drawImage(s._bmp, -s.size / 2, -s.size / 2, s.size, s.size);
    ctx.restore();
  };

  SumiPainter.prototype._stamp = function (s, i) {
    const ctx = this.ctx;
    const pts = s.samples;
    const p = pts[i];
    const q = pts[Math.min(pts.length - 1, i + 1)];
    const o = pts[Math.max(0, i - 1)];
    let dx = q.x - o.x, dy = q.y - o.y;
    const dl = Math.hypot(dx, dy) || 1;
    dx /= dl; dy /= dl;
    const nx = -dy, ny = dx;
    const hw = s.halfW[i], load = s.load[i], press = s.press[i];
    const r = s.color[0], g = s.color[1], b = s.color[2];
    const rng = this._rng;

    if (s.kind === 'wash') {
      /* feathered mist: soft radial pools whose alpha and radius ride
         the pressure bell — dense wet middle, edges lost in the paper */
      const a = 0.012 * s.ink * (0.4 + 0.6 * load) * (0.25 + 0.75 * press);
      if (a < 0.0008) return;
      for (let k = 0; k < 2; k++) {
        const R = Math.max(2, hw * (0.85 + rng() * 0.4) * (0.5 + 0.62 * press));
        const cx = p.x + (rng() - 0.5) * 4;
        const cy = p.y + ny * (rng() - 0.5) * hw * 0.55;
        const gr = ctx.createRadialGradient(cx, cy, R * 0.12, cx, cy, R);
        gr.addColorStop(0, 'rgba(' + r + ',' + g + ',' + b + ',' + a.toFixed(4) + ')');
        gr.addColorStop(1, 'rgba(' + r + ',' + g + ',' + b + ',0)');
        ctx.fillStyle = gr;
        ctx.beginPath();
        ctx.arc(cx, cy, R, 0, 6.2832);
        ctx.fill();
      }
      return;
    }

    /* narrow strokes overlap fewer stamps — normalize their ink */
    const boost = Math.min(2.6, Math.max(1, 4.5 / Math.max(2.2, hw)));

    /* belly — the wet body of the stroke, two nested pools */
    const bodyBase = (s.dab ? 0.115 : 0.085) * boost;
    const bodyA = bodyBase * s.ink * press * Math.pow(load, 1.3);
    if (bodyA > 0.003) {
      ctx.fillStyle = 'rgba(' + r + ',' + g + ',' + b + ',' + bodyA.toFixed(4) + ')';
      ctx.beginPath();
      ctx.arc(p.x + (rng() - 0.5) * 0.6, p.y + (rng() - 0.5) * 0.6, hw * 0.9, 0, 6.2832);
      ctx.fill();
      const coreA = 0.062 * boost * s.ink * press * load;
      ctx.fillStyle = 'rgba(' + r + ',' + g + ',' + b + ',' + coreA.toFixed(4) + ')';
      ctx.beginPath();
      ctx.arc(p.x + nx * (rng() - 0.5) * hw * 0.3, p.y + ny * (rng() - 0.5) * hw * 0.3, hw * 0.5, 0, 6.2832);
      ctx.fill();
    }

    /* bristles — dropout under low ink load gives kasure */
    for (let bi = 0; bi < s.bristles.length; bi++) {
      const br = s.bristles[bi];
      if (load < br.thr) continue;
      const off = br.u * hw * (0.92 + (rng() - 0.5) * 0.18);
      const x = p.x + nx * off + (rng() - 0.5) * 1.1;
      const y = p.y + ny * off + (rng() - 0.5) * 1.1;
      const rad = Math.max(0.5, hw * 0.15 * br.r);
      const a = (0.045 + 0.24 * br.a) * boost * s.ink * (0.35 + 0.65 * load);
      ctx.fillStyle = 'rgba(' + r + ',' + g + ',' + b + ',' + a.toFixed(4) + ')';
      ctx.beginPath();
      ctx.arc(x, y, rad, 0, 6.2832);
      ctx.fill();
    }

    /* nijimi — ink bleeding into the paper where the brush pauses */
    if (i === 0 || rng() < s.bleedP) {
      const R = hw * (1.7 + rng() * 1.1);
      const gr = ctx.createRadialGradient(p.x, p.y, R * 0.15, p.x, p.y, R);
      const a = (i === 0 ? 0.05 : 0.03) * s.ink * (0.3 + 0.7 * load);
      gr.addColorStop(0, 'rgba(' + r + ',' + g + ',' + b + ',' + a.toFixed(4) + ')');
      gr.addColorStop(1, 'rgba(' + r + ',' + g + ',' + b + ',0)');
      ctx.fillStyle = gr;
      ctx.beginPath();
      ctx.arc(p.x, p.y, R, 0, 6.2832);
      ctx.fill();
    }
  };

  SumiPainter.prototype._startLoop = function () {
    if (!this._raf && this.state === 'playing' && this.pageVisible && this.inView) {
      this._raf = requestAnimationFrame(this._tickBound);
    }
  };

  SumiPainter.prototype._stopLoop = function () {
    if (this._raf) { cancelAnimationFrame(this._raf); this._raf = 0; }
    this._last = 0;
  };

  SumiPainter.prototype.setPageVisible = function (v) {
    this.pageVisible = v;
    if (v) this._startLoop(); else this._stopLoop();
  };

  SumiPainter.prototype.setInView = function (v) {
    this.inView = v;
    if (v) this._startLoop(); else this._stopLoop();
  };

  SumiPainter.prototype.resize = function () {
    if (!this.ctx) return;
    if (this.state === 'idle') { this._size(); return; }
    this._stopLoop();
    this._snap = null;
    this._size();
    this._compose();
    this._renderAll(); /* same seed → same painting, refitted */
  };

  window.Sumi = { SumiPainter: SumiPainter, mulberry32: mulberry32, hashSeed: hashSeed };
})();
