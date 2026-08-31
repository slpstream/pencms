/**
 * Musings Theme JavaScript
 * Handles menu hover bridges and mobile navigation drawer interactions.
 */

document.addEventListener('DOMContentLoaded', function () {
  // Mobile menu toggle
  const menuToggle = document.querySelector('.musings-menu-toggle');
  const sidebarContent = document.querySelector('.musings-sidebar-content');

  if (menuToggle && sidebarContent) {
    menuToggle.addEventListener('click', function () {
      const isExpanded = menuToggle.getAttribute('aria-expanded') === 'true';
      menuToggle.setAttribute('aria-expanded', !isExpanded);
      menuToggle.classList.toggle('is-active');
      sidebarContent.classList.toggle('is-open');
    });
  }

  // Sturdy dropdown hover bridge & grace delay for 2-level nested menus
  const dropdownParents = document.querySelectorAll('.has-children, .menu-item-has-children');
  
  dropdownParents.forEach(function (parent) {
    let timeoutId = null;
    
    parent.addEventListener('mouseenter', function () {
      if (timeoutId) clearTimeout(timeoutId);
      parent.classList.add('is-open');
    });
    
    parent.addEventListener('mouseleave', function () {
      timeoutId = setTimeout(function () {
        parent.classList.remove('is-open');
      }, 200); // 200ms grace delay
    });
  });
});
