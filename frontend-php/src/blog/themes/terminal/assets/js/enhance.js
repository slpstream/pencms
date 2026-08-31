// enhance.js — progressive enhancement for terminal theme
// Adds:
//   1. language badge + copy button on fenced code blocks
//   2. table of contents on posts with >3 headings
//   3. keyboard navigation (j/k on post list, [ and ] for prev/next post)
//   4. light/dark theme toggle

const el = (tag, className, text) => {
  const node = document.createElement(tag);
  node.className = className;
  if (text) node.textContent = text;
  return node;
};

// --- 1. code blocks: language badge + copy button ---------------------------
for (const code of document.querySelectorAll('.prose pre > code, .article-content pre > code')) {
  const pre = code.parentElement;
  if (pre.classList.contains('static') || pre.querySelector('.code-bar')) continue;
  const lang = (code.className.match(/language-([\w+-]+)/) || [])[1];
  const bar = el('div', 'code-bar');
  bar.append(el('span', 'code-lang', lang || 'text'));
  if (navigator.clipboard) {
    const button = el('button', 'copy-code', 'copy');
    button.type = 'button';
    button.addEventListener('click', async () => {
      await navigator.clipboard.writeText(code.textContent);
      button.textContent = 'copied';
      setTimeout(() => { button.textContent = 'copy'; }, 1500);
    });
    bar.append(button);
  }
  pre.prepend(bar);
}

// --- 2. table of contents on longer posts -----------------------------------
const slugify = (text) => text.toLowerCase().replace(/[^\w]+/g, '-').replace(/^-+|-+$/g, '');
const prose = document.querySelector('.article-content, .prose');
const headings = prose ? [...prose.querySelectorAll('h2, h3')] : [];
const sidebarToc = document.getElementById('sidebar-toc');
const sidebarTocList = document.getElementById('sidebar-toc-list');

if (sidebarTocList && headings.length > 3 && sidebarTocList.children.length === 0) {
  for (const heading of headings) {
    if (!heading.id) heading.id = slugify(heading.textContent) || 'section';
    const item = el('li', `sidebar-list-item toc-${heading.tagName.toLowerCase()}`);
    const link = document.createElement('a');
    link.href = `#${heading.id}`;
    link.className = 'sidebar-list-link';
    link.textContent = heading.textContent;
    item.append(link);
    sidebarTocList.append(item);
  }
  if (sidebarToc) sidebarToc.style.display = 'block';
}

// --- 3. keyboard navigation --------------------------------------------------
const rows = [...document.querySelectorAll('.post-list h2 a, .post-row h2 a')];
const relHref = (rel) =>
  document.querySelector(`link[rel="${rel}"], a[rel="${rel}"]`)?.href;

const typing = (target) =>
  target.isContentEditable || /^(input|textarea|select)$/i.test(target.tagName);

document.addEventListener('keydown', (event) => {
  if (event.metaKey || event.ctrlKey || event.altKey || typing(event.target)) return;
  if (rows.length && (event.key === 'j' || event.key === 'k')) {
    const current = rows.indexOf(document.activeElement);
    const next = event.key === 'j'
      ? Math.min(current + 1, rows.length - 1)
      : Math.max(current - 1, 0);
    rows[next].focus();
    event.preventDefault();
  } else if (event.key === '[' || event.key === ']') {
    const href = relHref(event.key === '[' ? 'prev' : 'next');
    if (href) location.assign(href);
  }
});

// Document the keys — the hint exists only when the keys do.
const hints = [];
if (rows.length) hints.push('<kbd>j</kbd>/<kbd>k</kbd> move · <kbd>Enter</kbd> open');
if (relHref('prev') || relHref('next')) hints.push('<kbd>[</kbd>/<kbd>]</kbd> prev/next post');
const footer = document.querySelector('.colophon, .site-footer');
if (footer && hints.length && !footer.querySelector('.kbd-hint')) {
  const hint = el('p', 'kbd-hint');
  hint.innerHTML = hints.join(' · ');
  footer.append(hint);
}

// --- 4. light/dark theme toggle ----------------------------------------------
(function initThemeToggle() {
  const btn = document.getElementById('theme-toggle');
  const updateToggleUI = () => {
    const isLight = document.documentElement.classList.contains('theme-light');
    if (btn) {
      btn.setAttribute('aria-label', isLight ? 'Switch to dark mode' : 'Switch to light mode');
      btn.setAttribute('title', isLight ? 'Switch to dark mode' : 'Switch to light mode');
    }
  };

  if (btn) {
    btn.addEventListener('click', () => {
      const isLight = document.documentElement.classList.contains('theme-light');
      const newTheme = isLight ? 'dark' : 'light';

      if (newTheme === 'light') {
        document.documentElement.classList.add('theme-light');
        document.documentElement.classList.remove('cm-wysiwym-dark');
      } else {
        document.documentElement.classList.add('cm-wysiwym-dark');
        document.documentElement.classList.remove('theme-light');
      }

      try { localStorage.setItem('color-scheme', newTheme); } catch (e) {}
      try { document.cookie = "color-scheme=" + newTheme + "; path=/; max-age=31536000; SameSite=Lax"; } catch (e) {}
      updateToggleUI();
    });
    updateToggleUI();
  }

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    let saved = null;
    try { saved = localStorage.getItem('color-scheme'); } catch (err) {}
    if (!saved) {
      if (e.matches) {
        document.documentElement.classList.add('cm-wysiwym-dark');
        document.documentElement.classList.remove('theme-light');
      } else {
        document.documentElement.classList.add('theme-light');
        document.documentElement.classList.remove('cm-wysiwym-dark');
      }
      updateToggleUI();
    }
  });
})();
