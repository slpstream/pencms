/**
 * Freedomware Theme JavaScript
 * Dark mode toggle (light default), mobile nav drawer, sturdy dropdowns.
 */

document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
  initMobileMenu();
  initDropdownMenus();
  initImageModal();
});

/**
 * Theme toggle (light/dark).
 * Persists to localStorage + cookie. Light is default when unset.
 */
function initThemeToggle() {
  const toggleBtn = document.getElementById('theme-toggle');
  if (!toggleBtn) return;

  toggleBtn.addEventListener('click', () => {
    const isDark = document.documentElement.classList.contains('cm-wysiwym-dark');
    const newTheme = isDark ? 'light' : 'dark';

    if (newTheme === 'dark') {
      document.documentElement.classList.add('cm-wysiwym-dark');
    } else {
      document.documentElement.classList.remove('cm-wysiwym-dark');
    }

    try { localStorage.setItem('color-scheme', newTheme); } catch (e) {}
    try {
      document.cookie = 'color-scheme=' + newTheme + '; path=/; max-age=31536000; SameSite=Lax';
    } catch (e) {}

    const metaTag = document.querySelector('meta[name="color-scheme"]');
    if (metaTag) {
      metaTag.content = newTheme === 'dark' ? 'dark' : 'light';
    }

    // Re-init Mermaid theme if present
    if (typeof mermaid !== 'undefined' && mermaid.initialize) {
      try {
        mermaid.initialize({
          startOnLoad: false,
          theme: newTheme === 'dark' ? 'dark' : 'default'
        });
      } catch (err) {}
    }
  });
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
 * Sturdy dropdown menus with hover grace delay (200ms).
 */
function initDropdownMenus() {
  const navMenu = document.getElementById('nav-menu');
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
 * Image Modal Lightbox (scoped to post.html.twig and page.html.twig content).
 */
function initImageModal() {
  const images = document.querySelectorAll('.article-content img, .post-hero-image-wrapper img');
  if (!images.length) return;

  let modal = document.getElementById('fw-image-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'fw-image-modal';
    modal.className = 'fw-image-modal';
    modal.setAttribute('aria-hidden', 'true');
    modal.innerHTML = `
      <div class="fw-image-modal-container">
        <button type="button" class="fw-image-modal-close" aria-label="Close modal">&times;</button>
        <img class="fw-image-modal-img" src="" alt="">
        <div class="fw-image-modal-caption"></div>
      </div>
    `;
    document.body.appendChild(modal);

    const closeBtn = modal.querySelector('.fw-image-modal-close');
    const closeModal = () => {
      modal.classList.remove('open');
      modal.setAttribute('aria-hidden', 'true');
    };

    closeBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
      if (e.target === modal || e.target.classList.contains('fw-image-modal-container')) {
        closeModal();
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && modal.classList.contains('open')) {
        closeModal();
      }
    });
  }

  const modalImg = modal.querySelector('.fw-image-modal-img');
  const modalCaption = modal.querySelector('.fw-image-modal-caption');

  images.forEach((img) => {
    img.addEventListener('click', () => {
      modalImg.src = img.src;
      modalImg.alt = img.alt || '';

      let captionText = img.alt || img.title || '';
      const figure = img.closest('figure');
      if (figure) {
        const figcaption = figure.querySelector('figcaption');
        if (figcaption) {
          captionText = figcaption.textContent.trim();
        }
      }

      modalCaption.textContent = captionText;
      modalCaption.style.display = captionText ? 'block' : 'none';

      modal.classList.add('open');
      modal.setAttribute('aria-hidden', 'false');
    });
  });
}
