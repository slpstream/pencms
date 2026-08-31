<?php
$pageTitle = "AI Settings (PenCMS)";
$currentSection = "ai-settings";
$pageScript = "settings-ai.js";
include "includes/_admin-auth.php";
include "includes/_admin-head.php";
?>

<body class="bg-canvas text-forge-black font-sans antialiased h-screen flex flex-col overflow-hidden"
      x-data="aiSettings" x-init="init()">

    <!-- Header / Top Navigation -->
    <?php include "includes/_admin-header.php"; ?>

    <!-- Toast Notifications -->
    <div class="fixed top-24 right-6 z-[200] space-y-2">
        <template x-for="toast in toasts" :key="toast.id">
            <div x-transition:enter="transition ease-out duration-300" x-transition:enter-start="opacity-0 translate-x-8" x-transition:enter-end="opacity-100 translate-x-0"
                 x-transition:leave="transition ease-in duration-200" x-transition:leave-start="opacity-100" x-transition:leave-end="opacity-0"
                 class="px-5 py-3 shadow-stamp text-xs font-bold uppercase tracking-wider flex items-center space-x-2 min-w-[280px]"
                 :class="toast.type === 'error' ? 'bg-danger text-white border-l-4 border-danger-bg' : 'bg-forge-black text-white border-l-4 border-acid'">
                <span x-text="toast.message"></span>
            </div>
        </template>
    </div>

    <div class="flex flex-1 relative min-h-0 overflow-hidden">
        <!-- Collapsible Left Sidebar -->
        <?php include "includes/_admin-sidebar.php"; ?>

        <!-- Main Workspace Canvas -->
        <main class="flex-1 overflow-y-auto p-8 md:p-12 transition-all duration-300">
            <!-- Title Section -->
            <div class="mb-8 flex flex-col md:flex-row md:items-end md:justify-between gap-4">
                <div>
                    <h1 class="text-3xl text-forge-black font-sans font-black tracking-tight mb-2 pb-2 border-b-2 border-border-weld uppercase">
                        AI Settings
                    </h1>
                    <p class="text-forge-dark font-serif text-sm">
                        Configure permissions, guardrails, models and API keys for AI agents with custom prompts for prose and image generation.
                    </p>
                </div>
                <div class="flex-shrink-0 flex items-center gap-3">
                    <button type="button"
                            @click="toggleUseAi()"
                            class="pen-toggle"
                            :class="use_ai ? 'active' : ''"
                            role="switch"
                            :aria-checked="use_ai"
                            :disabled="savingUseAi"
                            id="use_ai_toggle">
                        <span class="pen-toggle-knob"></span>
                    </button>
                    <div class="flex flex-col">
                        <label @click="toggleUseAi()" class="font-sans font-bold text-xs uppercase tracking-wider text-forge-black cursor-pointer select-none" x-text="use_ai ? 'AI Integration enabled' : 'No AI integration active'">
                        </label>
                        <span class="text-[10px] text-forge-mid leading-relaxed">
                            <span x-show="!use_ai">Install-wide: click to enable AI features</span>
                            <span x-show="use_ai" x-cloak>AI features enabled for this install</span>
                        </span>
                    </div>
                </div>
            </div>

            <!-- Shown when AI is off: optional / BYOK / vault details -->
            <div x-show="!use_ai" x-cloak class="mb-8 p-4 bg-canvas border border-border flex flex-col gap-2.5">
                <h4 class="text-[10px] font-black uppercase tracking-wider text-forge-black flex items-center gap-1.5">
                    <svg class="w-3.5 h-3.5 text-rust" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z"></path>
                    </svg>
                    AI Integration Details
                </h4>
                <ul class="list-disc pl-4 text-[10px] font-serif text-forge-dark leading-relaxed space-y-1.5">
                    <li>Use of AI is <strong>optional</strong> and all core PenCMS features work fine without AI.</li>
                    <li>AI is <strong>BYOK</strong> (Bring Your Own Key).</li>
                    <li>
                        <details class="group inline">
                            <summary class="inline cursor-pointer hover:text-rust select-none list-none [&::-webkit-details-marker]:hidden">
                                AI keys are stored in an encrypted, local-only <strong>zero-knowledge vault</strong>. <span class="text-rust underline text-[9px] font-normal ml-1 group-open:hidden">Read more</span>
                            </summary>
                            <div class="mt-2 pl-4 border-l border-border text-[10px] text-forge-dark leading-relaxed space-y-1.5">
                                <p>The zero-knowledge vault is 100% client-side. Nothing is stored on the server in plaintext.</p>
                                <ul class="list-disc pl-4 space-y-1">
                                    <li>Your browser derives a <strong>Key Encryption Key (KEK)</strong> from your Master Password using PBKDF2 (SHA-256 with 100,000 iterations).</li>
                                    <li>All credentials are encrypted locally using a randomly generated 256-bit <strong>Data Encryption Key (DEK)</strong> via <strong>AES-256-GCM</strong>.</li>
                                    <li>The server only receives and stores the encrypted payload. The server never sees the plaintext contents.</li>
                                </ul>
                            </div>
                        </details>
                    </li>
                </ul>
            </div>

            <div x-show="use_ai" x-cloak>
            <!-- Config Tabs (only when AI Integration is enabled) -->
            <div class="flex border-b border-border mb-8 gap-1 select-none">
                <button @click="activeTab = 'permissions'"
                        class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                        :class="activeTab === 'permissions' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                    Permissions
                </button>
                <button @click="activeTab = 'models'"
                        class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                        :class="activeTab === 'models' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                    Models
                </button>
                <button @click="activeTab = 'prompts'"
                        class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                        :class="activeTab === 'prompts' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                    Prompts
                </button>
                <button @click="activeTab = 'agent-keys'"
                        class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                        :class="activeTab === 'agent-keys' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                    Agent Keys
                </button>
            </div>
            </div>

            <!-- PERMISSIONS TAB -->
            <div x-show="use_ai && activeTab === 'permissions'" class="space-y-8" x-cloak>
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
                    <div class="lg:col-span-2 space-y-6">
                        <!-- AI Agent Permissions & Guardrails Card -->
                        <div class="pen-card p-6 space-y-5">
                            <div class="flex items-center gap-2 border-b border-border pb-2">
                                <svg class="w-4 h-4 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                                </svg>
                                <h3 class="text-xs font-black uppercase tracking-wider text-forge-black">AI Agent Permissions & Guardrails</h3>
                                <span class="text-[10px] font-mono font-bold text-rust ml-auto" x-text="$store.app.activeSiteId"></span>
                            </div>
                            <p class="text-[10px] text-forge-mid font-serif leading-prose">
                                Guardrails apply to Content site
                                <span class="font-mono font-bold text-rust" x-text="$store.app.activeSiteId"></span>.
                            </p>

                            <!-- Publishing Autonomy -->
                            <div class="space-y-2">
                                <label class="pen-label !mb-1">Publishing Autonomy</label>
                                <p class="text-[10px] text-forge-mid font-serif leading-prose mb-2">
                                    Control whether AI agents may take posts, pages, and translation siblings live. The same dial applies when i18n is on — there is no extra review religion for other languages.
                                </p>
                                <div class="space-y-2 flex flex-col">
                                    <label class="inline-flex items-start gap-2.5 cursor-pointer text-xs font-bold text-forge-black">
                                        <input type="radio" name="publishAutonomy" value="autonomous" x-model="guardrails.publishAutonomy" class="mt-0.5 border-border text-rust focus:ring-rust">
                                        <div class="flex flex-col">
                                            <span>Autonomous Publishing</span>
                                            <span class="text-[10px] font-normal text-forge-mid font-serif">Allow full autonomy (AI can publish/unpublish posts, pages, and translation siblings directly).</span>
                                        </div>
                                    </label>
                                    <label class="inline-flex items-start gap-2.5 cursor-pointer text-xs font-bold text-forge-black">
                                        <input type="radio" name="publishAutonomy" value="require_approval" x-model="guardrails.publishAutonomy" class="mt-0.5 border-border text-rust focus:ring-rust">
                                        <div class="flex flex-col">
                                            <span>Require Human Approval</span>
                                            <span class="text-[10px] font-normal text-forge-mid font-serif">AI writes/updates content, but any attempt to publish is downgraded to draft.</span>
                                        </div>
                                    </label>
                                    <label class="inline-flex items-start gap-2.5 cursor-pointer text-xs font-bold text-forge-black">
                                        <input type="radio" name="publishAutonomy" value="restricted" x-model="guardrails.publishAutonomy" class="mt-0.5 border-border text-rust focus:ring-rust">
                                        <div class="flex flex-col">
                                            <span>Restricted / Human-Only</span>
                                            <span class="text-[10px] font-normal text-forge-mid font-serif">AI is completely blocked from modifying the status field at all.</span>
                                        </div>
                                    </label>
                                </div>
                            </div>

                            <!-- Metadata & Frontmatter Scope -->
                            <div class="pt-4 border-t border-border/40 space-y-2">
                                <label class="pen-label !mb-1">Metadata Scope</label>
                                <p class="text-[10px] text-forge-mid font-serif leading-prose mb-2">
                                    Restrict which frontmatter fields the AI is permitted to edit.
                                </p>
                                <div class="space-y-2 flex flex-col">
                                    <label class="inline-flex items-start gap-2.5 cursor-pointer text-xs font-bold text-forge-black">
                                        <input type="radio" name="metadataScope" value="allow_metadata" x-model="guardrails.metadataScope" class="mt-0.5 border-border text-rust focus:ring-rust">
                                        <div class="flex flex-col">
                                            <span>Allow Metadata Updates</span>
                                            <span class="text-[10px] font-normal text-forge-mid font-serif">AI can update fields like category, tags, name, and hero_title.</span>
                                        </div>
                                    </label>
                                    <label class="inline-flex items-start gap-2.5 cursor-pointer text-xs font-bold text-forge-black">
                                        <input type="radio" name="metadataScope" value="body_only" x-model="guardrails.metadataScope" class="mt-0.5 border-border text-rust focus:ring-rust">
                                        <div class="flex flex-col">
                                            <span>Body Text Only</span>
                                            <span class="text-[10px] font-normal text-forge-mid font-serif">AI is strictly prohibited from modifying metadata fields. Only body edits allowed.</span>
                                        </div>
                                    </label>
                                </div>
                            </div>
                        </div>

                        <!-- Save Permissions & Guardrails Button -->
                        <div class="flex justify-end pt-2">
                            <button @click="saveGuardrails()" class="pen-btn pen-btn-primary flex items-center gap-2" :disabled="savingGuardrails">
                                <svg x-show="savingGuardrails" class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
                                <span x-text="savingGuardrails ? 'Saving...' : 'Save Permissions & Guardrails'"></span>
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- MODELS TAB -->
            <div x-show="use_ai && activeTab === 'models'" class="space-y-8" x-cloak>
                <!-- Model Settings Grid -->
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
                    <!-- If Vault is locked, show Unlock Vault in Left Column -->
                    <div x-show="!vaultUnlocked" class="lg:col-span-2 space-y-6">
                        <!-- Vault Lock Card -->
                        <div class="pen-card p-6 flex flex-col gap-5">
                            <div class="flex justify-between items-center border-b border-border pb-2">
                                <h2 class="text-xs font-black uppercase tracking-widest text-forge-black flex items-center gap-2">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-rust" fill="currentColor" viewBox="0 0 256 256"><rect width="256" height="256" fill="none"/><rect x="100" y="100" width="56" height="56" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><rect x="48" y="48" width="160" height="160" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>
                                    <span>Unlock Vault</span>
                                </h2>
                                <svg xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-rust" viewBox="0 0 24 24" fill="none">
                                    <path d="M0 0h24v24H0z" fill="none" />
                                    <path fill="currentColor" d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12c5.16-1.26 9-6.45 9-12V5zm0 6c1.4 0 2.8 1.1 2.8 2.5V11c.6 0 1.2.6 1.2 1.3v3.5c0 .6-.6 1.2-1.3 1.2H9.2c-.6 0-1.2-.6-1.2-1.3v-3.5c0-.6.6-1.2 1.2-1.2V9.5C9.2 8.1 10.6 7 12 7m0 1.2c-.8 0-1.5.5-1.5 1.3V11h3V9.5c0-.8-.7-1.3-1.5-1.3" />
                                </svg>
                            </div>
                            <p class="text-[10px] text-forge-mid font-serif leading-prose">
                                Models and vault credentials are install-wide for this operator.
                            </p>
                            <p class="text-xs text-forge-dark font-serif leading-prose">
                                To view or change the AI provider credentials, you must unlock your Zero-Knowledge Vault. Plaintext credentials are encrypted locally and never exposed in plaintext to the server database.
                            </p>
                            <form autocomplete="off" @submit.prevent class="space-y-3">
                                <div>
                                    <label class="pen-label">Master Password (Login Password)</label>
                                    <div class="flex items-center gap-3">
                                        <div class="relative flex-1">
                                            <input :type="showVaultPassword ? 'text' : 'password'" x-model="unlockPassword" class="pen-input pr-10" placeholder="Enter password to unlock" @keydown.enter="unlockVault()">
                                            <button @click="showVaultPassword = !showVaultPassword" type="button" class="absolute inset-y-0 right-0 pr-3 flex items-center text-forge-mid hover:text-rust transition-colors focus:outline-none">
                                                <svg x-show="!showVaultPassword" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-5 h-5"><rect width="256" height="256" fill="none"/><line x1="48" y1="40" x2="208" y2="216" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M154.91,157.6a40,40,0,0,1-53.82-59.2" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M135.53,88.71a40,40,0,0,1,32.3,35.53" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M208.61,169.1C230.41,149.58,240,128,240,128S208,56,128,56a126,126,0,0,0-20.68,1.68" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M74,68.6C33.23,89.24,16,128,16,128s32,72,112,72a118.05,118.05,0,0,0,54-12.6" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                                                <svg x-show="showVaultPassword" x-cloak xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-5 h-5"><rect width="256" height="256" fill="none"/><path d="M128,56C48,56,16,128,16,128s32,72,112,72,112-72,112-72S208,56,128,56Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><circle cx="128" cy="128" r="40" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                                            </button>
                                        </div>
                                        <button type="button" @click="unlockVault()" class="pen-btn pen-btn-primary px-6">Unlock</button>
                                    </div>
                                </div>
                            </form>
                        </div>
                    </div>

                    <!-- Left Column (when unlocked): AI Provider & AI Image Config -->
                    <div x-show="vaultUnlocked" class="lg:col-span-2 space-y-6">
                        <!-- AI Provider Card -->
                        <div class="pen-card p-6 space-y-4">
                            <div class="flex items-center gap-2 border-b border-border pb-2">
                                <svg class="w-4 h-4 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                                </svg>
                                <h3 class="text-xs font-black uppercase tracking-wider text-forge-black">AI Provider Configuration</h3>
                            </div>
                            <p class="text-[10px] text-forge-mid font-serif leading-prose">
                                Models and vault credentials are install-wide for this operator.
                            </p>

                            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <div>
                                    <label class="pen-label">Provider</label>
                                    <select x-model="aiConfig.provider" @change="handleProviderChange()" class="pen-input font-bold bg-white">
                                        <template x-for="(info, key) in AI_PROVIDERS" :key="key">
                                            <option :value="key" x-text="info.label"></option>
                                        </template>
                                    </select>
                                </div>
                                <div>
                                    <label class="pen-label">Default Model</label>
                                    <input type="text" x-model="aiConfig.model" class="pen-input font-mono text-xs" placeholder="e.g. gpt-4o">
                                </div>
                            </div>

                            <div>
                                <label class="pen-label">Endpoint URL (Base URL)</label>
                                <input type="text" x-model="aiConfig.baseUrl" class="pen-input font-mono text-xs" placeholder="https://api.openai.com/v1">
                            </div>

                            <div x-show="AI_PROVIDERS[aiConfig.provider]?.requiresKey" x-transition>
                                <label class="pen-label">API Key</label>
                                <input type="text" id="ai-api-key-input" x-model="aiConfig.apiKey" autocomplete="off" class="pen-input font-mono text-xs" placeholder="Enter API Key">
                            </div>

                            <!-- Connection Testing Section -->
                            <div class="pt-3 border-t border-border/40 flex justify-between items-center gap-4">
                                <div class="flex-1 min-w-0">
                                    <p x-show="testingConnection" class="text-[10px] font-bold text-forge-mid uppercase tracking-wider flex items-center gap-1.5">
                                        <svg class="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
                                        <span>Testing Connection...</span>
                                    </p>
                                    <p x-show="connectionMessage" x-text="connectionMessage" class="text-[10px] font-bold uppercase tracking-wider truncate" :class="connectionSuccess ? 'text-acid-deep' : 'text-danger'"></p>
                                </div>
                                <button type="button" @click="testConnection()" class="pen-btn bg-forge-black text-white hover:bg-forge-dark border border-forge-black pen-btn-sm shrink-0" :disabled="testingConnection">
                                    Test Connection
                                </button>
                            </div>
                        </div>

                        <!-- AI Image Generation Card -->
                        <div class="pen-card p-6 space-y-4">
                            <div class="flex items-center gap-2 border-b border-border pb-2">
                                <svg class="w-4 h-4 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                </svg>
                                <h3 class="text-xs font-black uppercase tracking-wider text-forge-black">AI Image Generation</h3>
                            </div>

                            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <div>
                                    <label class="pen-label">Provider</label>
                                    <select x-model="aiImageConfig.provider" @change="handleImageProviderChange()" class="pen-input font-bold bg-white">
                                        <template x-for="(info, key) in IMAGE_PROVIDERS" :key="key">
                                            <option :value="key" x-text="info.label"></option>
                                        </template>
                                    </select>
                                </div>
                                <div>
                                    <label class="pen-label">Default Model</label>
                                    <input type="text" x-model="aiImageConfig.model" class="pen-input font-mono text-xs" placeholder="e.g. nano-banana-2-lite">
                                </div>
                            </div>

                            <div>
                                <label class="pen-label">Endpoint URL (Base URL)</label>
                                <input type="text" x-model="aiImageConfig.baseUrl" class="pen-input font-mono text-xs" placeholder="https://nano-gpt.com/api/v1/images">
                            </div>

                            <div x-show="IMAGE_PROVIDERS[aiImageConfig.provider]?.requiresKey" x-transition>
                                <div class="flex justify-between items-center mb-1">
                                    <label class="pen-label !mb-0">API Key</label>
                                    <label class="inline-flex items-center gap-1.5 cursor-pointer text-[10px] font-bold uppercase tracking-wider text-forge-mid hover:text-rust transition-colors">
                                        <input type="checkbox" x-model="useSameApiKey" class="rounded border-border text-rust focus:ring-rust w-3.5 h-3.5">
                                        <span>Use same API Key</span>
                                    </label>
                                </div>
                                <input type="text" id="ai-image-api-key-input" x-model="aiImageConfig.apiKey" :disabled="useSameApiKey" autocomplete="off" class="pen-input font-mono text-xs" :class="useSameApiKey ? 'bg-canvas text-forge-mid select-none' : ''" :placeholder="useSameApiKey ? 'Synced with AI Provider API Key' : 'Enter API Key'">
                            </div>

                            <!-- Connection Testing Section -->
                            <div class="pt-3 border-t border-border/40 flex justify-between items-center gap-4">
                                <div class="flex-1 min-w-0">
                                    <p x-show="testingImageConnection" class="text-[10px] font-bold text-forge-mid uppercase tracking-wider flex items-center gap-1.5">
                                        <svg class="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
                                        <span>Testing Connection...</span>
                                    </p>
                                    <p x-show="connectionImageMessage" x-text="connectionImageMessage" class="text-[10px] font-bold uppercase tracking-wider truncate" :class="connectionImageSuccess ? 'text-acid-deep' : 'text-danger'"></p>
                                </div>
                                <button type="button" @click="testImageConnection()" class="pen-btn bg-forge-black text-white hover:bg-forge-dark border border-forge-black pen-btn-sm shrink-0" :disabled="testingImageConnection">
                                    Test Connection
                                </button>
                            </div>
                        </div>

                        <!-- Save Model Settings Button (below the fold) -->
                        <div class="flex justify-end pt-2">
                            <button @click="saveVault()" class="pen-btn pen-btn-primary flex items-center gap-2" :disabled="savingVault">
                                <svg x-show="savingVault" class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
                                <span x-text="savingVault ? 'Saving...' : 'Save Model Settings'"></span>
                            </button>
                        </div>
                    </div>

                    <!-- Right Column (when unlocked): Lock Vault Card -->
                    <div x-show="vaultUnlocked" class="lg:col-span-1 space-y-6">
                        <!-- Locker actions card -->
                        <div class="pen-card p-6 flex flex-col gap-4">
                            <div class="flex items-center gap-2 border-b border-border pb-2">
                                <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-rust" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                                </svg>
                                <h3 class="text-xs font-black uppercase tracking-wider text-forge-black">Lock Vault</h3>
                            </div>
                            <p class="text-xs text-forge-dark font-serif leading-prose">
                                When you are done editing your credentials, you should encrypt and lock the vault to clear plaintext configurations from your browser memory.
                            </p>
                            <div class="flex justify-end pt-2">
                                <button @click="saveVault()" class="pen-btn pen-btn-acid flex items-center gap-2" :disabled="savingVault">
                                    <svg x-show="savingVault" class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
                                    <span x-text="savingVault ? 'Encrypting & Locking...' : 'Encrypt & Lock Vault'"></span>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- PROMPTS TAB -->
            <div x-show="use_ai && activeTab === 'prompts'" class="space-y-8" x-cloak>
                <!-- Prompt Settings Grid -->
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
                    <!-- Left Column: Prompts -->
                    <div class="lg:col-span-2 space-y-6">
                        <div class="pen-card p-6 space-y-4">
                            <div class="flex items-center gap-2 border-b border-border pb-2">
                                <svg class="w-4 h-4 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                </svg>
                                <h3 class="text-xs font-black uppercase tracking-wider text-forge-black">Configure Prompts</h3>
                                <span class="text-[10px] font-mono font-bold text-rust ml-auto" x-text="$store.app.activeSiteId"></span>
                            </div>
                            <p class="text-[10px] text-forge-mid font-serif leading-prose">
                                Prompts apply to Content site
                                <span class="font-mono font-bold text-rust" x-text="$store.app.activeSiteId"></span>.
                            </p>
                            <p class="text-[10px] text-forge-mid font-serif leading-prose">
                                Empty by default for each site. Prompts are never copied from other sites.
                            </p>

                            <div>
                                <label class="pen-label">Text Generation prompt</label>
                                <textarea x-model="promptSettings.textGenerationPrompt" class="pen-input h-32 resize-y font-mono text-xs" placeholder="Enter add-on instructions for text generation..."></textarea>
                            </div>

                            <div>
                                <label class="pen-label">Image Generation prompt</label>
                                <textarea x-model="promptSettings.imageGenerationPrompt" class="pen-input h-32 resize-y font-mono text-xs" placeholder="Enter add-on instructions for image generation..."></textarea>
                            </div>

                            <div>
                                <label class="pen-label">Post Quality Checklist</label>
                                <p class="text-[10px] text-forge-mid mb-1">Criteria the AI uses to evaluate posts when you request a quality review. Leave empty for the built-in default checklist.</p>
                                <textarea x-model="promptSettings.qualityChecklist" class="pen-input h-48 resize-y font-mono text-xs" placeholder="1. Title & Meta: Does the post have a clear, compelling hero_title?&#10;2. Structure: Does the post use H2/H3 headings logically?&#10;3. Readability: Are paragraphs concise? Is the tone consistent?&#10;4. SEO: Is the primary keyword used naturally?&#10;5. Content Completeness: Does the post adequately cover the topic?&#10;6. Formatting: Is markdown used effectively?&#10;7. Call to Action: Does the post end with a clear next step?"></textarea>
                            </div>
                        </div>

                        <!-- Save Prompt Settings Button -->
                        <div class="flex justify-end pt-2">
                            <button @click="savePromptSettings()" class="pen-btn pen-btn-primary flex items-center gap-2" :disabled="savingPromptSettings">
                                <svg x-show="savingPromptSettings" class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
                                <span x-text="savingPromptSettings ? 'Saving...' : 'Save Prompt Settings'"></span>
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- AGENT KEYS: always available (independent of AI Integration) -->
            <div x-show="!use_ai || activeTab === 'agent-keys'" class="space-y-8" x-cloak>
                <!-- Vault locked: unlock prompt (inline — Models tab may be hidden when AI is off) -->
                <div x-show="!vaultUnlocked" class="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
                    <div class="lg:col-span-2">
                        <div class="pen-card p-6 space-y-4">
                            <div class="flex items-center gap-2 border-b border-border pb-2">
                                <svg class="w-4 h-4 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path>
                                </svg>
                                <h3 class="text-xs font-black uppercase tracking-wider text-forge-black">AI Agent Keys</h3>
                            </div>
                            <p class="text-xs text-forge-dark font-serif leading-prose">
                                To view, generate, copy, or revoke API keys for AI agents, you must unlock your Zero-Knowledge Vault.
                            </p>
                            <form autocomplete="off" @submit.prevent class="space-y-3 pt-1">
                                <div>
                                    <label class="pen-label">Master Password (Login Password)</label>
                                    <div class="flex items-center gap-3">
                                        <div class="relative flex-1">
                                            <input :type="showVaultPassword ? 'text' : 'password'" x-model="unlockPassword" class="pen-input pr-10" placeholder="Enter password to unlock" @keydown.enter="unlockVault()">
                                            <button @click="showVaultPassword = !showVaultPassword" type="button" class="absolute inset-y-0 right-0 pr-3 flex items-center text-forge-mid hover:text-rust transition-colors focus:outline-none">
                                                <svg x-show="!showVaultPassword" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-5 h-5"><rect width="256" height="256" fill="none"/><line x1="48" y1="40" x2="208" y2="216" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M154.91,157.6a40,40,0,0,1-53.82-59.2" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M135.53,88.71a40,40,0,0,1,32.3,35.53" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M208.61,169.1C230.41,149.58,240,128,240,128S208,56,128,56a126,126,0,0,0-20.68,1.68" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><path d="M74,68.6C33.23,89.24,16,128,16,128s32,72,112,72a118.05,118.05,0,0,0,54-12.6" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                                                <svg x-show="showVaultPassword" x-cloak xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-5 h-5"><rect width="256" height="256" fill="none"/><path d="M128,56C48,56,16,128,16,128s32,72,112,72,112-72,112-72S208,56,128,56Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><circle cx="128" cy="128" r="40" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                                            </button>
                                        </div>
                                        <button type="button" @click="unlockVault()" class="pen-btn pen-btn-primary px-6">Unlock</button>
                                    </div>
                                </div>
                            </form>
                            <p x-show="use_ai" x-cloak class="text-[10px] text-forge-mid font-serif">
                                Or unlock from the <button type="button" @click="activeTab = 'models'" class="text-rust font-bold uppercase tracking-wider hover:underline">Models</button> tab.
                            </p>
                        </div>
                    </div>
                </div>

                <!-- Vault unlocked: note + keys list + generate card -->
                <div x-show="vaultUnlocked" x-cloak class="space-y-4">
                    <p class="text-[10px] text-forge-mid font-serif leading-normal">
                        Key actions are applied immediately. No manual save required.
                        Changing a key’s site does not remint the secret; existing JWTs keep the old
                        <code class="font-mono">site_id</code> until expiry — mint a new token to use the new site.
                    </p>

                    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
                        <!-- Left: existing keys + pending approvals -->
                        <div class="lg:col-span-2 space-y-4">
                            <div class="pen-card p-6 space-y-4">
                                <div class="flex items-center gap-2 border-b border-border pb-2">
                                    <svg class="w-4 h-4 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path>
                                    </svg>
                                    <h3 class="text-xs font-black uppercase tracking-wider text-forge-black">Existing Keys</h3>
                                </div>

                                <div class="space-y-3">
                                    <template x-for="(key, index) in agentKeys" :key="index">
                                        <div class="p-3 bg-canvas border border-border space-y-2">
                                            <div class="flex items-center justify-between gap-4">
                                                <div class="min-w-0 flex-1">
                                                    <p class="text-xs font-bold text-forge-black break-all">
                                                        <span x-text="key.name || 'Agent Key'"></span>
                                                    </p>
                                                    <p class="text-[10px] font-mono text-forge-mid break-all" x-show="key.displayKey && key.displayKey !== key.name" x-text="key.displayKey"></p>
                                                    <p class="text-[10px] font-mono text-forge-mid">
                                                        Created: <span x-text="key.created_at"></span>
                                                        · Scopes: <span x-text="(key.scopes || ['read','write']).join(', ')" class="font-bold"></span>
                                                    </p>
                                                </div>
                                                <div class="flex items-center gap-1.5 shrink-0">
                                                    <button x-show="key.displayKey && key.displayKey.startsWith('pen-sk-')" @click="navigator.clipboard.writeText(key.displayKey); showToast('Copied to clipboard')" class="text-forge-mid hover:text-rust transition-colors p-1" title="Copy API Key">
                                                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-5 h-5"><rect width="256" height="256" fill="none"/><polyline points="168 168 216 168 216 40 88 40 88 88" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><rect x="40" y="88" width="128" height="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                                                    </button>
                                                    <button @click="confirmRevokeKey(index, key.name)" class="text-danger hover:text-red-700 transition-colors p-1" title="Revoke this API Key">
                                                        <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                                                            <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                                        </svg>
                                                    </button>
                                                </div>
                                            </div>
                                            <div class="flex items-center gap-2">
                                                <label class="text-[10px] font-bold uppercase tracking-wider text-forge-mid shrink-0">Site:</label>
                                                <select x-model="key.site_id" class="pen-input text-xs font-bold bg-white flex-1 min-w-0">
                                                    <template x-for="s in sites" :key="'key-site-' + index + '-' + s.id">
                                                        <option :value="s.id" x-text="s.name ? (s.id + ' — ' + s.name) : s.id"></option>
                                                    </template>
                                                    <option value="default" x-show="sites.length === 0">default</option>
                                                </select>
                                                <button type="button" @click="reassignAgentKeySite(index)" class="text-[10px] font-bold uppercase tracking-wider text-rust hover:underline shrink-0" title="Save site binding">
                                                    Save
                                                </button>
                                            </div>
                                        </div>
                                    </template>
                                    <div x-show="agentKeys.length === 0" class="text-xs text-forge-mid italic py-2">No agent keys generated.</div>
                                </div>
                            </div>

                            <!-- Pending agent bootstrap approvals (below keys card) -->
                            <div class="space-y-2" x-show="pendingApprovals.length > 0">
                                <div class="flex items-center justify-between">
                                    <h4 class="text-[10px] font-black uppercase tracking-wider text-forge-mid">Pending approvals</h4>
                                    <button type="button" @click="refreshPendingApprovals()" class="pen-btn pen-btn-secondary pen-btn-sm" :disabled="checkingPendingApprovals">
                                        <span x-text="checkingPendingApprovals ? 'Checking...' : 'Refresh'"></span>
                                    </button>
                                </div>
                                <template x-for="req in pendingApprovals" :key="req.user_code">
                                    <div class="flex items-center justify-between p-3 bg-canvas border border-border gap-3">
                                        <div class="min-w-0 flex-1">
                                            <p class="text-xs font-bold text-forge-black font-mono" x-text="req.user_code"></p>
                                            <p class="text-[10px] text-forge-mid">
                                                <span class="font-mono font-bold" x-text="req.site_id || 'default'"></span>
                                                · <span class="font-bold" x-text="req.name"></span>
                                                · <span x-text="(req.scopes || []).join(', ')"></span>
                                                · <span x-text="req.status"></span>
                                            </p>
                                        </div>
                                        <div class="flex items-center gap-2 shrink-0">
                                            <button type="button" @click="approveBootstrap(req.user_code, false)" class="text-[10px] font-bold uppercase text-rust hover:underline" x-show="req.status === 'pending'">Approve</button>
                                            <button type="button" @click="approveBootstrap(req.user_code, true)" class="text-[10px] font-bold uppercase text-danger hover:underline">Deny</button>
                                        </div>
                                    </div>
                                </template>
                            </div>
                            <div x-show="pendingApprovals.length === 0" class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 bg-canvas border border-border">
                                <p class="text-[10px] text-forge-mid font-serif leading-normal">
                                    When an AI agent requests bootstrap access (approve-code flow), pending codes appear here for you to approve or deny.
                                </p>
                                <button type="button" @click="refreshPendingApprovals({ notifyEmpty: true })" class="pen-btn pen-btn-secondary pen-btn-sm shrink-0" :disabled="checkingPendingApprovals">
                                    <span x-text="checkingPendingApprovals ? 'Checking...' : 'Check for approvals'"></span>
                                </button>
                            </div>
                        </div>

                        <!-- Right: generate new key card -->
                        <div class="lg:col-span-1">
                            <div class="pen-card p-6 space-y-4 flex flex-col">
                                <div class="flex items-center gap-2 border-b border-border pb-2">
                                    <svg class="w-4 h-4 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path>
                                    </svg>
                                    <h3 class="text-xs font-black uppercase tracking-wider text-forge-black">Generate New Key</h3>
                                </div>

                                <p class="text-xs text-forge-dark font-serif leading-prose">
                                    Generate static bearer tokens for AI agents. Credentials are encrypted in your Zero-Knowledge Vault.
                                </p>

                                <p class="text-[10px] text-forge-mid font-serif leading-normal">
                                    Names are <strong class="font-sans">globally unique</strong> per operator. Prefer
                                    <code class="font-mono">{site}-{agent}</code> labels (e.g. <code class="font-mono">blog-cursor</code>);
                                    site binding is the separate Site field below. Manage sites under Settings → Sites.
                                </p>

                                <div class="space-y-3">
                                    <div>
                                        <label class="pen-label">Name</label>
                                        <input type="text" x-model="newKeyName" class="pen-input text-xs font-mono bg-white" placeholder="blog-cursor" autocomplete="off" spellcheck="false">
                                    </div>
                                    <div>
                                        <label class="pen-label">Site</label>
                                        <select x-model="newKeySiteId" class="pen-input text-xs font-bold bg-white">
                                            <template x-for="s in sites" :key="s.id">
                                                <option :value="s.id" x-text="s.name ? (s.id + ' — ' + s.name) : s.id"></option>
                                            </template>
                                            <option value="default" x-show="sites.length === 0">default</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label class="pen-label">Scope preset</label>
                                        <select x-model="newKeyPreset" @change="applyKeyPreset()" class="pen-input text-xs font-bold bg-white">
                                            <option value="read">Read-Only</option>
                                            <option value="writer">Writer</option>
                                            <option value="editor">Editor</option>
                                            <option value="publisher">Publisher</option>
                                            <option value="legacy_write">Read + Write (legacy)</option>
                                            <option value="legacy_publish">Read + Write + Publish (legacy)</option>
                                            <option value="custom">Custom</option>
                                        </select>
                                        <p class="text-[10px] text-forge-mid font-serif leading-normal mt-1.5">
                                            Writer/Editor/Publisher include <code class="font-mono">read</code>. Legacy <code class="font-mono">write</code> expands to all write/delete/content-publish caps, not host deploy. Host <code class="font-mono">publish</code> still needs a Deploy Grant.
                                        </p>
                                    </div>
                                    <div>
                                        <label class="pen-label">Scopes</label>
                                        <div class="grid grid-cols-1 gap-1 max-h-48 overflow-y-auto border border-border p-2 bg-white">
                                            <template x-for="cap in SITE_SCOPED_AGENT_CAPS" :key="cap">
                                                <label class="inline-flex items-center gap-1.5 cursor-pointer text-[10px] font-mono text-forge-dark">
                                                    <input type="checkbox" class="rounded border-border text-rust focus:ring-rust w-3.5 h-3.5"
                                                           :checked="hasKeyScope(cap)"
                                                           @change="toggleKeyScope(cap)">
                                                    <span x-text="cap"></span>
                                                </label>
                                            </template>
                                        </div>
                                    </div>
                                </div>

                                <div class="flex justify-end pt-2">
                                    <button @click="generateAgentKey()" class="pen-btn pen-btn-primary">
                                        Generate New Key
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

        </main>
    </div>

    <!-- Revoke Key Confirmation Modal -->
    <div x-show="showRevokeModal" x-cloak class="pen-modal-overlay p-4">
        <div class="pen-modal pen-modal-danger min-w-0 w-full max-w-[480px] sm:min-w-[480px]" @click.away="showRevokeModal = false">
            <div class="pen-modal-header">
                <h3 class="pen-modal-title">Revoke API Key</h3>
                <button @click="showRevokeModal = false" class="text-forge-mid hover:text-forge-black">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>
            <div class="pen-modal-body space-y-3">
                <p class="text-sm text-forge-black font-sans">
                    Are you sure you want to revoke the API key <strong class="font-mono text-xs bg-canvas px-1.5 py-0.5 border border-border" x-text="keyNameToRevoke"></strong>?
                </p>
                <p class="text-xs text-forge-muted font-serif leading-prose">
                    This action is immediate and permanent.<br>Any AI agents using this key will immediately lose access to the PenCMS API.
                </p>
            </div>
            <div class="pen-modal-footer">
                <button @click="showRevokeModal = false" class="pen-btn pen-btn-secondary pen-btn-sm">Cancel</button>
                <button @click="revokeAgentKey()" class="pen-btn pen-btn-danger pen-btn-sm">Revoke Key</button>
            </div>
        </div>
    </div>

    <!-- Footer -->
    <?php include "includes/_admin-footer.php"; ?>
