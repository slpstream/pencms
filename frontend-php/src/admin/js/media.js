/**
 * PenCMS Media Library Controller (media.js)
 */
document.addEventListener("alpine:init", () => {
  Alpine.data("mediaLibrary", () => ({
    assets: [],
    loading: true,
    searchQuery: "",
    sortOrder: "newest",
    filterType: "all",
    filterTypes: [],
    stats: {
      totalCount: 0,
      totalSize: 0,
    },
    deleteModalOpen: false,
    assetToDelete: null,
    showModal: false,
    modalImage: null,

    async init() {
      await this.loadFilterTypes();
      await this.loadAssets();

      this.$watch(
        () => this.$store.app.activeSiteId,
        async (next, prev) => {
          if (!next || next === prev) return;
          await this.loadFilterTypes();
          await this.loadAssets();
        }
      );
    },

    openModal(asset) {
      this.modalImage = asset;
      this.showModal = true;
    },

    closeModal() {
      this.showModal = false;
      this.modalImage = null;
    },

    async loadFilterTypes() {
      try {
        const config = await window.api.getConfig();
        if (config?.taxonomy?.[config?.primary_vocabulary]?.terms) {
          this.filterTypes = config.taxonomy[config.primary_vocabulary].terms;
        }
      } catch (err) {
        console.error("Failed to load taxonomy for media filters:", err);
      }
    },

    async loadAssets() {
      this.loading = true;
      try {
        this.assets = await window.api.listAllAssets();
        this.calculateStats();
      } catch (err) {
        console.error("Failed to load assets:", err);
      } finally {
        this.loading = false;
      }
    },

    calculateStats() {
      this.stats.totalCount = this.assets.length;
      this.stats.totalSize = this.assets.reduce(
        (acc, curr) => acc + (curr.size_bytes || 0),
        0,
      );
    },

    get filteredAssets() {
      const filtered = this.assets.filter((asset) => {
        const matchesSearch =
          asset.filename
            .toLowerCase()
            .includes(this.searchQuery.toLowerCase()) ||
          asset.entity_id
            .toLowerCase()
            .includes(this.searchQuery.toLowerCase());
        const matchesType =
          this.filterType === "all" || asset.entity_type === this.filterType;
        return matchesSearch && matchesType;
      });

      if (this.sortOrder === 'newest') {
        filtered.sort((a, b) => {
          const timeA = typeof a.modified_at === 'string' ? new Date(a.modified_at).getTime() : (a.modified_at || 0) * 1000;
          const timeB = typeof b.modified_at === 'string' ? new Date(b.modified_at).getTime() : (b.modified_at || 0) * 1000;
          return timeB - timeA;
        });
      } else if (this.sortOrder === 'oldest') {
        filtered.sort((a, b) => {
          const timeA = typeof a.modified_at === 'string' ? new Date(a.modified_at).getTime() : (a.modified_at || 0) * 1000;
          const timeB = typeof b.modified_at === 'string' ? new Date(b.modified_at).getTime() : (b.modified_at || 0) * 1000;
          return timeA - timeB;
        });
      } else if (this.sortOrder === 'az') {
        filtered.sort((a, b) => a.filename.localeCompare(b.filename));
      } else if (this.sortOrder === 'za') {
        filtered.sort((a, b) => b.filename.localeCompare(a.filename));
      }

      return filtered;
    },

    formatSize(bytes) {
      if (bytes === 0) return "0 B";
      const k = 1024;
      const sizes = ["B", "KB", "MB", "GB"];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
    },

    formatDate(timestamp) {
      if (!timestamp) return "N/A";
      // Check if timestamp is ISO string (returned by openapi spec) or unix epoch
      if (typeof timestamp === 'string') {
        return new Date(timestamp).toLocaleDateString();
      }
      return new Date(timestamp * 1000).toLocaleDateString();
    },

    getEditorLink(asset) {
      const store = this.$store && this.$store.app;
      if (store && typeof store.adminPath === 'function') {
        return store.adminPath('admin-editor.php', {
          id: asset.entity_id,
          collection: asset.entity_type,
        });
      }
      return `admin-editor.php?id=${asset.entity_id}&collection=${asset.entity_type}`;
    },

    formatEntityType(type) {
      return type.replace("_", " ").toUpperCase();
    },

    deleteAsset(asset) {
      if (!this.$store.app.hasCap("delete:media")) return;
      this.assetToDelete = asset;
      this.deleteModalOpen = true;
    },

    async confirmDeleteAsset() {
      if (!this.assetToDelete || !this.$store.app.hasCap("delete:media")) return;
      const asset = this.assetToDelete;
      try {
        await window.api.deleteAsset(
          asset.entity_type,
          asset.entity_id,
          asset.filename,
        );
        this.deleteModalOpen = false;
        this.assetToDelete = null;
        await this.loadAssets();
      } catch (err) {
        console.error("Delete failed:", err);
        alert("Failed to delete asset: " + err.message);
      }
    },
  }));
});
