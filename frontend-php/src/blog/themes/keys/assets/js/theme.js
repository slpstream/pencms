// Keys theme JavaScript - progressive enhancement
document.addEventListener('DOMContentLoaded', function () {
    initThemeToggle();

    // 1. Mobile menu toggle

    const toggleBtn = document.getElementById('mobile-menu-toggle');
    const navMenu = document.getElementById('nav-menu');

    if (toggleBtn && navMenu) {
        toggleBtn.addEventListener('click', function () {
            navMenu.classList.toggle('is-active');
            toggleBtn.classList.toggle('is-active');
            const expanded = toggleBtn.getAttribute('aria-expanded') === 'true';
            toggleBtn.setAttribute('aria-expanded', !expanded);
        });
    }

    // 2. Gallery keyboard navigation
    const photos = Array.from(document.querySelectorAll('.gallery img, .card-photo img'));
    if (photos.length > 1) {
        photos.forEach((img, i) => {
            img.tabIndex = 0;
            img.addEventListener('keydown', (event) => {
                const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
                if (!step) return;
                event.preventDefault();
                photos[(i + step + photos.length) % photos.length].focus();
            });
        });
    }
});

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

