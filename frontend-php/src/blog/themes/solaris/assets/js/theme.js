/**
 * Solaris Theme JS
 * Mobile menu toggle + dropdown hover grace delay
 */
(function () {
  'use strict';

  /* ---- Mobile menu toggle ---- */
  var toggle = document.getElementById('mobile-menu-toggle');
  var navMenu = document.getElementById('nav-menu');

  if (toggle && navMenu) {
    toggle.addEventListener('click', function () {
      var expanded = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', String(!expanded));
      navMenu.classList.toggle('open');
      toggle.classList.toggle('open');
    });
  }

  /* ---- Dropdown hover grace delay (200ms) ---- */
  var GRACE = 200;
  var items = document.querySelectorAll('.nav-item.has-children');

  items.forEach(function (item) {
    var timer = null;

    item.addEventListener('mouseenter', function () {
      clearTimeout(timer);
      item.classList.add('open');
    });

    item.addEventListener('mouseleave', function () {
      timer = setTimeout(function () {
        item.classList.remove('open');
      }, GRACE);
    });

    /* Keyboard accessibility */
    var trigger = item.querySelector('.nav-trigger');
    if (trigger) {
      trigger.addEventListener('focus', function () {
        clearTimeout(timer);
        item.classList.add('open');
      });
    }
  });

  /* Close dropdowns on Escape */
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      items.forEach(function (item) {
        item.classList.remove('open');
      });
      if (navMenu) navMenu.classList.remove('open');
      if (toggle) {
        toggle.setAttribute('aria-expanded', 'false');
        toggle.classList.remove('open');
      }
    }
  });
})();
