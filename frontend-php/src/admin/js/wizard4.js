/**
 * PenCMS Post Editor Controller (wizard4.js)
 * Alpine.js + Traven Editor Integration
 *
 * IMPORTANT: TravenEditor instances use ES2022 private fields (#view, etc.)
 * which break when accessed through Alpine's Proxy wrappers. Editor refs
 * are stored in this closure-scoped object, outside Alpine's reactivity.
 */
const _editors = {
    main: null,
    partials: {},
    lastActive: null
};

/**
 * Strip editor preview proxy URLs back to site-relative asset paths.
 * Used on human save, AI document context, and AI write paths so agents
 * never see or persist /api/assets/raw/... forms.
 */
function stripEditorContentUrls(text) {
    if (!text) return '';
    return String(text)
        .replace(/\/api\/assets\/raw\/sites\/[^/]+\/assets\//g, '')
        .replace(/\/api\/assets\/raw\/images\/content\//g, 'images/content/');
}

window.fromEditorContentUrls = stripEditorContentUrls;

document.addEventListener('alpine:init', () => {
    Alpine.data('wizard4', () => ({
        // Core state
        isNew: true,
        contentVersion: null,
        conflictModalOpen: false,
        saving: false,
        manualSaving: false,
        loading: false,
        saveStatus: 'saved',
        get saveStatusText() {
            if (this.saveStatus === 'saving') return 'Saving...';
            if (this.saveStatus === 'unsaved') return 'Unsaved';
            return 'Saved';
        },
        config: null,
        slugManuallyEdited: false,
        translationConfig: {
            language: 'en',
            languages: [],
            language_labels: {},
            i18n_active: false
        },
        requestedLanguage: null,
        currentLanguage: null,
        currentCollection: null,
        translationPeers: [],
        lockedTranslationMetadata: null,
        lockedComposite: null,

        // Assets
        availableAssets: [],
        activeMediaTab: 'local',
        globalAssets: [],
        globalVisibleLimit: 24,
        globalSearchQuery: '',
        globalSortOrder: 'newest',
        hoveredAsset: null,
        isUploading: false,
        dragOver: false,

        // UI state
        sidebarPanel: 'properties',
        showModal: false,
        modalImage: null,
        postSettingsOpen: false,
        settingsPost: null,
        toasts: [],
        toastCounter: 0,
        toolbarDropdownOpen: false,
        skinDropdownOpen: false,
        statusDropdownOpen: false,
        isDraggingLeftColumn: false,
        isDraggingRightColumn: false,
        workspacePrefs: { vimMode: false, mainToolbar: true, selectionBubble: true, gutterMenu: true, secondaryRailCollapsed: false, sidebarWidth: 32, rightColumnWidth: 25, leftColumnCollapsed: false, rightColumnCollapsed: false, propertiesCardCollapsed: false, classificationCardCollapsed: false, mediaGalleryCardCollapsed: false, documentOutlineCollapsed: true, aiAssistantCollapsed: false, rawMarkdown: false, editorSkin: 'starter', editorSkinThemeId: '' },
        addFragmentModalOpen: false,
        newFragmentName: '',
        removeFragmentModalOpen: false,
        fragmentToRemove: '',
        deleteAssetModalOpen: false,
        assetToDelete: null,
        collapsedPartials: [],
        expandedPartial: null,
        resumeModalOpen: false,
        resumeModalDraft: null,
        summaryWand: { status: 'idle', preview: '', error: '' },
        faqsWand: { status: 'idle', preview: [], error: '' },

        // Shortcode modal
        shortcodeModal: {
            open: false,
            mode: 'insert',   // 'insert' | 'edit'
            type: 'image',
            attrs: { src: '', alt: '', caption: '', class: '', size: '' },
            _editNode: null   // reference when editing an existing shortcode
        },

        // Editor references are stored in `_editors` (above), outside Alpine's
        // reactive scope, to avoid Proxy-wrapping that breaks private fields.

        /**
         * Build a site-scoped public URL for a logical content asset path.
         * Matches Site Settings / API public_asset_url: /api/assets/raw/sites/{id}/assets/...
         */
        contentAssetUrl(path) {
            if (!path) return '';
            const raw = String(path).trim();
            if (/^https?:\/\//i.test(raw) || raw.startsWith('/api/') || raw.startsWith('data:')) {
                return raw;
            }
            const logical = raw.replace(/^\/+/, '');
            if (logical.startsWith('shared/')) {
                return `/blog/${logical}`;
            }
            const siteId = (this.config?.site_id || 'default').trim() || 'default';
            return `/api/assets/raw/sites/${siteId}/assets/${logical}`;
        },

        /** Rewrite bare images/content/ paths for editor preview (never touch /api/ URLs). */
        toEditorContentUrls(text) {
            if (!text) return '';
            const siteId = (this.config?.site_id || 'default').trim() || 'default';
            const prefix = `/api/assets/raw/sites/${siteId}/assets/images/content/`;
            return text.replace(/(^|[\s("'])images\/content\//g, `$1${prefix}`);
        },

        /** Strip editor proxy URLs back to site-relative paths before save. */
        fromEditorContentUrls(text) {
            return stripEditorContentUrls(text);
        },

        // Auto-save
        autoSaveKey: 'pen_editor_draft',
        autoSaveTimer: null,
        serverSaveTimer: null,

        form: {
            id: '', category: 'posts', name: '', domain: 'blog',
            status: 'draft', content: '', composite: false,
            partials: {},
            posts: [{ id: 'index', title: '', metadata: [], tags: [] }],
            date: '', author: '', deck: '', summary: '', faqs: [],
            hero_image: '', hero_title: '', trumpet: '',
            page: false,
            pinned: false,
            noindex: false,
            publish_at: ''
        },

        // Site-scoped authors for the post byline picker (authors.yaml via GET /api/authors/).
        // form.author stays a string byline; never write into form.name (post title).
        authors: [],
        authorMode: 'pick',   // 'pick' | 'custom'
        authorCustom: '',
        authorSelect: '',     // '' | authors[].name | '__custom__'

        /** Format stored UTC publish_at for <input type="datetime-local">. */
        publishAtForInput() {
            if (!this.form.publish_at) return '';
            const d = new Date(this.form.publish_at);
            if (Number.isNaN(d.getTime())) return '';
            const pad = (n) => String(n).padStart(2, '0');
            return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
        },

        /** Persist datetime-local value as UTC ISO-8601 with Z. */
        setPublishAtFromInput(val) {
            if (!val) {
                this.form.publish_at = '';
                return;
            }
            const d = new Date(val);
            if (Number.isNaN(d.getTime())) {
                this.form.publish_at = '';
                return;
            }
            this.form.publish_at = d.toISOString().replace(/\.\d{3}Z$/, 'Z');
        },

        isScheduled() {
            if ((this.form.status || '').toLowerCase() !== 'published') return false;
            if (!this.form.publish_at) return false;
            const d = new Date(this.form.publish_at);
            return !Number.isNaN(d.getTime()) && d.getTime() > Date.now();
        },

        /** Control-rail face label: Scheduled when embargoed, else editorial status. */
        statusRailLabel() {
            if (this.isScheduled()) return 'Scheduled';
            const s = (this.form.status || 'draft').toLowerCase();
            const labels = {
                stub: 'Stub',
                draft: 'Draft',
                unpublished: 'Unpublished',
                published: 'Published',
            };
            return labels[s] || s;
        },

        setStatus(status) {
            if (this.statusOptionLocked(status)) return;
            this.form.status = status;
            this.statusDropdownOpen = false;
        },

        statusOptionLocked(status) {
            return (status === 'published' || status === 'unpublished')
                && !(this.$store && this.$store.app && this.$store.app.hasCap('publish:content'));
        },

        get isTranslation() {
            return !!(
                this.translationConfig?.i18n_active
                && this.currentLanguage
                && this.currentLanguage !== this.translationConfig.language
            );
        },

        get siblingStates() {
            const languages = this.translationConfig?.languages || [];
            return languages.map((language) => {
                if (language === this.currentLanguage) {
                    return {
                        language,
                        status: this.form.status || 'draft',
                        published: !!this.form.published,
                        needs_review: !!this.form.needs_review,
                        current: true
                    };
                }
                const peer = (this.translationPeers || []).find(
                    (item) => item.language === language
                );
                return peer
                    ? { ...peer, current: false }
                    : { language, status: 'missing', published: false, current: false };
            });
        },

        languageLabel(code) {
            const override = this.translationConfig?.language_labels?.[code];
            if (override) return override;
            try {
                if (Intl && Intl.DisplayNames) {
                    return new Intl.DisplayNames([code], { type: 'language' }).of(code) || code;
                }
            } catch (_) { /* use code */ }
            return code;
        },

        siblingEditorUrl(language) {
            const params = {
                id: this.form.id,
                collection: this.currentCollection || this.form.category || 'general',
                lang: language
            };
            const store = (window.Alpine && Alpine.store('app')) || null;
            return store && typeof store.adminPath === 'function'
                ? store.adminPath('admin-editor.php', params)
                : `admin-editor.php?${new URLSearchParams(params).toString()}`;
        },

        async openOrCreateSibling(state) {
            if (!state || !state.language || state.current) return;
            if (state.status !== 'missing') {
                window.location.href = this.siblingEditorUrl(state.language);
                return;
            }
            try {
                await window.api.createTranslationSibling(
                    this.currentCollection || this.form.category || 'general',
                    this.form.id,
                    state.language
                );
                window.location.href = this.siblingEditorUrl(state.language);
            } catch (error) {
                this.showToast('Could not create sibling: ' + error.message, 'error');
            }
        },

        cloneIdentityValue(value) {
            return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
        },

        captureTranslationIdentity(frontmatter, composite) {
            const locked = {};
            const structuralKeys = ['slug', 'category', 'domain', 'page', 'tags', 'posts', 'articles'];
            structuralKeys.forEach((key) => {
                if (Object.prototype.hasOwnProperty.call(frontmatter || {}, key)) {
                    locked[key] = this.cloneIdentityValue(frontmatter[key]);
                }
            });
            Object.keys(frontmatter || {}).forEach((key) => {
                if (key.startsWith('taxonomy_')) {
                    locked[key] = this.cloneIdentityValue(frontmatter[key]);
                }
            });
            this.lockedTranslationMetadata = locked;
            this.lockedComposite = !!composite;
        },

        enforceTranslationIdentity(metadata) {
            if (!this.isTranslation || !this.lockedTranslationMetadata) return metadata;
            const locked = this.lockedTranslationMetadata;
            const structuralKeys = new Set([
                'slug', 'category', 'domain', 'page', 'tags', 'posts', 'articles'
            ]);
            Object.keys(metadata).forEach((key) => {
                if (structuralKeys.has(key) || key.startsWith('taxonomy_')) {
                    delete metadata[key];
                }
            });
            Object.entries(locked).forEach(([key, value]) => {
                metadata[key] = this.cloneIdentityValue(value);
            });
            return metadata;
        },

        async init() {
            window.addEventListener('pen:toast', (e) => {
                if (e.detail && e.detail.message) {
                    this.showToast(e.detail.message, e.detail.type || 'success');
                }
            });

            window.addEventListener('keydown', (e) => {
                if (e.defaultPrevented) return;
                if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
                    e.preventDefault();
                    this.save();
                }
            });

            // Warm published-page catalog for typeahead, save warn, and AI tools.
            // Fire-and-forget; helpers still fall back to listPages if needed.
            try {
                const store = Alpine.store('app');
                if (store && typeof store.ensurePages === 'function') {
                    store.ensurePages().catch(() => {});
                }
            } catch (_) { /* ignore */ }

            // Expose frontmatter to the AI sidebar.
            // The Traven editor only contains the body (no ---/YAML fences), so
            // editor.getMarkdownState().frontmatter is always empty.  The sidebar
            // needs the actual frontmatter fields, which live in `this.form`.
            // Serialise them as simple `key: value` lines — the same shape that
            // `parseSimpleFrontmatter()` in ai-sidebar.js expects.
            const self = this;
            window.getPenFrontmatter = () => {
                const f = self.form;
                const lines = [];
                // Core identity fields
                if (f.name)        lines.push(`name: ${f.name}`);
                if (f.hero_title)  lines.push(`hero_title: ${f.hero_title}`);
                if (f.status)      lines.push(`status: ${f.status}`);
                if (f.category)    lines.push(`category: ${f.category}`);
                if (f.domain)      lines.push(`domain: ${f.domain}`);
                if (f.page !== undefined && f.page !== '')
                    lines.push(`page: ${f.page}`);
                if (f.pinned)
                    lines.push(`pinned: true`);
                if (f.noindex)
                    lines.push(`noindex: true`);
                if (f.confidence !== undefined && f.confidence !== '')
                    lines.push(`confidence: ${f.confidence}`);
                // Dates and attribution
                if (f.date)        lines.push(`date: ${f.date}`);
                if (f.publish_at)  lines.push(`publish_at: ${f.publish_at}`);
                if (f.author)      lines.push(`author: ${f.author}`);
                // Presentation
                if (f.deck)        lines.push(`deck: ${f.deck}`);
                if (f.summary)     lines.push(`summary: ${f.summary}`);
                if (f.trumpet)     lines.push(`trumpet: ${f.trumpet}`);
                if (f.hero_image)  lines.push(`hero_image: ${f.hero_image}`);
                if (f.main_image)  lines.push(`main_image: ${f.main_image}`);
                // Editorial
                if (f.published !== undefined && f.published !== '')
                    lines.push(`published: ${f.published}`);
                if (f.notes)       lines.push(`notes: ${f.notes}`);
                // Tags (simple inline list)
                if (Array.isArray(f.tags) && f.tags.length > 0)
                    lines.push(`tags: [${f.tags.join(', ')}]`);
                if (Array.isArray(f.faqs) && f.faqs.length > 0)
                    lines.push(`faqs: ${JSON.stringify(f.faqs)}`);
                // Agent provenance
                if (f.created_by && f.created_by !== 'human')
                    lines.push(`created_by: ${f.created_by}`);
                if (f.needs_review) lines.push(`needs_review: ${f.needs_review}`);
                if (f.source)      lines.push(`source: ${f.source}`);
                return lines.join('\n');
            };

            try {
                const generalConfig = await window.api.getGeneralConfig();
                const useAI = generalConfig.use_ai === true;

                const boot = window.PEN_EDITOR_SKIN_BOOT || {};
                const saved = localStorage.getItem('pen_editor_workspace_prefs');
                if (saved) {
                    this.workspacePrefs = { 
                        sidebarWidth: 32, 
                        rightColumnWidth: 25, 
                        leftColumnCollapsed: false, 
                        rightColumnCollapsed: false, 
                        documentOutlineCollapsed: true, 
                        aiAssistantCollapsed: false, 
                        ...this.workspacePrefs, 
                        ...JSON.parse(saved) 
                    };
                }

                // When the active site theme changes, reset to that theme's editor_skin.
                // Same theme: keep a user-picked override only if it is still in the picker map
                // (retired vendor keys like light/custom fall back to boot).
                const activeThemeId = boot.themeId || '';
                const bootSkinKey = boot.skinKey || 'starter';
                const skinsMap = window.PEN_EDITOR_SKINS || {};
                if (!activeThemeId || this.workspacePrefs.editorSkinThemeId !== activeThemeId) {
                    this.workspacePrefs.editorSkin = bootSkinKey;
                    this.workspacePrefs.editorSkinThemeId = activeThemeId;
                } else if (!this.workspacePrefs.editorSkin || !skinsMap[this.workspacePrefs.editorSkin]) {
                    this.workspacePrefs.editorSkin = bootSkinKey;
                }

                if (!useAI) {
                    this.workspacePrefs.documentOutlineCollapsed = false;
                }

                this.saveWorkspacePrefs();
                this.applySkin();
            } catch (e) { /* ignore */ }

            this.config = await window.api.getConfig();
            try {
                this.translationConfig = await window.api.getTranslationConfig();
            } catch (error) {
                console.warn('Translation configuration unavailable:', error);
            }
            
            // Set up default category/collection if not selected
            if (this.config && this.config.primary_vocabulary) {
                const vocab = this.config.taxonomy?.[this.config.primary_vocabulary];
                if (vocab && vocab.terms && vocab.terms.length > 0) {
                    this.form.category = vocab.terms[0];
                } else {
                    this.form.category = this.config.primary_vocabulary;
                }
            }

            await this.loadAuthors();

            const urlParams = new URLSearchParams(window.location.search);
            const id = urlParams.get('id');
            const requestedLanguage = String(urlParams.get('lang') || '')
                .trim().replace(/_/g, '-').toLowerCase();
            this.requestedLanguage = requestedLanguage || null;
            this.currentLanguage = this.requestedLanguage || this.translationConfig.language || 'en';
            this.currentCollection = urlParams.get('collection') || urlParams.get('category') || null;

            if (id) {
                this.isNew = false;
                await this.loadPage(id);
                await this.loadAssets();
            } else {
                this.requestedLanguage = null;
                this.currentLanguage = this.translationConfig.language || 'en';
                this.restoreDraft();
                if (urlParams.get('page') === 'true') {
                    this.form.page = true;
                }
                if (!this.form.date) {
                    this.form.date = new Date().toISOString().split('T')[0];
                }
                if (!this.form.author) {
                    await this.prefillAuthor();
                } else {
                    this.syncAuthorPickerFromForm();
                }
                await this.loadAssets();
            }

            // Auto-generate slug from name (priority) or hero_title (fallback)
            const updateSlug = () => {
                if (!this.isNew || this.slugManuallyEdited) return;
                const source = this.form.name || this.form.hero_title || '';
                this.form.id = this.nameToSlug(source);
            };

            this.$watch('form.name', updateSlug);
            this.$watch('form.hero_title', updateSlug);

            // Auto-save watch
            this.$watch('form', () => {
                if (this.loading) return;
                if (this.saveStatus !== 'saving') {
                    this.saveStatus = 'unsaved';
                }
                if (this.isNew) {
                    this.scheduleDraftSave();
                } else {
                    this.scheduleServerSave();
                }
            }, { deep: true });

            this.$watch('form.composite', (val) => {
                if (val) {
                    this.initAllPartials();
                }
            });

            this.$watch('form.page', (val) => {
                if (val) {
                    this.form.category = '';
                } else {
                    // Restore default category if empty
                    if (!this.form.category && this.config && this.config.primary_vocabulary) {
                        const vocab = this.config.taxonomy?.[this.config.primary_vocabulary];
                        if (vocab && vocab.terms && vocab.terms.length > 0) {
                            this.form.category = vocab.terms[0];
                        } else {
                            this.form.category = this.config.primary_vocabulary;
                        }
                    }
                }
            });

            this.$watch(
                () => this.$store.app.activeSiteId,
                async (next, prev) => {
                    if (next && next !== prev) {
                        await this.loadAuthors();
                    }
                }
            );

            this._initMainEditor();
            this.initAllPartials();

            this.$nextTick(() => {
                const trumpetInput = document.querySelector('input[x-model="form.trumpet"], textarea[x-model="form.trumpet"]');
                const titleInput = document.querySelector('textarea[x-model="form.hero_title"], input[x-model="form.hero_title"]');
                const deckInput = document.querySelector('textarea[x-model="form.deck"], input[x-model="form.deck"]');
                const summaryInput = document.querySelector('textarea[x-model="form.summary"], input[x-model="form.summary"]');

                if (trumpetInput) {
                    trumpetInput.addEventListener('focus', () => { this.activePartial = 'trumpet'; });
                }
                if (titleInput) {
                    titleInput.addEventListener('focus', () => { this.activePartial = 'title'; });
                }
                if (deckInput) {
                    deckInput.addEventListener('focus', () => { this.activePartial = 'deck'; });
                }
                if (summaryInput) {
                    summaryInput.addEventListener('focus', () => { this.activePartial = 'summary'; });
                }
            });
        },

        // ── Toast Notifications ──────────────────────────────────────
        showToast(message, type = 'success') {
            const id = ++this.toastCounter;
            this.toasts.push({ id, message, type });
            setTimeout(() => {
                this.toasts = this.toasts.filter(t => t.id !== id);
            }, 4000);
        },

        // ── Auto-save (localStorage) ────────────────────────────────
        scheduleDraftSave() {
            clearTimeout(this.autoSaveTimer);
            this.autoSaveTimer = setTimeout(() => {
                try {
                    localStorage.setItem(this.autoSaveKey, JSON.stringify(this.form));
                } catch (e) { /* ignore */ }
            }, 2000);
        },

        scheduleServerSave() {
            if (this.conflictModalOpen) return;
            clearTimeout(this.serverSaveTimer);
            this.serverSaveTimer = setTimeout(() => {
                if (this.conflictModalOpen || this.saving) return;
                this.save({ silent: true });
            }, 30000); // 30-second debounce
        },

        restoreDraft() {
            try {
                const raw = localStorage.getItem(this.autoSaveKey);
                if (!raw) return;
                const saved = JSON.parse(raw);
                if (saved && saved.name) {
                    this.resumeModalDraft = saved;
                    this.resumeModalOpen = true;
                }
            } catch (e) { localStorage.removeItem(this.autoSaveKey); }
        },

        acceptResumeDraft() {
            if (this.resumeModalDraft) {
                const saved = this.resumeModalDraft;
                this.form = { ...this.form, ...saved };
                this.slugManuallyEdited = true;
                if (this.config && this.config.primary_vocabulary && this.form.category === this.config.primary_vocabulary) {
                    const vocab = this.config.taxonomy?.[this.config.primary_vocabulary];
                    if (vocab && vocab.terms && vocab.terms.length > 0) {
                        this.form.category = vocab.terms[0];
                    }
                }
            }
            this.resumeModalOpen = false;
            this.resumeModalDraft = null;
        },

        discardResumeDraft() {
            localStorage.removeItem(this.autoSaveKey);
            this.resumeModalOpen = false;
            this.resumeModalDraft = null;
        },

        clearDraft() {
            localStorage.removeItem(this.autoSaveKey);
        },

        saveWorkspacePrefs() {
            try {
                localStorage.setItem('pen_editor_workspace_prefs', JSON.stringify(this.workspacePrefs));
                const html = document.documentElement;
                html.classList.toggle('pref-left-collapsed', !!this.workspacePrefs.leftColumnCollapsed);
                html.classList.toggle('pref-right-collapsed', !!this.workspacePrefs.rightColumnCollapsed);
                html.classList.toggle('pref-secondary-rail-collapsed', !!this.workspacePrefs.secondaryRailCollapsed);
            } catch (e) { /* ignore */ }
        },

        applySkin(skinName) {
            const boot = window.PEN_EDITOR_SKIN_BOOT || {};
            const skinsMap = window.PEN_EDITOR_SKINS || {};
            const bootSkinKey = boot.skinKey || 'starter';

            if (skinName) {
                // Unknown / retired keys (e.g. light, custom) → active theme boot skin
                this.workspacePrefs.editorSkin = skinsMap[skinName] ? skinName : bootSkinKey;
                if (boot.themeId) {
                    this.workspacePrefs.editorSkinThemeId = boot.themeId;
                }
                this.saveWorkspacePrefs();
            }

            let skin = this.workspacePrefs.editorSkin || bootSkinKey;
            if (!skinsMap[skin] && !(boot.skinKey === skin && Array.isArray(boot.hrefs))) {
                skin = bootSkinKey;
                this.workspacePrefs.editorSkin = skin;
            }

            let hrefs = [];
            // Prefer boot.hrefs for the active theme skin key. skinsMap can shadow the
            // same key with a site-custom copy (stale or 404), which strips the working
            // boot <link> and leaves the hero title block unstyled after init.
            if (skin === bootSkinKey && Array.isArray(boot.hrefs) && boot.hrefs.length) {
                hrefs = boot.hrefs.filter(Boolean);
            } else if (skinsMap[skin] && Array.isArray(skinsMap[skin].hrefs)) {
                hrefs = skinsMap[skin].hrefs.filter(Boolean);
            } else if (boot.skinKey === skin && Array.isArray(boot.hrefs)) {
                hrefs = boot.hrefs.filter(Boolean);
            } else if (skinsMap[bootSkinKey] && Array.isArray(skinsMap[bootSkinKey].hrefs)) {
                hrefs = skinsMap[bootSkinKey].hrefs.filter(Boolean);
                skin = bootSkinKey;
            } else if (Array.isArray(boot.hrefs)) {
                hrefs = boot.hrefs.filter(Boolean);
                skin = bootSkinKey;
            }

            document.querySelectorAll('link[id^="traven-skin"]').forEach((el) => el.remove());

            // Insert after admin-editor.css when present so dual-duty skin wins cascade
            // over host glue; otherwise after traven.css (legacy boot order).
            const adminEditorLink = document.querySelector('link[href*="admin-editor.css"]');
            const travenLink = document.querySelector('link[href*="traven.css"]');
            let insertAfter = adminEditorLink || travenLink;
            const cacheBust = String(Date.now());
            hrefs.forEach((href, idx) => {
                const link = document.createElement('link');
                link.id = 'traven-skin-' + idx;
                link.rel = 'stylesheet';
                const join = href.includes('?') ? '&' : '?';
                link.href = href + join + 'v=' + cacheBust;
                if (insertAfter) {
                    insertAfter.after(link);
                } else {
                    document.head.appendChild(link);
                }
                insertAfter = link;
            });

            window.dispatchEvent(new CustomEvent('pen:skin-changed', { detail: { skin, hrefs } }));
        },

        updateVimMode() {
            const enabled = !!this.workspacePrefs.vimMode;
            if (_editors.main && typeof _editors.main.setVimMode === 'function') {
                _editors.main.setVimMode(enabled);
            }
            Object.keys(_editors.partials).forEach(k => {
                const ed = _editors.partials[k];
                if (ed && typeof ed.setVimMode === 'function') {
                    ed.setVimMode(enabled);
                }
            });
        },

        toggleRawMarkdown() {
            this.workspacePrefs.rawMarkdown = !this.workspacePrefs.rawMarkdown;
            this.saveWorkspacePrefs();

            this.$nextTick(() => {
                if (_editors.main) {
                    const view = _editors.main.getView();
                    if (view) view.requestMeasure();
                }
                Object.keys(_editors.partials).forEach(name => {
                    const ed = _editors.partials[name];
                    if (ed) {
                        const view = ed.getView();
                        if (view) view.requestMeasure();
                    }
                });
            });
        },

        nameToSlug(name) {
            return name.toLowerCase().trim()
                .replace(/[^\w\s-]/g, '').replace(/[\s_]+/g, '-')
                .replace(/-+/g, '-').replace(/^-|-$/g, '');
        },

        // ── Site authors (byline picker) ────────────────────────────
        async loadAuthors() {
            try {
                const siteId = Alpine.store('app').activeSiteId || 'default';
                const response = await window.api.getAuthors();
                if (response.site_id && response.site_id !== siteId) {
                    this.authors = [];
                    this.syncAuthorPickerFromForm();
                    return;
                }
                const list = Array.isArray(response.authors) ? response.authors.slice() : [];
                list.sort((a, b) => {
                    const ao = Number(a.sort_order) || 0;
                    const bo = Number(b.sort_order) || 0;
                    if (ao !== bo) return ao - bo;
                    return String(a.name || '').localeCompare(String(b.name || ''));
                });
                this.authors = list;
            } catch (err) {
                console.error('Failed to load authors:', err);
                this.authors = [];
            }
            this.syncAuthorPickerFromForm();
        },

        /** Map form.author (byline string) onto select/custom UI. Never touches form.name. */
        syncAuthorPickerFromForm() {
            const byline = (this.form.author || '').trim();
            if (!byline) {
                this.authorMode = 'pick';
                this.authorSelect = '';
                this.authorCustom = '';
                return;
            }
            const match = this.authors.find(
                (a) => String(a.name || '').trim().toLowerCase() === byline.toLowerCase()
            );
            if (match) {
                this.authorMode = 'pick';
                this.authorSelect = match.name;
                this.authorCustom = '';
                return;
            }
            this.authorMode = 'custom';
            this.authorSelect = '__custom__';
            this.authorCustom = this.form.author;
        },

        onAuthorSelectChange() {
            if (this.authorSelect === '__custom__') {
                this.authorMode = 'custom';
                this.form.author = this.authorCustom || '';
                return;
            }
            this.authorMode = 'pick';
            this.authorCustom = '';
            this.form.author = this.authorSelect || '';
        },

        onAuthorCustomInput() {
            this.form.author = this.authorCustom || '';
        },

        async prefillAuthor() {
            let displayName = '';
            let username = '';
            try {
                const data = await window.AUTH.getMe();
                const profile = (data && data.user) || {};
                displayName = (profile.display_name || '').trim();
                username = (profile.username || '').trim();
            } catch (e) { /* ignore */ }

            const candidates = [displayName, username]
                .filter(Boolean)
                .map((s) => s.toLowerCase());

            if (this.authors.length > 0) {
                const match = this.authors.find((a) =>
                    candidates.includes(String(a.name || '').trim().toLowerCase())
                );
                if (match) {
                    this.form.author = match.name;
                    this.syncAuthorPickerFromForm();
                    return;
                }
                this.form.author = this.authors[0].name || '';
                this.syncAuthorPickerFromForm();
                return;
            }

            const fallback = displayName || username || window.AUTH?.userId || '';
            this.form.author = fallback;
            this.syncAuthorPickerFromForm();
        },

        // ── Load / Save ─────────────────────────────────────────────
        async loadPage(id) {
            this.loading = true;
            try {
                // Read category from URL params if present, else fallback
                const urlParams = new URLSearchParams(window.location.search);
                const category = this.currentCollection
                    || urlParams.get('collection')
                    || urlParams.get('category')
                    || null;
                
                const page = await window.api.getPage(
                    id,
                    category,
                    this.currentLanguage
                );
                this.currentLanguage = page.language
                    || this.currentLanguage
                    || this.translationConfig.language;
                this.currentCollection = category
                    || page.frontmatter.category
                    || 'general';
                this.translationPeers = page.translations || [];
                this.captureTranslationIdentity(page.frontmatter, page.composite);
                
                // Convert bare relative image paths to site-scoped API URLs for editor preview.
                // Do not rewrite paths already under /api/ (avoids doubling sites/.../assets/images/content/).
                let content = this.toEditorContentUrls(page.content || '');

                const partials = {};
                if (page.partials) {
                    Object.keys(page.partials).forEach(k => {
                        partials[k] = this.toEditorContentUrls(page.partials[k] || '');
                    });
                }

                this.form = {
                    ...this.form, ...page.frontmatter,
                    content: content, id: page.id,
                    composite: page.composite || false,
                    partials: partials,
                    posts: page.frontmatter.posts || [],
                    faqs: this.normalizeFaqs(page.frontmatter.faqs),
                    page: page.frontmatter.page === true || page.frontmatter.page === 'true',
                    pinned: page.frontmatter.pinned === true || page.frontmatter.pinned === 'true',
                    noindex: page.frontmatter.noindex === true || page.frontmatter.noindex === 'true'
                };
                this.contentVersion = page.version || null;

                // Map and resolve vocabularies dynamically based on the current primary_vocabulary
                if (this.config && this.config.taxonomy) {
                    const rawCategory = page.frontmatter.category || '';
                    let rawCategoryVocab = null;
                    
                    // Determine which vocabulary the rawCategory value belongs to
                    Object.entries(this.config.taxonomy).forEach(([vocabKey, vocab]) => {
                        if (vocab.terms && vocab.terms.includes(rawCategory)) {
                            rawCategoryVocab = vocabKey;
                        }
                    });

                    Object.keys(this.config.taxonomy).forEach(vocabKey => {
                        const prefixedKey = 'taxonomy_' + vocabKey;
                        
                        // Find the value for this vocabulary in the frontmatter
                        let resolvedValue = page.frontmatter[prefixedKey] ?? page.frontmatter[vocabKey] ?? null;
                        
                        // If no value found under normal keys, check if the rawCategory belongs to this vocabulary
                        if (resolvedValue === null && vocabKey === rawCategoryVocab) {
                            resolvedValue = rawCategory;
                        }

                        if (vocabKey === this.config.primary_vocabulary) {
                            // The primary vocabulary value is stored in form.category
                            if (resolvedValue !== null) {
                                this.form.category = resolvedValue;
                            }
                        } else {
                            // Non-primary vocabulary values are stored in form.taxonomy_vocabKey
                            if (resolvedValue !== null) {
                                this.form[prefixedKey] = resolvedValue;
                            }
                        }
                    });
                }
                
                const hasIndex = this.form.posts.length > 0 && this.form.posts[0].id === 'index';
                if (!hasIndex) this.form.posts.unshift({ id: 'index', title: '', metadata: [], tags: [] });
                this.form.posts.forEach(a => {
                    if (!a.metadata) a.metadata = [];
                    if (!a.tags) a.tags = [];
                });
                if (!this.form.date) {
                    this.form.date = new Date().toISOString().split('T')[0];
                }

                this.syncAuthorPickerFromForm();
                
                // If editor is already initialized, populate it
                if (_editors.main) {
                    _editors.main.setValue(this.form.content);
                }
                this.saveStatus = 'saved';
            } catch (err) {
                console.error(err);
                this.showToast('Failed to load post.', 'error');
            } finally {
                this.$nextTick(() => {
                    setTimeout(() => { this.loading = false; }, 100);
                });
            }
        },

        async save(options = {}) {
            this.saving = true;
            if (!options.silent) {
                this.manualSaving = true;
            }
            this.saveStatus = 'saving';
            try {
                if (_editors.main) {
                    this.form.content = _editors.main.getValue();
                }
                Object.keys(_editors.partials).forEach(name => {
                    if (_editors.partials[name]) {
                        this.form.partials[name] = _editors.partials[name].getValue();
                    }
                });

                // Auto-generate slug/ID if empty
                if (!this.form.id || !this.form.id.trim()) {
                    const source = this.form.name || this.form.hero_title || '';
                    if (source) {
                        this.form.id = this.nameToSlug(source);
                    }
                }

                // If slug is still empty, or equals "undefined" / "null", block save
                if (!this.form.id || !this.form.id.trim() || ['undefined', 'null'].includes(this.form.id.trim().toLowerCase())) {
                    throw new Error("A page slug is required and cannot be empty, 'undefined', or 'null'. Please provide a title or slug.");
                }

                const { content, composite, partials, id, frontmatter, ...metadata } = this.form;
                
                // For non-primary vocabularies, delete the legacy unprefixed keys from metadata
                if (this.config && this.config.taxonomy) {
                    Object.keys(this.config.taxonomy).forEach(vocabKey => {
                        // Never delete the system 'category' key from metadata since it holds the primary vocabulary value
                        if (vocabKey !== this.config.primary_vocabulary && vocabKey !== 'category') {
                            delete metadata[vocabKey];
                        }
                    });
                }

                [
                    'created_by',
                    'created_by_id',
                    'updated_by',
                    'updated_by_id',
                    'run_id',
                    'needs_review',
                    'reviewed_by',
                    'reviewed_at',
                    'review_decision',
                    'review_note',
                    'language',
                    'translation_group'
                ].forEach((key) => delete metadata[key]);
                this.enforceTranslationIdentity(metadata);

                const cleanMetadata = {};
                Object.keys(metadata).forEach(key => {
                    if (metadata[key] !== null && metadata[key] !== '') {
                        if (key === 'page' && !metadata[key]) {
                            return;
                        }
                        if (key === 'pinned' && !metadata[key]) {
                            return;
                        }
                        if (key === 'noindex' && !metadata[key]) {
                            return;
                        }
                        cleanMetadata[key] = metadata[key];
                    }
                });

                if (Array.isArray(cleanMetadata.faqs)) {
                    cleanMetadata.faqs = this.normalizeFaqs(cleanMetadata.faqs)
                        .filter((item) => item.q !== '' || item.a !== '');
                }

                // Clean proxy image paths to relative paths before saving to disk
                const cleanContent = this.fromEditorContentUrls(content || '');
                const cleanPartials = {};
                if (partials) {
                    Object.keys(partials).forEach(key => {
                        cleanPartials[key] = this.fromEditorContentUrls(partials[key] || '');
                    });
                }
                if (this.isTranslation && this.lockedTranslationMetadata) {
                    const manifest = this.lockedTranslationMetadata.posts
                        || this.lockedTranslationMetadata.articles
                        || [];
                    const allowed = new Set(
                        manifest
                            .filter((item) => item && item.id && item.id !== 'index')
                            .map((item) => item.id)
                    );
                    Object.keys(cleanPartials).forEach((key) => {
                        if (!allowed.has(key)) delete cleanPartials[key];
                    });
                    allowed.forEach((key) => {
                        if (!Object.prototype.hasOwnProperty.call(cleanPartials, key)) {
                            cleanPartials[key] = '';
                        }
                    });
                }

                const payload = {
                    frontmatter: cleanMetadata,
                    content: cleanContent,
                    composite: this.isTranslation ? this.lockedComposite : (composite || false),
                    partials: cleanPartials
                };
                if (options.force) {
                    payload.force = true;
                } else if (this.contentVersion != null && this.contentVersion !== '') {
                    payload.expected_version = this.contentVersion;
                }

                let result;
                if (this.isNew) {
                    result = await window.api.createPage({ ...payload, slug: this.form.id });
                    this.form.id = result.id;
                    this.isNew = false;
                    this.contentVersion = result.version || null;
                    this.clearDraft();
                    const editorParams = { id: result.id };
                    if (this.form.page) editorParams.page = 'true';
                    if (this.currentCollection || this.form.collection) {
                        editorParams.collection = this.currentCollection || this.form.collection;
                    }
                    const store = (window.Alpine && Alpine.store('app')) || null;
                    const href = (store && typeof store.adminPath === 'function')
                        ? store.adminPath('admin-editor.php', editorParams)
                        : ('admin-editor.php?id=' + encodeURIComponent(result.id));
                    history.replaceState(null, '', href);
                    await this.loadAssets();
                } else {
                    result = await window.api.updatePage(
                        id,
                        payload,
                        this.currentLanguage,
                        this.currentCollection
                    );
                    if (result && result.version) {
                        this.contentVersion = result.version;
                    }
                }
                if (result && result.version_warning) {
                    this.showToast(
                        'Document was modified by another user or agent; your save was applied.',
                        'error'
                    );
                }
                if (!options.silent) {
                    this.showToast('Post saved successfully.');
                    this._warnBrokenExpandRefs(cleanContent, cleanPartials);
                }
                this.saveStatus = 'saved';
                return { success: true };
            } catch (err) {
                this.saveStatus = 'unsaved';
                const ApiErrorType = window.ApiError || (typeof ApiError !== 'undefined' ? ApiError : null);
                if (
                    ApiErrorType &&
                    err instanceof ApiErrorType &&
                    err.status === 409 &&
                    err.detail &&
                    err.detail.error === 'version_conflict'
                ) {
                    this.conflictModalOpen = true;
                    if (options.throwOnError) {
                        throw err;
                    }
                    return { success: false, error: err.message, conflict: true };
                }
                this.showToast('Error: ' + err.message, 'error');
                if (options.throwOnError) {
                    throw err;
                }
                return { success: false, error: err.message };
            } finally {
                this.saving = false;
                this.manualSaving = false;
            }
        },

        async reloadFromConflict() {
            this.conflictModalOpen = false;
            if (this.form.id) {
                await this.loadPage(this.form.id);
            }
        },

        async overwriteFromConflict() {
            this.conflictModalOpen = false;
            await this.save({ force: true });
        },

        // ── Assets ──────────────────────────────────────────────────
        async loadAssets() {
            if (this.form.id) {
                try {
                    this.availableAssets = await window.api.listAssets(this.form.category, this.form.id);
                } catch (err) { console.warn('Failed to load assets:', err); }
            } else {
                this.availableAssets = [];
            }
            try {
                const all = await window.api.listAllAssets();
                this.globalAssets = all.filter(a => !this.form.id || a.entity_id !== this.form.id);
            } catch (err) { console.warn('Failed to load global assets:', err); }
        },

        get filteredGlobalAssets() {
            let assets = [...this.globalAssets];
            if (this.form.id) {
                assets = assets.filter(a => a.entity_id !== this.form.id);
            }
            if (this.globalSearchQuery.trim()) {
                const q = this.globalSearchQuery.toLowerCase();
                assets = assets.filter(a => a.filename.toLowerCase().includes(q) || a.path.toLowerCase().includes(q));
            }
            if (this.globalSortOrder === 'newest') {
                assets.sort((a, b) => b.modified_at.localeCompare(a.modified_at));
            } else if (this.globalSortOrder === 'oldest') {
                assets.sort((a, b) => a.modified_at.localeCompare(b.modified_at));
            } else if (this.globalSortOrder === 'az') {
                assets.sort((a, b) => a.filename.localeCompare(b.filename));
            }
            return assets;
        },

        formatBytes(bytes) {
            if (bytes === null || bytes === undefined || isNaN(bytes)) return '';
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
        },

        async handleFileUpload(event) {
            const file = event.target?.files?.[0];
            if (!file) return;
            if (this.config?.max_upload_size && file.size > this.config.max_upload_size) {
                this.showToast('File too large.', 'error');
                if (event.target) event.target.value = '';
                return;
            }
            this.isUploading = true;
            try {
                const result = await window.api.uploadAsset(this.form.category, this.form.id, file);
                await this.loadAssets();
                this.showToast('Image uploaded.');
            } catch (err) {
                this.showToast('Upload failed: ' + err.message, 'error');
            } finally {
                this.isUploading = false;
                if (event.target) event.target.value = '';
            }
        },

        async handleDrop(event) {
            this.dragOver = false;
            const file = event.dataTransfer?.files?.[0];
            if (!file || !file.type.startsWith('image/')) return;
            if (!this.form.id) {
                this.showToast('Save the post first to enable uploads.', 'error');
                return;
            }
            if (this.config?.max_upload_size && file.size > this.config.max_upload_size) {
                this.showToast('File too large.', 'error');
                return;
            }
            this.isUploading = true;
            try {
                const result = await window.api.uploadAsset(this.form.category, this.form.id, file);
                await this.loadAssets();
                this.showToast('Image uploaded via drag & drop.');
            } catch (err) {
                this.showToast('Upload failed: ' + err.message, 'error');
            } finally { this.isUploading = false; }
        },

        async handleHeroDrop(event) {
            this.dragOver = false;
            const file = event.dataTransfer?.files?.[0];
            if (!file || !file.type.startsWith('image/')) return;
            if (!this.form.id) {
                this.showToast('Save the post first to enable uploads.', 'error');
                return;
            }
            if (this.config?.max_upload_size && file.size > this.config.max_upload_size) {
                this.showToast('File too large.', 'error');
                return;
            }
            this.isUploading = true;
            try {
                const result = await window.api.uploadAsset(this.form.category, this.form.id, file);
                await this.loadAssets();
                if (result?.path) this.form.hero_image = result.path;
                this.showToast('Hero image uploaded and set.');
            } catch (err) {
                this.showToast('Upload failed: ' + err.message, 'error');
            } finally { this.isUploading = false; }
        },

        async handleHeroUpload(event) {
            const file = event.target?.files?.[0];
            if (!file) return;
            if (this.config?.max_upload_size && file.size > this.config.max_upload_size) {
                this.showToast('File too large.', 'error');
                if (event.target) event.target.value = '';
                return;
            }
            this.isUploading = true;
            try {
                const result = await window.api.uploadAsset(this.form.category, this.form.id, file);
                await this.loadAssets();
                if (result?.path) this.form.hero_image = result.path;
                this.showToast('Hero image set.');
            } catch (err) {
                this.showToast('Upload failed: ' + err.message, 'error');
            } finally {
                this.isUploading = false;
                if (event.target) event.target.value = '';
            }
        },

        deleteAsset(asset) {
            if (!this.$store.app.hasCap('delete:media')) return;
            this.assetToDelete = asset;
            this.deleteAssetModalOpen = true;
        },
        async confirmDeleteAsset() {
            if (!this.assetToDelete || !this.$store.app.hasCap('delete:media')) return;
            const asset = this.assetToDelete;
            try {
                await window.api.deleteAsset(this.form.category, this.form.id, asset.filename);
                if (this.form.main_image === asset.path) this.form.main_image = '';
                if (this.form.hero_image === asset.path) this.form.hero_image = '';
                await this.loadAssets();
                this.showToast('Asset deleted.');
                this.deleteAssetModalOpen = false;
                this.assetToDelete = null;
            } catch (err) { 
                this.showToast('Delete failed.', 'error'); 
            }
        },

        // ── Modal ────────────────────────────────────────────────────
        openModal(asset) {
            if (typeof asset === 'string') {
                this.modalImage = this.availableAssets.find(a => a.path === asset) ||
                    this.globalAssets.find(a => a.path === asset) ||
                    { url: this.contentAssetUrl(asset), filename: asset.split('/').pop(), path: asset };
            } else {
                this.modalImage = asset;
            }
            this.showModal = true;
        },
        closeModal() { this.showModal = false; this.modalImage = null; },

        togglePostSettings(post) {
            if (this.settingsPost === post) {
                this.settingsPost = null;
            } else {
                this.settingsPost = post;
            }
        },

        // ── Validation ───────────────────────────────────────────────
        get requiredFields() {
            if (this.form.page) {
                return ['name', 'hero_title'];
            }
            if (!this.config) return [];
            return Array.isArray(this.config.required_fields) ? this.config.required_fields : [];
        },
        get missingFields() { return this.requiredFields.filter(f => !this.hasValue(f)); },
        hasValue(field) { return !!this.form[field]; },
        get validationPercentage() {
            if (!this.requiredFields.length) return 100;
            return Math.round(((this.requiredFields.length - this.missingFields.length) / this.requiredFields.length) * 100);
        },
        get wordCount() {
            const countWords = (text) => {
                if (!text) return 0;
                return text.trim().split(/\s+/).filter(w => w.length > 0).length;
            };
            let count = countWords(this.form.content);
            if (this.form.composite && this.form.partials) {
                Object.values(this.form.partials).forEach(content => {
                    count += countWords(content);
                });
            }
            return count;
        },
        formatLabel(f) { return f.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' '); },

        // ── Composite / Fragments ────────────────────────────────────
        activePartial: 'main',

        async initAllPartials() {
            if (this.form.composite && this.form.posts) {
                await this.$nextTick();
                for (const post of this.form.posts.slice(1)) {
                    await this._initPartialEditor(post.id);
                }
            }
        },

        scrollToSection(id) {
            if (id === 'summary') {
                this.expandedPartial = 'summary';
                this.activePartial = 'summary';
            } else if (id === 'faqs') {
                this.expandedPartial = 'faqs';
                this.activePartial = 'faqs';
            } else if (this.expandedPartial !== id) {
                this.expandedPartial = null;
            }
            if (this.collapsedPartials.includes(id)) {
                this.toggleCollapse(id);
            }
            this.$nextTick(() => {
                let el = null;
                if (id === 'hero') {
                    el = document.querySelector('[x-ref="heroInput"]')?.parentElement;
                } else if (id === 'trumpet') {
                    el = document.querySelector('input[x-model="form.trumpet"]');
                } else if (id === 'title') {
                    el = document.querySelector('input[x-model="form.hero_title"]');
                } else if (id === 'deck') {
                    el = document.querySelector('textarea[x-model="form.deck"]');
                } else if (id === 'summary') {
                    el = document.querySelector('textarea[x-model="form.summary"]');
                } else if (id === 'faqs') {
                    el = document.getElementById('editor-faqs-rail');
                } else if (id === 'main') {
                    el = document.getElementById('main-editor');
                } else {
                    el = document.getElementById('partial-editor-' + id);
                }

                if (el) {
                    const section = el.closest('.pen-card') || el.closest('section') || el;
                    section.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    
                    if (typeof el.focus === 'function') {
                        el.focus();
                    } else if (id === 'main') {
                        if (_editors.main) _editors.main.focus();
                    } else if (_editors.partials[id]) {
                        _editors.partials[id].focus();
                    }
                }
            });
        },

        moveFragment(idx, direction) {
            const newIdx = idx + direction;
            if (newIdx < 1 || newIdx >= this.form.posts.length) return;
            const temp = this.form.posts[idx];
            this.form.posts[idx] = this.form.posts[newIdx];
            this.form.posts[newIdx] = temp;
            this.scheduleDraftSave();
        },

        addPartial() {
            this.newFragmentName = '';
            this.addFragmentModalOpen = true;
            this.$nextTick(() => {
                const el = document.getElementById('new-fragment-name-input');
                if (el) el.focus();
            });
        },
        confirmAddPartial() {
            const rawName = this.newFragmentName.trim();
            if (!rawName) return;
            const name = this.nameToSlug(rawName);
            if (name && name !== 'index' && !this.form.partials[name]) {
                this.form.partials[name] = '';
                this.form.posts.push({ id: name, title: rawName, content: '_' + name + '.md', metadata: [], tags: [] });
                this.activePartial = name;
                this._initPartialEditor(name);
                this.addFragmentModalOpen = false;
            } else if (this.form.partials[name]) {
                this.showToast('A fragment with that name already exists.', 'error');
            }
        },
        removePartial(name) {
            this.fragmentToRemove = name;
            this.removeFragmentModalOpen = true;
        },
        confirmRemovePartial() {
            const name = this.fragmentToRemove;
            if (!name) return;
            delete this.form.partials[name];
            this.form.posts = this.form.posts.filter(a => a.id !== name);
            if (this.activePartial === name) {
                this.activePartial = 'main';
                this.updateSharedToolbar('main');
            }
            if (this.settingsPost && this.settingsPost.id === name) {
                this.settingsPost = null;
            }
            if (_editors.partials[name]) { _editors.partials[name].destroy(); delete _editors.partials[name]; }
            this.removeFragmentModalOpen = false;
            this.fragmentToRemove = '';
        },
        togglePartial(name) {
            this.activePartial = this.activePartial === name ? null : name;
            if (name !== 'main' && this.activePartial === name) {
                this._initPartialEditor(name);
            } else {
                this.updateSharedToolbar(this.activePartial);
            }
        },
        toggleCollapse(id) {
            if (this.collapsedPartials.includes(id)) {
                this.collapsedPartials = this.collapsedPartials.filter(x => x !== id);
            } else {
                this.collapsedPartials.push(id);
            }
        },

        // Post metadata/tags helpers
        addPostMetadata(post) { if (!post.metadata) post.metadata = []; post.metadata.push(''); },
        removePostMetadata(post, i) { post.metadata.splice(i, 1); },
        addPostTag(post) { if (!post.tags) post.tags = []; post.tags.push({ label: '', href: '#' }); },
        removePostTag(post, i) { post.tags.splice(i, 1); },

        normalizeFaqs(raw) {
            if (!Array.isArray(raw)) return [];
            return raw.map((item) => ({
                q: String(item && item.q != null ? item.q : ''),
                a: String(item && item.a != null ? item.a : ''),
            }));
        },
        addFaq() {
            if (!Array.isArray(this.form.faqs)) this.form.faqs = [];
            this.form.faqs.push({ q: '', a: '' });
            this.expandedPartial = 'faqs';
            this.activePartial = 'faqs';
        },
        removeFaq(i) {
            if (!Array.isArray(this.form.faqs)) return;
            this.form.faqs.splice(i, 1);
        },
        moveFaq(i, direction) {
            if (!Array.isArray(this.form.faqs)) return;
            const next = i + direction;
            if (next < 0 || next >= this.form.faqs.length) return;
            const copy = this.form.faqs.slice();
            const tmp = copy[i];
            copy[i] = copy[next];
            copy[next] = tmp;
            this.form.faqs = copy;
        },

        get summaryWandActive() {
            return this.summaryWand.status !== 'idle';
        },
        _idleSummaryWand() {
            this.summaryWand.status = 'idle';
            this.summaryWand.preview = '';
            this.summaryWand.error = '';
        },
        _currentSummaryIsEmpty() {
            return !String(this.form.summary || '').trim();
        },
        async runSummaryWand() {
            this.expandedPartial = 'summary';
            this.activePartial = 'summary';
            if (this.summaryWand.status === 'loading') return;
            if (!this._currentSummaryIsEmpty()) {
                this.summaryWand.status = 'confirm-replace';
                this.summaryWand.preview = '';
                this.summaryWand.error = '';
                return;
            }
            await this._fetchSummaryWand(false);
        },
        async confirmSummaryReplace() {
            await this._fetchSummaryWand(true);
        },
        async _fetchSummaryWand(replace) {
            this.summaryWand.status = 'loading';
            this.summaryWand.preview = '';
            this.summaryWand.error = '';
            const body = window.getPenEditor?.('main')?.getValue?.() || '';
            if (!String(body).trim()) {
                this.summaryWand.status = 'error';
                this.summaryWand.error = 'Write some body text first.';
                return;
            }
            if (typeof window.penAiExtract !== 'function') {
                this.summaryWand.status = 'error';
                this.summaryWand.error = 'Extract helper is not loaded.';
                return;
            }
            try {
                const result = await window.penAiExtract({
                    field: 'summary',
                    body,
                    currentValue: this.form.summary || '',
                    replace: !!replace,
                });
                const value = String((result && result.value) || '').trim();
                if (!value) {
                    this.summaryWand.status = 'error';
                    this.summaryWand.error = 'The model returned an empty nutshell.';
                    return;
                }
                this.summaryWand.preview = value;
                this.summaryWand.status = 'preview';
            } catch (err) {
                this.summaryWand.status = 'error';
                this.summaryWand.error = (err && err.message) || 'Could not extract a summary.';
            }
        },
        applySummaryWand() {
            const value = String(this.summaryWand.preview || '').trim();
            if (!value) return;
            this.form.summary = value;
            this._idleSummaryWand();
            this.expandedPartial = 'summary';
            this.activePartial = 'summary';
        },
        discardSummaryWand() {
            this._idleSummaryWand();
            this.expandedPartial = 'summary';
        },

        get faqsWandActive() {
            return this.faqsWand.status !== 'idle';
        },
        _idleFaqsWand() {
            this.faqsWand.status = 'idle';
            this.faqsWand.preview = [];
            this.faqsWand.error = '';
        },
        _currentFaqsIsEmpty() {
            return !Array.isArray(this.form.faqs) || this.form.faqs.length === 0;
        },
        async runFaqsWand() {
            this.expandedPartial = 'faqs';
            this.activePartial = 'faqs';
            if (this.faqsWand.status === 'loading') return;
            if (!this._currentFaqsIsEmpty()) {
                this.faqsWand.status = 'confirm-replace';
                this.faqsWand.preview = [];
                this.faqsWand.error = '';
                return;
            }
            await this._fetchFaqsWand(false);
        },
        async confirmFaqsReplace() {
            await this._fetchFaqsWand(true);
        },
        async _fetchFaqsWand(replace) {
            this.faqsWand.status = 'loading';
            this.faqsWand.preview = [];
            this.faqsWand.error = '';
            const body = window.getPenEditor?.('main')?.getValue?.() || '';
            if (!String(body).trim()) {
                this.faqsWand.status = 'error';
                this.faqsWand.error = 'Write some body text first.';
                return;
            }
            if (typeof window.penAiExtract !== 'function') {
                this.faqsWand.status = 'error';
                this.faqsWand.error = 'Extract helper is not loaded.';
                return;
            }
            try {
                const result = await window.penAiExtract({
                    field: 'faqs',
                    body,
                    currentValue: Array.isArray(this.form.faqs) ? this.form.faqs : [],
                    replace: !!replace,
                });
                const raw = result && result.value;
                this.faqsWand.preview = this.normalizeFaqs(Array.isArray(raw) ? raw : []);
                this.faqsWand.status = 'preview';
            } catch (err) {
                this.faqsWand.status = 'error';
                this.faqsWand.error = (err && err.message) || 'Could not extract FAQs.';
            }
        },
        applyFaqsWand() {
            this.form.faqs = this.normalizeFaqs(this.faqsWand.preview);
            this._idleFaqsWand();
            this.expandedPartial = 'faqs';
            this.activePartial = 'faqs';
        },
        discardFaqsWand() {
            this._idleFaqsWand();
            this.expandedPartial = 'faqs';
        },

        isEditorActive() {
            return this.activePartial === 'main' || (this.form.posts && this.form.posts.slice(1).some(a => a.id === this.activePartial));
        },

        getHeaderHeight() {
            const el = document.getElementById('sticky-control-header');
            if (el) {
                return el.offsetHeight;
            }
            let h = this.workspacePrefs.secondaryRailCollapsed ? 42 : 54;
            if (this.workspacePrefs.mainToolbar && this.isEditorActive() && !this.workspacePrefs.rawMarkdown) {
                h += 20;
            }
            return h;
        },

        updateSharedToolbar(activeEditorKey) {
            const sharedContainer = document.getElementById('shared-editor-toolbar');
            if (!sharedContainer) return;

            // 1. Move any currently shared toolbar back to its original parent editor mount
            const currentShared = sharedContainer.querySelector('.traven-toolbar-container');
            if (currentShared) {
                const origKey = currentShared.dataset.editorKey;
                let origParent = null;
                if (origKey === 'main') {
                    origParent = document.getElementById('main-editor');
                } else if (origKey) {
                    origParent = document.getElementById('partial-editor-' + origKey);
                }
                if (origParent) {
                    origParent.prepend(currentShared);
                }
            }

            // 2. Move the active editor's toolbar to the shared container
            let activeParent = null;
            if (activeEditorKey === 'main') {
                activeParent = document.getElementById('main-editor');
            } else if (activeEditorKey && activeEditorKey !== 'hero' && activeEditorKey !== 'trumpet' && activeEditorKey !== 'title' && activeEditorKey !== 'deck' && activeEditorKey !== 'summary' && activeEditorKey !== 'faqs') {
                activeParent = document.getElementById('partial-editor-' + activeEditorKey);
            }

            if (activeParent) {
                const activeToolbar = activeParent.querySelector('.traven-toolbar-container');
                if (activeToolbar) {
                    activeToolbar.dataset.editorKey = activeEditorKey;
                    sharedContainer.appendChild(activeToolbar);
                }
            }
        },

        // ── Traven Editor Mounting ───────────────────────────────────
        _waitForTravenEditor(attempts = 0) {
            return new Promise((resolve, reject) => {
                const check = () => {
                    if (window.TravenEditor) {
                        if (!window.TravenEditor._mermaidConfigured) {
                            window.TravenEditor.configureMermaid("/assets/vendor/mermaid/mermaid.min.js");
                            window.TravenEditor._mermaidConfigured = true;
                        }
                        return resolve(window.TravenEditor);
                    }
                    if (attempts++ > 40) return reject(new Error('TravenEditor not loaded'));
                    setTimeout(check, 50);
                };
                check();
            });
        },

        /**
         * Host callback for Traven Insert Link modal: suggest published posts/pages
         * from the active Content site (title + bare slug as url).
         */
        async _suggestLinks(query) {
            try {
                const store = window.Alpine && Alpine.store('app');
                if (store && typeof store.getPublishedLinkCatalog === 'function') {
                    const catalog = await store.getPublishedLinkCatalog(query, 12);
                    // Link href is the bare slug; PHP preview + static generators resolve it.
                    return catalog.map((r) => ({
                        title: r.title,
                        url: r.slug,
                        slug: r.slug,
                    }));
                }
            } catch (e) {
                console.warn('onSuggestLinks: failed to load pages', e);
            }
            return [];
        },

        /**
         * Host callback for Expand/Embed Heading dropdown: sections in the chosen slug.
         */
        async _listHeadings(slug) {
            try {
                const store = window.Alpine && Alpine.store('app');
                if (store && typeof store.getPageHeadings === 'function') {
                    return await store.getPageHeadings(slug);
                }
            } catch (e) {
                console.warn('onListHeadings: failed to load headings', e);
            }
            return [];
        },

        /**
         * Host callback for Expand/Embed Target dropdown: summary + deck + sections.
         */
        async _listExpandTargets(slug) {
            try {
                const store = window.Alpine && Alpine.store('app');
                if (store && typeof store.getPageExpandTargets === 'function') {
                    return await store.getPageExpandTargets(slug);
                }
            } catch (e) {
                console.warn('onListExpandTargets: failed to load expand targets', e);
            }
            return { summary: null, deck: null, headings: [] };
        },

        _createExpandEmbedPlugins() {
            if (!window.ExpandEmbedPlugin) return [];
            // Editor WYSIWYM uses attribute cards; public PHP resolves real content.
            return [new window.ExpandEmbedPlugin({ resolve: null })];
        },

        _editorToolbar() {
            const base = Array.from(window.DEFAULT_TOOLBAR || [
                'heading', 'bold', 'italic', 'strikethrough', '|',
                'blockquote', 'code', 'codeblock', '|',
                'bulletlist', 'numberedlist', 'tasklist', '|',
                'table', 'link', 'image'
            ]);
            if (window.EXPAND_EMBED_TOOLBAR && window.EXPAND_EMBED_TOOLBAR.length) {
                const linkIdx = base.indexOf('link');
                if (linkIdx !== -1) {
                    base.splice(linkIdx + 1, 0, ...window.EXPAND_EMBED_TOOLBAR);
                    return base;
                }
                return [...base, '|', ...window.EXPAND_EMBED_TOOLBAR];
            }
            return base;
        },

        /**
         * Selection bubble: Expand after Link only. Embed stays on the main toolbar.
         */
        _editorBubbleToolbar() {
            const base = Array.from(window.DEFAULT_BUBBLE_TOOLBAR || [
                'bold', 'italic', 'strikethrough', 'highlight', 'subscript', 'superscript', 'code', 'link',
                'uppercase', 'lowercase', 'capitalize', 'removeformatting',
                'heading', 'blockquote', 'bulletlist', 'numberedlist', 'tasklist', 'codeblock',
            ]);
            if (window.expandEmbedTools && window.expandEmbedTools.expand) {
                const linkIdx = base.indexOf('link');
                if (linkIdx !== -1) {
                    base.splice(linkIdx + 1, 0, 'expand');
                    return base;
                }
                return [...base, 'expand'];
            }
            return base;
        },

        _expandEmbedExtraTools() {
            return window.expandEmbedTools || null;
        },

        /**
         * Author safeguard: warn when [expand]/[embed] targets are missing
         * from the published catalog of the active Content site.
         */
        async _warnBrokenExpandRefs(content, partials) {
            const blobs = [content || ''];
            if (partials) {
                Object.values(partials).forEach((v) => blobs.push(v || ''));
            }
            const text = blobs.join('\n');
            const re = /\[(expand|embed)\s*([^\]]*)\]/gi;
            const refs = [];
            let m;
            while ((m = re.exec(text)) !== null) {
                const mode = m[1].toLowerCase();
                const attr = m[2] || '';
                let slug = '';
                let heading = null;
                const slugMatch = attr.match(/(?:^|\s)slug\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s\]]+))/i);
                const defMatch = attr.match(/^\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s\]]+))/);
                const headMatch = attr.match(/heading\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s\]]+))/i);
                if (slugMatch) slug = slugMatch[1] || slugMatch[2] || slugMatch[3] || '';
                else if (defMatch) slug = defMatch[1] || defMatch[2] || defMatch[3] || '';
                if (headMatch) heading = headMatch[1] || headMatch[2] || headMatch[3] || null;
                if (slug.includes('#')) {
                    const parts = slug.split('#');
                    slug = parts[0];
                    if (!heading) heading = parts.slice(1).join('#') || null;
                }
                if (slug) refs.push({ mode, slug, heading });
            }
            if (!refs.length) return;

            let published = new Set();
            try {
                const store = window.Alpine && Alpine.store('app');
                if (store && typeof store.getPublishedLinkCatalog === 'function') {
                    const catalog = await store.getPublishedLinkCatalog('', 10000);
                    published = new Set(catalog.map((r) => r.slug).filter(Boolean));
                }
            } catch (e) {
                return;
            }
            const missing = [
                ...new Set(
                    refs
                        .filter((r) => !published.has(String(r.slug || '').trim()))
                        .map((r) => r.slug)
                ),
            ];
            if (missing.length) {
                this.showToast(
                    `Warning: ${missing.length} expand/embed target(s) not found or unpublished: ${missing.slice(0, 3).join(', ')}${missing.length > 3 ? '…' : ''}`,
                    'error'
                );
            }
        },

        async _initMainEditor() {
            await this.$nextTick();
            const el = document.querySelector('#main-editor');
            if (!el || _editors.main) return;

            try {
                const TravenEditor = await this._waitForTravenEditor();

                _editors.main = new TravenEditor({
                    element: el,
                    sourceElement: document.getElementById('raw-main-editor'),
                    initialValue: this.form.content,
                    theme: 'light',
                    lineWrapping: true,
                    vimMode: !!this.workspacePrefs.vimMode,
                    componentsUrl: false,
                    autoLoadStyles: false,
                    katex: {
                        js: "/assets/vendor/katex/katex.min.js",
                        css: "/assets/vendor/katex/katex.min.css"
                    },
                    toolbarMode: 'hybrid',
                    toolbar: this._editorToolbar(),
                    bubbleToolbar: this._editorBubbleToolbar(),
                    plugins: this._createExpandEmbedPlugins(),
                    extraTools: this._expandEmbedExtraTools() || undefined,
                    onSuggestLinks: (query) => this._suggestLinks(query),
                    onListHeadings: (slug) => this._listHeadings(slug),
                    onListExpandTargets: (slug) => this._listExpandTargets(slug),
                    imageAspectOptions: (Array.isArray(window.PEN_EDITOR_IMAGE_ASPECT) && window.PEN_EDITOR_IMAGE_ASPECT.length)
                        ? window.PEN_EDITOR_IMAGE_ASPECT
                        : null,
                    onChange: (val) => {
                        this.form.content = val;
                    },
                    onUploadImage: async (file) => {
                        try {
                            const result = await window.api.uploadAsset(this.form.category, this.form.id, file);
                            await this.loadAssets();
                            return result.url;
                        } catch (e) {
                            this.showToast('Upload failed: ' + e.message, 'error');
                            throw e;
                        }
                    },
                    onPickImage: () => this.pickImageFromLibrary()
                });

                _editors.main.on('save', () => {
                    this.save();
                });

                _editors.lastActive = _editors.main;

                if (this.activePartial === 'main') {
                    this.updateSharedToolbar('main');
                }

                el.addEventListener('focusin', () => {
                    _editors.lastActive = _editors.main;
                    this.activePartial = 'main';
                    this.updateSharedToolbar('main');
                });
            } catch (err) {
                console.error('Failed to initialize main editor:', err);
                this.showToast('Editor failed to load.', 'error');
            }
        },

        async _initPartialEditor(name) {
            await this.$nextTick();
            const el = document.querySelector('#partial-editor-' + name);
            if (!el || _editors.partials[name]) return;

            try {
                const TravenEditor = await this._waitForTravenEditor();

                _editors.partials[name] = new TravenEditor({
                    element: el,
                    sourceElement: document.getElementById('raw-partial-editor-' + name),
                    initialValue: this.form.partials[name] || '',
                    theme: 'light',
                    lineWrapping: true,
                    vimMode: !!this.workspacePrefs.vimMode,
                    componentsUrl: false,
                    autoLoadStyles: false,
                    katex: {
                        js: "/assets/vendor/katex/katex.min.js",
                        css: "/assets/vendor/katex/katex.min.css"
                    },
                    toolbarMode: 'hybrid',
                    toolbar: this._editorToolbar(),
                    bubbleToolbar: this._editorBubbleToolbar(),
                    plugins: this._createExpandEmbedPlugins(),
                    extraTools: this._expandEmbedExtraTools() || undefined,
                    onSuggestLinks: (query) => this._suggestLinks(query),
                    onListHeadings: (slug) => this._listHeadings(slug),
                    onListExpandTargets: (slug) => this._listExpandTargets(slug),
                    imageAspectOptions: (Array.isArray(window.PEN_EDITOR_IMAGE_ASPECT) && window.PEN_EDITOR_IMAGE_ASPECT.length)
                        ? window.PEN_EDITOR_IMAGE_ASPECT
                        : null,
                    onChange: (val) => {
                        this.form.partials[name] = val;
                    },
                    onUploadImage: async (file) => {
                        try {
                            const result = await window.api.uploadAsset(this.form.category, this.form.id, file);
                            await this.loadAssets();
                            return result.url;
                        } catch (e) {
                            this.showToast('Upload failed: ' + e.message, 'error');
                            throw e;
                        }
                    },
                    onPickImage: () => this.pickImageFromLibrary()
                });

                _editors.partials[name].on('save', () => {
                    this.save();
                });

                if (this.activePartial === name) {
                    this.updateSharedToolbar(name);
                }

                el.addEventListener('focusin', () => {
                    _editors.lastActive = _editors.partials[name];
                    this.activePartial = name;
                    this.updateSharedToolbar(name);
                });
            } catch (err) {
                console.error('Failed to initialize partial editor:', err);
                this.showToast('Editor failed to load.', 'error');
            }
        },

        prepareImageInsert(asset) {
            const editorRef = _editors.lastActive || _editors.main;
            if (editorRef && typeof editorRef.openImageModal === 'function') {
                const altText = asset.filename.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ');
                editorRef.openImageModal({
                    src: asset.url,
                    alt: altText
                });
            } else if (editorRef) {
                const altText = asset.filename.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ');
                const imgMarkdown = `![${altText}](${asset.url})`;
                editorRef.replaceSelection(imgMarkdown);
                editorRef.focus();
                this.showToast('Image inserted.');
            } else {
                this.showToast('Select the editor first.', 'error');
            }
        },

        /**
         * Host media-library picker for Traven onPickImage.
         * Opens a compact This Page / Library overlay above the image modal.
         * @returns {Promise<{url: string, alt: string}|null>}
         */
        pickImageFromLibrary() {
            return new Promise((resolve) => {
                const overlay = document.createElement('div');
                overlay.className = 'pen-modal-overlay p-4';
                overlay.style.zIndex = '10050';
                overlay.setAttribute('role', 'presentation');

                const dialog = document.createElement('div');
                dialog.className = 'pen-modal min-w-0 w-full max-w-[520px]';
                dialog.setAttribute('role', 'dialog');
                dialog.setAttribute('aria-modal', 'true');
                dialog.setAttribute('aria-labelledby', 'pen-image-picker-title');

                const header = document.createElement('div');
                header.className = 'pen-modal-header';
                const titleEl = document.createElement('h3');
                titleEl.className = 'pen-modal-title';
                titleEl.id = 'pen-image-picker-title';
                titleEl.textContent = 'Choose from library';
                const closeBtn = document.createElement('button');
                closeBtn.type = 'button';
                closeBtn.className = 'text-forge-mid hover:text-forge-black';
                closeBtn.setAttribute('aria-label', 'Close');
                closeBtn.innerHTML = '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>';
                header.appendChild(titleEl);
                header.appendChild(closeBtn);

                const body = document.createElement('div');
                body.className = 'pen-modal-body space-y-3';

                const tabs = document.createElement('div');
                tabs.className = 'flex gap-4 border-b border-border';
                const tabLocal = document.createElement('button');
                tabLocal.type = 'button';
                tabLocal.className = 'text-[10px] font-black uppercase tracking-wider pb-2 border-b-2 border-rust text-rust';
                tabLocal.textContent = 'This Page';
                const tabGlobal = document.createElement('button');
                tabGlobal.type = 'button';
                tabGlobal.className = 'text-[10px] font-black uppercase tracking-wider pb-2 border-b-2 border-transparent text-forge-mid hover:text-rust';
                tabGlobal.textContent = 'Library';
                tabs.appendChild(tabLocal);
                tabs.appendChild(tabGlobal);

                const searchWrap = document.createElement('div');
                searchWrap.className = 'hidden';
                const searchInput = document.createElement('input');
                searchInput.type = 'search';
                searchInput.className = 'w-full text-sm border border-border rounded px-2 py-1.5 bg-white';
                searchInput.placeholder = 'Search library…';
                searchWrap.appendChild(searchInput);

                const grid = document.createElement('div');
                grid.className = 'grid grid-cols-3 sm:grid-cols-4 gap-2 max-h-[320px] overflow-y-auto';

                const empty = document.createElement('p');
                empty.className = 'text-sm text-forge-mid col-span-full py-6 text-center';
                empty.textContent = 'No images yet.';

                body.appendChild(tabs);
                body.appendChild(searchWrap);
                body.appendChild(grid);

                const footer = document.createElement('div');
                footer.className = 'pen-modal-footer';
                const cancelBtn = document.createElement('button');
                cancelBtn.type = 'button';
                cancelBtn.className = 'pen-btn pen-btn-secondary pen-btn-sm';
                cancelBtn.textContent = 'Cancel';
                footer.appendChild(cancelBtn);

                dialog.appendChild(header);
                dialog.appendChild(body);
                dialog.appendChild(footer);
                overlay.appendChild(dialog);
                document.body.appendChild(overlay);

                let activeTab = 'local';
                let settled = false;

                const altFromAsset = (asset) =>
                    (asset.filename || '').replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ');

                const finish = (result) => {
                    if (settled) return;
                    settled = true;
                    document.removeEventListener('keydown', onKey, true);
                    overlay.remove();
                    resolve(result);
                };

                const onKey = (e) => {
                    if (e.key === 'Escape') {
                        e.preventDefault();
                        e.stopImmediatePropagation();
                        finish(null);
                    }
                };
                document.addEventListener('keydown', onKey, true);

                const setTabStyles = () => {
                    const activeCls = 'text-[10px] font-black uppercase tracking-wider pb-2 border-b-2 border-rust text-rust';
                    const idleCls = 'text-[10px] font-black uppercase tracking-wider pb-2 border-b-2 border-transparent text-forge-mid hover:text-rust';
                    tabLocal.className = activeTab === 'local' ? activeCls : idleCls;
                    tabGlobal.className = activeTab === 'global' ? activeCls : idleCls;
                    searchWrap.className = activeTab === 'global' ? '' : 'hidden';
                };

                const renderGrid = () => {
                    grid.innerHTML = '';
                    let assets;
                    if (activeTab === 'local') {
                        assets = this.availableAssets || [];
                    } else {
                        const q = searchInput.value.trim().toLowerCase();
                        assets = (this.filteredGlobalAssets || []).filter((a) => {
                            if (!q) return true;
                            return (a.filename || '').toLowerCase().includes(q)
                                || (a.path || '').toLowerCase().includes(q);
                        });
                    }
                    if (!assets.length) {
                        grid.appendChild(empty.cloneNode(true));
                        return;
                    }
                    assets.forEach((asset) => {
                        const cell = document.createElement('button');
                        cell.type = 'button';
                        cell.className = 'group relative aspect-square rounded overflow-hidden border border-border bg-forge-light/30 hover:ring-2 hover:ring-rust focus:outline-none focus-visible:ring-2 focus-visible:ring-rust';
                        cell.title = asset.filename || asset.path || '';
                        const img = document.createElement('img');
                        img.src = asset.url;
                        img.alt = altFromAsset(asset);
                        img.className = 'w-full h-full object-cover';
                        cell.appendChild(img);
                        cell.addEventListener('click', () => {
                            finish({ url: asset.url, alt: altFromAsset(asset) });
                        });
                        grid.appendChild(cell);
                    });
                };

                tabLocal.addEventListener('click', () => {
                    activeTab = 'local';
                    setTabStyles();
                    renderGrid();
                });
                tabGlobal.addEventListener('click', () => {
                    activeTab = 'global';
                    setTabStyles();
                    renderGrid();
                });
                searchInput.addEventListener('input', () => renderGrid());

                closeBtn.addEventListener('click', () => finish(null));
                cancelBtn.addEventListener('click', () => finish(null));
                overlay.addEventListener('click', (e) => {
                    if (e.target === overlay) finish(null);
                });

                setTabStyles();
                renderGrid();
                tabLocal.focus();
            });
        },

        // ── Shortcode Modal ──────────────────────────────────────────
        openShortcodeModal(asset, mode = 'insert') {
            this.shortcodeModal.mode = mode;
            this.shortcodeModal.type = 'image';
            this.shortcodeModal.attrs = {
                src: asset?.path || asset?.url || '',
                alt: asset?.filename?.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ') || '',
                caption: '',
                class: '',
                size: ''
            };
            this.shortcodeModal._editNode = null;
            this.shortcodeModal.open = true;
        },

        applyShortcodeEdit() {
            const a = this.shortcodeModal.attrs;
            let shortcode = '[image';
            if (a.src)     shortcode += ` src="${a.src}"`;
            if (a.alt)     shortcode += ` alt="${a.alt}"`;
            if (a.caption) shortcode += ` caption="${a.caption}"`;
            if (a.class)   shortcode += ` class="${a.class}"`;
            if (a.size)    shortcode += ` size="${a.size}"`;
            shortcode += ']';

            const editorRef = _editors.lastActive || _editors.main;
            if (editorRef) {
                editorRef.replaceSelection(shortcode);
                editorRef.focus();
                this.showToast(this.shortcodeModal.mode === 'insert' ? 'Shortcode inserted.' : 'Shortcode updated.');
            }
            this.shortcodeModal.open = false;
        },

        startResizeLeft(e) {
            e.preventDefault();
            this.isDraggingLeftColumn = true;
            const startX = e.clientX;
            const startWidthPercent = this.workspacePrefs.sidebarWidth || 32;
            
            const container = e.currentTarget.parentElement;
            const containerWidth = container.clientWidth;
            
            // Set body styling for dragging cursor and text selection prevention
            document.body.style.cursor = 'ew-resize';
            document.body.style.userSelect = 'none';
            document.body.style.webkitUserSelect = 'none';
            
            const onMouseMove = (moveEvent) => {
                const deltaX = moveEvent.clientX - startX;
                const deltaPercent = (deltaX / containerWidth) * 100;
                
                // Sidebar is order-first (visually on the left), so deltaX adds to its width
                let newPercent = startWidthPercent + deltaPercent;
                
                // Limits: min 10%, max 40%
                if (newPercent < 10) newPercent = 10;
                if (newPercent > 40) newPercent = 40;
                
                this.workspacePrefs.sidebarWidth = Math.round(newPercent * 10) / 10;
            };
            
            const onMouseUp = () => {
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);
                
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
                document.body.style.webkitUserSelect = '';
                
                this.isDraggingLeftColumn = false;
                this.saveWorkspacePrefs();
            };
            
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        },

        startResizeRight(e) {
            e.preventDefault();
            this.isDraggingRightColumn = true;
            const startX = e.clientX;
            const startWidthPercent = this.workspacePrefs.rightColumnWidth || 25;
            
            const container = e.currentTarget.parentElement;
            const containerWidth = container.clientWidth;
            
            // Set body styling for dragging cursor and text selection prevention
            document.body.style.cursor = 'ew-resize';
            document.body.style.userSelect = 'none';
            document.body.style.webkitUserSelect = 'none';
            
            const onMouseMove = (moveEvent) => {
                const deltaX = moveEvent.clientX - startX;
                const deltaPercent = (deltaX / containerWidth) * 100;
                
                // Right Column is visually on the right, so dragging left (negative deltaX) increases its width
                let newPercent = startWidthPercent - deltaPercent;
                
                // Limits: min 10%, max 40%
                if (newPercent < 10) newPercent = 10;
                if (newPercent > 40) newPercent = 40;
                
                this.workspacePrefs.rightColumnWidth = Math.round(newPercent * 10) / 10;
            };
            
            const onMouseUp = () => {
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);
                
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
                document.body.style.webkitUserSelect = '';
                
                this.isDraggingRightColumn = false;
                this.saveWorkspacePrefs();
            };
            
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        }
    }));
});

window.getPenEditor = (name) => {
    if (name === "body" || name === "main") return _editors.main;
    if (name) return _editors.partials[name] || _editors.main;
    return _editors.lastActive || _editors.main;
};

window.getPenDocumentContext = () => {
    // Return canonical site-relative paths (not editor preview /api/assets/raw URLs)
    // so AI agents round-trip the same form used on disk.
    const main = _editors.main
        ? stripEditorContentUrls(_editors.main.getValue())
        : '';
    const partials = {};
    Object.keys(_editors.partials).forEach(name => {
        if (_editors.partials[name]) {
            partials[name] = stripEditorContentUrls(
                _editors.partials[name].getValue()
            );
        }
    });
    return { main, partials };
};

window._editors = _editors;


