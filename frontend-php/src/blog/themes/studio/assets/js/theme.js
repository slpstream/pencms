/**
 * Studio Theme JavaScript — Progressive Enhancement & Sturdy Dropdowns
 */

document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
  initImageEnhancements();
  initMobileMenu();
  initDropdownMenus();
});


/**
 * Image ease-in loading effect for work cards & covers (from studio source enhance.js).
 */
function initImageEnhancements() {
  if (window.matchMedia('(prefers-reduced-motion: no-preference)').matches) {
    document.documentElement.classList.add('enhanced');
    const images = document.querySelectorAll('.work-card img, .project-cover img, .post-cover img, .prose img');
    images.forEach(img => {
      if (img.complete) {
        img.classList.add('is-loaded');
      } else {
        const reveal = () => img.classList.add('is-loaded');
        img.addEventListener('load', reveal, { once: true });
        img.addEventListener('error', reveal, { once: true });
      }
    });
  }
}

/**
 * Mobile navigation toggle.
 */
function initMobileMenu() {
  const menuToggle = document.getElementById('mobile-menu-toggle');
  const navMenu = document.getElementById('nav-menu');
  if (!menuToggle || !navMenu) return;

  menuToggle.addEventListener('click', (e) => {
    e.stopPropagation();
    navMenu.classList.toggle('active');
  });

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
 * Sturdy dropdown navigation with hover grace delay (PenCMS 3-slot menu contract).
 */
function initDropdownMenus() {
  const navMenus = document.querySelectorAll('.nav-menu, .site-head nav');
  navMenus.forEach(nav => {
    nav.querySelectorAll('.nav-item.has-children, li.has-children').forEach((item) => {
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

      const trigger = item.querySelector('.nav-trigger, a');
      if (trigger && item.querySelector('.sub-menu, .nav-children, ul')) {
        trigger.addEventListener('click', (e) => {
          if (window.matchMedia('(max-width: 768px)').matches) {
            e.preventDefault();
            e.stopPropagation();
            item.classList.toggle('open');
          }
        });
      }
    });
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

