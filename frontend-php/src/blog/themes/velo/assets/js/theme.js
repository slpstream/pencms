/**
 * Velo — published chrome only.
 * Mobile drawer, sturdy dropdown hover grace, band settle.
 * Light-only: no theme toggle. Admin / editor never loads this file.
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', () => {
    initMobileMenu();
    initDropdownMenus();
    initBandSettle();
  });

  function initMobileMenu() {
    const menuToggle = document.getElementById('mobile-menu-toggle');
    const navMenu = document.getElementById('nav-menu');
    if (!menuToggle || !navMenu) return;

    menuToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      const open = navMenu.classList.toggle('active');
      menuToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });

    document.addEventListener('click', (e) => {
      if (navMenu.classList.contains('active') && !navMenu.contains(e.target) && e.target !== menuToggle) {
        navMenu.classList.remove('active');
        menuToggle.setAttribute('aria-expanded', 'false');
        navMenu.querySelectorAll('.nav-item.has-children.open').forEach((item) => {
          item.classList.remove('open');
        });
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

  function initBandSettle() {
    const planes = document.querySelectorAll('.plane');
    if (!planes.length) return;

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      planes.forEach((el) => el.classList.add('settled'));
      return;
    }

    if (!('IntersectionObserver' in window)) {
      planes.forEach((el) => el.classList.add('settled'));
      return;
    }

    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('settled');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });

    planes.forEach((el) => io.observe(el));
  }
})();
