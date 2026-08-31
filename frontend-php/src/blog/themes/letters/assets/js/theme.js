/**
 * Letters Theme JavaScript
 * Mobile navigation drawer + sturdy dropdown hover bridge / grace delay.
 * Progressive enhancement only — nothing is lost without JS.
 */

document.addEventListener('DOMContentLoaded', function () {
  initThemeToggle();

  // Mobile menu toggle

  const menuToggle = document.getElementById('mobile-menu-toggle');
  const navList = document.getElementById('letters-nav');
  if (menuToggle && navList) {
    menuToggle.addEventListener('click', function () {
      const isExpanded = menuToggle.getAttribute('aria-expanded') === 'true';
      menuToggle.setAttribute('aria-expanded', String(!isExpanded));
      navList.classList.toggle('is-open');
    });

    // Close the drawer when clicking outside any link and the toggle
    document.addEventListener('click', function (e) {
      if (navList.classList.contains('is-open') &&
          !navList.contains(e.target) &&
          !menuToggle.contains(e.target)) {
        navList.classList.remove('is-open');
        menuToggle.setAttribute('aria-expanded', 'false');
        closeAllDropdowns(navList);
      }
    });
  }

  // Sturdy dropdown hover bridge & grace delay for 2-level nested menus
  navList && navList.querySelectorAll('.has-children').forEach(function (parent) {
    let timeoutId = null;

    parent.addEventListener('mouseenter', function () {
      if (timeoutId) { clearTimeout(timeoutId); timeoutId = null; }
      parent.classList.add('is-open');
    });

    parent.addEventListener('mouseleave', function () {
      timeoutId = setTimeout(function () {
        parent.classList.remove('is-open');
      }, 200);
    });

    const trigger = parent.querySelector('.nav-trigger');
    if (trigger) {
      trigger.addEventListener('click', function (e) {
        if (window.matchMedia('(max-width: 48rem)').matches) {
          e.preventDefault();
          e.stopPropagation();
          parent.classList.toggle('is-open');
        }
      });
    }
  });
});

function closeAllDropdowns(root) {
  root.querySelectorAll('.has-children.is-open').forEach(function (el) {
    el.classList.remove('is-open');
  });
}

function initThemeToggle() {
  const toggleBtn = document.querySelector('[data-theme-toggle]') || document.getElementById('theme-toggle');
  if (!toggleBtn) return;

  toggleBtn.addEventListener('click', function () {
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
  });
}

