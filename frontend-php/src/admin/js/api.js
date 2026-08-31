/**
 * PenCMS API Client
 * Targets /api/v1 for spec compliance and /api for legacy dashboard functions.
 */
class ApiError extends Error {
    constructor(status, detail, message) {
        super(message || `HTTP ${status}`);
        this.name = 'ApiError';
        this.status = status;
        this.detail = detail;
    }
}

class APIClient {
    constructor() {
        // window.AUTH.apiBase is "http://127.0.0.1:8008/api/v1" or similar
        this.v1BaseURL = window.AUTH.apiBase;
        this.apiBaseURL = this.v1BaseURL.replace('/v1', '');
    }

    get headers() {
        return window.AUTH.getHeaders();
    }

    async request(endpoint, options = {}) {
        // Wait for the vault to finish initializing (auto-unlock from session)
        // before reading headers, so that X-Pen-API-Key is available.
        if (window.VAULT && window.VAULT.ready) {
            await window.VAULT.ready;
        }

        // Determine whether to target the v1 prefix or root api path
        const isV1 = endpoint.startsWith('/content/') || 
                     endpoint.startsWith('/media/') || 
                     endpoint.startsWith('/translations/') ||
                     endpoint.startsWith('/feedback/') ||
                     endpoint.startsWith('/admin/') ||
                     endpoint.startsWith('/sync') || 
                     endpoint.startsWith('/auth/verify') ||
                     endpoint.startsWith('/cache/');

        const baseURL = isV1 ? this.v1BaseURL : this.apiBaseURL;
        const url = `${baseURL}${endpoint}`;
        
        const config = {
            headers: this.headers,
            ...options,
        };

        try {
            const response = await fetch(url, config);
            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                console.error(`API Error Response [${endpoint}]:`, error);
                
                let errorMessage = `HTTP ${response.status}`;
                if (response.status === 413) {
                    errorMessage = "File size exceeds the maximum allowable size of 10MB.";
                } else if (error.detail) {
                    if (Array.isArray(error.detail)) {
                        const msgs = error.detail.map(e => e.msg).join('\n');
                        if (msgs.toLowerCase().includes('field required') || msgs.toLowerCase().includes('missing')) {
                            errorMessage = "Upload failed: File is missing or exceeds the maximum allowable size (10MB).";
                        } else {
                            errorMessage = msgs;
                        }
                    } else if (typeof error.detail === 'string') {
                        if (error.detail.toLowerCase().includes('field required')) {
                            errorMessage = "Upload failed: File is missing or exceeds the maximum allowable size (10MB).";
                        } else {
                            errorMessage = error.detail;
                        }
                    } else {
                        errorMessage = JSON.stringify(error.detail);
                    }
                } else if (Object.keys(error).length > 0) {
                    errorMessage = JSON.stringify(error);
                }
                
                throw new ApiError(response.status, error.detail, errorMessage);
            }
            if (response.status === 204) return null;
            return await response.json();
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    }

    // Config & Health
    async getConfig() {
        return this.request('/config');
    }

    async healthCheck() {
        return this.request('/health');
    }

    withQuery(endpoint, params = {}) {
        const query = new URLSearchParams();
        Object.entries(params).forEach(([key, value]) => {
            if (value !== null && value !== undefined && value !== '') {
                query.set(key, String(value));
            }
        });
        const suffix = query.toString();
        return suffix ? `${endpoint}?${suffix}` : endpoint;
    }

    // Spec compliance content wrappers
    async listPages() {
        // Query collections, then get entries for each collection in parallel.
        // Paginate within a collection; do not raise pageSize without an API contract.
        try {
            const collections = await this.listCollections();
            const pageSize = 100;
            const perCollection = await Promise.all(
                (collections || []).map((col) => this._listCollectionEntries(col, pageSize))
            );
            return perCollection.flat();
        } catch (e) {
            console.error('listPages failed:', e);
            throw e;
        }
    }

    async _listCollectionEntries(col, pageSize) {
        const name = col && col.name;
        let allPages = [];
        let page = 1;
        let fetched = 0;
        let total = null;
        while (true) {
            const res = await this.listEntries(name, page, pageSize);
            const items = res.items || [];
            items.forEach(item => {
                item.id = item.slug;
                item.collection = name;
                if (!item.frontmatter) item.frontmatter = {};
                if (!item.frontmatter.category) item.frontmatter.category = name;
                if (!item.frontmatter.title) item.frontmatter.title = item.title;
                if (!item.frontmatter.status) item.frontmatter.status = item.status || 'published';
                if (!item.frontmatter.domain) item.frontmatter.domain = item.domain || 'blog';
            });
            allPages = allPages.concat(items);
            fetched += items.length;
            if (typeof res.total === "number") total = res.total;
            if (items.length === 0 || items.length < pageSize) break;
            if (total != null && fetched >= total) break;
            page += 1;
            if (page > 500) break;
        }
        return allPages;
    }

    async getPage(pageId, collection = null, language = null) {
        if (!collection) {
            // Find collection in store
            const store = window.Alpine && Alpine.store('app');
            if (store && typeof store.ensurePages === 'function') {
                await store.ensurePages();
            }
            const found = store && Array.isArray(store.pages)
                ? store.pages.find(p => p.id === pageId)
                : null;
            if (found && found.collection) {
                collection = found.collection;
            } else {
                collection = 'posts';
            }
        }
        const endpoint = this.withQuery(
            `/content/collections/${encodeURIComponent(collection)}/entries/${encodeURIComponent(pageId)}`,
            { language }
        );
        const entry = await this.request(endpoint);
        // Format to legacy Page schema wrapper
        return {
            id: pageId,
            frontmatter: entry.frontmatter,
            content: entry.body,
            composite: entry.composite || false,
            partials: entry.partials || {},
            language: entry.language || entry.frontmatter?.language || null,
            translation_group: entry.translation_group || entry.frontmatter?.translation_group || null,
            translations: entry.translations || [],
            provenance: entry.provenance || {},
            version: entry.version || null
        };
    }

    async createPage(data) {
        const collection = data.frontmatter.category || 'posts';
        const slug = data.slug || data.frontmatter.slug || data.id;
        const body = {
            frontmatter: data.frontmatter,
            body: data.content || '',
            composite: data.composite || false,
            partials: data.partials || {}
        };
        if (data.force) body.force = true;
        const res = await this.request(`/content/collections/${collection}/entries/${slug}`, {
            method: 'PUT',
            body: JSON.stringify(body)
        });
        return {
            id: slug,
            message: "Page created successfully",
            version: res && res.version,
            version_warning: res && res.version_warning
        };
    }

    async updatePage(pageId, data, language = null, collectionOverride = null) {
        const collection = collectionOverride || data.frontmatter.category || 'posts';
        const endpoint = this.withQuery(
            `/content/collections/${encodeURIComponent(collection)}/entries/${encodeURIComponent(pageId)}`,
            { language }
        );
        const body = {
            frontmatter: data.frontmatter,
            body: data.content || '',
            composite: data.composite || false,
            partials: data.partials || {}
        };
        if (data.expected_version != null && data.expected_version !== '') {
            body.expected_version = data.expected_version;
        }
        if (data.force) body.force = true;
        const res = await this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(body)
        });
        return {
            id: pageId,
            message: "Page updated successfully",
            version: res && res.version,
            version_warning: res && res.version_warning
        };
    }

    async deletePage(pageId, collection = null, language = null) {
        if (!collection) {
            const found = window.Alpine && Alpine.store('app') && Alpine.store('app').pages.find(p => p.id === pageId);
            collection = (found && found.collection) ? found.collection : 'posts';
        }
        const endpoint = this.withQuery(
            `/content/collections/${encodeURIComponent(collection)}/entries/${encodeURIComponent(pageId)}`,
            { language }
        );
        return this.request(endpoint, {
            method: 'DELETE'
        });
    }

    async syncFeedback() {
        return this.request('/feedback/sync', { method: 'POST' });
    }

    async listAdminComments(postSlug, visibility) {
        return this.request(
            this.withQuery('/admin/comments', {
                post_slug: postSlug,
                visibility,
            })
        );
    }

    async createAdminComment(postSlug, body, inReplyTo, approveParent) {
        const payload = {
            post_slug: postSlug,
            body,
        };
        if (inReplyTo) {
            payload.in_reply_to = inReplyTo;
        }
        if (approveParent !== undefined) {
            payload.approve_parent = !!approveParent;
        }
        return this.request('/admin/comments', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
    }

    async setCommentVisibility(commentSlug, postSlug, visibility) {
        return this.request(
            `/admin/comments/${encodeURIComponent(commentSlug)}`,
            {
                method: 'PATCH',
                body: JSON.stringify({
                    visibility,
                    post_slug: postSlug,
                }),
            }
        );
    }

    async patchComment(commentSlug, postSlug, fields) {
        return this.request(
            `/admin/comments/${encodeURIComponent(commentSlug)}`,
            {
                method: 'PATCH',
                body: JSON.stringify({
                    post_slug: postSlug,
                    ...(fields || {}),
                }),
            }
        );
    }

    async deleteComment(commentSlug, postSlug) {
        return this.request(
            this.withQuery(
                `/admin/comments/${encodeURIComponent(commentSlug)}`,
                { post_slug: postSlug }
            ),
            { method: 'DELETE' }
        );
    }

    // Translation administration (site-scoped via X-Pen-Site-Id)
    async getTranslationConfig() {
        return this.request('/translations/config');
    }

    async updateTranslationConfig(data) {
        return this.request('/translations/config', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async getTranslationCoverage(language = null) {
        return this.request(this.withQuery('/translations/coverage', { language }));
    }

    async getTranslationRuns(limit = 25) {
        return this.request(this.withQuery('/translations/runs', { limit }));
    }

    async getAgentKeys() {
        return this.request('/auth/keys');
    }

    async reviewTranslation(slug, language, decision) {
        return this.request(
            `/translations/${encodeURIComponent(slug)}/${encodeURIComponent(language)}/review`,
            {
                method: 'POST',
                body: JSON.stringify({ decision })
            }
        );
    }

    async createTranslationSibling(collection, slug, language) {
        return this.request(
            `/content/collections/${encodeURIComponent(collection)}/entries/${encodeURIComponent(slug)}/translations`,
            {
                method: 'POST',
                body: JSON.stringify({ language })
            }
        );
    }

    async getUiStrings(language = null) {
        return this.request(this.withQuery('/translations/strings', { language }));
    }

    async updateUiStrings(language, overrides) {
        return this.request(
            this.withQuery('/translations/strings', { language }),
            {
                method: 'PUT',
                body: JSON.stringify({ overrides })
            }
        );
    }

    // Collections endpoints
    async listCollections() {
        return this.request('/content/collections');
    }

    async listEntries(collection, page = 1, limit = 100) {
        return this.request(`/content/collections/${collection}/entries?page=${page}&limit=${limit}`);
    }

    // Media library endpoints
    async listAllAssets() {
        const files = await this.request('/media/files');
        return files.map(f => {
            const parts = f.filename.split('/');
            let entity_type = f.entity_type || 'general';
            let entity_id = f.entity_id || 'media';
            let display_name = parts[parts.length - 1];
            
            // Legacy path parsing fallback
            if (!f.entity_type && parts.length >= 4 && parts[0] === 'images' && parts[1] === 'content') {
                entity_type = parts[2];
                entity_id = parts[3];
                display_name = parts.slice(4).join('/');
            }
            
            let assetUrl = f.public_url;
            if (assetUrl && assetUrl.startsWith('/api/')) {
                assetUrl = this.apiBaseURL + assetUrl.substring(4);
            }
            
            return {
                filename: display_name,
                path: f.filename,
                url: assetUrl,
                entity_type: entity_type,
                entity_id: entity_id,
                size_bytes: f.size_bytes,
                modified_at: f.modified_at
            };
        });
    }

    async listAssets(type, id) {
        // Filter listAllAssets to only include assets for this type/id (slug/page_id is unique)
        const all = await this.listAllAssets();
        return all.filter(a => a.entity_id === id);
    }

    async uploadAsset(type, id, file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.readAsDataURL(file);
            reader.onload = async () => {
                const base64Content = reader.result.split(',')[1];
                const targetPath = `images/content/${type}/${id}/${file.name}`;
                try {
                    const result = await this.request('/media/files', {
                        method: 'POST',
                        body: JSON.stringify({
                            filename: targetPath,
                            content_base64: base64Content
                        })
                    });
                    
                    let assetUrl = result.public_url;
                    if (assetUrl && assetUrl.startsWith('/api/')) {
                        assetUrl = this.apiBaseURL + assetUrl.substring(4);
                    }
                    
                    resolve({
                        filename: file.name,
                        path: result.filename || targetPath,
                        url: assetUrl
                    });
                } catch (e) {
                    reject(e);
                }
            };
            reader.onerror = error => reject(error);
        });
    }

    async deleteAsset(type, id, filename) {
        return this.request(`/assets/${type}/${id}/${filename}`, {
            method: 'DELETE'
        });
    }

    // Sync
    async sync() {
        return this.request('/sync', { method: 'POST' });
    }

    // Taxonomy & Settings Management
    async getTaxonomy() {
        return this.request('/taxonomy/');
    }

    async updateTaxonomy(data) {
        return this.request('/taxonomy/', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async getStorageConfig() {
        return this.request('/storage/config');
    }

    async updateStorageConfig(data) {
        return this.request('/storage/config', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async testSSH(data) {
        return this.request('/storage/test-ssh', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async getPublishTarget(site) {
        return this.request(`/publish/target?site=${encodeURIComponent(site)}`);
    }

    async getPublishProviders() {
        return this.request('/publish/providers');
    }

    async updatePublishTarget(data) {
        return this.request('/publish/target', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async testPublish(site) {
        return this.request('/publish/test', {
            method: 'POST',
            body: JSON.stringify({ site })
        });
    }

    async runPublish(site, opts = {}) {
        const body = { site };
        if (opts.force_full) body.force_full = true;
        return this.request('/publish/run', {
            method: 'POST',
            body: JSON.stringify(body)
        });
    }

    async getPublishStatus(site, taskId) {
        let url = `/publish/status?site=${encodeURIComponent(site)}`;
        if (taskId) {
            url += `&task_id=${encodeURIComponent(taskId)}`;
        }
        return this.request(url);
    }

    async getPublishGrant(site) {
        return this.request(`/publish/grant?site=${encodeURIComponent(site)}`);
    }

    async enrollPublishGrant(site, password) {
        const body = { site };
        if (password) body.password = password;
        return this.request('/publish/grant', {
            method: 'POST',
            body: JSON.stringify(body)
        });
    }

    async revokePublishGrant(site) {
        return this.request(`/publish/grant?site=${encodeURIComponent(site)}`, {
            method: 'DELETE'
        });
    }

    /**
     * Build active site dist/ and trigger a browser zip download.
     * Returns { filename } on success; throws Error on failure (never a bogus zip).
     */
    async downloadPublishExportZip(site) {
        if (window.VAULT && window.VAULT.ready) {
            await window.VAULT.ready;
        }
        const url = `${this.apiBaseURL}/publish/export-zip`;
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                ...this.headers,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ site }),
        });
        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            let errorMessage = `HTTP ${response.status}`;
            if (error.detail) {
                if (Array.isArray(error.detail)) {
                    errorMessage = error.detail.map((e) => e.msg).join('\n');
                } else if (typeof error.detail === 'string') {
                    errorMessage = error.detail;
                } else {
                    errorMessage = JSON.stringify(error.detail);
                }
            }
            throw new Error(errorMessage);
        }
        const disposition = response.headers.get('Content-Disposition') || '';
        let filename = `${site}-static.zip`;
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
            throw new Error('Export returned an empty archive');
        }
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
        return { filename, size: blob.size };
    }

    async getSSHKey() {
        return this.request('/storage/ssh-key');
    }

    async generateSSHKey() {
        return this.request('/storage/generate-key', {
            method: 'POST'
        });
    }

    async restartService() {
        return this.request('/storage/restart', {
            method: 'POST'
        });
    }

    async updateActiveTheme(theme) {
        return this.request('/storage/theme', {
            method: 'PUT',
            body: JSON.stringify({ theme })
        });
    }

    async getGeneralConfig() {
        return this.request('/storage/general');
    }

    async getSiteBranding() {
        return this.request('/storage/branding');
    }

    async updateGeneralConfig(data) {
        return this.request('/storage/general', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async uploadLogo(file) {
        const formData = new FormData();
        formData.append('file', file);
        const headers = { ...this.headers };
        delete headers['Content-Type'];
        return this.request('/storage/logo', {
            method: 'POST',
            body: formData,
            headers: headers
        });
    }

    async uploadAvatar(file) {
        const formData = new FormData();
        formData.append('file', file);
        const headers = { ...this.headers };
        delete headers['Content-Type'];
        return this.request('/storage/avatar', {
            method: 'POST',
            body: formData,
            headers: headers
        });
    }

    async uploadHero(file) {
        const formData = new FormData();
        formData.append('file', file);
        const headers = { ...this.headers };
        delete headers['Content-Type'];
        return this.request('/storage/hero', {
            method: 'POST',
            body: formData,
            headers: headers
        });
    }

    async uploadFavicon(file) {
        const formData = new FormData();
        formData.append('file', file);
        const headers = { ...this.headers };
        delete headers['Content-Type'];
        return this.request('/storage/favicon', {
            method: 'POST',
            body: formData,
            headers: headers
        });
    }

    async uploadOgDefault(file) {
        const formData = new FormData();
        formData.append('file', file);
        const headers = { ...this.headers };
        delete headers['Content-Type'];
        return this.request('/storage/og-default', {
            method: 'POST',
            body: formData,
            headers: headers
        });
    }

    async uploadOgDefaultHero(file) {
        const formData = new FormData();
        formData.append('file', file);
        const headers = { ...this.headers };
        delete headers['Content-Type'];
        return this.request('/storage/og-defaulthero', {
            method: 'POST',
            body: formData,
            headers: headers
        });
    }

    async uploadOgWatermark(file) {
        const formData = new FormData();
        formData.append('file', file);
        const headers = { ...this.headers };
        delete headers['Content-Type'];
        return this.request('/storage/og-watermark', {
            method: 'POST',
            body: formData,
            headers: headers
        });
    }

    // Menus Management
    async getMenus() {
        return this.request('/menus');
    }

    async getMenuSlot(slot) {
        return this.request(`/menus/${slot}`);
    }

    async createMenuItem(slot, item) {
        return this.request(`/menus/${slot}/items`, {
            method: 'POST',
            body: JSON.stringify(item)
        });
    }

    async updateMenuItem(slot, itemId, item) {
        return this.request(`/menus/${slot}/items/${itemId}`, {
            method: 'PUT',
            body: JSON.stringify(item)
        });
    }

    async deleteMenuItem(slot, itemId) {
        return this.request(`/menus/${slot}/items/${itemId}`, {
            method: 'DELETE'
        });
    }

    async reorderMenuItems(slot, reorders) {
        return this.request(`/menus/${slot}/reorder`, {
            method: 'PUT',
            body: JSON.stringify(reorders)
        });
    }

    async clearMenuSlot(slot) {
        return this.request(`/menus/${slot}`, {
            method: 'DELETE'
        });
    }

    // Authors (site-scoped via X-Pen-Site-Id)
    async getAuthors() {
        return this.request('/authors/');
    }

    async createAuthor(data) {
        return this.request('/authors/', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async updateAuthor(slug, data) {
        return this.request(`/authors/${encodeURIComponent(slug)}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async deleteAuthor(slug) {
        return this.request(`/authors/${encodeURIComponent(slug)}`, {
            method: 'DELETE'
        });
    }

    async uploadAuthorAvatar(slug, file) {
        const formData = new FormData();
        formData.append('file', file);
        const headers = { ...this.headers };
        delete headers['Content-Type'];
        return this.request(`/authors/${encodeURIComponent(slug)}/avatar`, {
            method: 'POST',
            body: formData,
            headers: headers
        });
    }

    async logout() {
        if (typeof window !== 'undefined' && window.AUTH && typeof window.AUTH.logout === 'function') {
            return window.AUTH.logout();
        }
        try {
            await fetch(`${this.apiBaseURL}/auth/logout`, {
                method: 'POST',
                headers: this.headers
            });
        } catch (e) {
            console.warn('Logout API error:', e);
        }
        if (typeof document !== 'undefined') {
            document.cookie = 'pen_user_id=; path=/; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT';
            document.cookie = 'pen_role=; path=/; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT';
            document.cookie = 'pen_site_id=; path=/; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT';
        }
        if (typeof sessionStorage !== 'undefined') {
            try {
                sessionStorage.removeItem('pen_master_password');
                sessionStorage.clear();
            } catch (e) {}
        }
        if (typeof window !== 'undefined') {
            if (window.VAULT) {
                window.VAULT.unlocked = false;
                window.VAULT.secrets = {};
                window.VAULT.masterPassword = null;
            }
            window.location.href = 'login.php';
        }
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = APIClient;
    module.exports.ApiError = ApiError;
}
if (typeof window !== 'undefined') {
    window.ApiError = ApiError;
    window.api = new APIClient();
}
