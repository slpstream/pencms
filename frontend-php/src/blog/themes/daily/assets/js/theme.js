/**
 * Daily — theme toggle, mobile drawer, dropdowns.
 * Parent <a> links always navigate. Submenus open on hover (fine pointer),
 * or via the caret / label-only triggers on touch.
 */
document.addEventListener('DOMContentLoaded', function () {
  initThemeToggle();
  initMobileMenu();
  initDropdownMenus();
  initCopyLinks();
});

function initThemeToggle() {
  const toggleBtns = document.querySelectorAll('[data-theme-toggle]');
  if (!toggleBtns.length) return;

  function isDark() {
    return document.documentElement.classList.contains('cm-wysiwym-dark') ||
      document.documentElement.getAttribute('data-theme') === 'dark' ||
      (!document.documentElement.getAttribute('data-theme') && window.matchMedia('(prefers-color-scheme: dark)').matches);
  }

  function restyleMermaid(dark) {
    if (typeof mermaid === 'undefined' || !mermaid.initialize) return;
    const nodes = document.querySelectorAll('.mermaid');
    if (!nodes.length) return;

    try {
      mermaid.initialize({
        startOnLoad: false,
        theme: dark ? 'dark' : 'default'
      });
    } catch (err) {}

    nodes.forEach(function (el) {
      const src = el.getAttribute('data-src');
      if (src) el.textContent = src;
      el.removeAttribute('data-processed');
    });

    if (typeof mermaid.run === 'function') {
      mermaid.run({ querySelector: '.mermaid' }).catch(function () {});
    } else if (typeof mermaid.init === 'function') {
      mermaid.init(undefined, nodes);
    }
  }

  function apply(theme, opts) {
    document.documentElement.classList.toggle('cm-wysiwym-dark', theme === 'dark');
    document.documentElement.setAttribute('data-theme', theme);
    toggleBtns.forEach(function (btn) {
      btn.setAttribute('aria-checked', theme === 'dark' ? 'true' : 'false');
      btn.setAttribute('aria-label', theme === 'dark' ? 'Dark mode on' : 'Dark mode off');
    });
    try {
      localStorage.setItem('color-scheme', theme);
      localStorage.setItem('theme', theme);
    } catch (e) {}
    try {
      document.cookie = 'color-scheme=' + theme + '; path=/; max-age=31536000; SameSite=Lax';
      document.cookie = 'theme=' + theme + '; path=/; max-age=31536000; SameSite=Lax';
    } catch (e) {}
    if (!opts || !opts.skipMermaid) {
      restyleMermaid(theme === 'dark');
    }
  }

  apply(isDark() ? 'dark' : 'light', { skipMermaid: true });
  toggleBtns.forEach(function (toggleBtn) {
    toggleBtn.addEventListener('click', function () {
      apply(isDark() ? 'light' : 'dark');
    });
  });
}

function setItemOpen(item, open) {
  item.classList.toggle('open', open);
  item.querySelectorAll('[aria-expanded]').forEach(function (el) {
    el.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
}

function closeOpenItems(navMenu) {
  navMenu.querySelectorAll('.nav-item.has-children.open').forEach(function (item) {
    setItemOpen(item, false);
  });
}

function initMobileMenu() {
  const menuToggle = document.getElementById('mobile-menu-toggle');
  const navMenu = document.getElementById('nav-menu');
  if (!menuToggle || !navMenu) return;

  function setDrawerOpen(isOpen) {
    navMenu.classList.toggle('active', isOpen);
    menuToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    menuToggle.setAttribute('aria-label', isOpen ? 'Close menu' : 'Toggle menu');
    if (!isOpen) closeOpenItems(navMenu);
  }

  menuToggle.addEventListener('click', function (e) {
    e.stopPropagation();
    setDrawerOpen(!navMenu.classList.contains('active'));
  });

  document.addEventListener('click', function (e) {
    if (
      navMenu.classList.contains('active') &&
      !navMenu.contains(e.target) &&
      e.target !== menuToggle &&
      !menuToggle.contains(e.target)
    ) {
      setDrawerOpen(false);
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape' || !navMenu.classList.contains('active')) return;
    setDrawerOpen(false);
    menuToggle.focus();
  });
}

function initDropdownMenus() {
  const navMenu = document.getElementById('nav-menu');
  if (!navMenu) return;

  const prefersHover = function () {
    return window.matchMedia('(hover: hover) and (pointer: fine)').matches;
  };

  navMenu.querySelectorAll('.nav-item.has-children').forEach(function (item) {
    let mouseleaveTimer = null;
    const caret = item.querySelector('.nav-caret');
    const labelTrigger = item.querySelector('.nav-trigger');

    const cancelClose = function () {
      if (mouseleaveTimer) {
        clearTimeout(mouseleaveTimer);
        mouseleaveTimer = null;
      }
    };

    const toggleOpen = function (e) {
      e.preventDefault();
      e.stopPropagation();
      cancelClose();
      if (prefersHover()) {
        setItemOpen(item, true);
        return;
      }
      setItemOpen(item, !item.classList.contains('open'));
    };

    item.addEventListener('mouseenter', function () {
      if (!prefersHover()) return;
      cancelClose();
      setItemOpen(item, true);
    });

    item.addEventListener('mouseleave', function () {
      if (!prefersHover()) return;
      mouseleaveTimer = setTimeout(function () {
        setItemOpen(item, false);
      }, 200);
    });

    if (caret) caret.addEventListener('click', toggleOpen);

    if (labelTrigger) {
      labelTrigger.addEventListener('click', toggleOpen);
      labelTrigger.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') toggleOpen(e);
      });
    }
  });
}

function initCopyLinks() {
  document.querySelectorAll('[data-copy-link]').forEach(function (el) {
    el.addEventListener('click', function (e) {
      e.preventDefault();
      const href = el.getAttribute('href');
      if (href && navigator.clipboard) {
        navigator.clipboard.writeText(href);
      }
    });
  });
}
