/**
 * PenCMS SEO Settings controller (settings-seo.js)
 * Tabs: Site Meta / Social Previews / Indexing (site-scoped via activeSiteId).
 * Persist via PATCH /api/sites/{id}. Social fields are sparse overrides
 * (empty = inherit theme social_preview defaults).
 */
document.addEventListener('alpine:init', () => {
  Alpine.data('settingsSeo', () => ({
    loading: true,
    saving: false,
    activeTab: 'meta',

    registryName: '',
    domain: '',
    tagline: '',
    hero_title: '',
    title_template: '',
    meta_description: '',
    keywords: '',

    robots_index: true,
    robots_follow: true,
    robots_txt: '',
    sitemap_enabled: true,
    google_site_verification: '',
    bing_site_verification: '',
    indexnow_enabled: false,
    indexnow_key: '',
    content_signal_ai_train: false,
    seo_redirects_text: '',
    regenerateIndexNow: false,

    // Social overrides (empty string / '' for bool select = inherit)
    social_preview_defaults: {},
    og_font_catalog: [],
    twitter_card: '',
    og_title_fallback: '',
    og_description_fallback: '',
    og_default_image: '',
    og_accent_color: '',
    og_vignette_color: '',
    og_text_color: '',
    og_bar_color: '',
    og_font: '',
    og_headline_style: '',
    og_text_case: '',
    og_grade_preset: '',
    og_accent_bar: '', // '', 'true', 'false'
    og_watermark_enabled: '', // '', 'true', 'false'
    og_fallback_title: '',
    og_default_hero: '',
    og_watermark: '',
    og_watermark_source: '',
    og_watermark_layout: '',
    og_watermark_corner: '',
    og_watermark_scale: '',
    hero_image: '',
    logoBrandingUrl: null,

    ogPreviewTitle: '',
    ogPreviewTitleLast: '',
    ogPreviewUseSiteHero: false,
    ogPreviewing: false,
    ogPreviewObjectUrl: null,
    ogPreviewTimer: null,
    ogPreviewToken: 0,
    ogPreviewAbort: null,

    ogDefaultFile: null,
    ogDefaultPreview: null,
    ogHeroFile: null,
    ogHeroPreview: null,
    ogWatermarkFile: null,
    ogWatermarkPreview: null,

    message: '',
    messageType: 'success',

    DEFAULT_TITLE_TEMPLATE: '%page% | %site%',

    SOCIAL_STRING_KEYS: [
      'twitter_card',
      'og_title_fallback',
      'og_description_fallback',
      'og_default_image',
      'og_accent_color',
      'og_vignette_color',
      'og_text_color',
      'og_bar_color',
      'og_font',
      'og_headline_style',
      'og_text_case',
      'og_grade_preset',
      'og_fallback_title',
      'og_default_hero',
      'og_watermark',
      'og_watermark_source',
      'og_watermark_layout',
      'og_watermark_corner',
      'og_watermark_scale',
    ],

    apiBase() {
      return ((window.AUTH && window.AUTH.apiBase) || '/api/v1').replace(
        /\/v1\/?$/,
        ''
      );
    },

    boolOrDefault(value, fallback = true) {
      if (value === null || value === undefined) return fallback;
      return !!value;
    },

    sitemapPublicUrl() {
      const domain = (this.domain || '').trim();
      if (domain) {
        return `https://${domain}/sitemap.xml`;
      }
      return '/sitemap.xml';
    },

    themeDefault(key) {
      const d = this.social_preview_defaults || {};
      const v = d[key];
      if (v === null || v === undefined) return '';
      return String(v);
    },

    themeFontIds() {
      return this.themeFontCatalog().map((f) => f.id);
    },

    themeFontCatalog() {
      return (this.og_font_catalog || []).filter((f) => f.source === 'theme');
    },

    registryFontCatalog() {
      return (this.og_font_catalog || []).filter(
        (f) => f.source === 'registry' || f.source === 'engine'
      );
    },

    hasRasterSiteLogo() {
      const url = this.logoBrandingUrl || '';
      return /\.(png|webp|jpe?g|gif)(\?|$)/i.test(url);
    },

    hasSvgOnlySiteLogo() {
      const url = this.logoBrandingUrl || '';
      return /\.svg(\?|$)/i.test(url) && !this.hasRasterSiteLogo();
    },

    watermarkUsesCorner() {
      if ((this.og_watermark_source || '') === 'logo') return true;
      const layout =
        (this.og_watermark_layout || '').trim() ||
        this.themeDefault('og_watermark_layout') ||
        'full_canvas';
      return layout === 'corner';
    },

    sourceTip(key) {
      const override = (this[key] || '').toString().trim();
      if (override) return 'Site override';
      return 'Theme default';
    },

    colorInputValue(key) {
      const raw = ((this[key] || '').trim() || this.themeDefault(key) || '#000000').trim();
      if (/^#[0-9A-Fa-f]{6}$/.test(raw)) return raw;
      return '#000000';
    },

    assetPreviewUrl(logical) {
      if (!logical) return null;
      const path = String(logical).trim();
      if (!path) return null;
      if (/^https?:\/\//i.test(path) || path.startsWith('data:')) return path;
      const siteId = Alpine.store('app').activeSiteId || 'default';
      let clean = path.replace(/^\/+/, '');
      if (clean.startsWith('assets/')) clean = clean.slice(7);
      if (clean.startsWith('images/') || clean.startsWith('fonts/')) {
        return `${this.apiBase()}/assets/raw/sites/${encodeURIComponent(siteId)}/assets/${clean}`;
      }
      // Theme-relative path — not previewable via site assets
      return null;
    },

    previewUrl(field) {
      if (field === 'og_default_image') {
        return this.ogDefaultPreview || this.assetPreviewUrl(this.og_default_image);
      }
      if (field === 'og_default_hero') {
        return this.ogHeroPreview || this.assetPreviewUrl(this.og_default_hero);
      }
      if (field === 'og_watermark') {
        return this.ogWatermarkPreview || this.assetPreviewUrl(this.og_watermark);
      }
      return null;
    },

    clearSocialImage(field) {
      const map = {
        og_default_image: {
          file: 'ogDefaultFile',
          preview: 'ogDefaultPreview',
          ref: 'ogDefaultInput',
        },
        og_default_hero: {
          file: 'ogHeroFile',
          preview: 'ogHeroPreview',
          ref: 'ogHeroInput',
        },
        og_watermark: {
          file: 'ogWatermarkFile',
          preview: 'ogWatermarkPreview',
          ref: 'ogWatermarkInput',
        },
      };
      const spec = map[field];
      if (!spec) return;
      this[field] = '';
      this[spec.file] = null;
      this[spec.preview] = null;
      const input = this.$refs[spec.ref];
      if (input) input.value = '';
    },

    handleSocialImageSelect(event, field) {
      const file = event.target.files && event.target.files[0];
      if (!file) return;
      this._assignSocialFile(field, file);
    },

    handleSocialImageDrop(event, field) {
      const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
      if (!file) return;
      this._assignSocialFile(field, file);
    },

    _assignSocialFile(field, file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        if (field === 'og_default_image') {
          this.ogDefaultFile = file;
          this.ogDefaultPreview = e.target.result;
        } else if (field === 'og_default_hero') {
          this.ogHeroFile = file;
          this.ogHeroPreview = e.target.result;
        } else if (field === 'og_watermark') {
          this.ogWatermarkFile = file;
          this.ogWatermarkPreview = e.target.result;
          this.og_watermark_source = 'custom';
        }
      };
      reader.readAsDataURL(file);
    },

    resetSocialToTheme() {
      for (const key of this.SOCIAL_STRING_KEYS) {
        this[key] = '';
      }
      this.og_accent_bar = '';
      this.og_watermark_enabled = '';
      this.ogDefaultFile = null;
      this.ogDefaultPreview = null;
      this.ogHeroFile = null;
      this.ogHeroPreview = null;
      this.ogWatermarkFile = null;
      this.ogWatermarkPreview = null;
      this.showNotification(
        'Social overrides cleared in the form. Save to persist theme defaults.',
        'success'
      );
    },

    async init() {
      await this.loadForm();
      this.$watch(
        () => this.$store.app.activeSiteId,
        async (next, prev) => {
          if (next && next !== prev) {
            await this.loadForm();
          }
        }
      );
      this._bindOgPreviewWatchers();
    },

    _ogLookSignature() {
      return [
        this.og_accent_color,
        this.og_vignette_color,
        this.og_text_color,
        this.og_bar_color,
        this.og_font,
        this.og_headline_style,
        this.og_text_case,
        this.og_grade_preset,
        this.og_accent_bar,
        this.og_watermark_enabled,
        this.og_watermark_source,
        this.og_watermark_layout,
        this.og_watermark_corner,
        this.og_watermark_scale,
        this.ogPreviewUseSiteHero ? '1' : '0',
        this.ogHeroPreview || '',
        this.ogWatermarkPreview || '',
        this.logoBrandingUrl || '',
      ].join('\0');
    },

    _bindOgPreviewWatchers() {
      this.$watch(
        () => this._ogLookSignature(),
        () => this._scheduleOgPreview()
      );
      this.$watch(
        () => this.activeTab,
        (tab) => {
          if (tab === 'social') this._scheduleOgPreview(0);
        }
      );
    },

    _scheduleOgPreview(delay = 450) {
      if (this.loading || this.saving || this.activeTab !== 'social') return;
      if (this.ogPreviewTimer) {
        clearTimeout(this.ogPreviewTimer);
        this.ogPreviewTimer = null;
      }
      this.ogPreviewTimer = setTimeout(() => {
        this.ogPreviewTimer = null;
        this.generateOgPreview({ toast: false });
      }, delay);
    },

    onOgPreviewTitleBlur() {
      if ((this.ogPreviewTitle || '') === (this.ogPreviewTitleLast || '')) return;
      this.generateOgPreview({ toast: false });
    },

    async loadForm() {
      this.loading = true;
      this.message = '';
      this.ogDefaultFile = null;
      this.ogDefaultPreview = null;
      this.ogHeroFile = null;
      this.ogHeroPreview = null;
      this.ogWatermarkFile = null;
      this.ogWatermarkPreview = null;
      try {
        const siteId = Alpine.store('app').activeSiteId || 'default';
        const res = await fetch(`${this.apiBase()}/sites`, {
          headers: window.AUTH.getHeaders(),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const site = (data.sites || []).find((s) => s.id === siteId) || {};

        this.registryName = site.name || '';
        this.domain = site.domain || '';
        Alpine.store('app').sitename = site.sitename || site.name || '';
        this.tagline = site.tagline || '';
        this.hero_title = site.hero_title || '';
        this.title_template =
          site.title_template || this.DEFAULT_TITLE_TEMPLATE;
        this.meta_description = site.meta_description || '';
        this.keywords = site.keywords || '';

        this.robots_index = this.boolOrDefault(site.robots_index, true);
        this.robots_follow = this.boolOrDefault(site.robots_follow, true);
        this.robots_txt = site.robots_txt || '';
        this.sitemap_enabled = this.boolOrDefault(site.sitemap_enabled, true);
        this.google_site_verification = site.google_site_verification || '';
        this.bing_site_verification = site.bing_site_verification || '';
        this.indexnow_enabled = this.boolOrDefault(site.indexnow_enabled, false);
        this.indexnow_key = site.indexnow_key || '';
        this.content_signal_ai_train = this.boolOrDefault(
          site.content_signal_ai_train,
          false
        );
        this.seo_redirects_text = this.redirectsToText(site.seo_redirects || []);
        this.regenerateIndexNow = false;

        this.social_preview_defaults = site.social_preview_defaults || {};
        this.og_font_catalog = site.og_font_catalog || [];
        this.hero_image = site.hero_image || '';
        if (!this.hero_image) this.ogPreviewUseSiteHero = false;
        this._revokeOgPreview();
        this.logoBrandingUrl = null;
        try {
          if (window.api && window.api.getSiteBranding) {
            const branding = await window.api.getSiteBranding();
            this.logoBrandingUrl = (branding && branding.logo) || null;
          }
        } catch (brandErr) {
          console.error('Failed to load site branding:', brandErr);
        }

        // Sparse: keep empty when unset (do not coerce to theme values)
        for (const key of this.SOCIAL_STRING_KEYS) {
          this[key] = site[key] || '';
        }
        if (site.og_accent_bar === true) this.og_accent_bar = 'true';
        else if (site.og_accent_bar === false) this.og_accent_bar = 'false';
        else this.og_accent_bar = '';
        if (site.og_watermark_enabled === true) this.og_watermark_enabled = 'true';
        else if (site.og_watermark_enabled === false) this.og_watermark_enabled = 'false';
        else this.og_watermark_enabled = '';
      } catch (err) {
        console.error('Failed to load SEO settings:', err);
        this.showNotification(
          err.message || 'Failed to load SEO settings',
          'error'
        );
      } finally {
        this.loading = false;
      }
      if (this.activeTab === 'social') {
        this._scheduleOgPreview(0);
      }
    },

    redirectsToText(list) {
      return (list || [])
        .map((row) => `${row.from || ''} -> ${row.to || ''}`)
        .join('\n');
    },

    parseRedirectsText() {
      const lines = (this.seo_redirects_text || '').split('\n');
      const out = [];
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        const parts = trimmed.split(/\s*->\s*/);
        if (parts.length !== 2 || !parts[0].trim() || !parts[1].trim()) {
          throw new Error(`Invalid redirect line: ${trimmed}`);
        }
        out.push({ from: parts[0].trim(), to: parts[1].trim() });
      }
      return out;
    },

    showNotification(msg, type = 'success') {
      this.message = msg;
      this.messageType = type;
      setTimeout(() => {
        this.message = '';
      }, 5000);
    },

    socialPayload() {
      const payload = {};
      for (const key of this.SOCIAL_STRING_KEYS) {
        payload[key] = (this[key] || '').trim();
      }
      if (this.og_accent_bar === 'true') payload.og_accent_bar = true;
      else if (this.og_accent_bar === 'false') payload.og_accent_bar = false;
      else payload.og_accent_bar = null;
      if (this.og_watermark_enabled === 'true') payload.og_watermark_enabled = true;
      else if (this.og_watermark_enabled === 'false') payload.og_watermark_enabled = false;
      else payload.og_watermark_enabled = null;
      return payload;
    },

    _revokeOgPreview() {
      if (this.ogPreviewObjectUrl) {
        URL.revokeObjectURL(this.ogPreviewObjectUrl);
        this.ogPreviewObjectUrl = null;
      }
    },

    async generateOgPreview({ toast = true } = {}) {
      const token = ++this.ogPreviewToken;
      if (this.ogPreviewAbort) {
        this.ogPreviewAbort.abort();
      }
      this.ogPreviewAbort = new AbortController();
      this.ogPreviewing = true;
      this.ogPreviewTitleLast = this.ogPreviewTitle;
      try {
        const siteId = Alpine.store('app').activeSiteId || 'default';
        const payload = {
          ...this.socialPayload(),
          title: (this.ogPreviewTitle || '').trim() || undefined,
          use_site_hero: !!(this.ogPreviewUseSiteHero && this.hero_image),
        };
        if (
          typeof this.ogHeroPreview === 'string' &&
          this.ogHeroPreview.startsWith('data:')
        ) {
          payload.hero_data_url = this.ogHeroPreview;
        }
        if (
          this.og_watermark_source !== 'logo' &&
          typeof this.ogWatermarkPreview === 'string' &&
          this.ogWatermarkPreview.startsWith('data:')
        ) {
          payload.watermark_data_url = this.ogWatermarkPreview;
        }
        const res = await fetch(
          `${this.apiBase()}/sites/${encodeURIComponent(siteId)}/og-preview`,
          {
            method: 'POST',
            headers: {
              ...window.AUTH.getHeaders(),
              'Content-Type': 'application/json',
            },
            signal: this.ogPreviewAbort.signal,
            body: JSON.stringify(payload),
          }
        );
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(
            errData.detail || `Preview failed (${res.status})`
          );
        }
        const blob = await res.blob();
        const nextUrl = URL.createObjectURL(blob);
        if (token !== this.ogPreviewToken) {
          URL.revokeObjectURL(nextUrl);
          return;
        }
        this._revokeOgPreview();
        this.ogPreviewObjectUrl = nextUrl;
      } catch (err) {
        if (err && err.name === 'AbortError') return;
        if (token !== this.ogPreviewToken) return;
        console.error('Failed to generate OG preview:', err);
        if (toast) {
          this.showNotification(
            err.message || 'Failed to generate OG preview',
            'error'
          );
        }
      } finally {
        if (token === this.ogPreviewToken) {
          this.ogPreviewing = false;
        }
      }
    },

    async save() {
      this.saving = true;
      this.message = '';
      try {
        const siteId = Alpine.store('app').activeSiteId || 'default';

        if (this.ogDefaultFile && window.api && window.api.uploadOgDefault) {
          const up = await window.api.uploadOgDefault(this.ogDefaultFile);
          if (up && up.path) this.og_default_image = up.path;
          this.ogDefaultFile = null;
          if (up && up.url) this.ogDefaultPreview = up.url;
        }
        if (this.ogHeroFile && window.api && window.api.uploadOgDefaultHero) {
          const up = await window.api.uploadOgDefaultHero(this.ogHeroFile);
          if (up && up.path) this.og_default_hero = up.path;
          this.ogHeroFile = null;
          if (up && up.url) this.ogHeroPreview = up.url;
        }
        if (this.ogWatermarkFile && window.api && window.api.uploadOgWatermark) {
          const up = await window.api.uploadOgWatermark(this.ogWatermarkFile);
          if (up && up.path) this.og_watermark = up.path;
          this.ogWatermarkFile = null;
          if (up && up.url) this.ogWatermarkPreview = up.url;
        }

        const titleTemplate = (this.title_template || '').trim();
        const payload = {
              sitename: (Alpine.store('app').sitename || '').trim(),
              tagline: (this.tagline || '').trim(),
              hero_title: (this.hero_title || '').trim(),
              title_template: titleTemplate || this.DEFAULT_TITLE_TEMPLATE,
              meta_description: (this.meta_description || '').trim(),
              keywords: (this.keywords || '').trim(),
              robots_index: !!this.robots_index,
              robots_follow: !!this.robots_follow,
              robots_txt: (this.robots_txt || '').trim(),
              sitemap_enabled: !!this.sitemap_enabled,
              google_site_verification: (
                this.google_site_verification || ''
              ).trim(),
              bing_site_verification: (this.bing_site_verification || '').trim(),
              indexnow_enabled: !!this.indexnow_enabled,
              content_signal_ai_train: !!this.content_signal_ai_train,
              seo_redirects: this.parseRedirectsText(),
              ...this.socialPayload(),
        };
        if (this.regenerateIndexNow) {
          payload.indexnow_key = '';
        }
        const patchRes = await fetch(
          `${this.apiBase()}/sites/${encodeURIComponent(siteId)}`,
          {
            method: 'PATCH',
            headers: {
              ...window.AUTH.getHeaders(),
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
          }
        );
        if (!patchRes.ok) {
          const errData = await patchRes.json().catch(() => ({}));
          throw new Error(
            errData.detail || `Failed to update site (${patchRes.status})`
          );
        }

        const updated = await patchRes.json();
        Alpine.store('app').sitename =
          updated.sitename || this.registryName || Alpine.store('app').sitename;
        if (updated.title_template) {
          this.title_template = updated.title_template;
        }
        this.domain = updated.domain || this.domain || '';
        this.robots_index = this.boolOrDefault(updated.robots_index, true);
        this.robots_follow = this.boolOrDefault(updated.robots_follow, true);
        this.robots_txt = updated.robots_txt || '';
        this.sitemap_enabled = this.boolOrDefault(
          updated.sitemap_enabled,
          true
        );
        this.google_site_verification =
          updated.google_site_verification || '';
        this.bing_site_verification = updated.bing_site_verification || '';
        this.indexnow_enabled = this.boolOrDefault(
          updated.indexnow_enabled,
          false
        );
        this.indexnow_key = updated.indexnow_key || '';
        this.content_signal_ai_train = this.boolOrDefault(
          updated.content_signal_ai_train,
          false
        );
        this.seo_redirects_text = this.redirectsToText(
          updated.seo_redirects || []
        );
        this.regenerateIndexNow = false;

        this.social_preview_defaults =
          updated.social_preview_defaults || this.social_preview_defaults;
        if (updated.og_font_catalog) {
          this.og_font_catalog = updated.og_font_catalog;
        }
        for (const key of this.SOCIAL_STRING_KEYS) {
          this[key] = updated[key] || '';
        }
        if (updated.og_accent_bar === true) this.og_accent_bar = 'true';
        else if (updated.og_accent_bar === false) this.og_accent_bar = 'false';
        else this.og_accent_bar = '';
        if (updated.og_watermark_enabled === true) this.og_watermark_enabled = 'true';
        else if (updated.og_watermark_enabled === false) this.og_watermark_enabled = 'false';
        else this.og_watermark_enabled = '';

        this.showNotification('SEO settings saved successfully.');
      } catch (err) {
        console.error('Failed to save SEO settings:', err);
        this.showNotification(
          err.message || 'Failed to save SEO settings',
          'error'
        );
      } finally {
        this.saving = false;
      }
    },
  }));
});
