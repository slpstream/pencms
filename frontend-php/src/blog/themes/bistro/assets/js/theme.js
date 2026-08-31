/**
 * Bistro Theme JS — Navigation drawer & dropdown grace delay
 */
document.addEventListener('DOMContentLoaded', () => {
  const toggleBtn = document.getElementById('mobile-menu-toggle');
  const navMenu = document.getElementById('nav-menu');

  if (toggleBtn && navMenu) {
    toggleBtn.addEventListener('click', () => {
      const isExpanded = toggleBtn.getAttribute('aria-expanded') === 'true';
      toggleBtn.setAttribute('aria-expanded', !isExpanded);
      navMenu.classList.toggle('is-open');
    });
  }

  // Grace delay for dropdown hover bridges
  const dropdownItems = document.querySelectorAll('.nav-item.has-children');
  dropdownItems.forEach((item) => {
    let timeoutId = null;
    item.addEventListener('mouseenter', () => {
      if (timeoutId) clearTimeout(timeoutId);
      item.classList.add('is-hovered');
    });
    item.addEventListener('mouseleave', () => {
      timeoutId = setTimeout(() => {
        item.classList.remove('is-hovered');
      }, 150);
    });
  });
});
