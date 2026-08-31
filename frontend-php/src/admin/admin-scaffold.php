<?php
/**
 * admin-scaffold.php
 *
 * Template / scaffold for new 3-column admin pages.
 *
 * Structure mirrors admin-editor.php:
 *   - Top control bar (collapsible) with Toggle Left, Toggle Right,
 *     and (when AI is enabled) Toggle AI Assistant buttons.
 *   - Left column  (~32%) — resizable via drag handle
 *   - Center column        — fills remaining space
 *   - Right column (~25%) — resizable via drag handle; lower portion
 *                            hosts the AI Assistant accordion when enabled.
 *
 * The Alpine.js component is named `scaffold` and is defined in js/scaffold.js.
 * All column-state logic (collapse, resize, persist) lives there.
 */

$pageTitle  = "Scaffold (PenCMS)";
$currentSection = "scaffold";
$pageScript = "scaffold.js";

include "includes/_admin-auth.php";
require_once "includes/_admin-icons.php";
require_once "includes/_admin-modal.php";

$penLoadMarked = true;
include "includes/_admin-head.php";
?>

<!-- Scaffold page overrides — reuse the resizable-column CSS from admin-editor.css -->
<link rel="stylesheet" href="css/admin-editor.css">

<body class="bg-canvas text-forge-black font-sans antialiased h-screen flex flex-col overflow-hidden"
    x-data="scaffold">

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
                                    <?= htmlspecialchars($pageTitle) ?>
                                </h1>
                            </div>

                            <div class="flex items-center gap-1 shrink-0">
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
                                    @click="$dispatch('toggle-ai-sidebar')"
                                    title="Toggle AI Assistant">
                                    <svg x-show="!workspacePrefs.aiAssistantCollapsed" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-5 h-5 text-rust" fill="currentColor"><rect width="256" height="256" fill="none"/><path d="M208,144a15.78,15.78,0,0,1-10.42,14.94L146,178l-19,51.62a15.92,15.92,0,0,1-29.88,0L78,178l-51.62-19a15.92,15.92,0,0,1,0-29.88L78,110l19-51.62a15.92,15.92,0,0,1,29.88,0L146,110l51.62,19A15.78,15.78,0,0,1,208,144ZM152,48h16V64a8,8,0,0,0,16,0V48h16a8,8,0,0,0,0-16H184V16a8,8,0,0,0,16,0V32H152a8,8,0,0,0,0,16Zm88,32h-8V72a8,8,0,0,0-16,0v8h-8a8,8,0,0,0,0,16h8v8a8,8,0,0,0,16,0V96h8a8,8,0,0,0,0-16Z"/></svg>
                                    <svg x-show="workspacePrefs.aiAssistantCollapsed" class="w-5 h-5 text-rust"><use href="#icon-sparkle-ai"></use></svg>
                                </button>
                            </div>
                        </div>

                        <!-- Right: Collapse toggle for the control bar itself -->
                        <div class="flex items-center gap-3 flex-wrap">
                            <button
                                @click="workspacePrefs.secondaryRailCollapsed = !workspacePrefs.secondaryRailCollapsed; saveWorkspacePrefs()"
                                class="text-steel-muted hover:text-rust transition-colors p-1.5 shrink-0 border border-border bg-card hover:border-rust"
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

            <!-- ── 3-Column Content Area ────────────────────────────── -->
            <div class="px-6 md:px-10 pt-3 pb-0 flex-1 min-h-0 overflow-hidden">
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

                        <div class="space-y-6 lg:flex-1 lg:min-h-0 lg:overflow-y-auto">
                        <!-- ── Center Column Content ── -->
                        <!-- TODO: Add center column cards here -->
                        <div class="pen-card p-6 flex flex-col items-center justify-center min-h-[200px] text-steel-muted select-none">
                            <svg class="w-8 h-8 mb-3 opacity-30" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                                <rect x="3" y="3" width="18" height="18" rx="2"/>
                                <line x1="3" y1="9" x2="21" y2="9"/>
                                <line x1="9" y1="21" x2="9" y2="9"/>
                            </svg>
                            <span class="text-[11px] font-bold uppercase tracking-wider opacity-50">Center Column</span>
                            <span class="text-[10px] font-mono opacity-30 mt-1">Add cards here</span>
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
                        class="w-full lg:w-[25%] resizable-right-column nav-resizable-right-column space-y-4 lg:space-y-0 lg:flex lg:flex-col lg:gap-4 lg:h-full lg:min-h-0 lg:order-5 lg:pl-6 lg:overflow-hidden">

                        <!-- ── Right Column Content ── -->
                        <!-- TODO: Add right column cards here -->
                        <div class="pen-card p-4 flex flex-col items-center justify-center min-h-[120px] text-steel-muted select-none lg:shrink-0">
                            <span class="text-[11px] font-bold uppercase tracking-wider opacity-50">Right Column</span>
                            <span class="text-[10px] font-mono opacity-30 mt-1">Add cards here</span>
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
                        class="w-full lg:w-[32%] resizable-left-column nav-resizable-left-column space-y-6 lg:space-y-0 lg:flex lg:flex-col lg:gap-6 lg:h-full lg:min-h-0 lg:order-1 lg:pr-6 lg:z-30 lg:overflow-hidden">

                        <!-- ── Left Column Content ── -->
                        <!-- TODO: Add left column cards here -->
                        <div class="pen-card p-6 lg:shrink-0 flex flex-col items-center justify-center min-h-[120px] text-steel-muted select-none">
                            <span class="text-[11px] font-bold uppercase tracking-wider opacity-50">Left Column</span>
                            <span class="text-[10px] font-mono opacity-30 mt-1">Add cards here</span>
                        </div>

                    </aside>
                    <!-- ── End Left Column ── -->

                </div>
            </div>
            <!-- ── End 3-Column Content Area ── -->

        </main>
    </div>

    <!-- AI Assistant script (loads the aiSidebar Alpine component) -->
    <script src="js/mcp-client.js"></script>
    <script src="js/ai-handoff.js"></script>
    <script src="js/ai-sidebar.js"></script>

    <!-- Footer (loads api.js, store.js, and $pageScript = scaffold.js) -->
    <?php include "includes/_admin-footer.php"; ?>
</body>

</html>
