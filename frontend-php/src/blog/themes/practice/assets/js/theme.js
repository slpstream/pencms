/**
 * Practice theme JS
 * Mobile menu drawer toggle and sturdy hover grace delay
 */
document.addEventListener('DOMContentLoaded', function () {
  var toggle = document.getElementById('mobile-menu-toggle');
  var menu = document.getElementById('nav-menu');
  
  if (toggle && menu) {
    toggle.addEventListener('click', function () {
      menu.classList.toggle('is-active');
      var expanded = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', (!expanded).toString());
    });
  }

  // Dropdown hover grace delay for navigation
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
});
