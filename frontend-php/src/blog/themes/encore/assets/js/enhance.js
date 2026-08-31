// enhance.js — progressive enhancement for manual light/dark toggle.
document.addEventListener("DOMContentLoaded", function() {
  // Interactive Light / Dark mode toggle button (#theme-toggle)
  const toggleBtn = document.getElementById('theme-toggle');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', function() {
      const root = document.documentElement;
      const currentTheme = root.getAttribute('data-theme');
      
      let nextTheme;
      if (currentTheme === 'light') {
        nextTheme = 'dark';
      } else if (currentTheme === 'dark') {
        nextTheme = 'light';
      } else {
        // Fallback: inspect system preference
        const prefersLight = window.matchMedia('(prefers-color-scheme: light)').matches;
        nextTheme = prefersLight ? 'dark' : 'light';
      }

      root.setAttribute('data-theme', nextTheme);
      try {
        localStorage.setItem('encore-theme', nextTheme);
      } catch (e) {}
    });
  }
});
