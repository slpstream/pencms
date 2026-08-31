/**
 * Penmanship Theme JavaScript
 * Handles the theme toggle (Light/Dark mode), mobile navigation drawer,
 * and reading progress bar.
 */

document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
  initMobileMenu();
  initDropdownMenus();
  initReadingProgress();
});

/**
 * Initializes the theme toggle switch.
 * Synchronizes document class with localStorage and prefers-color-scheme.
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
 * Initializes sturdy dropdown menus with hover grace delay (no flimsy closes).
 */
function initDropdownMenus() {
  const navMenu = document.getElementById('site-nav-links');
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

/**
 * Initializes the mobile responsive navigation toggle.
 */
function initMobileMenu() {
  const menuToggle = document.getElementById('mobile-menu-toggle');
  const navLinks = document.getElementById('site-nav-links');
  if (!menuToggle || !navLinks) return;

  menuToggle.addEventListener('click', (e) => {
    e.stopPropagation();
    const isOpen = navLinks.classList.toggle('open');
    menuToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');

    // Toggle between hamburger and close icon
    const menuIcon = menuToggle.querySelector('.menu-icon');
    const closeIcon = menuToggle.querySelector('.close-icon');
    if (menuIcon && closeIcon) {
      menuIcon.style.display = isOpen ? 'none' : 'block';
      closeIcon.style.display = isOpen ? 'block' : 'none';
    }
  });

  // Close menu if clicking outside of it
  document.addEventListener('click', (e) => {
    if (navLinks.classList.contains('open') && !navLinks.contains(e.target) && e.target !== menuToggle) {
      navLinks.classList.remove('open');
      menuToggle.setAttribute('aria-expanded', 'false');
      const menuIcon = menuToggle.querySelector('.menu-icon');
      const closeIcon = menuToggle.querySelector('.close-icon');
      if (menuIcon && closeIcon) {
        menuIcon.style.display = 'block';
        closeIcon.style.display = 'none';
      }
    }
  });
}

/**
 * Initializes the reading progress indicator bar.
 * Tracks scroll position and updates the bar width.
 */
function initReadingProgress() {
  const progressBar = document.querySelector('.reading-progress-bar');
  if (!progressBar) return;

  const updateProgress = () => {
    const scrollTop = window.scrollY;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    if (docHeight <= 0) {
      progressBar.style.width = '0%';
      return;
    }
    const progress = Math.min((scrollTop / docHeight) * 100, 100);
    progressBar.style.width = progress + '%';
  };

  window.addEventListener('scroll', updateProgress, { passive: true });
  window.addEventListener('resize', updateProgress, { passive: true });
  updateProgress();
}
