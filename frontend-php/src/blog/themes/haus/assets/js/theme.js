/**
 * Haus — published chrome only.
 * Theme toggle, mobile drawer, sturdy dropdown hover grace, pointer-tracked VF hero.
 * Admin / editor never loads this file.
 */

document.documentElement.classList.add('js');

document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
  initMobileMenu();
  initDropdownMenus();
  initHero();
});

function initThemeToggle() {
  const toggleBtn = document.querySelector('[data-theme-toggle]') || document.getElementById('theme-toggle');
  if (!toggleBtn) return;

  toggleBtn.addEventListener('click', () => {
    const isDark = document.documentElement.classList.contains('cm-wysiwym-dark') ||
                   document.documentElement.getAttribute('data-theme') === 'dark' ||
                   (!document.documentElement.getAttribute('data-theme') && window.matchMedia('(prefers-color-scheme: dark)').matches);
    const newTheme = isDark ? 'light' : 'dark';

    document.documentElement.classList.toggle('cm-wysiwym-dark', newTheme === 'dark');
    document.documentElement.setAttribute('data-theme', newTheme);

    try {
      localStorage.setItem('color-scheme', newTheme);
      localStorage.setItem('theme', newTheme);
    } catch (e) {}
    try {
      document.cookie = 'color-scheme=' + newTheme + '; path=/; max-age=31536000; SameSite=Lax';
      document.cookie = 'theme=' + newTheme + '; path=/; max-age=31536000; SameSite=Lax';
    } catch (e) {}

    const metaTag = document.querySelector('meta[name="color-scheme"]');
    if (metaTag) {
      metaTag.content = newTheme === 'dark' ? 'dark' : 'light';
    }
  });

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    let userOverride = null;
    try {
      userOverride = localStorage.getItem('color-scheme') || localStorage.getItem('theme');
    } catch (err) {}
    if (!userOverride) {
      try {
        const match = document.cookie.match(/(^|;)\s*(?:color-scheme|theme)\s*=\s*([^;]+)/);
        userOverride = match ? match[2] : null;
      } catch (err) {}
    }
    if (!userOverride) {
      document.documentElement.classList.toggle('cm-wysiwym-dark', e.matches);
      document.documentElement.setAttribute('data-theme', e.matches ? 'dark' : 'light');
    }
  });
}

function initMobileMenu() {
  const menuToggle = document.getElementById('mobile-menu-toggle');
  const navMenu = document.getElementById('nav-menu');
  if (!menuToggle || !navMenu) return;

  menuToggle.addEventListener('click', (e) => {
    e.stopPropagation();
    const open = navMenu.classList.toggle('active');
    menuToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  });

  document.addEventListener('click', (e) => {
    if (navMenu.classList.contains('active') && !navMenu.contains(e.target) && e.target !== menuToggle) {
      navMenu.classList.remove('active');
      menuToggle.setAttribute('aria-expanded', 'false');
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
        if (window.matchMedia('(max-width: 768px)').matches) {
          e.preventDefault();
          e.stopPropagation();
          item.classList.toggle('open');
        }
      });
    }
  });
}

function initHero() {
  const heroEl = document.getElementById('hero');
  const title = document.getElementById('heroTitle');
  const lens = document.getElementById('heroLens');
  const read = document.getElementById('lensRead');
  if (!heroEl || !title) return;

  const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const hint = document.getElementById('heroHint');
  if (hint && matchMedia('(hover: none)').matches) hint.textContent = 'drag a finger across the line';

  const letters = [];
  title.querySelectorAll('.hero-line').forEach((line) => {
    line.setAttribute('aria-hidden', 'true');
    const text = line.textContent;
    line.textContent = '';
    [...text].forEach((ch) => {
      const s = document.createElement('span');
      s.className = 'hl-ch';
      s.textContent = ch === ' ' ? '\u00a0' : ch;
      line.appendChild(s);
      letters.push({ el: s, w: 170, wd: 68, heat: 0, lift: 0 });
    });
  });
  title.setAttribute('aria-label', title.innerText.replace(/\s+/g, ' ').trim());

  const REST_W = 170, REST_WD = 68, PEAK_W = 900, PEAK_WD = 150;
  let mode = RM ? 'drift' : 'sweep';
  let target = { x: -200, y: 0 };
  let pos = { x: -200, y: 0 };
  let sweepT0 = null;
  let idleTimer = null;
  let heroVisible = true;
  let peak = { w: REST_W, wd: REST_WD };
  let lastRead = '';
  let rafId = null;

  function accentRgb() {
    const raw = getComputedStyle(document.documentElement).getPropertyValue('--color-accent').trim() || '#2B1FE0';
    const hex = raw.replace('#', '');
    if (hex.length === 6) {
      return [parseInt(hex.slice(0, 2), 16), parseInt(hex.slice(2, 4), 16), parseInt(hex.slice(4, 6), 16)];
    }
    return [43, 31, 224];
  }
  function inkRgb() {
    const raw = getComputedStyle(document.documentElement).getPropertyValue('--color-text').trim() || '#16140E';
    const hex = raw.replace('#', '');
    if (hex.length === 6) {
      return [parseInt(hex.slice(0, 2), 16), parseInt(hex.slice(2, 4), 16), parseInt(hex.slice(4, 6), 16)];
    }
    return [22, 20, 14];
  }

  function staticRun() {
    title.querySelectorAll('.hero-line').forEach((line) => {
      const chs = [...line.querySelectorAll('.hl-ch')];
      chs.forEach((el, i) => {
        const p = chs.length > 1 ? i / (chs.length - 1) : 0;
        el.style.fontVariationSettings =
          `"wght" ${Math.round(lerp(120, 880, p))}, "wdth" ${Math.round(lerp(64, 140, p))}`;
      });
    });
  }

  function tick(t) {
    if (!heroVisible) return;
    const hr = heroEl.getBoundingClientRect();
    const tr = title.getBoundingClientRect();
    const cy = tr.top + tr.height / 2;
    const INK = inkRgb();
    const ULTRA = accentRgb();

    if (mode === 'sweep') {
      if (sweepT0 === null) sweepT0 = t;
      const p = clamp((t - sweepT0) / 1500, 0, 1);
      const e = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
      target.x = hr.left - 120 + (hr.width + 240) * e;
      target.y = cy;
      if (p >= 1) mode = 'drift';
    } else if (mode === 'drift') {
      if (RM) {
        staticRun();
        if (lens) lens.classList.remove('on');
        rafId = null;
        return;
      }
      const s = t / 1000;
      target.x = hr.left + hr.width * (0.5 + 0.40 * Math.sin(s * 0.42));
      target.y = cy + tr.height * 0.38 * Math.sin(s * 0.83 + 1.3);
    }

    pos.x = lerp(pos.x, target.x, 0.13);
    pos.y = lerp(pos.y, target.y, 0.13);

    const sigma = Math.max(120, hr.width * 0.105);
    const inv2s2 = 1 / (2 * sigma * sigma);
    let best = 0, bestL = null;

    for (const L of letters) {
      const r = L.el.getBoundingClientRect();
      const dx = (r.left + r.width / 2) - pos.x;
      const dy = (r.top + r.height / 2) - pos.y;
      const f = Math.exp(-(dx * dx + dy * dy) * inv2s2);
      if (f > best) { best = f; bestL = L; }
      const w = Math.round(REST_W + (PEAK_W - REST_W) * f);
      const wd = Math.round((REST_WD + (PEAK_WD - REST_WD) * f) * 2) / 2;
      if (Math.abs(w - L.w) >= 1 || Math.abs(wd - L.wd) >= 0.5) {
        L.w = w; L.wd = wd;
        L.el.style.fontVariationSettings = `"wght" ${w}, "wdth" ${wd}`;
      }
      if (!RM) {
        const lift = f > 0.04 ? -(f * 0.055) : 0;
        if (Math.abs(lift - L.lift) > 0.0025) {
          L.lift = lift;
          L.el.style.transform = lift ? `translateY(${lift.toFixed(4)}em)` : '';
        }
      }
      const h = f < 0.72 ? 0 : (f - 0.72) / 0.28;
      if (Math.abs(h - L.heat) > 0.04) {
        L.heat = h;
        L.el.style.color = h === 0 ? '' :
          `rgb(${Math.round(lerp(INK[0], ULTRA[0], h))},${Math.round(lerp(INK[1], ULTRA[1], h))},${Math.round(lerp(INK[2], ULTRA[2], h))})`;
      }
    }

    peak.w = Math.round(REST_W + (PEAK_W - REST_W) * best);
    peak.wd = Math.round(REST_WD + (PEAK_WD - REST_WD) * best);
    if (lens) {
      lens.style.transform = `translate(${(pos.x - hr.left).toFixed(1)}px, ${(pos.y - hr.top).toFixed(1)}px)`;
      lens.classList.toggle('flip', pos.x - hr.left > hr.width - 160);
    }
    const ch = best > 0.3 && bestL ? bestL.el.textContent : null;
    const html = (ch && ch !== '\u00a0'
      ? `<b>${ch}</b> U+${ch.codePointAt(0).toString(16).toUpperCase().padStart(4, '0')}<br>`
      : '') + `wght ${String(peak.w).padStart(3, '0')}<br>wdth ${String(peak.wd).padStart(3, '0')}`;
    if (read && html !== lastRead) { lastRead = html; read.innerHTML = html; }

    rafId = requestAnimationFrame(tick);
  }

  function wake() {
    if (rafId === null && heroVisible) rafId = requestAnimationFrame(tick);
  }

  heroEl.addEventListener('pointermove', (e) => {
    if (mode === 'sweep') return;
    mode = 'pointer';
    target.x = e.clientX;
    target.y = e.clientY;
    if (lens) lens.classList.add('on');
    if (RM) wake();
    clearTimeout(idleTimer);
    idleTimer = setTimeout(() => { mode = 'drift'; }, 3200);
  });
  heroEl.addEventListener('pointerleave', () => {
    clearTimeout(idleTimer);
    if (mode !== 'sweep') mode = 'drift';
    if (RM && lens) lens.classList.remove('on');
  });

  if ('IntersectionObserver' in window) {
    new IntersectionObserver(([en]) => {
      heroVisible = en.isIntersecting;
      if (heroVisible && !(RM && mode === 'drift')) wake();
      else if (!heroVisible && rafId) {
        cancelAnimationFrame(rafId);
        rafId = null;
      }
    }, { threshold: 0.05 }).observe(heroEl);
  }

  const start = () => {
    letters.forEach((L, i) => {
      L.el.style.transitionDelay = `${i * 26}ms, ${i * 26}ms`;
    });
    title.classList.add('hero-in');
    setTimeout(() => title.classList.add('hero-live'), 900);
    if (!RM) wake();
    else staticRun();
  };
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(() => requestAnimationFrame(start));
  } else {
    requestAnimationFrame(start);
  }
}
