/**
 * Cold War theme navigation runtime.
 *
 * Keeps the primary menu usable on touch and keyboard while giving desktop
 * users a short hover bridge between a parent item and its dropdown.
 *
 * Parent <a> links always navigate. Submenus open on hover/focus, or via the
 * dedicated caret (and label-only triggers) for touch and keyboard users.
 */
(function () {
    'use strict';

    var DROPDOWN_GRACE_MS = 200;

    function setOpen(item, open) {
        item.classList.toggle('open', open);

        item.querySelectorAll('[aria-expanded]').forEach(function (el) {
            el.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
    }

    function closeOpenItems(navMenu) {
        navMenu.querySelectorAll('.nav-item.has-children.open').forEach(function (item) {
            setOpen(item, false);
        });
    }

    function initMobileMenu() {
        var menuToggle = document.getElementById('mobile-menu-toggle');
        var navMenu = document.getElementById('nav-menu');
        if (!menuToggle || !navMenu) {
            return;
        }

        menuToggle.addEventListener('click', function (event) {
            event.stopPropagation();
            var isOpen = navMenu.classList.toggle('active');
            menuToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        });

        document.addEventListener('click', function (event) {
            if (!navMenu.classList.contains('active')) {
                return;
            }
            if (navMenu.contains(event.target) || event.target === menuToggle) {
                return;
            }
            navMenu.classList.remove('active');
            menuToggle.setAttribute('aria-expanded', 'false');
            closeOpenItems(navMenu);
        });

        document.addEventListener('keydown', function (event) {
            if (event.key !== 'Escape') {
                return;
            }
            navMenu.classList.remove('active');
            menuToggle.setAttribute('aria-expanded', 'false');
            closeOpenItems(navMenu);
            menuToggle.focus();
        });
    }

    function initDropdownMenus() {
        var navMenu = document.getElementById('nav-menu');
        if (!navMenu) {
            return;
        }

        navMenu.querySelectorAll('.nav-item.has-children').forEach(function (item) {
            var closeTimer = null;
            var caret = item.querySelector('.nav-caret');
            var labelTrigger = item.querySelector('.nav-trigger');

            var cancelClose = function () {
                if (closeTimer !== null) {
                    window.clearTimeout(closeTimer);
                    closeTimer = null;
                }
            };

            var scheduleClose = function () {
                cancelClose();
                closeTimer = window.setTimeout(function () {
                    setOpen(item, false);
                    closeTimer = null;
                }, DROPDOWN_GRACE_MS);
            };

            var prefersHover = function () {
                return window.matchMedia('(hover: hover) and (pointer: fine)').matches;
            };

            var toggleOpen = function (event) {
                event.preventDefault();
                event.stopPropagation();
                cancelClose();

                // Hover already opens the menu; a click on the caret/label must not
                // immediately collapse it. Touch/coarse pointers still need a toggle.
                if (prefersHover()) {
                    setOpen(item, true);
                    return;
                }

                setOpen(item, !item.classList.contains('open'));
            };

            item.addEventListener('mouseenter', function () {
                cancelClose();
                setOpen(item, true);
            });

            item.addEventListener('mouseleave', scheduleClose);

            item.addEventListener('focusin', function () {
                cancelClose();
                setOpen(item, true);
            });

            item.addEventListener('focusout', function (event) {
                if (!item.contains(event.relatedTarget)) {
                    scheduleClose();
                }
            });

            if (caret) {
                caret.addEventListener('click', toggleOpen);
            }

            // Label-only parents have no URL; the label itself toggles the menu.
            if (labelTrigger) {
                labelTrigger.addEventListener('click', toggleOpen);

                labelTrigger.addEventListener('keydown', function (event) {
                    if (event.key !== 'Enter' && event.key !== ' ') {
                        return;
                    }
                    toggleOpen(event);
                });
            }
        });

        document.addEventListener('click', function (event) {
            if (navMenu.contains(event.target)) {
                return;
            }
            closeOpenItems(navMenu);
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initMobileMenu();
        initDropdownMenus();
    });
}());
