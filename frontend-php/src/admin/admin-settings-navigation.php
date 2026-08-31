<?php
/**
 * admin-settings-navigation.php
 *
 * Site Navigation Menu Builder page using the resizable 3-column admin scaffold.
 *
 * Structure mirrors admin-editor.php:
 *   - Top control bar (collapsible) with Toggle Left, Toggle Right,
 *     and (when AI is enabled) Toggle AI Assistant buttons, plus Save/Discard actions.
 *   - Left column  (~32%) — resizable; contains "Add Item" form.
 *   - Center column        — fills remaining space; contains "Menu Structure" drag-and-drop builder.
 *   - Right column (~25%) — resizable; contains Slot Options and Menu Preview cards,
 *                            with the AI Assistant accordion at the bottom.
 */

$pageTitle  = "Site Navigation (PenCMS)";
$currentSection = "navigation";
$pageScript = "settings-navigation.js";

include "includes/_admin-auth.php";
require_once "includes/_admin-icons.php";
require_once "includes/_admin-modal.php";

$penLoadMarked = true;
include "includes/_admin-head.php";
?>

<!-- Scaffold page overrides — reuse the resizable-column CSS from admin-editor.css -->
<link rel="stylesheet" href="css/admin-editor.css">
<script src="/assets/vendor/sortablejs/sortable.min.js"></script>

<body class="bg-canvas text-forge-black font-sans antialiased h-screen flex flex-col overflow-hidden"
    x-data="navigationSettings">

    <?php require "includes/_admin-icon-sprite.php"; ?>

    <!-- Top Navigation Bar -->
    <?php include "includes/_admin-header.php"; ?>

    <div class="flex flex-1 relative min-h-0 overflow-hidden">
        <!-- Collapsible Left Sidebar (nav) -->
        <?php include "includes/_admin-sidebar.php"; ?>

        <!-- Main Workspace Canvas -->
        <main class="flex-1 flex flex-col min-h-0 overflow-hidden transition-all duration-300">

            <!-- ── Toast Notifications ──────────────────────────────── -->
            <div class="fixed top-20 right-6 z-[200] space-y-2">
                <template x-for="toast in toasts" :key="toast.id">
                    <div x-transition:enter="transition ease-out duration-300"
                        x-transition:enter-start="opacity-0 translate-x-8"
                        x-transition:enter-end="opacity-100 translate-x-0"
                        x-transition:leave="transition ease-in duration-200"
                        x-transition:leave-start="opacity-100"
                        x-transition:leave-end="opacity-0"
                        class="px-4 py-3 font-sans text-xs font-bold uppercase tracking-wider shadow-md min-w-[260px] flex items-center gap-2 border"
                        :class="toast.type === 'error' ? 'bg-danger text-white border-danger' : 'bg-acid text-acid-ink border-acid'">
                        <svg x-show="toast.type !== 'error'" class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-toast-success"></use></svg>
                        <svg x-show="toast.type === 'error'" class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-toast-error"></use></svg>
                        <span x-text="toast.message"></span>
                    </div>
                </template>
            </div>

            <!-- ── Sticky Control Bar ───────────────────────────────── -->
            <div class="sticky top-0 z-[60] flex flex-col border-b-2 border-border shadow-sm shrink-0">
                <div class="bg-[#f4edea] transition-all duration-200 shrink-0"
                    :class="workspacePrefs.secondaryRailCollapsed ? 'py-1.5' : 'py-3'">
                    <div class="px-6 flex flex-col md:flex-row md:justify-between md:items-center gap-3">

                        <!-- Left: Save status + column toggles -->
                        <div class="flex items-center gap-3 min-w-0">
                            <!-- Save Status Indicator -->
                            <div class="flex items-center gap-1.5 text-[9px] text-slate-500 font-mono select-none shrink-0">
                                <span class="w-1.5 h-1.5 -mt-0.5 rounded-full transition-colors duration-300"
                                    :class="{
                                        'bg-emerald-500': saveStatus === 'saved',
                                        'bg-amber-500/80': saveStatus === 'unsaved',
                                        'bg-rust animate-pulse': saveStatus === 'saving'
                                    }"></span>
                                <span x-text="saveStatusText" class="tracking-wide"></span>
                            </div>

                            <div class="flex items-center gap-1 shrink-0">
                                <!-- Toggle Preview Button -->
                                <button class="transition-colors p-1 shrink-0 border hover:border-rust"
                                    :class="workspacePrefs.menuPreviewCollapsed ? 'text-[#817d7b] border-[#817d7b] bg-[#f4edea]' : 'text-forge-black border-border bg-card'"
                                    @click="workspacePrefs.menuPreviewCollapsed = !workspacePrefs.menuPreviewCollapsed; saveWorkspacePrefs()"
                                    title="Toggle Preview">
                                    <svg class="w-5 h-5"><use href="#icon-panel-toggle-preview"></use></svg>
                                </button>

                                <!-- Toggle Left Button -->
                                <button class="transition-colors p-1 shrink-0 border hover:border-rust"
                                    :class="workspacePrefs.leftColumnCollapsed ? 'text-[#817d7b] border-[#817d7b] bg-[#f4edea]' : 'text-forge-black border-border bg-card'"
                                    @click="workspacePrefs.leftColumnCollapsed = !workspacePrefs.leftColumnCollapsed; saveWorkspacePrefs()"
                                    title="Toggle Left">
                                    <svg class="w-5 h-5"><use href="#icon-panel-toggle-left"></use></svg>
                                </button>

                                <!-- Toggle Right Button -->
                                <button class="transition-colors p-1 shrink-0 border hover:border-rust"
                                    :class="workspacePrefs.rightColumnCollapsed ? 'text-[#817d7b] border-[#817d7b] bg-[#f4edea]' : 'text-forge-black border-border bg-card'"
                                    @click="workspacePrefs.rightColumnCollapsed = !workspacePrefs.rightColumnCollapsed; saveWorkspacePrefs()"
                                    title="Toggle Right">
                                    <svg class="w-5 h-5"><use href="#icon-panel-toggle-right"></use></svg>
                                </button>

                                <!-- Toggle AI Assistant Button (only when AI is enabled) -->
                                <button type="button"
                                    x-show="$store.app.use_ai" x-cloak
                                    class="transition-colors p-1 shrink-0 border hover:border-rust text-[#817d7b] border-transparent hover:border-border hover:bg-card"
                                    @click="workspacePrefs.aiAssistantCollapsed = !workspacePrefs.aiAssistantCollapsed; saveWorkspacePrefs()"
                                    title="Toggle AI Assistant">
                                    <svg x-show="!workspacePrefs.aiAssistantCollapsed" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-5 h-5 text-rust" fill="currentColor"><rect width="256" height="256" fill="none"/><path d="M208,144a15.78,15.78,0,0,1-10.42,14.94L146,178l-19,51.62a15.92,15.92,0,0,1-29.88,0L78,178l-51.62-19a15.92,15.92,0,0,1,0-29.88L78,110l19-51.62a15.92,15.92,0,0,1,29.88,0L146,110l51.62,19A15.78,15.78,0,0,1,208,144ZM152,48h16V64a8,8,0,0,0,16,0V48h16a8,8,0,0,0,0-16H184V16a8,8,0,0,0-16,0V32H152a8,8,0,0,0,0,16Zm88,32h-8V72a8,8,0,0,0-16,0v8h-8a8,8,0,0,0,0,16h8v8a8,8,0,0,0,16,0V96h8a8,8,0,0,0,0-16Z"/></svg>
                                    <svg x-show="workspacePrefs.aiAssistantCollapsed" class="w-5 h-5 text-rust"><use href="#icon-sparkle-ai"></use></svg>
                                </button>

                                <!-- Show Only Published (filters Add Item picker + Site Map) -->
                                <label class="flex items-center gap-2 cursor-pointer select-none ml-2 pl-2 border-l border-border/60">
                                    <input type="checkbox"
                                           x-model="showOnlyPublished"
                                           class="rounded border-border text-rust focus:ring-rust w-3.5 h-3.5">
                                    <span class="text-[10px] font-serif tracking-wider text-forge-black whitespace-nowrap">Show Only Published</span>
                                </label>
                            </div>
                        </div>

                        <!-- Right: Actions + Collapse toggle for the control bar itself -->
                        <div class="flex items-center gap-3 flex-wrap">
                            <button type="button"
                                @click="clearAllModalOpen = true"
                                class="transition-colors p-1 shrink-0 border border-danger/40 bg-card text-danger hover:border-danger hover:bg-danger/10"
                                title="Clear All Menus"
                                :disabled="saving || clearingAll">
                                <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-trash"></use></svg>
                            </button>

                            <button x-show="saveStatus === 'unsaved'" x-cloak
                                @click="discardChanges()"
                                class="pen-btn pen-btn-secondary flex items-center gap-1.5 !text-[10px] !py-0 !px-2.5 !border h-7"
                                :disabled="saving">
                                Discard
                            </button>

                            <!-- Save Button: ALWAYS SHOWN -->
                            <button @click="saveChanges()"
                                class="pen-btn pen-btn-primary flex items-center gap-2 !text-xs !py-1.5"
                                :disabled="manualSaving">
                                <svg x-show="manualSaving" x-cloak class="animate-spin h-3.5 w-3.5 text-white" fill="none"><use href="#icon-spinner"></use></svg>
                                <span x-text="manualSaving ? 'Saving...' : 'Save'"></span>
                            </button>

                            <button
                                @click="workspacePrefs.secondaryRailCollapsed = !workspacePrefs.secondaryRailCollapsed; saveWorkspacePrefs()"
                                class="hidden text-steel-muted hover:text-rust transition-colors p-1.5 shrink-0 border border-border bg-card hover:border-rust"
                                :title="workspacePrefs.secondaryRailCollapsed ? 'Expand controls' : 'Collapse controls'">
                                <svg class="w-4 h-4 transition-transform duration-200"
                                    :class="workspacePrefs.secondaryRailCollapsed ? 'rotate-180' : ''"
                                    fill="none" stroke="currentColor" stroke-width="2.5">
                                    <use href="#icon-chevron-up"></use>
                                </svg>
                            </button>
                        </div>

                    </div>
                </div>
            </div>
            <!-- ── End Control Bar ──────────────────────────────────── -->

            <!-- ── Page Header (title, description, menu-type tabs) ──── -->
            <!-- Lives in normal page flow, NOT the sticky control bar. -->
            <div class="px-6 md:px-10 pt-8 shrink-0">
                <div class="mb-8" x-show="!workspacePrefs.menuPreviewCollapsed">
                    <h1 class="text-3xl text-forge-black font-sans font-black tracking-tight mb-2 pb-2 border-b-2 border-border-weld uppercase">
                        Site Navigation
                    </h1>
                    <p class="text-forge-dark font-serif text-sm">
                        Manage your website's primary, secondary, and footer navigation menus.
                        <span class="text-forge-mid font-sans text-xs ml-1">Editing menus for: <span class="font-mono font-bold text-rust" x-text="$store.app.activeSiteId"></span></span>
                    </p>
                </div>

                <!-- Menu Type Tabs -->
                <div class="flex border-b border-border mb-0 gap-1 select-none">
                    <button @click="activeTab = 'primary'"
                            class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                            :class="activeTab === 'primary' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                        Primary
                    </button>
                    <button @click="activeTab = 'secondary'"
                            class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                            :class="activeTab === 'secondary' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                        Secondary
                    </button>
                    <button @click="activeTab = 'footer'"
                            class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                            :class="activeTab === 'footer' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                        Footer
                    </button>
                </div>
            </div>
            <!-- ── End Page Header ──────────────────────────────────── -->

            <!-- ── Full-Width Menu Preview ─────────────────────────────── -->
            <div x-show="!workspacePrefs.menuPreviewCollapsed && menus[activeTab] && menus[activeTab].length > 0" class="px-6 md:px-10 py-3">
                <div class="flex flex-col">
                    <div class="flex items-center justify-between mb-0 cursor-pointer select-none pl-5"
                        @click="workspacePrefs.menuPreviewCardCollapsed = !workspacePrefs.menuPreviewCardCollapsed; saveWorkspacePrefs()">
                        <span class="text-[10px] font-black uppercase tracking-wider text-rust">Preview</span>
                        <svg class="w-3 h-3 text-steel-muted transition-transform duration-200" :class="workspacePrefs.menuPreviewCardCollapsed ? '-rotate-90' : ''" fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-chevron-down"></use></svg>
                    </div>
                    <div x-show="!workspacePrefs.menuPreviewCardCollapsed" x-transition>
                        <div class="min-h-[60px] py-2 pl-5">
                            <nav class="w-full">
                                <ul class="flex flex-row flex-wrap gap-x-3 gap-y-2 text-xs font-mono text-steel-muted">
                                    <template x-for="item in menus[activeTab].filter(x => !x.parent_id).slice().sort((a, b) => a.order - b.order)" :key="item.id">
                                        <li>
                                            <span class="self-start relative px-2 py-0.5 bg-canvas border border-border whitespace-nowrap inline-flex items-center" x-text="item.label"></span>
                                            <template x-if="childrenOf(item.id).length > 0">
                                                <ul class="mt-1 space-y-1">
                                                    <template x-for="(child, index) in childrenOf(item.id)" :key="child.id">
                                                        <li class="relative pl-3 ml-3">
                                                            <!-- Vertical rail descending INTO the child from above -->
                                                            <span class="absolute -top-1 -left-px w-px bg-border"
                                                                  :class="index === childrenOf(item.id).length - 1 ? 'h-3' : 'bottom-0'"
                                                                  aria-hidden="true"></span>
                                                            <!-- Horizontal arm reaching from the rail to the child chip -->
                                                            <span class="absolute top-2 -left-px h-px w-3 bg-border" aria-hidden="true"></span>
                                                            <span class="relative px-2 py-0.5 bg-canvas border border-border whitespace-nowrap inline-flex items-center" x-text="child.label"></span>
                                                        </li>
                                                    </template>
                                                </ul>
                                            </template>
                                        </li>
                                    </template>
                                </ul>
                            </nav>
                        </div>
                    </div>
                </div>
            </div>
            <!-- ── End Full-Width Menu Preview ──────────────────────────── -->

            <!-- ── 3-Column Content Area ────────────────────────────── -->
            <div class="px-6 md:px-10 py-3 flex-1 min-h-0 overflow-hidden">
                <div class="flex flex-col lg:flex-row gap-8 lg:gap-0 items-stretch h-full"
                    :style="'--left-width: ' + workspacePrefs.sidebarWidth + '%; --right-width: ' + workspacePrefs.rightColumnWidth + '%'">

                    <!-- ============================================================ -->
                    <!-- CENTER COLUMN — Primary workspace; fills remaining width     -->
                    <!-- Rendered first in DOM; order-3 keeps it visually in center  -->
                    <!-- ============================================================ -->
                    <div class="w-full resizable-workspace lg:order-3 lg:px-6 lg:h-full lg:flex lg:flex-col lg:min-h-0 lg:overflow-hidden"
                        :class="{
                            'workspace-both-collapsed lg:!px-0': workspacePrefs.leftColumnCollapsed && workspacePrefs.rightColumnCollapsed,
                            'workspace-left-collapsed lg:!pl-0': workspacePrefs.leftColumnCollapsed && !workspacePrefs.rightColumnCollapsed,
                            'workspace-right-collapsed lg:!pr-0': !workspacePrefs.leftColumnCollapsed && workspacePrefs.rightColumnCollapsed
                        }">

                        <!-- Loading Spinner -->
                        <template x-if="loading">
                            <div class="flex flex-col items-center justify-center py-20 select-none bg-card border-2 border-border p-6 min-h-[300px]">
                                <svg class="animate-spin h-10 w-10 text-rust mb-4" fill="none" viewBox="0 0 24 24">
                                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                                </svg>
                                <span class="text-sm font-mono text-forge-dark">Retrieving navigation data...</span>
                            </div>
                        </template>

                        <!-- Add Item Card (fixed-height, sized by content) -->
                        <div class="pen-card p-4 bg-card flex flex-col"
                             :class="!workspacePrefs.addItemCardCollapsed ? 'gap-3 lg:shrink-0' : 'gap-0 lg:shrink-0'">
                            <div class="flex items-center justify-between border-border cursor-pointer select-none"
                                :class="workspacePrefs.addItemCardCollapsed ? 'pb-0 mb-0 border-b-0' : 'border-b pb-2 mb-1'"
                                @click="workspacePrefs.addItemCardCollapsed = !workspacePrefs.addItemCardCollapsed; saveWorkspacePrefs()">
                                <span class="text-[10px] font-black uppercase tracking-wider text-rust">Add Item</span>
                                <svg class="w-3 h-3 text-steel-muted transition-transform duration-200" :class="workspacePrefs.addItemCardCollapsed ? '-rotate-90' : ''" fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-chevron-down"></use></svg>
                            </div>

                            <div class="flex flex-col xl:flex-row gap-4 min-h-0" x-show="!workspacePrefs.addItemCardCollapsed" x-transition>
                                <!-- Left Column (25%): Stacked Tab List -->
                                <div role="tablist" aria-label="Add Item Type" class="w-full xl:w-[25%] flex flex-col gap-1.5 select-none border-b xl:border-b-0 xl:border-r border-border pb-3 xl:pb-0 xl:pr-3 xl:-ml-[14px] shrink-0 justify-start">
                                    <button role="tab"
                                            :aria-selected="addType === 'page'"
                                            @click="addType = 'page'"
                                            class="w-full text-left py-1.5 pl-2.5 pr-2.5 xl:pl-3 xl:pr-1 text-[10px] font-bold uppercase tracking-wider border-l-2 transition-all duration-150"
                                            :class="addType === 'page' ? 'border-rust bg-rust-wash/65 text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                                        Page
                                    </button>
                                    <button role="tab"
                                            :aria-selected="addType === 'post'"
                                            @click="addType = 'post'"
                                            class="w-full text-left py-1.5 pl-2.5 pr-2.5 xl:pl-3 xl:pr-1 text-[10px] font-bold uppercase tracking-wider border-l-2 transition-all duration-150"
                                            :class="addType === 'post' ? 'border-rust bg-rust-wash/65 text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                                        Post
                                    </button>
                                    <button role="tab"
                                            :aria-selected="addType === 'categories'"
                                            @click="addType = 'categories'"
                                            class="w-full text-left py-1.5 pl-2.5 pr-2.5 xl:pl-3 xl:pr-1 text-[10px] font-bold uppercase tracking-wider border-l-2 transition-all duration-150"
                                            :class="addType === 'categories' ? 'border-rust bg-rust-wash/65 text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                                        <span x-text="taxonomyTabLabel()"></span>
                                    </button>
                                    <button role="tab"
                                            :aria-selected="addType === 'system'"
                                            @click="addType = 'system'"
                                            class="w-full text-left py-1.5 pl-2.5 pr-2.5 xl:pl-3 xl:pr-1 text-[10px] font-bold uppercase tracking-wider border-l-2 transition-all duration-150"
                                            :class="addType === 'system' ? 'border-rust bg-rust-wash/65 text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                                        System
                                    </button>
                                    <button role="tab"
                                            :aria-selected="addType === 'custom'"
                                            @click="addType = 'custom'"
                                            class="w-full text-left py-1.5 pl-2.5 pr-2.5 xl:pl-3 xl:pr-1 text-[10px] font-bold uppercase tracking-wider border-l-2 transition-all duration-150"
                                            :class="addType === 'custom' ? 'border-rust bg-rust-wash/65 text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                                        Custom Link
                                    </button>
                                    <button role="tab"
                                            :aria-selected="addType === 'label'"
                                            @click="addType = 'label'"
                                            class="w-full text-left py-1.5 pl-2.5 pr-2.5 xl:pl-3 xl:pr-1 text-[10px] font-bold uppercase tracking-wider border-l-2 transition-all duration-150"
                                            :class="addType === 'label' ? 'border-rust bg-rust-wash/65 text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                                        Label
                                    </button>
                                </div>

                                <!-- Right Column (75%): Tab Content & Actions -->
                                <div role="tabpanel" aria-label="Add Item Parameters" class="w-full xl:w-[75%] xl:pl-3 flex flex-col justify-between min-h-0">
                                    <!-- Fields -->
                                    <div class="space-y-4 flex-1">
                                        <!-- Label Input -->
                                        <div>
                                            <label class="block text-[10px] font-bold uppercase tracking-wider text-steel-muted mb-1">Item Label</label>
                                            <input type="text" x-model="newItem.label" placeholder="e.g. Services" class="pen-input w-full text-xs">
                                        </div>

                                        <!-- Link Type: Content Picker (Page or Post tab) -->
                                        <div x-show="addType === 'page' || addType === 'post'" class="space-y-2">
                                            <label class="block text-[10px] font-bold uppercase tracking-wider text-steel-muted mb-1">Select <span x-text="addType === 'page' ? 'Page' : 'Post'"></span></label>
                                            <input type="text" x-model="searchQuery" placeholder="Search..." class="pen-input w-full text-xs mb-2">
                                            <div class="max-h-24 overflow-y-auto border border-border/80 rounded bg-canvas flex flex-col min-h-0">
                                                <template x-for="p in filteredPages()">
                                                    <div @click="selectPage(p)"
                                                         class="px-2 py-1 cursor-pointer hover:bg-rust-wash hover:text-rust text-[11px] font-sans flex justify-between items-center transition-colors duration-150"
                                                         :class="newItem.content_slug === p.id ? 'bg-rust-wash text-rust font-bold' : 'text-forge-dark'"
                                                         :title="buildTreeItemTooltip(p.frontmatter || {}, false)">
                                                        <span class="truncate" x-text="p.frontmatter.title || p.title"></span>
                                                        <span x-show="addType === 'post'"
                                                              class="text-[8px] uppercase tracking-wider font-bold text-steel-muted ml-2 shrink-0"
                                                              x-text="p.frontmatter.category || p.frontmatter.type || 'general'"></span>
                                                    </div>
                                                </template>
                                                <template x-if="filteredPages().length === 0">
                                                    <div class="px-2 py-2 text-center text-[11px] text-steel-muted font-serif">No <span x-text="addType === 'page' ? 'pages' : 'posts'"></span> match search.</div>
                                                </template>
                                            </div>
                                            <!-- Current Selection Indicator -->
                                            <template x-if="newItem.content_slug">
                                                <div class="mt-2 text-[10px] font-mono text-rust bg-rust-wash px-2 py-1 border border-border-accent/40 rounded flex justify-between items-center select-none">
                                                    <span>Link target: <strong x-text="newItem.content_slug"></strong></span>
                                                    <button @click="newItem.content_slug = ''" class="hover:text-forge-black font-bold ml-2">Clear</button>
                                                </div>
                                            </template>
                                        </div>

                                        <!-- Link Type: Categories / Taxonomy Picker -->
                                        <div x-show="addType === 'categories'" class="space-y-2">
                                            <!-- Vocabulary Select Dropdown -->
                                            <div>
                                                <label class="block text-[10px] font-bold uppercase tracking-wider text-steel-muted mb-1">Select Vocabulary</label>
                                                <select x-model="selectedVocabKey" @change="onSelectedVocabChange()" class="pen-input w-full text-xs bg-card">
                                                    <template x-for="v in allVocabularies()" :key="v.key">
                                                        <option :value="v.key" x-text="v.label" :selected="selectedVocabKey === v.key"></option>
                                                    </template>
                                                </select>
                                            </div>

                                            <!-- Term List Selector -->
                                            <div class="space-y-2">
                                                <label class="block text-[10px] font-bold uppercase tracking-wider text-steel-muted mb-1">Select Term</label>
                                                <div class="max-h-24 overflow-y-auto border border-border/80 rounded bg-canvas flex flex-col min-h-0">
                                                    <template x-for="term in getSelectedVocabTerms()" :key="term">
                                                        <div @click="selectTaxonomyTerm(term)"
                                                             class="px-2 py-1 cursor-pointer hover:bg-rust-wash hover:text-rust text-[11px] font-sans flex justify-between items-center transition-colors duration-150"
                                                             :class="newItem.content_slug === `${selectedVocabKey}/${term}` ? 'bg-rust-wash text-rust font-bold' : 'text-forge-dark'">
                                                            <span class="truncate" x-text="term"></span>
                                                        </div>
                                                    </template>
                                                    <template x-if="getSelectedVocabTerms().length === 0">
                                                        <div class="px-2 py-2 text-center text-[11px] text-steel-muted font-serif">No terms listed in this vocabulary.</div>
                                                    </template>
                                                </div>

                                                <!-- Free-form term: always visible when uncontrolled + empty -->
                                                <div x-show="isSelectedVocabUncontrolled() && getSelectedVocabTerms().length === 0" class="space-y-1.5" x-cloak>
                                                    <label class="block text-[10px] font-bold uppercase tracking-wider text-steel-muted">Custom term</label>
                                                    <div class="flex items-center border border-border bg-canvas focus-within:border-rust transition-colors duration-150 h-8">
                                                        <input type="text"
                                                               x-model="customTermInput"
                                                               @keydown.enter.prevent="applyCustomTaxonomyTerm()"
                                                               :placeholder="isSelectedVocabHierarchical() ? 'Parent / Child' : 'tag or custom category word'"
                                                               class="bg-transparent text-xs px-3 py-1 focus:outline-none flex-1 min-w-0">
                                                        <button type="button" @click="applyCustomTaxonomyTerm()" class="px-2.5 h-full text-[10px] font-bold uppercase tracking-wider text-forge-dark hover:text-rust border-l border-border hover:bg-black/[0.02] flex items-center justify-center shrink-0" title="Use custom term">
                                                            + Add
                                                        </button>
                                                    </div>
                                                </div>

                                                <!-- Free-form term: accordion when uncontrolled + has listed terms -->
                                                <div x-show="isSelectedVocabUncontrolled() && getSelectedVocabTerms().length > 0" class="space-y-1" x-cloak>
                                                    <button type="button"
                                                            @click="customTermDrawerOpen = !customTermDrawerOpen"
                                                            class="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-steel-muted hover:text-rust transition-colors">
                                                        <span class="inline-block transition-transform duration-200" :class="customTermDrawerOpen ? 'rotate-45' : ''">+</span>
                                                        <span>Custom term</span>
                                                    </button>
                                                    <div x-show="customTermDrawerOpen" x-transition class="space-y-1.5">
                                                        <div class="flex items-center border border-border bg-canvas focus-within:border-rust transition-colors duration-150 h-8">
                                                            <input type="text"
                                                                   x-model="customTermInput"
                                                                   @keydown.enter.prevent="applyCustomTaxonomyTerm()"
                                                                   :placeholder="isSelectedVocabHierarchical() ? 'Parent / Child' : 'e.g. Term'"
                                                                   class="bg-transparent text-xs px-3 py-1 focus:outline-none flex-1 min-w-0">
                                                            <button type="button" @click="applyCustomTaxonomyTerm()" class="px-2.5 h-full text-[10px] font-bold uppercase tracking-wider text-forge-dark hover:text-rust border-l border-border hover:bg-black/[0.02] flex items-center justify-center shrink-0" title="Use custom term">
                                                                + Add
                                                            </button>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                            <!-- Current Selection Indicator -->
                                            <template x-if="newItem.content_type === 'taxonomy' && newItem.content_slug">
                                                <div class="mt-2 text-[10px] font-mono text-rust bg-rust-wash px-2 py-1 border border-border-accent/40 rounded flex flex-col gap-0.5 select-none">
                                                    <div class="flex justify-between items-center">
                                                        <span>Link target: <strong x-text="newItem.content_slug"></strong></span>
                                                        <button type="button" @click="newItem.content_slug = ''; newItem.url = ''" class="hover:text-forge-black font-bold ml-2">Clear</button>
                                                    </div>
                                                    <template x-if="newItem.url">
                                                        <span class="text-steel-muted">Preview: <strong class="text-forge-dark" x-text="newItem.url"></strong></span>
                                                    </template>
                                                </div>
                                            </template>
                                        </div>

                                        <!-- Link Type: System Pages Picker -->
                                        <div x-show="addType === 'system'" class="space-y-2">
                                            <label class="block text-[10px] font-bold uppercase tracking-wider text-steel-muted mb-1">Select System Page</label>
                                            <div class="border border-border/80 rounded bg-canvas flex flex-col min-h-0">
                                                <template x-for="sys in systemPages" :key="sys.id">
                                                    <div @click="selectSystemPage(sys)"
                                                         class="px-2 py-1 cursor-pointer hover:bg-rust-wash hover:text-rust text-[11px] font-sans flex justify-between items-center transition-colors duration-150"
                                                         :class="newItem.content_slug === sys.id ? 'bg-rust-wash text-rust font-bold' : 'text-forge-dark'">
                                                        <div class="flex flex-col min-w-0">
                                                            <span class="font-bold truncate" x-text="sys.title"></span>
                                                            <span class="text-[8px] text-steel-muted font-mono truncate" x-text="sys.url"></span>
                                                        </div>
                                                    </div>
                                                </template>
                                            </div>
                                            <!-- Current Selection Indicator -->
                                            <template x-if="newItem.content_type === 'system' && newItem.content_slug">
                                                <div class="mt-2 text-[10px] font-mono text-rust bg-rust-wash px-2 py-1 border border-border-accent/40 rounded flex justify-between items-center select-none">
                                                    <span>Link target: <strong x-text="newItem.content_slug"></strong></span>
                                                    <button @click="newItem.content_slug = ''; newItem.url = ''" class="hover:text-forge-black font-bold ml-2">Clear</button>
                                                </div>
                                            </template>
                                        </div>

                                        <!-- Link Type: Custom Link -->
                                        <div x-show="addType === 'custom'">
                                            <label class="block text-[10px] font-bold uppercase tracking-wider text-steel-muted mb-1">Custom URL</label>
                                            <input type="text" x-model="newItem.url" placeholder="e.g. /blog/contact or https://example.com" class="pen-input w-full text-xs">
                                        </div>

                                        <!-- Link Type: Label/Separator info -->
                                        <div x-show="addType === 'label'" class="text-xs text-steel-muted font-serif py-1 select-none">
                                            Separator labels group links and do not have an active link target
                                        </div>

                                    </div>

                                    <!-- Parent label + Open in New Tab on label row; select + Add to Menu below -->
                                    <div class="flex flex-col gap-1.5 pt-3 mt-auto">
                                        <div class="flex items-center justify-between gap-3">
                                            <label class="text-[10px] font-bold uppercase tracking-wider text-steel-muted">Parent</label>
                                            <label x-show="addType !== 'label'" class="flex items-center gap-2 cursor-pointer select-none shrink-0" x-cloak>
                                                <span class="text-[10px] font-serif tracking-wider text-forge-black whitespace-nowrap">Open in New Tab</span>
                                                <input type="checkbox" x-model="newItem.open_in_new_tab" class="rounded border-border text-rust focus:ring-rust w-4 h-4">
                                            </label>
                                        </div>
                                        <div class="flex items-center gap-3">
                                            <select x-model="newItem.parent_id" class="pen-input flex-1 min-w-0 text-xs bg-card">
                                                <option value="">Top level</option>
                                                <template x-for="parent in menus[activeTab].filter(i => !i.parent_id)" :key="parent.id">
                                                    <option :value="parent.id" x-text="parent.label"></option>
                                                </template>
                                            </select>
                                            <button @click="addItem()" class="pen-btn pen-btn-primary px-6 py-2 text-xs font-bold uppercase tracking-wider shrink-0">
                                                Add to Menu
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Menu Structure Card -->
                        <div x-show="!loading" class="px-0 py-6 bg-transparent flex flex-col gap-4 lg:flex-1 lg:min-h-0 lg:overflow-hidden">
                            <div class="flex items-center justify-between border-b border-border pb-2">
                                <h2 class="text-xs font-black uppercase tracking-widest text-forge-black select-none">
                                    Structure
                                    <span class="text-steel-muted font-bold normal-case tracking-normal ml-1" x-text="'— ' + activeTab.charAt(0).toUpperCase() + activeTab.slice(1) + ' Menu'"></span>
                                </h2>
                            </div>

                            <!-- Empty State -->
                            <div x-show="menus[activeTab].length === 0" class="flex flex-col items-center justify-center py-12 text-center select-none">
                                <svg class="w-12 h-12 text-steel-muted/60 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 6h16M4 12h16M4 18h16" />
                                </svg>
                                <h3 class="text-sm font-bold uppercase tracking-wider text-forge-black mb-1">No items configured</h3>
                                <p class="text-xs text-steel-muted font-serif max-w-sm mb-4">Click "Add to Menu" on the left panel to begin structuring the active menu.</p>
                            </div>

                            <!-- Drag-and-Drop Sortable List -->
                             <div :id="`menu-list-${activeTab}`" class="space-y-2.5 min-h-[100px] lg:flex-1 lg:overflow-y-auto pr-1">
                                 <template x-for="(item, index) in menus[activeTab]" :key="item.id">
                                     <div :data-id="item.id"
                                          class="flex items-stretch gap-2 transition-all duration-150"
                            :class="item.parent_id ? 'ml-8 border-l-4 border-l-rust/35 pl-2' : ''">

                                          <!-- Drag Handle (outside the card) -->
                                          <div x-show="editingItemId !== item.id" class="drag-handle cursor-move text-steel-muted hover:text-rust p-0.5 transition-colors duration-150 shrink-0 self-center">
                                              <svg class="w-4 h-4 fill-current" viewBox="0 0 24 24">
                                                  <path d="M11 18c0 1.1-.9 2-2 2s-2-.9-2-2 .9-2 2-2 2 .9 2 2zm-2-8c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0-6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm6 4c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"/>
                                              </svg>
                                          </div>

                                          <!-- Card: contains badge/slug + label, plus a vertically centered actions column -->
                                          <div x-show="editingItemId !== item.id" class="flex-grow min-w-0 border border-border/60 rounded bg-transparent flex flex-row relative">

                                              <!-- L-shaped nesting sub-indicator -->
                                              <div x-show="item.parent_id" class="absolute left-[14px] top-[18px] -ml-3 text-rust/45 select-none pointer-events-none">
                                                  <svg class="w-3.5 h-3.5 stroke-current fill-none" stroke-width="2.5" viewBox="0 0 24 24">
                                                      <path d="M5 4v10h10" />
                                                  </svg>
                                              </div>

                                              <!-- Text column (badge/slug + label) -->
                                              <div class="flex-1 min-w-0 flex flex-col gap-0 py-1.5 pr-2.5"
                                                   :class="item.parent_id ? 'pl-4' : 'pl-3'">
                                                  <!-- Top line: badge + slug -->
                                                  <div class="flex items-center gap-1.5 min-w-0">
                                                      <!-- Target Badge -->
                                                      <span class="pl-0 pr-1.5 py-0.5 text-[8px] font-mono uppercase tracking-wider bg-transparent text-steel-muted shrink-0"
                                                            x-text="getItemTargetLabel(item)">
                                                      </span>
                                                      <!-- Path preview (public static URL) -->
                                                      <span class="text-[9px] font-mono text-steel-muted truncate max-w-[200px]"
                                                            x-text="getItemPublicPath(item)">
                                                      </span>
                                                  </div>

                                                  <!-- Bottom line: item label -->
                                                  <span class="text-[11px] font-bold text-forge-dark truncate block" x-text="item.label"></span>
                                              </div>

                                              <!-- Inline actions: indent, outdent, edit, delete — vertically centered, evenly distributed -->
                                              <div class="flex items-center justify-evenly gap-0.5 px-2 border-l border-border/20 text-forge-mid shrink-0">
                                                  <!-- Indent -->
                                                  <button @click="indentItem(activeTab, item.id)"
                                                          :disabled="!canIndent(activeTab, item.id)"
                                                          class="p-0.5 hover:text-rust disabled:opacity-20 disabled:pointer-events-none transition-colors duration-150"
                                                          title="Indent (nest item)">
                                                      <svg class="w-3.5 h-3.5 fill-none stroke-current" stroke-width="2" viewBox="0 0 24 24">
                                                          <path d="M4 12h12m0 0l-4-4m4 4l-4 4" />
                                                      </svg>
                                                  </button>
                                                  <!-- Outdent -->
                                                  <button @click="outdentItem(activeTab, item.id)"
                                                          :disabled="!canOutdent(activeTab, item.id)"
                                                          class="p-0.5 hover:text-rust disabled:opacity-20 disabled:pointer-events-none transition-colors duration-150"
                                                          title="Outdent (make top level)">
                                                      <svg class="w-3.5 h-3.5 fill-none stroke-current transform -scale-x-100" stroke-width="2" viewBox="0 0 24 24">
                                                          <path d="M4 12h12m0 0l-4-4m4 4l-4 4" />
                                                      </svg>
                                                  </button>
                                                  <!-- Edit -->
                                                  <button @click="startEdit(item)"
                                                          class="p-0.5 hover:text-rust transition-colors duration-150"
                                                          title="Edit inline">
                                                      <svg class="w-3.5 h-3.5 fill-none stroke-current" stroke-width="2" viewBox="0 0 24 24">
                                                          <path d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                                                      </svg>
                                                  </button>
                                                  <!-- Delete -->
                                                  <button @click="deleteItem(activeTab, item.id)"
                                                          class="p-0.5 hover:text-danger transition-colors duration-150"
                                                          title="Delete item">
                                                      <svg class="w-3.5 h-3.5 fill-none stroke-current" stroke-width="2" viewBox="0 0 24 24">
                                                          <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                                      </svg>
                                                  </button>
                                              </div>

                                              <!-- Stacked up/down chevrons on the extreme right -->
                                              <div class="flex flex-col items-center justify-center gap-0 px-1 border-l border-border/20 text-forge-mid shrink-0 self-stretch">
                                                  <button @click.stop="moveItem(activeTab, index, -1)"
                                                          class="p-0.5 hover:text-rust transition-colors disabled:opacity-20 disabled:pointer-events-none"
                                                          :disabled="index === 0" title="Move Up">
                                                      <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" stroke-width="3"><use href="#icon-chevron-up"></use></svg>
                                                  </button>
                                                  <button @click.stop="moveItem(activeTab, index, 1)"
                                                          class="p-0.5 hover:text-rust transition-colors disabled:opacity-20 disabled:pointer-events-none"
                                                          :disabled="index === menus[activeTab].length - 1"
                                                          title="Move Down">
                                                      <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" stroke-width="3"><use href="#icon-chevron-down"></use></svg>
                                                  </button>
                                              </div>
                                          </div>

                                         <!-- Edit Mode Form -->
                                         <template x-if="editingItemId === item.id && editingItemData">
                                             <div class="p-4 bg-canvas/40 border-t border-border flex flex-col gap-3">
                                                 <div class="flex flex-wrap items-center gap-3">
                                                     <!-- Label -->
                                                     <div class="flex-1 min-w-[200px]">
                                                         <label class="block text-[10px] font-bold uppercase tracking-wider text-steel-muted mb-1">Item Label</label>
                                                         <input type="text" x-model="editingItemData.label" class="pen-input w-full text-xs bg-card">
                                                     </div>
                                                     <!-- Type Selection -->
                                                     <div>
                                                         <label class="block text-[10px] font-bold uppercase tracking-wider text-steel-muted mb-1">Type</label>
                                                         <select x-model="editingItemData.target_type" @change="onEditTargetTypeChange()" class="pen-input text-xs bg-card">
                                                             <option value="page">Page</option>
                                                             <option value="post">Post</option>
                                                             <option value="taxonomy">Category / Tag</option>
                                                             <option value="system">System Page</option>
                                                             <option value="custom">Custom URL</option>
                                                             <option value="label">Label Only</option>
                                                         </select>
                                                     </div>
                                                     <!-- Option checkbox -->
                                                     <div class="flex items-center h-full pt-5" x-show="editingItemData?.target_type !== 'label'">
                                                         <label class="flex items-center gap-2 cursor-pointer select-none">
                                                             <input type="checkbox" x-model="editingItemData.open_in_new_tab" class="rounded border-border text-rust focus:ring-rust w-4 h-4">
                                                             <span class="text-xs uppercase font-bold tracking-wider text-forge-black">New Tab</span>
                                                         </label>
                                                     </div>
                                                 </div>

                                                 <!-- Target specific forms -->
                                                 <div class="pt-2 border-t border-border/40">
                                                     <template x-if="editingItemData?.target_type === 'page' || editingItemData?.target_type === 'post'">
                                                         <div class="flex flex-col gap-2">
                                                             <label class="text-[10px] font-bold uppercase tracking-wider text-steel-muted">
                                                                 Link <span x-text="editingItemData?.target_type === 'page' ? 'Page' : 'Post'"></span>
                                                             </label>
                                                             <select x-model="editingItemData.content_slug" class="pen-input text-xs bg-card w-full">
                                                                 <option value="" x-text="editingItemData?.target_type === 'page' ? '-- Choose page --' : '-- Choose post --'"></option>
                                                                 <template x-for="p in editFilteredPages()">
                                                                     <option :value="p.id" :selected="editingItemData?.content_slug === p.id"
                                                                             x-text="p.frontmatter.title || p.title"></option>
                                                                 </template>
                                                             </select>
                                                         </div>
                                                     </template>
                                                     <template x-if="editingItemData?.target_type === 'taxonomy'">
                                                         <div class="flex flex-col gap-2">
                                                             <label class="text-[10px] font-bold uppercase tracking-wider text-steel-muted">Link Category / Term</label>
                                                             <select x-model="editingItemData.content_slug" @change="editingItemData.url = (() => { const slug = termToCategorySlug(editingItemData.content_slug); return slug ? '/category/' + slug + '/' : ''; })()" class="pen-input text-xs bg-card w-full">
                                                                 <option value="">-- Choose term --</option>
                                                                 <template x-for="v in allVocabularies()" :key="v.key">
                                                                     <template x-for="term in (taxonomy.raw.vocabularies[v.key].terms || [])" :key="term">
                                                                         <option :value="`${v.key}/${term}`" :selected="editingItemData?.content_slug === `${v.key}/${term}`" x-text="`${v.label}: ${term}`"></option>
                                                                     </template>
                                                                 </template>
                                                             </select>
                                                         </div>
                                                     </template>
                                                     <template x-if="editingItemData?.target_type === 'system'">
                                                         <div class="flex flex-col gap-2">
                                                             <label class="text-[10px] font-bold uppercase tracking-wider text-steel-muted">Link System Page</label>
                                                             <select x-model="editingItemData.content_slug" @change="editingItemData.url = systemPages.find(x => x.id === editingItemData.content_slug).url" class="pen-input text-xs bg-card w-full">
                                                                 <option value="">-- Choose system page --</option>
                                                                 <template x-for="sys in systemPages" :key="sys.id">
                                                                     <option :value="sys.id" :selected="editingItemData?.content_slug === sys.id" x-text="sys.title"></option>
                                                                 </template>
                                                             </select>
                                                         </div>
                                                     </template>
                                                     <template x-if="editingItemData?.target_type === 'custom'">
                                                         <div>
                                                             <label class="block text-[10px] font-bold uppercase tracking-wider text-steel-muted mb-1">Custom Link URL</label>
                                                             <input type="text" x-model="editingItemData.url" class="pen-input w-full text-xs bg-card" placeholder="e.g. /blog/contact or https://example.com">
                                                         </div>
                                                     </template>
                                                     <template x-if="editingItemData?.target_type === 'label'">
                                                         <span class="text-xs text-steel-muted font-serif">Label items act as separators and carry no link URL.</span>
                                                     </template>
                                                 </div>

                                                 <div class="flex justify-end gap-2 mt-1 select-none">
                                                     <button @click="cancelEdit()" class="pen-btn px-3 py-1.5 text-[10px] uppercase font-bold tracking-wider hover:bg-canvas">Cancel</button>
                                                     <button @click="saveEdit(activeTab, item.id)" class="pen-btn pen-btn-primary px-3 py-1.5 text-[10px] uppercase font-bold tracking-wider">Done</button>
                                                 </div>
                                             </div>
                                         </template>

                                     </div>
                                 </template>
                             </div>
                         </div>
                    </div>
                    <!-- ── End Center Column ── -->

                    <!-- ============================================================ -->
                    <!-- DRAG HANDLE — Right divider                                  -->
                    <!-- ============================================================ -->
                    <div x-show="!workspacePrefs.rightColumnCollapsed"
                        class="hidden lg:block w-3 -mx-1.5 cursor-ew-resize self-stretch relative z-50 group select-none lg:order-4"
                        @mousedown="startResizeRight($event)">
                        <div class="absolute inset-y-0 left-1/2 -translate-x-1/2 transition-all duration-150"
                            :class="isDraggingRightColumn ? 'w-[3px] bg-rust' : 'w-px bg-border/40 group-hover:w-[3px] group-hover:bg-rust'">
                        </div>
                    </div>

                    <!-- ============================================================ -->
                    <!-- RIGHT COLUMN (~25%) — sticky; AI Assistant in lower portion  -->
                    <!-- ============================================================ -->
                    <aside x-show="!workspacePrefs.rightColumnCollapsed"
                        class="w-full lg:w-[25%] resizable-right-column nav-resizable-right-column lg:flex lg:flex-col lg:gap-4 lg:h-full lg:min-h-0 lg:order-5 lg:pl-6 lg:z-30 lg:overflow-hidden">

                        <!-- ── Advanced Settings Card ── -->
                        <div class="pen-card p-4 bg-card flex flex-col lg:shrink-0"
                             :class="!workspacePrefs.advancedSettingsCardCollapsed ? 'gap-3' : 'gap-0'">
                            <div class="flex items-center justify-between border-border cursor-pointer select-none"
                                :class="workspacePrefs.advancedSettingsCardCollapsed ? 'pb-0 mb-0 border-b-0' : 'border-b pb-2 mb-1'"
                                @click="workspacePrefs.advancedSettingsCardCollapsed = !workspacePrefs.advancedSettingsCardCollapsed; saveWorkspacePrefs()">
                                <span class="text-[10px] font-black uppercase tracking-wider text-rust">Advanced</span>
                                <svg class="w-3 h-3 text-steel-muted transition-transform duration-200" :class="workspacePrefs.advancedSettingsCardCollapsed ? '-rotate-90' : ''" fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-chevron-down"></use></svg>
                            </div>
                            
                            <div class="space-y-3" x-show="!workspacePrefs.advancedSettingsCardCollapsed" x-transition>
                                <div>
                                    <label class="block text-[10px] font-bold uppercase tracking-wider text-steel-muted mb-1">
                                        Custom Menu Identifier Class
                                    </label>
                                    <input type="text" 
                                           x-model="slotClasses[activeTab]" 
                                           placeholder="e.g. primary-nav-custom" 
                                           class="pen-input w-full text-xs">
                                    <span class="text-[9px] text-steel-muted font-serif block mt-1 leading-normal select-none">
                                        Optional: Bespoke themes can use this CSS class or ID to target the active menu for layout or custom styling.
                                    </span>
                                </div>
                                
                                <button @click="saveSlotOptions()" 
                                        class="pen-btn pen-btn-primary w-full py-2 text-[10px] uppercase font-bold tracking-wider">
                                    Save ID
                                </button>
                            </div>
                        </div>

                        <!-- ── AI Assistant Accordion (lower portion of right column) ── -->
                        <div x-show="$store.app.use_ai" x-cloak
                            x-data="aiSidebar"
                            data-ai-accordion-card
                            class="pt-4 scroll-mt-[160px] lg:flex lg:flex-col lg:min-h-0"
                            :class="!workspacePrefs.aiAssistantCollapsed ? 'lg:flex-1 lg:overflow-hidden' : ''">

                            <!-- Accordion Trigger -->
                            <div class="flex items-center justify-between border-b border-border cursor-pointer select-none pb-2 w-full text-left font-sans outline-none focus-visible:ring-2 focus-visible:ring-rust"
                                @click="workspacePrefs.aiAssistantCollapsed = !workspacePrefs.aiAssistantCollapsed; saveWorkspacePrefs()">
                                <span class="text-[10px] font-black uppercase tracking-wider text-rust">AI</span>
                                <div class="flex items-center gap-2" @click.stop>
                                    <!-- New Conversation -->
                                    <button type="button" @click="newConversation()"
                                        x-show="!workspacePrefs.aiAssistantCollapsed"
                                        class="text-forge-mid hover:text-rust p-1 transition-colors"
                                        title="New Conversation">
                                        <?php admin_icon('plus'); ?>
                                    </button>
                                    <!-- Clear Conversation -->
                                    <button type="button" @click="newConversation()"
                                        x-show="!workspacePrefs.aiAssistantCollapsed"
                                        class="text-forge-mid hover:text-rust p-1 transition-colors"
                                        title="Clear Conversation">
                                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-clear-conversation"></use></svg>
                                    </button>
                                    <!-- Chevron toggle -->
                                    <svg @click="workspacePrefs.aiAssistantCollapsed = !workspacePrefs.aiAssistantCollapsed; saveWorkspacePrefs()"
                                        class="w-3 h-3 text-steel-muted transition-transform duration-200"
                                        :class="workspacePrefs.aiAssistantCollapsed ? '-rotate-90' : ''"
                                        fill="none" stroke="currentColor" stroke-width="2.5">
                                        <use href="#icon-chevron-down"></use>
                                    </svg>
                                </div>
                            </div>

                            <!-- Accordion Body -->
                            <div class="relative flex flex-col gap-3 pt-2 lg:flex-1 lg:min-h-0 lg:overflow-hidden"
                                x-show="!workspacePrefs.aiAssistantCollapsed" x-cloak x-transition>

                                <!-- Chat messages container -->
                                <div id="ai-chat-messages-container"
                                    class="flex-1 min-h-0 overflow-y-auto px-2 py-3 space-y-1 scrollbar-thin">

                                    <!-- Vault unlock form (shown before vault is unlocked) -->
                                    <template x-if="!vaultUnlocked">
                                        <div class="flex flex-col items-start gap-1">
                                            <div class="bg-white border border-border/60 text-forge-black self-start rounded-r-md rounded-bl-md p-3.5 max-w-[90%] shadow-sm w-full">
                                                <p class="text-xs font-serif leading-relaxed mb-3">Unlock your vault to use AI.</p>
                                                <form @submit.prevent="unlockVault()" class="flex flex-col gap-2">
                                                    <div class="relative w-full">
                                                        <input :type="showVaultPassword ? 'text' : 'password'"
                                                            x-model="vaultPassword" x-ref="vaultPasswordInput"
                                                            placeholder="Enter vault password"
                                                            class="pen-input !text-xs !py-1.5 w-full pr-8"
                                                            :disabled="isUnlockingVault">
                                                        <button type="button"
                                                            @click="showVaultPassword = !showVaultPassword"
                                                            class="absolute right-2 top-1/2 -translate-y-1/2 text-forge-mid hover:text-forge-black transition-colors"
                                                            tabindex="-1">
                                                            <template x-if="showVaultPassword">
                                                                <svg class="w-4 h-4"><use href="#icon-eye-outline"></use></svg>
                                                            </template>
                                                            <template x-if="!showVaultPassword">
                                                                <?php admin_icon('eye-slash', 'w-4 h-4'); ?>
                                                            </template>
                                                        </button>
                                                    </div>
                                                    <template x-if="vaultUnlockError">
                                                        <p class="text-[10px] text-danger font-bold" x-text="vaultUnlockError"></p>
                                                    </template>
                                                    <button type="submit"
                                                        class="pen-btn pen-btn-primary pen-btn-sm w-full flex justify-center items-center gap-2"
                                                        :disabled="isUnlockingVault || !vaultPassword.trim()">
                                                        <template x-if="isUnlockingVault">
                                                            <svg class="w-3 h-3 animate-spin" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-refresh-sync"></use></svg>
                                                        </template>
                                                        <template x-if="!isUnlockingVault">
                                                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-lock-closed"></use></svg>
                                                        </template>
                                                        <span x-text="isUnlockingVault ? 'Unlocking...' : 'Unlock Vault'"></span>
                                                    </button>
                                                </form>
                                            </div>
                                        </div>
                                    </template>

                                    <!-- Messages list -->
                                    <template x-for="(msg, index) in messages" :key="index">
                                        <div class="flex w-full"
                                            :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
                                            <div class="group"
                                                :class="msg.role === 'user'
                                                    ? 'bg-[#f0e9e6] text-forge-black rounded-l-md rounded-br-md max-w-[85%] text-[15px] leading-tight font-serif px-2.5 py-2.5'
                                                    : (msg.role === 'tool' || (msg.tool_calls && msg.tool_calls.length > 0 && !msg.content))
                                                        ? 'bg-transparent text-forge-black max-w-[92%] -ml-1 text-sm leading-relaxed font-sans !py-0 !mt-1'
                                                        : 'bg-transparent text-forge-black max-w-[92%] -ml-1 text-sm leading-relaxed font-sans py-2.5 !mt-3'">
                                                <div x-html="renderMsg(msg, index === messages.length - 1)"></div>

                                                <!-- Action controls for AI responses -->
                                                <div x-show="msg.role === 'assistant' && msg.content"
                                                    class="mt-2 pt-2 flex justify-start gap-2.5 select-none opacity-0 group-hover:opacity-100 transition-opacity">
                                                    <button @click="copyToClipboard(msg.content, index)"
                                                        class="transition-colors"
                                                        :class="copiedMessageIndex === index ? 'text-green-600' : 'text-forge-mid hover:text-rust'"
                                                        title="Copy to Clipboard">
                                                        <template x-if="copiedMessageIndex !== index">
                                                            <svg class="w-4 h-4"><use href="#icon-copy-clipboard"></use></svg>
                                                        </template>
                                                        <template x-if="copiedMessageIndex === index">
                                                            <svg class="w-4 h-4"><use href="#icon-checkmark-thin"></use></svg>
                                                        </template>
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    </template>
                                </div>

                                <!-- Streaming indicator -->
                                <div x-show="streaming" x-cloak class="flex justify-start mt-2 mb-1 px-0">
                                    <span class="text-[10px] font-mono text-rust animate-pulse font-bold" x-text="streamingWord"></span>
                                </div>

                                <!-- Handoff CTAs: pinned outside the scroll area so they stay visible -->
                                <template x-if="pendingOutgoingHandoff">
                                    <div class="shrink-0 px-2">
                                        <div class="mb-1 px-2.5 py-2.5 border border-border/70 bg-[#f4edea] text-[11px] font-sans leading-snug">
                                            <div class="flex items-start justify-between gap-2 mb-2">
                                                <p class="font-bold uppercase tracking-wide text-[11px] text-forge-mid">Go to <span x-text="outgoingHandoffLabel()"></span>?</p>
                                                <button type="button" @click="cancelOutgoingHandoff()" :disabled="_handoffConfirmBusy || _handoffNavigating" class="shrink-0 p-0.5 text-forge-mid hover:text-rust transition-colors disabled:opacity-50" title="Dismiss" aria-label="Dismiss">
                                                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" d="M6 6l12 12M18 6L6 18"></path></svg>
                                                </button>
                                            </div>
                                            <p class="font-serif text-[13px] leading-snug text-forge-mid mb-2" x-text="pendingOutgoingHandoff.goal"></p>
                                            <div x-show="isOriginDirty()" class="mb-2 space-y-1.5 border-t border-border/50 pt-2">
                                                <p class="text-[10px] font-bold uppercase tracking-wide text-rust">Unsaved changes on this page</p>
                                                <label class="flex items-center gap-2 cursor-pointer text-forge-mid">
                                                    <input type="radio" class="accent-rust" name="pen-handoff-save-nav" value="save" x-model="pendingOutgoingHandoff.saveChoice">
                                                    <span>Save first</span>
                                                </label>
                                                <label class="flex items-center gap-2 cursor-pointer text-forge-mid">
                                                    <input type="radio" class="accent-rust" name="pen-handoff-save-nav" value="discard" x-model="pendingOutgoingHandoff.saveChoice">
                                                    <span>Leave without saving</span>
                                                </label>
                                            </div>
                                            <div class="mt-2 flex gap-2 justify-end">
                                                <button type="button" @click="cancelOutgoingHandoff()" :disabled="_handoffConfirmBusy || _handoffNavigating" class="pen-btn pen-btn-sm" title="Stay on this page">Cancel</button>
                                                <button type="button" @click="confirmOutgoingHandoff()" :disabled="_handoffConfirmBusy || _handoffNavigating || (isOriginDirty() && !pendingOutgoingHandoff.saveChoice)" class="pen-btn pen-btn-primary pen-btn-sm" title="Leave and open the other surface">Continue</button>
                                            </div>
                                        </div>
                                    </div>
                                </template>
                                <template x-if="incomingHandoff">
                                    <div class="shrink-0 px-2">
                                        <div class="mb-1 px-2.5 py-2.5 border border-border/70 bg-[#f4edea] text-[11px] font-sans leading-snug">
                                            <div class="flex items-start justify-between gap-2 mb-2">
                                                <p class="font-bold uppercase tracking-wide text-[11px] text-forge-mid min-w-0">Continuing from <span x-text="handoffFromLabel()"></span></p>
                                                <button type="button" @click="dismissIncomingHandoff()" class="shrink-0 p-0.5 text-forge-mid hover:text-rust transition-colors" title="Dismiss" aria-label="Dismiss">
                                                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" d="M6 6l12 12M18 6L6 18"></path></svg>
                                                </button>
                                            </div>
                                            <p class="font-serif text-[13px] leading-snug text-forge-mid mb-2" x-text="incomingHandoff.goal"></p>
                                            <div class="mt-2 flex gap-2 justify-end">
                                                <button type="button" @click="continueIncomingHandoff()" :disabled="streaming" class="pen-btn pen-btn-primary pen-btn-sm" title="Send this goal to the assistant">Continue?</button>
                                            </div>
                                        </div>
                                    </div>
                                </template>

                                <!-- Prompt input area -->
                                <div class="pt-1 pb-3 select-none shrink-0">
                                    <div class="relative border border-border focus-within:border-rust transition-colors p-2 bg-white">
                                        <div class="relative flex items-end gap-2">
                                            <textarea id="ai-prompt-textarea" x-model="prompt"
                                                @input="autoGrow($event.target)"
                                                @keydown.enter="handleEnterKey($event)"
                                                @paste="handlePaste($event)"
                                                placeholder="Write a message..."
                                                class="flex-1 min-w-0 min-h-[44px] max-h-[320px] resize-none text-base font-serif bg-transparent p-1 leading-snug placeholder-forge-mid/60 text-forge-black border-0 outline-none focus:!border-0 focus:!ring-0"
                                                :disabled="streaming"></textarea>

                                            <div class="flex items-center gap-1.5 shrink-0 self-end">
                                                <!-- Stop button (while streaming) -->
                                                <button x-show="streaming" type="button" @click="cleanup()"
                                                    class="p-1.5 text-danger hover:bg-danger-wash rounded-full transition-colors"
                                                    title="Stop Generation">
                                                    <svg class="w-5 h-5 animate-pulse" fill="currentColor"><use href="#icon-stop-square"></use></svg>
                                                </button>
                                                <!-- Send button -->
                                                <button x-show="!streaming" type="button" @click="sendPrompt()"
                                                    :disabled="!prompt.trim()"
                                                    class="p-1.5 text-rust disabled:text-steel-muted hover:bg-rust-wash rounded-full transition-colors cursor-pointer disabled:cursor-not-allowed"
                                                    title="Send Prompt">
                                                    <svg class="w-5 h-5 text-rust"><use href="#icon-send-plane"></use></svg>
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <!-- ── End AI Accordion Body ── -->

                        </div>
                        <!-- ── End AI Assistant Accordion ── -->

                    </aside>
                    <!-- ── End Right Column ── -->

                    <!-- ============================================================ -->
                    <!-- DRAG HANDLE — Left divider                                   -->
                    <!-- ============================================================ -->
                    <div x-show="!workspacePrefs.leftColumnCollapsed"
                        class="hidden lg:block w-3 -mx-1.5 cursor-ew-resize self-stretch relative z-50 group select-none lg:order-2"
                        @mousedown="startResizeLeft($event)">
                        <div class="absolute inset-y-0 left-1/2 -translate-x-1/2 transition-all duration-150"
                            :class="isDraggingLeftColumn ? 'w-[3px] bg-rust' : 'w-px bg-border/40 group-hover:w-[3px] group-hover:bg-rust'">
                        </div>
                    </div>

                    <!-- ============================================================ -->
                    <!-- LEFT COLUMN (~32%) — sticky; add sidebar cards here          -->
                    <!-- ============================================================ -->
                    <aside x-show="!workspacePrefs.leftColumnCollapsed"
                        class="w-full lg:w-[32%] resizable-left-column nav-resizable-left-column lg:flex lg:flex-col lg:gap-6 lg:h-full lg:min-h-0 lg:order-1 lg:pr-6 lg:z-30 lg:overflow-hidden">

                        <!-- ── Left Column Content: Site Map / Page Tree ── -->
                        <div class="pen-card p-4 bg-card flex flex-col select-none lg:h-full lg:min-h-0 lg:overflow-hidden"
                             :class="!workspacePrefs.pageTreeCardCollapsed ? 'gap-3' : 'gap-0 lg:h-auto lg:min-h-0 lg:overflow-visible'">
                            <div class="flex items-center justify-between border-border cursor-pointer select-none shrink-0"
                                 :class="workspacePrefs.pageTreeCardCollapsed ? 'pb-0 mb-0 border-b-0' : 'border-b pb-2 mb-1'"
                                 @click="workspacePrefs.pageTreeCardCollapsed = !workspacePrefs.pageTreeCardCollapsed; saveWorkspacePrefs()">
                                 <span class="text-[10px] font-black uppercase tracking-wider text-rust">Site Map</span>
                                 <svg class="w-3 h-3 text-steel-muted transition-transform duration-200" :class="workspacePrefs.pageTreeCardCollapsed ? '-rotate-90' : ''" fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-chevron-down"></use></svg>
                            </div>

                            <div class="flex flex-col gap-3 flex-1 lg:min-h-0 lg:overflow-hidden" x-show="!workspacePrefs.pageTreeCardCollapsed" x-transition>

                            <!-- Loading skeleton -->
                            <div x-show="!pageTreeLoaded" class="flex flex-col gap-2 py-2 animate-pulse">
                                <div class="h-3 bg-border/40 rounded w-1/3"></div>
                                <div class="h-3 bg-border/40 rounded w-2/3"></div>
                                <div class="h-3 bg-border/40 rounded w-1/2"></div>
                            </div>

                            <!-- Tree Content -->
                            <div x-show="pageTreeLoaded" x-cloak class="flex-1 overflow-y-auto max-h-[500px] lg:max-h-none text-[11px] font-sans text-forge-black flex flex-col gap-0.5 pr-1">
                                
                                <!-- Home row -->
                                <div class="flex items-center gap-0.5 py-[1px] px-1 text-forge-black font-bold select-none">
                                    <span class="w-4 flex justify-center shrink-0 text-forge-black text-[8px]">▪</span>
                                    <span class="truncate">Home</span>
                                    <span class="ml-auto shrink-0 inline-flex items-center gap-0.5">
                                        <button type="button"
                                            x-show="isSystemInMenus('home')" x-cloak
                                            @click.stop="removeTreeItemFromActiveTab('system:home')"
                                            class="text-rust cursor-pointer group/rm inline-flex items-center justify-center p-0.5 -m-0.5"
                                            title="Remove from active menu"
                                            aria-label="Remove from active menu">
                                            <svg class="w-2.5 h-2.5 group-hover/rm:hidden group-focus-visible/rm:hidden"><use href="#icon-checkmark-thin"></use></svg>
                                            <span class="hidden group-hover/rm:inline group-focus-visible/rm:inline text-[10px] leading-none font-bold" aria-hidden="true">×</span>
                                        </button>
                                        <button type="button"
                                            x-show="!isInActiveTab('system:home')" x-cloak
                                            @click.stop="addTreeSystem('home')"
                                            class="text-rust cursor-pointer inline-flex items-center justify-center p-0.5 -m-0.5"
                                            title="Add to active menu"
                                            aria-label="Add to active menu">
                                            <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-plus-thin"></use></svg>
                                        </button>
                                    </span>
                                </div>

                                <!-- Pages branch -->
                                <div x-data="{ open: false }" class="flex flex-col">
                                    <button @click="open = !open" class="flex items-center justify-between py-[1px] px-1 w-full hover:bg-canvas/60 text-left transition-colors font-bold group/btn">
                                        <div class="flex items-center gap-0.5 min-w-0">
                                            <span class="w-4 flex justify-center text-steel-muted/80 shrink-0 transition-transform duration-200" :class="open ? 'rotate-90' : ''">
                                                <svg class="w-3 h-3 fill-current" viewBox="0 0 24 24"><path d="M8.59,16.59L13.17,12L8.59,7.41L10,6L16,12L10,18L8.59,16.59Z"/></svg>
                                            </span>
                                            <span class="truncate">Pages</span>
                                        </div>
                                        <span class="text-[9px] text-steel-muted/70 bg-border/30 px-1 py-0.5 rounded font-mono" x-text="treePages().length">0</span>
                                    </button>
                                    <div x-show="open" x-transition class="pl-2.5 ml-1.5 border-l border-border/30 flex flex-col gap-0.5 mt-0.5">
                                        <template x-for="p in treePages()" :key="p.id">
                                            <div class="flex items-center gap-0.5 py-[1px] px-1 hover:bg-canvas/60 text-steel-muted min-w-0">
                                                <span class="w-3 flex justify-center text-[8px] text-steel-muted/40 shrink-0">•</span>
                                                <span class="truncate" :title="p.tooltip" x-text="p.label"></span>
                                                <span class="ml-auto shrink-0 inline-flex items-center gap-0.5">
                                                    <button type="button"
                                                        x-show="isContentInMenus(p.id)" x-cloak
                                                        @click.stop="removeTreeItemFromActiveTab('content:' + p.id)"
                                                        class="text-rust cursor-pointer group/rm inline-flex items-center justify-center p-0.5 -m-0.5"
                                                        title="Remove from active menu"
                                                        aria-label="Remove from active menu">
                                                        <svg class="w-2.5 h-2.5 group-hover/rm:hidden group-focus-visible/rm:hidden"><use href="#icon-checkmark-thin"></use></svg>
                                                        <span class="hidden group-hover/rm:inline group-focus-visible/rm:inline text-[10px] leading-none font-bold" aria-hidden="true">×</span>
                                                    </button>
                                                    <button type="button"
                                                        x-show="!isInActiveTab('content:' + p.id)" x-cloak
                                                        @click.stop="addTreeContent(p, 'page')"
                                                        class="text-rust cursor-pointer inline-flex items-center justify-center p-0.5 -m-0.5"
                                                        title="Add to active menu"
                                                        aria-label="Add to active menu">
                                                        <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-plus-thin"></use></svg>
                                                    </button>
                                                </span>
                                            </div>
                                        </template>
                                        <div x-show="treePages().length === 0" class="py-[1px] px-1 text-steel-muted/60">No pages</div>
                                    </div>
                                </div>

                                <!-- Posts branch -->
                                <div x-data="{ open: false }" class="flex flex-col">
                                    <button @click="open = !open" class="flex items-center justify-between py-[1px] px-1 w-full hover:bg-canvas/60 text-left transition-colors font-bold group/btn">
                                        <div class="flex items-center gap-0.5 min-w-0">
                                            <span class="w-4 flex justify-center text-steel-muted/80 shrink-0 transition-transform duration-200" :class="open ? 'rotate-90' : ''">
                                                <svg class="w-3 h-3 fill-current" viewBox="0 0 24 24"><path d="M8.59,16.59L13.17,12L8.59,7.41L10,6L16,12L10,18L8.59,16.59Z"/></svg>
                                            </span>
                                            <span class="truncate">Posts</span>
                                        </div>
                                        <span class="text-[9px] text-steel-muted/70 bg-border/30 px-1 py-0.5 rounded font-mono" x-text="treePosts().length">0</span>
                                    </button>
                                    <div x-show="open" x-transition class="pl-2.5 ml-1.5 border-l border-border/30 flex flex-col gap-0.5 mt-0.5">
                                        <template x-for="p in treePosts()" :key="p.id">
                                            <div class="flex items-center gap-0.5 py-[1px] px-1 hover:bg-canvas/60 text-steel-muted min-w-0">
                                                <span class="w-3 flex justify-center text-[8px] text-steel-muted/40 shrink-0">•</span>
                                                <span class="truncate" :title="p.tooltip" x-text="p.label"></span>
                                                <span class="ml-auto shrink-0 inline-flex items-center gap-0.5">
                                                    <button type="button"
                                                        x-show="isContentInMenus(p.id)" x-cloak
                                                        @click.stop="removeTreeItemFromActiveTab('content:' + p.id)"
                                                        class="text-rust cursor-pointer group/rm inline-flex items-center justify-center p-0.5 -m-0.5"
                                                        title="Remove from active menu"
                                                        aria-label="Remove from active menu">
                                                        <svg class="w-2.5 h-2.5 group-hover/rm:hidden group-focus-visible/rm:hidden"><use href="#icon-checkmark-thin"></use></svg>
                                                        <span class="hidden group-hover/rm:inline group-focus-visible/rm:inline text-[10px] leading-none font-bold" aria-hidden="true">×</span>
                                                    </button>
                                                    <button type="button"
                                                        x-show="!isInActiveTab('content:' + p.id)" x-cloak
                                                        @click.stop="addTreeContent(p, 'post')"
                                                        class="text-rust cursor-pointer inline-flex items-center justify-center p-0.5 -m-0.5"
                                                        title="Add to active menu"
                                                        aria-label="Add to active menu">
                                                        <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-plus-thin"></use></svg>
                                                    </button>
                                                </span>
                                            </div>
                                        </template>
                                        <div x-show="treePosts().length === 0" class="py-[1px] px-1 text-steel-muted/60">No posts</div>
                                    </div>
                                </div>

                                <!-- Promoted Primary Vocabulary branch -->
                                <template x-if="treePrimaryVocabulary()">
                                    <div x-data="{ open: false }" class="flex flex-col">
                                        <button @click="open = !open" class="flex items-center justify-between py-[1px] px-1 w-full hover:bg-canvas/60 text-left transition-colors font-bold group/btn select-none">
                                            <div class="flex items-center gap-0.5 min-w-0">
                                                <span class="w-4 flex justify-center text-steel-muted/80 shrink-0 transition-transform duration-200" :class="open ? 'rotate-90' : ''">
                                                    <svg class="w-3 h-3 fill-current" viewBox="0 0 24 24"><path d="M8.59,16.59L13.17,12L8.59,7.41L10,6L16,12L10,18L8.59,16.59Z"/></svg>
                                                </span>
                                                <span class="truncate text-forge-black text-[11px] font-bold" x-text="treePrimaryVocabulary().label"></span>
                                            </div>
                                            
                                            <!-- Uncontrolled/Dynamic Info tooltip icon -->
                                            <template x-if="!treePrimaryVocabulary().controlled">
                                                <div class="relative group/tooltip shrink-0 ml-1 mr-1" @click.stop>
                                                    <span class="text-rust hover:text-rust-wash cursor-help select-none font-bold text-[9px] border border-rust/40 rounded-full w-3.5 h-3.5 inline-flex items-center justify-center">ℹ</span>
                                                    <div class="absolute bottom-full right-0 mb-2 hidden group-hover/tooltip:block w-40 bg-zinc-800 text-white text-[9px] leading-tight p-2 rounded shadow-lg z-[100] pointer-events-none text-center normal-case font-normal">
                                                        This category can also contain dynamic terms not listed here
                                                        <div class="w-1.5 h-1.5 bg-zinc-800 rotate-45 absolute top-full right-2 -mt-[3px]"></div>
                                                    </div>
                                                </div>
                                            </template>
                                        </button>
                                        
                                        <!-- Terms list -->
                                        <div x-show="open" x-transition class="pl-2.5 ml-1.5 border-l border-border/30 flex flex-col gap-0.5 mt-0.5">
                                            <template x-if="treePrimaryVocabulary().type === 'hierarchical'">
                                                <div class="flex flex-col gap-0.5">
                                                    <template x-for="node in treePrimaryVocabulary().terms" :key="node.fullPath">
                                                        <div x-data="{ openSub: false }" class="flex flex-col">
                                                            <div class="flex items-center gap-0.5 py-[1px] px-1 min-w-0 select-none w-full text-steel-muted font-normal"
                                                                :class="node.children && node.children.length > 0 ? 'cursor-pointer hover:bg-canvas/50' : ''"
                                                                @click="if (node.children && node.children.length > 0) openSub = !openSub">
                                                                <span class="w-3 flex justify-center shrink-0 text-steel-muted/60"
                                                                    :class="node.children && node.children.length > 0 ? (openSub ? 'rotate-90 transition-transform duration-200' : 'transition-transform duration-200') : 'text-[8px] text-steel-muted/40'">
                                                                    <template x-if="node.children && node.children.length > 0">
                                                                        <svg class="w-2 h-2 fill-current" viewBox="0 0 24 24"><path d="M8.59,16.59L13.17,12L8.59,7.41L10,6L16,12L10,18L8.59,16.59Z"/></svg>
                                                                    </template>
                                                                    <template x-if="!node.children || node.children.length === 0">
                                                                        <span>•</span>
                                                                    </template>
                                                                </span>
                                                                <span class="truncate text-steel-muted" :class="!node.isExplicit ? 'text-steel-muted/50' : ''" :title="node.fullPath" x-text="node.name"></span>
                                                                <span class="ml-auto shrink-0 inline-flex items-center gap-0.5">
                                                                    <button type="button"
                                                                        x-show="isTaxonomyTermInMenus(treePrimaryVocabulary().key, node.fullPath)" x-cloak
                                                                        @click.stop="removeTreeItemFromActiveTab('taxonomy:' + treePrimaryVocabulary().key + '/' + node.fullPath)"
                                                                        class="text-rust cursor-pointer group/rm inline-flex items-center justify-center p-0.5 -m-0.5"
                                                                        title="Remove from active menu"
                                                                        aria-label="Remove from active menu">
                                                                        <svg class="w-2.5 h-2.5 group-hover/rm:hidden group-focus-visible/rm:hidden"><use href="#icon-checkmark-thin"></use></svg>
                                                                        <span class="hidden group-hover/rm:inline group-focus-visible/rm:inline text-[10px] leading-none font-bold" aria-hidden="true">×</span>
                                                                    </button>
                                                                    <button type="button"
                                                                        x-show="!isInActiveTab('taxonomy:' + treePrimaryVocabulary().key + '/' + node.fullPath)" x-cloak
                                                                        @click.stop="addTreeTaxonomy(treePrimaryVocabulary().key, node.fullPath, node.name)"
                                                                        class="text-rust cursor-pointer inline-flex items-center justify-center p-0.5 -m-0.5"
                                                                        title="Add to active menu"
                                                                        aria-label="Add to active menu">
                                                                        <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-plus-thin"></use></svg>
                                                                    </button>
                                                                </span>
                                                            </div>
                                                            <!-- SubNode children -->
                                                            <template x-if="node.children && node.children.length > 0">
                                                                <div x-show="openSub" x-transition class="pl-2 ml-1 border-l border-border/10 flex flex-col gap-0.5">
                                                                    <template x-for="subNode in node.children" :key="subNode.fullPath">
                                                                        <div x-data="{ openSub2: false }" class="flex flex-col">
                                                                            <div class="flex items-center gap-0.5 py-[1px] px-1 min-w-0 select-none w-full text-steel-muted font-normal"
                                                                                :class="subNode.children && subNode.children.length > 0 ? 'cursor-pointer hover:bg-canvas/50' : ''"
                                                                                @click="if (subNode.children && subNode.children.length > 0) openSub2 = !openSub2">
                                                                                <span class="w-3 flex justify-center shrink-0 text-steel-muted/60"
                                                                                    :class="subNode.children && subNode.children.length > 0 ? (openSub2 ? 'rotate-90 transition-transform duration-200' : 'transition-transform duration-200') : 'text-[8px] text-steel-muted/40'">
                                                                                    <template x-if="subNode.children && subNode.children.length > 0">
                                                                                        <svg class="w-2 h-2 fill-current" viewBox="0 0 24 24"><path d="M8.59,16.59L13.17,12L8.59,7.41L10,6L16,12L10,18L8.59,16.59Z"/></svg>
                                                                                    </template>
                                                                                    <template x-if="!subNode.children || subNode.children.length === 0">
                                                                                        <span>•</span>
                                                                                    </template>
                                                                                </span>
                                                                                <span class="truncate text-steel-muted" :class="!subNode.isExplicit ? 'text-steel-muted/50' : ''" :title="subNode.fullPath" x-text="subNode.name"></span>
                                                                                <span class="ml-auto shrink-0 inline-flex items-center gap-0.5">
                                                                                    <button type="button"
                                                                                        x-show="isTaxonomyTermInMenus(treePrimaryVocabulary().key, subNode.fullPath)" x-cloak
                                                                                        @click.stop="removeTreeItemFromActiveTab('taxonomy:' + treePrimaryVocabulary().key + '/' + subNode.fullPath)"
                                                                                        class="text-rust cursor-pointer group/rm inline-flex items-center justify-center p-0.5 -m-0.5"
                                                                                        title="Remove from active menu"
                                                                                        aria-label="Remove from active menu">
                                                                                        <svg class="w-2.5 h-2.5 group-hover/rm:hidden group-focus-visible/rm:hidden"><use href="#icon-checkmark-thin"></use></svg>
                                                                                        <span class="hidden group-hover/rm:inline group-focus-visible/rm:inline text-[10px] leading-none font-bold" aria-hidden="true">×</span>
                                                                                    </button>
                                                                                    <button type="button"
                                                                                        x-show="!isInActiveTab('taxonomy:' + treePrimaryVocabulary().key + '/' + subNode.fullPath)" x-cloak
                                                                                        @click.stop="addTreeTaxonomy(treePrimaryVocabulary().key, subNode.fullPath, subNode.name)"
                                                                                        class="text-rust cursor-pointer inline-flex items-center justify-center p-0.5 -m-0.5"
                                                                                        title="Add to active menu"
                                                                                        aria-label="Add to active menu">
                                                                                        <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-plus-thin"></use></svg>
                                                                                    </button>
                                                                                </span>
                                                                            </div>
                                                                            <!-- Level 3 -->
                                                                            <template x-if="subNode.children && subNode.children.length > 0">
                                                                                <div x-show="openSub2" x-transition class="pl-2 ml-1 border-l border-border/10 flex flex-col gap-0.5">
                                                                                    <template x-for="leafNode in subNode.children" :key="leafNode.fullPath">
                                                                                        <div class="flex items-center gap-0.5 py-[1px] px-1 min-w-0 hover:bg-canvas/50 text-steel-muted select-none">
                                                                                            <span class="w-3 flex justify-center text-[8px] text-steel-muted/40 shrink-0">•</span>
                                                                                            <span class="truncate" :class="!leafNode.isExplicit ? 'text-steel-muted/50' : ''" :title="leafNode.fullPath" x-text="leafNode.name"></span>
                                                                                            <span class="ml-auto shrink-0 inline-flex items-center gap-0.5">
                                                                                                <button type="button"
                                                                                                    x-show="isTaxonomyTermInMenus(treePrimaryVocabulary().key, leafNode.fullPath)" x-cloak
                                                                                                    @click.stop="removeTreeItemFromActiveTab('taxonomy:' + treePrimaryVocabulary().key + '/' + leafNode.fullPath)"
                                                                                                    class="text-rust cursor-pointer group/rm inline-flex items-center justify-center p-0.5 -m-0.5"
                                                                                                    title="Remove from active menu"
                                                                                                    aria-label="Remove from active menu">
                                                                                                    <svg class="w-2.5 h-2.5 group-hover/rm:hidden group-focus-visible/rm:hidden"><use href="#icon-checkmark-thin"></use></svg>
                                                                                                    <span class="hidden group-hover/rm:inline group-focus-visible/rm:inline text-[10px] leading-none font-bold" aria-hidden="true">×</span>
                                                                                                </button>
                                                                                                <button type="button"
                                                                                                    x-show="!isInActiveTab('taxonomy:' + treePrimaryVocabulary().key + '/' + leafNode.fullPath)" x-cloak
                                                                                                    @click.stop="addTreeTaxonomy(treePrimaryVocabulary().key, leafNode.fullPath, leafNode.name)"
                                                                                                    class="text-rust cursor-pointer inline-flex items-center justify-center p-0.5 -m-0.5"
                                                                                                    title="Add to active menu"
                                                                                                    aria-label="Add to active menu">
                                                                                                    <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-plus-thin"></use></svg>
                                                                                                </button>
                                                                                            </span>
                                                                                        </div>
                                                                                    </template>
                                                                                </div>
                                                                            </template>
                                                                        </div>
                                                                    </template>
                                                                </div>
                                                            </template>
                                                        </div>
                                                    </template>
                                                </div>
                                            </template>
                                            <template x-if="treePrimaryVocabulary().type !== 'hierarchical'">
                                                <div class="flex flex-col gap-0.5">
                                                    <template x-for="term in treePrimaryVocabulary().terms" :key="term">
                                                        <div class="flex items-center gap-0.5 py-[1px] px-1 hover:bg-canvas/50 text-steel-muted min-w-0 select-none">
                                                            <span class="w-3 flex justify-center text-[8px] text-steel-muted/40 shrink-0">•</span>
                                                            <span class="truncate" :title="term" x-text="term"></span>
                                                            <span class="ml-auto shrink-0 inline-flex items-center gap-0.5">
                                                                <button type="button"
                                                                    x-show="isTaxonomyTermInMenus(treePrimaryVocabulary().key, term)" x-cloak
                                                                    @click.stop="removeTreeItemFromActiveTab('taxonomy:' + treePrimaryVocabulary().key + '/' + term)"
                                                                    class="text-rust cursor-pointer group/rm inline-flex items-center justify-center p-0.5 -m-0.5"
                                                                    title="Remove from active menu"
                                                                    aria-label="Remove from active menu">
                                                                    <svg class="w-2.5 h-2.5 group-hover/rm:hidden group-focus-visible/rm:hidden"><use href="#icon-checkmark-thin"></use></svg>
                                                                    <span class="hidden group-hover/rm:inline group-focus-visible/rm:inline text-[10px] leading-none font-bold" aria-hidden="true">×</span>
                                                                </button>
                                                                <button type="button"
                                                                    x-show="!isInActiveTab('taxonomy:' + treePrimaryVocabulary().key + '/' + term)" x-cloak
                                                                    @click.stop="addTreeTaxonomy(treePrimaryVocabulary().key, term, term)"
                                                                    class="text-rust cursor-pointer inline-flex items-center justify-center p-0.5 -m-0.5"
                                                                    title="Add to active menu"
                                                                    aria-label="Add to active menu">
                                                                    <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-plus-thin"></use></svg>
                                                                </button>
                                                            </span>
                                                        </div>
                                                    </template>
                                                    <div x-show="treePrimaryVocabulary().terms.length === 0" class="py-[1px] px-1 text-steel-muted/60">No listed terms</div>
                                                </div>
                                            </template>
                                        </div>
                                    </div>
                                </template>

                                <!-- Other vocabularies branch -->
                                <div x-data="{ open: false }" class="flex flex-col">
                                    <button @click="open = !open" class="flex items-center justify-between py-[1px] px-1 w-full hover:bg-canvas/60 text-left transition-colors font-bold group/btn">
                                        <div class="flex items-center gap-0.5 min-w-0">
                                            <span class="w-4 flex justify-center text-steel-muted/80 shrink-0 transition-transform duration-200" :class="open ? 'rotate-90' : ''">
                                                <svg class="w-3 h-3 fill-current" viewBox="0 0 24 24"><path d="M8.59,16.59L13.17,12L8.59,7.41L10,6L16,12L10,18L8.59,16.59Z"/></svg>
                                            </span>
                                            <span class="truncate">Taxonomy</span>
                                        </div>
                                    </button>
                                    
                                    <div x-show="open" x-transition class="pl-2.5 ml-1.5 border-l border-border/30 flex flex-col gap-0.5 mt-0.5">
                                        <template x-for="vocab in treeVocabularies()" :key="vocab.key">
                                            <div x-data="{ openVocab: false }" class="flex flex-col">
                                                <!-- Vocabulary Header -->
                                                <div class="flex items-center justify-between py-[1px] px-1 hover:bg-canvas/60 w-full text-left transition-colors font-bold min-w-0 cursor-pointer select-none" @click="openVocab = !openVocab">
                                                    <div class="flex items-center gap-0.5 min-w-0 flex-1 py-[1px] text-left">
                                                        <span class="w-3 flex justify-center text-steel-muted/80 shrink-0 transition-transform duration-200" :class="openVocab ? 'rotate-90' : ''">
                                                            <svg class="w-2.5 h-2.5 fill-current" viewBox="0 0 24 24"><path d="M8.59,16.59L13.17,12L8.59,7.41L10,6L16,12L10,18L8.59,16.59Z"/></svg>
                                                        </span>
                                                        <span class="truncate text-forge-black font-bold" x-text="vocab.label"></span>
                                                    </div>
                                                    
                                                    <!-- Uncontrolled/Dynamic Info tooltip icon -->
                                                    <template x-if="!vocab.controlled">
                                                        <div class="relative group/tooltip shrink-0 ml-1 mr-1" @click.stop>
                                                            <span class="text-rust hover:text-rust-wash cursor-help select-none font-bold text-[9px] border border-rust/40 rounded-full w-3.5 h-3.5 inline-flex items-center justify-center">ℹ</span>
                                                            <div class="absolute bottom-full right-0 mb-2 hidden group-hover/tooltip:block w-40 bg-zinc-800 text-white text-[9px] leading-tight p-2 rounded shadow-lg z-[100] pointer-events-none text-center normal-case font-normal">
                                                                This category can also contain dynamic terms not listed here.
                                                                <div class="w-1.5 h-1.5 bg-zinc-800 rotate-45 absolute top-full right-2 -mt-[3px]"></div>
                                                            </div>
                                                        </div>
                                                    </template>
                                                </div>

                                                <!-- Vocabulary Terms -->
                                                <div x-show="openVocab" x-transition class="pl-2 ml-1 border-l border-border/20 flex flex-col gap-0.5 mt-0.5">
                                                    <template x-if="vocab.type === 'hierarchical'">
                                                        <div class="flex flex-col gap-0.5">
                                                            <template x-for="node in vocab.terms" :key="node.fullPath">
                                                                <div x-data="{ openSub: false }" class="flex flex-col">
                                                                    <div class="flex items-center gap-0.5 py-[1px] px-1 min-w-0 select-none w-full text-steel-muted font-normal"
                                                                        :class="node.children && node.children.length > 0 ? 'cursor-pointer hover:bg-canvas/50' : ''"
                                                                        @click="if (node.children && node.children.length > 0) openSub = !openSub">
                                                                        <span class="w-3 flex justify-center shrink-0 text-steel-muted/60"
                                                                            :class="node.children && node.children.length > 0 ? (openSub ? 'rotate-90 transition-transform duration-200' : 'transition-transform duration-200') : 'text-[8px] text-steel-muted/40'">
                                                                            <template x-if="node.children && node.children.length > 0">
                                                                                <svg class="w-2 h-2 fill-current" viewBox="0 0 24 24"><path d="M8.59,16.59L13.17,12L8.59,7.41L10,6L16,12L10,18L8.59,16.59Z"/></svg>
                                                                            </template>
                                                                            <template x-if="!node.children || node.children.length === 0">
                                                                                <span>•</span>
                                                                            </template>
                                                                        </span>
                                                                        <span class="truncate text-steel-muted" :class="!node.isExplicit ? 'text-steel-muted/50' : ''" :title="node.fullPath" x-text="node.name"></span>
                                                                        <span class="ml-auto shrink-0 inline-flex items-center gap-0.5">
                                                                            <button type="button"
                                                                                x-show="isTaxonomyTermInMenus(vocab.key, node.fullPath)" x-cloak
                                                                                @click.stop="removeTreeItemFromActiveTab('taxonomy:' + vocab.key + '/' + node.fullPath)"
                                                                                class="text-rust cursor-pointer group/rm inline-flex items-center justify-center p-0.5 -m-0.5"
                                                                                title="Remove from active menu"
                                                                                aria-label="Remove from active menu">
                                                                                <svg class="w-2.5 h-2.5 group-hover/rm:hidden group-focus-visible/rm:hidden"><use href="#icon-checkmark-thin"></use></svg>
                                                                                <span class="hidden group-hover/rm:inline group-focus-visible/rm:inline text-[10px] leading-none font-bold" aria-hidden="true">×</span>
                                                                            </button>
                                                                            <button type="button"
                                                                                x-show="!isInActiveTab('taxonomy:' + vocab.key + '/' + node.fullPath)" x-cloak
                                                                                @click.stop="addTreeTaxonomy(vocab.key, node.fullPath, node.name)"
                                                                                class="text-rust cursor-pointer inline-flex items-center justify-center p-0.5 -m-0.5"
                                                                                title="Add to active menu"
                                                                                aria-label="Add to active menu">
                                                                                <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-plus-thin"></use></svg>
                                                                            </button>
                                                                        </span>
                                                                    </div>
                                                                    
                                                                    <!-- Level 2 Nester -->
                                                                    <template x-if="node.children && node.children.length > 0">
                                                                        <div x-show="openSub" x-transition class="pl-2 ml-1 border-l border-border/10 flex flex-col gap-0.5">
                                                                            <template x-for="subNode in node.children" :key="subNode.fullPath">
                                                                                <div x-data="{ openSub2: false }" class="flex flex-col">
                                                                                    <div class="flex items-center gap-0.5 py-[1px] px-1 min-w-0 select-none w-full text-steel-muted font-normal"
                                                                                        :class="subNode.children && subNode.children.length > 0 ? 'cursor-pointer hover:bg-canvas/50' : ''"
                                                                                        @click="if (subNode.children && subNode.children.length > 0) openSub2 = !openSub2">
                                                                                        <span class="w-3 flex justify-center shrink-0 text-steel-muted/60"
                                                                                            :class="subNode.children && subNode.children.length > 0 ? (openSub2 ? 'rotate-90 transition-transform duration-200' : 'transition-transform duration-200') : 'text-[8px] text-steel-muted/40'">
                                                                                            <template x-if="subNode.children && subNode.children.length > 0">
                                                                                                <svg class="w-2 h-2 fill-current" viewBox="0 0 24 24"><path d="M8.59,16.59L13.17,12L8.59,7.41L10,6L16,12L10,18L8.59,16.59Z"/></svg>
                                                                                            </template>
                                                                                            <template x-if="!subNode.children || subNode.children.length === 0">
                                                                                                <span>•</span>
                                                                                            </template>
                                                                                        </span>
                                                                                        <span class="truncate text-steel-muted" :class="!subNode.isExplicit ? 'text-steel-muted/50' : ''" :title="subNode.fullPath" x-text="subNode.name"></span>
                                                                                        <span class="ml-auto shrink-0 inline-flex items-center gap-0.5">
                                                                                            <button type="button"
                                                                                                x-show="isTaxonomyTermInMenus(vocab.key, subNode.fullPath)" x-cloak
                                                                                                @click.stop="removeTreeItemFromActiveTab('taxonomy:' + vocab.key + '/' + subNode.fullPath)"
                                                                                                class="text-rust cursor-pointer group/rm inline-flex items-center justify-center p-0.5 -m-0.5"
                                                                                                title="Remove from active menu"
                                                                                                aria-label="Remove from active menu">
                                                                                                <svg class="w-2.5 h-2.5 group-hover/rm:hidden group-focus-visible/rm:hidden"><use href="#icon-checkmark-thin"></use></svg>
                                                                                                <span class="hidden group-hover/rm:inline group-focus-visible/rm:inline text-[10px] leading-none font-bold" aria-hidden="true">×</span>
                                                                                            </button>
                                                                                            <button type="button"
                                                                                                x-show="!isInActiveTab('taxonomy:' + vocab.key + '/' + subNode.fullPath)" x-cloak
                                                                                                @click.stop="addTreeTaxonomy(vocab.key, subNode.fullPath, subNode.name)"
                                                                                                class="text-rust cursor-pointer inline-flex items-center justify-center p-0.5 -m-0.5"
                                                                                                title="Add to active menu"
                                                                                                aria-label="Add to active menu">
                                                                                                <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-plus-thin"></use></svg>
                                                                                            </button>
                                                                                        </span>
                                                                                    </div>
                                                                                    
                                                                                    <!-- Level 3 Nester -->
                                                                                    <template x-if="subNode.children && subNode.children.length > 0">
                                                                                        <div x-show="openSub2" x-transition class="pl-2 ml-1 border-l border-border/10 flex flex-col gap-0.5">
                                                                                            <template x-for="leafNode in subNode.children" :key="leafNode.fullPath">
                                                                                                <div class="flex items-center gap-0.5 py-[1px] px-1 min-w-0 hover:bg-canvas/50 text-steel-muted select-none">
                                                                                                    <span class="w-3 flex justify-center text-[8px] text-steel-muted/40 shrink-0">•</span>
                                                                                                    <span class="truncate" :class="!leafNode.isExplicit ? 'text-steel-muted/50' : ''" :title="leafNode.fullPath" x-text="leafNode.name"></span>
                                                                                                    <span class="ml-auto shrink-0 inline-flex items-center gap-0.5">
                                                                                                        <button type="button"
                                                                                                            x-show="isTaxonomyTermInMenus(vocab.key, leafNode.fullPath)" x-cloak
                                                                                                            @click.stop="removeTreeItemFromActiveTab('taxonomy:' + vocab.key + '/' + leafNode.fullPath)"
                                                                                                            class="text-rust cursor-pointer group/rm inline-flex items-center justify-center p-0.5 -m-0.5"
                                                                                                            title="Remove from active menu"
                                                                                                            aria-label="Remove from active menu">
                                                                                                            <svg class="w-2.5 h-2.5 group-hover/rm:hidden group-focus-visible/rm:hidden"><use href="#icon-checkmark-thin"></use></svg>
                                                                                                            <span class="hidden group-hover/rm:inline group-focus-visible/rm:inline text-[10px] leading-none font-bold" aria-hidden="true">×</span>
                                                                                                        </button>
                                                                                                        <button type="button"
                                                                                                            x-show="!isInActiveTab('taxonomy:' + vocab.key + '/' + leafNode.fullPath)" x-cloak
                                                                                                            @click.stop="addTreeTaxonomy(vocab.key, leafNode.fullPath, leafNode.name)"
                                                                                                            class="text-rust cursor-pointer inline-flex items-center justify-center p-0.5 -m-0.5"
                                                                                                            title="Add to active menu"
                                                                                                            aria-label="Add to active menu">
                                                                                                            <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-plus-thin"></use></svg>
                                                                                                        </button>
                                                                                                    </span>
                                                                                                </div>
                                                                                            </template>
                                                                                        </div>
                                                                                    </template>
                                                                                </div>
                                                                            </template>
                                                                        </div>
                                                                    </template>
                                                                </div>
                                                            </template>
                                                        </div>
                                                    </template>
                                                    <template x-if="vocab.type !== 'hierarchical'">
                                                        <div class="flex flex-col gap-0.5">
                                                            <template x-for="term in vocab.terms" :key="term">
                                                                <div class="flex items-center gap-0.5 py-[1px] px-1 hover:bg-canvas/50 text-steel-muted min-w-0 select-none">
                                                                    <span class="w-3 flex justify-center text-[8px] text-steel-muted/40 shrink-0">•</span>
                                                                    <span class="truncate" :title="term" x-text="term"></span>
                                                                    <span class="ml-auto shrink-0 inline-flex items-center gap-0.5">
                                                                        <button type="button"
                                                                            x-show="isTaxonomyTermInMenus(vocab.key, term)" x-cloak
                                                                            @click.stop="removeTreeItemFromActiveTab('taxonomy:' + vocab.key + '/' + term)"
                                                                            class="text-rust cursor-pointer group/rm inline-flex items-center justify-center p-0.5 -m-0.5"
                                                                            title="Remove from active menu"
                                                                            aria-label="Remove from active menu">
                                                                            <svg class="w-2.5 h-2.5 group-hover/rm:hidden group-focus-visible/rm:hidden"><use href="#icon-checkmark-thin"></use></svg>
                                                                            <span class="hidden group-hover/rm:inline group-focus-visible/rm:inline text-[10px] leading-none font-bold" aria-hidden="true">×</span>
                                                                        </button>
                                                                        <button type="button"
                                                                            x-show="!isInActiveTab('taxonomy:' + vocab.key + '/' + term)" x-cloak
                                                                            @click.stop="addTreeTaxonomy(vocab.key, term, term)"
                                                                            class="text-rust cursor-pointer inline-flex items-center justify-center p-0.5 -m-0.5"
                                                                            title="Add to active menu"
                                                                            aria-label="Add to active menu">
                                                                            <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-plus-thin"></use></svg>
                                                                        </button>
                                                                    </span>
                                                                </div>
                                                            </template>
                                                            <div x-show="vocab.terms.length === 0" class="py-[1px] px-1 text-steel-muted/60">No listed terms</div>
                                                        </div>
                                                    </template>
                                                </div>
                                            </div>
                                        </template>
                                    </div>
                                </div>

                            </div>
                        </div>
                    </div>

                    </aside>
                    <!-- ── End Left Column ── -->

                </div>
            </div>
            <!-- ── End 3-Column Content Area ── -->

        </main>
    </div>

    <!-- Clear All Menus Confirmation Modal -->
    <?php
    admin_modal([
        'show_var' => 'clearAllModalOpen',
        'title'    => 'Clear All Menus',
        'danger'   => true,
        'body'     => '
            <p class="text-sm text-forge-black font-sans">
                This will permanently remove every item from <strong>Primary</strong>, <strong>Secondary</strong>, and <strong>Footer</strong> menus.
            </p>
            <p class="text-xs text-forge-muted font-serif leading-prose">
                This change cannot be undone. Click Confirm to proceed.
            </p>',
        'footer'   => '
            <button @click="clearAllModalOpen = false" class="pen-btn pen-btn-secondary pen-btn-sm" :disabled="clearingAll">Cancel</button>
            <button @click="confirmClearAll()" class="pen-btn pen-btn-danger pen-btn-sm" :disabled="clearingAll">
                <span x-text="clearingAll ? \'Clearing...\' : \'Confirm\'"></span>
            </button>',
    ]);
    ?>

    <!-- Shared helpers + AI Assistant (loads the aiSidebar Alpine component) -->
    <script src="js/mcp-client.js"></script>
    <script src="js/ai-handoff.js"></script>
    <script src="js/menu-item-shape.js"></script>
    <script src="js/ai-sidebar-navigation.js"></script>

    <!-- Footer (loads api.js, store.js, and $pageScript = settings-navigation.js) -->
    <?php include "includes/_admin-footer.php"; ?>
</body>

</html>
