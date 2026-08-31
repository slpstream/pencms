/**
 * Upstack Theme JavaScript
 * Handles theme toggle (Light/Dark mode with Light default), mobile navigation, and dropdown menus.
 */

document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
  initMobileMenu();
  initDropdownMenus();
});

/**
 * Initializes the theme toggle switch.
 * Synchronizes document element class with localStorage and prefers-color-scheme.
 */
function initThemeToggle() {
  const toggleBtns = document.querySelectorAll('#theme-toggle, .theme-toggle-btn');
  if (!toggleBtns || toggleBtns.length === 0) return;

  toggleBtns.forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const isDark = document.documentElement.classList.contains('cm-wysiwym-dark');
      const newTheme = isDark ? 'light' : 'dark';
      
      if (newTheme === 'dark') {
        document.documentElement.classList.add('cm-wysiwym-dark');
        document.documentElement.setAttribute('data-theme', 'dark');
      } else {
        document.documentElement.classList.remove('cm-wysiwym-dark');
        document.documentElement.removeAttribute('data-theme');
      }
      
      try {
        localStorage.setItem('color-scheme', newTheme);
        localStorage.setItem('theme', newTheme);
      } catch (err) {
        console.warn('localStorage is not accessible:', err);
      }

      try {
        document.cookie = "color-scheme=" + newTheme + "; path=/; max-age=31536000; SameSite=Lax";
      } catch (err) {
        console.warn('Cookie access error:', err);
      }
      
      const metaTag = document.querySelector('meta[name="color-scheme"]');
      if (metaTag) {
        metaTag.content = newTheme === 'dark' ? 'dark' : 'light';
      }
    });
  });

  // System color scheme change listener (only applies if user hasn't explicitly set preference)
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    let userOverride = null;
    try {
      userOverride = localStorage.getItem('color-scheme') || localStorage.getItem('theme');
    } catch (err) {}
    if (!userOverride) {
      try {
        const match = document.cookie.match(/(^|;)\s*color-scheme\s*=\s*([^;]+)/);
        userOverride = match ? match[2] : null;
      } catch (err) {}
    }
    if (!userOverride) {
      if (e.matches) {
        document.documentElement.classList.add('cm-wysiwym-dark');
        document.documentElement.setAttribute('data-theme', 'dark');
      } else {
        document.documentElement.classList.remove('cm-wysiwym-dark');
        document.documentElement.removeAttribute('data-theme');
      }
    }
  });
}

/**
 * Initializes mobile responsive navigation menu.
 */
function initMobileMenu() {
  const menuToggle = document.getElementById('mobile-menu-toggle');
  const navMenu = document.getElementById('nav-menu');
  if (!menuToggle || !navMenu) return;

  menuToggle.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    navMenu.classList.toggle('active');
    navMenu.classList.toggle('is-active');
  });

  document.addEventListener('click', (e) => {
    if ((navMenu.classList.contains('active') || navMenu.classList.contains('is-active')) && !navMenu.contains(e.target) && !menuToggle.contains(e.target)) {
      navMenu.classList.remove('active');
      navMenu.classList.remove('is-active');
      navMenu.querySelectorAll('.nav-item.has-children.open').forEach((item) => {
        item.classList.remove('open');
      });
    }
  });
}

/**
 * Initializes sturdy dropdown menus with hover grace delay.
 */
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
    if (trigger && trigger.tagName === 'BUTTON') {
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
