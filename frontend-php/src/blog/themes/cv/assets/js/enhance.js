// enhance.js — progressive enhancement for CV theme.
// Replaces the static keyboard print hint with an interactive Print button.

document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();

  const hint = document.querySelector('.cv-print .print-hint');
  if (hint) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'print-button';
    button.textContent = 'Print this page';
    button.style.font = 'inherit';
    button.style.cursor = 'pointer';
    button.style.marginLeft = '0.5em';
    button.style.padding = '0.15em 0.5em';
    button.style.borderRadius = 'var(--radius, 3px)';
    button.style.border = '1px solid var(--color-border, #e2e4e7)';
    button.style.background = 'var(--color-code-bg, #f4f5f6)';
    button.style.color = 'var(--color-text, #26282b)';
    button.addEventListener('click', () => window.print());
    hint.replaceWith(button);
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

