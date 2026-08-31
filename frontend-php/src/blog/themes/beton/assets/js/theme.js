/**
 * Beton — mobile drawer, sturdy dropdowns, crane/reveal/measure.
 * Light-only: no theme toggle.
 */
document.addEventListener('DOMContentLoaded', () => {
  initMobileMenu();
  initDropdownMenus();
  initBetonMotion();
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

function initBetonMotion() {
  const docEl = document.documentElement;
  docEl.classList.add('js');

  const dimEl = document.querySelector('[data-vw]');
  const setDim = () => {
    if (dimEl) dimEl.textContent = Math.round(window.innerWidth) + ' PX';
  };
  setDim();
  window.addEventListener('resize', setDim, { passive: true });

  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (reduce.matches) {
    docEl.classList.add('static');
    return;
  }

  const veils = [...document.querySelectorAll('.reveal')];
  if ('IntersectionObserver' in window && veils.length) {
    veils.forEach((v) => v.classList.add('veiled'));
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add('revealed');
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.35 });
    veils.forEach((v) => io.observe(v));
  }
}
