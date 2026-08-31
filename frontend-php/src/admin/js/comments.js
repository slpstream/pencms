/**
 * PenCMS Comments admin — inbox / approve / reply / hide / delete / edit.
 * Distinct from the fb-* Feedback inbox. Does not call getPage / deletePage.
 */
document.addEventListener("alpine:init", () => {
  Alpine.data("commentsAdmin", () => ({
    postSlug: "",
    comments: [],
    pendingCounts: {},
    loading: false,
    savingSlug: null,
    filterVisibility: "PENDING",
    groupPage: 1,
    groupsPerPage: 10,
    digestLimit: 10,
    expandedDigestSlug: null,
    deleteModalOpen: false,
    itemToDelete: null,
    comments_enabled: false,
    commentsFlagKnown: false,
    savingCommentsEnabled: false,
    pulling: false,
    pullBanner: null,
    replyingSlug: null,
    replyBody: "",
    editingSlug: null,
    editBody: "",
    editAuthor: "",

    get postOptions() {
      const pages = (this.$store.app.pages || []).filter((page) => {
        const id = String((page && (page.id || page.slug)) || "");
        return id && !id.startsWith("fb-");
      });
      pages.sort((a, b) => {
        const na = this.postLabel(a).toLowerCase();
        const nb = this.postLabel(b).toLowerCase();
        return na.localeCompare(nb);
      });
      return pages;
    },

    get pendingTotal() {
      return Object.values(this.pendingCounts).reduce(
        (sum, n) => sum + (Number(n) || 0),
        0,
      );
    },

    get latestComments() {
      return this.comments
        .filter((item) => {
          const vis = String(item.visibility || "").toLowerCase();
          return vis === "visible" || vis === "hidden";
        })
        .sort((a, b) => {
          const ta = String(a.received_at || "");
          const tb = String(b.received_at || "");
          if (tb !== ta) return tb.localeCompare(ta);
          return String(b.slug || "").localeCompare(String(a.slug || ""));
        });
    },

    get pagedLatestComments() {
      return this.latestComments.slice(0, this.digestLimit);
    },

    get filteredComments() {
      const vis = this.filterVisibility;
      if (vis === "ALL") return this.comments;
      const want = vis.toLowerCase();
      return this.comments.filter(
        (item) => String(item.visibility || "").toLowerCase() === want,
      );
    },

    get commentGroups() {
      const byPost = new Map();
      for (const item of this.filteredComments) {
        const slug = String(item.post_slug || this.postSlug || "").trim();
        if (!byPost.has(slug)) byPost.set(slug, []);
        byPost.get(slug).push(item);
      }
      const groups = [];
      for (const [slug, comments] of byPost) {
        comments.sort((a, b) =>
          String(b.received_at || "").localeCompare(String(a.received_at || "")),
        );
        groups.push({
          postSlug: slug,
          comments,
          latest: comments[0] ? comments[0].received_at || "" : "",
          pendingInFilter: comments.filter(
            (c) => String(c.visibility || "").toLowerCase() === "pending",
          ).length,
        });
      }
      groups.sort((a, b) => String(b.latest).localeCompare(String(a.latest)));
      return groups;
    },

    get groupPageCount() {
      const n = this.commentGroups.length;
      if (!n) return 1;
      return Math.max(1, Math.ceil(n / this.groupsPerPage));
    },

    get pagedGroups() {
      const start = (this.groupPage - 1) * this.groupsPerPage;
      return this.commentGroups.slice(start, start + this.groupsPerPage);
    },

    postLabel(page) {
      const fm = (page && page.frontmatter) || {};
      const title = fm.hero_title || fm.name || fm.title;
      return (title || (page && (page.id || page.slug)) || "").trim();
    },

    postOptionLabel(page) {
      const base = this.postLabel(page);
      const id = page.id || page.slug || "";
      const n = Number(this.pendingCounts[id]) || 0;
      return n ? `${base} · ${n} pending` : base;
    },

    groupTitle(group) {
      const slug = group && group.postSlug;
      const page = this.postOptions.find(
        (p) => (p.id || p.slug) === slug,
      );
      if (page) return this.postLabel(page);
      return slug || "Unknown post";
    },

    groupPendingBadge(group) {
      const slug = group && group.postSlug;
      return Number(this.pendingCounts[slug]) || 0;
    },

    previewUrlFor(postSlug) {
      const page = this.postOptions.find(
        (p) => (p.id || p.slug) === postSlug,
      );
      const fm = (page && page.frontmatter) || {};
      const cat = String(fm.category || (page && page.collection) || "posts");
      const isPage = cat === "pages" || cat === "page";
      if (typeof this.$store.app.previewContentUrl === "function") {
        return this.$store.app.previewContentUrl(postSlug, isPage);
      }
      return `/blog/post.php?slug=${encodeURIComponent(postSlug || "")}`;
    },

    formatDate(value) {
      const raw = value || "";
      if (!raw) return "—";
      const d = new Date(raw);
      if (Number.isNaN(d.getTime())) return String(raw);
      return d.toISOString().replace("T", " ").replace(/\.\d+Z$/, " UTC");
    },

    formatDigestDate(value) {
      const raw = value || "";
      if (!raw) return "—";
      const d = new Date(raw);
      if (Number.isNaN(d.getTime())) return String(raw);
      const pad = (n) => String(n).padStart(2, "0");
      const yyyy = d.getUTCFullYear();
      const mm = pad(d.getUTCMonth() + 1);
      const dd = pad(d.getUTCDate());
      const hh = pad(d.getUTCHours());
      const min = pad(d.getUTCMinutes());
      return `${yyyy}-${mm}-${dd} ${hh}:${min}`;
    },

    truncateText(str, maxLength) {
      const text = String(str || "").replace(/\s+/g, " ").trim();
      if (!text) return "";
      if (text.length <= maxLength) return text;
      return text.slice(0, maxLength) + "…";
    },

    postNameFor(postSlug) {
      const slug = String(postSlug || "").trim();
      const page = this.postOptions.find(
        (p) => (p.id || p.slug) === slug,
      );
      if (page) return this.postLabel(page);
      return slug || "Unknown post";
    },

    showMoreDigest() {
      this.digestLimit += 10;
    },

    toggleDigest(item) {
      const slug = item && item.slug;
      if (!slug) return;
      if (this.expandedDigestSlug === slug) {
        this.expandedDigestSlug = null;
        this.resetEditors();
      } else {
        this.expandedDigestSlug = slug;
        this.resetEditors();
      }
    },

    visibilityClass(visibility) {
      const vis = String(visibility || "").toLowerCase();
      if (vis === "visible") return "text-rust";
      if (vis === "pending") return "text-warning";
      if (vis === "hidden") return "text-forge-mid";
      return "text-forge-dark";
    },

    itemPostSlug(item) {
      return String((item && item.post_slug) || this.postSlug || "").trim();
    },

    queryPostSlug() {
      try {
        return (
          new URLSearchParams(window.location.search).get("post_slug") || ""
        ).trim();
      } catch (err) {
        return "";
      }
    },

    activeSiteRecord() {
      const id = this.$store.app.activeSiteId || "default";
      return (this.$store.app.sites || []).find((s) => s && s.id === id) || null;
    },

    syncCommentsEnabled() {
      const site = this.activeSiteRecord();
      this.comments_enabled = !!(site && site.comments_enabled);
      this.commentsFlagKnown = true;
    },

    apiSitesBase() {
      return ((window.AUTH && window.AUTH.apiBase) || "/api/v1").replace(
        /\/v1\/?$/,
        "",
      );
    },

    async autoPull() {
      if (!this.comments_enabled || !this.$store.app.hasCap("write:posts")) return;
      try {
        await window.api.syncFeedback();
      } catch (err) {
        console.warn("Auto pull from relay skipped or failed:", err);
      }
    },

    async pullFromRelay() {
      if (!this.$store.app.hasCap("write:posts") || this.pulling) return;
      this.pulling = true;
      this.pullBanner = null;
      try {
        const result = await window.api.syncFeedback();
        const written = Number(result && result.written) || 0;
        const reason = result && result.reason;
        if (reason === "no_relay_configured" || reason === "relay_unreachable") {
          this.pullBanner = { type: "reason", message: reason };
        } else {
          this.pullBanner = {
            type: "ok",
            message:
              written === 1 ? "Pulled 1 item" : `Pulled ${written} items`,
          };
        }
        await this.$store.app.fetchPages();
        await this.reload();
      } catch (err) {
        console.error("Pull from relay failed:", err);
        this.pullBanner = {
          type: "reason",
          message: err.message || "Pull failed",
        };
      } finally {
        this.pulling = false;
      }
    },

    async ensureModerationData() {
      if (!this.comments_enabled) return;
      if (this.$store.app.hasCap("write:posts")) {
        await this.autoPull();
      }
      await this.$store.app.fetchPages();
      const fromQuery = this.queryPostSlug();
      if (fromQuery && !this.postSlug) {
        this.postSlug = fromQuery;
      }
      await this.reload();
    },

    async init() {
      if (
        !(this.$store.app.sites || []).length &&
        typeof this.$store.app.loadSites === "function"
      ) {
        await this.$store.app.loadSites();
      }
      this.syncCommentsEnabled();
      await this.ensureModerationData();
      this.$watch(
        () => this.$store.app.activeSiteId,
        async (next, prev) => {
          if (!next || next === prev) return;
          this.postSlug = "";
          this.comments = [];
          this.pendingCounts = {};
          this.digestLimit = 10;
          this.expandedDigestSlug = null;
          this.deleteModalOpen = false;
          this.itemToDelete = null;
          this.resetEditors();
          this.syncCommentsEnabled();
          await this.ensureModerationData();
        },
      );
    },

    leaveWithoutChange() {
      window.location.href = this.$store.app.adminPath("admin-dashboard.php");
    },

    async toggleCommentsEnabled() {
      if (!this.$store.app.hasCap("write:seo")) return;
      await this.setCommentsEnabled(!this.comments_enabled);
    },

    async setCommentsEnabled(next) {
      if (this.savingCommentsEnabled) return;
      if (!this.$store.app.hasCap("write:seo")) return;
      const enabled = !!next;
      this.savingCommentsEnabled = true;
      try {
        const siteId = this.$store.app.activeSiteId || "default";
        const patchRes = await fetch(
          `${this.apiSitesBase()}/sites/${encodeURIComponent(siteId)}`,
          {
            method: "PATCH",
            headers: {
              ...window.AUTH.getHeaders(),
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ comments_enabled: enabled }),
          },
        );
        if (!patchRes.ok) {
          const errData = await patchRes.json().catch(() => ({}));
          throw new Error(
            errData.detail || `Failed to update site (${patchRes.status})`,
          );
        }
        const site = this.activeSiteRecord();
        if (site) {
          site.comments_enabled = enabled;
        }
        this.comments_enabled = enabled;
        this.commentsFlagKnown = true;
        if (!enabled) {
          this.postSlug = "";
          this.comments = [];
          this.pendingCounts = {};
          this.digestLimit = 10;
          this.expandedDigestSlug = null;
          this.deleteModalOpen = false;
          this.itemToDelete = null;
          this.resetEditors();
        } else {
          await this.ensureModerationData();
        }
      } catch (err) {
        console.error("Failed to update comments_enabled:", err);
        alert("Failed to update comments setting: " + err.message);
      } finally {
        this.savingCommentsEnabled = false;
      }
    },

    setFilter(status) {
      this.filterVisibility = status;
      this.groupPage = 1;
      this.expandedDigestSlug = null;
      this.resetEditors();
    },

    async onPostChange() {
      const params = new URLSearchParams(window.location.search);
      if (this.postSlug) {
        params.set("post_slug", this.postSlug);
      } else {
        params.delete("post_slug");
      }
      const next = params.toString();
      const url = next
        ? `${window.location.pathname}?${next}`
        : window.location.pathname;
      window.history.replaceState({}, "", url);
      this.groupPage = 1;
      this.digestLimit = 10;
      this.expandedDigestSlug = null;
      this.resetEditors();
      await this.reload();
    },

    async reload() {
      if (!this.comments_enabled) {
        this.comments = [];
        this.pendingCounts = {};
        this.loading = false;
        return;
      }
      this.loading = true;
      try {
        const data = await window.api.listAdminComments(this.postSlug || "");
        this.comments = (data && data.comments) || [];
        this.pendingCounts = (data && data.pending_counts) || {};
        if (this.groupPage > this.groupPageCount) {
          this.groupPage = this.groupPageCount;
        }
      } catch (err) {
        console.error("Failed to load comments:", err);
        this.comments = [];
        this.pendingCounts = {};
      } finally {
        this.loading = false;
      }
    },

    resetEditors() {
      this.replyingSlug = null;
      this.replyBody = "";
      this.editingSlug = null;
      this.editBody = "";
      this.editAuthor = "";
    },

    startReply(item) {
      if (!item || item.in_reply_to || !this.$store.app.hasCap("write:posts")) return;
      this.editingSlug = null;
      this.replyingSlug = item.slug;
      this.replyBody = "";
    },

    startEdit(item) {
      if (!item || !this.$store.app.hasCap("write:posts")) return;
      this.replyingSlug = null;
      this.editingSlug = item.slug;
      this.editBody = item.body || "";
      this.editAuthor = item.author_name || "";
    },

    async setVisibility(item, visibility) {
      if (!item || !this.$store.app.hasCap("write:posts") || this.savingSlug) {
        return;
      }
      const postSlug = this.itemPostSlug(item);
      if (!postSlug) return;
      this.savingSlug = item.slug;
      try {
        await window.api.setCommentVisibility(item.slug, postSlug, visibility);
        await this.reload();
      } catch (err) {
        console.error("Visibility update failed:", err);
        alert("Failed to update visibility: " + err.message);
      } finally {
        this.savingSlug = null;
      }
    },

    async submitReply(item) {
      if (!item || !this.$store.app.hasCap("write:posts") || this.savingSlug) {
        return;
      }
      const text = String(this.replyBody || "").trim();
      if (!text) return;
      const postSlug = this.itemPostSlug(item);
      if (!postSlug) return;
      this.savingSlug = item.slug;
      try {
        await window.api.createAdminComment(postSlug, text, item.slug, true);
        this.resetEditors();
        await this.reload();
      } catch (err) {
        console.error("Reply failed:", err);
        alert("Failed to reply: " + err.message);
      } finally {
        this.savingSlug = null;
      }
    },

    async submitEdit(item) {
      if (!item || !this.$store.app.hasCap("write:posts") || this.savingSlug) {
        return;
      }
      const text = String(this.editBody || "").trim();
      if (!text) return;
      const postSlug = this.itemPostSlug(item);
      if (!postSlug) return;
      this.savingSlug = item.slug;
      try {
        await window.api.patchComment(item.slug, postSlug, {
          body: text,
          author_name: String(this.editAuthor || "").trim() || "Anonymous",
        });
        this.resetEditors();
        await this.reload();
      } catch (err) {
        console.error("Edit failed:", err);
        alert("Failed to save comment: " + err.message);
      } finally {
        this.savingSlug = null;
      }
    },

    requestDelete(item) {
      if (!item || !this.$store.app.hasCap("delete:posts")) return;
      this.itemToDelete = item;
      this.deleteModalOpen = true;
    },

    async confirmDelete() {
      if (!this.itemToDelete || !this.$store.app.hasCap("delete:posts")) return;
      const postSlug = this.itemPostSlug(this.itemToDelete);
      try {
        await window.api.deleteComment(this.itemToDelete.slug, postSlug);
        this.deleteModalOpen = false;
        this.itemToDelete = null;
        await this.reload();
      } catch (err) {
        console.error("Delete failed:", err);
        alert("Failed to delete: " + err.message);
      }
    },
  }));
});
