/**
 * Coldcase — mobile drawer + sturdy dropdown hover grace.
 * Parent <a> links always navigate. Submenus open on hover/focus,
 * or via the caret (and label-only triggers) on touch.
 */
document.addEventListener('DOMContentLoaded', () => {
  initMobileMenu();
  initDropdownMenus();
});

function setItemOpen(item, open) {
  item.classList.toggle('open', open);
  item.querySelectorAll('[aria-expanded]').forEach((el) => {
    el.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
}

function closeOpenItems(navMenu) {
  navMenu.querySelectorAll('.nav-item.has-children.open').forEach((item) => {
    setItemOpen(item, false);
  });
}

function initMobileMenu() {
  const menuToggle = document.getElementById('mobile-menu-toggle');
  const navMenu = document.getElementById('nav-menu');
  if (!menuToggle || !navMenu) return;

  function setDrawerOpen(isOpen) {
    navMenu.classList.toggle('active', isOpen);
    document.body.classList.toggle('cc-nav-open', isOpen);
    menuToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    menuToggle.setAttribute('aria-label', isOpen ? 'Close menu' : 'Open menu');
    if (!isOpen) closeOpenItems(navMenu);
  }

  menuToggle.addEventListener('click', (e) => {
    e.stopPropagation();
    setDrawerOpen(!navMenu.classList.contains('active'));
  });

  document.addEventListener('click', (e) => {
    if (
      navMenu.classList.contains('active') &&
      !navMenu.contains(e.target) &&
      e.target !== menuToggle &&
      !menuToggle.contains(e.target)
    ) {
      setDrawerOpen(false);
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape' || !navMenu.classList.contains('active')) return;
    setDrawerOpen(false);
    menuToggle.focus();
  });
}

function initDropdownMenus() {
  const navMenu = document.getElementById('nav-menu');
  if (!navMenu) return;

  const prefersHover = () =>
    window.matchMedia('(hover: hover) and (pointer: fine)').matches;

  navMenu.querySelectorAll('.nav-item.has-children').forEach((item) => {
    let mouseleaveTimer = null;
    const caret = item.querySelector('.nav-caret');
    const labelTrigger = item.querySelector('.nav-trigger');

    const cancelClose = () => {
      if (mouseleaveTimer) {
        clearTimeout(mouseleaveTimer);
        mouseleaveTimer = null;
      }
    };

    const toggleOpen = (e) => {
      e.preventDefault();
      e.stopPropagation();
      cancelClose();
      if (prefersHover()) {
        setItemOpen(item, true);
        return;
      }
      setItemOpen(item, !item.classList.contains('open'));
    };

    item.addEventListener('mouseenter', () => {
      if (!prefersHover()) return;
      cancelClose();
      setItemOpen(item, true);
    });

    item.addEventListener('mouseleave', () => {
      if (!prefersHover()) return;
      mouseleaveTimer = setTimeout(() => {
        setItemOpen(item, false);
      }, 200);
    });

    if (caret) caret.addEventListener('click', toggleOpen);

    if (labelTrigger) {
      labelTrigger.addEventListener('click', toggleOpen);
      labelTrigger.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') toggleOpen(e);
      });
    }
  });
}
