<?php
$pageTitle = "PenCMS Posts";
$currentSection = "posts";
include "includes/_admin-auth.php";
include "includes/_admin-head.php";
?>

<body class="bg-canvas text-forge-black font-sans antialiased h-screen flex flex-col overflow-hidden"
      x-data="{
          config: null,
          filterCategories: {},
          filterStatusActive: (() => {
              const allowed = ['ALL', 'STUB', 'DRAFT', 'PUBLISHED', 'SCHEDULED', 'UNPUBLISHED'];
              const raw = (new URLSearchParams(window.location.search).get('status') || 'ALL').toUpperCase();
              return allowed.includes(raw) ? raw : 'ALL';
          })(),
          categoryDropdownOpen: false,
          viewMode: localStorage.getItem('adminViewMode') || 'grid',

          isScheduled(page) {
              const fm = (page && page.frontmatter) || {};
              if ((fm.status || '').toLowerCase() !== 'published') return false;
              if (!fm.publish_at) return false;
              const d = new Date(fm.publish_at);
              return !Number.isNaN(d.getTime()) && d.getTime() > Date.now();
          },

          effectiveStatus(page) {
              if (this.isScheduled(page)) return 'SCHEDULED';
              return ((page.frontmatter && page.frontmatter.status) || '').toUpperCase();
          },

          isPinned(page) {
              const fm = (page && page.frontmatter) || {};
              return fm.pinned === true || fm.pinned === 'true';
          },

          async togglePin(page) {
              if (!$store.app.hasCap('write:posts')) return;
              const nextPinned = !this.isPinned(page);
              try {
                  const collection = page.collection
                      || (page.frontmatter && (page.frontmatter.category || page.frontmatter.type))
                      || 'posts';
                  const entry = await window.api.getPage(page.id, collection);
                  const frontmatter = { ...(entry.frontmatter || {}), pinned: nextPinned };
                  await window.api.updatePage(page.id, {
                      frontmatter,
                      content: entry.content || '',
                      composite: entry.composite || false,
                      partials: entry.partials || {},
                      expected_version: entry.version || undefined,
                  }, null, collection);
                  if (!page.frontmatter) page.frontmatter = {};
                  page.frontmatter.pinned = nextPinned;
              } catch (err) {
                  console.error('Pin toggle failed:', err);
                  alert('Failed to update pin: ' + err.message);
              }
          },

          dossierDate(page) {
              const fm = (page && page.frontmatter) || {};
              return fm.date || page.modified_at || '';
          },

          async init() {
              await this.reloadSiteLists();

              this.$watch(
                  () => $store.app.activeSiteId,
                  async () => {
                      await this.reloadSiteLists();
                  }
              );
          },

          async reloadSiteLists() {
              this.filterCategories = {};
              try {
                  this.config = await window.api.getConfig();
                  if (this.config?.taxonomy?.[this.config?.primary_vocabulary]?.terms) {
                      this.config.taxonomy[this.config.primary_vocabulary].terms.forEach(t => {
                          this.filterCategories[t.toUpperCase()] = true;
                      });
                  }
              } catch (err) {
                  console.error('Failed to load configuration:', err);
              }
              await $store.app.fetchPages();
          },

          toggleAllCategories(val) {
              Object.keys(this.filterCategories).forEach(cat => {
                  this.filterCategories[cat] = val;
              });
          },

          getVocabularyLabel() {
              return this.config?.taxonomy?.[this.config?.primary_vocabulary]?.label || 'Category';
          },

          getSelectedCategoriesText() {
              const active = Object.entries(this.filterCategories).filter(([_, v]) => v).map(([k]) => k);
              const total = Object.keys(this.filterCategories).length;
              if (active.length === 0) return 'None';
              if (active.length === total) return 'All';
              if (active.length <= 2) {
                  return active.map(c => c.charAt(0) + c.slice(1).toLowerCase()).join(', ');
              }
              return `${active.length} Selected`;
          },

          get filteredPages() {
              return $store.app.pages.filter(p => {
                  if (p.frontmatter && (p.frontmatter.page === true || p.frontmatter.page === 'true')) {
                      return false;
                  }
                  let cat = (p.frontmatter.category || p.frontmatter.type || '').toUpperCase();
                  let catMatch = Object.keys(this.filterCategories).length === 0 || this.filterCategories[cat] !== false;

                  const eff = this.effectiveStatus(p);
                  let statusMatch = this.filterStatusActive === 'ALL' || eff === this.filterStatusActive;
                  // PUBLISHED tab excludes future-dated (shown under SCHEDULED)
                  if (this.filterStatusActive === 'PUBLISHED' && this.isScheduled(p)) {
                      statusMatch = false;
                  }

                  return catMatch && statusMatch;
              }).sort((a, b) => {
                  const pinDiff = (this.isPinned(b) ? 1 : 0) - (this.isPinned(a) ? 1 : 0);
                  if (pinDiff !== 0) return pinDiff;
                  const dateA = Date.parse(this.dossierDate(a)) || 0;
                  const dateB = Date.parse(this.dossierDate(b)) || 0;
                  return dateB - dateA;
              });
          },

          deleteModalOpen: false,
          postToDelete: null,

          deletePost(page) {
              if (!$store.app.hasCap('delete:posts')) return;
              this.postToDelete = page;
              this.deleteModalOpen = true;
          },

          async confirmDeletePost() {
              if (!this.postToDelete || !$store.app.hasCap('delete:posts')) return;
              try {
                  const collection = this.postToDelete.collection || (this.postToDelete.frontmatter && (this.postToDelete.frontmatter.category || this.postToDelete.frontmatter.type)) || 'posts';
                  await window.api.deletePage(this.postToDelete.id, collection);
                  this.deleteModalOpen = false;
                  this.postToDelete = null;
                  await $store.app.fetchPages();
              } catch (err) {
                  console.error('Delete failed:', err);
                  alert('Failed to delete post: ' + err.message);
              }
          }
      }">

    <!-- Header / Top Navigation -->
    <?php include "includes/_admin-header.php"; ?>

    <div class="flex flex-1 relative min-h-0 overflow-hidden">
        <!-- Collapsible Left Sidebar -->
        <?php include "includes/_admin-sidebar.php"; ?>

        <!-- Main Workspace Canvas -->
        <main class="flex-1 overflow-y-auto p-8 md:p-12 transition-all duration-300">
            <!-- Title / Context Rail -->
            <div class="flex flex-col md:flex-row md:justify-between md:items-end mb-8 gap-4">
                <div>
                    <h1 class="text-3xl text-forge-black font-sans font-black tracking-tight mb-2 pb-2 border-b-2 border-border-weld uppercase">
                        Posts
                    </h1>
                    <p class="text-forge-dark font-serif text-sm">
                        Managing <span class="text-rust font-bold" x-text="$store.app.pages.filter(p => !(p.frontmatter && (p.frontmatter.page === true || p.frontmatter.page === 'true'))).length">0</span> posts
                    </p>
                </div>
                <a :href="$store.app.adminPath('admin-editor.php')"
                   x-show="$store.app.hasCap('write:posts')"
                   x-cloak
                   class="pen-btn pen-btn-primary flex items-center gap-2 self-start md:self-auto">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"></path>
                    </svg>
                    <span>New Post</span>
                </a>
            </div>

            <!-- Redesigned Filter Toolbar (Hybrid: Status Tabs + Dynamic Multi-select Dropdown) -->
            <div class="flex flex-col sm:flex-row justify-between items-stretch sm:items-end border-b border-border mb-8 gap-4">
                <!-- Status Tabs -->
                <div class="flex gap-1 overflow-x-auto scrollbar-none">
                    <template x-for="status in ['ALL', 'STUB', 'DRAFT', 'PUBLISHED', 'SCHEDULED', 'UNPUBLISHED']" :key="status">
                        <button @click="filterStatusActive = status"
                                class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150 whitespace-nowrap focus:outline-none"
                                :class="filterStatusActive === status ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                            <span x-text="status === 'ALL' ? 'ALL POSTS' : status"></span>
                        </button>
                    </template>
                </div>

                <!-- Category Dropdown & View Mode Toggle -->
                <div class="flex items-center gap-3 w-full sm:w-auto pb-2 self-start sm:self-auto">
                    <!-- Category Dropdown -->
                    <div class="relative w-full sm:w-72" @click.outside="categoryDropdownOpen = false">
                        <button @click="categoryDropdownOpen = !categoryDropdownOpen"
                                class="w-full px-4 py-2 border-2 border-border font-sans text-xs font-bold tracking-wide bg-canvas text-forge-black cursor-pointer hover:bg-card hover:border-steel-muted transition-colors flex items-center justify-between gap-3 select-none focus:outline-none">
                            <span><span x-text="getVocabularyLabel()"></span>: <span class="text-rust" x-text="getSelectedCategoriesText()"></span></span>
                            <svg class="w-3.5 h-3.5 text-steel-muted transition-transform duration-200" :class="categoryDropdownOpen ? 'rotate-180' : ''" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5"></path>
                            </svg>
                        </button>
                        
                        <!-- Dropdown List Popover -->
                        <div x-show="categoryDropdownOpen"
                             x-transition:enter="transition ease-out duration-100"
                             x-transition:enter-start="transform opacity-0 scale-95"
                             x-transition:enter-end="transform opacity-100 scale-100"
                             x-transition:leave="transition ease-in duration-75"
                             x-transition:leave-start="transform opacity-100 scale-100"
                             x-transition:leave-end="transform opacity-0 scale-95"
                             class="absolute left-0 top-full mt-0 w-full bg-card border-2 border-t-0 border-border shadow-md z-50 select-none overflow-hidden"
                             style="display: none;">
                             
                            <!-- Quick actions -->
                            <div class="flex justify-between items-center px-3 py-1.5 border-b border-border bg-canvas/50">
                                <button @click="toggleAllCategories(true)" class="text-[10px] font-bold text-forge-mid hover:text-rust uppercase tracking-wider focus:outline-none">Select All</button>
                                <button @click="toggleAllCategories(false)" class="text-[10px] font-bold text-forge-mid hover:text-rust uppercase tracking-wider focus:outline-none">Clear All</button>
                            </div>
                            
                            <!-- Checklist -->
                            <div class="max-h-[500px] overflow-y-auto divide-y divide-border/40 scrollbar-acid">
                                <template x-for="cat in Object.keys(filterCategories)" :key="cat">
                                    <label class="flex items-center gap-2 px-3 py-1.5 cursor-pointer hover:bg-rust-wash transition-colors select-none font-sans text-[11px] font-normal tracking-wide text-forge-dark">
                                        <input type="checkbox" x-model="filterCategories[cat]" class="sr-only">
                                        <span class="w-3 h-3 border border-border flex items-center justify-center transition-colors"
                                              :class="filterCategories[cat] ? 'bg-rust border-rust text-white' : 'bg-transparent'">
                                            <template x-if="filterCategories[cat]">
                                                <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24">
                                                    <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5"></path>
                                                </svg>
                                            </template>
                                        </span>
                                        <span x-text="cat.toLowerCase().split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')"></span>
                                    </label>
                                </template>
                            </div>
                        </div>
                    </div>

                    <!-- View Mode Toggle -->
                    <div class="flex border-2 border-border bg-canvas select-none h-[38px] shrink-0 items-center">
                        <button @click="viewMode = 'grid'; localStorage.setItem('adminViewMode', 'grid')" 
                                :class="viewMode === 'grid' ? 'text-rust bg-card' : 'text-forge-mid hover:text-forge-black bg-transparent opacity-40'" 
                                class="p-2 focus:outline-none transition-all duration-150 h-full flex items-center justify-center w-10" 
                                title="Grid View">
                            <svg class="w-5 h-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"><rect width="256" height="256" fill="none"/><rect x="48" y="48" width="160" height="160" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="128" y1="48" x2="128" y2="208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="48" y1="128" x2="208" y2="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                        </button>
                        <button @click="viewMode = 'list'; localStorage.setItem('adminViewMode', 'list')" 
                                :class="viewMode === 'list' ? 'text-rust bg-card' : 'text-forge-mid hover:text-forge-black bg-transparent opacity-40'" 
                                class="p-2 focus:outline-none transition-all duration-150 h-full flex items-center justify-center w-10 border-l border-border" 
                                title="List View">
                            <svg class="w-5 h-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"><rect width="256" height="256" fill="none"/><line x1="96" y1="64" x2="216" y2="64" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="96" y1="128" x2="216" y2="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="96" y1="192" x2="216" y2="192" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="40" y1="64" x2="56" y2="64" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="40" y1="128" x2="56" y2="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="40" y1="192" x2="56" y2="192" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                        </button>
                    </div>
                </div>

            </div>

            <!-- Page Cards Grid -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" x-show="!$store.app.loading && viewMode === 'grid'">
                <template x-for="page in filteredPages" :key="page.id">
                    <div class="pen-card p-6 flex flex-col justify-between hover:shadow-md transition-shadow duration-200 bg-card group relative">
                        <button x-show="$store.app.hasCap('delete:posts')" x-cloak @click.prevent="deletePost(page)" class="absolute -top-2.5 -right-2.5 p-1 bg-card hover:bg-rust-wash text-danger hover:text-rust-deep border-2 border-border hover:border-rust rounded-full transition-all opacity-0 group-hover:opacity-100 focus:opacity-100 focus:outline-none shadow-sm z-10" title="Delete Post">
                            <svg class="w-5 h-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"><rect width="256" height="256" fill="none"/><line x1="160" y1="96" x2="96" y2="160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><line x1="96" y1="96" x2="160" y2="160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><circle cx="128" cy="128" r="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>
                        </button>
                        <div>
                            <div class="flex justify-between items-start mb-4">
                                <div class="flex gap-2 items-center">
                                    <span class="pen-badge-acid text-[10px] px-2 py-0.5" x-text="page.frontmatter.category || page.frontmatter.type"></span>
                                    <button type="button"
                                        x-show="$store.app.hasCap('write:posts')"
                                        x-cloak
                                        @click.prevent="togglePin(page)"
                                        class="p-0.5 rounded transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-rust/30"
                                        :class="isPinned(page) ? 'text-rust' : 'text-forge-mid opacity-40 hover:opacity-70'"
                                        :title="isPinned(page) ? 'Unpin post' : 'Pin post'"
                                        :aria-pressed="isPinned(page) ? 'true' : 'false'"
                                        aria-label="Toggle pin">
                                        <svg class="w-4 h-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" aria-hidden="true"><rect width="256" height="256" fill="none"/><path d="M229.66,98.34a8,8,0,0,0,0-11.31L169,26.34a8,8,0,0,0-11.31,0L100.39,83.8S72.64,69.93,43,93.85a8,8,0,0,0-.65,11.91l107.9,107.89a8,8,0,0,0,12-.83c8.39-11.16,21.57-34.09,10.11-57Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><line x1="96.29" y1="159.71" x2="48" y2="208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>
                                    </button>
                                </div>
                                <div class="w-3.5 h-3.5 shrink-0"
                                     :class="{
                                         'bg-rust': isScheduled(page),
                                         'bg-acid': !isScheduled(page) && page.frontmatter.status?.toUpperCase() === 'PUBLISHED',
                                         'bg-black/20': page.frontmatter.status?.toUpperCase() === 'STUB',
                                         'bg-black/40': page.frontmatter.status?.toUpperCase() === 'DRAFT',
                                         'bg-black/60': page.frontmatter.status?.toUpperCase() === 'UNPUBLISHED'
                                     }"
                                     :title="isScheduled(page) ? 'scheduled' : page.frontmatter.status">
                                </div>
                            </div>

                            <h2 class="text-xl font-sans font-bold mb-2 leading-heading">
                                <a :href="$store.app.adminPath('admin-editor.php', { id: page.id, collection: page.collection || undefined })" class="text-forge-black hover:text-rust transition-colors duration-150 no-underline" x-text="page.frontmatter.hero_title || page.frontmatter.name || page.frontmatter.title || 'Untitled Document'"></a>
                            </h2>
                            <p class="text-sm text-forge-dark font-serif line-clamp-3 mb-6 leading-prose" x-text="page.frontmatter.deck || (page.content ? page.content.substring(0, 120) + '...' : 'Summary pending...')"></p>
                        </div>

                        <div class="pt-4 border-t border-border flex justify-between items-center mt-auto">
                            <span class="text-[11px] text-forge-mid font-mono truncate max-w-[180px]" x-text="page.frontmatter.slug || page.id"></span>
                            <div class="flex gap-3 font-sans text-xs font-bold uppercase tracking-wider select-none">
                                <a :href="$store.app.adminPath('admin-editor.php', { id: page.id, collection: page.collection || undefined })" class="text-rust hover:text-rust-deep transition-colors no-underline" title="Edit Content">Edit &rarr;</a>
                            </div>
                        </div>
                    </div>
                </template>
            </div>

            <!-- Page Cards List -->
            <div class="flex flex-col divide-y divide-border/60" x-show="!$store.app.loading && viewMode === 'list'">
                <template x-for="page in filteredPages" :key="page.id">
                    <div class="py-3 flex items-center justify-between gap-4 bg-transparent hover:bg-black/[0.01] transition-colors duration-150 group">
                        <a :href="$store.app.adminPath('admin-editor.php', { id: page.id, collection: page.collection || undefined })" class="flex items-center gap-3 sm:gap-6 flex-1 min-w-0 no-underline">
                            <!-- Status Indicator Rectangle -->
                            <div class="w-3.5 h-3.5 shrink-0"
                                 :class="{
                                     'bg-rust': isScheduled(page),
                                     'bg-acid': !isScheduled(page) && page.frontmatter.status?.toUpperCase() === 'PUBLISHED',
                                     'bg-black/20': page.frontmatter.status?.toUpperCase() === 'STUB',
                                     'bg-black/40': page.frontmatter.status?.toUpperCase() === 'DRAFT',
                                     'bg-black/60': page.frontmatter.status?.toUpperCase() === 'UNPUBLISHED'
                                 }"
                                 :title="isScheduled(page) ? 'scheduled' : page.frontmatter.status">
                            </div>

                            <!-- Eyebrow & Title -->
                            <div class="flex-1 min-w-0 flex flex-col">
                                <span class="text-[9px] text-forge-mid font-bold uppercase tracking-wider mb-0.5" style="font-family: 'Atkinson Hyperlegible Next', sans-serif;" x-text="page.frontmatter.category || page.frontmatter.type || 'general'"></span>
                                <h2 class="text-base font-sans font-bold text-forge-black group-hover:text-rust transition-colors truncate mb-0" x-text="page.frontmatter.hero_title || page.frontmatter.name || page.frontmatter.title || 'Untitled Document'"></h2>
                            </div>
                        </a>
                        <div class="flex items-center gap-3 shrink-0 select-none">
                            <button type="button"
                                x-show="$store.app.hasCap('write:posts')"
                                x-cloak
                                @click.prevent="togglePin(page)"
                                class="p-1 rounded transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-rust/30"
                                :class="isPinned(page) ? 'text-rust' : 'text-forge-mid opacity-40 hover:opacity-70'"
                                :title="isPinned(page) ? 'Unpin post' : 'Pin post'"
                                :aria-pressed="isPinned(page) ? 'true' : 'false'"
                                aria-label="Toggle pin">
                                <svg class="w-4 h-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" aria-hidden="true"><rect width="256" height="256" fill="none"/><path d="M229.66,98.34a8,8,0,0,0,0-11.31L169,26.34a8,8,0,0,0-11.31,0L100.39,83.8S72.64,69.93,43,93.85a8,8,0,0,0-.65,11.91l107.9,107.89a8,8,0,0,0,12-.83c8.39-11.16,21.57-34.09,10.11-57Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><line x1="96.29" y1="159.71" x2="48" y2="208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>
                            </button>
                            <button x-show="$store.app.hasCap('delete:posts')" x-cloak @click.prevent="deletePost(page)" class="p-2 text-danger hover:text-red-800 transition-all opacity-0 group-hover:opacity-100 focus:opacity-100 focus:outline-none" title="Delete Post">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                            </button>
                        </div>
                    </div>
                </template>
            </div>


            <!-- Empty State -->
            <template x-if="!$store.app.loading && filteredPages.length === 0">
                <div class="text-center py-20 border border-dashed border-border bg-card">
                    <p class="text-forge-dark font-serif text-sm">No posts found matching the filters.</p>
                </div>
            </template>

            <!-- Loading State -->
            <template x-if="$store.app.loading">
                <div class="flex justify-center py-20">
                    <span class="pen-spinner" role="status" aria-label="Loading…"></span>
                </div>
            </template>
        </main>
    </div>

    <!-- Delete Confirmation Modal -->
    <div x-show="deleteModalOpen" x-cloak class="pen-modal-overlay p-4" style="display:none" x-transition>
        <div class="pen-modal-danger min-w-0 w-full max-w-[480px] sm:min-w-[480px]" @click.away="deleteModalOpen = false" @keydown.escape.window="deleteModalOpen = false">
            <div class="pen-modal-header">
                <h3 class="pen-modal-title">Delete Post</h3>
                <button @click="deleteModalOpen = false" class="text-forge-mid hover:text-forge-black focus:outline-none">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>
            <div class="pen-modal-body space-y-3">
                <p class="text-sm text-forge-black font-sans">
                    Confirm if you want to permanently delete<br> <strong class="font-mono text-xs bg-canvas px-1.5 py-0.5 border border-border" x-text="postToDelete?.frontmatter?.hero_title || postToDelete?.frontmatter?.name || postToDelete?.frontmatter?.title || postToDelete?.id"></strong>
                </p>
                <p class="text-xs text-forge-muted font-serif leading-prose">
                    This action is immediate, will remove the entry from database indexes, physically delete the markdown files from disk, and cannot be undone.
                </p>
            </div>
            <div class="pen-modal-footer">
                <button @click="deleteModalOpen = false" class="pen-btn pen-btn-secondary pen-btn-sm focus:outline-none">Cancel</button>
                <button @click="confirmDeletePost()" class="pen-btn pen-btn-danger pen-btn-sm focus:outline-none">Delete Post</button>
            </div>
        </div>
    </div>

    <!-- Footer -->
    <?php include "includes/_admin-footer.php"; ?>
