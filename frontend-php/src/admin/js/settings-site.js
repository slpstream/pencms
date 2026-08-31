/**
 * PenCMS Site Settings controller (settings-site.js)
 * Tabs: Site Info / Graphics / Authors (site-scoped via X-Pen-Site-Id).
 */
const MAX_UPLOAD_SIZE = 10 * 1024 * 1024; // 10 MB

// ---------------------------------------------------------------------------
// Social-link URL canonicalization rules
// ---------------------------------------------------------------------------
// Each known platform maps to its canonical base URL, a set of domain aliases
// the user might type, and an optional default path prefix for bare usernames.
// Platforms with `null` (e.g. Mastodon) are federated — no single canonical
// domain exists, so only generic URL hygiene is applied.
// ---------------------------------------------------------------------------
const SOCIAL_PLATFORM_RULES = {
  twitter:   { canonical: 'https://x.com',              aliases: ['twitter.com','x.com','www.twitter.com','www.x.com'],                               pathPrefix: '',          knownPrefixes: [] },
  bluesky:   { canonical: 'https://bsky.app',           aliases: ['bsky.app','www.bsky.app','staging.bsky.app'],                                      pathPrefix: '/profile',  knownPrefixes: ['/profile'] },
  mastodon:  null,
  instagram: { canonical: 'https://www.instagram.com',  aliases: ['instagram.com','www.instagram.com','instagr.am'],                                   pathPrefix: '',          knownPrefixes: [] },
  facebook:  { canonical: 'https://www.facebook.com',   aliases: ['facebook.com','www.facebook.com','fb.com','www.fb.com','m.facebook.com'],             pathPrefix: '',          knownPrefixes: ['/groups','/pages'] },
  vk:        { canonical: 'https://vk.com',             aliases: ['vk.com','www.vk.com','m.vk.com'],                                                  pathPrefix: '',          knownPrefixes: [] },
  linkedin:  { canonical: 'https://www.linkedin.com',   aliases: ['linkedin.com','www.linkedin.com'],                                                  pathPrefix: '/in',       knownPrefixes: ['/in','/company','/school'] },
  github:    { canonical: 'https://github.com',         aliases: ['github.com','www.github.com'],                                                     pathPrefix: '',          knownPrefixes: [] },
  telegram:  { canonical: 'https://t.me',               aliases: ['t.me','telegram.me','www.telegram.me'],                                             pathPrefix: '',          knownPrefixes: [] },
  youtube:   { canonical: 'https://www.youtube.com',    aliases: ['youtube.com','www.youtube.com','youtu.be','m.youtube.com'],                           pathPrefix: '',          knownPrefixes: ['/channel','/@','/c','/user'] },
  tiktok:    { canonical: 'https://www.tiktok.com',     aliases: ['tiktok.com','www.tiktok.com','vm.tiktok.com'],                                       pathPrefix: '/@',        knownPrefixes: ['/@'] },
  reddit:    { canonical: 'https://www.reddit.com',     aliases: ['reddit.com','www.reddit.com','old.reddit.com'],                                      pathPrefix: '/user',     knownPrefixes: ['/r','/u','/user'] },
  discord:   { canonical: 'https://discord.gg',         aliases: ['discord.gg','discord.com','www.discord.com','discordapp.com','www.discordapp.com'], pathPrefix: '',          knownPrefixes: ['/invite','/servers'] },
  slack:     { canonical: 'https://slack.com',          aliases: ['slack.com','www.slack.com'],                                                        pathPrefix: '',          knownPrefixes: [] },
  whatsapp:  { canonical: 'https://wa.me',              aliases: ['wa.me','whatsapp.com','www.whatsapp.com','api.whatsapp.com'], pathPrefix: '',          knownPrefixes: [] },
};

document.addEventListener('alpine:init', () => {
  Alpine.data('settingsSite', () => ({
    loading: true,
    saving: false,
    savingAuthor: false,
    activeTab: 'info',

    // Modal state for errors/notices
    showMessageModal: false,
    modalTitle: '',
    modalMessage: '',
    modalIsError: true,

    // Site Info / Graphics
    sitename: '',
    tagline: '',
    hero_title: '',
    hero_image: '',
    contact_email: '',
    domain: '',
    display_logo: false,
    comments_enabled: false,
    feedback_relay_url: '',
    registryName: '',
    socialLinks: [],
    presetPlatforms: [
      { id: 'twitter', name: 'X (Twitter)' },
      { id: 'bluesky', name: 'Bluesky' },
      { id: 'mastodon', name: 'Mastodon' },
      { id: 'instagram', name: 'Instagram' },
      { id: 'facebook', name: 'Facebook' },
      { id: 'vk', name: 'VK' },
      { id: 'linkedin', name: 'LinkedIn' },
      { id: 'github', name: 'GitHub' },
      { id: 'telegram', name: 'Telegram' },
      { id: 'youtube', name: 'YouTube' },
      { id: 'tiktok', name: 'TikTok' },
      { id: 'reddit', name: 'Reddit' },
      { id: 'discord', name: 'Discord' },
      { id: 'slack', name: 'Slack' },
      { id: 'whatsapp', name: 'WhatsApp' },
    ],
    logoFile: null,
    logoPreview: null,
    heroFile: null,
    heroPreview: null,
    faviconFile: null,
    faviconPreview: null,
    message: '',
    messageType: 'success',

    // Authors
    authors: [],
    showAuthorForm: false,
    editingSlug: null,
    showAuthorAdvanced: false,
    authorForm: {
      name: '',
      slug: '',
      bio: '',
      website: '',
      email: '',
      role: '',
      sort_order: 0,
      avatar: null,
    },
    authorAvatarFile: null,
    authorAvatarPreview: null,
    deleteAuthorSlug: null,
    deletingAuthor: false,

    async init() {
      this.syncActiveTab();
      this.$watch(
        () => (this.$store.app.capabilities || []).join(","),
        async () => {
          this.syncActiveTab();
          if (this.canAuthors()) {
            await this.fetchAuthors();
          } else {
            this.authors = [];
          }
        }
      );
      await this.loadAll();
      this.$watch(
        () => this.$store.app.activeSiteId,
        async (next, prev) => {
          if (next && next !== prev) {
            this.resetAuthorForm();
            await this.loadAll();
          }
        }
      );
    },

    canSeo() {
      return this.$store.app.hasCap("write:seo");
    },

    canAuthors() {
      return this.$store.app.hasCap("write:authors");
    },

    syncActiveTab() {
      const seo = this.canSeo();
      const authors = this.canAuthors();
      if ((this.activeTab === "info" || this.activeTab === "graphics") && !seo) {
        this.activeTab = authors ? "authors" : "info";
        return;
      }
      if (this.activeTab === "authors" && !authors) {
        this.activeTab = seo ? "info" : "authors";
      }
    },

    async loadAll() {
      this.loading = true;
      try {
        const jobs = [this.loadForm()];
        if (this.canAuthors()) jobs.push(this.fetchAuthors());
        else this.authors = [];
        await Promise.all(jobs);
      } finally {
        this.loading = false;
      }
    },

    async loadForm() {
      try {
        const siteId = Alpine.store('app').activeSiteId || 'default';
        const sitesBase = ((window.AUTH && window.AUTH.apiBase) || '/api/v1').replace(
          /\/v1\/?$/,
          ''
        );

        const [sitesRes, branding] = await Promise.all([
          fetch(`${sitesBase}/sites`, { headers: window.AUTH.getHeaders() }),
          window.api.getSiteBranding(),
        ]);
        if (!sitesRes.ok) throw new Error(`HTTP ${sitesRes.status}`);
        const sitesData = await sitesRes.json();
        const site = (sitesData.sites || []).find((s) => s.id === siteId) || {};

        this.registryName = site.name || '';
        Alpine.store('app').sitename = site.sitename || site.name || '';
        this.tagline = site.tagline || '';
        this.hero_title = site.hero_title || '';
        this.hero_image = site.hero_image || '';
        this.contact_email = site.contact_email || '';
        this.domain = site.domain || '';
        this.comments_enabled = !!site.comments_enabled;
        this.feedback_relay_url = site.feedback_relay_url || '';
        this.socialLinks = Array.isArray(site.social_links)
          ? site.social_links.map((l) => ({ platform: l.platform || 'custom', url: l.url || '', label: l.label || '' }))
          : [];

        this.logoFile = null;
        this.heroFile = null;
        this.faviconFile = null;

        const ts = Date.now();
        const brandingSite = (branding && branding.site_id) || siteId;
        if (brandingSite === siteId) {
          this.logoPreview = branding.logo ? (branding.logo + (branding.logo.includes('?') ? '&' : '?') + 't=' + ts) : null;
          this.faviconPreview = branding.favicon ? (branding.favicon + (branding.favicon.includes('?') ? '&' : '?') + 't=' + ts) : null;
        } else {
          this.logoPreview = null;
          this.faviconPreview = null;
        }

        this.heroPreview = null;
        if (this.hero_image) {
          const path = this.hero_image.replace(/^\/+/, '');
          if (path.startsWith('images/')) {
            this.heroPreview = `/api/assets/raw/sites/${siteId}/assets/${path}?t=${ts}`;
          } else if (/^https?:\/\//i.test(this.hero_image)) {
            this.heroPreview = this.hero_image;
          } else {
            this.heroPreview = this.hero_image;
          }
        }

        const hasLogo = !!this.logoPreview;
        this.display_logo = hasLogo
          ? site.display_logo !== null && site.display_logo !== undefined
            ? !!site.display_logo
            : true
          : false;
      } catch (err) {
        console.error('Failed to load site configuration:', err);
        this.showNotification('Failed to load site configuration.', 'error');
      }
    },

    async fetchAuthors() {
      try {
        const siteId = Alpine.store('app').activeSiteId || 'default';
        const response = await window.api.getAuthors();
        if (response.site_id && response.site_id !== siteId) {
          this.authors = [];
          return;
        }
        this.authors = response.authors || [];
      } catch (err) {
        console.error('Failed to load authors:', err);
        this.authors = [];
        this.showNotification('Failed to load authors.', 'error');
      }
    },

    authorAvatarUrl(author) {
      if (!author || !author.avatar) return null;
      const siteId = Alpine.store('app').activeSiteId || 'default';
      const path = String(author.avatar).replace(/^\/+/, '');
      if (/^https?:\/\//i.test(path)) return path;
      if (path.startsWith('images/')) {
        return `/api/assets/raw/sites/${siteId}/assets/${path}`;
      }
      return path;
    },

    slugifyName(name) {
      return String(name || '')
        .toLowerCase()
        .trim()
        .replace(/[^\w\s-]/g, '')
        .replace(/[\s_]+/g, '-')
        .replace(/-+/g, '-')
        .replace(/^-|-$/g, '');
    },

    resetAuthorForm() {
      this.showAuthorForm = false;
      this.editingSlug = null;
      this.showAuthorAdvanced = false;
      this.authorForm = {
        name: '',
        slug: '',
        bio: '',
        website: '',
        email: '',
        role: '',
        sort_order: 0,
        avatar: null,
      };
      this.authorAvatarFile = null;
      this.authorAvatarPreview = null;
      this.deleteAuthorSlug = null;
    },

    openNewAuthor() {
      if (!this.canAuthors()) return;
      this.resetAuthorForm();
      this.showAuthorForm = true;
      const maxOrder = this.authors.reduce(
        (m, a) => Math.max(m, a.sort_order ?? 0),
        -1
      );
      this.authorForm.sort_order = maxOrder + 1;
    },

    openEditAuthor(author) {
      if (!this.canAuthors()) return;
      this.showAuthorForm = true;
      this.editingSlug = author.slug;
      this.authorForm = {
        name: author.name || '',
        slug: author.slug || '',
        bio: author.bio || '',
        website: author.website || '',
        email: author.email || '',
        role: author.role || '',
        sort_order: author.sort_order ?? 0,
        avatar: author.avatar || null,
      };
      this.authorAvatarFile = null;
      this.authorAvatarPreview = this.authorAvatarUrl(author);
    },

    cancelAuthorForm() {
      this.resetAuthorForm();
    },

    onAuthorNameInput() {
      if (!this.editingSlug) {
        this.authorForm.slug = this.slugifyName(this.authorForm.name);
      }
    },

    showErrorModal(title, msg) {
      this.modalTitle = title || 'File Upload Error';
      this.modalMessage = msg;
      this.modalIsError = true;
      this.showMessageModal = true;
    },

    dismissMessageModal() {
      this.showMessageModal = false;
      this.modalTitle = '';
      this.modalMessage = '';
    },

    validateFileSize(file) {
      if (!file) return true;
      if (file.size > MAX_UPLOAD_SIZE) {
        const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
        const msg = `File "${file.name}" is ${sizeMB} MB, which exceeds the maximum allowable size of 10 MB. Please select a smaller image.`;
        this.showNotification(msg, 'error');
        return false;
      }
      return true;
    },

    setAuthorAvatarFile(file) {
      if (!file) return;
      if (!this.validateFileSize(file)) {
        this.authorAvatarFile = null;
        return;
      }
      this.authorAvatarFile = file;
      const reader = new FileReader();
      reader.onload = (e) => {
        this.authorAvatarPreview = e.target.result;
      };
      reader.readAsDataURL(file);
    },

    handleAuthorAvatarSelect(event) {
      const files = event.target.files;
      if (files && files.length > 0) {
        this.setAuthorAvatarFile(files[0]);
      }
    },

    handleAuthorAvatarDrop(event) {
      const files = event.dataTransfer.files;
      if (files && files.length > 0) {
        this.setAuthorAvatarFile(files[0]);
      }
    },

    async saveAuthor() {
      if (this.savingAuthor || !this.canAuthors()) return;
      const name = (this.authorForm.name || '').trim();
      if (!name) {
        this.showNotification('Author name is required.', 'error');
        return;
      }
      const slugInput = (this.authorForm.slug || '').trim();
      if (!this.editingSlug && !slugInput) {
        this.showNotification('Author slug is required.', 'error');
        return;
      }

      this.savingAuthor = true;
      try {
        let slug = this.editingSlug;
        const payload = {
          name,
          bio: this.authorForm.bio || '',
          website: (this.authorForm.website || '').trim(),
          email: (this.authorForm.email || '').trim(),
          role: (this.authorForm.role || '').trim(),
          sort_order: Number(this.authorForm.sort_order) || 0,
        };

        if (this.editingSlug) {
          await window.api.updateAuthor(this.editingSlug, payload);
        } else {
          const createPayload = {
            ...payload,
            slug: slugInput,
          };
          const created = await window.api.createAuthor(createPayload);
          slug = created.slug;
        }

        if (this.authorAvatarFile && slug) {
          const upload = await window.api.uploadAuthorAvatar(
            slug,
            this.authorAvatarFile
          );
          if (upload && upload.url) {
            this.authorAvatarPreview = upload.url + '?t=' + Date.now();
          }
        }

        const wasEdit = !!this.editingSlug;
        await this.fetchAuthors();
        this.resetAuthorForm();
        this.showNotification(wasEdit ? 'Author updated.' : 'Author created.');
      } catch (err) {
        console.error('Failed to save author:', err);
        this.showNotification(err.message || 'Failed to save author.', 'error');
      } finally {
        this.savingAuthor = false;
      }
    },

    openDeleteAuthor(slug) {
      if (!this.canAuthors()) return;
      this.deleteAuthorSlug = slug;
    },

    cancelDeleteAuthor() {
      this.deleteAuthorSlug = null;
    },

    async confirmDeleteAuthor() {
      if (!this.deleteAuthorSlug || this.deletingAuthor || !this.canAuthors()) return;
      this.deletingAuthor = true;
      try {
        await window.api.deleteAuthor(this.deleteAuthorSlug);
        if (this.editingSlug === this.deleteAuthorSlug) {
          this.resetAuthorForm();
        }
        this.deleteAuthorSlug = null;
        await this.fetchAuthors();
        this.showNotification('Author deleted.');
      } catch (err) {
        console.error('Failed to delete author:', err);
        this.showNotification(err.message || 'Failed to delete author.', 'error');
      } finally {
        this.deletingAuthor = false;
      }
    },

    handleLogoDrop(event) {
      const files = event.dataTransfer.files;
      if (files && files.length > 0) {
        this.setLogoFile(files[0]);
      }
    },

    handleLogoFileSelect(event) {
      const files = event.target.files;
      if (files && files.length > 0) {
        this.setLogoFile(files[0]);
      }
    },

    setLogoFile(file) {
      if (!file) return;
      if (!this.validateFileSize(file)) {
        this.logoFile = null;
        return;
      }
      this.logoFile = file;
      this.display_logo = true;
      const reader = new FileReader();
      reader.onload = (e) => {
        this.logoPreview = e.target.result;
      };
      reader.readAsDataURL(file);
    },

    handleHeroDrop(event) {
      const files = event.dataTransfer.files;
      if (files && files.length > 0) {
        this.setHeroFile(files[0]);
      }
    },

    handleHeroFileSelect(event) {
      const files = event.target.files;
      if (files && files.length > 0) {
        this.setHeroFile(files[0]);
      }
    },

    setHeroFile(file) {
      if (!file) return;
      if (!this.validateFileSize(file)) {
        this.heroFile = null;
        return;
      }
      this.heroFile = file;
      const reader = new FileReader();
      reader.onload = (e) => {
        this.heroPreview = e.target.result;
      };
      reader.readAsDataURL(file);
    },

    handleFaviconDrop(event) {
      const files = event.dataTransfer.files;
      if (files && files.length > 0) {
        this.setFaviconFile(files[0]);
      }
    },

    handleFaviconFileSelect(event) {
      const files = event.target.files;
      if (files && files.length > 0) {
        this.setFaviconFile(files[0]);
      }
    },

    setFaviconFile(file) {
      if (!file) return;
      if (!this.validateFileSize(file)) {
        this.faviconFile = null;
        return;
      }
      this.faviconFile = file;
      const reader = new FileReader();
      reader.onload = (e) => {
        this.faviconPreview = e.target.result;
      };
      reader.readAsDataURL(file);
    },

    showNotification(msg, type = 'success') {
      this.message = msg;
      this.messageType = type;
      if (type === 'error') {
        this.showErrorModal('Upload Error', msg);
      }
      setTimeout(() => {
        this.message = '';
      }, 5000);
    },

    async save() {
      if (!this.canSeo()) return;
      this.saving = true;
      this.message = '';
      try {
        const siteId = Alpine.store('app').activeSiteId || 'default';
        if (this.heroFile) {
          const ext = this.heroFile.name.split('.').pop().toLowerCase();
          const norm = ext === 'jpeg' ? 'jpg' : ext;
          this.hero_image = `images/hero.${norm}`;
        }

        const sitesBase = ((window.AUTH && window.AUTH.apiBase) || '/api/v1').replace(
          /\/v1\/?$/,
          ''
        );
        const patchRes = await fetch(
          `${sitesBase}/sites/${encodeURIComponent(siteId)}`,
          {
            method: 'PATCH',
            headers: {
              ...window.AUTH.getHeaders(),
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              sitename: (Alpine.store('app').sitename || '').trim(),
              tagline: (this.tagline || '').trim(),
              hero_title: (this.hero_title || '').trim(),
              hero_image: (this.hero_image || '').trim(),
              contact_email: (this.contact_email || '').trim(),
              domain: (this.domain || '').trim(),
              display_logo: !!this.display_logo,
              comments_enabled: !!this.comments_enabled,
              social_links: this.socialLinks
                .map((l) => ({
                  platform: (l.platform || 'custom').trim(),
                  url: this.normalizeSocialUrl(l.platform, l.url),
                  label: l.platform === 'custom' && l.label ? l.label.trim() : undefined,
                }))
                .filter((l) => l.url !== ''),
            }),
          }
        );
        if (!patchRes.ok) {
          const errData = await patchRes.json().catch(() => ({}));
          throw new Error(
            errData.detail || `Failed to update site (${patchRes.status})`
          );
        }

        if (this.logoFile) {
          const logoRes = await window.api.uploadLogo(this.logoFile);
          if (logoRes && logoRes.url) {
            const sep = logoRes.url.includes('?') ? '&' : '?';
            this.logoPreview = logoRes.url + sep + 't=' + Date.now();
          }
          this.logoFile = null;
        }

        if (this.heroFile) {
          const heroRes = await window.api.uploadHero(this.heroFile);
          if (heroRes && heroRes.url) {
            const sep = heroRes.url.includes('?') ? '&' : '?';
            this.heroPreview = heroRes.url + sep + 't=' + Date.now();
          }
          this.heroFile = null;
        }

        if (this.faviconFile) {
          const favRes = await window.api.uploadFavicon(this.faviconFile);
          if (favRes && favRes.url) {
            const sep = favRes.url.includes('?') ? '&' : '?';
            this.faviconPreview = favRes.url + sep + 't=' + Date.now();
          }
          this.faviconFile = null;
        }

        this.showNotification('Site settings saved successfully.');
      } catch (err) {
        console.error('Failed to save site configuration:', err);
        this.showNotification(err.message || 'Failed to save settings.', 'error');
      } finally {
        this.saving = false;
      }
    },

    addSocialPlatform(platformId) {
      if (this.socialLinks.some((link) => link.platform === platformId)) return;
      this.socialLinks.push({ platform: platformId, url: '', label: '' });
    },

    addCustomSocial() {
      this.socialLinks.push({ platform: 'custom', label: '', url: '' });
    },

    removeSocial(index) {
      this.socialLinks.splice(index, 1);
    },

    isSocialPlatformAdded(platformId) {
      return this.socialLinks.some((link) => link.platform === platformId);
    },

    getSocialPlatformName(platformId) {
      const item = this.presetPlatforms.find((p) => p.id === platformId);
      return item ? item.name : platformId;
    },

    /**
     * Normalise a social-media URL to its canonical form.
     *
     * Handles bare usernames, @ prefixes, missing https://, alias domains,
     * and trailing slashes.  For unknown / federated platforms only generic
     * URL hygiene (ensure https://, strip trailing /) is applied.
     */
    normalizeSocialUrl(platform, rawInput) {
      let url = (rawInput || '').trim();
      if (!url) return '';

      const rules = SOCIAL_PLATFORM_RULES[platform] ?? null;

      // ----- Custom / federated (e.g. Mastodon): generic hygiene only -----
      if (rules === null) {
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
          const firstSeg = url.split('/')[0].split('?')[0];
          if (firstSeg.includes('.')) url = 'https://' + url;
        }
        url = url.replace('http://', 'https://');
        return url.replace(/\/+$/, '');
      }

      const { canonical, aliases, pathPrefix, knownPrefixes } = rules;

      // Strip leading @ and / — common user mistakes.
      let stripped = url.replace(/^[@/]+/, '').replace(/\/+$/, '');
      if (!stripped) return '';

      // Does this look like a URL or a bare username?
      const firstSeg = stripped.split('/')[0].split('?')[0];
      const isUrlLike = firstSeg.includes('.') || stripped.includes('://');

      if (isUrlLike) {
        // Ensure scheme.
        if (!stripped.startsWith('http://') && !stripped.startsWith('https://')) {
          stripped = 'https://' + stripped;
        }
        stripped = stripped.replace('http://', 'https://');

        // Split into host vs path.
        const afterScheme = stripped.includes('://') ? stripped.split('://')[1] : stripped;
        const slashIdx = afterScheme.indexOf('/');
        const hostname = (slashIdx === -1 ? afterScheme : afterScheme.substring(0, slashIdx)).toLowerCase();
        let path = slashIdx === -1 ? '' : afterScheme.substring(slashIdx);
        path = path.replace(/\/+$/, '');

        if (aliases.includes(hostname)) {
          // Rewrite to canonical domain, keep path.
          const hasKnown = knownPrefixes.length > 0 && knownPrefixes.some((kp) => path.startsWith(kp));
          if (hasKnown || !pathPrefix) {
            return canonical + path;
          }
          if (path) {
            return canonical + pathPrefix + path;
          }
          return canonical;
        }
        // Domain not in aliases — return cleaned URL as-is.
        return stripped;
      }

      // ----- Bare username / handle -----
      let username = stripped;

      if (platform === 'tiktok') {
        username = username.replace(/^@/, '');
        return canonical + '/@' + username;
      }
      if (platform === 'reddit') {
        for (const pfx of ['r/', 'u/', 'user/']) {
          if (username.toLowerCase().startsWith(pfx)) {
            return canonical + '/' + username;
          }
        }
        return canonical + '/user/' + username;
      }
      if (platform === 'youtube') {
        if (username.startsWith('@')) return canonical + '/' + username;
        for (const pfx of ['channel/', '@', 'c/', 'user/']) {
          if (username.startsWith(pfx)) return canonical + '/' + username;
        }
        return canonical + '/@' + username;
      }
      if (platform === 'linkedin') {
        for (const pfx of ['in/', 'company/', 'school/']) {
          if (username.toLowerCase().startsWith(pfx)) {
            return canonical + '/' + username;
          }
        }
        return canonical + '/in/' + username;
      }
      if (platform === 'bluesky') {
        return canonical + '/profile/' + username;
      }
      if (platform === 'whatsapp') {
        const digits = username.replace(/\D/g, '');
        if (digits && (username.startsWith('+') || /^\d+$/.test(username) || !/[a-zA-Z]/.test(username))) {
          return canonical + '/' + digits;
        }
        return canonical + '/' + username.replace(/^\/+/, '');
      }

      // Generic known platform.
      if (pathPrefix) {
        return canonical + pathPrefix + '/' + username;
      }
      return canonical + '/' + username;
    },

    /** Platform-specific placeholder text to guide the user. */
    getSocialPlaceholder(platform) {
      const hints = {
        twitter:   'username or https://x.com/username',
        bluesky:   'handle.bsky.social or full profile URL',
        mastodon:  'https://mastodon.social/@username',
        instagram: 'username or https://instagram.com/username',
        facebook:  'username or https://facebook.com/pagename',
        vk:        'username or https://vk.com/username',
        linkedin:  'username or https://linkedin.com/in/username',
        github:    'username or https://github.com/username',
        telegram:  'username or https://t.me/username',
        youtube:   '@handle or full channel URL',
        tiktok:    'username or https://tiktok.com/@username',
        reddit:    'u/username or https://reddit.com/u/username',
        discord:   'invite code or https://discord.gg/inviteCode',
        slack:     'https://workspace.slack.com or invite link',
        whatsapp:  'phone number or https://wa.me/1234567890',
      };
      return hints[platform] || 'https://...';
    },
  }));
});
