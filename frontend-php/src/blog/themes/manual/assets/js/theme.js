(() => {
  const root = document.documentElement;
  const toggle = document.querySelector('[data-theme-toggle]');
  const stored = localStorage.getItem('manual-color-scheme');
  const setMode = (mode) => {
    root.dataset.theme = mode;
    if (toggle) {
      const dark = mode === 'dark';
      toggle.setAttribute('aria-pressed', String(dark));
      toggle.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
    }
  };
  setMode(stored || 'light');
  toggle?.addEventListener('click', () => {
    const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('manual-color-scheme', next);
    setMode(next);
  });
  const button = document.querySelector('[data-menu-toggle]');
  const nav = document.querySelector('#primary-nav');
  button?.addEventListener('click', () => {
    const open = nav?.classList.toggle('is-open');
    button.setAttribute('aria-expanded', String(Boolean(open)));
  });
})();
