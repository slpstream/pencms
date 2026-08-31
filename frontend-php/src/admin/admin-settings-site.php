<?php
$pageTitle = "Site Settings (PenCMS)";
$currentSection = "site-settings";
$pageScript = "settings-site.js";
include "includes/_admin-auth.php";
include "includes/_admin-head.php";
?>

<body class="bg-canvas text-forge-black font-sans antialiased h-screen flex flex-col overflow-hidden"
      x-data="settingsSite">

    <!-- Header / Top Navigation -->
    <?php include "includes/_admin-header.php"; ?>

    <div class="flex flex-1 relative min-h-0 overflow-hidden">
        <!-- Collapsible Left Sidebar -->
        <?php include "includes/_admin-sidebar.php"; ?>

        <!-- Main Workspace Canvas -->
        <main class="flex-1 overflow-y-auto p-8 md:p-12 transition-all duration-300">
            <!-- Page Title -->
            <div class="mb-8 flex flex-col md:flex-row md:items-end md:justify-between gap-4">
                <div>
                    <h1 class="text-3xl text-forge-black font-sans font-black tracking-tight mb-2 pb-2 border-b-2 border-border-weld uppercase">
                        Site Settings
                    </h1>
                    <p class="text-forge-dark font-serif text-sm">
                        Edit public branding for the active Content site
                        <span class="font-mono font-bold text-rust" x-text="$store.app.activeSiteId"></span>
                        (header picker). Empty fields fall back to install defaults.
                        Logo, favicon, and hero files also apply to this site.
                        Admin chrome stays PenCMS-branded.
                    </p>
                </div>
                <div class="flex-shrink-0" x-show="activeTab !== 'authors' && canSeo()">
                    <button @click="save"
                            :disabled="saving || loading"
                            class="pen-btn pen-btn-primary flex items-center gap-2">
                        <svg x-show="saving" class="animate-spin h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        <span x-text="saving ? 'Saving...' : 'Save Settings'"></span>
                    </button>
                </div>
            </div>

            <!-- Toast Notification -->
            <div x-show="message"
                 x-cloak
                 x-transition
                 class="mb-6 p-4 border font-sans font-bold text-xs uppercase tracking-wider shadow-sm"
                 :class="messageType === 'success' ? 'bg-acid-wash border-acid text-acid-text' : 'bg-danger-bg border-danger text-danger'">
                <span x-text="message"></span>
            </div>

            <!-- Loader -->
            <div x-show="loading" class="py-20 text-center">
                <div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-rust border-t-transparent"></div>
            </div>

            <div x-show="!loading" x-cloak>
                <!-- Workspace Tabs -->
                <div class="flex border-b border-border mb-8 gap-1">
                    <button type="button"
                            x-show="canSeo()"
                            x-cloak
                            @click="activeTab = 'info'"
                            class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                            :class="activeTab === 'info' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                        Site Info
                    </button>
                    <button type="button"
                            x-show="canSeo()"
                            x-cloak
                            @click="activeTab = 'graphics'"
                            class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                            :class="activeTab === 'graphics' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                        Graphics
                    </button>
                    <button type="button"
                            x-show="canAuthors()"
                            x-cloak
                            @click="activeTab = 'authors'"
                            class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                            :class="activeTab === 'authors' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                        Authors
                    </button>
                </div>

                <!-- Tab: Site Info -->
                <div x-show="activeTab === 'info'" class="space-y-8 max-w-4xl">
                    <div class="pen-card p-6 flex flex-col gap-6">

                        <div class="border-b border-border pb-2">
                            <h2 class="text-xs font-black uppercase tracking-wider text-forge-black">
                                Active site —
                                <span class="font-mono text-rust" x-text="$store.app.activeSiteId"></span>
                            </h2>
                            <p class="text-[10px] text-forge-mid font-serif mt-1">
                                These values are stored on the site record (same as Settings → Sites soft-edit).
                            </p>
                        </div>

                        <!-- Site Name Input -->
                        <div class="flex flex-col gap-1.5">
                            <label class="pen-label">
                                Site Name
                            </label>
                            <input type="text"
                                   x-model="$store.app.sitename"
                                   :placeholder="registryName ? ('fallback: ' + registryName) : 'e.g. PenCMS Blog'"
                                   class="pen-input">
                            <p class="text-[10px] text-forge-mid">Public site title for this Content site (and admin header while it is active). Empty uses the registry display name.</p>
                        </div>

                        <!-- Tagline Input -->
                        <div class="flex flex-col gap-1.5">
                            <label class="pen-label">
                                Tagline
                            </label>
                            <input type="text"
                                   x-model="tagline"
                                   placeholder="e.g. Markdown-first static site engine"
                                   class="pen-input">
                            <p class="text-[10px] text-forge-mid">A short subtitle description for your site (used by SEO and headers).</p>
                        </div>

                        <!-- Hero Title Input -->
                        <div class="flex flex-col gap-1.5">
                            <label class="pen-label">
                                Index Hero Title
                            </label>
                            <input type="text"
                                   x-model="hero_title"
                                   placeholder="e.g. How-To & Docs"
                                   class="pen-input">
                            <p class="text-[10px] text-forge-mid">The main heading displayed in the homepage/index banner.</p>
                        </div>

                        <!-- Contact Email Input -->
                        <div class="flex flex-col gap-1.5">
                            <label class="pen-label">
                                Contact Email Address
                            </label>
                            <input type="email"
                                   x-model="contact_email"
                                   placeholder="e.g. contact@mysite.com"
                                   class="pen-input">
                            <p class="text-[10px] text-forge-mid">Optional contact email for this public site.</p>
                        </div>

                        <!-- Domain (registry Host routing) -->
                        <div class="flex flex-col gap-1.5">
                            <label class="pen-label">
                                Domain
                            </label>
                            <input type="text"
                                   x-model="domain"
                                   placeholder="e.g. wiki.example.com"
                                   class="pen-input font-mono"
                                   autocomplete="off"
                                   spellcheck="false">
                            <p class="text-[10px] text-forge-mid">Public hostname for this Content site (Host routing). Empty means no Host match for this site.</p>
                        </div>
                    </div>

                    <div class="pen-card p-6 flex flex-col gap-4">
                        <div class="flex items-start gap-3">
                            <button type="button"
                                    @click="comments_enabled = !comments_enabled"
                                    class="pen-toggle mt-0.5"
                                    :class="comments_enabled ? 'active' : ''"
                                    role="switch"
                                    :aria-checked="comments_enabled"
                                    id="comments_enabled_toggle">
                                <span class="pen-toggle-knob"></span>
                            </button>
                            <div class="flex flex-col gap-1">
                                <label @click="comments_enabled = !comments_enabled" class="font-sans font-bold text-xs uppercase tracking-wider text-forge-black cursor-pointer select-none" for="comments_enabled_toggle">
                                    Reader comments
                                </label>
                                <p class="text-[10px] text-forge-mid leading-relaxed">
                                    Off: no comment box on live or published posts; static <span class="font-mono">dist/</span> does not include comments.<br>
                                    On: live preview posts to this install; keys are created automatically.
                                </p>
                                <p class="text-[10px] text-forge-mid leading-relaxed" x-show="comments_enabled && !feedback_relay_url" x-cloak>
                                    Comments on static sites submit to the community relay unless you set your own relay URL.
                                </p>
                            </div>
                        </div>
                    </div>

                    <!-- Social Media Links Card (Accordion) -->
                    <div class="pen-card border border-border bg-card">
                        <details class="group">
                            <summary class="p-6 cursor-pointer select-none flex items-center justify-between gap-4 list-none [&::-webkit-details-marker]:hidden">
                                <div class="flex items-center gap-3">
                                    <h2 class="text-xs font-black uppercase tracking-wider text-forge-black">
                                        Social Media Links
                                    </h2>
                                    <span class="text-[10px] font-mono px-2 py-0.5 bg-canvas border border-border text-rust font-bold rounded-minimal"
                                          x-text="socialLinks.length + ' configured'"></span>
                                </div>
                                <div class="flex items-center gap-2">
                                    <span class="text-[10px] text-forge-mid font-serif group-open:hidden">Click to expand</span>
                                    <svg class="w-4 h-4 text-forge-mid transition-transform duration-200 group-open:rotate-180" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
                                    </svg>
                                </div>
                            </summary>
                            
                            <div class="px-6 pb-6 pt-2 border-t border-border space-y-6">
                                <p class="text-[10px] text-forge-mid font-serif leading-relaxed">
                                    Add optional, site-scoped social profile links (e.g. X, Bluesky, Mastodon, GitHub). Themes can access these via the <code class="font-mono text-rust">social_links</code> Twig variable.
                                </p>

                                <!-- Preset Suggestion Chips -->
                                <div class="space-y-2">
                                    <label class="pen-label">Popular Platforms</label>
                                    <div class="flex flex-wrap gap-2">
                                        <template x-for="p in presetPlatforms" :key="p.id">
                                            <button type="button"
                                                    @click="addSocialPlatform(p.id)"
                                                    :disabled="isSocialPlatformAdded(p.id)"
                                                    class="inline-flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-sans font-bold uppercase tracking-wider border transition-all duration-150"
                                                    :class="isSocialPlatformAdded(p.id) 
                                                        ? 'bg-canvas text-forge-mid border-border opacity-50 cursor-not-allowed' 
                                                        : 'bg-card text-forge-black border-border hover:border-rust hover:text-rust hover:bg-rust-wash/40 cursor-pointer'">
                                                <!-- Icons -->
                                                <template x-if="p.id === 'twitter'">
                                                    <svg class="w-3.5 h-3.5 fill-current shrink-0" viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
                                                </template>
                                                <template x-if="p.id === 'bluesky'">
                                                    <svg class="w-3.5 h-3.5 fill-current shrink-0" viewBox="0 0 568 501"><path d="M123.121 33.664c62.155 46.742 129.07 141.654 160.879 193.304 31.809-51.65 98.724-146.562 160.879-193.304 44.512-33.475 116.544-59.08 116.544 22.84 0 16.34-9.352 137.494-14.845 157.109-19.085 68.14-88.354 85.529-150.316 74.966 108.318 18.444 135.882 79.52 76.326 140.781-113.12 116.36-169.584-29.19-188.588-75.143-19.004 45.953-75.468 191.503-188.588 75.143-59.556-61.261-31.992-122.337 76.326-140.781-61.962 10.563-131.231-6.826-150.316-74.966C23.073 173.998 13.721 52.844 13.721 36.504c0-81.92 72.032-56.315 116.544-22.84z"/></svg>
                                                </template>
                                                <template x-if="p.id === 'mastodon'">
                                                    <svg class="w-3.5 h-3.5 fill-current shrink-0" viewBox="0 0 24 24"><path d="M23.268 5.313c-.35-2.578-2.617-4.61-5.3-5.004C15.534.024 12.012 0 12.012 0h-.024s-3.522.024-5.956.309C3.354.713 1.087 2.745.737 5.313c-.28 2.08-.344 4.316-.277 6.467.11 3.524.896 6.974 2.827 9.539 1.776 2.36 4.394 3.328 7.332 3.535 2.946.208 5.753-.29 7.732-1.294 0 0 .47-.234.47-.698 0-.464-.093-1.077-.093-1.077 0 0-.256.091-1.077.279-.82.188-2.316.398-3.953.398-2.616 0-3.324-1.234-3.504-2.58-.046-.35-.069-.744-.069-1.171 1.776.435 3.65.626 5.52.558 2.057-.075 4.048-.52 5.92-1.312 1.481-.624 2.827-1.488 3.5-3.053.483-1.127.674-2.392.74-3.657.115-2.15.051-4.387-.229-6.467zM17.476 13.9H15.11v-5.63c0-1.189-.5-1.791-1.501-1.791-1.106 0-1.662.715-1.662 2.13v3.088h-2.36v-3.088c0-1.415-.556-2.13-1.662-2.13-1.001 0-1.501.602-1.501 1.791v5.63H4.06V8.125c0-1.19.304-2.134.912-2.833.633-.701 1.46-1.064 2.481-1.064 1.187 0 2.083.454 2.684 1.363l.635 1.074.635-1.074c.601-.909 1.497-1.363 2.684-1.363 1.021 0 1.848.363 2.481 1.064.608.699.912 1.643.912 2.833V13.9z"/></svg>
                                                </template>
                                                <template x-if="p.id === 'instagram'">
                                                    <svg class="w-3.5 h-3.5 fill-current shrink-0" viewBox="0 0 24 24"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>
                                                </template>
                                                <template x-if="p.id === 'facebook'">
                                                    <svg class="w-3.5 h-3.5 fill-current shrink-0" viewBox="0 0 24 24"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>
                                                </template>
                                                <template x-if="p.id === 'vk'">
                                                    <svg class="w-3.5 h-3.5 fill-current shrink-0" viewBox="0 0 24 24"><path d="M15.684 0H8.316C1.592 0 0 1.592 0 8.316v7.368C0 22.408 1.592 24 8.316 24h7.368C22.408 24 24 22.408 24 15.684V8.316C24 1.592 22.408 0 15.684 0zm3.692 17.123h-1.644c-.624 0-.816-.495-1.933-1.616-1.042-1.042-1.492-1.176-1.745-1.176-.362 0-.466.102-.466.591v1.656c0 .428-.137.695-1.25.695-1.846 0-3.89-1.121-5.334-3.204-2.176-3.09-2.766-5.412-2.766-5.882 0-.256.102-.495.592-.495h1.644c.442 0 .607.205.776.68.854 2.476 2.278 4.646 2.871 4.646.223 0 .324-.102.324-.664v-2.585c-.068-1.154-.672-1.253-.672-1.666 0-.2.169-.4.436-.4h2.724c.371 0 .5.195.5.64v3.486c0 .376.163.504.275.504.223 0 .412-.128.824-.54 1.265-1.42 2.167-3.626 2.167-3.626.118-.256.321-.495.762-.495h1.644c.495 0 .6.256.495.607-.205.952-2.203 3.784-2.203 3.784-.173.275-.24.398 0 .72 0 0 1.905 2.545 2.1 3.523.119.467-.091.706-.558.706z"/></svg>
                                                </template>
                                                <template x-if="p.id === 'linkedin'">
                                                    <svg class="w-3.5 h-3.5 fill-current shrink-0" viewBox="0 0 24 24"><path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/></svg>
                                                </template>
                                                <template x-if="p.id === 'github'">
                                                    <svg class="w-3.5 h-3.5 fill-current shrink-0" viewBox="0 0 24 24"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
                                                </template>
                                                <template x-if="p.id === 'telegram'">
                                                    <svg class="w-3.5 h-3.5 shrink-0" viewBox="0 0 256 256"><rect width="256" height="256" fill="none"/><path d="M80,134.87,170.26,214a8,8,0,0,0,13.09-4.21L224,33.22a1,1,0,0,0-1.34-1.15L20,111.38A6.23,6.23,0,0,0,21,123.3Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><line x1="80" y1="134.87" x2="223.41" y2="32.09" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M124.37,173.78,93.76,205.54A8,8,0,0,1,80,200V134.87" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>
                                                </template>
                                                <template x-if="p.id === 'youtube'">
                                                    <svg class="w-3.5 h-3.5 fill-current shrink-0" viewBox="0 0 24 24"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>
                                                </template>
                                                <template x-if="p.id === 'tiktok'">
                                                    <svg class="w-3.5 h-3.5 fill-current shrink-0" viewBox="0 0 24 24"><path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.82.56-1.32 1.52-1.32 2.52-.02 1.05.5 2.06 1.37 2.62.9.59 2.08.68 3.05.24.96-.42 1.66-1.36 1.77-2.4.04-1.27.02-2.54.02-3.81.01-4.34.01-8.68.01-13.02z"/></svg>
                                                </template>
                                                <template x-if="p.id === 'reddit'">
                                                    <svg class="w-3.5 h-3.5 fill-current shrink-0" viewBox="0 0 24 24"><path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.562-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.688-.562-1.249-1.25-1.249zm-4.566 3.847a.31.31 0 0 0-.214.53 4.35 4.35 0 0 0 4.06 0 .31.31 0 0 0-.214-.53c-.76.096-1.536.096-2.295 0a.31.31 0 0 0-.177 0z"/></svg>
                                                </template>
                                                <template x-if="p.id === 'discord'">
                                                    <svg class="w-3.5 h-3.5 shrink-0" viewBox="0 0 256 256"><rect width="256" height="256" fill="none"/><circle cx="92" cy="136" r="16"/><circle cx="164" cy="136" r="16"/><path d="M151.47,81.43l6.95-27.37a8.1,8.1,0,0,1,9.21-6L203.69,54A8.08,8.08,0,0,1,210.23,60l29.53,116.37a8,8,0,0,1-4.55,9.24l-67,29.7a8.15,8.15,0,0,1-11-4.56L145.61,179.2" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M104.53,81.43l-7-27.37a8.1,8.1,0,0,0-9.21-6L52.31,54A8.08,8.08,0,0,0,45.77,60L16.24,176.35a8,8,0,0,0,4.55,9.24l67,29.7a8.15,8.15,0,0,0,11-4.56l11.64-31.53" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M84,85.24A181.44,181.44,0,0,1,128,80a181.44,181.44,0,0,1,44,5.24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M172,174.76A181.44,181.44,0,0,1,128,180a181.44,181.44,0,0,1-44-5.24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>
                                                </template>
                                                <template x-if="p.id === 'slack'">
                                                    <svg class="w-3.5 h-3.5 shrink-0" viewBox="0 0 256 256"><rect width="256" height="256" fill="none"/><path d="M80,56h24a0,0,0,0,1,0,0v72a24,24,0,0,1-24,24h0a24,24,0,0,1-24-24V80A24,24,0,0,1,80,56Z" transform="translate(184 24) rotate(90)" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M128,80H104A24,24,0,0,1,80,56h0a24,24,0,0,1,24-24h0a24,24,0,0,1,24,24Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M152,32h24a0,0,0,0,1,0,0v72a24,24,0,0,1-24,24h0a24,24,0,0,1-24-24V56a24,24,0,0,1,24-24Z" transform="translate(304 160) rotate(-180)" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M176,128V104a24,24,0,0,1,24-24h0a24,24,0,0,1,24,24h0a24,24,0,0,1-24,24Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M176,104h24a0,0,0,0,1,0,0v72a24,24,0,0,1-24,24h0a24,24,0,0,1-24-24V128a24,24,0,0,1,24-24Z" transform="translate(24 328) rotate(-90)" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M128,176h24a24,24,0,0,1,24,24h0a24,24,0,0,1-24,24h0a24,24,0,0,1-24-24Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M104,128h24a0,0,0,0,1,0,0v72a24,24,0,0,1-24,24h0a24,24,0,0,1-24-24V152A24,24,0,0,1,104,128Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M80,128v24a24,24,0,0,1-24,24h0a24,24,0,0,1-24-24h0a24,24,0,0,1,24-24Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>
                                                </template>
                                                <template x-if="p.id === 'whatsapp'">
                                                    <svg class="w-3.5 h-3.5 fill-current shrink-0" viewBox="0 0 256 256"><rect width="256" height="256" fill="none"/><path d="M152.58,145.23l23,11.48A24,24,0,0,1,152,176a72.08,72.08,0,0,1-72-72A24,24,0,0,1,99.29,80.46l11.48,23L101,118a8,8,0,0,0-.73,7.51,56.47,56.47,0,0,0,30.15,30.15A8,8,0,0,0,138,155ZM232,128A104,104,0,0,1,79.12,219.82L45.07,231.17a16,16,0,0,1-20.24-20.24l11.35-34.05A104,104,0,1,1,232,128Zm-40,24a8,8,0,0,0-4.42-7.16l-32-16a8,8,0,0,0-8,.5l-14.69,9.8a40.55,40.55,0,0,1-16-16l9.8-14.69a8,8,0,0,0,.5-8l-16-32A8,8,0,0,0,104,64a40,40,0,0,0-40,40,88.1,88.1,0,0,0,88,88A40,40,0,0,0,192,152Z"/></svg>
                                                </template>
                                                <span x-text="p.name"></span>
                                                <span x-show="!isSocialPlatformAdded(p.id)" class="text-[10px] text-rust ml-0.5">+</span>
                                            </button>
                                        </template>
                                    </div>
                                </div>

                                <!-- Active Social Links List -->
                                <div class="space-y-3 pt-2 border-t border-border">
                                    <template x-if="socialLinks.length === 0">
                                        <div class="p-4 bg-canvas border border-dashed border-border text-center text-xs text-forge-mid italic">
                                            No social media links added yet. Click a platform chip above or add a custom link below.
                                        </div>
                                    </template>

                                    <template x-for="(link, idx) in socialLinks" :key="idx">
                                        <div class="flex items-center gap-3 p-3 bg-canvas border border-border">
                                            <!-- Platform Icon & Label Badge -->
                                            <div class="flex items-center gap-2 min-w-[120px] max-w-[160px] shrink-0">
                                                <span class="p-1.5 bg-card border border-border text-forge-black shrink-0">
                                                    <template x-if="link.platform === 'twitter'">
                                                        <svg class="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
                                                    </template>
                                                    <template x-if="link.platform === 'bluesky'">
                                                        <svg class="w-3.5 h-3.5 fill-current" viewBox="0 0 568 501"><path d="M123.121 33.664c62.155 46.742 129.07 141.654 160.879 193.304 31.809-51.65 98.724-146.562 160.879-193.304 44.512-33.475 116.544-59.08 116.544 22.84 0 16.34-9.352 137.494-14.845 157.109-19.085 68.14-88.354 85.529-150.316 74.966 108.318 18.444 135.882 79.52 76.326 140.781-113.12 116.36-169.584-29.19-188.588-75.143-19.004 45.953-75.468 191.503-188.588 75.143-59.556-61.261-31.992-122.337 76.326-140.781-61.962 10.563-131.231-6.826-150.316-74.966C23.073 173.998 13.721 52.844 13.721 36.504c0-81.92 72.032-56.315 116.544-22.84z"/></svg>
                                                    </template>
                                                    <template x-if="link.platform === 'mastodon'">
                                                        <svg class="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24"><path d="M23.268 5.313c-.35-2.578-2.617-4.61-5.3-5.004C15.534.024 12.012 0 12.012 0h-.024s-3.522.024-5.956.309C3.354.713 1.087 2.745.737 5.313c-.28 2.08-.344 4.316-.277 6.467.11 3.524.896 6.974 2.827 9.539 1.776 2.36 4.394 3.328 7.332 3.535 2.946.208 5.753-.29 7.732-1.294 0 0 .47-.234.47-.698 0-.464-.093-1.077-.093-1.077 0 0-.256.091-1.077.279-.82.188-2.316.398-3.953.398-2.616 0-3.324-1.234-3.504-2.58-.046-.35-.069-.744-.069-1.171 1.776.435 3.65.626 5.52.558 2.057-.075 4.048-.52 5.92-1.312 1.481-.624 2.827-1.488 3.5-3.053.483-1.127.674-2.392.74-3.657.115-2.15.051-4.387-.229-6.467zM17.476 13.9H15.11v-5.63c0-1.189-.5-1.791-1.501-1.791-1.106 0-1.662.715-1.662 2.13v3.088h-2.36v-3.088c0-1.415-.556-2.13-1.662-2.13-1.001 0-1.501.602-1.501 1.791v5.63H4.06V8.125c0-1.19.304-2.134.912-2.833.633-.701 1.46-1.064 2.481-1.064 1.187 0 2.083.454 2.684 1.363l.635 1.074.635-1.074c.601-.909 1.497-1.363 2.684-1.363 1.021 0 1.848.363 2.481 1.064.608.699.912 1.643.912 2.833V13.9z"/></svg>
                                                    </template>
                                                    <template x-if="link.platform === 'instagram'">
                                                        <svg class="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>
                                                    </template>
                                                    <template x-if="link.platform === 'facebook'">
                                                        <svg class="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>
                                                    </template>
                                                    <template x-if="link.platform === 'vk'">
                                                        <svg class="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24"><path d="M15.684 0H8.316C1.592 0 0 1.592 0 8.316v7.368C0 22.408 1.592 24 8.316 24h7.368C22.408 24 24 22.408 24 15.684V8.316C24 1.592 22.408 0 15.684 0zm3.692 17.123h-1.644c-.624 0-.816-.495-1.933-1.616-1.042-1.042-1.492-1.176-1.745-1.176-.362 0-.466.102-.466.591v1.656c0 .428-.137.695-1.25.695-1.846 0-3.89-1.121-5.334-3.204-2.176-3.09-2.766-5.412-2.766-5.882 0-.256.102-.495.592-.495h1.644c.442 0 .607.205.776.68.854 2.476 2.278 4.646 2.871 4.646.223 0 .324-.102.324-.664v-2.585c-.068-1.154-.672-1.253-.672-1.666 0-.2.169-.4.436-.4h2.724c.371 0 .5.195.5.64v3.486c0 .376.163.504.275.504.223 0 .412-.128.824-.54 1.265-1.42 2.167-3.626 2.167-3.626.118-.256.321-.495.762-.495h1.644c.495 0 .6.256.495.607-.205.952-2.203 3.784-2.203 3.784-.173.275-.24.398 0 .72 0 0 1.905 2.545 2.1 3.523.119.467-.091.706-.558.706z"/></svg>
                                                    </template>
                                                    <template x-if="link.platform === 'linkedin'">
                                                        <svg class="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24"><path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z"/></svg>
                                                    </template>
                                                    <template x-if="link.platform === 'github'">
                                                        <svg class="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
                                                    </template>
                                                    <template x-if="link.platform === 'telegram'">
                                                        <svg class="w-3.5 h-3.5" viewBox="0 0 256 256"><rect width="256" height="256" fill="none"/><path d="M80,134.87,170.26,214a8,8,0,0,0,13.09-4.21L224,33.22a1,1,0,0,0-1.34-1.15L20,111.38A6.23,6.23,0,0,0,21,123.3Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><line x1="80" y1="134.87" x2="223.41" y2="32.09" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M124.37,173.78,93.76,205.54A8,8,0,0,1,80,200V134.87" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>
                                                    </template>
                                                    <template x-if="link.platform === 'youtube'">
                                                        <svg class="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>
                                                    </template>
                                                    <template x-if="link.platform === 'tiktok'">
                                                        <svg class="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24"><path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.82.56-1.32 1.52-1.32 2.52-.02 1.05.5 2.06 1.37 2.62.9.59 2.08.68 3.05.24.96-.42 1.66-1.36 1.77-2.4.04-1.27.02-2.54.02-3.81.01-4.34.01-8.68.01-13.02z"/></svg>
                                                    </template>
                                                    <template x-if="link.platform === 'reddit'">
                                                        <svg class="w-3.5 h-3.5 fill-current" viewBox="0 0 24 24"><path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.562-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.688-.562-1.249-1.25-1.249zm-4.566 3.847a.31.31 0 0 0-.214.53 4.35 4.35 0 0 0 4.06 0 .31.31 0 0 0-.214-.53c-.76.096-1.536.096-2.295 0a.31.31 0 0 0-.177 0z"/></svg>
                                                    </template>
                                                    <template x-if="link.platform === 'discord'">
                                                        <svg class="w-3.5 h-3.5" viewBox="0 0 256 256"><rect width="256" height="256" fill="none"/><circle cx="92" cy="136" r="16"/><circle cx="164" cy="136" r="16"/><path d="M151.47,81.43l6.95-27.37a8.1,8.1,0,0,1,9.21-6L203.69,54A8.08,8.08,0,0,1,210.23,60l29.53,116.37a8,8,0,0,1-4.55,9.24l-67,29.7a8.15,8.15,0,0,1-11-4.56L145.61,179.2" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M104.53,81.43l-7-27.37a8.1,8.1,0,0,0-9.21-6L52.31,54A8.08,8.08,0,0,0,45.77,60L16.24,176.35a8,8,0,0,0,4.55,9.24l67,29.7a8.15,8.15,0,0,0,11-4.56l11.64-31.53" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M84,85.24A181.44,181.44,0,0,1,128,80a181.44,181.44,0,0,1,44,5.24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M172,174.76A181.44,181.44,0,0,1,128,180a181.44,181.44,0,0,1-44-5.24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>
                                                    </template>
                                                    <template x-if="link.platform === 'slack'">
                                                        <svg class="w-3.5 h-3.5" viewBox="0 0 256 256"><rect width="256" height="256" fill="none"/><path d="M80,56h24a0,0,0,0,1,0,0v72a24,24,0,0,1-24,24h0a24,24,0,0,1-24-24V80A24,24,0,0,1,80,56Z" transform="translate(184 24) rotate(90)" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M128,80H104A24,24,0,0,1,80,56h0a24,24,0,0,1,24-24h0a24,24,0,0,1,24,24Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M152,32h24a0,0,0,0,1,0,0v72a24,24,0,0,1-24,24h0a24,24,0,0,1-24-24V56a24,24,0,0,1,24-24Z" transform="translate(304 160) rotate(-180)" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M176,128V104a24,24,0,0,1,24-24h0a24,24,0,0,1,24,24h0a24,24,0,0,1-24,24Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M176,104h24a0,0,0,0,1,0,0v72a24,24,0,0,1-24,24h0a24,24,0,0,1-24-24V128a24,24,0,0,1,24-24Z" transform="translate(24 328) rotate(-90)" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M128,176h24a24,24,0,0,1,24,24h0a24,24,0,0,1-24,24h0a24,24,0,0,1-24-24Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M104,128h24a0,0,0,0,1,0,0v72a24,24,0,0,1-24,24h0a24,24,0,0,1-24-24V152A24,24,0,0,1,104,128Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><path d="M80,128v24a24,24,0,0,1-24,24h0a24,24,0,0,1-24-24h0a24,24,0,0,1,24-24Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>
                                                    </template>
                                                    <template x-if="link.platform === 'whatsapp'">
                                                        <svg class="w-3.5 h-3.5 fill-current" viewBox="0 0 256 256"><rect width="256" height="256" fill="none"/><path d="M152.58,145.23l23,11.48A24,24,0,0,1,152,176a72.08,72.08,0,0,1-72-72A24,24,0,0,1,99.29,80.46l11.48,23L101,118a8,8,0,0,0-.73,7.51,56.47,56.47,0,0,0,30.15,30.15A8,8,0,0,0,138,155ZM232,128A104,104,0,0,1,79.12,219.82L45.07,231.17a16,16,0,0,1-20.24-20.24l11.35-34.05A104,104,0,1,1,232,128Zm-40,24a8,8,0,0,0-4.42-7.16l-32-16a8,8,0,0,0-8,.5l-14.69,9.8a40.55,40.55,0,0,1-16-16l9.8-14.69a8,8,0,0,0,.5-8l-16-32A8,8,0,0,0,104,64a40,40,0,0,0-40,40,88.1,88.1,0,0,0,88,88A40,40,0,0,0,192,152Z"/></svg>
                                                    </template>
                                                    <template x-if="link.platform === 'custom'">
                                                        <svg class="w-3.5 h-3.5 fill-none stroke-current" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 21a9 9 0 100-18 9 9 0 000 18zM2.25 12h19.5M12 2.25C14.5 5.5 15.75 8.75 15.75 12S14.5 18.5 12 21.75M12 2.25C9.5 5.5 8.25 8.75 8.25 12S9.5 18.5 12 21.75"/></svg>
                                                    </template>
                                                </span>
                                                <span class="text-xs font-sans font-bold uppercase tracking-wider text-forge-black truncate"
                                                      x-text="getSocialPlatformName(link.platform)"></span>
                                            </div>

                                            <!-- Custom Label Input (if custom platform) -->
                                            <template x-if="link.platform === 'custom'">
                                                <div class="w-32 shrink-0">
                                                    <input type="text"
                                                           x-model="link.label"
                                                           placeholder="Label (e.g. RSS)"
                                                           class="pen-input text-xs w-full"
                                                           autocomplete="off">
                                                </div>
                                            </template>

                                            <!-- URL Input -->
                                            <div class="flex-1 min-w-0">
                                                <input type="url"
                                                       x-model="link.url"
                                                       @blur="link.url = normalizeSocialUrl(link.platform, link.url)"
                                                       :placeholder="getSocialPlaceholder(link.platform)"
                                                       class="pen-input text-xs font-mono w-full"
                                                       autocomplete="off"
                                                       required>
                                            </div>

                                            <!-- Remove Button -->
                                            <button type="button"
                                                    @click="removeSocial(idx)"
                                                    class="p-1.5 text-forge-mid hover:text-danger transition-colors shrink-0"
                                                    title="Remove link">
                                                <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                                                    <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                                                </svg>
                                            </button>
                                        </div>
                                    </template>
                                </div>

                                <!-- Add Custom Link Button -->
                                <div class="flex justify-start pt-2">
                                    <button type="button"
                                            @click="addCustomSocial()"
                                            class="pen-btn text-xs flex items-center gap-1.5 border border-border bg-card hover:bg-canvas">
                                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
                                        </svg>
                                        <span>Add Custom Link</span>
                                    </button>
                                </div>
                            </div>
                        </details>
                    </div>
                </div>

                <!-- Tab: Graphics -->
                <div x-show="activeTab === 'graphics'" class="space-y-8 max-w-4xl" x-cloak>
                    <!-- Logo Card -->
                    <div class="pen-card p-6 flex flex-col gap-6" x-data="{ dragging: false }">
                        <h3 class="w-full font-sans font-black text-xs uppercase tracking-wider text-forge-dark border-b border-border pb-2">
                            Logo Preview
                        </h3>

                        <div class="relative group w-full min-h-[160px] border-2 border-dashed border-border bg-canvas flex flex-col items-center justify-center p-4 transition-all duration-200 cursor-pointer select-none"
                             :class="dragging ? 'border-rust bg-rust-wash' : 'border-border hover:border-rust hover:bg-rust-wash/50'"
                             @dragover.prevent="dragging = true"
                             @dragleave.prevent="dragging = false"
                             @drop.prevent="dragging = false; handleLogoDrop($event)"
                             @click="$refs.logoInput.click()">

                            <template x-if="logoPreview">
                                <img :src="logoPreview" alt="Logo Preview" class="max-h-28 object-contain transition-all duration-300"
                                     :class="display_logo ? 'opacity-100' : 'opacity-40 grayscale contrast-75'">
                            </template>

                            <template x-if="!logoPreview">
                                <div class="text-center flex flex-col items-center gap-2">
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-8 h-8 text-forge-mid">
                                        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v6m3-3H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                    <span class="block text-forge-mid text-[10px] uppercase font-bold tracking-wider">Drag Logo Here</span>
                                    <span class="text-[8px] text-forge-mid/70">or click to browse</span>
                                </div>
                            </template>

                            <template x-if="logoPreview">
                                <div class="absolute inset-0 bg-forge-black/75 opacity-0 group-hover:opacity-100 flex flex-col items-center justify-center transition-opacity duration-200">
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-6 h-6 text-white mb-1">
                                        <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                                    </svg>
                                    <span class="text-[10px] text-white font-bold uppercase tracking-wider">Change Logo</span>
                                </div>
                            </template>
                        </div>

                        <input type="file" x-ref="logoInput" class="hidden" accept="image/*" @change="handleLogoFileSelect($event)">

                        <p class="text-[10px] text-forge-mid leading-relaxed">
                            The uploaded logo replaces the default logo in your headers and RSS feed templates. Maximum allowable file size is <strong>10MB</strong>. For best results, use SVG or transparent PNG file.
                        </p>

                        <!-- Display Site Logo Toggle -->
                        <div class="flex items-center gap-3 border-t border-border pt-4" x-show="logoPreview" x-cloak>
                            <button type="button"
                                    @click="display_logo = !display_logo"
                                    class="pen-toggle"
                                    :class="display_logo ? 'active' : ''"
                                    role="switch"
                                    :aria-checked="display_logo"
                                    id="display_logo_toggle">
                                <span class="pen-toggle-knob"></span>
                            </button>
                            <div class="flex flex-col">
                                <label @click="display_logo = !display_logo" class="font-sans font-bold text-xs uppercase tracking-wider text-forge-black cursor-pointer select-none">
                                    Display Site Logo
                                </label>
                                <span class="text-[10px] text-forge-mid leading-relaxed">
                                    Toggle whether the logo image or the plain text site name is featured in page headers (when supported by the chosen theme).
                                </span>
                            </div>
                        </div>
                    </div>

                    <!-- Hero Image Card -->
                    <div class="pen-card p-6 flex flex-col gap-6" x-data="{ dragging: false }">
                        <h3 class="w-full font-sans font-black text-xs uppercase tracking-wider text-forge-dark border-b border-border pb-2">
                            Hero Image Preview
                        </h3>

                        <div class="relative group w-full min-h-[160px] border-2 border-dashed border-border bg-canvas flex flex-col items-center justify-center p-4 transition-all duration-200 cursor-pointer select-none"
                             :class="dragging ? 'border-rust bg-rust-wash' : 'border-border hover:border-rust hover:bg-rust-wash/50'"
                             @dragover.prevent="dragging = true"
                             @dragleave.prevent="dragging = false"
                             @drop.prevent="dragging = false; handleHeroDrop($event)"
                             @click="$refs.heroInput.click()">

                            <template x-if="heroPreview">
                                <img :src="heroPreview" alt="Hero Preview" class="max-h-28 object-contain transition-all duration-300">
                            </template>

                            <template x-if="!heroPreview">
                                <div class="text-center flex flex-col items-center gap-2">
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-8 h-8 text-forge-mid">
                                        <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375 0 11-.75 0 .375 0 01.75 0z" />
                                    </svg>
                                    <span class="block text-forge-mid text-[10px] uppercase font-bold tracking-wider">Drag Hero Image Here</span>
                                    <span class="text-[8px] text-forge-mid/70">or click to browse</span>
                                </div>
                            </template>

                            <template x-if="heroPreview">
                                <div class="absolute inset-0 bg-forge-black/75 opacity-0 group-hover:opacity-100 flex flex-col items-center justify-center transition-opacity duration-200">
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-6 h-6 text-white mb-1">
                                        <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                                    </svg>
                                    <span class="text-[10px] text-white font-bold uppercase tracking-wider">Change Hero Image</span>
                                </div>
                            </template>
                        </div>

                        <input type="file" x-ref="heroInput" class="hidden" accept="image/*" @change="handleHeroFileSelect($event)">

                        <p class="text-[10px] text-forge-mid leading-relaxed">
                            Some themes feature the uploaded hero image in the main homepage header background. Maximum allowable file size is <strong>10MB</strong>. For best results, use a high-resolution landscape image.
                        </p>
                    </div>

                    <!-- Favicon Card -->
                    <div class="pen-card p-6 flex flex-col gap-6" x-data="{ dragging: false }">
                        <h3 class="w-full font-sans font-black text-xs uppercase tracking-wider text-forge-dark border-b border-border pb-2">
                            Favicon Preview
                        </h3>

                        <div class="relative group w-full min-h-[160px] border-2 border-dashed border-border bg-canvas flex flex-col items-center justify-center p-4 transition-all duration-200 cursor-pointer select-none"
                             :class="dragging ? 'border-rust bg-rust-wash' : 'border-border hover:border-rust hover:bg-rust-wash/50'"
                             @dragover.prevent="dragging = true"
                             @dragleave.prevent="dragging = false"
                             @drop.prevent="dragging = false; handleFaviconDrop($event)"
                             @click="$refs.faviconInput.click()">

                            <template x-if="faviconPreview">
                                <img :src="faviconPreview" alt="Favicon Preview" class="w-16 h-16 object-contain transition-all duration-300">
                            </template>

                            <template x-if="!faviconPreview">
                                <div class="text-center flex flex-col items-center gap-2">
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-8 h-8 text-forge-mid">
                                        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v6m3-3H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                    <span class="block text-forge-mid text-[10px] uppercase font-bold tracking-wider">Drag Favicon Here</span>
                                    <span class="text-[8px] text-forge-mid/70">or click to browse</span>
                                </div>
                            </template>

                            <template x-if="faviconPreview">
                                <div class="absolute inset-0 bg-forge-black/75 opacity-0 group-hover:opacity-100 flex flex-col items-center justify-center transition-opacity duration-200">
                                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-6 h-6 text-white mb-1">
                                        <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                                    </svg>
                                    <span class="text-[10px] text-white font-bold uppercase tracking-wider">Change Favicon</span>
                                </div>
                            </template>
                        </div>

                        <input type="file" x-ref="faviconInput" class="hidden" accept=".ico,.svg,image/x-icon,image/svg+xml" @change="handleFaviconFileSelect($event)">

                        <p class="text-[10px] text-forge-mid leading-relaxed">
                            The uploaded favicon appears in the browser tab. For best results, use `.svg` or `.ico` formats.
                        </p>
                    </div>
                </div>

                <!-- Tab: Authors -->
                <div x-show="activeTab === 'authors'" class="space-y-8 max-w-4xl" x-cloak>
                    <div class="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
                        <div>
                            <h2 class="text-xs font-black uppercase tracking-wider text-forge-black">
                                Authors —
                                <span class="font-mono text-rust" x-text="$store.app.activeSiteId"></span>
                            </h2>
                            <p class="text-[10px] text-forge-mid font-serif mt-1 max-w-xl">
                                Site-scoped contributor bios (plain text). Guest contributors do not need a CMS login.
                                Avatars are optional. Saved per author — not via Save Settings.
                            </p>
                        </div>
                        <button type="button"
                                x-show="!showAuthorForm"
                                @click="openNewAuthor()"
                                class="pen-btn pen-btn-primary flex-shrink-0">
                            + Add Author
                        </button>
                    </div>

                    <!-- Create / Edit form -->
                    <div x-show="showAuthorForm" x-cloak x-transition class="pen-card p-6 flex flex-col gap-6">
                        <div class="border-b border-border pb-2 flex items-center justify-between gap-4">
                            <h3 class="font-sans font-black text-xs uppercase tracking-wider text-forge-dark"
                                x-text="editingSlug ? 'Edit Author' : 'New Author'"></h3>
                            <button type="button"
                                    @click="cancelAuthorForm()"
                                    class="p-1 text-forge-mid hover:text-rust transition-colors"
                                    aria-label="Close">
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-5 h-5">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>

                        <!-- Name / Slug (required) -->
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div class="flex flex-col gap-1.5">
                                <label class="pen-label">Name <span class="text-rust" aria-hidden="true">*</span></label>
                                <input type="text"
                                       x-model="authorForm.name"
                                       @input="onAuthorNameInput()"
                                       class="pen-input"
                                       placeholder="Jane Doe"
                                       autocomplete="off"
                                       required>
                            </div>
                            <div class="flex flex-col gap-1.5">
                                <label class="pen-label">Slug <span class="text-rust" aria-hidden="true">*</span></label>
                                <input type="text"
                                       x-model="authorForm.slug"
                                       :disabled="!!editingSlug"
                                       class="pen-input font-mono"
                                       :class="editingSlug ? 'opacity-60 cursor-not-allowed' : ''"
                                       placeholder="jane-doe"
                                       autocomplete="off"
                                       spellcheck="false"
                                       required>
                                <p class="text-[10px] text-forge-mid" x-show="!editingSlug">Auto-filled from name; edit before saving if needed.</p>
                                <p class="text-[10px] text-forge-mid" x-show="editingSlug">Slug cannot be changed after create.</p>
                            </div>
                        </div>

                        <!-- Optional -->
                        <div class="flex flex-col gap-4 border-t border-border pt-6">
                            <h4 class="font-sans font-black text-[10px] uppercase tracking-wider text-forge-black border-b border-border pb-1.5">
                                Optional
                            </h4>
                            <div class="flex flex-col md:flex-row gap-8">
                                <!-- Avatar dropzone -->
                                <div class="flex flex-col items-center gap-2 flex-shrink-0" x-data="{ dragging: false }">
                                    <div class="relative group w-32 h-32 rounded-full border-2 border-dashed border-steel-muted hover:border-rust flex items-center justify-center bg-canvas transition-all duration-300 overflow-hidden shadow-sm cursor-pointer"
                                         :class="dragging ? 'border-rust bg-rust-wash scale-105' : ''"
                                         @dragover.prevent="dragging = true"
                                         @dragleave.prevent="dragging = false"
                                         @drop.prevent="dragging = false; handleAuthorAvatarDrop($event)"
                                         @click="$refs.authorAvatarInput.click()">

                                        <template x-if="authorAvatarPreview">
                                            <img :src="authorAvatarPreview" alt="Author avatar" class="w-full h-full object-cover">
                                        </template>

                                        <template x-if="!authorAvatarPreview">
                                            <div class="flex flex-col items-center justify-center p-2 text-forge-mid">
                                                <svg class="w-8 h-8 mb-1 text-forge-mid" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                                </svg>
                                                <span class="text-[9px] uppercase tracking-wider font-bold text-center">Avatar</span>
                                            </div>
                                        </template>

                                        <div class="absolute inset-0 bg-forge-black/75 opacity-0 group-hover:opacity-100 flex flex-col items-center justify-center transition-all duration-200">
                                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-6 h-6 text-white mb-1">
                                                <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                                            </svg>
                                            <span class="text-[9px] text-white font-bold uppercase tracking-wider">Change Pic</span>
                                        </div>
                                    </div>
                                    <input type="file" x-ref="authorAvatarInput" class="hidden" accept="image/*" @change="handleAuthorAvatarSelect($event)">
                                    <span class="text-[10px] text-forge-mid italic text-center max-w-[8rem]">Drag or click to upload</span>
                                </div>

                                <div class="flex-1 flex flex-col gap-4 min-w-0">
                                    <div class="flex flex-col gap-1.5">
                                        <label class="pen-label">Bio (plain text)</label>
                                        <textarea x-model="authorForm.bio"
                                                  rows="4"
                                                  class="pen-input font-serif resize-y min-h-[6rem]"
                                                  placeholder="Short contributor bio as plain text"></textarea>
                                    </div>

                                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                        <div class="flex flex-col gap-1.5">
                                            <label class="pen-label">Website</label>
                                            <input type="url"
                                                   x-model="authorForm.website"
                                                   class="pen-input"
                                                   placeholder="https://example.com"
                                                   autocomplete="off">
                                        </div>
                                        <div class="flex flex-col gap-1.5">
                                            <label class="pen-label">Email</label>
                                            <input type="email"
                                                   x-model="authorForm.email"
                                                   class="pen-input"
                                                   placeholder="optional@example.com"
                                                   autocomplete="off">
                                        </div>
                                    </div>

                                    <!-- Advanced: Role + Sort order -->
                                    <div class="border border-border bg-canvas/40">
                                        <button type="button"
                                                class="w-full flex items-center justify-between gap-3 px-3 py-2.5 select-none"
                                                @click="showAuthorAdvanced = !showAuthorAdvanced"
                                                :aria-expanded="showAuthorAdvanced">
                                            <span class="text-[10px] font-black uppercase tracking-wider text-rust">Advanced</span>
                                            <svg class="w-3.5 h-3.5 text-forge-mid transition-transform duration-200"
                                                 :class="showAuthorAdvanced ? '' : '-rotate-90'"
                                                 fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"
                                                 aria-hidden="true">
                                                <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
                                            </svg>
                                        </button>
                                        <div x-show="showAuthorAdvanced"
                                             x-cloak
                                             x-transition
                                             class="px-3 pb-3 pt-1 border-t border-border space-y-4">
                                            <p class="text-[10px] text-forge-mid font-serif leading-relaxed">
                                                Optional extras for themes and list order. Most sites can leave these alone.
                                            </p>
                                            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                                <div class="flex flex-col gap-1.5">
                                                    <label class="pen-label">Role <span class="font-normal normal-case tracking-normal text-forge-mid">(label, not permissions)</span></label>
                                                    <input type="text"
                                                           x-model="authorForm.role"
                                                           class="pen-input"
                                                           placeholder="e.g. Editor"
                                                           autocomplete="off">
                                                </div>
                                                <div class="flex flex-col gap-1.5">
                                                    <label class="pen-label">Sort order</label>
                                                    <input type="number"
                                                           x-model.number="authorForm.sort_order"
                                                           class="pen-input font-mono"
                                                           step="1">
                                                    <p class="text-[10px] text-forge-mid">Lower numbers appear first in lists and as the default sidebar author.</p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="flex items-center justify-end gap-3 pt-2 border-t border-border">
                            <button type="button"
                                    @click="cancelAuthorForm()"
                                    class="pen-btn border border-forge-black"
                                    :disabled="savingAuthor">
                                Cancel
                            </button>
                            <button type="button"
                                    @click="saveAuthor()"
                                    :disabled="savingAuthor"
                                    class="pen-btn pen-btn-primary flex items-center gap-2">
                                <svg x-show="savingAuthor" class="animate-spin h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24">
                                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                                <span x-text="savingAuthor ? 'Saving...' : 'Save Author'"></span>
                            </button>
                        </div>
                    </div>

                    <!-- Author list -->
                    <div class="space-y-3">
                        <template x-if="authors.length === 0 && !showAuthorForm">
                            <div class="border-2 border-dashed border-border bg-canvas/60 p-8 text-center">
                                <p class="font-sans font-black uppercase text-xs tracking-wider text-forge-mid mb-1">No authors yet</p>
                                <p class="text-xs text-forge-mid font-serif">Add a contributor bio for this Content site.</p>
                            </div>
                        </template>

                        <template x-for="author in authors" :key="author.slug">
                            <div class="pen-card p-4 flex flex-col sm:flex-row sm:items-center gap-4"
                                 :class="editingSlug === author.slug ? 'border-rust/60 bg-rust-wash/30' : ''">
                                <div class="w-14 h-14 rounded-full overflow-hidden bg-canvas border border-border flex-shrink-0 flex items-center justify-center">
                                    <template x-if="authorAvatarUrl(author)">
                                        <img :src="authorAvatarUrl(author)" :alt="author.name" class="w-full h-full object-cover">
                                    </template>
                                    <template x-if="!authorAvatarUrl(author)">
                                        <svg class="w-7 h-7 text-forge-mid" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                        </svg>
                                    </template>
                                </div>
                                <div class="flex-1 min-w-0">
                                    <div class="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                                        <span class="font-sans font-bold text-sm text-forge-black" x-text="author.name"></span>
                                        <span class="font-mono text-[10px] text-forge-mid" x-text="author.slug"></span>
                                        <span x-show="author.role" class="text-[10px] uppercase tracking-wider font-bold text-rust" x-text="author.role"></span>
                                    </div>
                                    <p class="text-xs text-forge-dark font-serif mt-1 line-clamp-2 whitespace-pre-line" x-text="author.bio || 'No bio'"></p>
                                </div>
                                <div class="flex items-center gap-2 flex-shrink-0">
                                    <button type="button"
                                            @click="openEditAuthor(author)"
                                            class="pen-btn text-xs">
                                        Edit
                                    </button>
                                    <button type="button"
                                            @click="openDeleteAuthor(author.slug)"
                                            class="pen-btn text-xs text-danger border-danger/40 hover:bg-danger-bg">
                                        Delete
                                    </button>
                                </div>
                            </div>
                        </template>
                    </div>

                    <!-- Delete confirm -->
                    <div x-show="deleteAuthorSlug"
                         x-cloak
                         class="fixed inset-0 z-[150] flex items-center justify-center bg-forge-black/40 p-4"
                         @keydown.escape.window="cancelDeleteAuthor()">
                        <div class="pen-card p-6 max-w-md w-full bg-card shadow-lg" @click.outside="cancelDeleteAuthor()">
                            <h3 class="font-sans font-black text-xs uppercase tracking-wider text-forge-black mb-2">Delete author?</h3>
                            <p class="text-sm font-serif text-forge-dark mb-6">
                                Remove
                                <span class="font-mono font-bold text-rust" x-text="deleteAuthorSlug"></span>
                                from this site. Avatar files for this author will also be removed.
                            </p>
                            <div class="flex justify-end gap-2">
                                <button type="button" @click="cancelDeleteAuthor()" class="pen-btn" :disabled="deletingAuthor">Cancel</button>
                                <button type="button"
                                        @click="confirmDeleteAuthor()"
                                        :disabled="deletingAuthor"
                                        class="pen-btn pen-btn-primary bg-danger border-danger hover:opacity-90">
                                    <span x-text="deletingAuthor ? 'Deleting...' : 'Delete'"></span>
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- Error / Notice Modal -->
                    <div x-show="showMessageModal"
                         x-cloak
                         class="fixed inset-0 z-[160] flex items-center justify-center bg-forge-black/80 p-4"
                         @click.self="dismissMessageModal()"
                         @keydown.escape.window="dismissMessageModal()">
                        <div class="bg-card border-4 border-border-weld p-6 max-w-md w-full text-center shadow-2xl space-y-4" @click.outside="dismissMessageModal()">
                            <div class="flex justify-center">
                                <svg x-show="modalIsError" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-12 h-12 text-danger">
                                    <rect width="256" height="256" fill="none"/>
                                    <line x1="200" y1="56" x2="56" y2="200" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                                    <line x1="200" y1="200" x2="56" y2="56" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                                    <rect x="40" y="40" width="176" height="176" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                                </svg>
                                <svg x-show="!modalIsError" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-12 h-12 text-acid">
                                    <rect width="256" height="256" fill="none"/>
                                    <polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                                    <rect x="40" y="40" width="176" height="176" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/>
                                </svg>
                            </div>
                            <h3 class="font-sans font-black uppercase text-sm tracking-wider text-forge-black" x-text="modalTitle || (modalIsError ? 'File Upload Error' : 'Notice')"></h3>
                            <p class="text-xs text-forge-dark font-serif leading-relaxed" x-text="modalMessage"></p>
                            <div class="pt-2">
                                <button type="button" @click="dismissMessageModal()" class="pen-btn pen-btn-primary px-6 py-2">OK</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>

    <!-- Footer Partial -->
    <?php include "includes/_admin-footer.php"; ?>
