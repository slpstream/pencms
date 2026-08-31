<?php
$pageTitle = "Media Library (PenCMS)";
$currentSection = "media";
$pageScript = "media.js";
include "includes/_admin-auth.php";
include "includes/_admin-head.php";
?>

<body class="bg-canvas text-forge-black font-sans antialiased h-screen flex flex-col overflow-hidden"
      x-data="mediaLibrary" x-init="init()">

    <!-- Header / Top Navigation -->
    <?php include "includes/_admin-header.php"; ?>

    <div class="flex flex-1 relative min-h-0 overflow-hidden">
        <!-- Collapsible Left Sidebar -->
        <?php include "includes/_admin-sidebar.php"; ?>

        <!-- Main Workspace Canvas -->
        <main class="flex-1 overflow-y-auto p-8 md:p-12 transition-all duration-300">

            <!-- Title Section -->
            <div class="mb-8">
                <h1 class="text-3xl text-forge-black font-sans font-black tracking-tight mb-2 pb-2 border-b-2 border-border-weld uppercase">
                    Media Library
                </h1>
                <p class="text-forge-dark font-serif text-sm">
                    Archive of media assets for this site.
                    <span class="text-forge-mid font-sans text-xs ml-1">Site: <span class="font-mono font-bold text-rust" x-text="$store.app.activeSiteId"></span></span>
                </p>
            </div>

            <!-- Stats Bar -->
            <div class="flex flex-wrap items-center gap-4 mb-8">
                <div class="pen-card px-5 py-3 flex items-center gap-3">
                    <span class="text-[10px] font-bold text-forge-mid uppercase tracking-widest">Storage:</span>
                    <span class="text-sm font-mono font-bold text-rust" x-text="formatSize(stats.totalSize)"></span>
                </div>
                <div class="pen-card px-5 py-3 flex items-center gap-3">
                    <span class="text-[10px] font-bold text-forge-mid uppercase tracking-widest">Total Assets:</span>
                    <span class="text-sm font-mono font-bold text-rust" x-text="stats.totalCount"></span>
                </div>
            </div>

            <!-- Filters & Search -->
            <section class="pen-card p-4 mb-8 flex flex-col md:flex-row items-center gap-4">
                <div class="relative flex-1 w-full">
                    <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <svg class="h-5 w-5 text-forge-mid" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                    </div>
                    <input type="text"
                           x-model="searchQuery"
                           placeholder="Search by filename or entity ID..."
                           class="pen-input w-full pl-10">
                </div>

                <div class="flex items-center space-x-2 w-full md:w-auto">
                    <label class="text-xs font-bold uppercase text-forge-mid whitespace-nowrap">Filter By:</label>
                    <select x-model="filterType" class="pen-input text-xs py-1.5 min-w-[150px]">
                        <option value="all">All Types</option>
                        <template x-for="type in filterTypes" :key="type">
                            <option :value="type" x-text="type.charAt(0).toUpperCase() + type.slice(1).replace(/_/g, ' ')"></option>
                        </template>
                    </select>
                </div>

                <div class="flex items-center space-x-2 w-full md:w-auto">
                    <label class="text-xs font-bold uppercase text-forge-mid whitespace-nowrap">Sort By:</label>
                    <select x-model="sortOrder" class="pen-input text-xs py-1.5 min-w-[120px]">
                        <option value="newest">Newest</option>
                        <option value="oldest">Oldest</option>
                        <option value="az">A-Z</option>
                        <option value="za">Z-A</option>
                    </select>
                </div>

                <button @click="loadAssets()" class="p-2 text-forge-mid hover:text-rust transition-colors" title="Refresh">
                    <svg class="w-5 h-5" :class="loading ? 'animate-spin' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
                </button>
            </section>

            <!-- Loading Spinner -->
            <template x-if="loading">
                <div class="flex justify-center py-32">
                    <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-rust"></div>
                </div>
            </template>

            <!-- Empty State -->
            <template x-if="!loading && filteredAssets.length === 0">
                <div class="text-center py-32 border-2 border-dashed border-border rounded-[2px]">
                    <p class="text-xl text-forge-mid font-bold font-sans uppercase tracking-wider">No assets matching your criteria.</p>
                    <p class="text-sm text-forge-mid mt-2 font-serif">Try adjusting your filters or search query.</p>
                </div>
            </template>

            <!-- Assets Grid -->
            <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4" x-show="!loading">
                <template x-for="asset in filteredAssets" :key="asset.path">
                    <div class="group pen-card overflow-hidden border-transparent hover:border-rust/40 hover:shadow-md transition-all flex flex-col">

                        <!-- Image Preview -->
                        <div class="aspect-square bg-canvas overflow-hidden relative cursor-pointer" @click="openModal(asset)">
                            <img :src="asset.url" class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110">

                            <!-- Delete Button -->
                            <button x-show="$store.app.hasCap('delete:media')" x-cloak
                                    @click.stop="deleteAsset(asset)"
                                    class="absolute top-2 right-2 bg-danger text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-danger/80 shadow-lg z-20">
                                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                            </button>

                            <!-- Hover Overlay with Magnifying Glass -->
                            <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center justify-center z-10">
                                <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7"></path>
                                </svg>
                            </div>

                            <!-- Overlay Info -->
                            <div class="absolute inset-0 bg-gradient-to-t from-forge-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-3 z-15 pointer-events-none">
                                <span class="text-[10px] font-bold text-acid uppercase tracking-widest mb-1" x-text="formatEntityType(asset.entity_type)"></span>
                                <span class="text-steel-bright text-xs font-medium truncate" x-text="asset.entity_id"></span>
                            </div>
                        </div>

                        <!-- File Metadata -->
                        <div class="p-3 bg-card flex-1 flex flex-col">
                            <div class="mb-2">
                                <p class="text-[10px] font-bold text-forge-dark tracking-tighter truncate" :title="asset.filename" x-text="asset.filename"></p>
                                <div class="flex items-center justify-between mt-1">
                                    <span class="text-[10px] font-mono text-forge-mid" x-text="formatSize(asset.size_bytes)"></span>
                                    <span class="text-[10px] font-mono text-forge-mid" x-text="formatDate(asset.modified_at)"></span>
                                </div>
                            </div>

                            <div class="mt-auto pt-2 border-t border-border flex items-center justify-between">
                                <a :href="getEditorLink(asset)"
                                   class="text-[10px] font-bold uppercase tracking-widest text-rust hover:text-rust-deep transition-colors flex items-center space-x-1">
                                    <span>Edit Post</span>
                                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
                                </a>
                                <a :href="asset.url" target="_blank" class="text-forge-mid hover:text-rust transition-colors">
                                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a2 2 0 002 2h12a2 2 0 002-2v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                                </a>
                            </div>
                        </div>
                    </div>
                </template>
            </div>
        </main>
    </div>

    <!-- Delete Asset Confirmation Modal -->
    <div x-show="deleteModalOpen" x-cloak class="pen-modal-overlay p-4" style="display:none" x-transition>
        <div class="pen-modal-danger min-w-0 w-full max-w-[480px] sm:min-w-[480px]" @click.away="deleteModalOpen = false" @keydown.escape.window="deleteModalOpen = false">
            <div class="pen-modal-header">
                <h3 class="pen-modal-title">Delete Asset</h3>
                <button @click="deleteModalOpen = false" class="text-forge-mid hover:text-forge-black">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>
            <div class="pen-modal-body space-y-3">
                <p class="text-sm text-forge-black font-sans">
                    Are you sure you want to permanently delete the asset <strong class="font-mono text-xs bg-canvas px-1.5 py-0.5 border border-border" x-text="assetToDelete?.filename"></strong>?
                </p>
                <p class="text-xs text-forge-muted font-serif leading-prose">
                    This action is immediate and cannot be undone.
                </p>
            </div>
            <div class="pen-modal-footer">
                <button @click="deleteModalOpen = false" class="pen-btn pen-btn-secondary pen-btn-sm">Cancel</button>
                <button @click="confirmDeleteAsset()" class="pen-btn pen-btn-danger pen-btn-sm">Delete Asset</button>
            </div>
        </div>
    </div>

    <!-- ── Fullscreen Image Modal ──────────────────────────────────── -->
    <div x-show="showModal" class="fixed inset-0 z-[100] flex items-center justify-center p-8 bg-nav/90"
        @click="closeModal()" @keydown.escape.window="closeModal()" style="display:none" x-transition>
        <template x-if="modalImage">
            <div class="relative max-w-5xl" @click.stop>
                <img :src="modalImage.url" class="max-w-full max-h-[80vh] border border-border shadow-lg">
                <button @click="closeModal()"
                    class="absolute -top-4 -right-4 bg-card text-forge-black p-2 border border-border shadow-md hover:text-danger transition-colors">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
                <p class="mt-4 text-center text-steel-bright text-xs font-mono bg-nav/90 inline-block px-3 py-1 mx-auto"
                    x-text="modalImage.filename"></p>
            </div>
        </template>
    </div>

    <!-- Footer -->
    <?php include "includes/_admin-footer.php"; ?>
</body>
</html>
