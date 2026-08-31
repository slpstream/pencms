/**
 * Starter Theme JavaScript
 * Handles the theme toggle (Light/Dark mode) and mobile navigation drawer.
 */

document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
  initMobileMenu();
  initDropdownMenus();
});

/**
 * Initializes the theme toggle switch.
 * Synchronizes body class with localStorage and prefers-color-scheme.
 */
function initThemeToggle() {
  const toggleBtn = document.getElementById('theme-toggle');
  if (!toggleBtn) return;

  // Toggle theme on button click
  toggleBtn.addEventListener('click', () => {
    const isDark = document.documentElement.classList.contains('cm-wysiwym-dark');
    const newTheme = isDark ? 'light' : 'dark';
    
    // Update document class
    if (newTheme === 'dark') {
      document.documentElement.classList.add('cm-wysiwym-dark');
    } else {
      document.documentElement.classList.remove('cm-wysiwym-dark');
    }
    
    // Persist in localStorage and Cookie
    try {
      localStorage.setItem('color-scheme', newTheme);
    } catch (e) {
      console.warn('localStorage is not accessible:', e);
    }
    try {
      document.cookie = "color-scheme=" + newTheme + "; path=/; max-age=31536000; SameSite=Lax";
    } catch (e) {
      console.warn('Cookies are not accessible:', e);
    }
    
    // Update color-scheme meta tag if present
    const metaTag = document.querySelector('meta[name="color-scheme"]');
    if (metaTag) {
      metaTag.content = newTheme === 'dark' ? 'dark' : 'light';
    }
  });

  // Listen for system theme changes and sync if no user override is pinned
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    let userOverride = null;
    try {
      userOverride = localStorage.getItem('color-scheme');
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
      } else {
        document.documentElement.classList.remove('cm-wysiwym-dark');
      }
    }
  });
}

/**
 * Initializes the mobile responsive navigation toggle.
 */
function initMobileMenu() {
  const menuToggle = document.getElementById('mobile-menu-toggle');
  const navMenu = document.getElementById('nav-menu');
  if (!menuToggle || !navMenu) return;

  menuToggle.addEventListener('click', (e) => {
    e.stopPropagation();
    navMenu.classList.toggle('active');
  });

  // Close menu if clicking outside of it
  document.addEventListener('click', (e) => {
    if (navMenu.classList.contains('active') && !navMenu.contains(e.target) && e.target !== menuToggle) {
      navMenu.classList.remove('active');
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
