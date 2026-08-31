<?php
/**
 * admin-customize.php
 *
 * Theme Customize workshop (Twig + CSS). Fork/editor and AI rail are Core.
 *   - Left: allowlisted file tree (templates/ + partials/ + assets/css/)
 *   - Center: CodeJar editor + save (Twig + CSS)
 *   - Right: AI Assistant (MCP theme inspect/customize tools)
 *
 * Alpine component: customize (js/customize.js) + nested aiSidebar
 */

$pageTitle  = "Customize Theme (PenCMS)";
$currentSection = "customize";
$pageScript = "customize.js";

include "includes/_admin-auth.php";
require_once "includes/_admin-icons.php";
require_once "includes/_admin-modal.php";

$penLoadMarked = true;
include "includes/_admin-head.php";
?>

<!-- Reuse resizable-column CSS from admin-editor.css -->
<link rel="stylesheet" href="css/admin-editor.css">
<link rel="stylesheet" href="css/admin-customize.css">

<!-- CodeJar + highlight.js (Customize page only; bridge to window for customize.js) -->
<script type="module">
    import { CodeJar } from '/assets/vendor/codejar/codejar.js';
    import hljs from '/assets/vendor/highlightjs/es/core.min.js';
    import langCss from '/assets/vendor/highlightjs/es/languages/css.min.js';
    import langXml from '/assets/vendor/highlightjs/es/languages/xml.min.js';
    import langTwig from '/assets/vendor/highlightjs/es/languages/twig.min.js';
    hljs.registerLanguage('xml', langXml);
    hljs.registerLanguage('css', langCss);
    hljs.registerLanguage('twig', langTwig);
    window.CodeJar = CodeJar;
    window.hljs = hljs;
    window.dispatchEvent(new Event('pen:codejar-ready'));
</script>

<body class="bg-canvas text-forge-black font-sans antialiased h-screen flex flex-col overflow-hidden"
    x-data="customize">

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
            <div id="sticky-control-header" class="sticky top-0 z-[60] flex flex-col border-b-2 border-border shadow-sm shrink-0">
                <div class="bg-[#f4edea] transition-all duration-200"
                    :class="workspacePrefs.secondaryRailCollapsed ? 'py-1.5' : 'py-3'">
                    <div class="px-6 flex flex-col md:flex-row md:justify-between md:items-center gap-3">

                        <!-- Left: Page title + column toggles -->
                        <div class="flex items-center gap-3 min-w-0">
                            <div class="flex flex-col min-w-0">
                                <h1 class="font-sans font-bold text-forge-black truncate max-w-sm"
                                    :class="workspacePrefs.secondaryRailCollapsed ? 'text-sm' : 'text-base'">
                                    Customize Theme
                                </h1>
                                <div class="flex items-center gap-2 min-w-0"
                                    x-show="context.exists && !workspacePrefs.secondaryRailCollapsed"
                                    x-cloak>
                                    <!-- Save Status Indicator -->
                                    <div class="flex items-center gap-1.5 text-[9px] text-slate-500 font-mono select-none shrink-0">
                                        <span class="w-1.5 h-1.5 -mt-0.5 rounded-full transition-colors duration-300"
                                            :class="{
                                                'bg-emerald-500': saveStatus === 'saved',
                                                'bg-amber-500/80 animate-pulse': saveStatus === 'unsaved',
                                                'bg-rust animate-pulse': saveStatus === 'saving'
                                            }"></span>
                                        <span x-text="saveStatusText" class="tracking-wide"></span>
                                    </div>
                                    <span class="text-[10px] font-mono text-steel-muted/40 shrink-0">·</span>
                                    <span class="text-[10px] font-mono text-steel-muted truncate"
                                        x-text="themeDisplayName + (context.parent ? ' · from ' + context.parent : '')"></span>
                                </div>
                            </div>

                            <div class="flex items-center gap-1 shrink-0">
                                <button class="transition-colors p-1 shrink-0 border hover:border-rust"
                                    :class="workspacePrefs.leftColumnCollapsed ? 'text-[#817d7b] border-[#817d7b] bg-[#f4edea]' : 'text-forge-black border-border bg-card'"
                                    @click="workspacePrefs.leftColumnCollapsed = !workspacePrefs.leftColumnCollapsed; saveWorkspacePrefs()"
                                    title="Toggle Left">
                                    <svg class="w-5 h-5"><use href="#icon-panel-toggle-left"></use></svg>
                                </button>

                                <button class="transition-colors p-1 shrink-0 border hover:border-rust"
                                    :class="workspacePrefs.rightColumnCollapsed ? 'text-[#817d7b] border-[#817d7b] bg-[#f4edea]' : 'text-forge-black border-border bg-card'"
                                    @click="workspacePrefs.rightColumnCollapsed = !workspacePrefs.rightColumnCollapsed; saveWorkspacePrefs()"
                                    title="Toggle Right">
                                    <svg class="w-5 h-5"><use href="#icon-panel-toggle-right"></use></svg>
                                </button>

                                <!-- Toggle AI Assistant -->
                                <button type="button"
                                    x-show="$store.app.use_ai" x-cloak
                                    class="transition-colors p-1 shrink-0 border hover:border-rust text-[#817d7b] border-transparent hover:border-border hover:bg-card"
                                    @click="workspacePrefs.aiAssistantCollapsed = !workspacePrefs.aiAssistantCollapsed; saveWorkspacePrefs()"
                                    title="Toggle AI Assistant">
                                    <svg x-show="!workspacePrefs.aiAssistantCollapsed" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-5 h-5 text-rust" fill="currentColor"><rect width="256" height="256" fill="none"/><path d="M208,144a15.78,15.78,0,0,1-10.42,14.94L146,178l-19,51.62a15.92,15.92,0,0,1-29.88,0L78,178l-51.62-19a15.92,15.92,0,0,1,0-29.88L78,110l19-51.62a15.92,15.92,0,0,1,29.88,0L146,110l51.62,19A15.78,15.78,0,0,1,208,144ZM152,48h16V64a8,8,0,0,0,16,0V48h16a8,8,0,0,0,0-16H184V16a8,8,0,0,0-16,0V32H152a8,8,0,0,0,0,16Zm88,32h-8V72a8,8,0,0,0-16,0v8h-8a8,8,0,0,0,0,16h8v8a8,8,0,0,0,16,0V96h8a8,8,0,0,0,0-16Z"/></svg>
                                    <svg x-show="workspacePrefs.aiAssistantCollapsed" class="w-5 h-5 text-rust"><use href="#icon-sparkle-ai"></use></svg>
                                </button>
                            </div>
                        </div>

                        <!-- Right: workshop actions -->
                        <div class="flex items-center gap-2 flex-wrap">
                            <template x-if="context.exists">
                                <div class="flex items-center gap-2 flex-wrap">
                                    <button type="button"
                                        class="transition-colors p-1 shrink-0 border border-border bg-card hover:border-rust"
                                        :disabled="validating"
                                        @click="validateTheme()"
                                        title="Validate Theme">
                                        <svg x-show="!validating" class="w-5 h-5 text-forge-black" fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-toast-success"></use></svg>
                                        <svg x-show="validating" x-cloak class="animate-spin w-5 h-5 text-steel-muted" fill="none"><use href="#icon-spinner"></use></svg>
                                    </button>
                                    <button type="button"
                                        class="transition-colors p-1 shrink-0 border border-border bg-card hover:border-rust"
                                        :disabled="resetting"
                                        @click="resetTheme()"
                                        title="Reset Theme">
                                        <svg x-show="!resetting" class="w-5 h-5 text-forge-black" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-refresh-sync"></use></svg>
                                        <svg x-show="resetting" x-cloak class="animate-spin w-5 h-5 text-steel-muted" fill="none"><use href="#icon-spinner"></use></svg>
                                    </button>
                                    <button type="button"
                                        class="transition-colors p-1 shrink-0 border border-danger/40 bg-card text-danger hover:border-danger hover:bg-danger/10"
                                        :disabled="deleting"
                                        @click="deleteCustom()"
                                        title="Delete custom theme">
                                        <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-trash"></use></svg>
                                    </button>
                                    <button type="button"
                                        class="pen-btn pen-btn-primary flex items-center gap-2 !text-xs !py-1.5"
                                        :disabled="!dirty || saving"
                                        @click="saveFile()">
                                        <svg x-show="saving" x-cloak class="animate-spin h-3.5 w-3.5 text-white" fill="none"><use href="#icon-spinner"></use></svg>
                                        <span x-text="saving ? 'Saving…' : 'Save'"></span>
                                    </button>
                                </div>
                            </template>
                        </div>

                    </div>
                </div>
            </div>
            <!-- ── End Control Bar ──────────────────────────────────── -->

            <!-- ── Inactive custom banner ───────────────────────────── -->
            <div x-show="showInactiveBanner" x-cloak
                class="px-6 md:px-10 pt-3 shrink-0">
                <div class="border border-amber-600/40 bg-amber-50 text-forge-dark px-4 py-3 text-sm font-serif leading-relaxed">
                    A custom theme tree exists for this site, but the active theme is
                    <strong class="font-sans font-bold" x-text="context.registry_theme || 'a base'"></strong>.
                    Edits still save to the custom tree. Activate <strong class="font-sans font-bold">Custom</strong>
                    under Themes settings to use it on the public site.
                </div>
            </div>

            <!-- ── Validate results banner ──────────────────────────── -->
            <div x-show="showValidateBanner" x-cloak
                class="px-6 md:px-10 pt-3 shrink-0">
                <div class="border px-4 py-3 text-sm font-serif leading-relaxed"
                    :class="validateResult && validateResult.ok
                        ? 'border-border bg-card text-forge-dark'
                        : 'border-danger/40 bg-card text-forge-dark'">
                    <div class="flex items-start justify-between gap-3">
                        <div class="font-sans font-bold text-forge-black">
                            <span x-show="validateResult && validateResult.ok">Validation passed</span>
                            <span x-show="validateResult && !validateResult.ok">Validation found issues</span>
                            <span class="font-normal text-forge-mid text-xs ml-2"
                                x-text="validateResult
                                    ? (validateResult.error_count + ' error(s), ' + validateResult.warning_count + ' warning(s)')
                                    : ''"></span>
                        </div>
                        <button type="button"
                            class="text-xs text-steel-muted hover:text-rust shrink-0"
                            @click="validateResult = null">Dismiss</button>
                    </div>
                    <ul class="mt-2 space-y-1 list-none pl-0"
                        x-show="validateResult && validateResult.errors && validateResult.errors.length">
                        <template x-for="(err, i) in (validateResult && validateResult.errors) || []" :key="'e'+i">
                            <li class="text-danger">
                                <span class="font-sans font-semibold text-xs uppercase tracking-wide">Error</span>
                                <span x-text="err.message"></span>
                                <span class="text-forge-mid text-xs" x-show="err.path" x-text="' (' + err.path + ')'"></span>
                            </li>
                        </template>
                    </ul>
                    <ul class="mt-2 space-y-1 list-none pl-0"
                        x-show="validateResult && validateResult.warnings && validateResult.warnings.length">
                        <template x-for="(warn, i) in (validateResult && validateResult.warnings) || []" :key="'w'+i">
                            <li class="text-amber-800">
                                <span class="font-sans font-semibold text-xs uppercase tracking-wide">Warning</span>
                                <span x-text="warn.message"></span>
                                <span class="text-forge-mid text-xs" x-show="warn.path" x-text="' (' + warn.path + ')'"></span>
                            </li>
                        </template>
                    </ul>
                    <p class="mt-2 text-xs text-forge-mid" x-show="validateResult && !validateResult.ok">
                        Save and AI writes are not blocked — fix issues when ready.
                    </p>
                </div>
            </div>

            <!-- ── Loading / error ───────────────────────────────────── -->
            <div x-show="loading" x-cloak class="px-6 md:px-10 pt-6 text-sm text-forge-mid font-serif">
                Loading theme…
            </div>
            <div x-show="!loading && loadError && !context.exists" x-cloak
                class="px-6 md:px-10 pt-4 text-sm text-danger font-serif" x-text="loadError"></div>

            <!-- ── Empty state: no custom tree ───────────────────────── -->
            <div x-show="!loading && !context.exists" x-cloak
                class="flex-1 min-h-0 flex items-center justify-center px-6 md:px-10 pb-10">
                <div class="pen-card p-8 max-w-lg w-full text-center space-y-4">
                    <h2 class="font-sans font-bold text-lg text-forge-black">No custom theme yet</h2>
                    <p class="text-sm text-forge-dark font-serif leading-relaxed">
                        Create a site-private copy of the current base theme to edit Twig templates and CSS.
                        Install themes stay immutable.
                    </p>
                    <button type="button"
                        class="pen-btn pen-btn-primary"
                        :disabled="forking"
                        @click="forkCustom()">
                        <span x-text="forking ? 'Creating…' : forkCtaLabel"></span>
                    </button>
                </div>
            </div>

            <!-- ── 3-Column workshop (when tree exists) ──────────────── -->
            <div x-show="!loading && context.exists" x-cloak
                class="pl-4 pr-3 py-3 flex-1 min-h-0 overflow-hidden">
                <div class="flex flex-col lg:flex-row gap-8 lg:gap-0 items-stretch h-full"
                    :style="'--left-width: ' + workspacePrefs.sidebarWidth + '%; --right-width: ' + workspacePrefs.rightColumnWidth + '%'">

                    <!-- CENTER — CodeJar editor -->
                    <div class="w-full resizable-workspace lg:order-3 lg:px-6 lg:h-full lg:flex lg:flex-col lg:min-h-0 lg:overflow-hidden"
                        :class="{
                            'workspace-both-collapsed lg:!px-0': workspacePrefs.leftColumnCollapsed && workspacePrefs.rightColumnCollapsed,
                            'workspace-left-collapsed lg:!pl-0': workspacePrefs.leftColumnCollapsed && !workspacePrefs.rightColumnCollapsed,
                            'workspace-right-collapsed lg:!pr-0': !workspacePrefs.leftColumnCollapsed && workspacePrefs.rightColumnCollapsed
                        }">

                        <div class="lg:flex-1 lg:min-h-0 lg:overflow-hidden flex flex-col h-full">
                            <template x-if="!selectedPath">
                                <div class="pen-card p-6 flex flex-col items-center justify-center min-h-[200px] text-steel-muted select-none flex-1">
                                    <span class="text-[11px] font-bold uppercase tracking-wider opacity-50">Select a file</span>
                                    <span class="text-[10px] font-mono opacity-30 mt-1">Twig + assets/css</span>
                                </div>
                            </template>
                            <template x-if="selectedPath">
                                <div class="pen-codejar-shell" :data-theme="codejarTheme">
                                    <div class="pen-codejar-pathbar">
                                        <div class="pen-codejar-pathbar-left">
                                            <span class="text-[11px] font-mono font-bold text-forge-black truncate" x-text="selectedPath"></span>
                                            <span x-show="dirty" x-cloak class="text-[10px] font-bold uppercase tracking-wider text-rust shrink-0">Unsaved</span>
                                        </div>
                                        <div class="flex items-center gap-2 shrink-0">
                                            <button type="button"
                                                class="text-[9px] font-sans font-semibold uppercase tracking-wider text-forge-mid/80 hover:text-rust disabled:opacity-40 disabled:pointer-events-none transition-colors shrink-0 whitespace-nowrap"
                                                :disabled="resettingFile"
                                                @click="resetFile()"
                                                title="Restore this file from the parent theme"
                                                :aria-label="resettingFile ? 'Restoring from original' : 'Restore from original'">
                                                <span x-text="resettingFile ? 'Restoring…' : 'Restore from original'"></span>
                                            </button>
                                            <div class="pen-codejar-theme-toggle" role="group" aria-label="Editor theme">
                                                <button type="button"
                                                    :aria-pressed="codejarTheme === 'dark'"
                                                    @click="setCodejarTheme('dark')"
                                                    title="Dark theme"
                                                    aria-label="Dark theme">
                                                    <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                                                        <path d="M21.75 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009-5.998z" />
                                                    </svg>
                                                </button>
                                                <button type="button"
                                                    :aria-pressed="codejarTheme === 'light'"
                                                    @click="setCodejarTheme('light')"
                                                    title="Light theme"
                                                    aria-label="Light theme">
                                                    <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                                                        <path d="M12 2.25a.75.75 0 01.75.75v2.25a.75.75 0 01-1.5 0V3a.75.75 0 01.75-.75zM7.5 12a4.5 4.5 0 119 0 4.5 4.5 0 01-9 0zM18.894 6.166a.75.75 0 00-1.06-1.06l-1.591 1.59a.75.75 0 101.06 1.061l1.591-1.59zM21.75 12a.75.75 0 01-.75.75h-2.25a.75.75 0 010-1.5H21a.75.75 0 01.75.75zM17.834 18.894a.75.75 0 001.06-1.06l-1.59-1.591a.75.75 0 10-1.061 1.06l1.59 1.591zM12 18.75a.75.75 0 01.75.75V21a.75.75 0 01-1.5 0v-1.5a.75.75 0 01.75-.75zM7.758 17.303a.75.75 0 00-1.061-1.06l-1.591 1.59a.75.75 0 001.06 1.061l1.591-1.59zM6 12a.75.75 0 01-.75.75H3a.75.75 0 010-1.5h2.25A.75.75 0 016 12zM6.697 7.758a.75.75 0 001.06-1.061l-1.59-1.591a.75.75 0 00-1.061 1.06l1.59 1.591z" />
                                                    </svg>
                                                </button>
                                            </div>
                                            <button type="button"
                                                class="p-0.5 text-black hover:text-rust transition-colors shrink-0"
                                                title="Close file"
                                                aria-label="Close file"
                                                @click="closeFile()">
                                                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-6 h-6 text-black" fill="none"><rect width="256" height="256" fill="none"/><rect x="40" y="40" width="176" height="176" rx="8" fill="none" stroke="black" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><line x1="160" y1="96" x2="96" y2="160" fill="none" stroke="black" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><line x1="96" y1="96" x2="160" y2="160" fill="none" stroke="black" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>
                                            </button>
                                        </div>
                                    </div>
                                    <div class="pen-codejar"
                                        x-ref="codejarHost"
                                        x-init="mountCodeJar($el)"
                                        :aria-label="'Edit ' + selectedPath"></div>
                                </div>
                            </template>
                        </div>

                    </div>

                    <!-- End Center -->

                    <!-- DRAG HANDLE — Right -->
                    <div x-show="!workspacePrefs.rightColumnCollapsed"
                        class="hidden lg:block w-3 -mx-1.5 cursor-ew-resize self-stretch relative z-50 group select-none lg:order-4"
                        @mousedown="startResizeRight($event)">
                        <div class="absolute inset-y-0 left-1/2 -translate-x-1/2 transition-all duration-150"
                            :class="isDraggingRightColumn ? 'w-[3px] bg-rust' : 'w-px bg-border/40 group-hover:w-[3px] group-hover:bg-rust'">
                        </div>
                    </div>

                    <!-- RIGHT — AI Assistant -->
                    <aside x-show="!workspacePrefs.rightColumnCollapsed"
                        class="w-full lg:w-[25%] resizable-right-column nav-resizable-right-column space-y-4 lg:space-y-0 lg:flex lg:flex-col lg:gap-4 lg:h-full lg:min-h-0 lg:order-5 lg:pl-6 lg:overflow-hidden">

                        <div x-show="!$store.app.use_ai" x-cloak
                            class="pen-card p-4 flex flex-col items-center justify-center min-h-[120px] text-steel-muted select-none lg:flex-1">
                            <span class="text-[11px] font-bold uppercase tracking-wider opacity-50">AI Assistant</span>
                            <span class="text-[10px] font-mono opacity-30 mt-1 text-center">Enable AI in Settings to use theme tools</span>
                        </div>

                        <!-- ── AI Assistant Accordion ── -->
                        <div x-show="$store.app.use_ai" x-cloak
                            x-data="aiSidebar"
                            data-ai-accordion-card
                            class="pt-4 scroll-mt-[160px] lg:flex lg:flex-col lg:min-h-0 lg:flex-1"
                            :class="!workspacePrefs.aiAssistantCollapsed ? 'lg:overflow-hidden' : ''">

                            <!-- Accordion Trigger -->
                            <div class="flex items-center justify-between border-b border-border cursor-pointer select-none pb-2 w-full text-left font-sans outline-none focus-visible:ring-2 focus-visible:ring-rust"
                                @click="workspacePrefs.aiAssistantCollapsed = !workspacePrefs.aiAssistantCollapsed; saveWorkspacePrefs()">
                                <span class="text-[10px] font-black uppercase tracking-wider text-rust">AI</span>
                                <div class="flex items-center gap-2" @click.stop>
                                    <button type="button" @click="newConversation()"
                                        x-show="!workspacePrefs.aiAssistantCollapsed"
                                        class="text-forge-mid hover:text-rust p-1 transition-colors"
                                        title="New Conversation">
                                        <?php admin_icon('plus'); ?>
                                    </button>
                                    <button type="button" @click="newConversation()"
                                        x-show="!workspacePrefs.aiAssistantCollapsed"
                                        class="text-forge-mid hover:text-rust p-1 transition-colors"
                                        title="Clear Conversation">
                                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5"><use href="#icon-clear-conversation"></use></svg>
                                    </button>
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

                                <div id="ai-chat-messages-container"
                                    class="flex-1 min-h-0 overflow-y-auto px-2 py-3 space-y-1 scrollbar-thin">

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

                                    <template x-if="vaultUnlocked && messages.length === 0">
                                        <p class="text-[11px] font-serif text-steel-muted/80 leading-relaxed px-1">Paste or attach screenshots of the live site. The Vault chat model must support image inputs.</p>
                                    </template>

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
                                                    <input type="radio" class="accent-rust" name="pen-handoff-save-customize" value="save" x-model="pendingOutgoingHandoff.saveChoice">
                                                    <span>Save first</span>
                                                </label>
                                                <label class="flex items-center gap-2 cursor-pointer text-forge-mid">
                                                    <input type="radio" class="accent-rust" name="pen-handoff-save-customize" value="discard" x-model="pendingOutgoingHandoff.saveChoice">
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

                                <div class="pt-1 pb-0 select-none shrink-0">
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
                                                @input="autoGrow($event.target)"
                                                @keydown.enter="handleEnterKey($event)"
                                                @paste="handlePaste($event)"
                                                placeholder="Write a message..."
                                                class="flex-1 min-w-0 min-h-[44px] max-h-[320px] resize-none text-base font-serif bg-transparent p-1 leading-snug placeholder-forge-mid/60 text-forge-black border-0 outline-none focus:!border-0 focus:!ring-0"
                                                :disabled="streaming"></textarea>

                                            <div class="flex items-center gap-1.5 shrink-0 self-end">
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
                            </div>
                            <!-- ── End AI Accordion Body ── -->

                        </div>
                        <!-- ── End AI Assistant Accordion ── -->

                    </aside>
                    <!-- End Right -->

                    <!-- DRAG HANDLE — Left -->
                    <div x-show="!workspacePrefs.leftColumnCollapsed"
                        class="hidden lg:block w-3 -mx-1.5 cursor-ew-resize self-stretch relative z-50 group select-none lg:order-2"
                        @mousedown="startResizeLeft($event)">
                        <div class="absolute inset-y-0 left-1/2 -translate-x-1/2 transition-all duration-150"
                            :class="isDraggingLeftColumn ? 'w-[3px] bg-rust' : 'w-px bg-border/40 group-hover:w-[3px] group-hover:bg-rust'">
                        </div>
                    </div>

                    <!-- LEFT — file tree -->
                    <aside x-show="!workspacePrefs.leftColumnCollapsed"
                        class="w-full lg:w-[32%] resizable-left-column nav-resizable-left-column space-y-4 lg:space-y-0 lg:flex lg:flex-col lg:gap-4 lg:h-full lg:min-h-0 lg:order-1 lg:pr-6 lg:z-30 lg:overflow-hidden">

                        <!-- Card 1: TEMPLATES -->
                        <div class="pen-card p-0 flex flex-col transition-all duration-200"
                            :class="workspacePrefs.templatesCardCollapsed ? 'lg:flex-none lg:h-auto' : 'lg:flex-[2_2_0%] lg:min-h-0 lg:overflow-hidden'">
                            <div class="flex items-center justify-between px-3 py-2 border-border cursor-pointer select-none shrink-0"
                                :class="workspacePrefs.templatesCardCollapsed ? 'border-b-0' : 'border-b'"
                                @click="workspacePrefs.templatesCardCollapsed = !workspacePrefs.templatesCardCollapsed; saveWorkspacePrefs()">
                                <span class="text-[10px] font-black uppercase tracking-wider text-rust">Templates</span>
                                <div class="flex items-center gap-2" @click.stop>
                                    <button type="button" @click="openNewFileModal('templates')"
                                        x-show="!workspacePrefs.templatesCardCollapsed"
                                        class="text-forge-mid hover:text-rust p-1 transition-colors"
                                        title="New template">
                                        <?php admin_icon('plus'); ?>
                                    </button>
                                    <svg @click="workspacePrefs.templatesCardCollapsed = !workspacePrefs.templatesCardCollapsed; saveWorkspacePrefs()"
                                        class="w-3 h-3 text-steel-muted transition-transform duration-200"
                                        :class="workspacePrefs.templatesCardCollapsed ? '-rotate-90' : ''"
                                        fill="none" stroke="currentColor" stroke-width="2.5">
                                        <use href="#icon-chevron-down"></use>
                                    </svg>
                                </div>
                            </div>
                            <div class="flex-1 min-h-0 overflow-y-auto py-1"
                                x-show="!workspacePrefs.templatesCardCollapsed" x-cloak x-transition>
                                <template x-if="templateFiles.length === 0">
                                    <p class="px-3 py-4 text-xs text-steel-muted font-serif">No templates in tree.</p>
                                </template>
                                <template x-for="f in templateFiles" :key="typeof f === 'string' ? f : f.path">
                                    <button type="button"
                                        class="w-full text-left px-3 py-1.5 text-[12px] font-sans truncate transition-colors border-l-2"
                                        :class="selectedPath === (typeof f === 'string' ? f : f.path)
                                            ? 'bg-rust-wash border-rust text-forge-black font-bold'
                                            : 'border-transparent text-forge-dark hover:bg-canvas'"
                                        :title="typeof f === 'string' ? f : f.path"
                                        @click="openFile(typeof f === 'string' ? f : f.path)">
                                        <span x-text="formatDisplayName(f)"></span><span x-show="dirty && selectedPath === (typeof f === 'string' ? f : f.path)" class="text-rust"> *</span>
                                    </button>
                                </template>
                            </div>
                        </div>

                        <!-- Card 2: PARTIALS -->
                        <div class="pen-card p-0 flex flex-col transition-all duration-200"
                            :class="workspacePrefs.partialsCardCollapsed ? 'lg:flex-none lg:h-auto' : 'lg:flex-[2_2_0%] lg:min-h-0 lg:overflow-hidden'">
                            <div class="flex items-center justify-between px-3 py-2 border-border cursor-pointer select-none shrink-0"
                                :class="workspacePrefs.partialsCardCollapsed ? 'border-b-0' : 'border-b'"
                                @click="workspacePrefs.partialsCardCollapsed = !workspacePrefs.partialsCardCollapsed; saveWorkspacePrefs()">
                                <span class="text-[10px] font-black uppercase tracking-wider text-rust">Partials</span>
                                <div class="flex items-center gap-2" @click.stop>
                                    <button type="button" @click="openNewFileModal('partials')"
                                        x-show="!workspacePrefs.partialsCardCollapsed"
                                        class="text-forge-mid hover:text-rust p-1 transition-colors"
                                        title="New partial">
                                        <?php admin_icon('plus'); ?>
                                    </button>
                                    <svg @click="workspacePrefs.partialsCardCollapsed = !workspacePrefs.partialsCardCollapsed; saveWorkspacePrefs()"
                                        class="w-3 h-3 text-steel-muted transition-transform duration-200"
                                        :class="workspacePrefs.partialsCardCollapsed ? '-rotate-90' : ''"
                                        fill="none" stroke="currentColor" stroke-width="2.5">
                                        <use href="#icon-chevron-down"></use>
                                    </svg>
                                </div>
                            </div>
                            <div class="flex-1 min-h-0 overflow-y-auto py-1"
                                x-show="!workspacePrefs.partialsCardCollapsed" x-cloak x-transition>
                                <template x-if="partialFiles.length === 0">
                                    <p class="px-3 py-4 text-xs text-steel-muted font-serif">No partials in tree.</p>
                                </template>
                                <template x-for="f in partialFiles" :key="typeof f === 'string' ? f : f.path">
                                    <button type="button"
                                        class="w-full text-left px-3 py-1.5 text-[12px] font-sans truncate transition-colors border-l-2"
                                        :class="selectedPath === (typeof f === 'string' ? f : f.path)
                                            ? 'bg-rust-wash border-rust text-forge-black font-bold'
                                            : 'border-transparent text-forge-dark hover:bg-canvas'"
                                        :title="typeof f === 'string' ? f : f.path"
                                        @click="openFile(typeof f === 'string' ? f : f.path)">
                                        <span x-text="formatDisplayName(f)"></span><span x-show="dirty && selectedPath === (typeof f === 'string' ? f : f.path)" class="text-rust"> *</span>
                                    </button>
                                </template>
                            </div>
                        </div>

                        <!-- Card 3: STYLESHEETS -->
                        <div class="pen-card p-0 flex flex-col transition-all duration-200"
                            :class="workspacePrefs.stylesheetsCardCollapsed ? 'lg:flex-none lg:h-auto' : 'lg:flex-[1_1_0%] lg:min-h-0 lg:overflow-hidden'">
                            <div class="flex items-center justify-between px-3 py-2 border-border cursor-pointer select-none shrink-0"
                                :class="workspacePrefs.stylesheetsCardCollapsed ? 'border-b-0' : 'border-b'"
                                @click="workspacePrefs.stylesheetsCardCollapsed = !workspacePrefs.stylesheetsCardCollapsed; saveWorkspacePrefs()">
                                <span class="text-[10px] font-black uppercase tracking-wider text-rust">Stylesheets</span>
                                <div class="flex items-center gap-2" @click.stop>
                                    <button type="button" @click="openNewFileModal('stylesheets')"
                                        x-show="!workspacePrefs.stylesheetsCardCollapsed"
                                        class="text-forge-mid hover:text-rust p-1 transition-colors"
                                        title="New stylesheet">
                                        <?php admin_icon('plus'); ?>
                                    </button>
                                    <svg @click="workspacePrefs.stylesheetsCardCollapsed = !workspacePrefs.stylesheetsCardCollapsed; saveWorkspacePrefs()"
                                        class="w-3 h-3 text-steel-muted transition-transform duration-200"
                                        :class="workspacePrefs.stylesheetsCardCollapsed ? '-rotate-90' : ''"
                                        fill="none" stroke="currentColor" stroke-width="2.5">
                                        <use href="#icon-chevron-down"></use>
                                    </svg>
                                </div>
                            </div>
                            <div class="flex-1 min-h-0 overflow-y-auto py-1"
                                x-show="!workspacePrefs.stylesheetsCardCollapsed" x-cloak x-transition>
                                <template x-if="stylesheetFiles.length === 0">
                                    <p class="px-3 py-4 text-xs text-steel-muted font-serif">No stylesheets in tree.</p>
                                </template>
                                <template x-for="f in stylesheetFiles" :key="typeof f === 'string' ? f : f.path">
                                    <button type="button"
                                        class="w-full text-left px-3 py-1.5 text-[12px] font-sans truncate transition-colors border-l-2"
                                        :class="selectedPath === (typeof f === 'string' ? f : f.path)
                                            ? 'bg-rust-wash border-rust text-forge-black font-bold'
                                            : 'border-transparent text-forge-dark hover:bg-canvas'"
                                        :title="typeof f === 'string' ? f : f.path"
                                        @click="openFile(typeof f === 'string' ? f : f.path)">
                                        <span x-text="formatDisplayName(f)"></span><span x-show="dirty && selectedPath === (typeof f === 'string' ? f : f.path)" class="text-rust"> *</span>
                                    </button>
                                </template>
                            </div>
                        </div>

                    </aside>
                    <!-- End Left -->

                </div>
            </div>
            <!-- ── End 3-Column Content Area ── -->

        </main>

    </div>

    <?php
    admin_modal([
        'show_var' => 'resetModalOpen',
        'title'    => 'Reset Custom Theme',
        'danger'   => true,
        'body'     => '
            <p class="text-sm text-forge-black font-sans">
                Reset the entire custom theme to a fresh copy of the parent base?
            </p>
            <p class="text-xs text-forge-muted font-serif leading-prose">
                All local Twig and CSS edits will be lost. This change cannot be undone.
            </p>',
        'footer'   => '
            <button @click="resetModalOpen = false" class="pen-btn pen-btn-secondary pen-btn-sm" :disabled="resetting">Cancel</button>
            <button @click="confirmResetTheme()" class="pen-btn pen-btn-danger pen-btn-sm" :disabled="resetting">
                <span x-text="resetting ? \'Resetting...\' : \'Reset Theme\'"></span>
            </button>',
    ]);

    admin_modal([
        'show_var' => 'resetFileModalOpen',
        'title'    => 'Restore from Original',
        'danger'   => true,
        'body'     => '
            <p class="text-sm text-forge-black font-sans">
                Restore
                <span class="font-mono font-bold" x-text="selectedPath"></span>
                from the parent theme?
            </p>
            <p class="text-xs text-forge-muted font-serif leading-prose">
                Local edits to this file will be discarded. Unsaved editor changes will also be lost.
            </p>',
        'footer'   => '
            <button @click="resetFileModalOpen = false" class="pen-btn pen-btn-secondary pen-btn-sm" :disabled="resettingFile">Cancel</button>
            <button @click="confirmResetFile()" class="pen-btn pen-btn-danger pen-btn-sm" :disabled="resettingFile">
                <span x-text="resettingFile ? \'Restoring...\' : \'Restore File\'"></span>
            </button>',
    ]);

    admin_modal([
        'show_var' => 'deleteModalOpen',
        'title'    => 'Delete Custom Theme',
        'danger'   => true,
        'body'     => '
            <p class="text-sm text-forge-black font-sans">
                Delete this site\'s custom theme?
            </p>
            <p class="text-xs text-forge-muted font-serif leading-prose">
                This cannot be undone. If Custom is active, the site will revert to the parent base theme.
            </p>',
        'footer'   => '
            <button @click="deleteModalOpen = false" class="pen-btn pen-btn-secondary pen-btn-sm" :disabled="deleting">Cancel</button>
            <button @click="confirmDeleteCustom()" class="pen-btn pen-btn-danger pen-btn-sm" :disabled="deleting">
                <span x-text="deleting ? \'Deleting...\' : \'Delete Theme\'"></span>
            </button>',
    ]);
    ?>

    <!-- New File Modal (dynamic title by kind; same pen-modal chrome as admin_modal) -->
    <div x-show="newFileModalOpen" x-cloak class="pen-modal-overlay p-4" style="display:none"
        x-transition>
        <div class="pen-modal min-w-0 w-full max-w-[480px] sm:min-w-[480px]"
            @click.away="!creatingFile && (newFileModalOpen = false)"
            @keydown.escape.window="!creatingFile && (newFileModalOpen = false)">
            <div class="pen-modal-header">
                <h3 class="pen-modal-title" x-text="newFileModalTitle"></h3>
                <button type="button" @click="newFileModalOpen = false" :disabled="creatingFile"
                    class="text-forge-mid hover:text-forge-black">
                    <?php admin_icon('close', 'w-5 h-5'); ?>
                </button>
            </div>
            <div class="pen-modal-body space-y-4">
                <div class="flex flex-col gap-2">
                    <label for="new-theme-file-name-input" class="pen-label" x-text="newFileNameLabel"></label>
                    <input type="text" id="new-theme-file-name-input" x-model="newFileName" class="pen-input"
                        :placeholder="newFileNamePlaceholder"
                        :disabled="creatingFile"
                        @keydown.enter="confirmCreateFile()">
                    <p class="text-xs text-forge-muted font-serif leading-prose">
                        Saves as
                        <code class="font-mono text-[11px] text-forge-dark" x-text="newFilePathPreview || newFilePrefixHint"></code>
                    </p>
                </div>
            </div>
            <div class="pen-modal-footer">
                <button type="button" @click="newFileModalOpen = false"
                    class="pen-btn pen-btn-secondary pen-btn-sm" :disabled="creatingFile">Cancel</button>
                <button type="button" @click="confirmCreateFile()"
                    class="pen-btn pen-btn-primary pen-btn-sm" :disabled="creatingFile || !newFileName.trim()">
                    <span x-text="creatingFile ? 'Creating…' : 'Create'"></span>
                </button>
            </div>
        </div>
    </div>

    <!-- AI Assistant script -->
    <script src="js/mcp-client.js"></script>
    <script src="js/ai-handoff.js"></script>
    <script src="js/ai-sidebar-customize.js"></script>

    <!-- Footer (loads api.js, store.js, and $pageScript = customize.js) -->
    <?php include "includes/_admin-footer.php"; ?>
</body>

</html>
