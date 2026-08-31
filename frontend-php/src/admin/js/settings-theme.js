/**
 * PenCMS Theme Settings Logic
 *
 * Manages theme settings:
 *   - Installed Themes (selection, custom theme create/delete)
 *   - Style Settings (theme.json schema-driven overrides)
 *   - Import / Export packaging (window.__pencmsProThemePackage mixin)
 */
document.addEventListener('alpine:init', () => {
    Alpine.data('settingsTheme', () => ({
        ...(typeof window.__pencmsProThemePackage === 'function'
            ? window.__pencmsProThemePackage()
            : {}),
        // ── Tab state ──────────────────────────────────────────
        activeTab: 'installed',   // 'installed' | 'import' | 'export' | 'style'

        // ── Theme selection state ──────────────────────────────
        installTheme: window.__PEN_THEME_INIT__?.installTheme || 'starter',
        activeTheme:  window.__PEN_THEME_INIT__?.installTheme || 'starter',
        selectedTheme: window.__PEN_THEME_INIT__?.installTheme || 'starter',
        siteTheme: null,

        // ── Custom theme state ─────────────────────────────────
        customExists: false,
        customLabel: 'Custom',
        customParent: null,
        forking: false,
        deletingCustom: false,
        themesWithScreenshot: window.__PEN_THEME_INIT__?.themesWithScreenshot || [],
        installedThemes: window.__PEN_THEME_INIT__?.themes || [],

        // ── Modal state ────────────────────────────────────────
        confirmDeleteModalOpen: false,
        confirmReplaceModalOpen: false,

        // ── UI state ───────────────────────────────────────────
        loading: true,
        savingTheme: false,
        message: '',
        isError: false,
        _messageTimer: null,

        // Screenshot hover viewer (~50% size; delayed open; screenshot hit-target only)
        shotPreview: null, // { src, name } | null
        _shotPreviewTimer: null,
        shotPreviewDelayMs: 450,

        // ── Style settings state ───────────────────────────────
        styleSchema: null,
        styleValues: {},
        styleDarkValues: {},
        styleFormValues: {},
        styleFormDarkValues: {},
        styleDefaults: {},
        styleDarkDefaults: {},
        styleSavedForTheme: null,
        styleHasDark: false,
        styleLoading: false,
        styleSaving: false,
        styleLoadedSnapshot: '',
        styleLoadError: '',
        /** Open font listbox keyed by field.id (independent Display/Body/Mono). */
        styleFontDropdownOpen: {},

        get styleDirty() {
            const current = JSON.stringify({
                values: this.styleValues,
                dark: this.styleDarkValues,
            });
            return current !== this.styleLoadedSnapshot;
        },

        // ── Helpers ────────────────────────────────────────────

        setMessage(msg, isError = false, durationMs = 10000) {
            if (this._messageTimer) {
                clearTimeout(this._messageTimer);
                this._messageTimer = null;
            }
            this.message = msg;
            this.isError = !!isError;
            if (msg && durationMs > 0) {
                this._messageTimer = setTimeout(() => {
                    this.message = '';
                    this.isError = false;
                    this._messageTimer = null;
                }, durationMs);
            }
        },

        clearMessage() {
            if (this._messageTimer) {
                clearTimeout(this._messageTimer);
                this._messageTimer = null;
            }
            this.message = '';
            this.isError = false;
        },

        apiSitesBase() {
            const base = ((window.AUTH && window.AUTH.apiBase) || '/api/v1');
            return base.replace(/\/v1\/?$/, '');
        },

        siteId() {
            return (Alpine.store('app').activeSiteId || 'default');
        },

        // ── Lifecycle ──────────────────────────────────────────

        async init() {
            const hash = (window.location.hash || '').replace(/^#/, '');
            if (['installed', 'style', 'import', 'export'].includes(hash)) {
                this.activeTab = hash;
            }
            await this.loadTheme();
            if (typeof this.initPackageFormDefaults === 'function') {
                this.initPackageFormDefaults();
            }
            if (!this.isError && typeof this.showStoredImportMessage === 'function') {
                this.showStoredImportMessage();
            }
            if (this.activeTab === 'style') {
                this.loadStyleSettings();
            }
            this.$watch(
                () => this.$store.app.activeSiteId,
                async (next, prev) => {
                    if (next && next !== prev) {
                        await this.loadTheme();
                        if (this.activeTab === 'style') {
                            this.loadStyleSettings();
                        }
                    }
                }
            );
        },

        setTab(tab) {
            this.activeTab = tab;
            this.clearMessage();
            const url = new URL(window.location.href);
            url.hash = tab;
            window.history.replaceState(null, '', url.toString());
            if (tab === 'installed' && typeof this.loadInstalledThemes === 'function') {
                this.loadInstalledThemes();
            }
            if (tab === 'style') {
                this.loadStyleSettings();
            }
            if (tab === 'export' && typeof this.initPackageFormDefaults === 'function') {
                this.initPackageFormDefaults();
            }
        },

        showStoredImportMessage() {
            try {
                const stored = window.sessionStorage.getItem('penThemeImportMessage');
                if (!stored) return;
                window.sessionStorage.removeItem('penThemeImportMessage');
                const { message, isError } = JSON.parse(stored);
                if (message) {
                    this.setMessage(message, !!isError);
                }
            } catch (_e) {
                window.sessionStorage.removeItem('penThemeImportMessage');
            }
        },

        // ── Data loading ───────────────────────────────────────

        async loadCustomContext(siteId) {
            try {
                const res = await fetch(
                    `${this.apiSitesBase()}/sites/${encodeURIComponent(siteId)}/theme/context`,
                    { headers: window.AUTH.getHeaders() }
                );
                if (!res.ok) {
                    this.customExists = false;
                    this.customLabel = 'Custom';
                    this.customParent = null;
                    return;
                }
                const ctx = await res.json();
                this.customExists = !!ctx.exists;
                this.customLabel = (ctx.name && String(ctx.name).trim()) || 'Custom';
                this.customParent = ctx.parent || null;
            } catch (_err) {
                this.customExists = false;
                this.customLabel = 'Custom';
                this.customParent = null;
            }
        },

        async loadTheme() {
            this.loading = true;
            this.clearMessage();
            try {
                const siteId = this.siteId();
                const sitesRes = await fetch(`${this.apiSitesBase()}/sites`, {
                    headers: window.AUTH.getHeaders()
                });
                if (!sitesRes.ok) throw new Error(`HTTP ${sitesRes.status}`);
                const sitesData = await sitesRes.json();
                const site = (sitesData.sites || []).find(s => s.id === siteId) || {};
                this.siteTheme = site.theme || null;
                const effective = this.siteTheme || this.installTheme;
                this.activeTheme = effective;
                this.selectedTheme = effective;
                await this.loadCustomContext(siteId);
            } catch (err) {
                this.setMessage(`Failed to load site theme: ${err.message}`, true);
                this.siteTheme = null;
                this.activeTheme = this.installTheme;
                this.selectedTheme = this.installTheme;
                this.customExists = false;
            } finally {
                this.loading = false;
            }
        },

        // ── Theme actions ──────────────────────────────────────

        apiDetail(data, status) {
            return typeof data.detail === 'string'
                ? data.detail
                : (data.detail ? JSON.stringify(data.detail) : `HTTP ${status}`);
        },

        setTheme(theme) {
            this.selectedTheme = theme;
            this.applyTheme();
        },

        async applyTheme() {
            this.savingTheme = true;
            this.clearMessage();
            try {
                const siteId = this.siteId();
                const response = await fetch(`${this.apiSitesBase()}/sites/${encodeURIComponent(siteId)}`, {
                    method: 'PATCH',
                    headers: window.AUTH.getHeaders(),
                    body: JSON.stringify({ theme: this.selectedTheme })
                });
                const data = await response.json().catch(() => ({}));
                if (!response.ok) {
                    throw new Error(this.apiDetail(data, response.status));
                }
                this.siteTheme = data.theme || this.selectedTheme;
                this.activeTheme = this.selectedTheme;
                this.setMessage(`Theme for <strong>${siteId}</strong> switched to <strong>${this.selectedTheme}</strong>.`);
                if (Alpine.store('app') && typeof Alpine.store('app').loadSites === 'function') {
                    await Alpine.store('app').loadSites();
                }
                await this.loadCustomContext(siteId);
                if (this.packageFormSourceKey !== undefined) {
                    this.packageFormSourceKey = null;
                }
                if (this.activeTab === 'style') {
                    await this.loadStyleSettings();
                }
                if (this.activeTab === 'export' && typeof this.initPackageFormDefaults === 'function') {
                    this.initPackageFormDefaults();
                }
            } catch (err) {
                this.setMessage(`Failed to switch theme: ${err.message}`, true);
            } finally {
                this.savingTheme = false;
            }
        },

        // ── Custom theme management ────────────────────────────

        async createCustom() {
            if (this.customExists || this.forking) return;
            this.forking = true;
            this.clearMessage();
            try {
                const siteId = this.siteId();
                const parent = (this.activeTheme === 'custom')
                    ? null
                    : (this.activeTheme || this.installTheme);
                const body = parent ? { parent } : {};
                const response = await fetch(
                    `${this.apiSitesBase()}/sites/${encodeURIComponent(siteId)}/theme/fork`,
                    {
                        method: 'POST',
                        headers: window.AUTH.getHeaders(),
                        body: JSON.stringify(body),
                    }
                );
                const data = await response.json().catch(() => ({}));
                if (!response.ok) {
                    throw new Error(this.apiDetail(data, response.status));
                }
                this.setMessage(`Custom theme created from <strong>${data.parent || parent}</strong>.`);
                if (Alpine.store('app') && typeof Alpine.store('app').loadSites === 'function') {
                    await Alpine.store('app').loadSites();
                }
                await this.loadCustomContext(siteId);
                this.siteTheme = 'custom';
                this.activeTheme = 'custom';
                this.selectedTheme = 'custom';
                if (this.packageFormSourceKey !== undefined) {
                    this.packageFormSourceKey = null;
                }
            } catch (err) {
                this.setMessage(`Failed to create custom theme: ${err.message}`, true);
            } finally {
                this.forking = false;
            }
        },

        deleteCustom() {
            if (!this.customExists || this.deletingCustom) return;
            this.confirmDeleteModalOpen = true;
        },

        async confirmDeleteCustom() {
            this.confirmDeleteModalOpen = false;
            if (!this.customExists || this.deletingCustom) return;
            this.deletingCustom = true;
            this.clearMessage();
            try {
                const siteId = this.siteId();
                const response = await fetch(
                    `${this.apiSitesBase()}/sites/${encodeURIComponent(siteId)}/theme`,
                    {
                        method: 'DELETE',
                        headers: window.AUTH.getHeaders(),
                    }
                );
                const data = await response.json().catch(() => ({}));
                if (!response.ok) {
                    throw new Error(this.apiDetail(data, response.status));
                }
                const reverted = data.reverted_theme || data.parent || this.installTheme;
                this.setMessage(data.reverted_theme
                    ? `Custom theme deleted. Site theme reverted to <strong>${reverted}</strong>.`
                    : 'Custom theme deleted.');
                if (Alpine.store('app') && typeof Alpine.store('app').loadSites === 'function') {
                    await Alpine.store('app').loadSites();
                }
                await this.loadTheme();
            } catch (err) {
                this.setMessage(`Failed to delete custom theme: ${err.message}`, true);
            } finally {
                this.deletingCustom = false;
            }
        },

        async customizeActiveTheme() {
            if (this.activeTheme === 'custom') {
                window.location.href = 'admin-customize.php';
                return;
            }
            if (!this.customExists) {
                await this.createCustom();
                if (this.customExists || this.activeTheme === 'custom') {
                    window.location.href = 'admin-customize.php';
                }
                return;
            }
            // Custom theme exists, but active theme is a base theme -> open PenCMS replace confirm modal
            this.confirmReplaceModalOpen = true;
        },

        async confirmReplaceCustom() {
            this.confirmReplaceModalOpen = false;
            // Delete existing custom theme, then create new from activeTheme
            this.deletingCustom = true;
            try {
                const siteId = this.siteId();
                await fetch(`${this.apiSitesBase()}/sites/${encodeURIComponent(siteId)}/theme`, {
                    method: 'DELETE',
                    headers: window.AUTH.getHeaders(),
                });
                this.customExists = false;
            } catch (_e) {} finally {
                this.deletingCustom = false;
            }
            await this.createCustom();
            if (this.customExists || this.activeTheme === 'custom') {
                window.location.href = 'admin-customize.php';
            }
        },

        // ── Style settings helpers ─────────────────────────────

        /** Mirror backend _is_font_select_field: font selects get live type previews. */
        isFontSelectField(field) {
            if (!field || field.type !== 'select') return false;
            const id = String(field.id || '').toLowerCase();
            const v = String(field.var || '').toLowerCase();
            return id.startsWith('font') || v.includes('font');
        },

        styleFontOptionLabel(field) {
            const value = this.styleFormValues[field.id] ?? '';
            const options = Array.isArray(field.options) ? field.options : [];
            const match = options.find((opt) => opt && opt.value === value);
            return (match && match.label) || (value === '' ? 'Theme default' : value);
        },

        toggleStyleFontDropdown(fieldId) {
            const next = !this.styleFontDropdownOpen[fieldId];
            this.styleFontDropdownOpen = next ? { [fieldId]: true } : {};
        },

        closeStyleFontDropdown(fieldId) {
            if (this.styleFontDropdownOpen[fieldId]) {
                const next = { ...this.styleFontDropdownOpen };
                delete next[fieldId];
                this.styleFontDropdownOpen = next;
            }
        },

        selectStyleFontOption(fieldId, value) {
            this.setStyleValue(fieldId, false, value);
            this.closeStyleFontDropdown(fieldId);
        },

        onStyleFontListKeydown(field, event) {
            const fieldId = field.id;
            if (!this.styleFontDropdownOpen[fieldId]) return;
            const options = Array.isArray(field.options) ? field.options : [];
            if (!options.length) return;

            if (event.key === 'Escape') {
                event.preventDefault();
                this.closeStyleFontDropdown(fieldId);
                return;
            }

            const current = this.styleFormValues[fieldId] ?? '';
            let idx = options.findIndex((opt) => opt && opt.value === current);
            if (idx < 0) idx = 0;

            if (event.key === 'ArrowDown') {
                event.preventDefault();
                const next = options[Math.min(idx + 1, options.length - 1)];
                if (next) this.setStyleValue(fieldId, false, next.value);
            } else if (event.key === 'ArrowUp') {
                event.preventDefault();
                const prev = options[Math.max(idx - 1, 0)];
                if (prev) this.setStyleValue(fieldId, false, prev.value);
            } else if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                this.closeStyleFontDropdown(fieldId);
            }
        },

        _styleThemeUrl(siteId) {
            return `${this.apiSitesBase()}/sites/${encodeURIComponent(siteId)}/theme/style`;
        },

        _styleIndexFromSchema(schema) {
            const index = {};
            if (!schema || !Array.isArray(schema.groups)) return index;
            for (const group of schema.groups) {
                if (!group || !Array.isArray(group.fields)) continue;
                for (const field of group.fields) {
                    if (field && field.id) {
                        index[field.id] = field;
                    }
                }
            }
            return index;
        },

        _styleHasDark(schema) {
            if (!schema || !schema.dark_scope) return false;
            if (!Array.isArray(schema.groups)) return false;
            for (const group of schema.groups) {
                if (!group || !Array.isArray(group.fields)) continue;
                for (const field of group.fields) {
                    if (field && 'dark_default' in field) return true;
                }
            }
            return false;
        },

        async loadStyleSettings() {
            if (this.styleLoading) return;
            this.styleLoading = true;
            this.styleLoadError = '';
            try {
                const siteId = this.siteId();
                const res = await fetch(this._styleThemeUrl(siteId), {
                    headers: window.AUTH.getHeaders(),
                });
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const data = await res.json();

                this.styleSchema = data.schema || null;
                this.styleSavedForTheme = data.saved_for_theme || null;
                this.styleHasDark = this._styleHasDark(this.styleSchema);

                const index = this._styleIndexFromSchema(this.styleSchema);
                this.styleDefaults = {};
                this.styleDarkDefaults = {};
                for (const id in index) {
                    const field = index[id];
                    this.styleDefaults[id] = field.default || '';
                    if ('dark_default' in field) {
                        this.styleDarkDefaults[id] = field.dark_default;
                    }
                }

                this.styleValues = { ...(data.values || {}) };
                this.styleDarkValues = { ...(data.dark_values || {}) };

                this.styleFormValues = {};
                this.styleFormDarkValues = {};
                for (const id in index) {
                    const field = index[id];
                    this.styleFormValues[id] = this.styleValues[id] || field.default || '';
                    if ('dark_default' in field) {
                        this.styleFormDarkValues[id] = this.styleDarkValues[id] || field.dark_default;
                    }
                }

                this.styleLoadedSnapshot = JSON.stringify({
                    values: this.styleValues,
                    dark: this.styleDarkValues,
                });
                this.styleFontDropdownOpen = {};
            } catch (err) {
                this.styleLoadError = err.message;
                this.styleSchema = null;
                this.styleValues = {};
                this.styleDarkValues = {};
                this.styleFormValues = {};
                this.styleFormDarkValues = {};
                this.styleDefaults = {};
                this.styleDarkDefaults = {};
                this.styleSavedForTheme = null;
                this.styleFontDropdownOpen = {};
                this.styleHasDark = false;
                this.styleLoadedSnapshot = '';
            } finally {
                this.styleLoading = false;
            }
        },

        setStyleValue(fieldId, isDark, value) {
            const defaults = isDark ? this.styleDarkDefaults : this.styleDefaults;
            const target = isDark ? this.styleDarkValues : this.styleValues;
            const form = isDark ? this.styleFormDarkValues : this.styleFormValues;
            const field = this._styleIndexFromSchema(this.styleSchema)[fieldId];
            const hasDarkPair = !!(field && Object.prototype.hasOwnProperty.call(field, 'dark_default'));

            form[fieldId] = value;

            if (isDark) {
                // Once light is customized, keep dark explicit even at dark_default —
                // otherwise :root !important light overrides leak into dark mode.
                const lightCustomized = Object.prototype.hasOwnProperty.call(this.styleValues, fieldId);
                if ((value === '' || value === defaults[fieldId]) && !lightCustomized) {
                    delete target[fieldId];
                } else {
                    target[fieldId] = value === '' ? defaults[fieldId] : value;
                }
            } else {
                if (value === '' || value === defaults[fieldId]) {
                    delete target[fieldId];
                    // Light back to inherit: drop a dark pin that only matched dark_default.
                    if (hasDarkPair && this.styleDarkValues[fieldId] === this.styleDarkDefaults[fieldId]) {
                        delete this.styleDarkValues[fieldId];
                    }
                } else {
                    target[fieldId] = value;
                    this._pinDarkCompanion(fieldId, field);
                }
            }
        },

        /** Ensure a light override always carries an explicit dark companion. */
        _pinDarkCompanion(fieldId, field) {
            if (!field || !Object.prototype.hasOwnProperty.call(field, 'dark_default')) return;
            if (Object.prototype.hasOwnProperty.call(this.styleDarkValues, fieldId)) return;
            const pinned = this.styleFormDarkValues[fieldId] || field.dark_default;
            if (!pinned) return;
            this.styleDarkValues[fieldId] = pinned;
            this.styleFormDarkValues[fieldId] = pinned;
        },

        _pinAllDarkCompanions() {
            const index = this._styleIndexFromSchema(this.styleSchema);
            for (const id of Object.keys(this.styleValues)) {
                this._pinDarkCompanion(id, index[id]);
            }
        },

        async saveStyleSettings() {
            if (this.styleSaving || !this.styleSchema) return;
            this.styleSaving = true;
            this.clearMessage();
            try {
                // Paired light/dark colors must both be explicit on save. Untouched
                // dark pickers sit at dark_default in the form but were previously
                // omitted from the payload ("inherit"), so :root !important light
                // rules won in dark mode too.
                this._pinAllDarkCompanions();

                const siteId = this.siteId();
                const res = await fetch(this._styleThemeUrl(siteId), {
                    method: 'PUT',
                    headers: window.AUTH.getHeaders(),
                    body: JSON.stringify({
                        values: this.styleValues,
                        dark: this.styleDarkValues,
                    }),
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(this.apiDetail(data, res.status));

                this.styleSchema = data.schema || null;
                this.styleSavedForTheme = data.saved_for_theme || null;
                this.styleValues = { ...(data.values || {}) };
                this.styleDarkValues = { ...(data.dark_values || {}) };

                const index = this._styleIndexFromSchema(this.styleSchema);
                for (const id in index) {
                    const field = index[id];
                    this.styleFormValues[id] = this.styleValues[id] || field.default || '';
                    if ('dark_default' in field) {
                        this.styleFormDarkValues[id] = this.styleDarkValues[id] || field.dark_default;
                    }
                }

                this.styleLoadedSnapshot = JSON.stringify({
                    values: this.styleValues,
                    dark: this.styleDarkValues,
                });
                this.setMessage(`Style settings saved for <strong>${siteId}</strong>.`);
            } catch (err) {
                this.setMessage(`Failed to save style settings: ${err.message}`, true);
            } finally {
                this.styleSaving = false;
            }
        },

        async resetStyleSettings() {
            if (this.styleSaving || !this.styleSchema) return;
            this.styleSaving = true;
            this.clearMessage();
            try {
                const siteId = this.siteId();
                const res = await fetch(this._styleThemeUrl(siteId), {
                    method: 'PUT',
                    headers: window.AUTH.getHeaders(),
                    body: JSON.stringify({ values: {}, dark: {} }),
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(this.apiDetail(data, res.status));

                this.styleSchema = data.schema || null;
                this.styleSavedForTheme = data.saved_for_theme || null;
                this.styleValues = {};
                this.styleDarkValues = {};

                const index = this._styleIndexFromSchema(this.styleSchema);
                for (const id in index) {
                    const field = index[id];
                    this.styleFormValues[id] = field.default || '';
                    if ('dark_default' in field) {
                        this.styleFormDarkValues[id] = field.dark_default;
                    }
                }

                this.styleLoadedSnapshot = JSON.stringify({
                    values: this.styleValues,
                    dark: this.styleDarkValues,
                });
                this.setMessage(`Style settings reset to theme defaults for <strong>${siteId}</strong>.`);
            } catch (err) {
                this.setMessage(`Failed to reset style settings: ${err.message}`, true);
            } finally {
                this.styleSaving = false;
            }
        },

        showThemeShotPreview(theme) {
            if (!theme?.has_screenshot) return;
            this.showShotPreview(this.screenshotUrl(theme.slug, true), theme.name || theme.slug);
        },

        // ── Screenshot helpers ─────────────────────────────────

        screenshotUrl(slug, hasScreenshot) {
            if (hasScreenshot) {
                return `/blog/themes/${encodeURIComponent(slug)}/screenshot.webp`;
            }
            return '/admin/images/theme-no-screenshot.svg';
        },

        showShotPreview(src, name, customized = false) {
            if (!src || src.includes('theme-no-screenshot')) return;
            if (this._shotPreviewTimer) {
                clearTimeout(this._shotPreviewTimer);
                this._shotPreviewTimer = null;
            }
            this._shotPreviewTimer = setTimeout(() => {
                this._shotPreviewTimer = null;
                this.shotPreview = {
                    src,
                    name: name || '',
                    customized: !!customized,
                };
            }, this.shotPreviewDelayMs);
        },

        hideShotPreview() {
            if (this._shotPreviewTimer) {
                clearTimeout(this._shotPreviewTimer);
                this._shotPreviewTimer = null;
            }
            this.shotPreview = null;
        },

        customParentShotUrl() {
            const parent = (this.customParent || '').trim();
            if (!parent) return null;
            const known = Array.isArray(this.themesWithScreenshot)
                ? this.themesWithScreenshot
                : [];
            if (!known.includes(parent)) return null;
            return `/blog/themes/${encodeURIComponent(parent)}/screenshot.webp`;
        },

        showCustomShotPreview() {
            const src = this.customParentShotUrl();
            if (!src) return;
            const name = this.customLabel || 'Custom';
            this.showShotPreview(src, name, true);
        }
    }));
});
