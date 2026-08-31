/**
 * PenCMS Admin Scaffold Controller (scaffold.js)
 * Alpine.js component for the 3-column resizable admin layout scaffold.
 *
 * This is an intentionally minimal controller — it handles only:
 *   - Workspace preferences (persist to localStorage)
 *   - Left / Right column collapse toggles
 *   - Drag-to-resize handles for both column dividers
 *   - Toast notification queue
 *
 * Pages that extend this scaffold should register their own Alpine component
 * (or extend this one) to add page-specific logic.
 */

document.addEventListener('alpine:init', () => {
    Alpine.data('scaffold', () => ({

        // ── UI State ─────────────────────────────────────────────────
        isDraggingLeftColumn:  false,
        isDraggingRightColumn: false,
        toasts:       [],
        toastCounter: 0,

        // ── Workspace Preferences ────────────────────────────────────
        // These mirror the shape used by wizard4 so that the shared
        // localStorage key 'pen_editor_workspace_prefs' keeps parity.
        workspacePrefs: {
            sidebarWidth:             32,
            rightColumnWidth:         25,
            leftColumnCollapsed:      false,
            rightColumnCollapsed:     false,
            secondaryRailCollapsed:   false,
            aiAssistantCollapsed:     false,
        },

        // ── Init ─────────────────────────────────────────────────────
        async init() {
            // Toast event bus
            window.addEventListener('pen:toast', (e) => {
                if (e.detail && e.detail.message) {
                    this.showToast(e.detail.message, e.detail.type || 'success');
                }
            });

            // Load persisted prefs (non-blocking — failures are silently ignored)
            try {
                const saved = localStorage.getItem('pen_editor_workspace_prefs');
                if (saved) {
                    this.workspacePrefs = {
                        ...this.workspacePrefs,
                        ...JSON.parse(saved),
                    };
                }
                this.saveWorkspacePrefs();
            } catch (e) { /* ignore */ }
        },

        // ── Toast Notifications ──────────────────────────────────────
        showToast(message, type = 'success') {
            const id = ++this.toastCounter;
            this.toasts.push({ id, message, type });
            setTimeout(() => {
                this.toasts = this.toasts.filter(t => t.id !== id);
            }, 4000);
        },

        // ── Workspace Preferences ────────────────────────────────────
        saveWorkspacePrefs() {
            try {
                localStorage.setItem('pen_editor_workspace_prefs', JSON.stringify(this.workspacePrefs));
                const html = document.documentElement;
                html.classList.toggle('pref-left-collapsed',           !!this.workspacePrefs.leftColumnCollapsed);
                html.classList.toggle('pref-right-collapsed',          !!this.workspacePrefs.rightColumnCollapsed);
                html.classList.toggle('pref-secondary-rail-collapsed', !!this.workspacePrefs.secondaryRailCollapsed);
            } catch (e) { /* ignore */ }
        },

        getHeaderHeight() {
            const el = document.getElementById('sticky-control-header');
            if (el) {
                return el.offsetHeight;
            }
            return this.workspacePrefs.secondaryRailCollapsed ? 42 : 54;
        },

        // ── Resize Handlers ──────────────────────────────────────────

        /**
         * Left-column drag handle (between Left and Center columns).
         * Dragging right increases sidebarWidth; dragging left decreases it.
         */
        startResizeLeft(e) {
            e.preventDefault();
            this.isDraggingLeftColumn = true;

            const startX         = e.clientX;
            const startWidthPct  = this.workspacePrefs.sidebarWidth || 32;
            const containerWidth = e.currentTarget.parentElement.clientWidth;

            document.body.style.cursor           = 'ew-resize';
            document.body.style.userSelect       = 'none';
            document.body.style.webkitUserSelect = 'none';

            const onMouseMove = (moveEvent) => {
                const deltaPct = ((moveEvent.clientX - startX) / containerWidth) * 100;
                let newPct = startWidthPct + deltaPct;
                if (newPct < 10) newPct = 10;
                if (newPct > 40) newPct = 40;
                this.workspacePrefs.sidebarWidth = Math.round(newPct * 10) / 10;
            };

            const onMouseUp = () => {
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup',  onMouseUp);
                document.body.style.cursor           = '';
                document.body.style.userSelect       = '';
                document.body.style.webkitUserSelect = '';
                this.isDraggingLeftColumn = false;
                this.saveWorkspacePrefs();
            };

            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup',  onMouseUp);
        },

        /**
         * Right-column drag handle (between Center and Right columns).
         * Dragging left increases rightColumnWidth; dragging right decreases it.
         */
        startResizeRight(e) {
            e.preventDefault();
            this.isDraggingRightColumn = true;

            const startX         = e.clientX;
            const startWidthPct  = this.workspacePrefs.rightColumnWidth || 25;
            const containerWidth = e.currentTarget.parentElement.clientWidth;

            document.body.style.cursor           = 'ew-resize';
            document.body.style.userSelect       = 'none';
            document.body.style.webkitUserSelect = 'none';

            const onMouseMove = (moveEvent) => {
                const deltaPct = ((moveEvent.clientX - startX) / containerWidth) * 100;
                let newPct = startWidthPct - deltaPct;   // inverted: right-side drag
                if (newPct < 10) newPct = 10;
                if (newPct > 40) newPct = 40;
                this.workspacePrefs.rightColumnWidth = Math.round(newPct * 10) / 10;
            };

            const onMouseUp = () => {
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup',  onMouseUp);
                document.body.style.cursor           = '';
                document.body.style.userSelect       = '';
                document.body.style.webkitUserSelect = '';
                this.isDraggingRightColumn = false;
                this.saveWorkspacePrefs();
            };

            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup',  onMouseUp);
        },
    }));
});
