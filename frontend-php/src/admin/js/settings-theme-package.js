/**
 * PenCMS Theme Settings packaging / import / export.
 * Loaded before settings-theme.js. Alpine.data('settingsTheme') spreads
 * window.__pencmsProThemePackage().
 */
(function () {
    function apiBase() {
        const base = ((window.AUTH && window.AUTH.apiBase) || '/api/v1');
        return base.replace(/\/v1\/?$/, '');
    }

    async function _downloadBlob(url, { method, body, fallbackName }) {
        if (window.VAULT && window.VAULT.ready) {
            await window.VAULT.ready;
        }
        const response = await fetch(url, {
            method: method || 'GET',
            headers: {
                ...(window.api && window.api.headers ? window.api.headers : window.AUTH.getHeaders()),
                ...(body ? { 'Content-Type': 'application/json' } : {}),
            },
            body: body ? JSON.stringify(body) : undefined,
        });
        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            let errorMessage = `HTTP ${response.status}`;
            if (error.detail) {
                errorMessage = typeof error.detail === 'string'
                    ? error.detail
                    : JSON.stringify(error.detail);
            }
            const err = new Error(errorMessage);
            err.status = response.status;
            throw err;
        }
        const disposition = response.headers.get('Content-Disposition') || '';
        let filename = fallbackName;
        const star = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(disposition);
        const plain = /filename\s*=\s*"([^"]+)"/i.exec(disposition)
            || /filename\s*=\s*([^;]+)/i.exec(disposition);
        if (star && star[1]) {
            try {
                filename = decodeURIComponent(star[1].trim());
            } catch (_e) {
                filename = star[1].trim();
            }
        } else if (plain && plain[1]) {
            filename = plain[1].trim().replace(/^["']|["']$/g, '');
        }
        const blob = await response.blob();
        if (!blob || blob.size === 0) {
            throw new Error('Package returned an empty archive');
        }
        const warningsHeader = response.headers.get('X-Pen-Package-Warnings') || '';
        const warnings = warningsHeader
            ? warningsHeader.split(' | ').map((w) => w.trim()).filter(Boolean)
            : [];
        const objectUrl = URL.createObjectURL(blob);
        try {
            const a = document.createElement('a');
            a.href = objectUrl;
            a.download = filename;
            a.rel = 'noopener';
            document.body.appendChild(a);
            a.click();
            a.remove();
        } finally {
            URL.revokeObjectURL(objectUrl);
        }
        return { filename, size: blob.size, warnings };
    }

    window.__pencmsProThemePackage = function () {
        return {
            confirmOverwriteModalOpen: false,
            confirmPackageOverwriteModalOpen: false,
            packageSlug: '',
            packageName: '',
            packageAuthor: '',
            packageFormSourceKey: null,
            packaging: false,
            packageInstalling: false,
            downloadingThemeSlug: null,
            pendingPackageSlug: '',
            importFile: null,
            importUrl: '',
            importUrlError: '',
            importDragActive: false,
            importing: false,
            importingUrl: false,
            pendingImportSlug: '',
            pendingImportMode: 'zip',
            _githubHosts: new Set(['github.com', 'www.github.com']),
            _gitlabHosts: new Set(['gitlab.com', 'www.gitlab.com']),

            async _proDownloadThemePackageZip(siteId, { slug, name, author }) {
                const url = `${apiBase()}/sites/${encodeURIComponent(siteId)}/theme/package-zip`;
                return _downloadBlob(url, {
                    method: 'POST',
                    body: { slug, name, author },
                    fallbackName: `${slug}.zip`,
                });
            },

            async _proDownloadInstalledThemeZip(slug) {
                const url = `${apiBase()}/themes/${encodeURIComponent(slug)}/export-zip`;
                return _downloadBlob(url, {
                    method: 'GET',
                    fallbackName: `${slug}.zip`,
                });
            },

            async _proPackageInstallTheme(siteId, { slug, name, author, overwrite = false }) {
                const headers = window.AUTH.getHeaders();
                const response = await fetch(
                    `${apiBase()}/sites/${encodeURIComponent(siteId)}/theme/package-install`,
                    {
                        method: 'POST',
                        headers: { ...headers, 'Content-Type': 'application/json' },
                        body: JSON.stringify({ slug, name, author, overwrite }),
                    }
                );
                const data = await response.json().catch(() => ({}));
                if (!response.ok) {
                    const err = new Error(
                        typeof data.detail === 'string' ? data.detail : (`HTTP ${response.status}`)
                    );
                    err.status = response.status;
                    throw err;
                }
                return data;
            },

        // ── Import helpers ─────────────────────────────────────

        _githubHosts: new Set(['github.com', 'www.github.com']),
        _gitlabHosts: new Set(['gitlab.com', 'www.gitlab.com']),

        onImportUrlInput() {
            if (this.importUrlError) {
                this.importUrlError = '';
            }
        },

        validateImportUrlField() {
            const url = (this.importUrl || '').trim();
            if (!url) {
                this.importUrlError = '';
                return;
            }
            this.importUrlError = this._validateImportUrl(url) || '';
        },

        _parseGithubRepoPath(path) {
            const segments = (path || '').split('/').filter(Boolean);
            if (segments.length < 2) return null;
            const owner = segments[0];
            let repo = segments[1];
            if (repo.endsWith('.git')) {
                repo = repo.slice(0, -4);
            }
            if (!owner || !repo) return null;
            return { owner, repo };
        },

        _parseGitlabRepoPath(path) {
            const rawPath = path || '';
            if (!rawPath.includes('/-/')) {
                let projectPath = rawPath.replace(/^\/+|\/+$/g, '');
                if (!projectPath) return null;
                if (projectPath.endsWith('.git')) {
                    projectPath = projectPath.slice(0, -4);
                }
                return { projectPath };
            }

            const [projectPart, remainderRaw] = rawPath.split('/-/', 2);
            let projectPath = projectPart.replace(/^\/+|\/+$/g, '');
            if (!projectPath) return null;
            if (projectPath.endsWith('.git')) {
                projectPath = projectPath.slice(0, -4);
            }

            const remainder = (remainderRaw || '').replace(/^\/+|\/+$/g, '');
            if (remainder && !remainder.startsWith('tree/')) {
                // Non-tree /-/ paths (blob, commits, etc.) are not installable.
                return null;
            }
            return { projectPath };
        },

        _validateImportUrl(raw) {
            const url = (raw || '').trim();
            if (!url) {
                return 'URL is required';
            }

            let parsed;
            try {
                parsed = new URL(url);
            } catch (_err) {
                return 'Enter a valid HTTPS URL';
            }

            if (parsed.protocol !== 'https:') {
                return 'Only HTTPS URLs are supported';
            }
            if (parsed.username || parsed.password) {
                return 'URLs with embedded credentials are not supported';
            }

            const hostname = (parsed.hostname || '').toLowerCase();
            if (!hostname) {
                return 'Invalid URL hostname';
            }

            const path = parsed.pathname || '';
            if (path.toLowerCase().endsWith('.zip')) {
                return null;
            }

            if (this._githubHosts.has(hostname)) {
                if (!this._parseGithubRepoPath(path)) {
                    return 'GitHub URL must point to a repository or .zip archive';
                }
                return null;
            }

            if (this._gitlabHosts.has(hostname)) {
                if (!this._parseGitlabRepoPath(path)) {
                    return 'GitLab URL must point to a repository or .zip archive';
                }
                return null;
            }

            return 'URL must be a direct .zip download or a public GitHub/GitLab HTTPS repository';
        },

        importFileSize() {
            if (!this.importFile || !this.importFile.size) return '';
            const size = this.importFile.size;
            if (size < 1024) return `${size} B`;
            if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
            return `${(size / (1024 * 1024)).toFixed(1)} MB`;
        },

        onImportFileChange(event) {
            const files = event?.target?.files || event?.dataTransfer?.files;
            if (files && files.length > 0) {
                this.setImportFile(files[0]);
            }
            if (event?.target) {
                event.target.value = '';
            }
        },

        onImportDrop(event) {
            this.importDragActive = false;
            const files = event?.dataTransfer?.files;
            if (files && files.length > 0) {
                const file = files[0];
                if (!file.name.toLowerCase().endsWith('.zip')) {
                    this.setMessage('Only .zip archives are accepted.', true);
                    return;
                }
                if (file.size > 25 * 1024 * 1024) {
                    this.setMessage('File is too large. Maximum upload size is 25 MB.', true);
                    return;
                }
                this.setImportFile(file);
            }
        },

        setImportFile(file) {
            if (!file) {
                this.importFile = null;
                return;
            }
            const isZip = file.name.toLowerCase().endsWith('.zip') || file.type === 'application/zip';
            if (!isZip) {
                this.setMessage('Only .zip archives are accepted.', true);
                return;
            }
            if (file.size > 25 * 1024 * 1024) {
                this.setMessage('File is too large. Maximum upload size is 25 MB.', true);
                return;
            }
            this.importFile = file;
            this.clearMessage();
        },

        clearImportFile() {
            this.importFile = null;
            this.importDragActive = false;
            if (this.$refs.importZip) {
                this.$refs.importZip.value = '';
            }
        },

        async importTheme(overwrite = false) {
            if (!this.importFile || this.importing) return;
            this.importing = true;
            this.pendingImportMode = 'zip';
            this.clearMessage();

            try {
                const formData = new FormData();
                formData.append('file', this.importFile);
                formData.append('overwrite', overwrite ? 'true' : 'false');

                const authHeaders = window.AUTH.getHeaders();
                // Multipart requests must not specify application/json; let the
                // browser set the correct boundary.
                const headers = { ...authHeaders };
                delete headers['Content-Type'];

                const response = await fetch(`${this.apiSitesBase()}/themes/install`, {
                    method: 'POST',
                    headers,
                    body: formData,
                });

                const data = await response.json().catch(() => ({}));

                if (response.status === 409) {
                    this.pendingImportSlug = data.slug || this._slugFromFilename() || 'this theme';
                    this.confirmOverwriteModalOpen = true;
                    this.importing = false;
                    return;
                }

                if (!response.ok) {
                    throw new Error(this.apiDetail(data, response.status));
                }

                this._finishImportSuccess(data);
            } catch (err) {
                this.setMessage(`Failed to install theme: ${err.message}`, true);
                this.importing = false;
            }
        },

        async installFromUrl(overwrite = false) {
            const url = (this.importUrl || '').trim();
            if (!url || this.importingUrl) return;

            const validationError = this._validateImportUrl(url);
            if (validationError) {
                this.importUrlError = validationError;
                return;
            }

            this.importUrlError = '';
            this.importingUrl = true;
            this.pendingImportMode = 'url';
            this.clearMessage();

            try {
                const response = await fetch(`${this.apiSitesBase()}/themes/install-from-url`, {
                    method: 'POST',
                    headers: {
                        ...window.AUTH.getHeaders(),
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        url,
                        overwrite,
                    }),
                });

                const data = await response.json().catch(() => ({}));

                if (response.status === 409) {
                    this.pendingImportSlug = this._slugFromImportDetail(data.detail) || 'this theme';
                    this.confirmOverwriteModalOpen = true;
                    this.importingUrl = false;
                    return;
                }

                if (!response.ok) {
                    throw new Error(this.apiDetail(data, response.status));
                }

                this._finishImportSuccess(data);
            } catch (err) {
                this.setMessage(`Failed to install theme: ${err.message}`, true);
                this.importingUrl = false;
            }
        },

        _finishImportSuccess(data) {
            const slug = data.slug || 'theme';
            const name = data.name || slug;
            const overwrote = data.overwrote ? 'overwrote' : 'installed';
            const flash = `Theme <strong>${name}</strong> (${slug}) ${overwrote} successfully.`;
            if (data.warnings && data.warnings.length > 0) {
                // eslint-disable-next-line no-console
                console.warn('Theme install warnings:', data.warnings);
            }
            this._storeImportMessage(flash, false);
            this.clearImportFile();
            this.importUrl = '';
            this.importUrlError = '';
            this.importing = false;
            this.importingUrl = false;
            window.location.href = 'admin-settings-theme.php#installed';
            window.location.reload();
        },

        _slugFromImportDetail(detail) {
            if (!detail || typeof detail !== 'string') return null;
            const match = detail.match(/Theme '([^']+)' already exists/);
            return match ? match[1] : null;
        },

        async confirmOverwriteImport() {
            this.confirmOverwriteModalOpen = false;
            if (this.pendingImportMode === 'url') {
                await this.installFromUrl(true);
                return;
            }
            await this.importTheme(true);
        },

        _slugFromFilename() {
            const name = this.importFile?.name || '';
            return name.replace(/\.zip$/i, '').replace(/[^a-z0-9]+/gi, '-').toLowerCase() || null;
        },

        _storeImportMessage(message, isError) {
            try {
                window.sessionStorage.setItem(
                    'penThemeImportMessage',
                    JSON.stringify({ message, isError })
                );
            } catch (_e) {}
        },

        // ── Export / package actions ───────────────────────────

        async loadInstalledThemes() {
            try {
                const res = await fetch(`${this.apiSitesBase()}/themes`, {
                    headers: window.AUTH.getHeaders(),
                });
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const data = await res.json();
                this.installedThemes = Array.isArray(data.themes) ? data.themes : [];
                this.themesWithScreenshot = this.installedThemes
                    .filter((theme) => theme.has_screenshot)
                    .map((theme) => theme.slug);
            } catch (_err) {
                // Keep the last known list when refresh fails.
            }
        },

        _packageFormSourceKey() {
            if (this.activeTheme === 'custom') {
                return `custom:${this.customParent || ''}`;
            }
            return this.activeTheme || this.installTheme || '';
        },

        initPackageFormDefaults() {
            const sourceKey = this._packageFormSourceKey();
            if (this.packageFormSourceKey === sourceKey) {
                return;
            }
            this.packageFormSourceKey = sourceKey;

            const base = this.activeTheme === 'custom'
                ? (this.customParent || 'custom-theme')
                : (this.activeTheme || this.installTheme || 'starter');
            const slug = String(base).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'my-theme';
            const match = this.installedThemes.find((theme) => theme.slug === base);
            this.packageSlug = slug;
            this.packageName = this.activeTheme === 'custom'
                ? (this.customLabel || 'Custom Theme')
                : (match?.name || slug);
        },

        sanitizePackageSlug(raw) {
            return String(raw || '')
                .toLowerCase()
                .replace(/[^a-z0-9-]+/g, '-')
                .replace(/^-+|-+$/g, '')
                .replace(/^custom$/, 'my-theme')
                .slice(0, 64);
        },

        async downloadPackageZip() {
            if (this.packaging) return;
            const slug = this.sanitizePackageSlug(this.packageSlug);
            if (!slug) {
                this.setMessage('Theme slug is required.', true);
                return;
            }
            this.packaging = true;
            this.clearMessage();
            try {
                const result = await this._proDownloadThemePackageZip(this.siteId(), {
                    slug,
                    name: (this.packageName || '').trim() || null,
                    author: (this.packageAuthor || '').trim() || null,
                });
                let msg = `Downloaded <strong>${result.filename}</strong> (${Math.round(result.size / 1024)} KB).`;
                if (result.warnings && result.warnings.length > 0) {
                    msg += ` <span class="text-forge-mid font-normal normal-case">${result.warnings.join(' ')}</span>`;
                }
                this.setMessage(msg);
            } catch (err) {
                this.setMessage(`Failed to download theme package: ${err.message}`, true);
            } finally {
                this.packaging = false;
            }
        },

        async savePackageAsInstalled(overwrite = false) {
            if (this.packageInstalling) return;
            const slug = this.sanitizePackageSlug(this.packageSlug);
            if (!slug) {
                this.setMessage('Theme slug is required.', true);
                return;
            }
            this.packageInstalling = true;
            this.clearMessage();
            try {
                const data = await this._proPackageInstallTheme(this.siteId(), {
                    slug,
                    name: (this.packageName || '').trim() || null,
                    author: (this.packageAuthor || '').trim() || null,
                    overwrite,
                });
                const name = data.name || slug;
                const verb = data.overwrote ? 'overwrote' : 'saved';
                let msg = `Theme <strong>${name}</strong> (${slug}) ${verb} as an installed theme.`;
                if (data.warnings && data.warnings.length > 0) {
                    const shotWarnings = data.warnings.filter((w) => /screenshot/i.test(w));
                    if (shotWarnings.length > 0) {
                        msg += ` <span class="text-forge-mid font-normal normal-case">${shotWarnings.join(' ')}</span>`;
                    }
                    // eslint-disable-next-line no-console
                    console.warn('Theme package warnings:', data.warnings);
                }
                this.setMessage(msg);
                await this.loadInstalledThemes();
            } catch (err) {
                if (err.status === 409) {
                    this.pendingPackageSlug = slug;
                    this.confirmPackageOverwriteModalOpen = true;
                    return;
                }
                this.setMessage(`Failed to save theme: ${err.message}`, true);
            } finally {
                this.packageInstalling = false;
            }
        },

        async confirmOverwritePackageInstall() {
            this.confirmPackageOverwriteModalOpen = false;
            await this.savePackageAsInstalled(true);
        },

        async downloadInstalledTheme(slug) {
            if (!slug || this.downloadingThemeSlug) return;
            if (slug === 'custom') {
                return this.downloadCustomTheme();
            }
            this.downloadingThemeSlug = slug;
            this.clearMessage();
            try {
                const result = await this._proDownloadInstalledThemeZip(slug);
                this.setMessage(`Downloaded <strong>${result.filename}</strong> (${Math.round(result.size / 1024)} KB).`);
            } catch (err) {
                this.setMessage(`Failed to download theme: ${err.message}`, true);
            } finally {
                this.downloadingThemeSlug = null;
            }
        },

        async downloadCustomTheme() {
            if (this.downloadingThemeSlug || this.packaging) return;
            this.downloadingThemeSlug = 'custom';
            this.clearMessage();
            const slug = this.sanitizePackageSlug(this.customParent || 'custom-theme') || 'custom-theme';
            try {
                const result = await this._proDownloadThemePackageZip(this.siteId(), {
                    slug,
                    name: (this.customLabel || 'Custom Theme').trim() || null,
                    author: null,
                });
                let msg = `Downloaded <strong>${result.filename}</strong> (${Math.round(result.size / 1024)} KB).`;
                if (result.warnings && result.warnings.length > 0) {
                    msg += ` <span class="text-forge-mid font-normal normal-case">${result.warnings.join(' ')}</span>`;
                }
                this.setMessage(msg);
            } catch (err) {
                this.setMessage(`Failed to download custom theme: ${err.message}`, true);
            } finally {
                this.downloadingThemeSlug = null;
            }
        },
        };
    };
})();
