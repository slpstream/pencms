/**
 * PenCMS Feedback inbox — list / pull / status / delete via existing page APIs.
 */
document.addEventListener("alpine:init", () => {
  Alpine.data("feedbackInbox", () => ({
    items: [],
    loading: true,
    pulling: false,
    savingStatus: false,
    filterKind: "all",
    filterStatus: "ALL",
    selectedId: null,
    selected: null,
    editStatus: "stub",
    pullBanner: null,
    deleteModalOpen: false,
    itemToDelete: null,

    collectionOf(item) {
      return (
        (item &&
          (item.collection ||
            (item.frontmatter && item.frontmatter.category))) ||
        "general"
      );
    },

    isInboxItem(page) {
      const id = String((page && (page.id || page.slug)) || "");
      if (!id.startsWith("fb-")) return false;
      const kind = String(
        (page.frontmatter && page.frontmatter.kind) || "",
      ).toLowerCase();
      return kind === "contact" || kind === "comment";
    },

    itemStatus(item) {
      return String(
        (item && item.frontmatter && item.frontmatter.status) || "",
      ).toLowerCase();
    },

    get unreadStubCount() {
      return this.items.filter((item) => this.itemStatus(item) === "stub")
        .length;
    },

    get filteredItems() {
      const kind = this.filterKind;
      const status = this.filterStatus;
      const rows = this.items.filter((item) => {
        const k = String(
          (item.frontmatter && item.frontmatter.kind) || "",
        ).toLowerCase();
        if (kind !== "all" && k !== kind) return false;
        const st = this.itemStatus(item);
        if (status === "STUB") return st === "stub";
        if (status === "DRAFT") return st === "draft";
        return true;
      });
      rows.sort((a, b) => {
        const da =
          (a.frontmatter && a.frontmatter.received_at) || a.modified_at || "";
        const db =
          (b.frontmatter && b.frontmatter.received_at) || b.modified_at || "";
        return String(db).localeCompare(String(da));
      });
      return rows;
    },

    excerpt(item) {
      const raw =
        (item && item.content) ||
        (item && item.frontmatter && item.frontmatter.name) ||
        "";
      const text = String(raw).replace(/\s+/g, " ").trim();
      if (text.length <= 120) return text;
      return `${text.slice(0, 117)}…`;
    },

    formatDate(value) {
      const raw = value || "";
      if (!raw) return "—";
      const d = new Date(raw);
      if (Number.isNaN(d.getTime())) return String(raw);
      return d.toISOString().replace("T", " ").replace(/\.\d+Z$/, " UTC");
    },

    field(item, key) {
      return (item && item.frontmatter && item.frontmatter[key]) || "";
    },

    async autoPull() {
      if (!this.$store.app.hasCap("write:posts")) return;
      try {
        await window.api.syncFeedback();
      } catch (err) {
        console.warn("Auto pull from relay skipped or failed:", err);
      }
    },

    async init() {
      if (this.$store.app.hasCap("write:posts")) {
        await this.autoPull();
      }
      await this.reload();
      this.$watch(
        () => this.$store.app.activeSiteId,
        async (next, prev) => {
          if (!next || next === prev) return;
          this.selectedId = null;
          this.selected = null;
          if (this.$store.app.hasCap("write:posts")) {
            await this.autoPull();
          }
          await this.reload();
        },
      );
    },

    async reload() {
      this.loading = true;
      try {
        await this.$store.app.fetchPages();
        const inbox = (this.$store.app.pages || []).filter((p) =>
          this.isInboxItem(p),
        );
        const hydrated = await Promise.all(
          inbox.map(async (page) => {
            try {
              const entry = await window.api.getPage(
                page.id,
                this.collectionOf(page),
              );
              return {
                ...page,
                frontmatter: {
                  ...(page.frontmatter || {}),
                  ...(entry.frontmatter || {}),
                },
                content: entry.content || "",
                version: entry.version,
                composite: entry.composite,
                partials: entry.partials,
              };
            } catch (err) {
              console.error("Failed to load feedback body:", page.id, err);
              return { ...page, content: "" };
            }
          }),
        );
        this.items = hydrated;
        if (this.selectedId) {
          const still = hydrated.find((i) => i.id === this.selectedId);
          if (still) {
            this.selected = still;
            this.editStatus = this.itemStatus(still) || "stub";
          } else {
            this.selectedId = null;
            this.selected = null;
          }
        }
      } catch (err) {
        console.error("Failed to load feedback:", err);
        this.items = [];
      } finally {
        this.loading = false;
      }
    },

    select(item) {
      this.selectedId = item.id;
      this.selected = item;
      this.editStatus = this.itemStatus(item) || "stub";
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

    async saveStatus() {
      if (!this.selected || !this.$store.app.hasCap("write:pages")) return;
      this.savingStatus = true;
      try {
        const collection = this.collectionOf(this.selected);
        const entry = await window.api.getPage(this.selected.id, collection);
        const frontmatter = {
          ...(entry.frontmatter || {}),
          status: this.editStatus,
        };
        await window.api.updatePage(
          this.selected.id,
          {
            frontmatter,
            content: entry.content || "",
            composite: entry.composite || false,
            partials: entry.partials || {},
            expected_version: entry.version || undefined,
          },
          null,
          collection,
        );
        await this.reload();
      } catch (err) {
        console.error("Status update failed:", err);
        alert("Failed to update status: " + err.message);
      } finally {
        this.savingStatus = false;
      }
    },

    requestDelete(item) {
      if (!item || !this.$store.app.hasCap("delete:pages")) return;
      this.itemToDelete = item;
      this.deleteModalOpen = true;
    },

    async confirmDelete() {
      if (!this.itemToDelete || !this.$store.app.hasCap("delete:pages")) return;
      try {
        const collection = this.collectionOf(this.itemToDelete);
        await window.api.deletePage(this.itemToDelete.id, collection);
        if (this.selectedId === this.itemToDelete.id) {
          this.selectedId = null;
          this.selected = null;
        }
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
