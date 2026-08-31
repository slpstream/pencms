<?php
$pageTitle = "PenCMS Dashboard";
$currentSection = "dashboard";
$pageScript = "dashboard.js";
include "includes/_admin-auth.php";
include "includes/_admin-head.php";
?>

<body class="bg-canvas text-forge-black font-sans antialiased h-screen flex flex-col overflow-hidden"
      x-data="adminDashboard">

    <!-- Header / Top Navigation -->
    <?php include "includes/_admin-header.php"; ?>

    <div class="flex flex-1 relative min-h-0 overflow-hidden">
        <!-- Collapsible Left Sidebar -->
        <?php include "includes/_admin-sidebar.php"; ?>

        <!-- Dashboard workspace: main + optional site rail -->
        <div class="flex-1 flex min-h-0 min-w-0 overflow-hidden">
            <main class="flex-1 overflow-y-auto p-8 md:p-12 transition-all duration-300 min-w-0">
                <!-- Title -->
                <div class="flex flex-col md:flex-row md:justify-between md:items-end mb-6 gap-4">
                    <div>
                        <h1 class="text-3xl text-forge-black font-sans font-black tracking-tight mb-2 pb-2 border-b-2 border-border-weld uppercase">
                            Dashboard
                        </h1>
                        <p class="text-forge-dark font-serif text-sm">
                            Overview for
                            <span class="text-rust font-bold" x-text="sitename">…</span>
                        </p>
                    </div>
                    <div class="flex flex-wrap items-center gap-2 self-start md:self-auto">
                        <a :href="previewHref()" target="_blank" rel="noopener"
                           class="pen-btn flex items-center gap-2">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"></path>
                            </svg>
                            <span>Preview</span>
                        </a>
                        <a :href="$store.app.adminPath('admin-editor.php')" class="pen-btn pen-btn-primary flex items-center gap-2">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"></path>
                            </svg>
                            <span>New Post</span>
                        </a>
                        <a href="admin-publish.php" class="pen-btn flex items-center gap-2">
                            <span>Publish</span>
                        </a>
                    </div>
                </div>

                <!-- Site tabs (2–5 sites) -->
                <div x-show="useSiteTabs" x-cloak class="flex border-b border-border mb-8 gap-1 overflow-x-auto scrollbar-none">
                    <template x-for="s in sites" :key="s.id">
                        <button type="button"
                                @click="selectSite(s.id)"
                                class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150 whitespace-nowrap focus:outline-none"
                                :class="activeSiteId === s.id
                                    ? 'border-rust bg-card text-rust font-black'
                                    : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                            <span x-text="s.name || s.id"></span>
                        </button>
                    </template>
                </div>

                <!-- Compact site picker when rail is desktop-only (>5 sites, small screens) -->
                <div x-show="useSiteRail" x-cloak class="md:hidden mb-6">
                    <label class="block text-[10px] font-sans font-bold uppercase tracking-wider text-forge-mid mb-1.5">Content site</label>
                    <select class="pen-input w-full text-sm"
                            :value="activeSiteId"
                            @change="selectSite($event.target.value)">
                        <template x-for="s in sites" :key="'m-' + s.id">
                            <option :value="s.id" x-text="siteLabel(s)"></option>
                        </template>
                    </select>
                </div>

                <!-- Loading -->
                <template x-if="loading">
                    <div class="flex justify-center py-20">
                        <span class="pen-spinner" role="status" aria-label="Loading…"></span>
                    </div>
                </template>

                <div x-show="!loading" x-cloak class="space-y-10">
                    <p x-show="loadError" x-text="loadError" class="text-sm text-danger font-serif"></p>

                    <!-- Site identity strip -->
                    <section class="border-b border-border pb-6">
                        <div class="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
                            <div class="min-w-0">
                                <p class="text-[10px] font-sans font-bold uppercase tracking-wider text-forge-mid mb-1">Active site</p>
                                <h2 class="text-2xl font-sans font-black text-forge-black tracking-tight truncate" x-text="sitename"></h2>
                                <div class="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs font-serif text-forge-dark">
                                    <span>
                                        <span class="text-forge-mid uppercase tracking-wider font-sans font-bold text-[10px] mr-1">ID</span>
                                        <span class="font-mono" x-text="activeSiteId"></span>
                                    </span>
                                    <span>
                                        <span class="text-forge-mid uppercase tracking-wider font-sans font-bold text-[10px] mr-1">Theme</span>
                                        <span x-text="(activeSite && activeSite.theme) || '—'"></span>
                                    </span>
                                    <span>
                                        <span class="text-forge-mid uppercase tracking-wider font-sans font-bold text-[10px] mr-1">Domain</span>
                                        <span x-text="(activeSite && activeSite.domain) ? activeSite.domain : 'No domain'"></span>
                                    </span>
                                </div>
                            </div>
                        </div>
                    </section>

                    <!-- Content stats -->
                    <section>
                        <div class="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mb-4 pb-2 border-b border-border">
                            <h3 class="text-xs font-sans font-black uppercase tracking-wider text-forge-black">
                                Content
                            </h3>
                            <div x-show="$store.app.use_ai" x-cloak class="min-w-0 sm:max-w-xl sm:text-right space-y-2">
                                <div x-show="summaryFill.status === 'idle' || summaryFill.status === 'done' || summaryFill.status === 'error'"
                                     class="flex flex-wrap items-center gap-x-3 gap-y-1 sm:justify-end">
                                    <span class="text-[11px] font-serif text-forge-mid"
                                          x-text="emptySummaryCount === 0
                                            ? 'No empty summaries on published posts/pages'
                                            : (emptySummaryCount + ' empty ' + (emptySummaryCount === 1 ? 'summary' : 'summaries') + ' on published posts/pages')"></span>
                                    <button type="button"
                                            @click="requestFillEmptySummaries()"
                                            class="pen-btn pen-btn-sm"
                                            :disabled="emptySummaryCount === 0 || summaryFill.status === 'running'">
                                        Fill empty summaries
                                    </button>
                                </div>
                                <div x-show="summaryFill.status === 'confirm'" class="space-y-2">
                                    <p class="text-xs font-serif text-forge-dark"
                                       x-text="'Fill empty summaries on ' + emptySummaryCount + ' published posts/pages? Existing summaries will not be changed.'"></p>
                                    <div class="flex flex-wrap items-center gap-2 sm:justify-end">
                                        <button type="button" @click="confirmFillEmptySummaries()" class="pen-btn pen-btn-primary pen-btn-sm">
                                            Fill
                                        </button>
                                        <button type="button" @click="cancelSummaryFill()" class="pen-btn pen-btn-sm">
                                            Cancel
                                        </button>
                                    </div>
                                </div>
                                <div x-show="summaryFill.status === 'running'" class="flex flex-wrap items-center gap-x-3 gap-y-1 sm:justify-end">
                                    <span class="text-[11px] font-serif text-forge-dark"
                                          x-text="'Filling ' + summaryFill.current + ' of ' + summaryFill.total + '…'"></span>
                                    <button type="button" @click="cancelSummaryFill()" class="pen-btn pen-btn-sm">
                                        Cancel
                                    </button>
                                </div>
                                <p x-show="summaryFill.status === 'done'"
                                   class="text-[11px] font-serif text-forge-dark"
                                   x-text="summaryFillResultText"></p>
                                <p x-show="summaryFill.status === 'error'"
                                   class="text-[11px] font-serif text-danger"
                                   x-text="summaryFill.error"></p>
                            </div>
                        </div>
                        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-0 border border-border divide-x divide-y sm:divide-y-0 divide-border bg-card">
                            <a href="admin-posts.php?status=published"
                               class="px-4 py-5 no-underline hover:bg-rust-wash/40 transition-colors group">
                                <p class="text-[10px] font-sans font-bold uppercase tracking-wider text-forge-mid mb-1">Published</p>
                                <p class="text-2xl font-sans font-black text-forge-black group-hover:text-rust transition-colors" x-text="stats.published">0</p>
                            </a>
                            <a href="admin-posts.php?status=draft"
                               class="px-4 py-5 no-underline hover:bg-rust-wash/40 transition-colors group">
                                <p class="text-[10px] font-sans font-bold uppercase tracking-wider text-forge-mid mb-1">Drafts</p>
                                <p class="text-2xl font-sans font-black text-forge-black group-hover:text-rust transition-colors" x-text="stats.draft">0</p>
                            </a>
                            <a href="admin-posts.php?status=stub"
                               class="px-4 py-5 no-underline hover:bg-rust-wash/40 transition-colors group">
                                <p class="text-[10px] font-sans font-bold uppercase tracking-wider text-forge-mid mb-1">Stubs</p>
                                <p class="text-2xl font-sans font-black text-forge-black group-hover:text-rust transition-colors" x-text="stats.stub">0</p>
                            </a>
                            <a href="admin-posts.php?status=unpublished"
                               class="px-4 py-5 no-underline hover:bg-rust-wash/40 transition-colors group">
                                <p class="text-[10px] font-sans font-bold uppercase tracking-wider text-forge-mid mb-1">Unpublished</p>
                                <p class="text-2xl font-sans font-black text-forge-black group-hover:text-rust transition-colors" x-text="stats.unpublished">0</p>
                            </a>
                            <a href="admin-pages.php"
                               class="px-4 py-5 no-underline hover:bg-rust-wash/40 transition-colors group col-span-2 sm:col-span-1">
                                <p class="text-[10px] font-sans font-bold uppercase tracking-wider text-forge-mid mb-1">Pages</p>
                                <p class="text-2xl font-sans font-black text-forge-black group-hover:text-rust transition-colors" x-text="stats.pages">0</p>
                            </a>
                        </div>
                    </section>

                    <!-- Needs attention | Recent work -->
                    <section class="grid grid-cols-1 lg:grid-cols-2 gap-10">
                        <!-- Needs attention -->
                        <div>
                            <h3 class="text-xs font-sans font-black uppercase tracking-wider text-forge-black mb-4 pb-2 border-b border-border">
                                Needs attention
                            </h3>

                            <template x-if="setupAllClear">
                                <p class="text-sm font-serif text-forge-dark mb-4">
                                    Setup looks complete for this site.
                                </p>
                            </template>

                            <ul class="divide-y divide-border/60 border border-border bg-card" x-show="incompleteAttention.length > 0">
                                <template x-for="item in incompleteAttention" :key="item.id">
                                    <li class="flex items-center justify-between gap-3 px-4 py-3">
                                        <span class="text-sm font-serif text-forge-dark min-w-0"
                                              :class="item.soft ? 'text-forge-mid' : ''"
                                              x-text="item.label"></span>
                                        <a :href="item.href"
                                           class="shrink-0 text-[11px] font-sans font-bold uppercase tracking-wider text-rust hover:text-rust-deep no-underline"
                                           x-text="item.hrefLabel + ' →'"></a>
                                    </li>
                                </template>
                            </ul>

                            <div x-show="exportAttention" class="mt-3 border border-dashed border-border px-4 py-3 flex items-center justify-between gap-3 bg-canvas">
                                <span class="text-xs font-serif text-forge-mid" x-text="exportAttention && exportAttention.label"></span>
                                <a href="admin-publish.php"
                                   class="shrink-0 text-[11px] font-sans font-bold uppercase tracking-wider text-rust hover:text-rust-deep no-underline">
                                    Publish →
                                </a>
                            </div>
                        </div>

                        <!-- Recent work -->
                        <div class="space-y-8">
                            <div>
                                <h3 class="text-xs font-sans font-black uppercase tracking-wider text-forge-black mb-4 pb-2 border-b border-border">
                                    Latest published
                                </h3>
                                <template x-if="latestPublished.length === 0">
                                    <p class="text-sm font-serif text-forge-mid">No published posts yet.</p>
                                </template>
                                <ul class="divide-y divide-border/60" x-show="latestPublished.length > 0">
                                    <template x-for="entry in latestPublished" :key="'pub-' + entry.id">
                                        <li>
                                            <a :href="editorHref(entry)"
                                               class="py-2.5 flex items-center gap-3 no-underline group hover:bg-black/[0.01] transition-colors">
                                                <span class="w-3 h-3 shrink-0 bg-acid" title="published"></span>
                                                <span class="text-sm font-sans font-bold text-forge-black group-hover:text-rust truncate transition-colors"
                                                      x-text="entryTitle(entry)"></span>
                                            </a>
                                        </li>
                                    </template>
                                </ul>
                            </div>

                            <div>
                                <h3 class="text-xs font-sans font-black uppercase tracking-wider text-forge-black mb-4 pb-2 border-b border-border">
                                    Latest drafts &amp; stubs
                                </h3>
                                <template x-if="latestInProgress.length === 0">
                                    <p class="text-sm font-serif text-forge-mid">No drafts or stubs in progress.</p>
                                </template>
                                <ul class="divide-y divide-border/60" x-show="latestInProgress.length > 0">
                                    <template x-for="entry in latestInProgress" :key="'wip-' + entry.id">
                                        <li>
                                            <a :href="editorHref(entry)"
                                               class="py-2.5 flex items-center gap-3 no-underline group hover:bg-black/[0.01] transition-colors">
                                                <span class="w-3 h-3 shrink-0"
                                                      :class="statusBadgeClass(entryStatus(entry))"
                                                      :title="entryStatus(entry)"></span>
                                                <span class="text-sm font-sans font-bold text-forge-black group-hover:text-rust truncate transition-colors"
                                                      x-text="entryTitle(entry)"></span>
                                            </a>
                                        </li>
                                    </template>
                                </ul>
                            </div>
                        </div>
                    </section>

                    <!-- Main pages -->
                    <section>
                        <div class="flex items-end justify-between gap-4 mb-4 pb-2 border-b border-border">
                            <h3 class="text-xs font-sans font-black uppercase tracking-wider text-forge-black">
                                Main pages
                            </h3>
                            <a href="admin-pages.php"
                               class="text-[11px] font-sans font-bold uppercase tracking-wider text-rust hover:text-rust-deep no-underline">
                                All pages →
                            </a>
                        </div>
                        <template x-if="mainPages.length === 0">
                            <div class="py-8 border border-dashed border-border bg-card text-center">
                                <p class="text-sm font-serif text-forge-dark mb-3">No pages yet for this site.</p>
                                <a :href="$store.app.adminPath('admin-editor.php', { page: 'true' })" class="pen-btn pen-btn-primary pen-btn-sm inline-flex">New Page</a>
                            </div>
                        </template>
                        <ul class="divide-y divide-border/60" x-show="mainPages.length > 0">
                            <template x-for="entry in mainPages" :key="'page-' + entry.id">
                                <li>
                                    <a :href="editorHref(entry)"
                                       class="py-3 flex items-center justify-between gap-4 no-underline group hover:bg-black/[0.01] transition-colors">
                                        <div class="flex items-center gap-3 min-w-0">
                                            <span class="w-3 h-3 shrink-0"
                                                  :class="statusBadgeClass(entryStatus(entry))"
                                                  :title="entryStatus(entry)"></span>
                                            <span class="text-sm font-sans font-bold text-forge-black group-hover:text-rust truncate transition-colors"
                                                  x-text="entryTitle(entry)"></span>
                                        </div>
                                        <span class="text-[10px] font-sans font-bold uppercase tracking-wider text-forge-mid shrink-0"
                                              x-text="entryStatus(entry) || '—'"></span>
                                    </a>
                                </li>
                            </template>
                        </ul>
                    </section>

                    <!-- Quick links -->
                    <section>
                        <h3 class="text-xs font-sans font-black uppercase tracking-wider text-forge-black mb-4 pb-2 border-b border-border">
                            Quick access
                        </h3>
                        <div class="flex flex-wrap gap-x-6 gap-y-3 text-sm font-sans font-bold uppercase tracking-wider">
                            <a href="admin-posts.php" x-show="$store.app.hasCap('write:posts')" x-cloak class="text-forge-dark hover:text-rust no-underline transition-colors">Posts</a>
                            <a href="admin-pages.php" x-show="$store.app.hasCap('write:pages')" x-cloak class="text-forge-dark hover:text-rust no-underline transition-colors">Pages</a>
                            <a :href="$store.app.adminPath('admin-editor.php')" x-show="$store.app.hasCap('write:posts')" x-cloak class="text-forge-dark hover:text-rust no-underline transition-colors">New Post</a>
                            <a href="admin-media.php" x-show="$store.app.hasCap('write:media')" x-cloak class="text-forge-dark hover:text-rust no-underline transition-colors">Media</a>
                            <a href="admin-publish.php" x-show="$store.app.hasCap('publish')" x-cloak class="text-forge-dark hover:text-rust no-underline transition-colors">Publish</a>
                            <a href="admin-settings-sites.php" x-show="$store.app.edition === 'pro' && $store.app.hasCap('manage:sites')" x-cloak class="text-forge-dark hover:text-rust no-underline transition-colors">Sites</a>
                            <a href="admin-settings-site.php" x-show="$store.app.hasAnyCap('write:seo', 'write:authors')" x-cloak class="text-forge-dark hover:text-rust no-underline transition-colors">Site Settings</a>
                            <a href="admin-settings-theme.php" x-show="$store.app.hasCap('write:theme')" x-cloak class="text-forge-dark hover:text-rust no-underline transition-colors">Themes</a>
                            <a href="admin-settings-structure.php" x-show="$store.app.isAdmin()" x-cloak class="text-forge-dark hover:text-rust no-underline transition-colors">Structure</a>
                            <a href="admin-settings-navigation.php" x-show="$store.app.hasCap('write:menus')" x-cloak class="text-forge-dark hover:text-rust no-underline transition-colors">Navigation</a>
                            <a href="admin-settings-seo.php" x-show="$store.app.hasCap('write:seo')" x-cloak class="text-forge-dark hover:text-rust no-underline transition-colors">SEO</a>
                            <a href="admin-settings-storage.php" x-show="$store.app.isAdmin()" x-cloak class="text-forge-dark hover:text-rust no-underline transition-colors">Storage</a>
                            <a href="admin-settings-ai.php" x-show="$store.app.isAdmin() && $store.app.use_ai" x-cloak
                               class="text-forge-dark hover:text-rust no-underline transition-colors">AI</a>
                        </div>
                    </section>
                </div>
            </main>

            <!-- Right site rail (>5 sites) -->
            <aside x-show="useSiteRail" x-cloak
                   class="hidden md:flex w-[220px] shrink-0 flex-col border-l border-border bg-card overflow-y-auto">
                <div class="px-4 py-4 border-b border-border sticky top-0 bg-card z-10">
                    <p class="text-[10px] font-sans font-black uppercase tracking-wider text-forge-mid">Sites</p>
                </div>
                <nav class="flex flex-col py-1" aria-label="Content sites">
                    <template x-for="s in sites" :key="'rail-' + s.id">
                        <button type="button"
                                @click="selectSite(s.id)"
                                class="text-left px-4 py-2.5 border-l-2 transition-colors focus:outline-none"
                                :class="activeSiteId === s.id
                                    ? 'border-rust bg-rust-wash/65 text-rust'
                                    : 'border-transparent text-forge-mid hover:text-forge-black hover:bg-black/[0.02]'">
                            <span class="block text-xs font-sans font-bold truncate" x-text="s.name || s.id"></span>
                            <span class="block text-[10px] font-mono text-forge-mid truncate mt-0.5" x-text="s.id"
                                  x-show="s.name"></span>
                        </button>
                    </template>
                </nav>
            </aside>
        </div>
    </div>

    <script src="js/ai-extract.js"></script>
    <!-- Footer -->
    <?php include "includes/_admin-footer.php"; ?>
