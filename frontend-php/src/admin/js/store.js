/**
 * Global Alpine.js Store for PenCMS
 */
document.addEventListener('alpine:init', () => {
    Alpine.store('app', {
        pages: [],
        loading: false,
        error: null,
        sitename: '',
        use_ai: false,
        sites: [],
        edition: 'core',
        activeSiteId: (window.AUTH && window.AUTH.siteId) || 'default',
        role: (window.AUTH && window.AUTH.role) || null,
        userUuid: (window.AUTH && window.AUTH.userId) || null,
        status: 'active',
        memberships: [],
        capabilities: [],
        mustChangePassword: false,
        changePasswordCurrent: '',
        changePasswordNew: '',
        changingPassword: false,
        changePasswordError: null,
        _pagesInflight: null,
        _pagesInflightSite: null,

        isDashboardPath() {
            const path = window.location.pathname;
            return path.endsWith('index.php') ||
                path.endsWith('/') ||
                path === '' ||
                path.endsWith('admin-dashboard.php');
        },

        async init() {
            const siteAtStart = this.activeSiteId;
            const isDashboard = this.isDashboardPath();
            await Promise.all([
                this.loadSites(),
                this.loadSession(),
                isDashboard ? this.fetchPages() : Promise.resolve(),
                this.loadGeneralConfig(),
            ]);
            if (this.activeSiteId !== siteAtStart) {
                await this.loadSession({ force: true });
                if (isDashboard) await this.fetchPages();
                await this.loadGeneralConfig();
            }
            this.sitename = this.resolveActiveSitename();
        },

        async loadGeneralConfig() {
            try {
                const config = await window.api.getGeneralConfig();
                this.use_ai = config.use_ai === true;
            } catch (err) {
                console.error("Failed to load general config in store:", err);
            }
        },

        apiSitesBase() {
            const base = (window.AUTH && window.AUTH.apiBase) || '/api/v1';
            return base.replace(/\/v1\/?$/, '');
        },

        resolveActiveSitename() {
            const active = (this.sites || []).find((s) => s.id === this.activeSiteId);
            if (active && active.sitename) return active.sitename;
            if (active && active.name) return active.name;
            return 'PenCMS';
        },

        /**
         * Public preview URL for the active Content site.
         * Previews MUST always target local /blog/ (localhost) because hosted domain sites are
         * static/published builds and not updated in real time during editing.
         */
        previewUrl() {
            const id = this.activeSiteId || 'default';
            return `/blog/?site=${encodeURIComponent(id)}`;
        },

        /**
         * Public preview URL for a specific post/page under the active Content site.
         * Previews MUST always target local /blog/ (localhost) so users see live, real-time
         * draft edits before publishing to a external static site domain.
         */
        previewContentUrl(slug, isPage, language = null, defaultLanguage = null) {
            const id = this.activeSiteId || 'default';
            if (language && defaultLanguage && language !== defaultLanguage) {
                return `/blog/${encodeURIComponent(language)}/${encodeURIComponent(slug || '')}/?site=${encodeURIComponent(id)}`;
            }
            const path = (isPage ? 'page.php' : 'post.php') + '?slug=' + encodeURIComponent(slug || '');
            return `/blog/${path}&site=${encodeURIComponent(id)}`;
        },

        /**
         * Admin path with query params; always includes site= for bookmarkable URLs.
         * @param {string} path e.g. 'admin-editor.php'
         * @param {Record<string, string|number|boolean|null|undefined>} params
         */
        adminPath(path, params = {}) {
            const q = new URLSearchParams();
            Object.keys(params || {}).forEach((key) => {
                const val = params[key];
                if (val === undefined || val === null || val === '') return;
                q.set(key, String(val));
            });
            if (!q.has('site')) {
                q.set('site', this.activeSiteId || 'default');
            }
            const qs = q.toString();
            return qs ? `${path}?${qs}` : path;
        },

        /** Keep the header <select> visually in sync after async option load. */
        syncContentSiteSelect() {
            requestAnimationFrame(() => {
                const el = document.getElementById('pen-content-site');
                if (el && this.activeSiteId) {
                    el.value = this.activeSiteId;
                }
            });
        },

        applySession(data) {
            if (!data) return;
            const user = data.user || {};
            if (user.uuid) this.userUuid = user.uuid;
            if (user.role) this.role = user.role;
            if (user.status) this.status = user.status;
            this.memberships = data.memberships || [];
            this.capabilities = data.capabilities || [];
            this.mustChangePassword = !!data.must_change_password;
            this.edition = data.edition === 'pro' ? 'pro' : 'core';
        },

        isAdmin() {
            return this.role === 'admin';
        },

        hasCap(cap) {
            return (this.capabilities || []).includes(cap);
        },

        hasAnyCap(...caps) {
            return caps.some((cap) => this.hasCap(cap));
        },

        async submitChangePassword() {
            const current = (this.changePasswordCurrent || '').trim();
            const next = (this.changePasswordNew || '').trim();
            this.changePasswordError = null;
            if (!current || !next) {
                this.changePasswordError = 'Enter your current password and a new password.';
                return;
            }
            this.changingPassword = true;
            try {
                const res = await fetch(`${this.apiSitesBase()}/auth/change-password`, {
                    method: 'POST',
                    headers: window.AUTH.getHeaders(),
                    body: JSON.stringify({
                        current_password: current,
                        new_password: next,
                    }),
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    const detail = typeof data.detail === 'string'
                        ? data.detail
                        : 'Failed to change password';
                    throw new Error(detail);
                }
                this.changePasswordCurrent = '';
                this.changePasswordNew = '';
                await this.loadSession({ force: true });
            } catch (err) {
                this.changePasswordError = err.message || 'Failed to change password';
            } finally {
                this.changingPassword = false;
            }
        },

        async loadSession(opts) {
            try {
                if (!window.AUTH || typeof window.AUTH.getMe !== 'function') return;
                const data = await window.AUTH.getMe(opts);
                this.applySession(data);
            } catch (err) {
                console.error('Failed to load session:', err);
            }
        },

        applySiteId(id) {
            const next = (id && String(id).trim()) || 'default';
            if (window.AUTH && typeof window.AUTH.setSiteId === 'function') {
                window.AUTH.setSiteId(next);
            } else if (window.AUTH) {
                window.AUTH.siteId = next;
            }
            this.activeSiteId = next;
            this.sitename = this.resolveActiveSitename();
            this.syncContentSiteSelect();
        },

        async loadSites() {
            try {
                const res = await fetch(`${this.apiSitesBase()}/sites`, {
                    headers: window.AUTH.getHeaders(),
                });
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const data = await res.json();
                this.sites = data.sites || [];
                if (
                    this.sites.length &&
                    !this.sites.some((s) => s.id === this.activeSiteId)
                ) {
                    this.applySiteId(this.sites[0].id);
                } else {
                    this.sitename = this.resolveActiveSitename();
                    this.syncContentSiteSelect();
                }
            } catch (err) {
                console.error('Failed to load sites registry:', err);
                if (!this.sites.length) {
                    this.sites = [{ id: 'default', name: 'Default' }];
                }
                this.syncContentSiteSelect();
            }
        },

        async setActiveSite(id) {
            const next = (id && String(id).trim()) || '';
            if (!next) return;
            if (!this.sites.length || !this.sites.some((s) => s.id === next)) {
                return;
            }
            this.applySiteId(next);

            const path = window.location.pathname;
            if (path.endsWith('admin-editor.php')) {
                window.location.href = this.adminPath('admin-posts.php');
                return;
            }

            await Promise.all([
                this.fetchPages(),
                this.loadSession({ force: true }),
            ]);
        },

        async fetchPages() {
            const siteId = this.activeSiteId || 'default';
            if (this._pagesInflight && this._pagesInflightSite === siteId) {
                return this._pagesInflight;
            }
            this._pagesInflightSite = siteId;
            this._pagesInflight = this._fetchPagesForSite(siteId).finally(() => {
                if (this._pagesInflightSite === siteId) {
                    this._pagesInflight = null;
                    this._pagesInflightSite = null;
                }
            });
            return this._pagesInflight;
        },

        async _fetchPagesForSite(siteId) {
            this.loading = true;
            try {
                const pages = await window.api.listPages();
                if ((this.activeSiteId || 'default') !== siteId) return;
                this.pages = pages;
                this.error = null;
            } catch (err) {
                if ((this.activeSiteId || 'default') !== siteId) return;
                this.error = "Failed to load pages from database collections.";
                console.error(err);
            } finally {
                if ((this.activeSiteId || 'default') === siteId) {
                    this.loading = false;
                }
            }
        },

        /**
         * True when status is published and publish_at is null or in the past.
         * Matches PHP ExpandResolver / settings-navigation isLivePublished.
         */
        isLivePublished(fm) {
            if ((fm?.status || '').toLowerCase() !== 'published') return false;
            if (!fm.publish_at) return true;
            const d = new Date(fm.publish_at);
            return !Number.isNaN(d.getTime()) && d.getTime() <= Date.now();
        },

        /** Load pages into the store if empty; never treat [] as already loaded. */
        async ensurePages() {
            if (!Array.isArray(this.pages) || !this.pages.length) {
                await this.fetchPages();
            }
            return this.pages || [];
        },

        /**
         * Published (live) pages suitable for internal links and expand/embed targets.
         * @param {string} [query]
         * @param {number} [limit=12]
         * @returns {Promise<Array<{slug, title, hero_title, name, suggested_text, markdown_link, expand_shortcode}>>}
         */
        async getPublishedLinkCatalog(query = '', limit = 12) {
            const pages = await this.ensurePages();
            const q = String(query || '').trim().toLowerCase();
            const results = [];
            for (const p of pages || []) {
                const fm = p.frontmatter || {};
                const liveFm = {
                    ...fm,
                    status: fm.status || p.status || 'published',
                    publish_at: fm.publish_at ?? p.publish_at ?? null,
                };
                if (!this.isLivePublished(liveFm)) continue;

                const slug = String(p.id || p.slug || '').trim();
                if (!slug) continue;

                const hero_title = String(fm.hero_title || '').trim();
                const name = String(fm.name || '').trim();
                const title = hero_title || name || String(fm.title || p.title || slug).trim() || slug;
                const suggested_text = hero_title || name || String(fm.title || p.title || '').trim() || slug;

                if (q) {
                    const hay = `${title} ${hero_title} ${name} ${slug}`.toLowerCase();
                    if (!hay.includes(q)) continue;
                }

                const esc = (s) => String(s).replace(/"/g, '\\"');
                results.push({
                    slug,
                    title,
                    hero_title: hero_title || null,
                    name: name || null,
                    suggested_text,
                    markdown_link: `[${suggested_text}](${slug})`,
                    expand_shortcode: `[expand slug="${esc(slug)}" text="${esc(suggested_text)}"]`,
                });
                if (results.length >= limit) break;
            }
            return results;
        },

        /**
         * Extract H1–H3 (+ composite partial titles) from a page payload.
         * Shared by Expand/Embed heading dropdown and AI list_page_headings.
         *
         * @param {{ body?: string, content?: string, partials?: object, frontmatter?: object, composite?: boolean }} payload
         * @param {string} [slug]
         * @returns {{ slug: string, headings: Array<{level:number,title:string,source:string,partial_id?:string}>, composite: boolean }}
         */
        extractPageHeadings(payload, slug = '') {
            const headings = [];
            const body = payload?.body || payload?.content || '';
            for (const line of String(body).replace(/\r/g, '').split('\n')) {
                const match = line.match(/^(#{1,3})\s+(.*)$/);
                if (match) {
                    headings.push({
                        level: match[1].length,
                        title: match[2].trim(),
                        source: 'body',
                    });
                }
            }

            const partials = payload?.partials;
            if (partials && typeof partials === 'object') {
                const partialMeta =
                    payload?.frontmatter?.partials ||
                    payload?.partials_meta ||
                    payload?.composite_partials ||
                    null;

                for (const [id, md] of Object.entries(partials)) {
                    let title = id;
                    if (Array.isArray(partialMeta)) {
                        const found = partialMeta.find(
                            (p) => p && (p.id === id || p.slug === id),
                        );
                        if (found?.title) title = found.title;
                    } else if (partialMeta && typeof partialMeta === 'object') {
                        const found = partialMeta[id];
                        if (found && typeof found === 'object' && found.title) {
                            title = found.title;
                        } else if (typeof found === 'string') {
                            title = found;
                        }
                    }
                    headings.push({
                        level: 2,
                        title: String(title),
                        source: 'partial',
                        partial_id: id,
                    });
                    for (const line of String(md || '')
                        .replace(/\r/g, '')
                        .split('\n')) {
                        const match = line.match(/^(#{1,3})\s+(.*)$/);
                        if (match) {
                            headings.push({
                                level: match[1].length,
                                title: match[2].trim(),
                                source: 'partial',
                                partial_id: id,
                            });
                        }
                    }
                }
            }

            return {
                slug: String(slug || payload?.id || payload?.slug || '').trim(),
                headings,
                composite: !!payload?.composite,
            };
        },

        /**
         * Load a page via the admin API and return section headings for Expand/Embed.
         * @param {string} slug
         * @returns {Promise<Array<{title:string,level?:number,source?:string}>>}
         */
        async getPageHeadings(slug) {
            const id = String(slug || '').trim();
            if (!id || !window.api?.getPage) return [];
            try {
                const page = await window.api.getPage(id);
                const { headings } = this.extractPageHeadings(
                    {
                        body: page?.content || '',
                        content: page?.content || '',
                        partials: page?.partials || {},
                        frontmatter: page?.frontmatter || {},
                        composite: page?.composite,
                    },
                    id,
                );
                return headings;
            } catch (e) {
                console.warn('getPageHeadings failed:', e);
                return [];
            }
        },

        /**
         * Expand/Embed target picker: frontmatter summary/deck (if non-empty) + section headings.
         * @param {string} slug
         * @returns {Promise<{summary: string|null, deck: string|null, headings: Array<{title:string,level?:number,source?:string}>}>}
         */
        async getPageExpandTargets(slug) {
            const id = String(slug || '').trim();
            if (!id || !window.api?.getPage) {
                return { summary: null, deck: null, headings: [] };
            }
            try {
                const page = await window.api.getPage(id);
                const summaryRaw = String(page?.frontmatter?.summary || '').trim();
                const deckRaw = String(page?.frontmatter?.deck || '').trim();
                const { headings } = this.extractPageHeadings(
                    {
                        body: page?.content || '',
                        content: page?.content || '',
                        partials: page?.partials || {},
                        frontmatter: page?.frontmatter || {},
                        composite: page?.composite,
                    },
                    id,
                );
                return {
                    summary: summaryRaw || null,
                    deck: deckRaw || null,
                    headings,
                };
            } catch (e) {
                console.warn('getPageExpandTargets failed:', e);
                return { summary: null, deck: null, headings: [] };
            }
        },

        async triggerSync() {
            this.loading = true;
            try {
                await window.api.sync();
                this.error = null;
                return true;
            } catch (err) {
                this.error = "Git synchronization failed: " + err.message;
                console.error(err);
                throw err;
            } finally {
                this.loading = false;
            }
        },

        async logout() {
            if (window.AUTH && typeof window.AUTH.logout === 'function') {
                return window.AUTH.logout();
            }
            if (window.api && typeof window.api.logout === 'function') {
                return window.api.logout();
            }
            window.location.href = 'login.php';
        }
    });
});
