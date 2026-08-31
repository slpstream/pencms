/**
 * PenCMS Site Navigation Controller (settings-navigation.js)
 */
document.addEventListener("alpine:init", () => {
  Alpine.data("navigationSettings", () => ({
    saving: false,
    manualSaving: false,
    clearingAll: false,
    clearAllModalOpen: false,
    loading: false,
    saveStatus: "saved",
    get saveStatusText() {
      if (this.saveStatus === "saving") return "Saving...";
      if (this.saveStatus === "unsaved") return "Unsaved";
      return "Saved";
    },
    serverSaveTimer: null,
    activeTab: "primary",
    toasts: [],
    toastCounter: 0,

    // ── UI State (scaffold layout dragging) ─────────────────────
    isDraggingLeftColumn:  false,
    isDraggingRightColumn: false,

    workspacePrefs: {
      sidebarWidth:             32,
      rightColumnWidth:         25,
      leftColumnCollapsed:      false,
      rightColumnCollapsed:     false,
      secondaryRailCollapsed:   true,
      aiAssistantCollapsed:     false,
      addItemCardCollapsed:     false,
      advancedSettingsCardCollapsed: true,
      menuPreviewCardCollapsed: false,
      menuPreviewCollapsed:     false,
      pageTreeCardCollapsed:    false,
    },

    // Slot-specific identifiers (mocked, persisted to localStorage)
    slotClasses: {
      primary: "",
      secondary: "",
      footer: "",
    },

    menus: {
      primary: [],
      secondary: [],
      footer: [],
    },
    originalMenusJson: "",
    pages: [],

    // Add Item panel state
    showAddPanel: false,
    // The active tab is one of:
    //   "page"   — static pages (frontmatter.page === true)
    //   "post"   — regular articles
    //   "custom" — arbitrary URL
    //   "label"  — non-link separator
    // "page" and "post" both serialize to the backend's discriminated
    // `content` target type with content_type=page|post (see addItem()).
    // Future system entries (archives, categories, home) will join this
    // list as additional tabs without changing the backend union.
    addType: "page",
    newItem: {
      label: "",
      content_slug: "",
      content_type: "page",
      url: "",
      open_in_new_tab: false,
      parent_id: "",
    },
    searchQuery: "",
    showOnlyPublished: true,
    selectedVocabKey: "",
    customTermInput: "",
    customTermDrawerOpen: false,
    // Public static paths (site root). Preview PHP routes may differ;
    // ThemeEngine rebuilds hrefs at render time. Keep these urls in sync with
    // ThemeEngine system targets (home → index; blog → /category/ archives).
    systemPages: [
      { id: "home", title: "Home Page", url: "/" },
      // All-posts archive (category.php with no term; static: category/index.html)
      { id: "blog", title: "Archives", url: "/category/" },
      { id: "search", title: "Search Page", url: "/search/" },
      { id: "rss", title: "RSS Feed", url: "/feed.xml" },
    ],

    // Inline Edit State
    editingItemId: null,
    editingItemData: null,

    // Page Tree state
    taxonomy: null,
    pageTreeLoaded: false,

    async init() {
      this.loading = true;

      // Toast event bus
      window.addEventListener('pen:toast', (e) => {
        if (e.detail && e.detail.message) {
          this.showToast(e.detail.message, e.detail.type || 'success');
        }
      });

      // Load persisted prefs
      try {
        const saved = localStorage.getItem('pen_editor_workspace_prefs');
        if (saved) {
          this.workspacePrefs = {
            ...this.workspacePrefs,
            ...JSON.parse(saved),
          };
        }
        this.saveWorkspacePrefs();
      } catch (e) { /* ignore */ }

      // Load persisted slot classes
      try {
        const savedClasses = localStorage.getItem('pen_menu_slot_classes');
        if (savedClasses) {
          this.slotClasses = {
            ...this.slotClasses,
            ...JSON.parse(savedClasses),
          };
        }
      } catch (e) { /* ignore */ }

      try {
        await this.fetchMenus();
        await this.fetchPages();
        await this.fetchTaxonomy();
        this.pageTreeLoaded = true;

        // Refetch when Content site switcher changes
        this.$watch(
          () => this.$store.app.activeSiteId,
          async (next, prev) => {
            if (!next || next === prev) return;
            try {
              await this.fetchMenus();
              await this.fetchPages();
              await this.fetchTaxonomy();
              this.$nextTick(() => {
                this.initSortable("primary");
                this.initSortable("secondary");
                this.initSortable("footer");
              });
            } catch (err) {
              console.error("Failed to reload menus for site change:", err);
              this.showToast("Failed to reload menus for site", "error");
            }
          }
        );

        // Setup beforeunload prompt
        window.addEventListener("beforeunload", (e) => {
          if (this.hasChanges() || this.saveStatus === "unsaved") {
            e.preventDefault();
            e.returnValue = "";
          }
        });

        // Track dirty state + schedule debounced server autosave
        this.$watch(
          "menus",
          () => {
            if (this.loading || this.saving) return;
            if (this.hasChanges()) {
              if (this.saveStatus !== "saving") {
                this.saveStatus = "unsaved";
              }
              this.scheduleServerSave();
            } else {
              clearTimeout(this.serverSaveTimer);
              if (this.saveStatus !== "saving") {
                this.saveStatus = "saved";
              }
            }
          },
          { deep: true }
        );

        // Initialize Sortable on slots
        this.$nextTick(() => {
          this.initSortable("primary");
          this.initSortable("secondary");
          this.initSortable("footer");
        });
      } catch (err) {
        console.error("Initialization error:", err);
        this.showToast("Failed to load navigation configuration", "error");
      } finally {
        this.loading = false;
      }
    },

    scheduleServerSave() {
      clearTimeout(this.serverSaveTimer);
      this.serverSaveTimer = setTimeout(() => {
        if (!this.saving && this.hasChanges()) {
          this.saveChanges({ silent: true });
        }
      }, 30000);
    },

    // Rebuild a contiguous parent→children flat list for Structure DnD.
    // `order` is sibling-scoped; a global sort interleaves children under the
    // wrong visual parents. Structure indents by adjacency, so each parent
    // must be immediately followed by its own children.
    flattenMenuTree(items) {
      const byId = new Map(items.map((item) => [item.id, item]));
      const roots = items
        .filter((item) => !item.parent_id)
        .slice()
        .sort((a, b) => a.order - b.order);
      const placed = new Set();
      const flat = [];

      for (const root of roots) {
        flat.push(root);
        placed.add(root.id);
        const children = items
          .filter((item) => item.parent_id === root.id)
          .slice()
          .sort((a, b) => a.order - b.order);
        for (const child of children) {
          flat.push(child);
          placed.add(child.id);
        }
      }

      // Orphans (missing parent) stay visible as top-level so nothing disappears.
      const orphans = items
        .filter((item) => !placed.has(item.id))
        .slice()
        .sort((a, b) => a.order - b.order);
      for (const orphan of orphans) {
        if (orphan.parent_id && !byId.has(orphan.parent_id)) {
          orphan.parent_id = null;
        }
        flat.push(orphan);
      }

      return flat;
    },

    async fetchMenus() {
      try {
        const data = await window.api.getMenus();
        // Flatten nested items from server structure back to a flat list representation for the UI.
        // The server returns a structured schema matching MenuItem, but we read it into a flat list
        // with order and parent_id attributes to match our UI drag-and-drop layout.
        const flatMenus = { primary: [], secondary: [], footer: [] };
        
        for (const slot of ["primary", "secondary", "footer"]) {
          const items = (data[slot] || []).map((item) =>
            window.PenMenuItemShape.fromApiItem(item)
          );

          flatMenus[slot] = this.flattenMenuTree(items);
        }

        this.originalMenusJson = JSON.stringify(flatMenus);
        this.menus = flatMenus;
      } catch (e) {
        console.error("Failed to fetch menus:", e);
        this.showToast("Could not fetch menu data", "error");
      }
    },

    async fetchPages() {
      try {
        this.pages = await window.api.listPages();
      } catch (e) {
        console.error("Failed to fetch pages:", e);
      }
    },

    async fetchTaxonomy() {
      try {
        const response = await window.api.getTaxonomy();
        this.taxonomy = response;
        if (response && response.parsed && response.parsed.primary_vocabulary) {
          this.selectedVocabKey = response.parsed.primary_vocabulary;
        } else if (response && response.raw && response.raw.vocabularies) {
          this.selectedVocabKey = Object.keys(response.raw.vocabularies)[0] || "";
        }
      } catch (e) {
        console.error("Failed to fetch taxonomy:", e);
      }
    },

    parseHierarchicalTerms(rawTerms) {
      const root = [];
      const nodeMap = new Map();
      const allPaths = new Set();
      
      for (const term of rawTerms) {
        const parts = term.split(" / ");
        let currentPath = "";
        for (let i = 0; i < parts.length; i++) {
          currentPath = currentPath ? `${currentPath} / ${parts[i]}` : parts[i];
          allPaths.add(currentPath);
        }
      }
      
      const sortedPaths = Array.from(allPaths).sort((a, b) => {
        const depthA = a.split(" / ").length;
        const depthB = b.split(" / ").length;
        if (depthA !== depthB) return depthA - depthB;
        
        const getMinIndex = (path) => {
          let idx = rawTerms.indexOf(path);
          if (idx !== -1) return idx;
          const prefix = path + " / ";
          idx = rawTerms.findIndex(t => t.startsWith(prefix));
          return idx !== -1 ? idx : 999999;
        };
        return getMinIndex(a) - getMinIndex(b);
      });
      
      for (const path of sortedPaths) {
        const parts = path.split(" / ");
        const name = parts[parts.length - 1];
        const isExplicit = rawTerms.includes(path);
        
        const node = {
          name,
          fullPath: path,
          isExplicit,
          children: []
        };
        
        nodeMap.set(path, node);
        
        if (parts.length === 1) {
          root.push(node);
        } else {
          const parentPath = parts.slice(0, -1).join(" / ");
          const parentNode = nodeMap.get(parentPath);
          if (parentNode) {
            parentNode.children.push(node);
          } else {
            root.push(node);
          }
        }
      }
      
      return root;
    },

    formatTreeItemStatus(status) {
      const key = (status || "published").trim().toLowerCase();
      const labels = {
        published: "Published",
        draft: "Draft",
        stub: "Stub",
        unpublished: "Unpublished",
      };
      return labels[key] || key.charAt(0).toUpperCase() + key.slice(1);
    },

    /** True when status is published and publish_at is null or in the past. */
    isLivePublished(fm) {
      if ((fm?.status || "").toLowerCase() !== "published") return false;
      if (!fm.publish_at) return true;
      const d = new Date(fm.publish_at);
      return !Number.isNaN(d.getTime()) && d.getTime() <= Date.now();
    },

    buildTreeItemTooltip(fm, isPost = false) {
      const parts = [];
      const heroTitle = (fm.hero_title || "").trim();
      const category = (fm.category || fm.type || "").trim();
      const status = this.formatTreeItemStatus(fm.status);

      if (heroTitle) {
        parts.push(isPost && category ? `${heroTitle} (${category})` : heroTitle);
      } else if (isPost && category) {
        parts.push(category);
      }

      if (status) {
        parts.push(status);
      }

      return parts.join(" · ");
    },

    mapPageToTreeItem(p, isPost = false) {
      const fm = p.frontmatter || {};
      return {
        id: p.id,
        label: fm.name || fm.title || p.title || p.id,
        tooltip: this.buildTreeItemTooltip(fm, isPost),
        collection: p.collection,
      };
    },

    treePages() {
      if (!this.pages) return [];
      return this.pages
        .filter(p => {
          const isPage = !!(p.frontmatter && (p.frontmatter.page === true || p.frontmatter.page === "true"));
          if (!isPage) return false;
          if (this.showOnlyPublished) {
            return this.isLivePublished(p.frontmatter || {});
          }
          return true;
        })
        .map(p => this.mapPageToTreeItem(p, false))
        .sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: 'base' }));
    },

    treePosts() {
      if (!this.pages) return [];
      return this.pages
        .filter(p => {
          const isPage = !!(p.frontmatter && (p.frontmatter.page === true || p.frontmatter.page === "true"));
          if (isPage) return false;
          if (this.showOnlyPublished) {
            return this.isLivePublished(p.frontmatter || {});
          }
          return true;
        })
        .map(p => this.mapPageToTreeItem(p, true))
        .sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: 'base' }));
    },

    treePrimaryVocabulary() {
      if (!this.taxonomy || !this.taxonomy.parsed || !this.taxonomy.raw) return null;
      const primaryKey = this.taxonomy.parsed.primary_vocabulary;
      if (!primaryKey) return null;
      const vocab = this.taxonomy.raw.vocabularies[primaryKey];
      if (!vocab) return null;
      
      const label = vocab.label || (primaryKey.charAt(0).toUpperCase() + primaryKey.slice(1));
      const type = vocab.type || "flat";
      const controlled = vocab.controlled !== false;
      const rawTerms = vocab.terms || [];
      
      let terms = [];
      if (type === "hierarchical") {
        terms = this.parseHierarchicalTerms(rawTerms);
      } else {
        terms = [...rawTerms];
      }
      
      return {
        key: primaryKey,
        label,
        type,
        controlled,
        terms
      };
    },

    /** Add Item tab + site-map branch label for taxonomy (primary vocab label, else "Taxonomy"). */
    taxonomyTabLabel() {
      const primary = this.treePrimaryVocabulary();
      return (primary && primary.label) || "Taxonomy";
    },

    treeVocabularies() {
      if (!this.taxonomy || !this.taxonomy.raw || !this.taxonomy.raw.vocabularies) return [];
      const primaryKey = this.taxonomy.parsed && this.taxonomy.parsed.primary_vocabulary;
      const vocabs = [];
      for (const [key, vocab] of Object.entries(this.taxonomy.raw.vocabularies)) {
        if (key === primaryKey) continue;
        
        const label = vocab.label || (key.charAt(0).toUpperCase() + key.slice(1));
        const type = vocab.type || "flat";
        const controlled = vocab.controlled !== false;
        const rawTerms = vocab.terms || [];
        
        let terms = [];
        if (type === "hierarchical") {
          terms = this.parseHierarchicalTerms(rawTerms);
        } else {
          // Flat terms - preserve original order
          terms = [...rawTerms];
        }
        
        vocabs.push({
          key,
          label,
          type,
          controlled,
          terms
        });
      }
      return vocabs;
    },

    allVocabularies() {
      const list = [];
      const primary = this.treePrimaryVocabulary();
      if (primary) {
        list.push(primary);
      }
      list.push(...this.treeVocabularies());
      return list;
    },

    /**
     * Typed membership keys for every item across primary/secondary/footer.
     * Keys: content:{id} | taxonomy:{vocab}/{termPath} | system:{id} | custom:{url}
     * ✓ means in any menu; remove acts on activeTab only (v3).
     */
    itemMembershipKey(item) {
      if (!item) return null;
      if (item.target_type === "content" && item.content_slug) {
        return `content:${item.content_slug}`;
      }
      if (item.target_type === "taxonomy" && item.content_slug) {
        return `taxonomy:${item.content_slug}`;
      }
      if (item.target_type === "system" && item.content_slug) {
        return `system:${item.content_slug}`;
      }
      if (item.target_type === "custom" && item.url) {
        return `custom:${item.url}`;
      }
      return null;
    },

    menuMembershipKeys() {
      const keys = new Set();
      for (const slot of ["primary", "secondary", "footer"]) {
        for (const item of this.menus[slot] || []) {
          const key = this.itemMembershipKey(item);
          if (key) keys.add(key);
        }
      }
      return keys;
    },

    isContentInMenus(contentId) {
      if (!contentId) return false;
      return this.menuMembershipKeys().has(`content:${contentId}`);
    },

    isTaxonomyTermInMenus(vocabKey, termPath) {
      if (!vocabKey || !termPath) return false;
      return this.menuMembershipKeys().has(`taxonomy:${vocabKey}/${termPath}`);
    },

    isSystemInMenus(systemId) {
      if (!systemId) return false;
      return this.menuMembershipKeys().has(`system:${systemId}`);
    },

    isCustomUrlInMenus(url) {
      if (!url) return false;
      return this.menuMembershipKeys().has(`custom:${url}`);
    },

    isInActiveTab(key) {
      if (!key) return false;
      return (this.menus[this.activeTab] || []).some(
        (item) => this.itemMembershipKey(item) === key
      );
    },

    findInActiveTab(key) {
      if (!key) return [];
      return (this.menus[this.activeTab] || []).filter(
        (item) => this.itemMembershipKey(item) === key
      );
    },

    removeTreeItemFromActiveTab(key) {
      const matches = this.findInActiveTab(key);
      if (!matches.length) {
        this.showToast("Not in the active menu — use + to add here, or switch tabs to remove it", "error");
        return;
      }
      for (const item of matches) {
        if ((this.menus[this.activeTab] || []).some((x) => x.id === item.id)) {
          this.deleteItem(this.activeTab, item.id);
        }
      }
    },

    /**
     * Add a Site Map entry to activeTab. Payload mirrors addItem().
     * No-op with toast if already present in the active slot.
     */
    addTreeItem(fields) {
      const key = this.itemMembershipKey(fields);
      if (!key) return;
      if (this.isInActiveTab(key)) {
        this.showToast("Already in the active menu", "error");
        return;
      }
      const tempId = `temp-${Date.now()}`;
      const item = {
        id: tempId,
        label: fields.label,
        parent_id: null,
        order: this.menus[this.activeTab].length,
        open_in_new_tab: false,
        target_type: fields.target_type,
        content_slug: fields.content_slug,
        content_type: fields.content_type,
        url: fields.url || "",
      };
      this.menus[this.activeTab].push(item);
      this.showToast("Item added locally");
    },

    addTreeContent(p, contentType) {
      if (!p || !p.id) return;
      this.addTreeItem({
        label: p.label || p.frontmatter?.title || p.title || p.id,
        target_type: "content",
        content_slug: p.id,
        content_type: contentType === "post" ? "post" : "page",
        url: "",
      });
    },

    addTreeTaxonomy(vocabKey, termPath, label) {
      if (!vocabKey || !termPath) return;
      const leaf = String(termPath).split(" / ").pop();
      const slug = this.termToCategorySlug(`${vocabKey}/${termPath}`);
      this.addTreeItem({
        label: label || leaf,
        target_type: "taxonomy",
        content_slug: `${vocabKey}/${termPath}`,
        content_type: "categories",
        url: slug ? `/category/${slug}/` : "",
      });
    },

    addTreeSystem(systemId) {
      const sys = (this.systemPages || []).find((x) => x.id === systemId);
      if (!sys) return;
      this.addTreeItem({
        label: sys.title,
        target_type: "system",
        content_slug: sys.id,
        content_type: "system",
        url: sys.url || "",
      });
    },

    getSelectedVocab() {
      if (!this.taxonomy || !this.taxonomy.raw || !this.taxonomy.raw.vocabularies || !this.selectedVocabKey) {
        return null;
      }
      return this.taxonomy.raw.vocabularies[this.selectedVocabKey] || null;
    },

    getSelectedVocabTerms() {
      const vocab = this.getSelectedVocab();
      return vocab ? (vocab.terms || []) : [];
    },

    isSelectedVocabControlled() {
      const vocab = this.getSelectedVocab();
      if (!vocab) return true;
      return vocab.controlled !== false;
    },

    isSelectedVocabUncontrolled() {
      return !this.isSelectedVocabControlled();
    },

    isSelectedVocabHierarchical() {
      const vocab = this.getSelectedVocab();
      return !!(vocab && vocab.type === "hierarchical");
    },

    onSelectedVocabChange() {
      this.customTermInput = "";
      this.customTermDrawerOpen = false;
      if (this.newItem.content_type === "taxonomy" && this.newItem.content_slug) {
        const prefix = `${this.selectedVocabKey}/`;
        if (!this.newItem.content_slug.startsWith(prefix)) {
          this.newItem.content_slug = "";
          this.newItem.url = "";
        }
      }
    },

    applyCustomTaxonomyTerm() {
      const term = (this.customTermInput || "").trim();
      if (!term || !this.selectedVocabKey) return;
      this.selectTaxonomyTerm(term);
      this.customTermInput = "";
    },

    selectTaxonomyTerm(term) {
      this.newItem.content_slug = `${this.selectedVocabKey}/${term}`;
      this.newItem.content_type = "taxonomy";
      const leaf = term.split(" / ").pop();
      const slug = this.termToCategorySlug(`${this.selectedVocabKey}/${term}`);
      this.newItem.url = slug ? `/category/${slug}/` : "";
      if (!this.newItem.label) {
        this.newItem.label = leaf;
      }
    },

    selectSystemPage(sys) {
      this.newItem.content_slug = sys.id;
      this.newItem.content_type = "system";
      this.newItem.url = sys.url;
      if (!this.newItem.label) {
        this.newItem.label = sys.title;
      }
    },

    initSortable(slot) {
      const el = document.getElementById(`menu-list-${slot}`);
      if (!el) return;

      Sortable.create(el, {
        handle: ".drag-handle",
        animation: 150,
        ghostClass: "bg-rust-wash",
        onEnd: () => {
          // Reorder menus[slot] based on DOM order
          const newOrderIds = Array.from(el.querySelectorAll("[data-id]")).map(
            (item) => item.getAttribute("data-id")
          );

          const itemsMap = {};
          this.menus[slot].forEach((item) => {
            itemsMap[item.id] = item;
          });

          const reordered = newOrderIds
            .map((id, index) => {
              const item = itemsMap[id];
              if (item) {
                item.order = index;
              }
              return item;
            })
            .filter(Boolean);

          this.menus[slot] = reordered;
          this.syncParentIds(slot);
        },
      });
    },

    syncParentIds(slot) {
      let lastParentId = null;
      this.menus[slot].forEach((item) => {
        if (item.parent_id !== null) {
          item.parent_id = lastParentId;
        } else {
          lastParentId = item.id;
        }
      });
    },

    hasChanges() {
      return JSON.stringify(this.menus) !== this.originalMenusJson;
    },

    dirtySlots() {
      let original;
      try {
        original = JSON.parse(this.originalMenusJson || "{}");
      } catch (e) {
        original = { primary: [], secondary: [], footer: [] };
      }
      return ["primary", "secondary", "footer"].filter(
        (slot) =>
          JSON.stringify(this.menus[slot] || []) !==
          JSON.stringify(original[slot] || [])
      );
    },

    // Children of a given top-level item in the active slot, sorted by order.
    childrenOf(parentId) {
      const items = this.menus[this.activeTab] || [];
      return items
        .filter((x) => x.parent_id === parentId)
        .slice()
        .sort((a, b) => a.order - b.order);
    },

    showToast(message, type = "success") {
      const id = ++this.toastCounter;
      this.toasts.push({ id, message, type });
      setTimeout(() => {
        this.toasts = this.toasts.filter((t) => t.id !== id);
      }, 4000);
    },

    filteredPages() {
      const query = this.searchQuery.toLowerCase().trim();
      // The "Page" and "Post" tabs draw from the same `pages` cache but
      // filter by the entry's frontmatter `page` flag — `page: true` is the
      // single source of truth that flips an entry into the Pages bucket
      // (see `PageFrontmatter.page` in models/page.py and admin-pages.php's
      // `filteredPages` getter). Future system entries (archives,
      // categories, index/home) will be filtered in here as well, keyed by
      // a separate collection or marker field so they don't collide with
      // the page/post dichotomy.
      const wantPage = this.addType === "page";
      const matchesKind = (p) => {
        const isPage = !!(p.frontmatter && (p.frontmatter.page === true || p.frontmatter.page === "true"));
        return wantPage ? isPage : !isPage;
      };
      let source = this.pages.filter(matchesKind);
      if (this.showOnlyPublished) {
        source = source.filter((p) => this.isLivePublished(p.frontmatter || {}));
      }
      if (!query) return source;
      return source.filter(
        (p) =>
          (p.frontmatter.title || p.title || "").toLowerCase().includes(query) ||
          (p.id || "").toLowerCase().includes(query)
      );
    },

    getItemTargetLabel(item) {
      if (item.target_type !== "content") {
        return item.target_type;
      }
      const p = this.pages.find((x) => x.id === item.content_slug);
      if (p) {
        const isPage = !!(p.frontmatter && (p.frontmatter.page === true || p.frontmatter.page === "true"));
        return isPage ? "page" : "post";
      }
      return item.content_type || "page";
    },

    /**
     * Must stay in sync with TaxonomySlug::termToCategorySlug (PHP).
     */
    termToCategorySlug(term) {
      let leaf = String(term || "").trim();
      const m = leaf.match(/^([a-z0-9_]+)\/(.+)$/i);
      if (m) leaf = m[2];
      const sep = leaf.lastIndexOf(" / ");
      if (sep !== -1) leaf = leaf.slice(sep + 3);
      return leaf.trim().toLowerCase().replace(/ /g, "-");
    },

    /**
     * Absolute-from-root public path as published by the static site
     * generator (trailing slash for HTML dirs). Not the PHP preview URL.
     */
    getItemPublicPath(item) {
      if (!item) return "—";
      switch (item.target_type) {
        case "content":
          return item.content_slug ? `/${item.content_slug}/` : "—";
        case "taxonomy": {
          const slug = this.termToCategorySlug(item.content_slug);
          return slug ? `/category/${slug}/` : "—";
        }
        case "system": {
          const id = item.content_slug;
          if (id === "home") return "/";
          if (id === "blog") return "/category/";
          if (id === "search") return "/search/";
          if (id === "rss") return "/feed.xml";
          const sys = (this.systemPages || []).find((x) => x.id === id);
          return (sys && sys.url) || item.url || "—";
        }
        case "custom":
          return item.url || "—";
        case "label":
        default:
          return "—";
      }
    },

    selectPage(p) {
      this.newItem.content_slug = p.id;
      // The active tab (Page vs Post) is the user's stated intent for the
      // target type, so we defer to it rather than to the entry's own
      // collection name. This keeps page:true and a posts collection
      // consistent: if the user picked the "Page" tab we record
      // content_type=page, otherwise we record content_type=post.
      this.newItem.content_type = this.addType === "page" ? "page" : "post";
      if (!this.newItem.label) {
        this.newItem.label = p.frontmatter.title || p.title;
      }
    },

    // --- CRUD Actions ---

    addItem() {
      if (!this.newItem.label.trim()) {
        this.showToast("Label is required", "error");
        return;
      }

      const isContent = this.addType === "page" || this.addType === "post";
      const isSelectionRequired = isContent || this.addType === "categories" || this.addType === "system";
      if (isSelectionRequired && !this.newItem.content_slug) {
        this.showToast("Please select an item", "error");
        return;
      }

      if (this.addType === "custom" && !this.newItem.url.trim()) {
        this.showToast("URL is required", "error");
        return;
      }

      let targetType = this.addType;
      if (isContent) {
        targetType = "content";
      } else if (this.addType === "categories") {
        targetType = "taxonomy";
      }

      const slot = this.activeTab;
      const parentId = this.newItem.parent_id || null;
      const validParent =
        parentId &&
        this.menus[slot].some((x) => x.id === parentId && !x.parent_id);

      const tempId = `temp-${Date.now()}`;
      const item = {
        id: tempId,
        label: this.newItem.label,
        parent_id: validParent ? parentId : null,
        order: this.menus[slot].length,
        open_in_new_tab: this.newItem.open_in_new_tab,
        target_type: targetType,
        content_slug: this.newItem.content_slug,
        content_type: isContent ? (this.addType === "page" ? "page" : "post") : this.addType,
        url: this.newItem.url,
      };

      this.insertMenuItem(slot, item, validParent ? parentId : null);

      // Reset form
      this.newItem = {
        label: "",
        content_slug: "",
        content_type: "page",
        url: "",
        open_in_new_tab: false,
        parent_id: "",
      };
      this.searchQuery = "";
      this.showAddPanel = false;
      this.showToast("Item added locally");
    },

    /**
     * Insert a new menu item into the flat list.
     * When parentId is set, places the item after the parent's last child
     * (or immediately after the parent if it has none). Otherwise appends.
     */
    insertMenuItem(slot, item, parentId) {
      const arr = [...this.menus[slot]];

      if (!parentId) {
        item.parent_id = null;
        item.order = arr.length;
        arr.push(item);
      } else {
        const parentIdx = arr.findIndex((x) => x.id === parentId && !x.parent_id);
        if (parentIdx === -1) {
          item.parent_id = null;
          item.order = arr.length;
          arr.push(item);
        } else {
          item.parent_id = parentId;
          let insertAt = parentIdx + 1;
          while (insertAt < arr.length && arr[insertAt].parent_id === parentId) {
            insertAt++;
          }
          arr.splice(insertAt, 0, item);
        }
      }

      arr.forEach((x, idx) => {
        x.order = idx;
      });
      this.menus[slot] = arr;
    },

    deleteItem(slot, itemId) {
      // Find children of this item
      const hasChildren = this.menus[slot].some((x) => x.parent_id === itemId);
      if (hasChildren) {
        if (!confirm("Deleting this parent item will also delete all of its children. Proceed?")) {
          return;
        }
      }

      // Filter out item and its children
      this.menus[slot] = this.menus[slot].filter(
        (x) => x.id !== itemId && x.parent_id !== itemId
      );
      this.showToast("Item removed locally");
    },

    startEdit(item) {
      this.editingItemData = JSON.parse(JSON.stringify(item));
      // The edit Type dropdown mirrors Add Item (Page / Post), while the
      // backend still stores both as target_type=content + content_type.
      if (this.editingItemData.target_type === "content") {
        this.editingItemData.target_type =
          this.getItemTargetLabel(item) === "post" ? "post" : "page";
      }
      this.editingItemId = item.id;
    },

    cancelEdit() {
      // Clear id first so x-if tears down the form; defer nulling data so
      // nested bindings do not evaluate against null in the same flush.
      this.editingItemId = null;
      this.$nextTick(() => {
        this.editingItemData = null;
      });
    },

    editFilteredPages() {
      if (!this.editingItemData) return [];
      const wantPage = this.editingItemData.target_type === "page";
      return this.pages.filter((p) => {
        const isPage = !!(p.frontmatter && (p.frontmatter.page === true || p.frontmatter.page === "true"));
        return wantPage ? isPage : !isPage;
      });
    },

    onEditTargetTypeChange() {
      if (!this.editingItemData) return;
      this.editingItemData.content_slug = "";
      this.editingItemData.url = "";
    },

    saveEdit(slot, itemId) {
      if (!this.editingItemData) return;
      if (!this.editingItemData.label.trim()) {
        this.showToast("Label is required", "error");
        return;
      }
      if (this.editingItemData.target_type === "custom" && !this.editingItemData.url.trim()) {
        this.showToast("URL is required", "error");
        return;
      }

      const isContent =
        this.editingItemData.target_type === "page" ||
        this.editingItemData.target_type === "post";
      if (isContent && !this.editingItemData.content_slug) {
        this.showToast("Please select an item", "error");
        return;
      }

      // Snapshot so we never mutate live edit bindings (page/post → content)
      // while the form is still mounted — that was throwing Alpine expression errors.
      const saved = JSON.parse(JSON.stringify(this.editingItemData));
      if (isContent) {
        saved.content_type = saved.target_type;
        saved.target_type = "content";
      }

      const idx = this.menus[slot].findIndex((x) => x.id === itemId);
      if (idx !== -1) {
        this.menus[slot][idx] = saved;
      }

      this.editingItemId = null;
      this.$nextTick(() => {
        this.editingItemData = null;
      });
      this.showToast("Item updated locally");
    },

    // --- Nesting (Indent / Outdent) ---

    canIndent(slot, itemId) {
      const idx = this.menus[slot].findIndex((x) => x.id === itemId);
      if (idx <= 0) return false; // first item can't be child
      const item = this.menus[slot][idx];
      if (item.parent_id) return false; // already child

      // Find preceding top-level item
      for (let i = idx - 1; i >= 0; i--) {
        if (!this.menus[slot][i].parent_id) {
          return true;
        }
      }
      return false;
    },

    indentItem(slot, itemId) {
      const idx = this.menus[slot].findIndex((x) => x.id === itemId);
      if (idx <= 0) return;
      const item = this.menus[slot][idx];

      // Find preceding top-level item
      let parent = null;
      for (let i = idx - 1; i >= 0; i--) {
        if (!this.menus[slot][i].parent_id) {
          parent = this.menus[slot][i];
          break;
        }
      }

      if (parent) {
        item.parent_id = parent.id;
        this.showToast("Nested item");
      }
    },

    canOutdent(slot, itemId) {
      const item = this.menus[slot].find((x) => x.id === itemId);
      return item && item.parent_id !== null;
    },

    outdentItem(slot, itemId) {
      const item = this.menus[slot].find((x) => x.id === itemId);
      if (item) {
        item.parent_id = null;
        this.showToast("Outdented item");
      }
    },

    moveItem(slot, index, direction) {
      const newIdx = index + direction;
      if (newIdx < 0 || newIdx >= this.menus[slot].length) return;

      const arr = [...this.menus[slot]];
      const temp = arr[index];
      arr[index] = arr[newIdx];
      arr[newIdx] = temp;

      arr.forEach((item, idx) => {
        item.order = idx;
      });

      this.menus[slot] = arr;
      this.syncParentIds(slot);
      this.showToast("Item reordered");
    },

    // --- Save changes to Backend REST API ---

    discardChanges() {
      if (confirm("Are you sure you want to discard all unsaved changes?")) {
        clearTimeout(this.serverSaveTimer);
        this.loading = true;
        this.menus = JSON.parse(this.originalMenusJson);
        this.saveStatus = "saved";
        this.$nextTick(() => {
          this.loading = false;
        });
        this.showToast("Changes discarded");
      }
    },

    async confirmClearAll() {
      if (this.clearingAll) return;
      this.clearingAll = true;

      try {
        clearTimeout(this.serverSaveTimer);
        await Promise.all([
          window.api.clearMenuSlot("primary"),
          window.api.clearMenuSlot("secondary"),
          window.api.clearMenuSlot("footer"),
        ]);
        this.clearAllModalOpen = false;
        await this.fetchMenus();
        this.saveStatus = "saved";
        this.showToast("All menus cleared");
      } catch (err) {
        console.error(err);
        this.showToast(err.message || "Failed to clear menus", "error");
      } finally {
        this.clearingAll = false;
      }
    },

    buildItemPayload(slot, item, parentId) {
      const payload = window.PenMenuItemShape.toApiItem(slot, item, parentId);
      // Save path should not send client id on create/update body
      delete payload.id;
      delete payload.order;
      return payload;
    },

    async saveSlot(slot) {
      const original = JSON.parse(this.originalMenusJson || "{}");
      const originalItems = original[slot] || [];
      const currentItems = this.menus[slot] || [];

      // 1. Delete items
      const toDelete = originalItems.filter(
        (o) => !currentItems.some((c) => c.id === o.id)
      );
      for (const item of toDelete) {
        await window.api.deleteMenuItem(slot, item.id);
      }

      // 2. Setup ID Mapping for client-side temp IDs
      const tempIdMap = {};

      const topLevelItems = currentItems.filter((x) => !x.parent_id);
      const childItems = currentItems.filter((x) => x.parent_id);

      for (const item of topLevelItems) {
        const isTemp = String(item.id).startsWith("temp-");
        const payload = this.buildItemPayload(slot, item, null);

        if (isTemp) {
          const res = await window.api.createMenuItem(slot, payload);
          tempIdMap[item.id] = res.id;
          item.id = res.id;
        } else {
          await window.api.updateMenuItem(slot, item.id, payload);
        }
      }

      for (const item of childItems) {
        const isTemp = String(item.id).startsWith("temp-");

        let resolvedParentId = item.parent_id;
        if (tempIdMap[resolvedParentId]) {
          resolvedParentId = tempIdMap[resolvedParentId];
        }

        const payload = this.buildItemPayload(slot, item, resolvedParentId);

        if (isTemp) {
          const res = await window.api.createMenuItem(slot, payload);
          tempIdMap[item.id] = res.id;
          item.id = res.id;
          item.parent_id = resolvedParentId;
        } else {
          item.parent_id = resolvedParentId;
          await window.api.updateMenuItem(slot, item.id, payload);
        }
      }

      // 3. Finalize order
      const reorders = currentItems.map((item, index) => {
        let pId = item.parent_id;
        if (tempIdMap[pId]) {
          pId = tempIdMap[pId];
        }
        return {
          id: item.id,
          parent_id: pId,
          order: index,
        };
      });

      await window.api.reorderMenuItems(slot, reorders);
    },

    async saveChanges(options = {}) {
      if (this.saving) return;
      if (!this.hasChanges()) {
        this.saveStatus = "saved";
        return;
      }

      this.saving = true;
      if (!options.silent) {
        this.manualSaving = true;
      }
      this.saveStatus = "saving";
      clearTimeout(this.serverSaveTimer);

      try {
        const slots = this.dirtySlots();
        for (const slot of slots) {
          await this.saveSlot(slot);
        }

        if (!options.silent) {
          this.showToast("Navigation settings saved successfully");
        }

        // Reload menus to get fresh backend IDs & reset originalMenusJson
        this.loading = true;
        await this.fetchMenus();
        this.saveStatus = "saved";
      } catch (err) {
        console.error(err);
        this.saveStatus = "unsaved";
        this.showToast(err.message || "Failed to save menu changes", "error");
      } finally {
        this.loading = false;
        this.saving = false;
        this.manualSaving = false;
      }
    },

    // ── Workspace Preferences ────────────────────────────────────
    saveWorkspacePrefs() {
      try {
        localStorage.setItem('pen_editor_workspace_prefs', JSON.stringify(this.workspacePrefs));
        const html = document.documentElement;
        html.classList.toggle('pref-left-collapsed',           !!this.workspacePrefs.leftColumnCollapsed);
        html.classList.toggle('pref-right-collapsed',          !!this.workspacePrefs.rightColumnCollapsed);
        html.classList.toggle('pref-secondary-rail-collapsed', !!this.workspacePrefs.secondaryRailCollapsed);
      } catch (e) { /* ignore */ }
    },

    // ── Resize Handlers ──────────────────────────────────────────
    startResizeLeft(e) {
      e.preventDefault();
      this.isDraggingLeftColumn = true;

      const startX         = e.clientX;
      const startWidthPct  = this.workspacePrefs.sidebarWidth || 32;
      const containerWidth = e.currentTarget.parentElement.clientWidth;

      document.body.style.cursor           = 'ew-resize';
      document.body.style.userSelect       = 'none';
      document.body.style.webkitUserSelect = 'none';

      const onMouseMove = (moveEvent) => {
        const deltaPct = ((moveEvent.clientX - startX) / containerWidth) * 100;
        let newPct = startWidthPct + deltaPct;
        if (newPct < 10) newPct = 10;
        if (newPct > 40) newPct = 40;
        this.workspacePrefs.sidebarWidth = Math.round(newPct * 10) / 10;
      };

      const onMouseUp = () => {
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup',  onMouseUp);
        document.body.style.cursor           = '';
        document.body.style.userSelect       = '';
        document.body.style.webkitUserSelect = '';
        this.isDraggingLeftColumn = false;
        this.saveWorkspacePrefs();
      };

      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup',  onMouseUp);
    },

    startResizeRight(e) {
      e.preventDefault();
      this.isDraggingRightColumn = true;

      const startX         = e.clientX;
      const startWidthPct  = this.workspacePrefs.rightColumnWidth || 25;
      const containerWidth = e.currentTarget.parentElement.clientWidth;

      document.body.style.cursor           = 'ew-resize';
      document.body.style.userSelect       = 'none';
      document.body.style.webkitUserSelect = 'none';

      const onMouseMove = (moveEvent) => {
        const deltaPct = ((moveEvent.clientX - startX) / containerWidth) * 100;
        let newPct = startWidthPct - deltaPct;
        if (newPct < 10) newPct = 10;
        if (newPct > 40) newPct = 40;
        this.workspacePrefs.rightColumnWidth = Math.round(newPct * 10) / 10;
      };

      const onMouseUp = () => {
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup',  onMouseUp);
        document.body.style.cursor           = '';
        document.body.style.userSelect       = '';
        document.body.style.webkitUserSelect = '';
        this.isDraggingRightColumn = false;
        this.saveWorkspacePrefs();
      };

      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup',  onMouseUp);
    },

    saveSlotOptions() {
      try {
        localStorage.setItem('pen_menu_slot_classes', JSON.stringify(this.slotClasses));
        this.showToast("Slot options updated");
      } catch (e) {
        this.showToast("Failed to save slot options", "error");
      }
    },
  }));
});
