/* =============================================================================
 * theme.js — 1337 theme chrome interactions
 *
 *   - Mobile drawer toggle for primary nav + rail widgets (secondary / profile)
 *   - Sturdy dropdown: 200ms mouseleave grace delay before dismissing .open
 *     (guide §12 — no flimsy hovering). Click + focus locking for a11y.
 *   - Caret blink pause on hero hover (subtle, motion-respectful)
 *
 * 1337 is single-dark — there is NO mode toggle in this theme.
 * ========================================================================== */

(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        var toggle = document.getElementById("mobile-menu-toggle");
        var nav = document.getElementById("nav-menu");
        var stack = document.getElementById("rail-nav-stack");

        function setMobileDrawerOpen(isOpen) {
            if (nav) {
                nav.classList.toggle("open", isOpen);
            }
            if (stack) {
                stack.classList.toggle("drawer-open", isOpen);
            }
            if (toggle) {
                toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
            }
        }

        /* ---- Mobile drawer ----------------------------------------------- */
        if (toggle && nav) {
            toggle.addEventListener("click", function () {
                setMobileDrawerOpen(!nav.classList.contains("open"));
            });
            // Close on Escape for keyboard users
            (stack || nav).addEventListener("keydown", function (e) {
                if (e.key === "Escape" && nav.classList.contains("open")) {
                    setMobileDrawerOpen(false);
                    toggle.focus();
                }
            });
        }

        /* ---- Sturdy dropdowns (desktop hover + click/focus locking) ------- */
        var GRACE_MS = 200;
        var items = document.querySelectorAll(".nav-item.has-children");

        items.forEach(function (item) {
            var timer = null;

            function open() {
                if (timer) { clearTimeout(timer); timer = null; }
                item.classList.add("open");
            }
            function scheduleClose() {
                if (timer) clearTimeout(timer);
                timer = setTimeout(function () {
                    item.classList.remove("open");
                    timer = null;
                }, GRACE_MS);
            }

            // Hover bridge — open on enter, grace-close on leave
            item.addEventListener("mouseenter", open);
            item.addEventListener("mouseleave", scheduleClose);

            // Click locking (mobile + desktop): toggle on tap of the trigger
            var trigger = item.querySelector(".nav-trigger");
            if (trigger) {
                trigger.addEventListener("click", function (e) {
                    // Only intercept when the trigger is a label (no URL) or
                    // when the link already has a destination we let the browser
                    // follow on a plain click without modifier keys. For labels,
                    // always toggle.
                    if (trigger.tagName === "SPAN" || trigger.classList.contains("nav-label")) {
                        e.preventDefault();
                        item.classList.toggle("open");
                    }
                });
            }

            // Focus-within keeps it open while Tabbing through children
            item.addEventListener("focusin", open);
            item.addEventListener("focusout", scheduleClose);

            // Cancel a pending close if the pointer re-enters
            item.addEventListener("mouseenter", function () {
                if (timer) { clearTimeout(timer); timer = null; }
            });
        });

        /* ---- Caret blink pause on hero hover (subtle) -------------------- */
        // Only bother when motion is allowed.
        if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: no-preference)").matches) {
            var hero = document.querySelector(".boot-hero");
            if (hero) {
                var carets = hero.querySelectorAll(".boot-hero-caret, .boot-hero-title");
                hero.addEventListener("mouseenter", function () {
                    carets.forEach(function (el) {
                        el.style.animationPlayState = "paused";
                    });
                });
                hero.addEventListener("mouseleave", function () {
                    carets.forEach(function (el) {
                        el.style.animationPlayState = "running";
                    });
                });
            }
        }
    });
})();
