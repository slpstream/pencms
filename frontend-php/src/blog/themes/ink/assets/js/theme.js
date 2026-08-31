document.addEventListener('DOMContentLoaded', function() {
  // 1. Dark / Light Mode Toggle
  const themeToggleBtn = document.getElementById('theme-toggle');
  if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', function() {
      const isDark = document.documentElement.getAttribute('data-theme') === 'dark' || 
                     document.documentElement.classList.contains('cm-wysiwym-dark');
      const newTheme = isDark ? 'light' : 'dark';
      
      if (newTheme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
        document.documentElement.classList.add('cm-wysiwym-dark');
      } else {
        document.documentElement.removeAttribute('data-theme');
        document.documentElement.classList.remove('cm-wysiwym-dark');
      }
      
      try {
        localStorage.setItem('theme', newTheme);
        localStorage.setItem('color-scheme', newTheme);
        document.cookie = "color-scheme=" + newTheme + "; path=/; max-age=31536000; SameSite=Lax";
      } catch (e) {}
    });
  }

  // 2. Mobile Navigation Drawer Toggle
  const mobileMenuBtn = document.getElementById('mobile-menu-toggle');
  const siteNavLinks = document.getElementById('site-nav-links');
  if (mobileMenuBtn && siteNavLinks) {
    const menuIcon = mobileMenuBtn.querySelector('.menu-icon');
    const closeIcon = mobileMenuBtn.querySelector('.close-icon');

    mobileMenuBtn.addEventListener('click', function() {
      const isOpen = siteNavLinks.classList.toggle('open');
      mobileMenuBtn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      if (menuIcon) menuIcon.style.display = isOpen ? 'none' : 'block';
      if (closeIcon) closeIcon.style.display = isOpen ? 'block' : 'none';
    });
  }

  // 3. Sturdy Dropdown Navigation (200ms grace delay)
  const dropdownParents = document.querySelectorAll('.site-nav-links .has-children');
  dropdownParents.forEach(function(parent) {
    let leaveTimer = null;

    parent.addEventListener('mouseenter', function() {
      if (leaveTimer) {
        clearTimeout(leaveTimer);
        leaveTimer = null;
      }
      parent.classList.add('open');
    });

    parent.addEventListener('mouseleave', function() {
      leaveTimer = setTimeout(function() {
        parent.classList.remove('open');
      }, 200);
    });
  });

  // 4. Reading Progress Bar
  const progressBar = document.querySelector('.reading-progress-bar');
  if (progressBar) {
    window.addEventListener('scroll', function() {
      const scrollTop = window.scrollY || document.documentElement.scrollTop;
      const docHeight = document.documentElement.scrollHeight - document.documentElement.clientHeight;
      if (docHeight > 0) {
        const scrollPercent = (scrollTop / docHeight) * 100;
        progressBar.style.width = Math.min(Math.max(scrollPercent, 0), 100) + '%';
      }
    }, { passive: true });
  }
});
