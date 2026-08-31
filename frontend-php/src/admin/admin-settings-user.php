<?php
$pageTitle = "User Profile & Vault (PenCMS)";
$currentSection = "profile";
$pageScript = "settings-user.js";
include "includes/_admin-auth.php";

// Scan for existing avatar
$sharedPath = dirname(__DIR__, 3) . "/backend-python/apps/blog/shared/images/";
$formats = ["png", "svg", "webp", "jpg", "jpeg", "gif"];
$avatarUrl = null;
foreach ($formats as $ext) {
    if (file_exists($sharedPath . "avatar." . $ext)) {
        $avatarUrl = "/blog/shared/images/avatar." . $ext;
        break;
    }
}

include "includes/_admin-head.php";
?>

<body class="bg-canvas text-forge-black font-sans antialiased h-screen flex flex-col overflow-hidden"
      x-data="userSettings" x-init="init()">

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
            <div class="mb-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b-2 border-border-weld">
                <div>
                    <h1 class="text-3xl text-forge-black font-sans font-black tracking-tight mb-2 uppercase">
                        User Profile & Vault
                    </h1>
                    <p class="text-forge-dark font-serif text-sm">
                        Manage display name, credentials, security API keys, and your zero-knowledge secrets.
                    </p>
                </div>
                <div class="flex items-center gap-3">
                    <button type="button" @click="window.AUTH.logout()" class="pen-btn pen-btn-secondary flex items-center gap-2" title="Sign Out and End Session">
                        <svg class="w-4 h-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
                            <rect width="256" height="256" fill="none"/>
                            <polyline points="112 40 48 40 48 216 112 216" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                            <line x1="112" y1="128" x2="224" y2="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                            <polyline points="184 88 224 128 184 168" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                        </svg>
                        <span>Sign Out</span>
                    </button>
                    <button @click="saveProfile()" class="pen-btn pen-btn-primary flex items-center gap-2" :disabled="saving">
                        <svg x-show="saving" class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
                        <span x-text="saving ? 'Saving...' : 'Save Profile'"></span>
                    </button>
                </div>
            </div>

            <!-- Content Grid -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">

                <!-- Left Column: Public Profile -->
                <div class="lg:col-span-1 space-y-6">
                    <div class="pen-card p-6 flex flex-col gap-5">
                        <h2 class="text-xs font-black uppercase tracking-widest text-forge-black border-b border-border pb-2">Public Profile</h2>

                        <!-- Circular Avatar Upload Zone -->
                        <div class="flex flex-col items-center pb-4 border-b border-border/30" x-data="{ dragging: false }">
                            <div class="relative group w-32 h-32 rounded-full border-2 border-dashed border-steel-muted hover:border-rust flex items-center justify-center bg-canvas transition-all duration-300 overflow-hidden shadow-sm cursor-pointer"
                                 :class="dragging ? 'border-rust bg-rust-wash scale-105' : ''"
                                 @dragover.prevent="dragging = true"
                                 @dragleave.prevent="dragging = false"
                                 @drop.prevent="dragging = false; handleDrop($event)"
                                 @click="$refs.avatarInput.click()">

                                <!-- Avatar Exists -->
                                <template x-if="profile.avatar">
                                    <img :src="profile.avatar" alt="Avatar Preview" class="w-full h-full object-cover">
                                </template>

                                <!-- No Avatar Exists -->
                                <template x-if="!profile.avatar">
                                    <div class="flex flex-col items-center justify-center p-2 text-forge-mid">
                                        <svg class="w-8 h-8 mb-1 text-forge-mid" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                        </svg>
                                        <span class="text-[9px] uppercase tracking-wider font-bold text-center">Upload Pic</span>
                                    </div>
                                </template>

                                <!-- Hover Overlay -->
                                <div class="absolute inset-0 bg-forge-black/75 opacity-0 group-hover:opacity-100 flex flex-col items-center justify-center transition-all duration-200">
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-6 h-6 text-white mb-1">
                                        <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                                    </svg>
                                    <span class="text-[9px] text-white font-bold uppercase tracking-wider">Change Pic</span>
                                </div>
                            </div>

                            <input type="file" x-ref="avatarInput" class="hidden" accept="image/*" @change="handleFileSelect($event)">
                            <span class="text-[10px] text-forge-mid italic mt-2">Drag and drop or click to change avatar</span>
                        </div>

                        <div>
                            <label class="pen-label">Display Name</label>
                            <input type="text" x-model="profile.display_name" class="pen-input" placeholder="John Doe">
                        </div>

                        <div>
                            <label class="pen-label">Avatar URL</label>
                            <input type="text" x-model="profile.avatar" class="pen-input text-xs font-mono" placeholder="/blog/shared/images/avatar.png">
                        </div>

                        <div>
                            <label class="pen-label">Website / Social</label>
                            <input type="url" x-model="profile.website" class="pen-input" placeholder="https://example.com">
                        </div>

                        <div>
                            <label class="pen-label">Bio</label>
                            <textarea x-model="profile.bio" class="pen-input h-24 resize-none" placeholder="A short biography..."></textarea>
                        </div>
                    </div>
                </div>

                <!-- Right Column: Vault & Agents -->
                <div class="lg:col-span-2 space-y-6">

                    <!-- The Encrypted Vault -->
                    <div class="pen-card p-6 flex flex-col gap-5">
                        <div class="flex justify-between items-center border-b border-border pb-2">
                            <h2 class="text-xs font-black uppercase tracking-widest text-forge-black flex items-center gap-2">
                                <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-rust" fill="currentColor" viewBox="0 0 256 256"><path d="M72,128a134.63,134.63,0,0,1-14.16,60.47,8,8,0,1,1-14.32-7.12A118.8,118.8,0,0,0,56,128,71.73,71.73,0,0,1,83,71.8,8,8,0,1,1,93,84.29,55.76,55.76,0,0,0,72,128Zm56-8a8,8,0,0,0-8,8,184.12,184.12,0,0,1-23,89.1,8,8,0,0,0,14,7.76A200.19,200.19,0,0,0,136,128,8,8,0,0,0,128,120Zm0-32a40,40,0,0,0-40,40,8,8,0,0,0,16,0,24,24,0,0,1,48,0,214.09,214.09,0,0,1-20.51,92A8,8,0,1,0,146,226.83,230,230,0,0,0,168,128,40,40,0,0,0,128,88Zm0-64A104.11,104.11,0,0,0,24,128a87.76,87.76,0,0,1-5,29.33,8,8,0,0,0,15.09,5.33A103.9,103.9,0,0,0,40,128a88,88,0,0,1,176,0,282.24,282.24,0,0,1-5.29,54.45,8,8,0,0,0,6.3,9.4,8.22,8.22,0,0,0,1.55.15,8,8,0,0,0,7.84-6.45A298.37,298.37,0,0,0,232,128,104.12,104.12,0,0,0,128,24ZM94.4,152.17A8,8,0,0,0,85,158.42a151,151,0,0,1-17.21,45.44,8,8,0,0,0,13.86,8,166.67,166.67,0,0,0,19-50.25A8,8,0,0,0,94.4,152.17ZM128,56a72.85,72.85,0,0,0-9,.56,8,8,0,0,0,2,15.87A56.08,56.08,0,0,1,184,128a252.12,252.12,0,0,1-1.92,31A8,8,0,0,0,189,168a8.39,8.39,0,0,0,1,.06,8,8,0,0,0,7.92-7,266.48,266.48,0,0,0,2-33A72.08,72.08,0,0,0,128,56Zm57.93,128.25a8,8,0,0,0-9.75,5.75c-1.46,5.69-3.15,11.4-5,17a8,8,0,0,0,5,10.13,7.88,7.88,0,0,0,2.55.42,8,8,0,0,0,7.58-5.46c2-5.92,3.79-12,5.35-18.05A8,8,0,0,0,185.94,184.26Z"></path></svg>
                                <span>Encrypted Zero-Knowledge Vault</span>
                            </h2>
                            <div class="flex items-center -my-2" :title="vaultUnlocked ? 'Vault Unlocked. Click to Lock' : 'Vault Locked'">
                                <!-- Unlocked Icon -->
                                <svg x-show="vaultUnlocked" @click="saveVault()" xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-acid-deep cursor-pointer" viewBox="0 0 24 24" fill="none">
                                    <title>Vault Unlocked. Click to Lock</title>
                                    <path d="M0 0h24v24H0z" fill="none" />
                                    <path fill="currentColor" d="M12 1L3 5v6c0 5.5 3.8 10.7 9 12c5.2-1.3 9-6.5 9-12V5zm4 14.8c0 .6-.6 1.2-1.3 1.2H9.2c-.6 0-1.2-.6-1.2-1.3v-3.5c0-.6.6-1.2 1.2-1.2V8.5C9.2 7.1 10.6 6 12 6s2.8 1.1 2.8 2.5V9h-1.3v-.5c0-.8-.7-1.3-1.5-1.3s-1.5.5-1.5 1.3V11h4.3c.6 0 1.2.6 1.2 1.3z" />
                                </svg>
                                <!-- Locked Icon -->
                                <svg x-show="!vaultUnlocked" xmlns="http://www.w3.org/2000/svg" class="w-8 h-8 text-rust" viewBox="0 0 24 24" fill="none">
                                    <title>Vault Locked</title>
                                    <path d="M0 0h24v24H0z" fill="none" />
                                    <path fill="currentColor" d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12c5.16-1.26 9-6.45 9-12V5zm0 6c1.4 0 2.8 1.1 2.8 2.5V11c.6 0 1.2.6 1.2 1.3v3.5c0 .6-.6 1.2-1.3 1.2H9.2c-.6 0-1.2-.6-1.2-1.3v-3.5c0-.6.6-1.2 1.2-1.2V9.5C9.2 8.1 10.6 7 12 7m0 1.2c-.8 0-1.5.5-1.5 1.3V11h3V9.5c0-.8-.7-1.3-1.5-1.3" />
                                </svg>
                            </div>
                        </div>

                        <p class="text-xs text-forge-dark font-serif leading-prose">
                            This vault is encrypted locally in your browser using AES-256-GCM. The server never sees the plaintext contents. Use this to store sensitive API keys and SFTP passwords.
                        </p>

                        <!-- Vault Unlock Form -->
                        <form autocomplete="off" @submit.prevent x-show="!vaultUnlocked" class="p-4 bg-canvas border border-border space-y-3">
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
                                    <button @click="unlockVault()" class="pen-btn pen-btn-primary px-6">Unlock</button>
                                </div>
                            </div>
                        </form>

                        <!-- Vault Editor (Shown when unlocked) -->
                        <form autocomplete="off" @submit.prevent x-show="vaultUnlocked" x-cloak class="space-y-4">

                            <div class="flex justify-end">
                                <button @click="addVaultItem()" class="text-xs font-bold text-rust hover:underline uppercase tracking-wider">+ Add Secret</button>
                            </div>

                            <div class="space-y-4">
                                <template x-for="(item, index) in vaultData" :key="index">
                                    <template x-if="!(item.key === 'AGENT_KEYS' && (item.value && (typeof item.value === 'object' || String(item.value) === '[object Object]')))">
                                        <div class="relative p-4 bg-canvas border border-border group space-y-3">
                                            <!-- Remove Button -->
                                            <button @click="removeVaultItem(index)" class="absolute top-2 right-2 text-forge-mid hover:text-danger p-1 opacity-0 group-hover:opacity-100 transition-opacity" title="Remove Secret">
                                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                                            </button>

                                            <!-- KEY Field -->
                                            <div>
                                                <label class="flex items-center gap-1 text-[10px] font-sans font-bold uppercase tracking-wider text-forge-dark mb-1">
                                                    <svg class="w-3.5 h-3.5 text-forge-mid" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path></svg>
                                                    <span>Key Name <span class="text-rust">*</span></span>
                                                </label>
                                                <input type="text" x-model="item.key" class="pen-input font-mono text-xs" placeholder="e.g. SFTP_PASSWORD">
                                            </div>

                                            <!-- VALUE Field -->
                                            <div>
                                                <label class="flex items-center gap-1 text-[10px] font-sans font-bold uppercase tracking-wider text-forge-dark mb-1">
                                                    <svg class="w-3.5 h-3.5 text-forge-mid" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
                                                    <span>Secret Value <span class="text-rust">*</span></span>
                                                </label>
                                                <input type="text" x-model="item.value" class="pen-input font-mono text-xs" placeholder="Enter secret value">
                                            </div>
                                        </div>
                                    </template>
                                </template>
                                <div x-show="vaultData.length === 0" class="text-xs text-forge-mid italic py-4 text-center">Vault is empty.</div>
                            </div>

                            <div class="pt-4 border-t border-border/40 flex justify-end items-center">
                                <button @click="saveVault()" class="pen-btn pen-btn-acid flex items-center gap-2" :disabled="savingVault">
                                    <svg x-show="savingVault" class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
                                    <span x-text="savingVault ? 'Encrypting & Locking...' : 'Encrypt & Lock Vault'"></span>
                                </button>
                            </div>
                        </form>
                    </div>

                </div>
            </div>
        </main>
    </div>

    <!-- Footer -->
    <?php include "includes/_admin-footer.php"; ?>
