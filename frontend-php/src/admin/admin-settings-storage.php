<?php
$pageTitle = "Content Storage (PenCMS)";
$currentSection = "storage";
include "includes/_admin-auth.php";
include "includes/_admin-head.php";
?>

<body class="bg-canvas text-forge-black font-sans antialiased h-screen flex flex-col overflow-hidden"
      x-data="storageSettings">

    <!-- Header / Top Navigation -->
    <?php include "includes/_admin-header.php"; ?>

    <div class="flex flex-1 relative min-h-0 overflow-hidden">
        <!-- Collapsible Left Sidebar -->
        <?php include "includes/_admin-sidebar.php"; ?>

        <!-- Main Workspace Canvas -->
        <main class="flex-1 overflow-y-auto p-8 md:p-12 transition-all duration-300">
            <!-- Title Section -->
            <div class="mb-8 flex flex-col md:flex-row md:items-end md:justify-between gap-4">
                <div>
                    <h1 class="text-3xl text-forge-black font-sans font-black tracking-tight mb-2 pb-2 border-b-2 border-border-weld uppercase">
                        Content Storage Settings
                    </h1>
                    <p class="text-forge-dark font-serif text-sm">
                        Configure where your Markdown pages, posts, and media assets are stored.
                    </p>
                </div>
                <div class="flex-shrink-0">
                    <button @click="save()" class="pen-btn-primary flex items-center gap-2" :disabled="saving">
                        <svg x-show="saving" class="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                        <span x-text="saving ? 'Saving...' : 'Save Configuration'"></span>
                    </button>
                </div>
            </div>

            <!-- Restart Banner -->
            <div x-show="restartRequired" x-cloak x-transition class="mb-8 p-4 bg-acid-wash border-2 border-acid-deep flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-6 h-6 text-warning flex-shrink-0"><rect width="256" height="256" fill="none"/><path d="M142.41,40.22l87.46,151.87C236,202.79,228.08,216,215.46,216H40.54C27.92,216,20,202.79,26.13,192.09L113.59,40.22C119.89,29.26,136.11,29.26,142.41,40.22Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="128" y1="144" x2="128" y2="104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><circle cx="128" cy="180" r="12" fill="currentColor"/></svg>
                    <div>
                        <p class="text-xs font-sans font-black uppercase tracking-wider text-acid-text">Configuration Saved. Service Restart Required.</p>
                        <p class="text-[11px] text-acid-text font-serif mt-0.5">Changes will take effect once the backend service is restarted.</p>
                    </div>
                </div>
                <button @click="restart()" class="pen-btn-primary pen-btn-sm flex items-center gap-2" :disabled="restarting">
                    <svg x-show="restarting" class="animate-spin h-3.5 w-3.5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                    <span x-text="restarting ? 'Restarting...' : 'Restart Now'"></span>
                </button>
            </div>

            <!-- Restarting Overlay -->
            <div x-show="restarting" x-cloak class="fixed inset-0 bg-forge-black/80 z-50 flex items-center justify-center">
                <div class="bg-card border-4 border-border-weld p-8 max-w-sm text-center">
                    <div class="inline-block animate-spin rounded-full h-10 w-10 border-4 border-rust border-t-transparent mb-4"></div>
                    <h3 class="font-sans font-black uppercase text-sm tracking-wider mb-2">Restarting Service</h3>
                    <p class="text-xs text-forge-mid font-serif">Waiting for the CMS backend to reload...</p>
                </div>
            </div>

            <!-- Vault Unlock Modal -->
            <div x-show="showVaultModal" x-cloak class="fixed inset-0 bg-forge-black/80 z-50 flex items-center justify-center" @click.self="cancelVaultUnlock()">
                <div class="bg-card border-4 border-border-weld p-8 max-w-md w-full mx-4">
                    <h3 class="font-sans font-black uppercase text-sm tracking-wider mb-1">Vault Locked</h3>
                    <p class="text-xs text-forge-mid font-serif mb-6">Please enter your Master Password to save credentials.</p>
                    <form @submit.prevent="unlockVaultAndSave()" class="space-y-4">
                        <div>
                            <label class="pen-label">Master Password</label>
                            <input type="password" x-model="vaultPassword" class="pen-input w-full" placeholder="Enter your Master Password" autofocus>
                            <p x-show="vaultError" x-text="vaultError" class="text-[10px] text-danger font-bold font-sans uppercase tracking-wider mt-1.5"></p>
                        </div>
                        <div class="flex justify-end gap-3 pt-2">
                            <button type="button" @click="cancelVaultUnlock()" class="pen-btn">Cancel</button>
                            <button type="submit" class="pen-btn-primary">Unlock &amp; Save</button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- Message Modal -->
            <div x-show="showMessageModal" x-cloak class="fixed inset-0 bg-forge-black/80 z-50 flex items-center justify-center" @click.self="dismissMessageModal()">
                <div class="bg-card border-4 border-border-weld p-8 max-w-md w-full mx-4 text-center">
                    <div class="mb-4 flex justify-center">
                        <svg x-show="!modalIsError" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-10 h-10 text-acid"><rect width="256" height="256" fill="none"/><polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><rect x="40" y="40" width="176" height="176" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                        <svg x-show="modalIsError" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-10 h-10 text-danger"><rect width="256" height="256" fill="none"/><line x1="200" y1="56" x2="56" y2="200" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="200" y1="200" x2="56" y2="56" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><rect x="40" y="40" width="176" height="176" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                    </div>
                    <h3 class="font-sans font-black uppercase text-sm tracking-wider mb-1" x-text="modalIsError ? 'Error' : 'Success'"></h3>
                    <p class="text-xs text-forge-mid font-serif mb-6" x-text="modalMessage"></p>
                    <button @click="dismissMessageModal()" class="pen-btn-primary">OK</button>
                </div>
            </div>

            <!-- Config Tabs -->
            <div class="flex border-b border-border mb-8 gap-1">
                <button @click="activeTab = 'content'"
                        class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                        :class="activeTab === 'content' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                    Content Storage
                </button>
                <button @click="activeTab = 'assets'"
                        class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                        :class="activeTab === 'assets' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                    Asset Storage
                </button>
                <button @click="activeTab = 'keys'; loadPublicKey()"
                        class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                        :class="activeTab === 'keys' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                    SSH Key Management
                </button>
            </div>

            <!-- Main Panels -->
            <div x-show="loading" class="py-20 text-center">
                <div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-rust border-t-transparent"></div>
            </div>

            <div x-show="!loading" x-cloak>

                <!-- CONTENT STORAGE TAB -->
                <div x-show="activeTab === 'content'" class="space-y-8">
                    <div>
                        <h3 class="font-sans font-black uppercase text-sm tracking-wide text-forge-dark mb-1">Select Content Provider</h3>
                        <p class="text-xs text-forge-mid font-serif mb-4">Choose where your source Markdown files are saved.</p>
                        <p class="text-xs text-forge-mid font-serif mb-4">
                            Active Content site:
                            <span class="font-mono font-bold text-rust" x-text="$store.app.activeSiteId"></span>
                        </p>

                        <div class="grid gap-4" :class="availableProviders.length > 2 ? 'grid-cols-3' : 'grid-cols-2'">
                            <template x-for="type in availableProviders" :key="type">
                                <div @click="setProvider('content', type)"
                                     class="pen-card p-5 cursor-pointer flex flex-col justify-between border-2 transition-all relative"
                                     :class="contentProvider === type ? 'border-rust bg-rust-wash' : 'border-border hover:border-forge-mid bg-card'">
                                    <div class="flex items-start justify-between">
                                        <!-- Selection indicator -->
                                        <div class="w-4 h-4 rounded-full border-2 border-border-weld flex items-center justify-center bg-canvas"
                                             :class="contentProvider === type ? 'bg-rust border-rust' : ''">
                                            <div x-show="contentProvider === type" class="w-1.5 h-1.5 rounded-full bg-white"></div>
                                        </div>
                                    </div>
                                    <div class="mt-4">
                                        <h4 class="font-sans font-black uppercase text-xs tracking-wider" :class="contentProvider === type ? 'text-rust' : 'text-forge-dark'" x-text="providerLabel(type)"></h4>
                                        <p class="text-[11px] text-forge-mid mt-1 font-serif leading-ui" x-text="providerDescription(type)"></p>
                                    </div>
                                </div>
                            </template>
                        </div>
                    </div>

                    <!-- Local/Git Path -->
                    <div x-show="!isSSH('content')" class="mt-8 space-y-4 max-w-xl">
                        <div>
                            <label class="pen-label">Content Root (install-wide)</label>
                            <input type="text" x-model="contentBasePath" @input="syncDisplayedPaths()" placeholder="../relative/path/to/content" class="pen-input font-mono text-sm">
                            <span class="text-[10px] text-forge-mid mt-1 block">
                                All sites live under <code class="font-mono text-[10px]">sites/{id}/</code> inside this directory.
                            </span>
                        </div>
                        <div>
                            <label class="pen-label">Directory Path</label>
                            <input type="text" x-model="contentPath" readonly class="pen-input font-mono text-sm bg-canvas text-forge-mid">
                            <span x-show="contentProvider === 'git'" class="text-[10px] text-forge-mid mt-1 block">
                                If a .git directory exists at the content root, Git versioning activates automatically.
                            </span>
                        </div>
                    </div>

                    <!-- SSH Fields (Pro: ssh in available_providers) -->
                    <div x-show="isSSH('content') && availableProviders.includes('ssh') && $store.app.edition === 'pro'" class="mt-8 space-y-6 max-w-2xl">
                        <div class="grid grid-cols-3 gap-4">
                            <div class="col-span-2">
                                <label class="pen-label">Host</label>
                                <input type="text" x-model="contentSSH.host" placeholder="myserver.example.com" class="pen-input text-sm">
                            </div>
                            <div>
                                <label class="pen-label">Port</label>
                                <input type="number" x-model="contentSSH.port" placeholder="22" class="pen-input text-sm">
                            </div>
                        </div>
                        <div>
                            <label class="pen-label">Username</label>
                            <input type="text" x-model="contentSSH.username" placeholder="deploy" class="pen-input text-sm">
                        </div>
                        <div>
                            <label class="pen-label">Remote Path</label>
                            <input type="text" x-model="contentSSH.path" placeholder="/var/www/content" class="pen-input font-mono text-sm">
                        </div>

                        <!-- Auth Method Selection -->
                        <div class="pt-4 border-t border-border/60">
                            <label class="pen-label mb-2">Authentication Method</label>
                            <div class="flex gap-4">
                                <button @click="contentAuthMethod = 'key'" type="button"
                                        class="flex-1 p-3 border-2 text-left transition-all"
                                        :class="contentAuthMethod === 'key' ? 'border-rust bg-rust-wash' : 'border-border bg-card hover:border-forge-mid'">
                                    <div class="font-sans font-black text-xs uppercase tracking-wider text-forge-dark">SSH Key</div>
                                    <div class="text-[10px] text-forge-mid font-serif mt-0.5">Recommended & secure</div>
                                </button>
                                <button @click="contentAuthMethod = 'password'" type="button"
                                        class="flex-1 p-3 border-2 text-left transition-all"
                                        :class="contentAuthMethod === 'password' ? 'border-rust bg-rust-wash' : 'border-border bg-card hover:border-forge-mid'">
                                    <div class="font-sans font-black text-xs uppercase tracking-wider text-forge-dark">Password</div>
                                    <div class="text-[10px] text-forge-mid font-serif mt-0.5">Standard password auth</div>
                                </button>
                            </div>
                        </div>

                        <!-- Password Field -->
                        <div x-show="contentAuthMethod === 'password'" class="space-y-4 pt-2" x-transition>
                            <div>
                                <label class="pen-label">SFTP Password</label>
                                <div class="relative">
                                    <input :type="showContentPassword ? 'text' : 'password'" x-model="contentPassword"
                                           :placeholder="contentHasPassword ? '••••••••' : 'Enter SFTP password'"
                                           class="pen-input text-sm pr-10">
                                    <button @click="showContentPassword = !showContentPassword" type="button"
                                            class="absolute inset-y-0 right-0 pr-3 flex items-center text-forge-mid hover:text-rust transition-colors focus:outline-none">
                                        <svg x-show="!showContentPassword" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                                        </svg>
                                        <svg x-show="showContentPassword" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                                            <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                        </svg>
                                    </button>
                                </div>
                                <span x-show="contentHasPassword" class="text-[10px] text-forge-mid mt-1 block">
                                    Saved password is not shown. Enter a new one to update.
                                </span>
                            </div>
                            <div class="p-4 bg-rust-wash border border-rust/40">
                                <p class="text-[11px] text-forge-dark leading-relaxed font-serif">
                                    <strong>Zero-Knowledge Encryption:</strong> Passwords are encrypted locally in your browser using your Master Password before being synced. The CMS server never stores or transmits them in plaintext.
                                </p>
                            </div>
                        </div>

                        <!-- Connection test -->
                        <div class="flex items-center gap-4 pt-4 border-t border-border/60">
                            <button @click="testSSH('content')" type="button"
                                    class="pen-btn-secondary"
                                    :disabled="contentSSHStatus === 'testing'">
                                <span x-text="contentSSHStatus === 'testing' ? 'Testing...' : 'Test Connection'"></span>
                            </button>
                            <div class="text-xs font-mono font-bold flex items-center gap-1.5">
                                <svg x-show="contentSSHStatus === 'success'" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-4 h-4 text-acid flex-shrink-0"><rect width="256" height="256" fill="none"/><polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><rect x="40" y="40" width="176" height="176" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                                <span x-show="contentSSHStatus === 'success'" class="text-acid-deep">Connected (<span x-text="contentSSHResult"></span>)</span>
                                <svg x-show="contentSSHStatus === 'error'" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-4 h-4 text-danger flex-shrink-0"><rect width="256" height="256" fill="none"/><line x1="200" y1="56" x2="56" y2="200" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="200" y1="200" x2="56" y2="56" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><rect x="40" y="40" width="176" height="176" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                                <span x-show="contentSSHStatus === 'error'" class="text-danger">Connection Failed: <span x-text="contentSSHResult"></span></span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- ASSETS STORAGE TAB -->
                <div x-show="activeTab === 'assets'" class="space-y-8">
                    <div>
                        <h3 class="font-sans font-black uppercase text-sm tracking-wide text-forge-dark mb-1">Select Asset Provider</h3>
                        <p class="text-xs text-forge-mid font-serif mb-4">Choose where your images and site media files are saved.</p>
                        <p class="text-xs text-forge-mid font-serif mb-4">
                            Active Content site:
                            <span class="font-mono font-bold text-rust" x-text="$store.app.activeSiteId"></span>
                        </p>

                        <div class="grid gap-4" :class="availableProviders.length > 2 ? 'grid-cols-3' : 'grid-cols-2'">
                            <template x-for="type in availableProviders" :key="type">
                                <div @click="setProvider('assets', type)"
                                     class="pen-card p-5 cursor-pointer flex flex-col justify-between border-2 transition-all relative"
                                     :class="assetsProvider === type ? 'border-rust bg-rust-wash' : 'border-border hover:border-forge-mid bg-card'">
                                    <div class="flex items-start justify-between">
                                        <!-- Selection indicator -->
                                        <div class="w-4 h-4 rounded-full border-2 border-border-weld flex items-center justify-center bg-canvas"
                                             :class="assetsProvider === type ? 'bg-rust border-rust' : ''">
                                            <div x-show="assetsProvider === type" class="w-1.5 h-1.5 rounded-full bg-white"></div>
                                        </div>
                                    </div>
                                    <div class="mt-4">
                                        <h4 class="font-sans font-black uppercase text-xs tracking-wider" :class="assetsProvider === type ? 'text-rust' : 'text-forge-dark'" x-text="providerLabel(type)"></h4>
                                        <p class="text-[11px] text-forge-mid mt-1 font-serif leading-ui" x-text="providerDescription(type)"></p>
                                    </div>
                                </div>
                            </template>
                        </div>
                    </div>

                    <!-- Local/Git Path -->
                    <div x-show="!isSSH('assets')" class="mt-8 space-y-4 max-w-xl">
                        <div>
                            <label class="pen-label">Directory Path</label>
                            <input type="text" x-model="assetsPath" readonly class="pen-input font-mono text-sm bg-canvas text-forge-mid">
                            <span class="text-[10px] text-forge-mid mt-1 block">
                                Per-site media is stored under <code class="font-mono text-[10px]">sites/{id}/assets/</code> inside the content root.
                            </span>
                        </div>
                    </div>

                    <!-- SSH Fields (Pro: ssh in available_providers) -->
                    <div x-show="isSSH('assets') && availableProviders.includes('ssh') && $store.app.edition === 'pro'" class="mt-8 space-y-6 max-w-2xl">
                        <div class="grid grid-cols-3 gap-4">
                            <div class="col-span-2">
                                <label class="pen-label">Host</label>
                                <input type="text" x-model="assetsSSH.host" placeholder="myserver.example.com" class="pen-input text-sm">
                            </div>
                            <div>
                                <label class="pen-label">Port</label>
                                <input type="number" x-model="assetsSSH.port" placeholder="22" class="pen-input text-sm">
                            </div>
                        </div>
                        <div>
                            <label class="pen-label">Username</label>
                            <input type="text" x-model="assetsSSH.username" placeholder="deploy" class="pen-input text-sm">
                        </div>
                        <div>
                            <label class="pen-label">Remote Path</label>
                            <input type="text" x-model="assetsSSH.path" placeholder="/var/www/assets" class="pen-input font-mono text-sm">
                        </div>

                        <!-- Auth Method Selection -->
                        <div class="pt-4 border-t border-border/60">
                            <label class="pen-label mb-2">Authentication Method</label>
                            <div class="flex gap-4">
                                <button @click="assetsAuthMethod = 'key'" type="button"
                                        class="flex-1 p-3 border-2 text-left transition-all"
                                        :class="assetsAuthMethod === 'key' ? 'border-rust bg-rust-wash' : 'border-border bg-card hover:border-forge-mid'">
                                    <div class="font-sans font-black text-xs uppercase tracking-wider text-forge-dark">SSH Key</div>
                                    <div class="text-[10px] text-forge-mid font-serif mt-0.5">Recommended & secure</div>
                                </button>
                                <button @click="assetsAuthMethod = 'password'" type="button"
                                        class="flex-1 p-3 border-2 text-left transition-all"
                                        :class="assetsAuthMethod === 'password' ? 'border-rust bg-rust-wash' : 'border-border bg-card hover:border-forge-mid'">
                                    <div class="font-sans font-black text-xs uppercase tracking-wider text-forge-dark">Password</div>
                                    <div class="text-[10px] text-forge-mid font-serif mt-0.5">Standard password auth</div>
                                </button>
                            </div>
                        </div>

                        <!-- Password Field -->
                        <div x-show="assetsAuthMethod === 'password'" class="space-y-4 pt-2" x-transition>
                            <div>
                                <label class="pen-label">SFTP Password</label>
                                <div class="relative">
                                    <input :type="showAssetsPassword ? 'text' : 'password'" x-model="assetsPassword"
                                           :placeholder="assetsHasPassword ? '••••••••' : 'Enter SFTP password'"
                                           class="pen-input text-sm pr-10">
                                    <button @click="showAssetsPassword = !showAssetsPassword" type="button"
                                            class="absolute inset-y-0 right-0 pr-3 flex items-center text-forge-mid hover:text-rust transition-colors focus:outline-none">
                                        <svg x-show="!showAssetsPassword" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                                        </svg>
                                        <svg x-show="showAssetsPassword" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                                            <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                        </svg>
                                    </button>
                                </div>
                                <span x-show="assetsHasPassword" class="text-[10px] text-forge-mid mt-1 block">
                                    Saved password is not shown. Enter a new one to update.
                                </span>
                            </div>
                            <div class="p-4 bg-rust-wash border border-rust/40">
                                <p class="text-[11px] text-forge-dark leading-relaxed font-serif">
                                    <strong>Zero-Knowledge Encryption:</strong> Passwords are encrypted locally in your browser using your Master Password before being synced. The CMS server never stores or transmits them in plaintext.
                                </p>
                            </div>
                        </div>

                        <!-- Connection test -->
                        <div class="flex items-center gap-4 pt-4 border-t border-border/60">
                            <button @click="testSSH('assets')" type="button"
                                    class="pen-btn-secondary"
                                    :disabled="assetsSSHStatus === 'testing'">
                                <span x-text="assetsSSHStatus === 'testing' ? 'Testing...' : 'Test Connection'"></span>
                            </button>
                            <div class="text-xs font-mono font-bold flex items-center gap-1.5">
                                <svg x-show="assetsSSHStatus === 'success'" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-4 h-4 text-acid flex-shrink-0"><rect width="256" height="256" fill="none"/><polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><rect x="40" y="40" width="176" height="176" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                                <span x-show="assetsSSHStatus === 'success'" class="text-acid-deep">Connected (<span x-text="assetsSSHResult"></span>)</span>
                                <svg x-show="assetsSSHStatus === 'error'" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-4 h-4 text-danger flex-shrink-0"><rect width="256" height="256" fill="none"/><line x1="200" y1="56" x2="56" y2="200" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><line x1="200" y1="200" x2="56" y2="56" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><rect x="40" y="40" width="176" height="176" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg>
                                <span x-show="assetsSSHStatus === 'error'" class="text-danger">Connection Failed: <span x-text="assetsSSHResult"></span></span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- SSH KEY MANAGEMENT TAB -->
                <div x-show="activeTab === 'keys'" class="space-y-6">
                    <div class="flex items-center gap-3 mb-6">
                        <h4 class="font-sans font-black uppercase text-sm tracking-wide text-forge-dark">SSH Key Pair Status</h4>
                        <template x-if="sshKeyExists">
                            <span class="pen-badge bg-acid-wash text-acid-text border-acid-deep border">SSH Key Found</span>
                        </template>
                        <template x-if="!sshKeyExists">
                            <span class="pen-badge bg-danger-bg text-danger border-danger border">No SSH Key</span>
                        </template>
                    </div>

                    <!-- Key exists -->
                    <div x-show="sshKeyExists" class="space-y-6 max-w-3xl">
                        <div class="space-y-2">
                            <label class="pen-label">Public Key</label>
                            <div class="flex flex-col">
                                <code class="flex-1 bg-[#111008] text-steel-bright border-l-4 border-rust p-4 font-mono text-xs leading-relaxed overflow-x-auto whitespace-pre-wrap break-all" x-text="sshPublicKey.trim()"></code>
                                <div class="flex justify-end p-2">
                                    <button @click="copyPublicKey()" class="pen-btn-secondary" :disabled="copiedKey">
                                        <span x-text="copiedKey ? 'Copied!' : 'Copy'"></span>
                                    </button>
                                </div>
                            </div>
                        </div>
                        <div class="p-4 bg-rust-wash border border-rust/40 space-y-2 font-serif text-xs leading-relaxed text-forge-dark">
                            <h5 class="font-sans font-black uppercase text-[10px] tracking-wider text-rust">To Authorize on Remote Host</h5>
                            <p>
                                Add the public key above to the remote server's <code class="bg-card px-1 py-0.5 border border-border font-mono text-[10px]">~/.ssh/authorized_keys</code> file. Or run this from your local terminal:
                            </p>
                            <pre class="bg-card p-2 border border-border font-mono text-[10px] overflow-x-auto select-all">ssh-copy-id -i ~/.ssh/id_ed25519 user@hostname</pre>
                        </div>
                    </div>

                    <!-- Key does not exist -->
                    <div x-show="!sshKeyExists" class="space-y-6 max-w-2xl">
                        <div class="p-4 bg-rust-wash border border-rust/40">
                            <p class="font-serif text-xs leading-relaxed text-forge-dark">
                                An SSH key pair is required to authenticate with remote servers using key-based authentication. If you prefer password authentication, you can skip this.
                            </p>
                        </div>
                        <button @click="generateKey()" class="pen-btn-primary pen-btn-sm flex items-center gap-2" :disabled="generatingKey">
                            <svg x-show="generatingKey" class="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                            <span x-text="generatingKey ? 'Generating SSH Key...' : 'Generate Ed25519 Key Pair'"></span>
                        </button>
                    </div>

                    <!-- SSH Config Hint -->
                    <div class="max-w-3xl p-4 bg-canvas border border-border/60">
                        <h4 class="font-sans font-black uppercase text-[10px] tracking-wider text-forge-dark mb-1">Advanced: Custom Keys</h4>
                        <p class="text-[11px] text-forge-mid font-serif leading-relaxed">
                            If you have custom keys or ssh configs, create a standard config file in <code class="bg-card px-1 py-0.5 border border-border font-mono">~/.ssh/config</code> on the server hosting this CMS. The backend system SSH client inherits those configs automatically.
                        </p>
                    </div>
                </div>
            </div>
        </main>
    </div>

    <!-- Footer -->
    <?php include "includes/_admin-footer.php"; ?>

    <!-- JS Logic -->
    <script src="js/settings-storage.js"></script>
</body>
</html>
