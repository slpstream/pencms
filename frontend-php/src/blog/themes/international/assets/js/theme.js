/**
 * Global — published chrome only.
 * Theme toggle (light/dark with persistent state), mobile drawer, dropdown menus.
 * Admin / editor never loads this file.
 */

document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
  initMobileMenu();
  initDropdownMenus();
});

function isGlobalDark() {
  const explicit = document.documentElement.getAttribute('data-theme');
  if (explicit === 'dark') return true;
  if (explicit === 'light') return false;
  return document.documentElement.classList.contains('cm-wysiwym-dark')
    || window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function restyleGlobalMermaid(isDark) {
  if (typeof mermaid === 'undefined' || !mermaid.initialize) return;
  try {
    mermaid.initialize({
      startOnLoad: false,
      theme: isDark ? 'dark' : 'neutral'
    });
  } catch (err) {}

  document.querySelectorAll('.mermaid').forEach((el) => {
    const src = el.getAttribute('data-src');
    if (src) {
      el.textContent = src;
    }
    el.removeAttribute('data-processed');
  });

  if (typeof mermaid.run === 'function') {
    mermaid.run({ querySelector: '.mermaid' }).catch(() => {});
  } else if (typeof mermaid.init === 'function') {
    mermaid.init(undefined, document.querySelectorAll('.mermaid'));
  }
}

window.applyGlobalColorScheme = function (theme) {
  const isDark = theme === 'dark';
  document.documentElement.classList.toggle('cm-wysiwym-dark', isDark);
  document.documentElement.setAttribute('data-theme', theme);

  const schemeMeta = document.querySelector('meta[name="color-scheme"]');
  if (schemeMeta) {
    schemeMeta.content = isDark ? 'dark' : 'light';
  }
  const themeColor = document.querySelector('meta[name="theme-color"]');
  if (themeColor) {
    themeColor.content = isDark ? '#161616' : '#f6f5f4';
  }

  restyleGlobalMermaid(isDark);
};

window.bootGlobalMermaid = function () {
  document.querySelectorAll('pre code.language-mermaid').forEach((codeBlock) => {
    const pre = codeBlock.parentNode;
    const div = document.createElement('div');
    div.className = 'mermaid';
    div.textContent = codeBlock.textContent;
    pre.replaceWith(div);
  });
  document.querySelectorAll('.mermaid').forEach((el) => {
    if (!el.getAttribute('data-src')) {
      el.setAttribute('data-src', el.textContent);
    }
  });
  restyleGlobalMermaid(isGlobalDark());
};

function initThemeToggle() {
  const toggleBtn = document.querySelector('[data-theme-toggle]') || document.getElementById('theme-toggle');
  if (!toggleBtn) return;

  toggleBtn.addEventListener('click', () => {
    const newTheme = isGlobalDark() ? 'light' : 'dark';

    try {
      localStorage.setItem('color-scheme', newTheme);
      localStorage.setItem('theme', newTheme);
    } catch (e) {}
    try {
      document.cookie = 'color-scheme=' + newTheme + '; path=/; max-age=31536000; SameSite=Lax';
      document.cookie = 'theme=' + newTheme + '; path=/; max-age=31536000; SameSite=Lax';
    } catch (e) {}

    window.applyGlobalColorScheme(newTheme);
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
      window.applyGlobalColorScheme(e.matches ? 'dark' : 'light');
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
