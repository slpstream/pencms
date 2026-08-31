<?php
$pageTitle = "PenCMS Pages";
$currentSection = "pages";
include "includes/_admin-auth.php";
include "includes/_admin-head.php";
?>

<body class="bg-canvas text-forge-black font-sans antialiased h-screen flex flex-col overflow-hidden"
      x-data="{
          config: null,
          filterStatusActive: (() => {
              const allowed = ['ALL', 'STUB', 'DRAFT', 'PUBLISHED', 'SCHEDULED', 'UNPUBLISHED'];
              const raw = (new URLSearchParams(window.location.search).get('status') || 'ALL').toUpperCase();
              return allowed.includes(raw) ? raw : 'ALL';
          })(),
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

          async init() {
              await $store.app.fetchPages();
              this.$watch(
                  () => $store.app.activeSiteId,
                  async () => {
                      await $store.app.fetchPages();
                  }
              );
          },

          get filteredPages() {
              return $store.app.pages.filter(p => {
                  if (!p.frontmatter || (p.frontmatter.page !== true && p.frontmatter.page !== 'true')) {
                      return false;
                  }
                  const eff = this.effectiveStatus(p);
                  let statusMatch = this.filterStatusActive === 'ALL' || eff === this.filterStatusActive;
                  if (this.filterStatusActive === 'PUBLISHED' && this.isScheduled(p)) {
                      statusMatch = false;
                  }

                  return statusMatch;
              });
          },

          deleteModalOpen: false,
          postToDelete: null,

          deletePost(page) {
              if (!$store.app.hasCap('delete:pages')) return;
              this.postToDelete = page;
              this.deleteModalOpen = true;
          },

          async confirmDeletePost() {
              if (!this.postToDelete || !$store.app.hasCap('delete:pages')) return;
              try {
                  const collection = this.postToDelete.collection || (this.postToDelete.frontmatter && (this.postToDelete.frontmatter.category || this.postToDelete.frontmatter.type)) || 'posts';
                  await window.api.deletePage(this.postToDelete.id, collection);
                  this.deleteModalOpen = false;
                  this.postToDelete = null;
                  await $store.app.fetchPages();
              } catch (err) {
                  console.error('Delete failed:', err);
                  alert('Failed to delete page: ' + err.message);
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
                        Pages
                    </h1>
                    <p class="text-forge-dark font-serif text-sm">
                        Managing <span class="text-rust font-bold" x-text="$store.app.pages.filter(p => p.frontmatter && (p.frontmatter.page === true || p.frontmatter.page === 'true')).length">0</span> pages
                    </p>
                </div>
                <a :href="$store.app.adminPath('admin-editor.php', { page: 'true' })"
                   x-show="$store.app.hasCap('write:pages')"
                   x-cloak
                   class="pen-btn pen-btn-primary flex items-center gap-2 self-start md:self-auto">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"></path>
                    </svg>
                    <span>Create New</span>
                </a>
            </div>

            <!-- Redesigned Filter Toolbar (Status Tabs + View Mode Toggle) -->
            <div class="flex flex-col sm:flex-row justify-between items-stretch sm:items-end border-b border-border mb-8 gap-4">
                <!-- Status Tabs -->
                <div class="flex gap-1 overflow-x-auto scrollbar-none">
                    <template x-for="status in ['ALL', 'STUB', 'DRAFT', 'PUBLISHED', 'SCHEDULED', 'UNPUBLISHED']" :key="status">
                        <button @click="filterStatusActive = status"
                                class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150 whitespace-nowrap focus:outline-none"
                                :class="filterStatusActive === status ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                            <span x-text="status === 'ALL' ? 'ALL PAGES' : status"></span>
                        </button>
                    </template>
                </div>

                <!-- View Mode Toggle -->
                <div class="flex items-center gap-3 w-full sm:w-auto pb-2 self-start sm:self-auto justify-end">
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
                        <button x-show="$store.app.hasCap('delete:pages')" x-cloak @click.prevent="deletePost(page)" class="absolute -top-2.5 -right-2.5 p-1 bg-card hover:bg-rust-wash text-danger hover:text-rust-deep border-2 border-border hover:border-rust rounded-full transition-all opacity-0 group-hover:opacity-100 focus:opacity-100 focus:outline-none shadow-sm z-10" title="Delete Page">
                            <svg class="w-5 h-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256"><rect width="256" height="256" fill="none"/><line x1="160" y1="96" x2="96" y2="160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><line x1="96" y1="96" x2="160" y2="160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><circle cx="128" cy="128" r="96" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>
                        </button>
                        <div>
                            <div class="flex justify-between items-start mb-4">
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

                            <!-- Title -->
                            <div class="flex-1 min-w-0 flex flex-col">
                                <h2 class="text-base font-sans font-bold text-forge-black group-hover:text-rust transition-colors truncate mb-0" x-text="page.frontmatter.hero_title || page.frontmatter.name || page.frontmatter.title || 'Untitled Document'"></h2>
                            </div>
                        </a>
                        <div class="flex items-center gap-3 shrink-0 select-none">
                            <button x-show="$store.app.hasCap('delete:pages')" x-cloak @click.prevent="deletePost(page)" class="p-2 text-danger hover:text-red-800 transition-all opacity-0 group-hover:opacity-100 focus:opacity-100 focus:outline-none" title="Delete Page">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                            </button>
                        </div>
                    </div>
                </template>
            </div>


            <!-- Empty State -->
            <template x-if="!$store.app.loading && filteredPages.length === 0">
                <div class="text-center py-20 border border-dashed border-border bg-card">
                    <p class="text-forge-dark font-serif text-sm">No pages found matching the filters.</p>
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
                <h3 class="pen-modal-title">Delete Page</h3>
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
                <button @click="confirmDeletePost()" class="pen-btn pen-btn-danger pen-btn-sm focus:outline-none">Delete Page</button>
            </div>
        </div>
    </div>

    <!-- Footer -->
    <?php include "includes/_admin-footer.php"; ?>
