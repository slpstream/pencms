// theme.js — progressive enhancement for Cause theme.
// The hero's impact stat number counts up when scrolled into view.
// Decorative, skipped for reduced-motion users, real value stays in rendered HTML.

document.addEventListener('DOMContentLoaded', function () {
  initThemeToggle();

  const number = document.querySelector('.impact-number');
  const motionOk = window.matchMedia && window.matchMedia('(prefers-reduced-motion: no-preference)').matches;


  if (number && motionOk && 'IntersectionObserver' in window) {
    const finalText = number.textContent.trim();
    const target = Number(finalText.replace(/[^\d]/g, ''));
    const suffix = finalText.replace(/^[\d,.\s]+/, '');
    const grouped = finalText.includes(',');

    if (target > 0 && target < 10000000) {
      const format = function (n) {
        return (grouped ? n.toLocaleString('en-US') : String(n)) + suffix;
      };

      const observer = new IntersectionObserver(function (entries) {
        if (!entries.some(function (entry) { return entry.isIntersecting; })) return;
        observer.disconnect();

        const started = performance.now();
        const tick = function (now) {
          const progress = Math.min((now - started) / 900, 1);
          const eased = 1 - Math.pow(1 - progress, 3);
          number.textContent = format(Math.round(target * eased));
          if (progress < 1) {
            requestAnimationFrame(tick);
          } else {
            number.textContent = finalText;
          }
        };
        requestAnimationFrame(tick);
      });

      observer.observe(number);
    }
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

