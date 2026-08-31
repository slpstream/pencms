<?php
$pageTitle = "Content Editor (PenCMS)";
$currentSection = "editor";
$pageScript = "wizard4.js";
include "includes/_admin-auth.php";
require_once "includes/_admin-icons.php";
require_once "includes/_admin-modal.php";

// Resolve content skins from installed themes (starter = missing-stack fallback)
require_once "includes/_editor-skin-resolve.php";
$availableSkinsList = $penEditorSkinsList;
$availableSkinsJson = json_encode($availableSkinsList);
$penEditorSkinsMapJson = json_encode($penEditorSkinsMap);
$penEditorSkinBootJson = json_encode($penEditorSkinBoot);
$penEditorImageAspectJson = json_encode($penEditorImageAspect ?? []);

$penLoadTraven = true;
$penLoadMarked = true;
include "includes/_admin-head.php";
?>

<!-- Stahl & Feuer overrides -->
<link rel="stylesheet" href="css/admin-editor.css">
<script>
    window.PEN_EDITOR_SKIN_BOOT = <?= $penEditorSkinBootJson ?: '{}' ?>;
    window.PEN_EDITOR_SKINS = <?= $penEditorSkinsMapJson ?: '{}' ?>;
    window.PEN_EDITOR_IMAGE_ASPECT = <?= $penEditorImageAspectJson ?: '[]' ?>;
</script>

<body class="bg-canvas text-forge-black font-sans antialiased h-screen flex flex-col overflow-hidden" x-data="wizard4"
    :class="{
          'hide-main-toolbar': !workspacePrefs.mainToolbar,
          'hide-selection-bubble': !workspacePrefs.selectionBubble,
          'hide-gutter-insertion': !workspacePrefs.gutterMenu,
          'raw-markdown-active': workspacePrefs.rawMarkdown
      }">

    <?php require "includes/_admin-icon-sprite.php"; ?>

    <!-- Top Navigation Bar -->
    <?php include "includes/_admin-header.php"; ?>

    <div class="flex flex-1 relative min-h-0 overflow-hidden">
        <!-- Collapsible Left Sidebar -->
        <?php include "includes/_admin-sidebar.php"; ?>

        <!-- Main Workspace Canvas -->
        <main class="flex-1 flex flex-col min-h-0 overflow-hidden transition-all duration-300">

            <!-- ── Toast Notifications ─────────────────────────────── -->
            <div class="fixed top-20 right-6 z-[200] space-y-2">
                <template x-for="toast in toasts" :key="toast.id">
                    <div x-transition:enter="transition ease-out duration-300"
                        x-transition:enter-start="opacity-0 translate-x-8"
                        x-transition:enter-end="opacity-100 translate-x-0"
                        x-transition:leave="transition ease-in duration-200" x-transition:leave-start="opacity-100"
                        x-transition:leave-end="opacity-0"
                        class="px-4 py-3 font-sans text-xs font-bold uppercase tracking-wider shadow-md min-w-[260px] flex items-center gap-2 border"
                        :class="toast.type === 'error' ? 'bg-danger text-white border-danger' : 'bg-acid text-acid-ink border-acid'">
                        <svg x-show="toast.type !== 'error'" class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-toast-success"></use></svg>
                        <svg x-show="toast.type === 'error'" class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-toast-error"></use></svg>
                        <span x-text="toast.message"></span>
                    </div>
                </template>
            </div>

            <!-- ── Sticky Control Header (Context Actions & Editor Toolbars) ── -->
            <div id="sticky-control-header" class="sticky top-0 z-[60] flex flex-col border-b-2 border-border shadow-sm shrink-0">
                <div x-show="translationConfig.i18n_active && !isNew" x-cloak
                    class="bg-card border-b border-border px-6 py-2 flex flex-wrap items-center gap-2">
                    <span class="text-[9px] font-black uppercase tracking-wider text-forge-mid mr-1">Language siblings</span>
                    <template x-for="state in siblingStates" :key="state.language">
                        <button type="button" @click="openOrCreateSibling(state)"
                            :disabled="state.current"
                            class="px-2.5 py-1 border text-[9px] font-black uppercase tracking-wider transition-colors"
                            :class="state.current ? 'border-rust bg-rust-wash text-rust' : (state.status === 'missing' ? 'border-dashed border-border text-forge-mid hover:border-rust' : 'border-border bg-canvas text-forge-dark hover:border-rust')"
                            :title="state.current ? 'Currently open exact sibling' : (state.status === 'missing' ? 'Create empty manual sibling' : 'Open exact sibling')">
                            <span x-text="languageLabel(state.language)"></span>
                            <span class="font-mono opacity-70" x-text="' ' + state.language"></span>
                            <span x-text="state.status === 'missing' ? ' +' : (' · ' + (state.needs_review ? 'review' : state.status))"></span>
                        </button>
                    </template>
                    <span x-show="isTranslation" class="ml-auto text-[9px] font-mono text-forge-mid"
                        x-text="'Locked group ' + (form.translation_group || 'assigned on disk')"></span>
                </div>

                <!-- Secondary Toolbar Rail (Context Actions) -->
                <div class="bg-[#f4edea] transition-all duration-200"
                    :class="workspacePrefs.secondaryRailCollapsed ? 'py-1.5' : 'py-3'">
                    <div class="px-6 flex flex-col md:flex-row md:justify-between md:items-center gap-3">
                        <!-- Breadcrumbs -->
                        <div class="flex items-center gap-3 min-w-0">
                            <div class="flex flex-col min-w-0">
                                <h1 class="font-sans font-bold text-forge-black truncate max-w-sm"
                                    :class="workspacePrefs.secondaryRailCollapsed ? 'text-sm' : 'text-base'"
                                    x-text="form.name || (isNew ? 'Create Entry' : 'Untitled Entry')">Create Entry</h1>

                                        <!-- Save Status Indicator -->
                                        <div class="flex items-center gap-1.5 text-[9px] text-slate-500 font-mono select-none mr-1.5">
                                            <span class="w-1.5 h-1.5 -mt-0.5 rounded-full transition-colors duration-300"
                                                :class="{
                                                    'bg-emerald-500': saveStatus === 'saved',
                                                    'bg-amber-500/80': saveStatus === 'unsaved',
                                                    'bg-rust animate-pulse': saveStatus === 'saving'
                                                }"></span>
                                            <span x-text="saveStatusText" class="tracking-wide"></span> -

                                            <span class="text-[9px] font-mono text-slate-500"
                                                x-text="isNew ? 'NEW' : form.id">
                                            </span>
                                        </div>

                            </div>

                            <div class="flex items-center gap-1 shrink-0">
                                <!-- Markdown Logo (Toggle) -->
                                <button type="button"
                                    class="transition-colors border flex items-center justify-center h-[30px] w-[40px] mr-1.5 cursor-pointer outline-none"
                                    :class="workspacePrefs.rawMarkdown ? 'text-[#0f0d0b] border-border bg-card shadow-inner' : 'text-[#817d7b] border-transparent hover:border-border hover:bg-card'"
                                    @click="toggleRawMarkdown()"
                                    :title="workspacePrefs.rawMarkdown ? 'Toggle OFF to edit Rich Text' : 'Toggle ON to edit Raw Markdown'">
                                    <svg class="h-4 w-6 transition-colors shrink-0"><use href="#icon-toggle-markdown"></use></svg>
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

                                <!-- Toggle AI Assistant Button -->
                                <button type="button"
                                    x-show="$store.app.use_ai" x-cloak
                                    class="transition-colors p-1 shrink-0 border hover:border-rust text-[#817d7b] border-transparent hover:border-border hover:bg-card"
                                    @click="$dispatch('toggle-ai-sidebar')" title="Toggle AI Assistant">
                                    <svg x-show="!workspacePrefs.aiAssistantCollapsed" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-5 h-5 text-rust" fill="currentColor"><rect width="256" height="256" fill="none"/><path d="M208,144a15.78,15.78,0,0,1-10.42,14.94L146,178l-19,51.62a15.92,15.92,0,0,1-29.88,0L78,178l-51.62-19a15.92,15.92,0,0,1,0-29.88L78,110l19-51.62a15.92,15.92,0,0,1,29.88,0L146,110l51.62,19A15.78,15.78,0,0,1,208,144ZM152,48h16V64a8,8,0,0,0,16,0V48h16a8,8,0,0,0,0-16H184V16a8,8,0,0,0-16,0V32H152a8,8,0,0,0,0,16Zm88,32h-8V72a8,8,0,0,0-16,0v8h-8a8,8,0,0,0,0,16h8v8a8,8,0,0,0,16,0V96h8a8,8,0,0,0,0-16Z"/></svg>
                                    <svg x-show="workspacePrefs.aiAssistantCollapsed" class="w-5 h-5 text-rust"><use href="#icon-sparkle-ai"></use></svg>
                                </button>
                            </div>
                        </div>

                        <!-- Actions + Readiness -->
                        <div class="flex items-center gap-3 flex-wrap">
                            <!-- Spec Readiness: hidden when collapsed -->
                            <div x-show="!workspacePrefs.secondaryRailCollapsed" x-cloak
                                class="pref-secondary-rail-item hidden md:flex items-center gap-2 bg-card border border-border px-3 h-7">
                                <span
                                    class="text-[9px] font-black text-steel-muted uppercase tracking-widest">Specs</span>
                                <div class="w-16 bg-border h-1 overflow-hidden">
                                    <div class="h-full bg-rust transition-all duration-700"
                                        :style="'width:' + validationPercentage + '%'"></div>
                                </div>
                                <span class="text-[10px] font-mono font-black text-rust-bright"
                                    x-text="validationPercentage + '%'"></span>
                            </div>

                            <!-- Word Count: hidden when collapsed -->
                            <div x-show="!workspacePrefs.secondaryRailCollapsed" x-cloak
                                class="pref-secondary-rail-item hidden md:flex items-center gap-2 bg-card border border-border px-3 h-7 cursor-help"
                                :title="'Estimated read time: ' + Math.ceil(wordCount / 200) + ' min'">
                                <span
                                    class="text-[9px] font-black text-steel-muted uppercase tracking-widest">Words</span>
                                <span class="text-[10px] font-mono font-black text-rust-bright"
                                    x-text="wordCount"></span>
                            </div>

                            <!-- Status dropdown: face shows Scheduled when publish_at is future -->
                            <div x-show="!workspacePrefs.secondaryRailCollapsed" x-cloak
                                class="pref-secondary-rail-item relative"
                                @click.outside="statusDropdownOpen = false">
                                <button type="button"
                                    @click="statusDropdownOpen = !statusDropdownOpen"
                                    class="pen-btn pen-btn-secondary flex items-center gap-1.5 !text-[10px] !py-0 !px-2.5 !border h-7 !font-bold !uppercase"
                                    :class="isScheduled() ? 'text-rust border-rust' : 'text-forge-black'"
                                    :title="isScheduled() ? ('Goes live at ' + form.publish_at) : ('Status: ' + (form.status || 'draft'))">
                                    <span x-text="statusRailLabel()"></span>
                                    <svg class="w-2.5 h-2.5 text-steel-muted transition-transform duration-200"
                                        :class="statusDropdownOpen ? 'rotate-180' : ''"
                                        fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-chevron-down"></use></svg>
                                </button>

                                <div x-show="statusDropdownOpen"
                                    x-transition:enter="transition ease-out duration-100"
                                    x-transition:enter-start="transform opacity-0 scale-95"
                                    x-transition:enter-end="transform opacity-100 scale-100"
                                    x-transition:leave="transition ease-in duration-75"
                                    x-transition:leave-start="transform opacity-100 scale-100"
                                    x-transition:leave-end="transform opacity-0 scale-95"
                                    class="absolute right-0 top-full mt-1.5 w-44 bg-card border-2 border-border shadow-md z-[100] select-none overflow-hidden"
                                    style="display: none;">
                                    <div class="px-3 py-1.5 border-b border-border bg-canvas/50">
                                        <span class="text-[10px] font-black uppercase tracking-wider text-rust">Status</span>
                                    </div>
                                    <div class="divide-y divide-border/40">
                                        <template x-for="opt in [
                                            { value: 'stub', label: 'Stub' },
                                            { value: 'draft', label: 'Draft' },
                                            { value: 'unpublished', label: 'Unpublished' },
                                            { value: 'published', label: 'Published' }
                                        ]" :key="opt.value">
                                            <button type="button"
                                                @click="setStatus(opt.value)"
                                                :disabled="statusOptionLocked(opt.value)"
                                                class="w-full flex items-center justify-between gap-2 px-3 py-2 text-left font-sans text-[11px] font-bold tracking-wide text-forge-dark uppercase"
                                                :class="statusOptionLocked(opt.value)
                                                    ? 'opacity-40 cursor-not-allowed'
                                                    : (form.status === opt.value ? 'bg-rust-wash text-rust cursor-pointer hover:bg-rust-wash' : 'cursor-pointer hover:bg-rust-wash')"
                                                :title="statusOptionLocked(opt.value) ? 'Requires publish:content' : ''">
                                                <span x-text="opt.label"></span>
                                                <span x-show="form.status === opt.value" class="text-rust" aria-hidden="true">✓</span>
                                            </button>
                                        </template>
                                    </div>
                                    <p x-show="isScheduled()" x-cloak
                                        class="px-3 py-2 border-t border-border text-[9px] font-bold uppercase tracking-wider text-rust leading-snug">
                                        Scheduled — listed after go-live time
                                    </p>
                                </div>
                            </div>

                            <!-- Toolbars Config Dropdown: hidden when collapsed -->
                            <div x-show="!workspacePrefs.secondaryRailCollapsed" x-cloak class="pref-secondary-rail-item relative"
                                @click.outside="toolbarDropdownOpen = false">
                                <button @click="toolbarDropdownOpen = !toolbarDropdownOpen"
                                    class="pen-btn pen-btn-secondary flex items-center gap-1.5 !text-[10px] !py-0 !px-2.5 !border h-7"
                                    title="Configure Editor Toolbars">
                                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-settings-gear"></use></svg>
                                    <span>Toolbars</span>
                                    <svg class="w-2.5 h-2.5 text-steel-muted transition-transform duration-200" :class="toolbarDropdownOpen ? 'rotate-180' : ''" fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-chevron-down"></use></svg>
                                </button>

                                <!-- Dropdown List Popover -->
                                <div x-show="toolbarDropdownOpen" x-transition:enter="transition ease-out duration-100"
                                    x-transition:enter-start="transform opacity-0 scale-95"
                                    x-transition:enter-end="transform opacity-100 scale-100"
                                    x-transition:leave="transition ease-in duration-75"
                                    x-transition:leave-start="transform opacity-100 scale-100"
                                    x-transition:leave-end="transform opacity-0 scale-95"
                                    class="absolute right-0 top-full mt-1.5 w-48 bg-card border-2 border-border shadow-md z-[100] select-none overflow-hidden"
                                    style="display: none;">

                                    <div class="px-3 py-1.5 border-b border-border bg-canvas/50">
                                        <span class="text-[10px] font-black uppercase tracking-wider text-rust">Toolbar
                                            Layout</span>
                                    </div>

                                    <div class="divide-y divide-border/40">
                                        <!-- Main Toolbar -->
                                        <label
                                            class="flex items-center gap-2.5 px-3 py-2 cursor-pointer hover:bg-rust-wash transition-colors select-none font-sans text-[11px] font-bold tracking-wide text-forge-dark uppercase">
                                            <input type="checkbox" x-model="workspacePrefs.mainToolbar"
                                                @change="saveWorkspacePrefs()" class="sr-only">
                                            <span
                                                class="w-3 h-3 border border-border flex items-center justify-center transition-colors"
                                                :class="workspacePrefs.mainToolbar ? 'bg-rust border-rust text-white' : 'bg-transparent'">
                                                <template x-if="workspacePrefs.mainToolbar">
                                                    <?php admin_icon('check'); ?>
                                                </template>
                                            </span>
                                            <span>Top Toolbar</span>
                                        </label>

                                        <!-- Selection Bubble -->
                                        <label
                                            class="flex items-center gap-2.5 px-3 py-2 cursor-pointer hover:bg-rust-wash transition-colors select-none font-sans text-[11px] font-bold tracking-wide text-forge-dark uppercase">
                                            <input type="checkbox" x-model="workspacePrefs.selectionBubble"
                                                @change="saveWorkspacePrefs()" class="sr-only">
                                            <span
                                                class="w-3 h-3 border border-border flex items-center justify-center transition-colors"
                                                :class="workspacePrefs.selectionBubble ? 'bg-rust border-rust text-white' : 'bg-transparent'">
                                                <template x-if="workspacePrefs.selectionBubble">
                                                    <?php admin_icon('check'); ?>
                                                </template>
                                            </span>
                                            <span>Selection Bubble</span>
                                        </label>

                                        <!-- Gutter Menu -->
                                        <label
                                            class="flex items-center gap-2.5 px-3 py-2 cursor-pointer hover:bg-rust-wash transition-colors select-none font-sans text-[11px] font-bold tracking-wide text-forge-dark uppercase">
                                            <input type="checkbox" x-model="workspacePrefs.gutterMenu"
                                                @change="saveWorkspacePrefs()" class="sr-only">
                                            <span
                                                class="w-3 h-3 border border-border flex items-center justify-center transition-colors"
                                                :class="workspacePrefs.gutterMenu ? 'bg-rust border-rust text-white' : 'bg-transparent'">
                                                <template x-if="workspacePrefs.gutterMenu">
                                                    <?php admin_icon('check'); ?>
                                                </template>
                                            </span>
                                            <span>Gutter Menu</span>
                                        </label>
                                    </div>

                                    <div class="px-3 py-1.5 border-t border-b border-border bg-canvas/50">
                                        <span
                                            class="text-[10px] font-black uppercase tracking-wider text-rust">Keybindings</span>
                                    </div>

                                    <div class="divide-y divide-border/40">
                                        <!-- Vim Keybindings -->
                                        <label
                                            class="flex items-center gap-2.5 px-3 py-2 cursor-pointer hover:bg-rust-wash transition-colors select-none font-sans text-[11px] font-bold tracking-wide text-forge-dark uppercase">
                                            <input type="checkbox" x-model="workspacePrefs.vimMode"
                                                @change="saveWorkspacePrefs(); updateVimMode()" class="sr-only">
                                            <span
                                                class="w-3 h-3 border border-border flex items-center justify-center transition-colors"
                                                :class="workspacePrefs.vimMode ? 'bg-rust border-rust text-white' : 'bg-transparent'">
                                                <template x-if="workspacePrefs.vimMode">
                                                    <?php admin_icon('check'); ?>
                                                </template>
                                            </span>
                                            <span>Vim Keybindings</span>
                                        </label>
                                    </div>
                                </div>
                            </div>

                            <!-- Editor Skin Dropdown: hidden when collapsed -->
                            <div x-show="!workspacePrefs.secondaryRailCollapsed" x-cloak class="pref-secondary-rail-item relative"
                                @click.outside="skinDropdownOpen = false">
                                <button @click="skinDropdownOpen = !skinDropdownOpen"
                                    class="pen-btn pen-btn-secondary flex items-center gap-1.5 !text-[10px] !py-0 !px-2.5 !border h-7"
                                    title="Change Editor Skin">
                                    <!-- Palette icon (Phosphor) -->
                                    <svg class="w-3.5 h-3.5" fill="currentColor"><use href="#icon-palette"></use></svg>
                                    <span>Skin</span>
                                    <svg class="w-2.5 h-2.5 text-steel-muted transition-transform duration-200" :class="skinDropdownOpen ? 'rotate-180' : ''" fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-chevron-down"></use></svg>
                                </button>

                                <!-- Dropdown List Popover -->
                                <div x-show="skinDropdownOpen" x-transition:enter="transition ease-out duration-100"
                                    x-transition:enter-start="transform opacity-0 scale-95"
                                    x-transition:enter-end="transform opacity-100 scale-100"
                                    x-transition:leave="transition ease-in duration-75"
                                    x-transition:leave-start="transform opacity-100 scale-100"
                                    x-transition:leave-end="transform opacity-0 scale-95"
                                    class="absolute right-0 top-full mt-1.5 w-48 bg-card border-2 border-border shadow-md z-[100] select-none overflow-hidden"
                                    style="display: none;">

                                    <div class="px-3 py-1.5 border-b border-border bg-canvas/50">
                                        <span class="text-[10px] font-black uppercase tracking-wider text-rust">Editor Skin</span>
                                    </div>

                                    <div class="divide-y divide-border/40">
                                        <template x-for="skin in <?= htmlspecialchars($availableSkinsJson, ENT_QUOTES, 'UTF-8') ?>" :key="skin.key">
                                            <label class="flex items-center gap-2.5 px-3 py-2 cursor-pointer hover:bg-rust-wash transition-colors select-none font-sans text-[11px] font-bold tracking-wide text-forge-dark uppercase"
                                                @click="applySkin(skin.key); skinDropdownOpen = false">
                                                <span class="w-3 h-3 rounded-full border border-border flex items-center justify-center transition-colors"
                                                    :class="workspacePrefs.editorSkin === skin.key ? 'border-rust bg-rust-wash' : 'bg-transparent'">
                                                    <span class="w-1.5 h-1.5 rounded-full transition-all duration-200"
                                                        :class="workspacePrefs.editorSkin === skin.key ? 'bg-rust scale-100' : 'bg-transparent scale-0'"></span>
                                                </span>
                                                <span x-text="skin.label"></span>
                                            </label>
                                        </template>
                                    </div>
                                </div>
                            </div>

                            <!-- Preview Link: hidden when collapsed -->
                            <a x-show="!workspacePrefs.secondaryRailCollapsed" x-cloak
                                :href="$store.app.previewContentUrl(form.id, form.page, currentLanguage, translationConfig.language)" target="_blank" rel="noopener"
                                class="pref-secondary-rail-item pen-btn pen-btn-secondary flex items-center gap-1.5 !text-[10px] !py-0 !px-2.5 !border h-7"
                                :class="!form.id && 'opacity-50 pointer-events-none'" title="View live post">
                                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-external-link"></use></svg>
                                <span>Preview</span>
                            </a>

                            <!-- Save Button: ALWAYS SHOWN -->
                            <button @click="save()"
                                class="pen-btn pen-btn-primary flex items-center gap-2 !text-xs !py-1.5"
                                :disabled="manualSaving">
                                <svg x-show="manualSaving" x-cloak class="animate-spin h-3.5 w-3.5 text-white" fill="none"><use href="#icon-spinner"></use></svg>
                                <span x-text="manualSaving ? 'Saving...' : (isNew ? 'Create Entry' : 'Save')"></span>
                            </button>

                            <!-- Toggle Collapse Button -->
                            <button
                                @click="workspacePrefs.secondaryRailCollapsed = !workspacePrefs.secondaryRailCollapsed; saveWorkspacePrefs()"
                                class="text-steel-muted hover:text-rust transition-colors p-1.5 shrink-0 border border-border bg-card hover:border-rust"
                                :title="workspacePrefs.secondaryRailCollapsed ? 'Expand controls' : 'Collapse controls'">
                                <svg class="w-4 h-4 transition-transform duration-200" :class="workspacePrefs.secondaryRailCollapsed ? 'rotate-180' : ''" fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-chevron-up"></use></svg>
                            </button>
                        </div>
                    </div>
                </div>
                <!-- Shared Editor Toolbar -->
                <div id="shared-editor-toolbar" class="bg-[#f4edea] transition-all duration-200"
                    x-show="workspacePrefs.mainToolbar && isEditorActive() && !workspacePrefs.rawMarkdown"
                    style="display: none;"></div>
            </div>

            <!-- ── Main Content Area ────────────────────────────────── -->
            <div class="px-6 md:px-10 pt-3 pb-0 flex-1 min-h-0 overflow-hidden">
                <div class="flex flex-col lg:flex-row gap-8 lg:gap-0 items-stretch h-full"
                    :style="'--left-width: ' + workspacePrefs.sidebarWidth + '%; --right-width: ' + workspacePrefs.rightColumnWidth + '%'">

                    <!-- ============================================== -->
                    <!-- Primary Content Workspace                      -->
                    <!-- ============================================== -->
                    <div class="w-full resizable-workspace lg:order-3 lg:px-6 lg:h-full lg:flex lg:flex-col lg:min-h-0 lg:overflow-hidden" :class="{
                             'workspace-both-collapsed lg:!px-0': workspacePrefs.leftColumnCollapsed && workspacePrefs.rightColumnCollapsed,
                             'workspace-left-collapsed lg:!pl-0': workspacePrefs.leftColumnCollapsed && !workspacePrefs.rightColumnCollapsed,
                             'workspace-right-collapsed lg:!pr-0': !workspacePrefs.leftColumnCollapsed && workspacePrefs.rightColumnCollapsed
                         }">

                        <div class="space-y-6 lg:flex-1 lg:min-h-0 lg:overflow-y-auto">
                        <!-- Unified Main Post Card -->
                        <div class="pen-card overflow-hidden flex flex-col space-y-0">
                            <!-- Graphic Upload Zones -->
                            <div x-show="!collapsedPartials.includes('hero')" x-transition
                                class="relative aspect-[21/9] w-full bg-card border-2 border-dashed hover:border-rust overflow-hidden group transition-all cursor-pointer flex flex-col items-center justify-center p-0"
                                :class="{
                                     'border-rust bg-rust-wash/30': dragOver,
                                     'border-transparent': !dragOver && form.hero_image,
                                     'border-border': !dragOver && !form.hero_image,
                                     'opacity-50 !cursor-not-allowed': !form.id && !form.hero_image
                                 }" @click="activePartial = 'hero'; if(form.id && !form.hero_image) $refs.heroInput.click()"
                                @dragover.prevent="if(form.id) dragOver = true" @dragleave="dragOver = false"
                                @drop.prevent="dragOver = false; if(form.id) handleHeroDrop($event)">

                                <template x-if="form.hero_image">
                                    <img :src="contentAssetUrl(form.hero_image)"
                                        class="w-full h-full object-cover">
                                </template>

                                <template x-if="!form.hero_image">
                                    <div
                                        class="w-full h-full flex flex-col items-center justify-center text-forge-mid py-6">
                                        <svg class="w-8 h-8 mb-2 text-border" fill="none" stroke="currentColor" stroke-width="1.5"><use href="#icon-drag-handle"></use></svg>
                                        <span class="text-[10px] font-bold uppercase tracking-wider"
                                            x-text="form.id ? 'Set Hero Banner Image' : 'Save post to enable upload'"></span>
                                    </div>
                                </template>

                                <div x-show="form.hero_image" x-cloak
                                    class="absolute top-3 right-3 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <button @click.stop="$refs.heroInput.click()"
                                        class="bg-card text-forge-dark hover:text-rust p-2 border border-border shadow-sm"
                                        title="Replace Hero Image">
                                        <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-image-replace"></use></svg>
                                    </button>
                                    <button @click.stop="form.hero_image = ''"
                                        class="bg-danger-bg text-danger hover:bg-danger/10 p-2 border border-danger/20 shadow-sm"
                                        title="Remove Hero Image">
                                        <?php admin_icon('close', 'w-4 h-4'); ?>
                                    </button>
                                </div>
                                <input type="file" x-ref="heroInput" class="hidden" accept="image/*"
                                    @change="handleHeroUpload($event)">
                            </div>

                            <!-- Title Blocks (Trumpet, Headline, Deck)
                                 Classes match published Twig (.post-detail-*) so dual-duty skins
                                 style admin + publish from one rule block. -->
                            <div class="pt-6 pb-6 flex flex-col gap-4 traven-preview hero-title-block"
                                x-show="!collapsedPartials.includes('trumpet') || !collapsedPartials.includes('title') || !collapsedPartials.includes('deck')"
                                x-transition>
                                <div x-show="!collapsedPartials.includes('trumpet') && !form.page" x-transition>
                                    <input type="text" x-model="form.trumpet" @focus="activePartial = 'trumpet'"
                                        class="w-full bg-transparent border-0 outline-none px-0 placeholder:text-forge-mid/40 post-detail-trumpet"
                                        placeholder="Tagline (Trumpet / Eyebrow)">
                                </div>
                                <div x-show="!collapsedPartials.includes('title')" x-transition>
                                    <h1 class="post-detail-title">
                                        <textarea x-model="form.hero_title" @focus="activePartial = 'title'"
                                            class="w-full bg-transparent border-0 border-b border-transparent focus:border-border outline-none leading-tight px-0 placeholder:text-forge-mid/30 transition-colors resize-none overflow-hidden"
                                            placeholder="Headline / Post Title" rows="1" @keydown.enter.prevent=""
                                            @input="$el.style.height = '1px'; $el.style.height = $el.scrollHeight + 'px'"
                                            @pen:skin-changed.window="setTimeout(() => { $el.style.height = '1px'; $el.style.height = $el.scrollHeight + 'px'; }, 50); setTimeout(() => { $el.style.height = '1px'; $el.style.height = $el.scrollHeight + 'px'; }, 250);"
                                            x-init="$nextTick(() => { $el.style.height = '1px'; $el.style.height = $el.scrollHeight + 'px' }); $watch('form.hero_title', () => { $el.style.height = '1px'; $el.style.height = $el.scrollHeight + 'px' })"></textarea>
                                    </h1>
                                </div>
                                <div x-show="!collapsedPartials.includes('deck') && !form.page" x-transition>
                                    <textarea x-model="form.deck" @focus="activePartial = 'deck'"
                                        class="w-full bg-transparent border-0 outline-none px-0 resize-none overflow-hidden placeholder:text-forge-mid/40 mt-1 post-detail-deck"
                                        placeholder="Editorial deck / teaser under the title..." rows="1"
                                        @input="$el.style.height = 'auto'; $el.style.height = $el.scrollHeight + 'px'"
                                        @pen:skin-changed.window="setTimeout(() => { $el.style.height = 'auto'; $el.style.height = $el.scrollHeight + 'px'; }, 50); setTimeout(() => { $el.style.height = 'auto'; $el.style.height = $el.scrollHeight + 'px'; }, 250);"
                                        x-init="$nextTick(() => { $el.style.height = 'auto'; $el.style.height = $el.scrollHeight + 'px' }); $watch('form.deck', () => { $el.style.height = 'auto'; $el.style.height = $el.scrollHeight + 'px' })"></textarea>
                                </div>
                            </div>
                            <!-- Main Content Editor -->
                            <section class="overflow-hidden" x-show="!collapsedPartials.includes('main')"
                                x-transition>
                                <div id="main-editor" class="w-full bg-card"></div>
                                <!-- Raw Markdown Editor Mount -->
                                <div id="raw-main-editor" class="w-full bg-card raw-editor-mount"
                                    x-show="workspacePrefs.rawMarkdown"></div>
                            </section>
                        </div>

                        <!-- Composite Fragments -->
                        <template x-if="form.composite">
                            <div class="space-y-6">
                                <template x-for="(post, idx) in form.posts.slice(1)" :key="post.id">
                                    <section class="pen-card overflow-hidden"
                                        x-show="!collapsedPartials.includes(post.id)" x-transition>
                                        <div :id="'partial-editor-' + post.id" class="w-full bg-card"></div>
                                        <!-- Raw Markdown Editor Mount for Partials -->
                                        <div :id="'raw-partial-editor-' + post.id"
                                            class="w-full bg-card raw-editor-mount" x-show="workspacePrefs.rawMarkdown">
                                        </div>
                                    </section>
                                </template>
                            </div>
                        </template>
                        </div>
                    </div>

                    <!-- Divider hairline / Drag Handle (Right) -->
                    <div x-show="!workspacePrefs.rightColumnCollapsed"
                        class="hidden lg:block w-3 -mx-1.5 cursor-ew-resize self-stretch relative z-50 group select-none lg:order-4"
                        @mousedown="startResizeRight($event)">
                        <!-- Visual hairline inside the wider hover area (transition between 1px and 3px) -->
                        <div class="absolute inset-y-0 left-1/2 -translate-x-1/2 transition-all duration-150"
                            :class="isDraggingRightColumn ? 'w-[3px] bg-rust' : 'w-px bg-border/40 group-hover:w-[3px] group-hover:bg-rust'">
                        </div>
                    </div>

                    <!-- Right Column (Document Outline) (~25%) -->
                    <aside x-show="!workspacePrefs.rightColumnCollapsed"
                        class="w-full lg:w-[25%] resizable-right-column nav-resizable-right-column space-y-4 lg:space-y-0 lg:flex lg:flex-col lg:gap-4 lg:h-full lg:min-h-0 lg:order-5 lg:pl-6 lg:overflow-hidden">
                        <!-- Document Outline Accordion Card -->
                        <div class="lg:flex lg:flex-col"
                            :class="!workspacePrefs.documentOutlineCollapsed ? 'lg:flex-1 lg:min-h-0' : ''">
                            <!-- Accordion Trigger Header for Document Outline -->
                            <div class="flex items-center justify-between border-b border-border cursor-pointer select-none pb-2 w-full text-left font-sans outline-none focus-visible:ring-2 focus-visible:ring-rust"
                                @click="workspacePrefs.documentOutlineCollapsed = !workspacePrefs.documentOutlineCollapsed; saveWorkspacePrefs()">
                                <span class="text-[10px] font-black uppercase tracking-wider text-rust">Outline</span>
                                <div class="flex items-center gap-2" @click.stop>
                                    <!-- Add Fragment (only visible when expanded and composite is true) -->
                                    <button type="button" @click="addPartial()"
                                        x-show="!workspacePrefs.documentOutlineCollapsed && form.composite && !isTranslation"
                                        class="text-forge-mid hover:text-rust p-1 transition-colors"
                                        title="Add Fragment">
                                        <?php admin_icon('plus'); ?>
                                    </button>
                                    <svg @click="workspacePrefs.documentOutlineCollapsed = !workspacePrefs.documentOutlineCollapsed; saveWorkspacePrefs()" class="w-3 h-3 text-steel-muted transition-transform duration-200" :class="workspacePrefs.documentOutlineCollapsed ? '-rotate-90' : ''" fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-chevron-down"></use></svg>
                                </div>
                            </div>

                            <div class="space-y-3 lg:flex-1 lg:min-h-0 lg:overflow-y-auto scrollbar-thin pr-1 pt-2"
                                x-show="!workspacePrefs.documentOutlineCollapsed" x-transition>
                                <!-- Unified Header Cards Group -->
                                <div class="space-y-0">
                                    <!-- Hero Image Item -->
                                    <div class="flex items-center gap-2 w-full">
                                        <!-- Eye Visibility Column -->
                                        <div class="flex-shrink-0">
                                            <button @click.stop="toggleCollapse('hero')"
                                                class="p-1 text-forge-mid hover:text-rust transition-colors"
                                                :title="collapsedPartials.includes('hero') ? 'Show in editor' : 'Hide in editor'">
                                                <template x-if="!collapsedPartials.includes('hero')">
                                                    <?php admin_icon('eye'); ?>
                                                </template>
                                                <template x-if="collapsedPartials.includes('hero')">
                                                    <?php admin_icon('eye-slash'); ?>
                                                </template>
                                            </button>
                                        </div>
                                        <div class="flex-grow min-w-0 transition-all cursor-pointer relative py-1.5 px-2.5 shadow-none rounded-t"
                                            :class="(expandedPartial === 'hero' || activePartial === 'hero') ? 'border border-rust bg-card rounded-t' : 'border-t border-x border-border/60 bg-canvas hover:bg-card'"
                                            @click="scrollToSection('hero')">
                                            <div class="flex items-center justify-between">
                                                <code class="text-[9px] font-mono text-forge-mid">[HERO IMAGE]</code>
                                                <button
                                                    @click.stop="expandedPartial = (expandedPartial === 'hero' ? null : 'hero'); if(expandedPartial) activePartial = 'hero'"
                                                    class="p-1 text-forge-mid hover:text-rust transition-colors"
                                                    :class="expandedPartial === 'hero' && 'text-rust'"
                                                    title="Hero Image Settings">
                                                    <?php admin_icon('link'); ?>
                                                </button>
                                            </div>
                                            <div class="mt-0.5">
                                                <template x-if="expandedPartial !== 'hero'">
                                                    <span
                                                        class="text-[11px] font-semibold text-forge-dark truncate block py-0.5"
                                                        @click.stop="expandedPartial = 'hero'; activePartial = 'hero'; scrollToSection('hero')"
                                                        x-text="form.hero_image || 'No image set'"></span>
                                                </template>
                                                <template x-if="expandedPartial === 'hero'">
                                                    <div @click.stop
                                                        class="mt-2.5 pt-2.5 border-t border-border/40 space-y-2 cursor-default">
                                                        <!-- IF NO HERO IMAGE IS SET -->
                                                        <template x-if="!form.hero_image">
                                                            <div x-data="{ localDragOver: false }"
                                                                @click="if(form.id) $refs.outlineHeroInput.click()"
                                                                @dragover.prevent="if(form.id) localDragOver = true"
                                                                @dragleave="localDragOver = false"
                                                                @drop.prevent="localDragOver = false; if(form.id) handleHeroDrop($event)"
                                                                class="p-4 border border-dashed border-border flex flex-col items-center justify-center cursor-pointer hover:border-rust hover:bg-rust-wash/20 transition-all text-center"
                                                                :class="[!form.id && 'opacity-50 cursor-not-allowed', localDragOver ? 'border-rust bg-rust-wash/30' : 'border-border']">
                                                                <input type="file" x-ref="outlineHeroInput" class="hidden"
                                                                    accept="image/*" @change="handleHeroUpload($event)">
                                                                    <svg class="w-5 h-5 mb-1 text-forge-mid" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-plus-thin"></use></svg>
                                                                <span
                                                                    class="text-[9px] font-bold uppercase tracking-wider text-rust"
                                                                    x-text="form.id ? 'Drop or Click +' : 'Save post to upload'"></span>
                                                            </div>
                                                        </template>

                                                        <!-- IF HERO IMAGE IS SET -->
                                                        <template x-if="form.hero_image">
                                                            <div class="space-y-2">
                                                                <!-- Thumbnail -->
                                                                <div
                                                                    class="aspect-[21/9] w-full bg-card border border-border overflow-hidden">
                                                                    <img :src="contentAssetUrl(form.hero_image)"
                                                                        class="w-full h-full object-cover">
                                                                </div>
                                                                <!-- Actions -->
                                                                <div class="flex justify-between items-center gap-2 pt-1">
                                                                    <button @click.stop="$refs.outlineHeroInput.click()"
                                                                        class="flex-1 text-[10px] font-bold text-rust hover:text-rust-deep uppercase tracking-wider py-1 border border-rust/20 bg-rust-wash/10 hover:bg-rust-wash/30 text-center">
                                                                        Replace
                                                                    </button>
                                                                    <button @click.stop="form.hero_image = ''"
                                                                        class="flex-1 text-[10px] font-bold text-danger hover:text-red-700 uppercase tracking-wider py-1 border border-danger/10 bg-danger-bg hover:bg-danger-bg/80 text-center">
                                                                        Remove
                                                                    </button>
                                                                    <input type="file" x-ref="outlineHeroInput"
                                                                        class="hidden" accept="image/*"
                                                                        @change="handleHeroUpload($event)">
                                                                </div>
                                                            </div>
                                                        </template>
                                                    </div>
                                                </template>
                                            </div>
                                        </div>
                                    </div>

                                    <!-- Tagline / Trumpet Item -->
                                    <div class="flex items-center gap-2 w-full" x-show="!form.page">
                                        <!-- Eye Visibility Column -->
                                        <div class="flex-shrink-0">
                                            <button @click.stop="toggleCollapse('trumpet')"
                                                class="p-1 text-forge-mid hover:text-rust transition-colors"
                                                :title="collapsedPartials.includes('trumpet') ? 'Show in editor' : 'Hide in editor'">
                                                <template x-if="!collapsedPartials.includes('trumpet')">
                                                    <?php admin_icon('eye'); ?>
                                                </template>
                                                <template x-if="collapsedPartials.includes('trumpet')">
                                                    <?php admin_icon('eye-slash'); ?>
                                                </template>
                                            </button>
                                        </div>
                                        <div class="flex-grow min-w-0 transition-all cursor-pointer relative py-1.5 px-2.5 shadow-none"
                                            :class="(expandedPartial === 'trumpet' || activePartial === 'trumpet') ? 'border border-rust bg-card' : 'border-x border-border/60 bg-canvas hover:bg-card'"
                                            @click="scrollToSection('trumpet')">
                                            <div class="flex items-center justify-between">
                                                <code class="text-[9px] font-mono text-forge-mid">[TAGLINE / TRUMPET]</code>
                                                <button
                                                    @click.stop="expandedPartial = (expandedPartial === 'trumpet' ? null : 'trumpet'); if(expandedPartial) activePartial = 'trumpet'"
                                                    class="p-1 text-forge-mid hover:text-rust transition-colors"
                                                    :class="expandedPartial === 'trumpet' && 'text-rust'"
                                                    title="Tagline Settings">
                                                    <?php admin_icon('link'); ?>
                                                </button>
                                            </div>
                                            <div class="mt-0.5">
                                                <template x-if="expandedPartial !== 'trumpet'">
                                                    <span
                                                        class="text-[11px] font-semibold text-forge-dark truncate block py-0.5"
                                                        @click.stop="expandedPartial = 'trumpet'; activePartial = 'trumpet'; scrollToSection('trumpet')"
                                                        x-text="form.trumpet || 'No tagline set'"></span>
                                                </template>
                                                <template x-if="expandedPartial === 'trumpet'">
                                                    <input type="text" x-model="form.trumpet" @click.stop
                                                        @keydown.enter="expandedPartial = null"
                                                        @blur="expandedPartial = null"
                                                        class="w-full text-[11px] font-semibold text-forge-dark bg-transparent border-0 border-b border-rust outline-none py-0.5 px-0.5 !shadow-none focus:!shadow-none focus-visible:!shadow-none"
                                                        x-init="$nextTick(() => $el.focus())" placeholder="No tagline set">
                                                </template>
                                            </div>
                                        </div>
                                    </div>

                                    <!-- Headline / Title Item -->
                                    <div class="flex items-center gap-2 w-full">
                                        <!-- Eye Visibility Column -->
                                        <div class="flex-shrink-0">
                                            <button @click.stop="toggleCollapse('title')"
                                                class="p-1 text-forge-mid hover:text-rust transition-colors"
                                                :title="collapsedPartials.includes('title') ? 'Show in editor' : 'Hide in editor'">
                                                <template x-if="!collapsedPartials.includes('title')">
                                                    <?php admin_icon('eye'); ?>
                                                </template>
                                                <template x-if="collapsedPartials.includes('title')">
                                                    <?php admin_icon('eye-slash'); ?>
                                                </template>
                                            </button>
                                        </div>
                                        <div class="flex-grow min-w-0 transition-all cursor-pointer relative py-1.5 px-2.5 shadow-none"
                                            :class="(expandedPartial === 'title' || activePartial === 'title') ? 'border border-rust bg-card' : 'border-x border-border/60 bg-canvas hover:bg-card'"
                                            @click="scrollToSection('title')">
                                            <div class="flex items-center justify-between">
                                                <code class="text-[9px] font-mono text-forge-mid">[HEADLINE / TITLE]</code>
                                                <button
                                                    @click.stop="expandedPartial = (expandedPartial === 'title' ? null : 'title'); if(expandedPartial) activePartial = 'title'"
                                                    class="p-1 text-forge-mid hover:text-rust transition-colors"
                                                    :class="expandedPartial === 'title' && 'text-rust'"
                                                    title="Title Settings">
                                                    <?php admin_icon('link'); ?>
                                                </button>
                                            </div>
                                            <div class="mt-0.5">
                                                <template x-if="expandedPartial !== 'title'">
                                                    <span
                                                        class="text-[11px] font-semibold text-forge-dark truncate block py-0.5"
                                                        @click.stop="expandedPartial = 'title'; activePartial = 'title'; scrollToSection('title')"
                                                        x-text="form.hero_title || 'Untitled Title'"></span>
                                                </template>
                                                <template x-if="expandedPartial === 'title'">
                                                    <input type="text" x-model="form.hero_title" @click.stop
                                                        @keydown.enter="expandedPartial = null"
                                                        @blur="expandedPartial = null"
                                                        class="w-full text-[11px] font-semibold text-forge-dark bg-transparent border-0 border-b border-rust outline-none py-0.5 px-0.5 !shadow-none focus:!shadow-none focus-visible:!shadow-none"
                                                        x-init="$nextTick(() => $el.focus())" placeholder="Untitled Title">
                                                </template>
                                            </div>
                                        </div>
                                    </div>

                                    <!-- Deck Item (editorial deck under title) -->
                                    <div class="flex items-center gap-2 w-full" x-show="!form.page">
                                        <!-- Eye Visibility Column -->
                                        <div class="flex-shrink-0">
                                            <button @click.stop="toggleCollapse('deck')"
                                                class="p-1 text-forge-mid hover:text-rust transition-colors"
                                                :title="collapsedPartials.includes('deck') ? 'Show in editor' : 'Hide in editor'">
                                                <template x-if="!collapsedPartials.includes('deck')">
                                                    <?php admin_icon('eye'); ?>
                                                </template>
                                                <template x-if="collapsedPartials.includes('deck')">
                                                    <?php admin_icon('eye-slash'); ?>
                                                </template>
                                            </button>
                                        </div>
                                        <div class="flex-grow min-w-0 transition-all cursor-pointer relative py-1.5 px-2.5 shadow-none rounded-b"
                                            :class="(expandedPartial === 'deck' || activePartial === 'deck') ? 'border border-rust bg-card rounded-b' : 'border-x border-b border-border/60 bg-canvas hover:bg-card'"
                                            @click="scrollToSection('deck')">
                                            <div class="flex items-center justify-between">
                                                <code class="text-[9px] font-mono text-forge-mid">[DECK]</code>
                                                <button
                                                    @click.stop="expandedPartial = (expandedPartial === 'deck' ? null : 'deck'); if(expandedPartial) activePartial = 'deck'"
                                                    class="p-1 text-forge-mid hover:text-rust transition-colors"
                                                    :class="expandedPartial === 'deck' && 'text-rust'"
                                                    title="Deck Settings">
                                                    <?php admin_icon('link'); ?>
                                                </button>
                                            </div>
                                            <p class="text-[9px] text-forge-mid/80 mt-0.5 leading-snug">On-page teaser under the title. Expand target via source=&quot;deck&quot;.</p>
                                            <div class="mt-0.5">
                                                <template x-if="expandedPartial !== 'deck'">
                                                    <span
                                                        class="text-[11px] font-semibold text-forge-dark truncate block py-0.5"
                                                        @click.stop="expandedPartial = 'deck'; activePartial = 'deck'; scrollToSection('deck')"
                                                        x-text="form.deck || 'No deck set'"></span>
                                                </template>
                                                <template x-if="expandedPartial === 'deck'">
                                                    <textarea x-model="form.deck" @click.stop
                                                        @keydown.enter.prevent="if (!$event.shiftKey) expandedPartial = null"
                                                        @blur="expandedPartial = null"
                                                        class="w-full text-[11px] font-semibold text-forge-dark bg-transparent border-0 border-b border-rust outline-none py-0.5 px-0.5 !shadow-none focus:!shadow-none focus-visible:!shadow-none resize-none leading-relaxed"
                                                        rows="3" x-init="$nextTick(() => $el.focus())"
                                                        placeholder="No deck set"></textarea>
                                                </template>
                                            </div>
                                        </div>
                                    </div>

                                    <!-- Summary Item (Expand/Embed nutshell) -->
                                    <div class="flex items-center gap-2 w-full" x-show="!form.page">
                                        <div class="flex-shrink-0">
                                            <button @click.stop="toggleCollapse('summary')"
                                                class="p-1 text-forge-mid hover:text-rust transition-colors"
                                                :title="collapsedPartials.includes('summary') ? 'Show in editor' : 'Hide in editor'">
                                                <template x-if="!collapsedPartials.includes('summary')">
                                                    <?php admin_icon('eye'); ?>
                                                </template>
                                                <template x-if="collapsedPartials.includes('summary')">
                                                    <?php admin_icon('eye-slash'); ?>
                                                </template>
                                            </button>
                                        </div>
                                        <div class="flex-grow min-w-0 transition-all cursor-pointer relative py-1.5 px-2.5 shadow-none rounded-b"
                                            :class="(expandedPartial === 'summary' || activePartial === 'summary') ? 'border border-rust bg-card rounded-b' : 'border-x border-b border-border/60 bg-canvas hover:bg-card'"
                                            @click="scrollToSection('summary')">
                                            <div class="flex items-center justify-between">
                                                <code class="text-[9px] font-mono text-forge-mid">[SUMMARY]</code>
                                                <div class="flex items-center gap-0.5">
                                                    <button
                                                        type="button"
                                                        x-show="$store.app.use_ai"
                                                        x-cloak
                                                        @click.stop="runSummaryWand()"
                                                        class="p-1 text-forge-mid hover:text-rust transition-colors disabled:opacity-40"
                                                        :class="summaryWand.status !== 'idle' && 'text-rust'"
                                                        :disabled="summaryWand.status === 'loading'"
                                                        title="Fill summary from body">
                                                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" aria-hidden="true"><use href="#icon-magic-wand"></use></svg>
                                                    </button>
                                                    <button
                                                        @click.stop="expandedPartial = (expandedPartial === 'summary' ? null : 'summary'); if(expandedPartial) activePartial = 'summary'"
                                                        class="p-1 text-forge-mid hover:text-rust transition-colors"
                                                        :class="expandedPartial === 'summary' && 'text-rust'"
                                                        title="Summary Settings">
                                                        <?php admin_icon('link'); ?>
                                                    </button>
                                                </div>
                                            </div>
                                            <p class="text-[9px] text-forge-mid/80 mt-0.5 leading-snug">Expand/Embed nutshell via source=&quot;summary&quot;. Distinct from deck.</p>
                                            <div class="mt-0.5">
                                                <template x-if="expandedPartial !== 'summary'">
                                                    <span
                                                        class="text-[11px] font-semibold text-forge-dark truncate block py-0.5"
                                                        @click.stop="expandedPartial = 'summary'; activePartial = 'summary'; scrollToSection('summary')"
                                                        x-text="form.summary || 'No summary set'"></span>
                                                </template>
                                                <template x-if="expandedPartial === 'summary'">
                                                    <div @click.stop>
                                                    <textarea x-model="form.summary"
                                                        @keydown.enter.prevent="if (!$event.shiftKey && !summaryWandActive) expandedPartial = null"
                                                        @blur="if (!summaryWandActive) expandedPartial = null"
                                                        class="w-full text-[11px] font-semibold text-forge-dark bg-transparent border-0 border-b border-rust outline-none py-0.5 px-0.5 !shadow-none focus:!shadow-none focus-visible:!shadow-none resize-none leading-relaxed"
                                                        rows="3" x-init="$nextTick(() => $el.focus())"
                                                        placeholder="No summary set"></textarea>
                                                    <div x-show="summaryWand.status === 'confirm-replace'" class="mt-1.5 space-y-1">
                                                        <p class="text-[10px] text-forge-mid leading-snug">Replace existing summary? Generates a new nutshell from the body.</p>
                                                        <div class="flex items-center gap-2">
                                                            <button type="button" @click="confirmSummaryReplace()"
                                                                class="text-[9px] font-bold text-rust hover:text-rust-deep">Replace</button>
                                                            <button type="button" @click="discardSummaryWand()"
                                                                class="text-[9px] font-bold text-forge-mid hover:text-forge-dark">Cancel</button>
                                                        </div>
                                                    </div>
                                                    <div x-show="summaryWand.status === 'loading'" class="mt-1.5 text-[10px] text-forge-mid">Extracting nutshell…</div>
                                                    <div x-show="summaryWand.status === 'preview'" class="mt-1.5 space-y-1">
                                                        <p class="text-[8px] uppercase font-bold text-forge-mid tracking-wider">Preview</p>
                                                        <p class="text-[11px] font-semibold text-forge-dark leading-relaxed whitespace-pre-wrap" x-text="summaryWand.preview"></p>
                                                        <div class="flex items-center gap-2">
                                                            <button type="button" @click="applySummaryWand()"
                                                                class="text-[9px] font-bold text-rust hover:text-rust-deep">Apply</button>
                                                            <button type="button" @click="discardSummaryWand()"
                                                                class="text-[9px] font-bold text-forge-mid hover:text-forge-dark">Discard</button>
                                                        </div>
                                                    </div>
                                                    <div x-show="summaryWand.status === 'error'" class="mt-1.5 space-y-1">
                                                        <p class="text-[10px] text-danger leading-snug" x-text="summaryWand.error"></p>
                                                        <button type="button" @click="discardSummaryWand()"
                                                            class="text-[9px] font-bold text-forge-mid hover:text-forge-dark">Dismiss</button>
                                                    </div>
                                                    </div>
                                                </template>
                                            </div>
                                        </div>
                                    </div>

                                    <!-- FAQs Item (first-class Q&A list; public HTML + FAQPage when non-empty) -->
                                    <div id="editor-faqs-rail" class="flex items-center gap-2 w-full">
                                        <div class="flex-shrink-0">
                                            <button @click.stop="toggleCollapse('faqs')"
                                                class="p-1 text-forge-mid hover:text-rust transition-colors"
                                                :title="collapsedPartials.includes('faqs') ? 'Show in editor' : 'Hide in editor'">
                                                <template x-if="!collapsedPartials.includes('faqs')">
                                                    <?php admin_icon('eye'); ?>
                                                </template>
                                                <template x-if="collapsedPartials.includes('faqs')">
                                                    <?php admin_icon('eye-slash'); ?>
                                                </template>
                                            </button>
                                        </div>
                                        <div class="flex-grow min-w-0 transition-all cursor-pointer relative py-1.5 px-2.5 shadow-none rounded-b"
                                            :class="(expandedPartial === 'faqs' || activePartial === 'faqs') ? 'border border-rust bg-card rounded-b' : 'border-x border-b border-border/60 bg-canvas hover:bg-card'"
                                            @click="scrollToSection('faqs')">
                                            <div class="flex items-center justify-between">
                                                <code class="text-[9px] font-mono text-forge-mid">[FAQS]</code>
                                                <div class="flex items-center gap-0.5">
                                                    <button
                                                        type="button"
                                                        x-show="$store.app.use_ai"
                                                        x-cloak
                                                        @click.stop="runFaqsWand()"
                                                        class="p-1 text-forge-mid hover:text-rust transition-colors disabled:opacity-40"
                                                        :class="faqsWand.status !== 'idle' && 'text-rust'"
                                                        :disabled="faqsWand.status === 'loading'"
                                                        title="Fill FAQs from body">
                                                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" aria-hidden="true"><use href="#icon-magic-wand"></use></svg>
                                                    </button>
                                                    <button
                                                        @click.stop="if (faqsWandActive) { expandedPartial = 'faqs'; activePartial = 'faqs'; } else { expandedPartial = (expandedPartial === 'faqs' ? null : 'faqs'); if(expandedPartial) activePartial = 'faqs' }"
                                                        class="p-1 text-forge-mid hover:text-rust transition-colors"
                                                        :class="expandedPartial === 'faqs' && 'text-rust'"
                                                        title="FAQ Settings">
                                                        <?php admin_icon('link'); ?>
                                                    </button>
                                                </div>
                                            </div>
                                            <p class="text-[9px] text-forge-mid/80 mt-0.5 leading-snug">Optional Q&amp;A pairs stored on this post or page. Empty is valid. The public heading is FAQ or Backgrounder depending on the theme; schema stays FAQPage.</p>
                                            <div class="mt-0.5" @click.stop>
                                                <template x-if="expandedPartial !== 'faqs'">
                                                    <span
                                                        class="text-[11px] font-semibold text-forge-dark truncate block py-0.5"
                                                        @click="expandedPartial = 'faqs'; activePartial = 'faqs'; scrollToSection('faqs')"
                                                        x-text="(form.faqs && form.faqs.length) ? (form.faqs.length + (form.faqs.length === 1 ? ' question' : ' questions')) : 'No FAQs set'"></span>
                                                </template>
                                                <template x-if="expandedPartial === 'faqs'">
                                                    <div class="space-y-2 mt-1"
                                                        @focusout="if (!faqsWandActive && !$event.currentTarget.contains($event.relatedTarget)) expandedPartial = null">
                                                        <template x-for="(faq, faqIdx) in form.faqs" :key="faqIdx">
                                                            <div class="p-2 bg-canvas/50 border border-border/80 space-y-1.5 relative">
                                                                <div class="absolute top-1.5 right-1.5 flex items-center gap-0.5">
                                                                    <button type="button" @click="moveFaq(faqIdx, -1)"
                                                                        class="p-0.5 text-forge-mid hover:text-rust transition-colors disabled:opacity-30"
                                                                        :disabled="faqIdx === 0" title="Move up">
                                                                        <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="3"><use href="#icon-chevron-up"></use></svg>
                                                                    </button>
                                                                    <button type="button" @click="moveFaq(faqIdx, 1)"
                                                                        class="p-0.5 text-forge-mid hover:text-rust transition-colors disabled:opacity-30"
                                                                        :disabled="faqIdx === form.faqs.length - 1" title="Move down">
                                                                        <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="3"><use href="#icon-chevron-down"></use></svg>
                                                                    </button>
                                                                    <button type="button" @click="removeFaq(faqIdx)"
                                                                        class="p-0.5 text-forge-mid hover:text-danger transition-colors"
                                                                        title="Remove">
                                                                        <?php admin_icon('close'); ?>
                                                                    </button>
                                                                </div>
                                                                <div class="flex flex-col gap-1 pr-14">
                                                                    <label class="text-[8px] uppercase font-bold text-forge-mid">Question</label>
                                                                    <textarea x-model="faq.q"
                                                                        @blur="if (!faqsWandActive && !($event.relatedTarget && $event.relatedTarget.closest('#editor-faqs-rail'))) expandedPartial = null"
                                                                        class="w-full text-[11px] font-semibold text-forge-dark bg-transparent border-0 border-b border-border/80 focus:border-rust outline-none py-0.5 px-0.5 resize-none leading-relaxed"
                                                                        rows="2" placeholder="Question…"></textarea>
                                                                </div>
                                                                <div class="flex flex-col gap-1 pr-14">
                                                                    <label class="text-[8px] uppercase font-bold text-forge-mid">Answer</label>
                                                                    <textarea x-model="faq.a"
                                                                        @blur="if (!faqsWandActive && !($event.relatedTarget && $event.relatedTarget.closest('#editor-faqs-rail'))) expandedPartial = null"
                                                                        class="w-full text-[11px] font-semibold text-forge-dark bg-transparent border-0 border-b border-border/80 focus:border-rust outline-none py-0.5 px-0.5 resize-none leading-relaxed"
                                                                        rows="3" placeholder="Answer…"></textarea>
                                                                </div>
                                                            </div>
                                                        </template>
                                                        <div x-show="!form.faqs?.length"
                                                            class="text-[10px] text-forge-mid py-0.5">No FAQs set.</div>
                                                        <button type="button" @click="addFaq()"
                                                            class="text-[9px] font-bold text-rust hover:text-rust-deep">+
                                                            ADD QUESTION</button>
                                                        <div x-show="faqsWand.status === 'confirm-replace'" class="mt-1.5 space-y-1">
                                                            <p class="text-[10px] text-forge-mid leading-snug">Replace existing FAQs? Extracts Q&amp;A this body already answers.</p>
                                                            <div class="flex items-center gap-2">
                                                                <button type="button" @click="confirmFaqsReplace()"
                                                                    class="text-[9px] font-bold text-rust hover:text-rust-deep">Replace</button>
                                                                <button type="button" @click="discardFaqsWand()"
                                                                    class="text-[9px] font-bold text-forge-mid hover:text-forge-dark">Cancel</button>
                                                            </div>
                                                        </div>
                                                        <div x-show="faqsWand.status === 'loading'" class="mt-1.5 text-[10px] text-forge-mid">Extracting Q&amp;A…</div>
                                                        <div x-show="faqsWand.status === 'preview'" class="mt-1.5 space-y-1">
                                                            <p class="text-[8px] uppercase font-bold text-forge-mid tracking-wider">Preview</p>
                                                            <p x-show="!faqsWand.preview.length" class="text-[10px] text-forge-mid leading-snug">This piece is not Q&amp;A-shaped. Apply to keep an empty list (no FAQPage).</p>
                                                            <template x-for="(pair, previewIdx) in faqsWand.preview" :key="'faq-preview-' + previewIdx">
                                                                <div class="p-2 bg-canvas/50 border border-border/80 space-y-1">
                                                                    <p class="text-[11px] font-semibold text-forge-dark leading-relaxed" x-text="pair.q"></p>
                                                                    <p class="text-[11px] text-forge-dark leading-relaxed" x-text="pair.a"></p>
                                                                </div>
                                                            </template>
                                                            <div class="flex items-center gap-2">
                                                                <button type="button" @click="applyFaqsWand()"
                                                                    class="text-[9px] font-bold text-rust hover:text-rust-deep">Apply</button>
                                                                <button type="button" @click="discardFaqsWand()"
                                                                    class="text-[9px] font-bold text-forge-mid hover:text-forge-dark">Discard</button>
                                                            </div>
                                                        </div>
                                                        <div x-show="faqsWand.status === 'error'" class="mt-1.5 space-y-1">
                                                            <p class="text-[10px] text-danger leading-snug" x-text="faqsWand.error"></p>
                                                            <button type="button" @click="discardFaqsWand()"
                                                                class="text-[9px] font-bold text-forge-mid hover:text-forge-dark">Dismiss</button>
                                                        </div>
                                                    </div>
                                                </template>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <!-- Main Post Item -->
                                <div class="flex items-center gap-2 w-full">
                                    <!-- Eye Visibility Column -->
                                    <div class="flex-shrink-0">
                                        <button @click.stop="toggleCollapse('main')"
                                            class="p-1 text-forge-mid hover:text-rust transition-colors"
                                            :title="collapsedPartials.includes('main') ? 'Show in editor' : 'Hide in editor'">
                                            <template x-if="!collapsedPartials.includes('main')">
                                                <?php admin_icon('eye'); ?>
                                            </template>
                                            <template x-if="collapsedPartials.includes('main')">
                                                <?php admin_icon('eye-slash'); ?>
                                            </template>
                                        </button>
                                    </div>

                                    <!-- Main Post Card -->
                                    <div class="flex-grow min-w-0 border transition-all cursor-pointer relative py-1.5 px-2.5 shadow-none"
                                        :class="(settingsPost === form.posts[0] || (settingsPost === null && activePartial === 'main')) ? 'border-rust bg-card' : 'border-border/60 bg-canvas hover:bg-card'"
                                        @click="scrollToSection('main')">
                                        <div class="flex items-center justify-between">
                                            <code class="text-[9px] font-mono text-forge-mid"
                                                x-text="'content/' + (form.id || '[slug]') + '/index.md'"></code>
                                            <div class="flex items-center gap-1.5">
                                                <button @click.stop="togglePostSettings(form.posts[0])"
                                                    class="p-1 transition-colors"
                                                    :class="settingsPost === form.posts[0] ? 'text-rust' : 'text-forge-mid hover:text-rust'"
                                                    title="Post Settings">
                                                    <?php admin_icon('link'); ?>
                                                </button>
                                            </div>
                                        </div>
                                        <span class="text-[11px] font-semibold text-forge-dark truncate block mt-0.5"
                                            x-text="form.hero_title || 'Untitled Main Post'"></span>

                                        <!-- Collapsible Settings Panel -->
                                        <div x-show="settingsPost === form.posts[0]"
                                            x-transition:enter="transition ease-out duration-200"
                                            x-transition:enter-start="opacity-0 transform -translate-y-2"
                                            x-transition:enter-end="opacity-100 transform translate-y-0"
                                            x-transition:leave="transition ease-in duration-150"
                                            x-transition:leave-start="opacity-100 transform translate-y-0"
                                            x-transition:leave-end="opacity-0 transform -translate-y-2" @click.stop
                                            class="mt-3 pt-3 border-t border-border/40 space-y-3 text-left cursor-default">

                                            <!-- Tagline override -->
                                            <div class="flex flex-col gap-1">
                                                <label
                                                    class="text-[9px] uppercase font-bold text-forge-mid tracking-wider">Tagline
                                                    override</label>
                                                <input type="text" x-model="form.posts[0].trumpet"
                                                    class="w-full bg-canvas/40 border border-border text-xs py-1 px-2 focus:border-rust outline-none font-bold text-rust transition-colors"
                                                    :placeholder="form.trumpet || 'NONE'"
                                                    :class="!form.posts[0].trumpet && 'opacity-50 font-medium'">
                                                <p class="text-[8px] text-forge-mid">Overrides the global tagline for
                                                    this
                                                    specific post.</p>
                                            </div>

                                            <!-- Metadata specs -->
                                            <div class="space-y-2">
                                                <div class="flex justify-between items-center">
                                                    <label
                                                        class="text-[9px] uppercase font-bold text-forge-mid tracking-wider">Metadata
                                                        specs</label>
                                                    <button @click="addPostMetadata(form.posts[0])"
                                                        class="text-[9px] font-bold text-rust hover:text-rust-deep">+
                                                        ADD
                                                        ENTRY</button>
                                                </div>
                                                <div class="space-y-1.5">
                                                    <template x-for="(meta, mIdx) in form.posts[0].metadata"
                                                        :key="mIdx">
                                                        <div class="flex items-center gap-1.5">
                                                            <input type="text" x-model="form.posts[0].metadata[mIdx]"
                                                                class="w-full bg-canvas/40 border border-border text-xs py-1 px-2 focus:border-rust outline-none transition-colors"
                                                                placeholder="Value...">
                                                            <button
                                                                @click="removePostMetadata(form.posts[0], mIdx)"
                                                                class="text-forge-mid hover:text-danger transition-colors p-1 shrink-0">
                                                                <?php admin_icon('close'); ?>
                                                            </button>
                                                        </div>
                                                    </template>
                                                    <div x-show="!form.posts[0].metadata?.length"
                                                        class="text-[10px] text-forge-mid py-0.5">No metadata defined.
                                                    </div>
                                                </div>
                                            </div>

                                            <!-- Tag entities link -->
                                            <div class="space-y-2">
                                                <div class="flex justify-between items-center">
                                                    <label
                                                        class="text-[9px] uppercase font-bold text-forge-mid tracking-wider">Linked
                                                        entity tags</label>
                                                    <button @click="addPostTag(form.posts[0])"
                                                        class="text-[9px] font-bold text-rust hover:text-rust-deep">+
                                                        ADD
                                                        TAG</button>
                                                </div>
                                                <div class="space-y-2">
                                                    <template x-for="(tag, tIdx) in form.posts[0].tags" :key="tIdx">
                                                        <div
                                                            class="p-2 bg-canvas/50 border border-border/80 space-y-2 relative group">
                                                            <button @click="removePostTag(form.posts[0], tIdx)"
                                                                class="absolute top-1.5 right-1.5 text-forge-mid hover:text-danger transition-colors">
                                                                <?php admin_icon('close'); ?>
                                                            </button>
                                                            <div class="grid grid-cols-1 gap-1.5">
                                                                <div class="flex flex-col gap-1">
                                                                    <label
                                                                        class="text-[8px] uppercase font-bold text-forge-mid">Display
                                                                        text</label>
                                                                    <input type="text" x-model="tag.label"
                                                                        class="w-full bg-transparent border-b border-border/80 text-[11px] py-0.5 focus:border-rust outline-none transition-colors"
                                                                        placeholder="Label...">
                                                                </div>
                                                                <div class="flex flex-col gap-1">
                                                                    <label
                                                                        class="text-[8px] uppercase font-bold text-forge-mid">Slug</label>
                                                                    <input type="text" x-model="tag.href"
                                                                        class="w-full bg-transparent border-b border-border/80 text-[11px] py-0.5 focus:border-rust outline-none transition-colors"
                                                                        placeholder="#slug">
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </template>
                                                    <div x-show="!form.posts[0].tags?.length"
                                                        class="text-[10px] text-forge-mid py-0.5">No linked tags.</div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <!-- Fragments List -->
                                <template x-if="form.composite">
                                    <div class="space-y-3">
                                        <template x-for="(post, idx) in form.posts.slice(1)" :key="post.id">
                                            <div class="flex items-center gap-2 w-full">
                                                <!-- Eye Visibility Column -->
                                                <div class="flex-shrink-0">
                                                    <button @click.stop="toggleCollapse(post.id)"
                                                        class="p-1 text-forge-mid hover:text-rust transition-colors"
                                                        :title="collapsedPartials.includes(post.id) ? 'Show in editor' : 'Hide in editor'">
                                                        <template x-if="!collapsedPartials.includes(post.id)">
                                                            <?php admin_icon('eye'); ?>
                                                        </template>
                                                        <template x-if="collapsedPartials.includes(post.id)">
                                                            <?php admin_icon('eye-slash'); ?>
                                                        </template>
                                                    </button>
                                                </div>

                                                <!-- Fragment Card -->
                                                <div class="flex-grow min-w-0 border transition-all cursor-pointer relative py-1.5 pl-2.5 pr-7 shadow-none"
                                                    :class="(settingsPost === post || (settingsPost === null && activePartial === post.id)) ? 'border-rust bg-card' : 'border-border/60 bg-canvas hover:bg-card'"
                                                    @click="scrollToSection(post.id)">

                                                    <!-- Stacked Chevrons inside the card, hugging the border of the header area -->
                                                    <div
                                                        class="absolute right-0.5 top-0 h-9 flex flex-col justify-center gap-0 text-forge-mid border-l border-border/20 pl-0.5">
                                                        <!-- Reorder Up -->
                                                        <button @click.stop="moveFragment(idx + 1, -1)"
                                                            class="p-0.5 hover:text-rust transition-colors disabled:opacity-30"
                                                            :disabled="isTranslation || idx === 0" title="Move Up">
                                                            <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="3"><use href="#icon-chevron-up"></use></svg>
                                                        </button>
                                                        <!-- Reorder Down -->
                                                        <button @click.stop="moveFragment(idx + 1, 1)"
                                                            class="p-0.5 hover:text-rust transition-colors disabled:opacity-30"
                                                            :disabled="isTranslation || idx === form.posts.length - 2"
                                                            title="Move Down">
                                                            <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="3"><use href="#icon-chevron-down"></use></svg>
                                                        </button>
                                                    </div>

                                                    <div class="flex items-center justify-between pr-1">
                                                        <code
                                                            class="text-[9px] font-mono text-forge-mid truncate max-w-[65%]"
                                                            x-text="'_' + post.id + '.md'"></code>
                                                        <div class="flex items-center gap-1 shrink-0">
                                                            <!-- Settings -->
                                                            <button @click.stop="togglePostSettings(post)"
                                                                class="p-0.5 transition-colors ml-1"
                                                                :class="settingsPost === post ? 'text-rust' : 'text-forge-mid hover:text-rust'"
                                                                title="Fragment Settings">
                                                                <?php admin_icon('link'); ?>
                                                            </button>
                                                            <!-- Remove -->
                                                            <button @click.stop="removePartial(post.id)"
                                                                :disabled="isTranslation"
                                                                class="p-0.5 text-forge-mid hover:text-danger transition-colors"
                                                                title="Remove Fragment">
                                                                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-trash"></use></svg>
                                                            </button>
                                                        </div>
                                                    </div>
                                                    <template x-if="settingsPost !== post">
                                                        <span
                                                            class="text-[11px] font-semibold text-forge-dark truncate block mt-0.5 pr-1 py-0.5"
                                                            x-text="post.title || 'Untitled Fragment'"></span>
                                                    </template>
                                                    <template x-if="settingsPost === post">
                                                        <input type="text" x-model="post.title" @click.stop
                                                            class="w-full text-[11px] font-semibold text-forge-dark bg-transparent border-0 border-b border-rust outline-none py-0.5 px-0.5 !shadow-none focus:!shadow-none focus-visible:!shadow-none mt-0.5"
                                                            placeholder="Untitled Fragment">
                                                    </template>

                                                    <!-- Accordion Content -->
                                                    <div x-show="settingsPost === post"
                                                        x-transition:enter="transition ease-out duration-200"
                                                        x-transition:enter-start="opacity-0 transform -translate-y-2"
                                                        x-transition:enter-end="opacity-100 transform translate-y-0"
                                                        x-transition:leave="transition ease-in duration-150"
                                                        x-transition:leave-start="opacity-100 transform translate-y-0"
                                                        x-transition:leave-end="opacity-0 transform -translate-y-2"
                                                        @click.stop
                                                        class="mt-3 pt-3 border-t border-border/40 space-y-3 text-left cursor-default pr-2">

                                                        <!-- Tagline override -->
                                                        <div class="flex flex-col gap-1">
                                                            <label
                                                                class="text-[9px] uppercase font-bold text-forge-mid tracking-wider">Tagline
                                                                override</label>
                                                            <input type="text" x-model="post.trumpet"
                                                                class="w-full bg-canvas/40 border border-border text-xs py-1 px-2 focus:border-rust outline-none font-bold text-rust transition-colors"
                                                                :placeholder="form.trumpet || 'NONE'"
                                                                :class="!post.trumpet && 'opacity-50 font-medium'">
                                                            <p class="text-[8px] text-forge-mid">Overrides the global
                                                                tagline for this specific fragment.</p>
                                                        </div>

                                                        <!-- Metadata specs -->
                                                        <div class="space-y-2">
                                                            <div class="flex justify-between items-center">
                                                                <label
                                                                    class="text-[9px] uppercase font-bold text-forge-mid tracking-wider">Metadata
                                                                    specs</label>
                                                                <button @click="addPostMetadata(post)"
                                                                    class="text-[9px] font-bold text-rust hover:text-rust-deep">+
                                                                    ADD ENTRY</button>
                                                            </div>
                                                            <div class="space-y-1.5">
                                                                <template x-for="(meta, mIdx) in post.metadata"
                                                                    :key="mIdx">
                                                                    <div class="flex items-center gap-1.5">
                                                                        <input type="text"
                                                                            x-model="post.metadata[mIdx]"
                                                                            class="w-full bg-canvas/40 border border-border text-xs py-1 px-2 focus:border-rust outline-none transition-colors"
                                                                            placeholder="Value...">
                                                                        <button
                                                                            @click="removePostMetadata(post, mIdx)"
                                                                            class="text-forge-mid hover:text-danger transition-colors p-1 shrink-0">
                                                                            <?php admin_icon('close'); ?>
                                                                        </button>
                                                                    </div>
                                                                </template>
                                                                <div x-show="!post.metadata?.length"
                                                                    class="text-[10px] text-forge-mid py-0.5">No
                                                                    metadata
                                                                    defined.</div>
                                                            </div>
                                                        </div>

                                                        <!-- Tag entities link -->
                                                        <div class="space-y-2">
                                                            <div class="flex justify-between items-center">
                                                                <label
                                                                    class="text-[9px] uppercase font-bold text-forge-mid tracking-wider">Linked
                                                                    entity tags</label>
                                                                <button @click="addPostTag(post)"
                                                                    class="text-[9px] font-bold text-rust hover:text-rust-deep">+
                                                                    ADD TAG</button>
                                                            </div>
                                                            <div class="space-y-2">
                                                                <template x-for="(tag, tIdx) in post.tags"
                                                                    :key="tIdx">
                                                                    <div
                                                                        class="p-2 bg-canvas/50 border border-border/80 space-y-2 relative group">
                                                                        <button @click="removePostTag(post, tIdx)"
                                                                            class="absolute top-1.5 right-1.5 text-forge-mid hover:text-danger transition-colors">
                                                                            <?php admin_icon('close'); ?>
                                                                        </button>
                                                                        <div class="grid grid-cols-1 gap-1.5">
                                                                            <div class="flex flex-col gap-1">
                                                                                <label
                                                                                    class="text-[8px] uppercase font-bold text-forge-mid">Display
                                                                                    text</label>
                                                                                <input type="text" x-model="tag.label"
                                                                                    class="w-full bg-transparent border-b border-border/80 text-[11px] py-0.5 focus:border-rust outline-none transition-colors"
                                                                                    placeholder="Label...">
                                                                            </div>
                                                                            <div class="flex flex-col gap-1">
                                                                                <label
                                                                                    class="text-[8px] uppercase font-bold text-forge-mid">Slug</label>
                                                                                <input type="text" x-model="tag.href"
                                                                                    class="w-full bg-transparent border-b border-border/80 text-[11px] py-0.5 focus:border-rust outline-none transition-colors"
                                                                                    placeholder="#slug">
                                                                            </div>
                                                                        </div>
                                                                    </div>
                                                                </template>
                                                                <div x-show="!post.tags?.length"
                                                                    class="text-[10px] text-forge-mid py-0.5">No linked
                                                                    tags.</div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </template>
                                    </div>
                                </template>


                            </div>
                        </div>

                        <!-- AI Assistant (Inline Accordion Card) -->
                        <div x-show="$store.app.use_ai" x-cloak x-data="aiSidebar" data-ai-accordion-card
                            class="pt-4 scroll-mt-[160px] lg:flex lg:flex-col lg:min-h-0"
                            :class="!workspacePrefs.aiAssistantCollapsed ? 'lg:flex-1 lg:overflow-hidden' : ''">
                            <!-- Accordion Trigger Button for AI Assistant -->
                            <div class="flex items-center justify-between border-b border-border cursor-pointer select-none pb-2 w-full text-left font-sans outline-none focus-visible:ring-2 focus-visible:ring-rust"
                                @click="workspacePrefs.aiAssistantCollapsed = !workspacePrefs.aiAssistantCollapsed; saveWorkspacePrefs()">
                                <span class="text-[10px] font-black uppercase tracking-wider text-rust">AI</span>
                                <div class="flex items-center gap-2" @click.stop>
                                    <!-- New Conversation (only visible when expanded) -->
                                    <button type="button" @click="newConversation()"
                                        x-show="!workspacePrefs.aiAssistantCollapsed"
                                        class="text-forge-mid hover:text-rust p-1 transition-colors"
                                        title="New Conversation">
                                        <?php admin_icon('plus'); ?>
                                    </button>

                                    <!-- Undo (only visible when expanded and there's something to undo) -->
                                    <button type="button" @click="undo()"
                                        x-show="!workspacePrefs.aiAssistantCollapsed && undoStack.length > 0"
                                        class="text-forge-mid hover:text-rust flex items-center gap-1 transition-colors"
                                        title="Undo last AI edit">
                                        <svg class="w-3.5 h-3.5"><use href="#icon-undo-arrow"></use></svg>
                                    </button>

                                    <!-- Trash Conversation (functionally equivalent to New Conversation) -->
                                    <button type="button" @click="newConversation()"
                                        x-show="!workspacePrefs.aiAssistantCollapsed"
                                        class="text-forge-mid hover:text-rust p-1 transition-colors"
                                        title="Clear Conversation">
                                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-clear-conversation"></use></svg>
                                    </button>

                                    <svg @click="workspacePrefs.aiAssistantCollapsed = !workspacePrefs.aiAssistantCollapsed; saveWorkspacePrefs()" class="w-3 h-3 text-steel-muted transition-transform duration-200" :class="workspacePrefs.aiAssistantCollapsed ? '-rotate-90' : ''" fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-chevron-down"></use></svg>
                                </div>
                            </div>

                            <!-- Accordion Body (x-cloak and relative for containing token warning modal).
                                 flex-1 + min-h-0 so it fills the card, leaving the messages sibling
                                 to scroll internally while the prompt input stays pinned at the
                                 bottom of the visible right column. -->
                            <div class="relative flex flex-col gap-3 pt-2 lg:flex-1 lg:min-h-0 lg:overflow-hidden"
                                x-show="!workspacePrefs.aiAssistantCollapsed" x-cloak x-transition>

                                <!-- Chat Output Logs (transparent, no card frame, no shadow, messages area fills
                                     remaining space inside the capped accordion body and scrolls internally) -->
                                <div id="ai-chat-messages-container"
                                    class="flex-1 min-h-0 overflow-y-auto px-2 py-3 space-y-1 scrollbar-thin">
                                    <!-- Initial Greeting (vault unlock form) -->
                                    <template x-if="!vaultUnlocked">
                                        <div class="flex flex-col items-start gap-1">
                                            <div
                                                class="bg-white border border-border/60 text-forge-black self-start rounded-r-md rounded-bl-md p-3.5 max-w-[90%] shadow-sm w-full">
                                                <p class="text-xs font-serif leading-relaxed mb-3">
                                                    Unlock your vault to use AI.
                                                </p>
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
                                                        <p class="text-[10px] text-danger font-bold"
                                                            x-text="vaultUnlockError"></p>
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
                                                        <span
                                                            x-text="isUnlockingVault ? 'Unlocking...' : 'Unlock Vault'"></span>
                                                    </button>
                                                </form>
                                            </div>
                                        </div>
                                    </template>

                                    <!-- Messages List -->
                                    <template x-for="(msg, index) in messages" :key="index">
                                        <div class="flex w-full"
                                            :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
                                            <div class="group"
                                                :class="msg.role === 'user'
                                                    ? 'bg-[#f0e9e6] text-forge-black rounded-l-md rounded-br-md max-w-[85%] text-[15px] leading-tight font-serif px-2.5 py-2.5'
                                                    : (msg.role === 'tool' || (msg.tool_calls && msg.tool_calls.length > 0 && !msg.content))
                                                        ? 'bg-transparent text-forge-black max-w-[92%] -ml-1 text-sm leading-relaxed font-sans !py-0 !mt-1'
                                                        : 'bg-transparent text-forge-black max-w-[92%] -ml-1 text-sm leading-relaxed font-sans py-2.5 !mt-3'">
                                                <!-- Attached Images in Chat Bubble -->
                                                <template x-if="msg.attachedImages && msg.attachedImages.length > 0">
                                                    <div class="flex flex-wrap gap-1.5 mb-2 mt-0.5">
                                                        <template x-for="(img, imgIdx) in msg.attachedImages" :key="imgIdx">
                                                            <div class="relative group/img">
                                                                <img :src="img.dataUrl" 
                                                                     :alt="img.name" 
                                                                     :title="img.name" 
                                                                     class="max-w-[120px] max-h-[120px] object-contain border border-border bg-white rounded-none" />
                                                                <button type="button" 
                                                                        @click="removeImageFromChatAndPending(msg, imgIdx)" 
                                                                        class="absolute top-0.5 right-0.5 bg-forge-black/70 hover:bg-rust text-white w-4 h-4 flex items-center justify-center text-[9px] font-bold transition-colors" 
                                                                        title="Delete image from chat">✕</button>
                                                            </div>
                                                        </template>
                                                    </div>
                                                </template>

                                                <!-- Attached Files in Chat Bubble -->
                                                <template x-if="msg.attachedFiles && msg.attachedFiles.length > 0">
                                                    <div class="flex flex-col gap-1 mb-2 mt-0.5">
                                                        <template x-for="(file, fileIdx) in msg.attachedFiles" :key="fileIdx">
                                                            <div class="flex items-center gap-1.5 text-[11px] text-steel-muted font-sans leading-none">
                                                                <!-- Choose SVG based on extension (.md vs .txt/others) -->
                                                                <template x-if="file.name.endsWith('.md')">
                                                                <svg class="w-3.5 h-3.5 text-steel-muted shrink-0"><use href="#icon-download"></use></svg>
                                                                </template>
                                                                <template x-if="!file.name.endsWith('.md')">
                                                                <svg class="w-3.5 h-3.5 text-steel-muted shrink-0"><use href="#icon-upload"></use></svg>
                                                                </template>
                                                                <span x-text="file.name" class="font-normal"></span>
                                                                <span class="text-steel-muted/60" x-text="'(' + file.sizeKb + ' KB)'"></span>
                                                            </div>
                                                        </template>
                                                    </div>
                                                </template>
                                                <!-- Parsed HTML message context -->
                                                <div x-html="renderMsg(msg, index === messages.length - 1)"></div>

                                                <!-- Dynamic Vision Error Alert -->
                                                <template x-if="msg.errorType === 'image_input_not_supported'">
                                                    <div class="mt-2.5 p-3 border border-danger/20 bg-danger-bg text-danger text-xs font-sans">
                                                        <div class="flex items-center gap-1.5 font-bold mb-1.5">
                                                        <svg class="w-4 h-4 text-danger shrink-0" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-alert-triangle"></use></svg>
                                                            <span>Selected Model Does Not Support Image Inputs</span>
                                                        </div>
                                                        <p class="mb-2.5 leading-relaxed text-danger/90">Please choose a multimodal vision model, or remove the attached images to continue.</p>
                                                        <div class="flex gap-2">
                                                            <button type="button" @click="retryWithoutImages()"
                                                                class="px-2.5 py-1 bg-danger hover:bg-danger/90 text-white font-semibold transition-colors">
                                                                Retry Without Images
                                                            </button>
                                                            <button type="button" @click="clearAttachedImages()"
                                                                class="px-2.5 py-1 bg-white hover:bg-danger-bg text-danger border border-danger/20 font-semibold transition-colors">
                                                                Clear Images
                                                            </button>
                                                        </div>
                                                    </div>
                                                </template>

                                                <!-- Action controls for AI responses (if not streaming or user message) -->
                                                <div x-show="msg.role === 'assistant' && msg.content"
                                                    class="mt-2 pt-2 flex justify-start gap-2.5 select-none opacity-0 group-hover:opacity-100 transition-opacity">
                                                    <button @click="applyToEditor(msg.content)"
                                                        class="text-forge-mid hover:text-rust transition-colors"
                                                        title="Apply to Editor">
                                                        <svg class="w-4 h-4"><use href="#icon-apply-arrow"></use></svg>
                                                    </button>
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

                                    <!-- Streaming status indicator (inside scrollable area, left-aligned like assistant bubbles) -->
                                    <div x-show="streaming" x-cloak
                                        class="flex justify-start mt-2 mb-1 px-0">
                                        <span class="text-[10px] font-mono text-rust animate-pulse font-bold"
                                            x-text="streamingWord"></span>
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
                                                    <input type="radio" class="accent-rust" name="pen-handoff-save-editor" value="save" x-model="pendingOutgoingHandoff.saveChoice">
                                                    <span>Save first</span>
                                                </label>
                                                <label class="flex items-center gap-2 cursor-pointer text-forge-mid">
                                                    <input type="radio" class="accent-rust" name="pen-handoff-save-editor" value="discard" x-model="pendingOutgoingHandoff.saveChoice">
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

                                <!-- Prompt Input Area (frameless box, pinned to bottom of the accordion body) -->
                                <div class="pt-1 pb-3 select-none shrink-0">
                                    <div class="relative border border-border focus-within:border-rust transition-colors p-2 bg-white"
                                        x-data="{ dragOver: false }"
                                        @dragover.prevent="dragOver = true"
                                        @dragleave.prevent="dragOver = false"
                                        @drop.prevent="handleFileDrop($event); dragOver = false"
                                        :class="dragOver ? 'border-rust bg-rust-wash/20 ring-2 ring-rust/10' : ''"
                                        style="container-type:inline-size">
                                        <!-- Attached files chips/pills list -->
                                        <div x-show="(attachedFiles && attachedFiles.length > 0) || (attachedImages && attachedImages.length > 0)" class="flex flex-wrap gap-1.5 mb-2 pb-2 border-b border-border/40" x-cloak>
                                            <template x-for="(file, index) in attachedFiles" :key="'file-' + index">
                                                <div class="inline-flex items-center gap-1.5 bg-rust-wash text-rust text-[10px] font-sans font-semibold px-2.5 py-1 rounded-none border border-rust/10">
                                                <svg class="w-3.5 h-3.5 text-rust/80 shrink-0"><use href="#icon-save-disk"></use></svg>
                                                    <span x-text="file.name" class="truncate max-w-[120px]"></span>
                                                    <span class="text-steel-muted font-normal" x-text="'(' + Math.round(file.content.length / 100) / 10 + ' KB)'"></span>
                                                    <button type="button" @click="removeAttachedFile(index)" class="text-rust/60 hover:text-rust transition-colors font-bold ml-1" title="Remove attachment">✕</button>
                                                </div>
                                            </template>
                                            <template x-for="(img, index) in attachedImages" :key="'img-' + index">
                                                <div class="inline-flex items-center gap-1.5 text-[10px] font-sans font-semibold px-1.5 py-1 rounded-none border transition-colors duration-150"
                                                    :class="(img.width && Math.max(img.width, img.height) > 2048) ? 'bg-warning-bg text-warning border-warning/40' : 'bg-steel-light text-forge-mid border-border'"
                                                    :title="img.estimatedTokens ? 'Estimated tokens: ' + img.estimatedTokens + (Math.max(img.width || 0, img.height || 0) > 2048 ? ' (Warning: Large image)' : '') : (img.encoding ? 'Encoding...' : '')">
                                                    
                                                    <template x-if="img.encoding">
                                                    <svg class="w-5 h-5 rounded-none shrink-0 animate-spin text-steel-muted/60" fill="none"><use href="#icon-spinner"></use></svg>
                                                    </template>
                                                    <template x-if="!img.encoding && img.dataUrl">
                                                        <img :src="img.dataUrl" class="w-5 h-5 rounded-none object-cover shrink-0" :alt="img.name" />
                                                    </template>
                                                    
                                                    <span x-text="img.name" class="truncate max-w-[100px]"></span>
                                                    <span class="font-normal" :class="(img.width && Math.max(img.width, img.height) > 2048) ? 'text-warning' : 'text-steel-muted'" x-text="img.width ? img.width + '×' + img.height : '(' + Math.round(img.size / 1024) + ' KB)'"></span>
                                                    <button type="button" @click="removeAttachedImage(index)" class="transition-colors font-bold ml-0.5" :class="(img.width && Math.max(img.width, img.height) > 2048) ? 'text-warning hover:text-warning' : 'text-steel-muted hover:text-rust'" title="Remove image">✕</button>
                                                </div>
                                            </template>
                                        </div>

                                        <div class="relative flex items-end gap-2">
                                            <textarea id="ai-prompt-textarea" x-model="prompt"
                                                @input="autoGrow($event.target)" @keydown.enter="handleEnterKey($event)"
                                                @paste="handlePaste($event)"
                                                placeholder="Write a message..."
                                                class="flex-1 min-w-0 min-h-[44px] max-h-[320px] resize-none text-base font-serif bg-transparent p-1 pr-1 leading-snug placeholder-forge-mid/60 text-forge-black border-0 outline-none focus:!border-0 focus:!border-transparent focus:!outline-none focus:!ring-0"
                                                :disabled="streaming"></textarea>

                                            <!-- Tools Dropdown (fills the prompt input for review/edit before sending). Pinned top-right via absolute so it stays put while the textarea grows. -->
                                            <div class="absolute top-0.5 right-0.5 z-[150]" x-data="{ toolsOpen: false }">
                                                <button type="button" @click="toolsOpen = !toolsOpen"
                                                    @keydown.escape.window="toolsOpen = false" title="Tools"
                                                    class="flex items-center gap-1 text-[9px] font-black uppercase tracking-wider text-forge-mid hover:text-rust px-1.5 py-0.5 transition-colors"
                                                    :class="toolsOpen ? 'text-rust' : ''">
                                                    <svg class="w-3 h-3"><use href="#icon-wrench-tools"></use></svg>
                                                    <span class="prompt-tools-label font-serif">Tools</span>
                                                    <svg class="w-2.5 h-2.5 transition-transform duration-200" :class="toolsOpen ? 'rotate-180' : ''" fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-chevron-down"></use></svg>
                                                </button>
                                                <div x-show="toolsOpen" x-cloak x-transition @click.away="toolsOpen = false"
                                                    class="absolute right-0 bottom-full mb-1 w-[240px] bg-white border border-border shadow-md z-[150] max-h-[280px] overflow-y-auto scrollbar-thin flex flex-col">
                                                    <!-- SECTION: CONTENT -->
                                                    <div class="px-2.5 py-1.5 text-[8px] font-sans font-bold uppercase tracking-wider text-steel-muted bg-forge-light/30 border-b border-border/20">Content</div>
                                                    <button type="button" @click="fillPrompt('seo'); toolsOpen = false"
                                                        class="flex flex-col gap-0.5 w-full text-left px-2.5 py-2 hover:bg-rust-wash transition-colors border-b border-border/40">
                                                        <span
                                                            class="text-[10px] font-serif font-bold uppercase tracking-wider text-forge-black">SEO
                                                            Audit</span>
                                                        <span
                                                            class="text-[10px] font-serif text-forge-mid leading-snug">Analyze
                                                            title, meta, headings, keyword usage</span>
                                                    </button>
                                                    <button type="button" @click="fillPrompt('rewrite'); toolsOpen = false"
                                                        class="flex flex-col gap-0.5 w-full text-left px-2.5 py-2 hover:bg-rust-wash transition-colors border-b border-border/40">
                                                        <span
                                                            class="text-[10px] font-serif font-bold uppercase tracking-wider text-forge-black">Rewrite
                                                            Selection</span>
                                                        <span
                                                            class="text-[10px] font-serif text-forge-mid leading-snug">Engaging
                                                            rewrite preserving key information</span>
                                                    </button>
                                                    <button type="button" @click="fillPrompt('meta'); toolsOpen = false"
                                                        class="flex flex-col gap-0.5 w-full text-left px-2.5 py-2 hover:bg-rust-wash transition-colors border-b border-border/40">
                                                        <span
                                                            class="text-[10px] font-serif font-bold uppercase tracking-wider text-forge-black">Generate
                                                            Meta</span>
                                                        <span
                                                            class="text-[10px] font-serif text-forge-mid leading-snug">150–160
                                                            character meta description</span>
                                                    </button>
                                                    <button type="button" @click="fillPrompt('expand'); toolsOpen = false"
                                                        class="flex flex-col gap-0.5 w-full text-left px-2.5 py-2 hover:bg-rust-wash transition-colors border-b border-border/40">
                                                        <span
                                                            class="text-[10px] font-serif font-bold uppercase tracking-wider text-forge-black">Expand
                                                            Text</span>
                                                        <span class="text-[10px] font-serif text-forge-mid leading-snug">Add
                                                            detail, examples, supporting information</span>
                                                    </button>
                                                    <button type="button" @click="fillPrompt('links'); toolsOpen = false"
                                                        class="flex flex-col gap-0.5 w-full text-left px-2.5 py-2 hover:bg-rust-wash transition-colors border-b border-border/40">
                                                        <span
                                                            class="text-[10px] font-serif font-bold uppercase tracking-wider text-forge-black">Suggest
                                                            Links</span>
                                                        <span
                                                            class="text-[10px] font-serif text-forge-mid leading-snug">Internal
                                                            link options via tool search</span>
                                                    </button>
                                                    <button type="button" @click="fillPrompt('quality_check'); toolsOpen = false"
                                                        class="flex flex-col gap-0.5 w-full text-left px-2.5 py-2 hover:bg-rust-wash transition-colors border-b border-border/40">
                                                        <span
                                                            class="text-[10px] font-serif font-bold uppercase tracking-wider text-forge-black">Quality Check</span>
                                                        <span
                                                            class="text-[10px] font-serif text-forge-mid leading-snug">Evaluate post against quality checklist & scorecard</span>
                                                    </button>

                                                    <!-- SECTION: MEDIA -->
                                                    <div class="px-2.5 py-1.5 text-[8px] font-sans font-bold uppercase tracking-wider text-steel-muted bg-forge-light/30 border-b border-border/20">Media</div>
                                                    <button type="button" @click="fillPrompt('generate_image'); toolsOpen = false"
                                                        class="flex flex-col gap-0.5 w-full text-left px-2.5 py-2 hover:bg-rust-wash transition-colors border-b border-border/40">
                                                        <span
                                                            class="text-[10px] font-serif font-bold uppercase tracking-wider text-forge-black">Generate AI Image</span>
                                                        <span
                                                            class="text-[10px] font-serif text-forge-mid leading-snug">Create a contextual post image using prompt</span>
                                                    </button>
                                                    <button type="button" @click="fillPrompt('attach_images'); toolsOpen = false"
                                                        class="flex flex-col gap-0.5 w-full text-left px-2.5 py-2 hover:bg-rust-wash transition-colors border-b border-border/40">
                                                        <span
                                                            class="text-[10px] font-serif font-bold uppercase tracking-wider text-forge-black">Add images to Media Gallery</span>
                                                        <span
                                                            class="text-[10px] font-serif text-forge-mid leading-snug">Save attached uploads to the gallery & post</span>
                                                    </button>

                                                    <!-- SECTION: WORKFLOW -->
                                                    <div class="px-2.5 py-1.5 text-[8px] font-sans font-bold uppercase tracking-wider text-steel-muted bg-forge-light/30 border-b border-border/20">Workflow</div>
                                                    <button type="button" @click="fillPrompt('git_commit'); toolsOpen = false"
                                                        class="flex flex-col gap-0.5 w-full text-left px-2.5 py-2 hover:bg-rust-wash transition-colors">
                                                        <span
                                                            class="text-[10px] font-serif font-bold uppercase tracking-wider text-forge-black">Commit & Push</span>
                                                        <span
                                                            class="text-[10px] font-serif text-forge-mid leading-snug">Stage changes, generate commit message & push</span>
                                                    </button>
                                                </div>
                                            </div>

                                            <div class="flex items-center gap-1.5 shrink-0 self-end">
                                                <!-- Add File '+' Button inside action row -->
                                                <button type="button" @click="$refs.fileInput.click()"
                                                    :disabled="streaming"
                                                    class="p-1.5 rounded-full transition-colors shrink-0 mb-0.5"
                                                    :class="streaming ? 'text-steel-muted cursor-not-allowed' : 'text-forge-mid hover:text-rust hover:bg-rust-wash cursor-pointer'"
                                                    title="Attach file: text (.txt, .md) or image (.png, .jpg, .gif, .webp)">
                                                    <svg class="w-3.5 h-3.5"><use href="#icon-attach-paperclip"></use></svg>
                                                </button>
                                                <input type="file" x-ref="fileInput" @change="handleFileSelect($event)" accept=".txt,.md,image/png,image/jpeg,image/gif,image/webp" class="hidden" multiple />

                                                <button x-show="streaming" type="button" @click="cleanup()"
                                                    class="p-1.5 text-danger hover:bg-danger-wash rounded-full transition-colors"
                                                    title="Stop Generation">
                                                    <svg class="w-5 h-5 animate-pulse" fill="currentColor"><use href="#icon-stop-square"></use></svg>
                                                </button>

                                                <!-- Send button -->
                                                <button x-show="!streaming" type="button" @click="sendPrompt()"
                                                    :disabled="(!prompt.trim() && attachedFiles.length === 0 && attachedImages.length === 0) || attachedImages.some(i => i.encoding)"
                                                    class="p-1.5 text-rust disabled:text-steel-muted hover:bg-rust-wash rounded-full transition-colors cursor-pointer disabled:cursor-not-allowed"
                                                    title="Send Prompt">
                                                    <svg class="w-5 h-5 text-rust"><use href="#icon-send-plane"></use></svg>
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <div x-show="tokenWarningModalOpen" x-cloak x-transition
                                    class="absolute inset-0 bg-forge-black/40 backdrop-blur-sm flex items-center justify-center p-4 z-[200]">
                                    <div class="bg-white border-[3px] border-rust p-5 shadow-stamp w-full max-w-[320px] font-sans text-left"
                                        @click.away="confirmTokenWarning(false)"
                                        @keydown.escape.window="confirmTokenWarning(false)">
                                        <div class="flex items-center gap-2 text-rust mb-3">
                                        <svg class="w-5 h-5 text-rust animate-pulse" fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-alert-triangle"></use></svg>
                                            <h3 class="text-xs font-black uppercase tracking-wider text-forge-black">
                                                Large Prompt Warning</h3>
                                        </div>
                                        <div class="space-y-2 mb-4 select-none">
                                            <p class="text-xs text-forge-black font-sans leading-relaxed">
                                                This request is approximately <strong class="text-rust font-mono"
                                                    x-text="tokenWarningCount"></strong> tokens.
                                            </p>
                                            <p class="text-[11px] text-forge-muted font-serif leading-prose">
                                                Large prompts can be slow and consume more credits. Would you like to
                                                continue?
                                            </p>
                                        </div>
                                        <div class="flex justify-end gap-2.5 select-none">
                                            <button @click="confirmTokenWarning(false)"
                                                class="px-3 py-1.5 bg-canvas border border-border text-[10px] font-black uppercase tracking-wider text-forge-mid hover:text-forge-black hover:border-forge-black transition-colors shadow-sm">
                                                Cancel
                                            </button>
                                            <button @click="confirmTokenWarning(true)"
                                                class="px-3 py-1.5 bg-rust border border-rust text-[10px] font-black uppercase tracking-wider text-white hover:bg-rust-dark hover:border-rust-dark transition-colors shadow-sm">
                                                Continue
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </aside>

                    <!-- Divider hairline / Drag Handle (Left) -->
                    <div x-show="!workspacePrefs.leftColumnCollapsed"
                        class="hidden lg:block w-3 -mx-1.5 cursor-ew-resize self-stretch relative z-50 group select-none lg:order-2"
                        @mousedown="startResizeLeft($event)">
                        <!-- Visual hairline inside the wider hover area (transition between 1px and 3px) -->
                        <div class="absolute inset-y-0 left-1/2 -translate-x-1/2 transition-all duration-150"
                            :class="isDraggingLeftColumn ? 'w-[3px] bg-rust' : 'w-px bg-border/40 group-hover:w-[3px] group-hover:bg-rust'">
                        </div>
                    </div>

                    <!-- ============================================== -->
                    <!-- Left Column (Sidebar) (~32%)                    -->
                    <!-- ============================================== -->
                    <aside x-show="!workspacePrefs.leftColumnCollapsed"
                        class="w-full lg:w-[32%] resizable-left-column nav-resizable-left-column space-y-6 lg:space-y-0 lg:flex lg:flex-col lg:gap-6 lg:h-full lg:min-h-0 lg:order-1 lg:pr-6 lg:z-50 lg:overflow-visible">

                        <!-- Properties Spec Card -->
                        <div class="pen-card p-6 lg:shrink-0">
                            <div class="flex items-center justify-between border-border cursor-pointer select-none"
                                :class="workspacePrefs.propertiesCardCollapsed ? 'pb-0 mb-0 border-b-0' : 'border-b pb-3 mb-5'"
                                @click="workspacePrefs.propertiesCardCollapsed = !workspacePrefs.propertiesCardCollapsed; saveWorkspacePrefs()">
                                <span
                                    class="text-[10px] font-black uppercase tracking-wider text-rust">Properties</span>
                                <div class="flex items-center gap-2">
                                    <div class="w-2 h-2"
                                        :class="validationPercentage === 100 ? 'bg-acid' : 'bg-warning'"></div>
                                        <svg class="w-3 h-3 text-steel-muted transition-transform duration-200" :class="workspacePrefs.propertiesCardCollapsed ? '-rotate-90' : ''" fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-chevron-down"></use></svg>
                                </div>
                            </div>

                            <div class="space-y-4" x-show="!workspacePrefs.propertiesCardCollapsed" x-transition>
                                <div class="flex flex-col gap-0.5">
                                    <label class="pen-label">Internal name *</label>
                                    <input type="text" x-model="form.name" class="pen-input"
                                        placeholder="Title / Reference Name">
                                </div>
                                <div class="flex flex-col gap-0.5">
                                    <label class="pen-label">Slug / ID *</label>
                                    <input type="text" x-model="form.id" class="pen-input font-mono text-xs"
                                        :disabled="!isNew" @input="slugManuallyEdited = true">
                                    <p class="text-[9px] text-forge-mid mt-0.5 uppercase font-bold tracking-widest"
                                        x-text="isNew ? 'Auto-generated' : 'Permanent ID'"></p>
                                </div>

                                <div x-show="isTranslation" x-cloak
                                    class="p-3 border border-border bg-canvas text-[9px] text-forge-mid font-serif">
                                    Slug, language, translation group, content kind, taxonomy identity, tags, domain, and composite manifest are inherited from the default sibling and locked. Prose and locale-local fragment contents remain editable.
                                </div>

                                <div class="grid grid-cols-2 gap-4" x-show="!form.page">
                                    <div class="flex flex-col gap-0.5">
                                        <label class="pen-label"
                                            x-text="(config?.taxonomy?.[config?.primary_vocabulary]?.label || 'Category') + ' *'"></label>
                                        <select x-model="form.category"
                                            :disabled="isTranslation"
                                            class="pen-select text-xs font-bold bg-card cursor-pointer">
                                            <template
                                                x-for="term in (config?.taxonomy?.[config?.primary_vocabulary]?.terms || [])"
                                                :key="term">
                                                <option :value="term" x-text="term"></option>
                                            </template>
                                        </select>
                                    </div>
                                    <div class="flex flex-col gap-0.5">
                                        <label class="pen-label">Date</label>
                                        <input type="date" x-model="form.date" class="pen-input font-mono text-xs">
                                    </div>
                                </div>

                                <div class="flex flex-col gap-0.5" x-show="form.status === 'published'">
                                    <label class="pen-label">Go live at</label>
                                    <input type="datetime-local"
                                        class="pen-input font-mono text-xs"
                                        :value="publishAtForInput()"
                                        @change="setPublishAtFromInput($event.target.value)">
                                    <p class="text-[9px] text-forge-mid mt-0.5 uppercase font-bold tracking-widest"
                                        x-text="isScheduled() ? 'Scheduled — not listed until this time' : (form.publish_at ? 'Past or now — lists immediately' : 'Empty — lists as soon as published')"></p>
                                </div>

                                <div class="flex flex-col gap-0.5" x-show="!form.page">
                                    <label class="pen-label">Author</label>
                                    <select x-model="authorSelect"
                                        @change="onAuthorSelectChange()"
                                        class="pen-select text-xs bg-card cursor-pointer">
                                        <option value="">— Clear —</option>
                                        <template x-for="siteAuthor in authors" :key="siteAuthor.slug">
                                            <option :value="siteAuthor.name"
                                                x-text="siteAuthor.role ? (siteAuthor.name + ' — ' + siteAuthor.role) : siteAuthor.name"></option>
                                        </template>
                                        <option value="__custom__">Custom…</option>
                                    </select>
                                    <input type="text"
                                        x-show="authorMode === 'custom'"
                                        x-model="authorCustom"
                                        @input="onAuthorCustomInput()"
                                        class="pen-input mt-1"
                                        placeholder="Custom byline">
                                    <p class="text-[9px] text-forge-mid mt-0.5 font-serif"
                                        x-show="authors.length === 0">
                                        No authors for this site.
                                        <a href="admin-settings-site.php" class="text-rust underline hover:no-underline">Site Settings → Authors</a>
                                    </p>
                                </div>

                                <div class="flex items-center gap-3" x-show="!form.page" x-cloak>
                                    <button type="button"
                                        @click="form.pinned = !form.pinned"
                                        :disabled="isTranslation"
                                        class="p-1 rounded transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-rust/30"
                                        :class="form.pinned ? 'text-rust' : 'text-forge-mid opacity-40 hover:opacity-70'"
                                        :title="form.pinned ? 'Unpin post' : 'Pin post'"
                                        :aria-pressed="form.pinned ? 'true' : 'false'"
                                        aria-label="Toggle pin">
                                        <svg class="w-5 h-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" aria-hidden="true"><rect width="256" height="256" fill="none"/><path d="M229.66,98.34a8,8,0,0,0,0-11.31L169,26.34a8,8,0,0,0-11.31,0L100.39,83.8S72.64,69.93,43,93.85a8,8,0,0,0-.65,11.91l107.9,107.89a8,8,0,0,0,12-.83c8.39-11.16,21.57-34.09,10.11-57Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><line x1="96.29" y1="159.71" x2="48" y2="208" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>
                                    </button>
                                    <span class="font-sans font-normal text-[10px] uppercase tracking-wider text-forge-dark select-none"
                                        x-text="form.pinned ? 'Pinned' : 'Pin post'"></span>
                                </div>

                                <div class="flex items-center gap-3">
                                    <input type="checkbox" x-model="form.noindex" id="noindex-v4"
                                        class="pen-checkbox">
                                    <label for="noindex-v4"
                                        class="font-sans font-normal text-[10px] uppercase tracking-wider text-forge-dark cursor-pointer select-none">Hide from search engines</label>
                                </div>
                                <p class="text-[9px] text-forge-mid -mt-1 font-serif leading-snug">Keeps the URL published. Adds noindex to HTML and omits it from sitemap, RSS, llms.txt, and search.</p>

                                <div class="flex items-center gap-3">
                                    <input type="checkbox" x-model="form.page" id="page-v4"
                                        :disabled="isTranslation"
                                        class="pen-checkbox">
                                    <label for="page-v4"
                                        class="font-sans font-normal text-[10px] uppercase tracking-wider text-forge-dark cursor-pointer select-none">This Post is a Page</label>
                                </div>

                                <div class="flex items-center gap-3">
                                    <input type="checkbox" x-model="form.composite" id="composite-v4"
                                        :disabled="isTranslation"
                                        class="pen-checkbox">
                                    <label for="composite-v4"
                                        class="font-sans font-normal text-[10px] uppercase tracking-wider text-forge-dark cursor-pointer select-none">Composite
                                        Post (Fragments)</label>
                                </div>
                            </div>
                        </div>

                        <!-- Dynamic Classification Card -->
                        <template
                            x-if="!form.page && config?.taxonomy && Object.keys(config.taxonomy).filter(k => k !== config.primary_vocabulary && config.taxonomy[k].controlled).length > 0">
                            <div class="pen-card p-6 lg:shrink-0">
                                <div class="flex items-center justify-between border-border cursor-pointer select-none"
                                    :class="workspacePrefs.classificationCardCollapsed ? 'pb-0 mb-0 border-b-0' : 'border-b pb-3 mb-4'"
                                    @click="workspacePrefs.classificationCardCollapsed = !workspacePrefs.classificationCardCollapsed; saveWorkspacePrefs()">
                                    <span class="text-[10px] font-black uppercase tracking-wider text-rust">Tags</span>
                                    <svg class="w-3 h-3 text-steel-muted transition-transform duration-200" :class="workspacePrefs.classificationCardCollapsed ? '-rotate-90' : ''" fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-chevron-down"></use></svg>
                                </div>
                                <div class="space-y-4" x-show="!workspacePrefs.classificationCardCollapsed"
                                    x-transition>
                                    <template
                                        x-for="[vocabKey, vocab] in Object.entries(config.taxonomy).filter(([k, v]) => k !== config.primary_vocabulary && v.controlled)"
                                        :key="vocabKey">
                                        <div class="flex flex-col gap-0.5">
                                            <label class="pen-label" x-text="vocab.label || vocabKey"></label>
                                            <select x-model="form['taxonomy_' + vocabKey]"
                                                :disabled="isTranslation"
                                                class="pen-select text-xs bg-card">
                                                <option value="">— None —</option>
                                                <template x-for="term in vocab.terms" :key="term">
                                                    <option :value="term" x-text="term"></option>
                                                </template>
                                            </select>
                                        </div>
                                    </template>
                                </div>
                            </div>
                        </template>

                        <!-- Media Gallery Card -->
                        <div class="lg:flex lg:flex-col relative" :class="!workspacePrefs.mediaGalleryCardCollapsed ? 'lg:flex-1 lg:min-h-0' : ''">
                            <div class="flex items-center justify-between border-b border-border w-full text-left font-sans outline-none pb-0">
                                <!-- Tabs -->
                                <div class="flex gap-4 -mb-[1px]">
                                    <span class="flex items-center mr-[-8px] pb-2 border-b-2 border-transparent transition-colors duration-200"
                                        :class="activeMediaTab === 'local' ? 'text-rust' : 'text-forge-mid'">
                                        <svg class="w-[18px] h-[18px]"><use href="#icon-tabs-grid"></use></svg>
                                    </span>
                                    <button
                                        @click="activeMediaTab = 'local'; if(workspacePrefs.mediaGalleryCardCollapsed) { workspacePrefs.mediaGalleryCardCollapsed = false; saveWorkspacePrefs(); }"
                                        class="text-[10px] font-black uppercase tracking-wider transition-colors outline-none focus-visible:ring-1 focus-visible:ring-rust pb-2 border-b-2"
                                        :class="activeMediaTab === 'local' ? 'text-rust border-rust' : 'text-forge-mid hover:text-rust border-transparent'"
                                        title="This page's media">
                                        This Page
                                    </button>
                                    <button
                                        @click="activeMediaTab = 'global'; if(workspacePrefs.mediaGalleryCardCollapsed) { workspacePrefs.mediaGalleryCardCollapsed = false; saveWorkspacePrefs(); }"
                                        class="text-[10px] font-black uppercase tracking-wider transition-colors outline-none focus-visible:ring-1 focus-visible:ring-rust pb-2 border-b-2"
                                        :class="activeMediaTab === 'global' ? 'text-rust border-rust' : 'text-forge-mid hover:text-rust border-transparent'"
                                        title="All media">
                                        Library
                                    </button>
                                </div>
                                <div class="flex items-center gap-2 cursor-pointer select-none pb-2"
                                    @click="workspacePrefs.mediaGalleryCardCollapsed = !workspacePrefs.mediaGalleryCardCollapsed; saveWorkspacePrefs()">
                                    <span class="text-[9px] font-bold text-forge-mid"
                                        x-text="activeMediaTab === 'local' ? (availableAssets.length + ' assets') : (filteredGlobalAssets.length + ' assets')"></span>
                                        <svg class="w-3 h-3 text-steel-muted transition-transform duration-200" :class="workspacePrefs.mediaGalleryCardCollapsed ? '-rotate-90' : ''" fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-chevron-down"></use></svg>
                                </div>
                            </div>

                            <!-- Floating Hover Preview Tooltip -->
                            <div x-show="hoveredAsset" x-cloak x-transition.opacity
                                class="hidden lg:block absolute left-[102%] top-0 w-80 bg-card border border-border p-3 shadow-xl z-[150] pointer-events-none text-left"
                                style="display: none;">
                                <div class="flex flex-col gap-2">
                                    <div class="aspect-video bg-canvas border border-border overflow-hidden flex items-center justify-center">
                                        <img :src="hoveredAsset?.url" class="max-h-full max-w-full object-contain">
                                    </div>
                                    <div class="space-y-1">
                                        <p class="text-[10px] font-bold text-forge-black truncate" x-text="hoveredAsset?.filename"></p>
                                        <div class="flex items-center justify-between text-[8px] text-forge-mid font-mono uppercase">
                                            <span x-text="hoveredAsset?.entity_id"></span>
                                            <span x-text="hoveredAsset?.size_bytes ? formatBytes(hoveredAsset.size_bytes) : ''"></span>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div class="space-y-4 lg:space-y-0 lg:gap-4 lg:flex lg:flex-col lg:flex-1 lg:min-h-0 pt-2" x-show="!workspacePrefs.mediaGalleryCardCollapsed" x-transition>
                                <!-- Direct upload box -->
                                <div x-show="activeMediaTab === 'local'" x-cloak x-data="{ localDragOver: false }" @click="if(form.id) $refs.assetInput.click()"
                                    @dragover.prevent="if(form.id) localDragOver = true"
                                    @dragleave="localDragOver = false"
                                    @drop.prevent="localDragOver = false; if(form.id) handleDrop($event)"
                                    class="p-4 border-2 border-dashed flex flex-col items-center justify-center cursor-pointer hover:border-rust hover:bg-rust-wash/20 transition-all text-center lg:shrink-0"
                                    :class="[!form.id && 'opacity-50 cursor-not-allowed', localDragOver ? 'border-rust bg-rust-wash/30' : 'border-border']">
                                    <input type="file" x-ref="assetInput" class="hidden" accept="image/*"
                                        @change="handleFileUpload($event)">
                                        <svg class="w-6 h-6 mb-1 text-forge-mid" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-plus-thin"></use></svg>
                                    <span class="text-[10px] font-bold uppercase tracking-wider text-rust"
                                        x-text="form.id ? 'Upload Image' : 'Save post first to upload'"></span>
                                </div>

                                <!-- Search and Sort Controls (Global Library only) -->
                                <div x-show="activeMediaTab === 'global'" x-cloak class="flex gap-2 pb-2 lg:shrink-0">
                                    <input type="text" x-model="globalSearchQuery" placeholder="Search..."
                                        class="flex-1 pen-input text-[11px] py-1 px-2 h-7" />

                                    <select x-model="globalSortOrder"
                                        class="pen-select text-[11px] py-1 px-2 h-7 bg-card cursor-pointer w-24">
                                        <option value="newest">Newest</option>
                                        <option value="oldest">Oldest</option>
                                        <option value="az">A-Z</option>
                                    </select>
                                </div>

                                <!-- Grid -->
                                <div class="grid grid-cols-3 gap-2 content-start auto-rows-max max-h-[220px] lg:max-h-none lg:flex-1 lg:min-h-0 overflow-y-auto pr-1 scrollbar-thin">
                                    <template x-for="asset in (activeMediaTab === 'local' ? availableAssets : filteredGlobalAssets.slice(0, globalVisibleLimit))" :key="asset.path">
                                        <div class="group relative aspect-square bg-canvas border border-border overflow-hidden cursor-pointer"
                                            :class="form.hero_image === asset.path ? 'border-rust ring-2 ring-rust-wash' : 'hover:border-border-accent'"
                                            :title="asset.filename"
                                            @mouseenter="hoveredAsset = asset"
                                            @mouseleave="hoveredAsset = null">

                                            <img :src="asset.url" class="w-full h-full object-cover">

                                            <!-- Hover actions overlay -->
                                            <div
                                                class="absolute inset-0 bg-nav/85 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex flex-col items-center justify-center p-1">
                                                <button @click.stop="prepareImageInsert(asset)"
                                                    class="w-8 h-8 bg-card text-forge-black flex items-center justify-center shadow-md hover:bg-rust hover:text-white transition-colors mb-2 border border-border"
                                                    title="Insert into editor">
                                                    <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-plus-thin"></use></svg>
                                                </button>

                                                <div class="flex justify-center gap-1">
                                                    <button @click.stop="form.hero_image = asset.path"
                                                        class="px-1.5 py-0.5 bg-nav/80 hover:bg-card hover:text-forge-black text-steel-bright text-[7px] font-bold uppercase transition-colors border border-border-chassis">
                                                        Hero
                                                    </button>
                                                </div>
                                            </div>

                                            <!-- Delete asset -->
                                            <button x-show="activeMediaTab === 'local' && $store.app.hasCap('delete:media')" x-cloak @click.stop="deleteAsset(asset)"
                                                class="absolute top-1 right-1 opacity-0 group-hover:opacity-100 bg-danger hover:bg-danger text-white p-0.5 shadow transition-all duration-150"
                                                :style="'background-color: #b91c1c'" title="Delete image">
                                                <?php admin_icon('close', 'w-3 h-3'); ?>
                                            </button>

                                            <!-- Status indicator tags -->
                                            <div
                                                class="absolute top-1 left-1 flex flex-col gap-0.5 pointer-events-none">
                                                <div x-show="form.hero_image === asset.path" x-cloak
                                                    class="bg-rust text-white text-[7px] font-bold uppercase px-1 shadow-sm">
                                                    Hero
                                                </div>
                                            </div>
                                        </div>
                                    </template>
                                </div>

                                <!-- Load More button (Global Library only) -->
                                <template x-if="activeMediaTab === 'global' && filteredGlobalAssets.length > globalVisibleLimit">
                                    <button @click="globalVisibleLimit += 24"
                                        class="w-full mt-2 py-1.5 font-serif hover:text-rust text-[9px] font-black uppercase tracking-wider transition-colors outline-none shrink-0">
                                        Load More
                                    </button>
                                </template>
                            </div>
                        </div>
                        </div>


                    </aside>
                </div>
            </div>
        </main>
    </div>

    <!-- ── Fullscreen Image Modal ──────────────────────────────────── -->
    <div x-show="showModal" class="fixed inset-0 z-[100] flex items-center justify-center p-8 bg-nav/90"
        @click="closeModal()" @keydown.escape.window="closeModal()" style="display:none" x-transition>
        <template x-if="modalImage">
            <div class="relative max-w-5xl" @click.stop>
                <img :src="modalImage.url" class="max-w-full max-h-[80vh] border border-border-chassis shadow-lg">
                <button @click="closeModal()"
                    class="absolute -top-4 -right-4 bg-card text-forge-black p-2 border border-border shadow-md hover:text-danger transition-colors">
                    <?php admin_icon('close', 'w-4 h-4'); ?>
                </button>
                <p class="mt-4 text-center text-steel-bright text-xs font-mono bg-nav/90 inline-block px-3 py-1 mx-auto"
                    x-text="modalImage.path"></p>
            </div>
        </template>
    </div>



    <!-- ── Image Shortcode Editor Modal ────────────────────────────── -->
    <div x-show="shortcodeModal.open" class="fixed inset-0 z-[100] flex items-center justify-center p-8 bg-nav/70"
        @click="shortcodeModal.open = false" @keydown.escape.window="shortcodeModal.open = false" style="display:none"
        x-transition>
        <div class="bg-card shadow-lg max-w-lg w-full overflow-hidden border border-border border-t-[4px] border-t-rust"
            @click.stop>
            <div class="px-6 py-4 border-b border-border bg-canvas flex justify-between items-center">
                <h3 class="text-sm font-bold uppercase tracking-wider text-forge-black"
                    x-text="shortcodeModal.mode === 'insert' ? 'Insert Shortcode Image' : 'Edit Shortcode Image'"></h3>
                <button @click="shortcodeModal.open = false" class="text-forge-mid hover:text-rust transition-colors">
                    <?php admin_icon('close', 'w-5 h-5'); ?>
                </button>
            </div>
            <template x-if="shortcodeModal.type === 'image'">
                <div class="p-6 space-y-4">
                    <div class="flex flex-col gap-1.5">
                        <label class="pen-label">Image Source Path</label>
                        <input type="text" x-model="shortcodeModal.attrs.src" class="pen-input font-mono text-xs"
                            readonly>
                    </div>
                    <div class="flex flex-col gap-1.5">
                        <label class="pen-label">Alt Text (Accessibility)</label>
                        <input type="text" x-model="shortcodeModal.attrs.alt" class="pen-input">
                    </div>
                    <div class="flex flex-col gap-1.5">
                        <label class="pen-label">Caption Label</label>
                        <input type="text" x-model="shortcodeModal.attrs.caption" class="pen-input">
                    </div>
                    <div class="grid grid-cols-2 gap-4">
                        <div class="flex flex-col gap-1.5">
                            <label class="pen-label">Layout Class</label>
                            <select x-model="shortcodeModal.attrs.class"
                                class="pen-select text-xs bg-card cursor-pointer">
                                <option value="">Default (Portrait)</option>
                                <option value="vignette-left">Vignette Left</option>
                                <option value="vignette-right">Vignette Right</option>
                                <option value="inline-image-left">Inline Left</option>
                                <option value="inline-image-right">Inline Right</option>
                                <option value="figure-full">Full Width</option>
                                <option value="landscape mx-auto">Landscape Center</option>
                            </select>
                        </div>
                        <div class="flex flex-col gap-1.5">
                            <label class="pen-label">Size Spec</label>
                            <select x-model="shortcodeModal.attrs.size"
                                class="pen-select text-xs bg-card cursor-pointer">
                                <option value="">Default</option>
                                <option value="small">Small</option>
                                <option value="medium">Medium</option>
                                <option value="large">Large</option>
                                <option value="full">Full</option>
                            </select>
                        </div>
                    </div>
                    <div class="bg-canvas border border-border p-3">
                        <code class="text-[10px] font-mono text-rust break-all"
                            x-text="'[image' + (shortcodeModal.attrs.src ? ' src=&quot;' + shortcodeModal.attrs.src + '&quot;' : '') + (shortcodeModal.attrs.alt ? ' alt=&quot;' + shortcodeModal.attrs.alt + '&quot;' : '') + (shortcodeModal.attrs.caption ? ' caption=&quot;' + shortcodeModal.attrs.caption + '&quot;' : '') + (shortcodeModal.attrs.class ? ' class=&quot;' + shortcodeModal.attrs.class + '&quot;' : '') + (shortcodeModal.attrs.size ? ' size=&quot;' + shortcodeModal.attrs.size + '&quot;' : '') + ']'"></code>
                    </div>
                </div>
            </template>
            <div class="px-6 py-4 border-t border-border bg-canvas flex justify-end gap-3">
                <button @click="shortcodeModal.open = false"
                    class="text-xs font-bold text-forge-mid uppercase tracking-widest hover:text-forge-black py-2">Cancel</button>
                <button @click="applyShortcodeEdit()" class="pen-btn pen-btn-primary text-sm"
                    x-show="shortcodeModal.type === 'image'"
                    x-text="shortcodeModal.mode === 'insert' ? 'Insert Asset' : 'Save Changes'"></button>
            </div>
        </div>
    </div>

    <!-- Resume Unsaved Draft Modal -->
    <?php
    admin_modal([
        'show_var' => 'resumeModalOpen',
        'title' => 'Resume Unsaved Draft',
        'body' => '
            <p class="text-sm text-forge-black font-sans">
                Would you like to resume editing your unsaved draft <strong
                    class="font-mono text-xs bg-canvas px-1.5 py-0.5 border border-border"
                    x-text="resumeModalDraft?.name || \'Untitled Post\'"></strong>?
            </p>
            <p class="text-xs text-forge-muted font-serif leading-prose">
                You have a previously unsaved session. If you choose not to resume, this draft will be permanently
                discarded.
            </p>',
        'footer' => '
            <button @click="discardResumeDraft()" class="pen-btn pen-btn-secondary pen-btn-sm">Discard
                Draft</button>
            <button @click="acceptResumeDraft()" class="pen-btn pen-btn-primary pen-btn-sm">Resume Draft</button>',
    ]);
    ?>

    <!-- Delete Asset Confirmation Modal -->
    <?php
    admin_modal([
        'show_var' => 'deleteAssetModalOpen',
        'title' => 'Delete Asset',
        'danger' => true,
        'body' => '
            <p class="text-sm text-forge-black font-sans">
                Are you sure you want to permanently delete the asset <strong
                    class="font-mono text-xs bg-canvas px-1.5 py-0.5 border border-border"
                    x-text="assetToDelete?.filename"></strong>?
            </p>
            <p class="text-xs text-forge-muted font-serif leading-prose">
                This action is immediate and cannot be undone.
            </p>',
        'footer' => '
            <button @click="deleteAssetModalOpen = false"
                class="pen-btn pen-btn-secondary pen-btn-sm">Cancel</button>
            <button @click="confirmDeleteAsset()" class="pen-btn pen-btn-danger pen-btn-sm">Delete Asset</button>',
    ]);
    ?>

    <!-- Add Fragment Modal -->
    <?php
    admin_modal([
        'show_var' => 'addFragmentModalOpen',
        'title' => 'Add Fragment',
        'body_spacing' => 'space-y-4',
        'body' => '
            <div class="flex flex-col gap-2">
                <label for="new-fragment-name-input" class="pen-label">Fragment Name (e.g. \'background\',
                    \'analysis\')</label>
                <input type="text" id="new-fragment-name-input" x-model="newFragmentName" class="pen-input"
                    placeholder="e.g. background" @keydown.enter="confirmAddPartial()">
            </div>',
        'footer' => '
            <button @click="addFragmentModalOpen = false"
                class="pen-btn pen-btn-secondary pen-btn-sm">Cancel</button>
            <button @click="confirmAddPartial()" class="pen-btn pen-btn-primary pen-btn-sm">Add Fragment</button>',
    ]);
    ?>

    <!-- Remove Fragment Modal -->
    <?php
    admin_modal([
        'show_var' => 'removeFragmentModalOpen',
        'title' => 'Remove Fragment',
        'danger' => true,
        'body' => '
            <p class="text-sm text-forge-black font-sans">
                Are you sure you want to remove the fragment <strong
                    class="font-mono text-xs bg-canvas px-1.5 py-0.5 border border-border"
                    x-text="\'_\' + fragmentToRemove + \'.md\'"></strong>?
            </p>
            <p class="text-xs text-forge-muted font-serif leading-prose">
                This action is immediate and cannot be undone.
            </p>',
        'footer' => '
            <button @click="removeFragmentModalOpen = false"
                class="pen-btn pen-btn-secondary pen-btn-sm">Cancel</button>
            <button @click="confirmRemovePartial()" class="pen-btn pen-btn-danger pen-btn-sm">Remove
                Fragment</button>',
    ]);
    ?>

    <!-- Version conflict (optimistic concurrency) -->
    <?php
    admin_modal([
        'show_var' => 'conflictModalOpen',
        'title' => 'Document was modified',
        'danger' => true,
        'body' => '
            <p class="text-sm text-forge-black font-sans">
                Document was modified by another user or agent.
            </p>
            <p class="text-xs text-forge-muted font-serif leading-prose">
                Your unsaved editor buffer is still here. Reload to discard local
                changes and take the disk version, or overwrite to keep your edits.
            </p>',
        'footer' => '
            <button @click="reloadFromConflict()" class="pen-btn pen-btn-secondary pen-btn-sm">Reload from disk</button>
            <button @click="overwriteFromConflict()" class="pen-btn pen-btn-danger pen-btn-sm">Overwrite</button>',
    ]);
    ?>

    <!-- ========================================== -->
    <!-- AI ASSISTANT INLINE ACCORDION (rendered above) -->
    <!-- ========================================== -->

    <!-- AI Assistant Command Overlay (Ctrl+K / Cmd+K) -->
    <dialog id="ai-command-overlay" closedby="any" x-data="aiCommandOverlay" @keydown.escape.window="closeOverlay()"
        class="bg-white border-[3px] border-rust p-4 shadow-stamp w-full max-w-[600px] font-sans text-left rounded-none overflow-hidden outline-none">
        <div class="flex items-center gap-3">
        <svg class="w-5 h-5 text-rust shrink-0"><use href="#icon-sparkle-ai"></use></svg>
            <input type="text" x-ref="input" x-model="commandText" @keydown.enter.prevent="submitCommand()"
                placeholder="Tell the AI what to do with the selection or document..."
                class="flex-1 bg-transparent border-0 outline-none text-sm placeholder-forge-mid/60 text-forge-black font-sans py-1">
        </div>

        <div
            class="mt-2.5 pt-2 border-t border-border/50 flex items-center justify-between text-[10px] font-sans text-steel-muted">
            <div class="flex items-center gap-1.5 min-w-0">
                <template x-if="hasSelection">
                    <span class="flex items-center gap-1.5 min-w-0">
                    <svg class="w-3.5 h-3.5 text-rust shrink-0" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-expand-arrows"></use></svg>
                        <span class="truncate">Context: <span class="font-bold text-forge-black"
                                x-text="selectionWordCount"></span> words selected</span>
                        <span class="shrink-0 text-steel-muted font-serif" x-text="selectionPreview"></span>
                    </span>
                </template>
                <template x-if="!hasSelection">
                    <span class="flex items-center gap-1.5">
                    <svg class="w-3.5 h-3.5 text-steel-muted/60 shrink-0" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-ai-command"></use></svg>
                        <span>Context: Full Document</span>
                    </span>
                </template>
            </div>

            <div class="flex items-center gap-4 shrink-0 select-none">
                <button type="button" @click="closeOverlay()"
                    class="flex items-center gap-1.5 hover:text-danger group transition-colors cursor-pointer outline-none">
                    <span
                        class="px-1.5 py-0.5 bg-canvas border border-border font-mono text-[9px] group-hover:border-danger/30 transition-colors">Esc</span>
                    <span
                        class="text-[9px] text-steel-muted group-hover:text-danger transition-colors font-sans font-bold uppercase tracking-wider">Cancel</span>
                </button>
                <button type="button" @click="submitCommand()"
                    class="flex items-center gap-1.5 hover:text-rust group transition-colors cursor-pointer outline-none">
                    <span
                        class="px-1.5 py-0.5 bg-rust text-white border border-rust font-mono text-[9px] group-hover:bg-rust-deep group-hover:border-rust-deep transition-colors">Enter</span>
                    <span
                        class="text-[9px] text-steel-muted group-hover:text-rust transition-colors font-sans font-bold uppercase tracking-wider">Send
                        to AI</span>
                </button>
            </div>
        </div>
    </dialog>

    <!-- AI Assistant script -->
    <script src="js/ai-extract.js"></script>
    <script src="js/mcp-client.js"></script>
    <script src="js/ai-handoff.js"></script>
    <script src="js/ai-sidebar.js"></script>

    <!-- Footer -->
    <?php include "includes/_admin-footer.php"; ?>
</body>

</html>
