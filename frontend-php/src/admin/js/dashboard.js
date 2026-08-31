/**
 * PenCMS Admin Dashboard — site-scoped command center
 */
document.addEventListener("alpine:init", () => {
  Alpine.data("adminDashboard", () => ({
    loading: true,
    branding: null,
    menus: null,
    taxonomy: null,
    loadError: null,
    _reloading: false,
    _summaryFillRunId: 0,
    summaryFill: {
      status: "idle",
      total: 0,
      current: 0,
      filled: 0,
      skipped: 0,
      failed: 0,
      error: "",
      cancelRequested: false,
    },

    get sites() {
      return (this.$store.app && this.$store.app.sites) || [];
    },

    get activeSiteId() {
      return (this.$store.app && this.$store.app.activeSiteId) || "default";
    },

    get activeSite() {
      const id = this.activeSiteId;
      return this.sites.find((s) => s.id === id) || null;
    },

    get useSiteTabs() {
      const n = this.sites.length;
      return n >= 2 && n <= 5;
    },

    get useSiteRail() {
      return this.sites.length > 5;
    },

    get sitename() {
      const s = this.activeSite;
      if (s && s.sitename) return s.sitename;
      if (s && s.name) return s.name;
      return (this.$store.app && this.$store.app.sitename) || "PenCMS";
    },

    async init() {
      this.$watch(
        () => this.$store.app.activeSiteId,
        async (next, prev) => {
          if (!next || next === prev) return;
          await this.reload();
        }
      );
      await this.reload();
    },

    async selectSite(id) {
      if (!id || id === this.activeSiteId) return;
      await this.$store.app.setActiveSite(id);
    },

    async reload() {
      if (this._reloading) return;
      this._summaryFillRunId += 1;
      this._resetSummaryFill();
      this._reloading = true;
      this.loading = true;
      this.loadError = null;
      try {
        await Promise.all([
          this.$store.app.fetchPages(),
          this.loadBranding(),
          this.loadMenus(),
          this.loadTaxonomy(),
        ]);
      } catch (err) {
        console.error("Dashboard reload failed:", err);
        this.loadError = "Failed to load dashboard data for this site.";
      } finally {
        this.loading = false;
        this._reloading = false;
      }
    },

    async loadBranding() {
      try {
        this.branding = await window.api.getSiteBranding();
      } catch (err) {
        console.error("Failed to load branding:", err);
        this.branding = { logo: null, favicon: null };
      }
    },

    async loadMenus() {
      try {
        this.menus = await window.api.getMenus();
      } catch (err) {
        console.error("Failed to load menus:", err);
        this.menus = { primary: [], secondary: [], footer: [] };
      }
    },

    async loadTaxonomy() {
      try {
        const response = await window.api.getTaxonomy();
        // API returns { raw, parsed }; prefer raw (same as Structure settings)
        this.taxonomy =
          (response && (response.raw || response.parsed)) ||
          response ||
          { vocabularies: {}, primary_vocabulary: "" };
      } catch (err) {
        console.error("Failed to load taxonomy:", err);
        this.taxonomy = { vocabularies: {}, primary_vocabulary: "" };
      }
    },

    isPage(entry) {
      return !!(
        entry &&
        entry.frontmatter &&
        (entry.frontmatter.page === true || entry.frontmatter.page === "true")
      );
    },

    entryStatus(entry) {
      const raw =
        (entry && entry.frontmatter && entry.frontmatter.status) ||
        entry.status ||
        "";
      return String(raw).toLowerCase();
    },

    entryTitle(entry) {
      if (!entry) return "Untitled";
      const fm = entry.frontmatter || {};
      return (
        fm.hero_title ||
        fm.name ||
        fm.title ||
        entry.title ||
        entry.id ||
        "Untitled"
      );
    },

    entryModified(entry) {
      if (!entry) return 0;
      const raw =
        entry.modified_at ||
        (entry.frontmatter &&
          (entry.frontmatter.modified_at || entry.frontmatter.updated)) ||
        "";
      const t = Date.parse(raw);
      return Number.isFinite(t) ? t : 0;
    },

    sortByModified(list) {
      return [...list].sort(
        (a, b) => this.entryModified(b) - this.entryModified(a)
      );
    },

    get posts() {
      const pages = (this.$store.app && this.$store.app.pages) || [];
      return pages.filter((p) => !this.isPage(p));
    },

    get pagesOnly() {
      const pages = (this.$store.app && this.$store.app.pages) || [];
      return pages.filter((p) => this.isPage(p));
    },

    get stats() {
      const posts = this.posts;
      const by = (status) =>
        posts.filter((p) => this.entryStatus(p) === status).length;
      return {
        published: by("published"),
        draft: by("draft"),
        stub: by("stub"),
        unpublished: by("unpublished"),
        pages: this.pagesOnly.length,
      };
    },

    get attentionItems() {
      const items = [];
      const site = this.activeSite || {};

      if (!String(site.contact_email || "").trim()) {
        items.push({
          id: "contact_email",
          label: "Add a contact email",
          href: "admin-settings-site.php",
          hrefLabel: "Site Settings",
        });
      }
      if (!String(site.tagline || "").trim()) {
        items.push({
          id: "tagline",
          label: "Add a site tagline",
          href: "admin-settings-site.php",
          hrefLabel: "Site Settings",
        });
      }
      if (!String(site.hero_image || "").trim()) {
        items.push({
          id: "hero_image",
          label: "Set a default hero image",
          href: "admin-settings-site.php",
          hrefLabel: "Site Settings",
        });
      }
      if (!this.branding || !this.branding.logo) {
        items.push({
          id: "logo",
          label: "Upload a site logo",
          href: "admin-settings-site.php",
          hrefLabel: "Site Settings",
        });
      }

      const primary = (this.menus && this.menus.primary) || [];
      if (!Array.isArray(primary) || primary.length === 0) {
        items.push({
          id: "menus",
          label: "Set up the primary menu",
          href: "admin-settings-navigation.php",
          hrefLabel: "Navigation",
        });
      }

      const vocabs =
        (this.taxonomy && this.taxonomy.vocabularies) ||
        {};
      const vocabKeys = Object.keys(vocabs);
      const hasTerms = vocabKeys.some((k) => {
        const terms = vocabs[k] && vocabs[k].terms;
        return Array.isArray(terms) && terms.length > 0;
      });
      if (vocabKeys.length === 0 || !hasTerms) {
        items.push({
          id: "taxonomy",
          label: "Add at least one vocabulary with terms",
          href: "admin-settings-structure.php",
          hrefLabel: "Structure",
        });
      }

      if (!String(site.theme || "").trim()) {
        items.push({
          id: "theme",
          label: "Choose a theme for this site",
          href: "admin-settings-theme.php",
          hrefLabel: "Themes",
        });
      }

      if (!String(site.domain || "").trim()) {
        items.push({
          id: "domain",
          label: "Set a domain for public URLs",
          href: "admin-settings-site.php",
          hrefLabel: "Site Settings",
          soft: true,
        });
      }

      // Soft export reminder — always shown (last-export not persisted yet)
      items.push({
        id: "export",
        label: "Publish or export static site — last publish time is not recorded yet",
        href: "admin-publish.php",
        hrefLabel: "Publish",
        soft: true,
      });

      return items;
    },

    get incompleteAttention() {
      return this.attentionItems.filter((i) => i.id !== "export");
    },

    get exportAttention() {
      return this.attentionItems.find((i) => i.id === "export") || null;
    },

    get setupAllClear() {
      return this.incompleteAttention.length === 0;
    },

    get latestPublished() {
      return this.sortByModified(
        this.posts.filter((p) => this.entryStatus(p) === "published")
      ).slice(0, 5);
    },

    get latestInProgress() {
      return this.sortByModified(
        this.posts.filter((p) => {
          const s = this.entryStatus(p);
          return s === "draft" || s === "stub";
        })
      ).slice(0, 5);
    },

    get mainPages() {
      return this.sortByModified(this.pagesOnly).slice(0, 8);
    },

    editorHref(entry) {
      if (!entry || !entry.id) {
        return this.$store.app.adminPath('admin-editor.php');
      }
      const params = { id: entry.id };
      if (entry.collection) params.collection = entry.collection;
      return this.$store.app.adminPath('admin-editor.php', params);
    },

    previewHref() {
      return this.$store.app.previewUrl();
    },

    siteLabel(site) {
      if (!site) return "";
      if (site.name) return site.id + " — " + site.name;
      return site.id;
    },

    statusBadgeClass(status) {
      const s = String(status || "").toLowerCase();
      if (s === "published") return "bg-acid";
      if (s === "stub") return "bg-black/20";
      if (s === "draft") return "bg-black/40";
      if (s === "unpublished") return "bg-black/60";
      return "bg-black/20";
    },

    summaryEmpty(value) {
      return !String(value == null ? "" : value).trim();
    },

    get emptySummaryPublished() {
      const pages = (this.$store.app && this.$store.app.pages) || [];
      return pages.filter((entry) => {
        if (this.entryStatus(entry) !== "published") return false;
        const fm = (entry && entry.frontmatter) || {};
        return this.summaryEmpty(fm.summary);
      });
    },

    get emptySummaryCount() {
      return this.emptySummaryPublished.length;
    },

    get summaryFillResultText() {
      const p = this.summaryFill;
      const parts = [];
      if (p.cancelRequested) parts.push("Stopped.");
      parts.push("Filled " + p.filled + ".");
      if (p.skipped) parts.push("Skipped " + p.skipped + ".");
      if (p.failed) parts.push("Failed " + p.failed + ".");
      return parts.join(" ");
    },

    _resetSummaryFill() {
      this.summaryFill = {
        status: "idle",
        total: 0,
        current: 0,
        filled: 0,
        skipped: 0,
        failed: 0,
        error: "",
        cancelRequested: false,
      };
    },

    _frontmatterForSave(fm) {
      const next = { ...(fm || {}) };
      [
        "created_by",
        "created_by_id",
        "updated_by",
        "updated_by_id",
        "run_id",
        "needs_review",
        "reviewed_by",
        "reviewed_at",
        "review_decision",
        "review_note",
        "language",
        "translation_group",
      ].forEach((key) => {
        delete next[key];
      });
      return next;
    },

    requestFillEmptySummaries() {
      if (this.summaryFill.status === "running") return;
      if (this.emptySummaryCount === 0) return;
      this.summaryFill.status = "confirm";
      this.summaryFill.error = "";
      this.summaryFill.cancelRequested = false;
    },

    cancelSummaryFill() {
      if (this.summaryFill.status === "running") {
        this.summaryFill.cancelRequested = true;
        return;
      }
      this._resetSummaryFill();
    },

    async confirmFillEmptySummaries() {
      if (this.summaryFill.status === "running") return;
      const candidates = this.emptySummaryPublished.slice();
      if (!candidates.length) {
        this._resetSummaryFill();
        return;
      }
      if (typeof window.penAiExtract !== "function") {
        this.summaryFill.status = "error";
        this.summaryFill.error = "Extract helper is not loaded.";
        return;
      }

      const runId = ++this._summaryFillRunId;
      const siteId = this.activeSiteId;
      this.summaryFill.status = "running";
      this.summaryFill.total = candidates.length;
      this.summaryFill.current = 0;
      this.summaryFill.filled = 0;
      this.summaryFill.skipped = 0;
      this.summaryFill.failed = 0;
      this.summaryFill.error = "";
      this.summaryFill.cancelRequested = false;

      for (let i = 0; i < candidates.length; i++) {
        if (runId !== this._summaryFillRunId) return;
        if (this.summaryFill.cancelRequested || this.activeSiteId !== siteId) {
          break;
        }
        this.summaryFill.current = i + 1;
        try {
          const outcome = await this._fillOneEmptySummary(candidates[i], siteId);
          if (outcome === "filled") this.summaryFill.filled += 1;
          else if (outcome === "skipped") this.summaryFill.skipped += 1;
          else this.summaryFill.failed += 1;
        } catch (err) {
          if (err && (err.code === "vault_locked" || err.code === "no_provider")) {
            this.summaryFill.status = "error";
            this.summaryFill.error = (err && err.message) || "AI is not ready.";
            break;
          }
          this.summaryFill.failed += 1;
        }
      }

      if (runId !== this._summaryFillRunId) return;
      if (this.activeSiteId === siteId) {
        try {
          await this.$store.app.fetchPages();
        } catch (err) {
          console.error("Failed to refresh pages after summary fill:", err);
        }
      }
      if (runId !== this._summaryFillRunId) return;
      if (this.summaryFill.status === "running") {
        this.summaryFill.status = "done";
      }
    },

    async _fillOneEmptySummary(item, siteId) {
      if (!item || !item.id) return "failed";
      if (siteId && this.activeSiteId !== siteId) return "skipped";
      const language = item.language || null;
      const entry = await window.api.getPage(item.id, item.collection, language);
      if (siteId && this.activeSiteId !== siteId) return "skipped";
      const fm = (entry && entry.frontmatter) || {};
      const status = String(fm.status || item.status || "").toLowerCase();
      if (status !== "published") return "skipped";
      const currentSummary = fm.summary;
      if (!this.summaryEmpty(currentSummary)) return "skipped";
      const body = entry && entry.content != null ? String(entry.content) : "";
      if (!body.trim()) return "skipped";

      let result;
      try {
        result = await window.penAiExtract({
          field: "summary",
          body,
          currentValue: currentSummary || "",
          replace: false,
        });
      } catch (err) {
        if (err && err.status === 409) return "skipped";
        throw err;
      }

      const value = String((result && result.value) || "").trim();
      if (!value) return "failed";
      if (siteId && this.activeSiteId !== siteId) return "skipped";

      const payload = {
        frontmatter: { ...this._frontmatterForSave(fm), summary: value },
        content: body,
        composite: !!(entry && entry.composite),
        partials: (entry && entry.partials) || {},
      };
      if (entry && entry.version != null && entry.version !== "") {
        payload.expected_version = entry.version;
      }

      try {
        await window.api.updatePage(
          item.id,
          payload,
          language,
          item.collection
        );
      } catch (err) {
        if (err && err.status === 409) return "skipped";
        throw err;
      }
      return "filled";
    },
  }));
});
