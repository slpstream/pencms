// Gazette Theme — progressive enhancement & theme toggle
document.addEventListener("DOMContentLoaded", function () {
  initThemeToggle();
});

function initThemeToggle() {
  const toggleBtns = document.querySelectorAll('[data-theme-toggle], #theme-toggle');
  if (!toggleBtns.length) return;

  toggleBtns.forEach(function (toggleBtn) {
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
  });
}
