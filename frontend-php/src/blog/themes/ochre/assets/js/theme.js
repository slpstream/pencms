/**
 * Ochre — doorplate overlay + sturdy dropdown hover grace.
 * Dark-only: no theme toggle. No canvas / torch / reveal choreography.
 */
document.addEventListener('DOMContentLoaded', () => {
  initMobileMenu();
  initDropdownMenus();
});

function initMobileMenu() {
  const menuToggle = document.getElementById('mobile-menu-toggle');
  const navMenu = document.getElementById('nav-menu');
  if (!menuToggle || !navMenu) return;

  function setOpen(isOpen) {
    navMenu.classList.toggle('active', isOpen);
    document.body.classList.toggle('ochre-door-open', isOpen);
    menuToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    if (!isOpen) {
      navMenu.querySelectorAll('.nav-item.has-children.open').forEach((item) => {
        item.classList.remove('open');
      });
    }
  }

  menuToggle.addEventListener('click', (e) => {
    e.stopPropagation();
    setOpen(!navMenu.classList.contains('active'));
  });

  document.addEventListener('click', (e) => {
    if (
      navMenu.classList.contains('active') &&
      !navMenu.contains(e.target) &&
      e.target !== menuToggle &&
      !menuToggle.contains(e.target)
    ) {
      setOpen(false);
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && navMenu.classList.contains('active')) {
      setOpen(false);
      menuToggle.focus();
    }
  });
}

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
