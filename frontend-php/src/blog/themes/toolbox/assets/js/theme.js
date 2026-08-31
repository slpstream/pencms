/**
 * Toolbox theme JS — mobile nav, dropdown grace, before/after image pairs.
 */
document.addEventListener('DOMContentLoaded', function () {
  initThemeToggle();

  var toggle = document.getElementById('mobile-menu-toggle');

  var menu = document.getElementById('nav-menu');

  if (toggle && menu) {
    toggle.addEventListener('click', function () {
      menu.classList.toggle('is-active');
      var expanded = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', (!expanded).toString());
    });
  }

  var hasChildren = document.querySelectorAll('.nav-item.has-children');
  hasChildren.forEach(function (item) {
    var timer = null;
    item.addEventListener('mouseenter', function () {
      if (timer) clearTimeout(timer);
      item.classList.add('is-open');
    });
    item.addEventListener('mouseleave', function () {
      timer = setTimeout(function () {
        item.classList.remove('is-open');
      }, 150);
    });
  });

  // Before/after gallery: two images whose alt starts with Before/After
  document.querySelectorAll('.article-content p').forEach(function (p) {
    var imgs = p.querySelectorAll('img');
    if (imgs.length !== 2 || p.childElementCount !== 2) return;
    var first = (imgs[0].alt || '').trim().toLowerCase();
    var second = (imgs[1].alt || '').trim().toLowerCase();
    if (!first.startsWith('before') || !second.startsWith('after')) return;
    p.classList.add('before-after');
    imgs.forEach(function (img, index) {
      var figure = document.createElement('figure');
      var caption = document.createElement('figcaption');
      caption.textContent = index === 0 ? 'Before' : 'After';
      img.replaceWith(figure);
      figure.append(img, caption);
    });
  });
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

