/**
 * Pulp — ticker, woodcut letters, spread shelf, sturdy dropdowns.
 * Light-only: no theme toggle.
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', () => {
    initMobileMenu();
    initDropdownMenus();
    initPulpPress();
  });

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
          if (window.matchMedia('(max-width: 820px)').matches) {
            e.preventDefault();
            e.stopPropagation();
            item.classList.toggle('open');
          }
        });
      }
    });
  }

  function escapeHtml(ch) {
    return String(ch)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function splitWoodcut(el) {
    if (!el) return;
    const name = (el.getAttribute('data-name') || el.textContent || '').trim();
    if (!name) return;
    el.setAttribute('aria-label', name);
    let html = '';
    let letters = 0;
    let longest = 1;
    const tokens = name.split(/(\s+)/);
    for (let t = 0; t < tokens.length; t++) {
      const token = tokens[t];
      if (!token) continue;
      if (/^\s+$/.test(token)) {
        html += '<span class="ml-space">&nbsp;</span>';
        continue;
      }
      let inner = '';
      let wordLetters = 0;
      for (let i = 0; i < token.length; i++) {
        const esc = escapeHtml(token.charAt(i));
        inner += '<span class="ml" data-l="' + esc + '"><i>' + esc + '</i></span>';
        letters += 1;
        wordLetters += 1;
      }
      if (wordLetters > longest) longest = wordLetters;
      html += '<span class="ml-word">' + inner + '</span>';
    }
    el.innerHTML = html;
    el.style.setProperty('--letters', String(Math.max(letters, 1)));
    el.style.setProperty('--longest', String(Math.max(longest, 1)));
  }

  function initPulpPress() {
    const docEl = document.documentElement;
    docEl.classList.add('js');

    const motionMQ = window.matchMedia('(prefers-reduced-motion: reduce)');
    let reduceMotion = motionMQ.matches;

    document.addEventListener('visibilitychange', function () {
      docEl.classList.toggle('tab-hidden', document.hidden);
    });

    splitWoodcut(document.getElementById('mastTitle'));
    splitWoodcut(document.getElementById('postWoodcut'));

    const track = document.getElementById('tickerTrack');
    if (track) {
      const set = track.querySelector('.tk-set');
      if (set) {
        const clone = set.cloneNode(true);
        clone.setAttribute('aria-hidden', 'true');
        clone.querySelectorAll('a').forEach((a) => {
          a.setAttribute('tabindex', '-1');
        });
        track.appendChild(clone);
        const setTickerSpeed = function () {
          const setWidth = track.scrollWidth / 2;
          track.style.setProperty('--roll-dur', Math.max(30, Math.round(setWidth / 85)) + 's');
        };
        setTickerSpeed();
        if (document.fonts && document.fonts.ready) document.fonts.ready.then(setTickerSpeed);
      }
    }

    const masthead = document.querySelector('.masthead');
    let pressTimers = [];
    const replay = document.getElementById('replayBtn');

    function clearPress() {
      if (!masthead) return;
      pressTimers.forEach(clearTimeout);
      pressTimers = [];
      masthead.classList.remove('printing', 'p1', 'p2', 'done');
    }

    function runPress() {
      if (reduceMotion || !masthead) return;
      clearPress();
      masthead.classList.add('printing');
      void masthead.offsetWidth;
      pressTimers.push(setTimeout(function () { masthead.classList.add('p1'); }, 250));
      pressTimers.push(setTimeout(function () { masthead.classList.add('p2'); }, 1400));
      pressTimers.push(setTimeout(function () { masthead.classList.add('done'); }, 2500));
      pressTimers.push(setTimeout(function () {
        masthead.classList.remove('printing', 'p1', 'p2');
      }, 4600));
    }

    runPress();
    if (replay) {
      replay.hidden = reduceMotion;
      replay.addEventListener('click', function () {
        if (reduceMotion) return;
        runPress();
      });
    }

    const revealEls = Array.prototype.slice.call(document.querySelectorAll('.reveal'));
    if ('IntersectionObserver' in window && !reduceMotion) {
      const io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('in');
            io.unobserve(entry.target);
          }
        });
      }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
      revealEls.forEach(function (el, i) {
        el.style.transitionDelay = (i % 3) * 70 + 'ms';
        io.observe(el);
      });
    } else {
      revealEls.forEach(function (el) { el.classList.add('in'); });
    }

    const shelf = document.getElementById('shelf');
    const posEl = document.getElementById('shelfPos');
    const spreads = shelf ? Array.prototype.slice.call(shelf.querySelectorAll('.spread')) : [];

    function currentIndex() {
      if (!shelf) return 0;
      const mid = shelf.scrollLeft + shelf.clientWidth / 2;
      let best = 0;
      let bestDist = Infinity;
      spreads.forEach(function (sp, i) {
        const c = sp.offsetLeft + sp.offsetWidth / 2;
        const d = Math.abs(c - mid);
        if (d < bestDist) { bestDist = d; best = i; }
      });
      return best;
    }

    function updatePos() {
      if (!posEl || !spreads.length) return;
      posEl.textContent = 'SPREAD ' + (currentIndex() + 1) + ' OF ' + spreads.length;
    }

    function goTo(i) {
      if (!shelf || !spreads.length) return;
      i = Math.max(0, Math.min(spreads.length - 1, i));
      const sp = spreads[i];
      const target = sp.offsetLeft + sp.offsetWidth / 2 - shelf.clientWidth / 2;
      shelf.scrollTo({ left: target, behavior: reduceMotion ? 'auto' : 'smooth' });
    }

    if (shelf) {
      let posTick = null;
      shelf.addEventListener('scroll', function () {
        if (posTick) return;
        posTick = setTimeout(function () { posTick = null; updatePos(); }, 80);
      }, { passive: true });
      updatePos();

      const prev = document.getElementById('shelfPrev');
      const next = document.getElementById('shelfNext');
      if (prev) prev.addEventListener('click', function () { goTo(currentIndex() - 1); });
      if (next) next.addEventListener('click', function () { goTo(currentIndex() + 1); });

      let dragging = false;
      let dragStartX = 0;
      let dragStartScroll = 0;
      let moved = false;
      shelf.addEventListener('pointerdown', function (e) {
        if (e.pointerType !== 'mouse') return;
        dragging = true;
        moved = false;
        dragStartX = e.clientX;
        dragStartScroll = shelf.scrollLeft;
      });
      window.addEventListener('pointermove', function (e) {
        if (!dragging) return;
        const dx = e.clientX - dragStartX;
        if (Math.abs(dx) > 6 && !moved) {
          moved = true;
          shelf.classList.add('dragging');
          if (window.getSelection) window.getSelection().removeAllRanges();
        }
        if (moved) shelf.scrollLeft = dragStartScroll - dx;
      });
      window.addEventListener('pointerup', function () {
        if (!dragging) return;
        dragging = false;
        if (moved) {
          shelf.classList.remove('dragging');
          goTo(currentIndex());
        }
      });

      shelf.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowRight') { e.preventDefault(); goTo(currentIndex() + 1); }
        if (e.key === 'ArrowLeft') { e.preventDefault(); goTo(currentIndex() - 1); }
      });
    }

    Array.prototype.forEach.call(document.querySelectorAll('.card, .spread'), function (el) {
      let offT = null;
      el.addEventListener('touchstart', function () {
        clearTimeout(offT);
        el.classList.add('reg');
      }, { passive: true });
      el.addEventListener('touchend', function () {
        clearTimeout(offT);
        offT = setTimeout(function () { el.classList.remove('reg'); }, 900);
      });
      el.addEventListener('touchcancel', function () {
        clearTimeout(offT);
        el.classList.remove('reg');
      });
    });

    let driftNow = 1;
    let driftTarget = 1;
    let driftRaf = null;
    let lastY = window.pageYOffset;
    let lastT = performance.now();
    function stopDrift() {
      if (driftRaf) { cancelAnimationFrame(driftRaf); driftRaf = null; }
      driftNow = 1;
      driftTarget = 1;
      docEl.style.setProperty('--drift', '1');
    }
    const driftTick = function () {
      driftTarget = Math.max(1, driftTarget - 0.045);
      driftNow += (driftTarget - driftNow) * 0.14;
      docEl.style.setProperty('--drift', driftNow.toFixed(3));
      if (driftTarget > 1 || Math.abs(driftNow - 1) > 0.012) {
        driftRaf = requestAnimationFrame(driftTick);
      } else {
        driftNow = 1;
        driftRaf = null;
        docEl.style.setProperty('--drift', '1');
      }
    };
    window.addEventListener('scroll', function () {
      if (reduceMotion) return;
      const y = window.pageYOffset;
      const now = performance.now();
      const v = Math.abs(y - lastY) / Math.max(16, now - lastT);
      lastY = y;
      lastT = now;
      driftTarget = Math.min(2.4, Math.max(driftTarget, 1 + v * 0.55));
      if (!driftRaf && !document.hidden) driftRaf = requestAnimationFrame(driftTick);
    }, { passive: true });

    if ('IntersectionObserver' in window) {
      const sleeper = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          en.target.classList.toggle('asleep', !en.isIntersecting);
        });
      });
      const tickerBar = document.querySelector('.ticker');
      if (tickerBar) sleeper.observe(tickerBar);
    }

    function onMotionChange() {
      reduceMotion = motionMQ.matches;
      if (replay) replay.hidden = reduceMotion;
      if (reduceMotion) { clearPress(); stopDrift(); }
    }
    if (motionMQ.addEventListener) motionMQ.addEventListener('change', onMotionChange);
    else if (motionMQ.addListener) motionMQ.addListener(onMotionChange);
  }
})();
