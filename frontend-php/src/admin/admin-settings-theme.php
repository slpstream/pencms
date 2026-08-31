<?php
$pageTitle = "Theme Settings (PenCMS)";
$currentSection = "themes";
$pageScript = "settings-theme.js";
include "includes/_admin-auth.php";

$configPath = dirname(__DIR__, 3) . '/backend-python/config.ini';
if (!file_exists($configPath)) {
    die("config.ini not found");
}

$cfg = parse_ini_file($configPath, true);
$themesDir = $cfg["theme"]["directory"] ?? "../frontend-php/src/blog/themes";
$installTheme = $cfg["theme"]["active"] ?? "starter";
$themesRoot = dirname($configPath) . "/" . $themesDir;
if (!is_dir($themesRoot)) {
    $themesRoot = __DIR__ . "/../blog/themes";
}

// Scan available themes in PHP to build the initial list
$availableThemes = [];
if (is_dir($themesRoot)) {
    $dirs = scandir($themesRoot);
    foreach ($dirs as $dir) {
        if ($dir === "." || $dir === ".." || str_starts_with($dir, "_") || $dir === "custom") {
            continue;
        }
        $themePath = $themesRoot . "/" . $dir;
        if (is_dir($themePath) && file_exists($themePath . "/theme.json")) {
            $jsonContent = file_get_contents($themePath . "/theme.json");
            $themeData = json_decode($jsonContent, true);
            if ($themeData) {
                $availableThemes[$dir] = [
                        "slug" => $dir,
                        "name" => $themeData["name"] ?? $dir,
                        "version" => $themeData["version"] ?? "1.0.0",
                        "author" => $themeData["author"] ?? "Unknown",
                        "description" =>
                            $themeData["description"] ?? "No description provided.",
                        "color_mode" => $themeData["color_mode"] ?? "both",
                        "supports" => $themeData["supports"] ?? [],
                        "has_screenshot" => file_exists($themePath . "/screenshot.webp"),
                    ];
            }
        }
    }
}

// Style Settings font previews need the shared registry @font-face sheet.
$penLoadFontRegistry = true;
include "includes/_admin-head.php";
?>

<body class="bg-canvas text-forge-black font-sans antialiased h-screen flex flex-col overflow-hidden"
      x-data="settingsTheme">

    <!-- Bootstrap theme init data for Alpine.js -->
    <script>
        window.__PEN_THEME_INIT__ = {
            installTheme: <?= json_encode($installTheme, JSON_HEX_TAG | JSON_HEX_APOS) ?>,
            themes: <?= json_encode(array_values($availableThemes), JSON_HEX_TAG | JSON_HEX_APOS) ?>,
            themesWithScreenshot: <?= json_encode(
                array_values(array_keys(array_filter(
                    $availableThemes,
                    static fn ($t) => !empty($t['has_screenshot'])
                ))),
                JSON_HEX_TAG | JSON_HEX_APOS
            ) ?>
        };
    </script>

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
                        Theme Settings
                    </h1>
                    <p class="text-forge-dark font-serif text-sm">
                        Manage the look of
                        <span class="font-mono font-bold text-rust" x-text="$store.app.activeSiteId"></span>
                        by selecting, importing, or styling themes.
                        <span class="text-forge-mid" x-show="!siteTheme" x-cloak>
                            (using install default
                            <span class="font-mono" x-text="installTheme"></span>
                            — choose a theme to set a site override)
                        </span>
                    </p>
                </div>
                <div class="flex-shrink-0">
                    <button type="button"
                            @click="customizeActiveTheme()"
                            :disabled="forking || deletingCustom"
                            class="px-5 py-2.5 bg-rust hover:bg-rust-dark text-white font-sans font-bold text-xs uppercase tracking-wider transition-colors shadow-sm flex items-center gap-2 border border-rust">
                        <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15"/></svg>
                        <span x-text="forking ? 'Creating…' : 'Customize'"></span>
                    </button>
                </div>
            </div>

            <!-- Alert Banners via Alpine -->
            <div x-show="message" x-cloak x-transition class="mb-8 p-4 flex items-center justify-between gap-3 pen-card"
                 :class="isError ? 'bg-danger-bg border-danger text-danger' : 'bg-acid-wash border-l-4 border-acid-deep text-acid-text'">
                <div class="flex items-center space-x-3 min-w-0">
                    <span x-show="!isError" class="text-xl w-6 h-6 text-acid flex-shrink-0"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-6 h-6"><rect width="256" height="256" fill="none"/><polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><rect x="40" y="40" width="176" height="176" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg></span>
                    <span x-show="isError" x-text="'❌'" class="text-xl text-danger flex-shrink-0"></span>
                    <span x-html="message" class="text-xs font-bold uppercase tracking-label"></span>
                </div>
                <button type="button"
                        @click="clearMessage()"
                        title="Dismiss"
                        aria-label="Dismiss"
                        class="p-1 text-current opacity-60 hover:opacity-100 transition-opacity flex-shrink-0 cursor-pointer">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            </div>

            <!-- Loading Spinner -->
            <div x-show="loading" class="py-20 text-center flex flex-col items-center justify-center gap-3">
                <div class="w-10 h-10 border-4 border-rust border-t-transparent rounded-full animate-spin"></div>
                <p class="text-xs text-forge-mid font-mono uppercase tracking-wider">Loading theme settings…</p>
            </div>

            <!-- Workspace Tabs -->
            <template x-if="!loading">
                <div class="flex flex-col h-full">
                <!-- Navigation Subtabs -->
                <div class="flex border-b border-border mb-8 gap-1">
                    <button @click="setTab('installed')"
                            class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                            :class="activeTab === 'installed' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                        Installed Themes
                    </button>
<?php include "includes/theme-package-tabs.php"; ?>
                    <button @click="setTab('style')"
                            class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                            :class="activeTab === 'style' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                        Style Settings
                    </button>
                </div>


                <!-- ═══════════════════════════════════════════════════════
                     TAB 1: INSTALLED THEMES
                     ═══════════════════════════════════════════════════════ -->
                <div x-show="activeTab === 'installed'" class="space-y-8"
                     :class="savingTheme || forking || deletingCustom ? 'opacity-60 pointer-events-none' : ''">

                    <!-- ── Active Theme Lead Card ────────────────────── -->
                    <div>
                        <div class="pb-3 mb-6 border-b border-border/40">
                            <h3 class="text-xl font-bold uppercase tracking-tight text-primary">Active Theme</h3>
                            <p class="text-sm text-forge-dark font-serif mt-1">
                                The theme currently rendering content for
                                <span class="font-mono font-bold text-rust" x-text="$store.app.activeSiteId"></span>.
                            </p>
                        </div>

                        <template x-for="theme in installedThemes" :key="'active-' + theme.slug">
                        <div x-show="activeTheme === theme.slug" x-cloak
                             class="pen-card p-0 overflow-hidden bg-card border-rust shadow-md max-w-[760px]">
                            <div class="flex flex-col md:flex-row h-full">
                                <div class="md:w-1/2 flex-shrink-0 bg-forge-dark/[0.03] aspect-[16/10] md:aspect-auto relative overflow-hidden border-b md:border-b-0 md:border-r border-border/40"
                                     :class="theme.has_screenshot ? 'cursor-zoom-in' : ''"
                                     @mouseenter="showThemeShotPreview(theme)"
                                     @mouseleave="hideShotPreview()">
                                    <img :src="screenshotUrl(theme.slug, theme.has_screenshot)"
                                         :alt="theme.name + ' preview'"
                                         class="w-full h-full object-cover"
                                         onerror="this.src='/admin/images/theme-no-screenshot.svg'"
                                         loading="lazy">
                                    <!-- Floating Badges (Top-Left Flush) -->
                                    <div class="absolute top-2.5 left-0 pointer-events-none flex flex-col gap-1 items-start">
                                        <span class="inline-flex items-center text-[9px] px-2.5 py-0.5 font-bold uppercase tracking-wider bg-acid text-acid-ink backdrop-blur-md border border-acid-ink/10 border-l-0 shadow-sm">
                                            Active
                                        </span>
                                        <span x-show="theme.color_mode === 'light'" x-cloak class="inline-flex items-center gap-1 text-[9px] px-2.5 py-0.5 font-bold uppercase tracking-wider bg-forge-black/80 text-amber-300 backdrop-blur-md border border-white/15 border-l-0 shadow-sm">
                                            <svg class="w-2.5 h-2.5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><circle cx="12" cy="12" r="4"/><path stroke-linecap="round" d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41m11.32-11.32l1.41-1.41"/></svg>
                                            Light
                                        </span>
                                        <span x-show="theme.color_mode === 'dark'" x-cloak class="inline-flex items-center gap-1 text-[9px] px-2.5 py-0.5 font-bold uppercase tracking-wider bg-forge-black/80 text-indigo-300 backdrop-blur-md border border-white/15 border-l-0 shadow-sm">
                                            <svg class="w-2.5 h-2.5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>
                                            Dark
                                        </span>
                                        <span x-show="theme.color_mode !== 'light' && theme.color_mode !== 'dark'" x-cloak class="inline-flex items-center gap-1 text-[9px] px-2.5 py-0.5 font-bold uppercase tracking-wider bg-forge-black/80 text-teal-300 backdrop-blur-md border border-white/15 border-l-0 shadow-sm">
                                            <svg class="w-2.5 h-2.5 text-teal-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><circle cx="12" cy="12" r="9"/><path fill="currentColor" stroke-none" d="M12 3a9 9 0 0 1 0 18V3z"/></svg>
                                            Light & Dark
                                        </span>
                                    </div>
                                </div>
                                <div class="md:w-1/2 p-6 flex flex-col justify-between">
                                    <div>
                                        <h3 class="text-2xl font-bold font-sans uppercase tracking-tight text-rust mb-2" x-text="theme.name"></h3>
                                        <p class="text-xs text-forge-dark font-serif leading-relaxed mb-4" x-text="theme.description"></p>
                                    </div>
                                    <div class="border-t border-border/30 pt-3 mt-auto flex items-center gap-4 text-xs font-sans">
                                        <button type="button"
                                                class="px-2.5 py-1.5 text-forge-mid hover:text-rust hover:border-rust/40 border border-border bg-card transition-colors flex items-center justify-center disabled:opacity-50"
                                                title="Download Zip"
                                                :disabled="downloadingThemeSlug === theme.slug"
                                                @click.stop="downloadInstalledTheme(theme.slug)"
                                                x-show="$store.app.hasCap('write:theme')" x-cloak>
                                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><g transform="rotate(180 12 12)"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/></g></svg>
                                        </button>
                                        <span class="text-forge-mid ml-auto">
                                            <span class="uppercase tracking-label font-bold text-[10px]">Author:</span>
                                            <span class="text-primary font-bold ml-1" x-text="theme.author"></span>
                                        </span>
                                        <span class="text-forge-mid">
                                            <span class="uppercase tracking-label font-bold text-[10px]">Version:</span>
                                            <span class="text-primary font-mono ml-1" x-text="theme.version"></span>
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>
                        </template>

                        <!-- Active Theme Lead: Custom theme -->
                        <div x-show="activeTheme === 'custom'" x-cloak
                             class="pen-card p-0 overflow-hidden bg-card border-rust shadow-md max-w-[760px]">
                            <div class="flex flex-col md:flex-row h-full">
                                <div class="md:w-1/2 flex-shrink-0 bg-forge-dark/[0.03] aspect-[16/10] md:aspect-auto relative overflow-hidden border-b md:border-b-0 md:border-r border-border/40"
                                     :class="customParentShotUrl() ? 'cursor-zoom-in' : ''"
                                     @mouseenter="showCustomShotPreview()"
                                     @mouseleave="hideShotPreview()">
                                    <template x-if="customParentShotUrl()">
                                        <img :src="customParentShotUrl()"
                                             :alt="(customLabel || 'Custom') + ' preview'"
                                             class="w-full h-full object-cover opacity-50 saturate-50 brightness-[0.97]"
                                             @error="$el.style.display='none'"
                                             loading="lazy">
                                    </template>
                                    <template x-if="!customParentShotUrl()">
                                        <img src="/admin/images/theme-no-screenshot.svg"
                                             alt="Custom theme preview"
                                             class="w-full h-full object-cover"
                                             loading="lazy">
                                    </template>
                                    <!-- Floating Active Badge (Top-Left Flush) -->
                                    <div class="absolute top-2.5 left-0 pointer-events-none">
                                        <span class="inline-flex items-center text-[9px] px-2.5 py-0.5 font-bold uppercase tracking-wider bg-acid text-acid-ink backdrop-blur-md border border-acid-ink/10 border-l-0 shadow-sm">
                                            Active
                                        </span>
                                    </div>
                                </div>
                                <div class="md:w-1/2 p-6 flex flex-col justify-between">
                                    <div>
                                        <div class="flex items-center gap-2 flex-wrap mb-2">
                                            <h3 class="text-2xl font-bold font-sans uppercase tracking-tight text-rust"
                                                x-text="customLabel"></h3>
                                            <span class="text-[10px] px-2 py-0.5 font-bold uppercase tracking-wider rounded bg-rust/10 text-rust border border-rust/20">Custom</span>
                                        </div>
                                        <p class="text-xs text-forge-dark font-serif mb-4 leading-relaxed">
                                            Site-private custom theme.
                                            <span x-show="customParent" x-cloak>
                                                Based on <span class="font-mono font-bold" x-text="customParent"></span>.
                                            </span>
                                        </p>
                                    </div>
                                    <div class="border-t border-border/30 pt-3 mt-auto flex flex-wrap items-center gap-3 text-xs font-sans">
                                        <button type="button"
                                                class="px-2.5 py-1.5 text-forge-mid hover:text-rust hover:border-rust/40 border border-border bg-card transition-colors flex items-center justify-center disabled:opacity-50"
                                                title="Download Zip"
                                                :disabled="downloadingThemeSlug === 'custom'"
                                                @click.stop="downloadInstalledTheme('custom')"
                                                x-show="$store.app.hasCap('write:theme')" x-cloak>
                                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><g transform="rotate(180 12 12)"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/></g></svg>
                                        </button>
                                        <button type="button"
                                                class="text-rust font-bold uppercase tracking-label hover:underline"
                                                @click.stop="setTab('export')"
                                                x-show="$store.app.hasCap('write:theme')" x-cloak>
                                            Export as base
                                        </button>
                                        <button type="button"
                                                class="px-2.5 py-1.5 text-danger hover:text-danger-dark hover:border-danger/40 border border-border bg-card transition-colors flex items-center justify-center disabled:opacity-50 ml-auto"
                                                title="Delete Custom Theme"
                                                :disabled="deletingCustom"
                                                @click.stop.prevent="deleteCustom()">
                                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- ── Custom Theme Section (always visible when exists) ── -->
                    <div x-show="customExists && activeTheme !== 'custom'" x-cloak>
                        <div class="pb-3 mb-4 border-b border-border/40">
                            <h3 class="text-lg font-bold uppercase tracking-tight text-primary">Custom Theme</h3>
                        </div>

                        <div class="flex flex-wrap gap-6">
                            <div class="pen-card p-0 overflow-hidden bg-card border-border hover:border-rust/40 hover:shadow-sm transition-all duration-200 cursor-pointer group flex flex-col w-[280px]"
                                 @click="setTheme('custom')">
                                <!-- Thumbnail: muted parent shot -->
                                <div class="aspect-[16/10] bg-forge-dark/[0.03] overflow-hidden relative border-b border-border/40"
                                     :class="customParentShotUrl() ? 'cursor-zoom-in' : ''"
                                     @mouseenter="showCustomShotPreview()"
                                     @mouseleave="hideShotPreview()">
                                    <template x-if="customParentShotUrl()">
                                        <img :src="customParentShotUrl()"
                                             :alt="(customLabel || 'Custom') + ' preview'"
                                             class="w-full h-full object-cover opacity-50 saturate-50 brightness-[0.97] group-hover:scale-[1.02] transition-transform duration-300"
                                             @error="$el.style.display='none'"
                                             loading="lazy">
                                    </template>
                                    <template x-if="!customParentShotUrl()">
                                        <img src="/admin/images/theme-no-screenshot.svg"
                                             alt="Custom theme preview"
                                             class="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-300"
                                             loading="lazy">
                                    </template>
                                    <div class="absolute top-2.5 left-0 pointer-events-none">
                                        <span class="inline-flex items-center text-[9px] px-2.5 py-0.5 font-bold uppercase tracking-wider bg-rust/90 text-white backdrop-blur-md border border-white/20 border-l-0 shadow-sm">
                                            Custom
                                        </span>
                                    </div>
                                </div>
                                <!-- Info -->
                                <div class="p-4 flex-1 flex flex-col justify-between">
                                    <div>
                                        <h4 class="text-sm font-bold font-sans uppercase tracking-tight text-primary group-hover:text-rust transition-colors mb-1.5"
                                            x-text="customLabel"></h4>
                                        <p class="text-[11px] text-forge-dark font-serif leading-relaxed line-clamp-2">
                                            Site-private custom theme.
                                            <span x-show="customParent" x-cloak>
                                                Based on <span class="font-mono font-bold" x-text="customParent"></span>.
                                            </span>
                                        </p>
                                    </div>
                                    <div class="mt-3 pt-3 border-t border-border/30 flex items-center gap-2" @click.stop>
                                        <button type="button"
                                                class="px-2.5 py-1.5 text-forge-mid hover:text-rust hover:bg-rust-wash hover:border-rust/40 border border-border/80 bg-canvas/40 transition-colors flex items-center justify-center disabled:opacity-50"
                                                title="Download Zip"
                                                :disabled="downloadingThemeSlug === 'custom'"
                                                @click="downloadInstalledTheme('custom')"
                                                x-show="$store.app.hasCap('write:theme')" x-cloak>
                                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><g transform="rotate(180 12 12)"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/></g></svg>
                                        </button>
                                        <button type="button"
                                                class="px-2.5 py-1.5 text-danger hover:text-danger hover:bg-danger-bg hover:border-danger/40 border border-border/80 bg-canvas/40 transition-colors flex items-center justify-center disabled:opacity-50"
                                                title="Delete Custom Theme"
                                                :disabled="deletingCustom"
                                                @click.stop.prevent="deleteCustom()">
                                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                                        </button>
                                        <button type="button"
                                                class="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider bg-rust hover:bg-rust-dark text-white border border-rust shadow-sm transition-colors flex-1"
                                                @click="setTheme('custom')">
                                            Activate
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- ── + Create Custom CTA (when no custom exists) ──── -->
                    <div x-show="!customExists" x-cloak
                         class="pen-card p-5 bg-card border-border flex flex-wrap items-center justify-between gap-4 max-w-[760px]">
                        <div>
                            <h4 class="text-sm font-bold uppercase tracking-wider text-primary mb-1">Create a Custom Theme</h4>
                            <p class="text-xs text-forge-dark font-serif leading-relaxed max-w-xl">
                                Create a site-private custom theme based on the currently active theme.
                                The original theme stays untouched — switching back later won't delete your custom version.
                            </p>
                        </div>
                        <button type="button"
                                class="px-4 py-2 text-xs font-bold uppercase tracking-label border-2 border-rust text-rust hover:bg-rust-wash transition-colors disabled:opacity-50 flex items-center gap-1.5"
                                :disabled="forking || savingTheme"
                                @click="createCustom()">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15"/></svg>
                            <span x-text="forking ? 'Creating…' : 'Create Custom'"></span>
                        </button>
                    </div>

                    <!-- ── Available Themes Grid ─────────────────────── -->
                    <div>
                        <div class="pb-3 mb-6 border-b border-border/40">
                            <h3 class="text-lg font-bold uppercase tracking-tight text-primary">Available Themes</h3>
                            <p class="text-xs text-forge-mid font-serif mt-1">
                                <span x-text="installedThemes.length"></span> themes installed. Click a theme to activate it.
                            </p>
                        </div>

                        <div class="flex flex-wrap gap-6">
                            <template x-for="theme in installedThemes" :key="'grid-' + theme.slug">
                            <div x-show="activeTheme !== theme.slug"
                                 x-cloak
                                 class="pen-card p-0 overflow-hidden bg-card border-border hover:border-rust/40 hover:shadow-sm transition-all duration-200 cursor-pointer group flex flex-col w-[280px]"
                                 @click="setTheme(theme.slug)">
                                <div class="aspect-[16/10] bg-forge-dark/[0.03] overflow-hidden relative border-b border-border/40"
                                     :class="theme.has_screenshot ? 'cursor-zoom-in' : ''"
                                     @mouseenter="showThemeShotPreview(theme)"
                                     @mouseleave="hideShotPreview()">
                                    <img :src="screenshotUrl(theme.slug, theme.has_screenshot)"
                                         :alt="theme.name + ' preview'"
                                         class="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-300"
                                         onerror="this.src='/admin/images/theme-no-screenshot.svg'"
                                         loading="lazy">
                                    <!-- Floating Mode Badge (Top-Left Flush) -->
                                    <div class="absolute top-2.5 left-0 pointer-events-none">
                                        <span x-show="theme.color_mode === 'light'" x-cloak class="inline-flex items-center gap-1 text-[9px] px-2.5 py-0.5 font-bold uppercase tracking-wider bg-forge-black/80 text-amber-300 backdrop-blur-md border border-white/15 border-l-0 shadow-sm">
                                            <svg class="w-2.5 h-2.5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><circle cx="12" cy="12" r="4"/><path stroke-linecap="round" d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32l1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41m11.32-11.32l1.41-1.41"/></svg>
                                            Light
                                        </span>
                                        <span x-show="theme.color_mode === 'dark'" x-cloak class="inline-flex items-center gap-1 text-[9px] px-2.5 py-0.5 font-bold uppercase tracking-wider bg-forge-black/80 text-indigo-300 backdrop-blur-md border border-white/15 border-l-0 shadow-sm">
                                            <svg class="w-2.5 h-2.5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>
                                            Dark
                                        </span>
                                        <span x-show="theme.color_mode !== 'light' && theme.color_mode !== 'dark'" x-cloak class="inline-flex items-center gap-1 text-[9px] px-2.5 py-0.5 font-bold uppercase tracking-wider bg-forge-black/80 text-teal-300 backdrop-blur-md border border-white/15 border-l-0 shadow-sm">
                                            <svg class="w-2.5 h-2.5 text-teal-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><circle cx="12" cy="12" r="9"/><path fill="currentColor" stroke-none" d="M12 3a9 9 0 0 1 0 18V3z"/></svg>
                                            Light & Dark
                                        </span>
                                    </div>
                                </div>
                                <div class="p-4 flex-1 flex flex-col justify-between">
                                    <div>
                                        <h4 class="text-sm font-bold font-sans uppercase tracking-tight text-primary group-hover:text-rust transition-colors mb-1.5" x-text="theme.name"></h4>
                                        <p class="text-[11px] text-forge-dark font-serif leading-relaxed line-clamp-2" x-text="theme.description"></p>
                                    </div>
                                    <div class="mt-3 pt-3 border-t border-border/30 flex items-center gap-2" @click.stop>
                                        <button type="button"
                                                class="px-2.5 py-1.5 text-forge-mid hover:text-rust hover:bg-rust-wash hover:border-rust/40 border border-border/80 bg-canvas/40 transition-colors flex items-center justify-center disabled:opacity-50"
                                                title="Download Zip"
                                                :disabled="downloadingThemeSlug === theme.slug"
                                                @click="downloadInstalledTheme(theme.slug)"
                                                x-show="$store.app.hasCap('write:theme')" x-cloak>
                                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><g transform="rotate(180 12 12)"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/></g></svg>
                                        </button>
                                        <button type="button"
                                                class="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider bg-rust hover:bg-rust-dark text-white border border-rust shadow-sm transition-colors flex-1"
                                                @click="setTheme(theme.slug)">
                                            Activate
                                        </button>
                                    </div>
                                </div>
                            </div>
                            </template>
                        </div>
                    </div>

                  <br>

                </div>


<?php include "includes/theme-package-panels.php"; ?>

                <!-- ═══════════════════════════════════════════════════════
                     TAB 3: STYLE SETTINGS
                     ═══════════════════════════════════════════════════════ -->
                <div x-show="activeTab === 'style'" class="space-y-8 max-w-4xl">
                    <p class="text-xs text-forge-dark font-serif leading-relaxed -mt-2">
                        Quick visual overrides for the active theme. Changes here apply to
                        <span class="font-mono font-bold text-rust" x-text="$store.app.activeSiteId"></span>
                        only and do not modify the base theme files.
                    </p>

                    <!-- Style Loading -->
                    <div x-show="styleLoading" class="py-12 text-center flex flex-col items-center justify-center gap-3">
                        <div class="w-8 h-8 border-4 border-rust border-t-transparent rounded-full animate-spin"></div>
                        <p class="text-xs text-forge-mid font-mono uppercase tracking-wider">Loading style settings…</p>
                    </div>

                    <!-- Load Error -->
                    <div x-show="!styleLoading && styleLoadError" x-cloak
                         class="pen-card p-4 bg-card border border-danger/30 text-danger">
                        <p class="text-xs font-bold uppercase tracking-wider" x-text="styleLoadError"></p>
                    </div>

                    <!-- Empty State -->
                    <div x-show="!styleLoading && !styleLoadError && styleSchema === null" x-cloak
                         class="pen-card p-8 bg-card border-border">
                        <div class="flex items-start gap-4">
                            <div class="w-10 h-10 rounded-full bg-rust/10 flex items-center justify-center flex-shrink-0">
                                <svg class="w-5 h-5 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z"/>
                                </svg>
                            </div>
                            <div>
                                <h3 class="text-sm font-bold uppercase tracking-wider text-primary mb-1">No Style Settings for This Theme</h3>
                                <p class="text-xs text-forge-dark font-serif leading-relaxed">
                                    The active theme does not expose adjustable style variables.
                                    Use <a href="admin-customize.php" class="text-rust hover:underline">Customize</a>
                                    to edit theme files directly.
                                </p>
                            </div>
                        </div>
                    </div>

                    <!-- Stale Theme Notice -->
                    <div x-show="!styleLoading && styleSchema !== null && styleSavedForTheme && styleSavedForTheme !== activeTheme"
                         x-cloak
                         class="pen-card p-4 bg-card border border-amber-500/30 text-amber-700">
                        <p class="text-xs font-bold uppercase tracking-wider">
                            Style overrides were saved for theme
                            <span class="font-mono" x-text="styleSavedForTheme"></span>.
                            Switch back to that theme to apply them, or create new overrides here.
                        </p>
                    </div>

                    <!-- Dynamic Schema Groups -->
                    <template x-if="!styleLoading && styleSchema !== null">
                        <div class="space-y-8">
                            <template x-for="group in styleSchema.groups" :key="group.id">
                                <div class="pen-card p-6 bg-card">
                                    <div class="flex items-center gap-2 border-b border-border pb-3 mb-5">
                                        <svg class="w-4 h-4 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                                            <path stroke-linecap="round" stroke-linejoin="round" d="M4.098 19.902a3.75 3.75 0 005.304 0l6.401-6.402M6.75 21A3.75 3.75 0 013 17.25V4.125C3 3.504 3.504 3 4.125 3h5.25c.621 0 1.125.504 1.125 1.125v4.072M6.75 21a3.75 3.75 0 003.75-3.75V8.197M6.75 21h13.125c.621 0 1.125-.504 1.125-1.125v-5.25c0-.621-.504-1.125-1.125-1.125h-4.072" />
                                        </svg>
                                        <h3 class="text-xs font-black uppercase tracking-wider text-forge-black" x-text="group.label || group.id"></h3>
                                    </div>

                                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                        <template x-for="field in group.fields" :key="field.id">
                                            <div class="space-y-1.5">
                                                <div class="flex items-center justify-between gap-2">
                                                    <label class="pen-label !mb-0 text-xs" x-text="field.label"></label>
                                                    <span class="text-[10px] font-mono text-forge-mid" x-text="field.var"></span>
                                                </div>

                                                <!-- Color field -->
                                                <div x-show="field.type === 'color'" class="flex items-center gap-2">
                                                    <input type="color"
                                                           :id="'style-' + field.id"
                                                           class="w-8 h-8 border border-border rounded cursor-pointer flex-shrink-0"
                                                           :value="styleFormValues[field.id]"
                                                           @input="setStyleValue(field.id, false, $event.target.value)">
                                                    <input type="text"
                                                           class="pen-input flex-1 min-w-0 text-xs font-mono"
                                                           :value="styleFormValues[field.id]"
                                                           @input="setStyleValue(field.id, false, $event.target.value)">
                                                    <template x-if="styleHasDark && 'dark_default' in field">
                                                        <div class="flex items-center gap-2 ml-1 pl-2 border-l border-border">
                                                            <span class="text-[10px] uppercase tracking-wider text-forge-mid">Dark</span>
                                                            <input type="color"
                                                                   :id="'style-dark-' + field.id"
                                                                   class="w-8 h-8 border border-border rounded cursor-pointer flex-shrink-0"
                                                                   :value="styleFormDarkValues[field.id]"
                                                                   @input="setStyleValue(field.id, true, $event.target.value)">
                                                        </div>
                                                    </template>
                                                </div>

                                                <!-- Select field -->
                                                <!-- :selected per option, not :value on the select: the select's
                                                     binding would run before x-for has rendered any options,
                                                     and Alpine never re-applies it once they exist. -->
                                                <div x-show="field.type === 'select' && !isFontSelectField(field)">
                                                    <select :id="'style-' + field.id"
                                                            class="pen-input w-full bg-canvas text-xs"
                                                            @change="setStyleValue(field.id, false, $event.target.value)">
                                                        <template x-for="opt in field.options" :key="opt.value">
                                                            <option :value="opt.value"
                                                                    :selected="opt.value === styleFormValues[field.id]"
                                                                    x-text="opt.label"></option>
                                                        </template>
                                                    </select>
                                                </div>

                                                <!-- Font select: custom listbox so each option renders in its stack -->
                                                <div x-show="field.type === 'select' && isFontSelectField(field)"
                                                     class="relative"
                                                     @click.outside="closeStyleFontDropdown(field.id)"
                                                     @keydown="onStyleFontListKeydown(field, $event)">
                                                    <button type="button"
                                                            :id="'style-' + field.id"
                                                            class="pen-input w-full bg-canvas text-xs text-left flex items-center justify-between gap-2 cursor-pointer"
                                                            :aria-expanded="!!styleFontDropdownOpen[field.id]"
                                                            aria-haspopup="listbox"
                                                            @click="toggleStyleFontDropdown(field.id)"
                                                            :style="styleFormValues[field.id] ? { fontFamily: styleFormValues[field.id] } : {}">
                                                        <span class="truncate" x-text="styleFontOptionLabel(field)"></span>
                                                        <svg class="w-3.5 h-3.5 text-steel-muted shrink-0 transition-transform duration-200"
                                                             :class="styleFontDropdownOpen[field.id] ? 'rotate-180' : ''"
                                                             fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" aria-hidden="true">
                                                            <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5"></path>
                                                        </svg>
                                                    </button>
                                                    <div x-show="styleFontDropdownOpen[field.id]"
                                                         x-transition:enter="transition ease-out duration-100"
                                                         x-transition:enter-start="transform opacity-0 scale-95"
                                                         x-transition:enter-end="transform opacity-100 scale-100"
                                                         x-transition:leave="transition ease-in duration-75"
                                                         x-transition:leave-start="transform opacity-100 scale-100"
                                                         x-transition:leave-end="transform opacity-0 scale-95"
                                                         class="absolute left-0 top-full mt-1 w-full bg-card border-2 border-border shadow-md z-50 select-none overflow-hidden"
                                                         style="display: none;"
                                                         role="listbox"
                                                         :aria-labelledby="'style-' + field.id">
                                                        <div class="max-h-60 overflow-y-auto divide-y divide-border/40 scrollbar-acid">
                                                            <template x-for="opt in field.options" :key="opt.value">
                                                                <button type="button"
                                                                        role="option"
                                                                        class="w-full text-left px-3 py-2 text-xs hover:bg-rust-wash transition-colors cursor-pointer"
                                                                        :class="opt.value === styleFormValues[field.id] ? 'bg-rust-wash text-rust' : 'text-forge-dark'"
                                                                        :aria-selected="opt.value === styleFormValues[field.id]"
                                                                        :style="opt.value ? { fontFamily: opt.value } : {}"
                                                                        @click="selectStyleFontOption(field.id, opt.value)"
                                                                        x-text="opt.label"></button>
                                                            </template>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </template>
                                    </div>
                                </div>
                            </template>

                            <!-- Actions -->
                            <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                                <div class="text-xs font-serif">
                                    <span x-show="styleDirty" class="text-rust font-bold uppercase tracking-wider">Unsaved changes</span>
                                    <span x-show="!styleDirty && styleSavedForTheme" class="text-forge-mid">Saved overrides for this theme.</span>
                                </div>
                                <div class="flex items-center gap-3">
                                    <button type="button"
                                            class="pen-btn pen-btn-secondary pen-btn-sm"
                                            :disabled="styleSaving"
                                            @click="resetStyleSettings()">
                                        Reset to defaults
                                    </button>
                                    <button type="button"
                                            class="pen-btn pen-btn-primary pen-btn-sm"
                                            :disabled="!styleDirty || styleSaving"
                                            @click="saveStyleSettings()">
                                        <span x-text="styleSaving ? 'Saving…' : 'Save Style Settings'"></span>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </template>

                    <!-- Cross-links: Explore More -->
                    <div class="pen-card p-6 bg-card">
                        <div class="flex items-center gap-2 border-b border-border pb-3 mb-5">
                            <svg class="w-4 h-4 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"/>
                            </svg>
                            <h3 class="text-xs font-black uppercase tracking-wider text-forge-black">Explore More</h3>
                        </div>
                        <p class="text-xs text-forge-dark font-serif leading-relaxed mb-4">
                            For deeper customization options, visit these related settings:
                        </p>
                        <div class="space-y-3">
                            <a href="admin-customize.php"
                               class="flex items-center gap-3 p-3 rounded border border-border hover:border-rust/40 hover:bg-black/[0.01] transition-all group">
                                <div class="w-8 h-8 rounded bg-rust/10 flex items-center justify-center flex-shrink-0">
                                    <svg class="w-4 h-4 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                                        <path stroke-linecap="round" stroke-linejoin="round" d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5"/>
                                    </svg>
                                </div>
                                <div>
                                    <p class="text-xs font-bold uppercase tracking-wider text-primary group-hover:text-rust transition-colors">Customize</p>
                                    <p class="text-[10px] text-forge-mid font-serif">Edit theme templates (Twig), CSS, and partials directly with the built-in code editor and AI assistant.</p>
                                </div>
                            </a>
                            <a href="admin-settings-navigation.php"
                               class="flex items-center gap-3 p-3 rounded border border-border hover:border-rust/40 hover:bg-black/[0.01] transition-all group">
                                <div class="w-8 h-8 rounded bg-rust/10 flex items-center justify-center flex-shrink-0">
                                    <svg class="w-4 h-4 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                                        <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"/>
                                    </svg>
                                </div>
                                <div>
                                    <p class="text-xs font-bold uppercase tracking-wider text-primary group-hover:text-rust transition-colors">Navigation</p>
                                    <p class="text-[10px] text-forge-mid font-serif">Set up navigation menus, nav bars, and link structures for your site's header and footer.</p>
                                </div>
                            </a>
                            <a href="admin-settings-structure.php"
                               class="flex items-center gap-3 p-3 rounded border border-border hover:border-rust/40 hover:bg-black/[0.01] transition-all group">
                                <div class="w-8 h-8 rounded bg-rust/10 flex items-center justify-center flex-shrink-0">
                                    <svg class="w-4 h-4 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                                        <path stroke-linecap="round" stroke-linejoin="round" d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z"/>
                                        <path stroke-linecap="round" stroke-linejoin="round" d="M6 6h.008v.008H6V6z"/>
                                    </svg>
                                </div>
                                <div>
                                    <p class="text-xs font-bold uppercase tracking-wider text-primary group-hover:text-rust transition-colors">Structure & Taxonomy</p>
                                    <p class="text-[10px] text-forge-mid font-serif">Configure categories, vocabularies, and content organization rules.</p>
                                </div>
                            </a>
                        </div>
                    </div>
                  <br>
                </div>

                </div>
            </template>
        </main>
    </div>

    <!-- Delete Custom Confirmation Modal -->
    <div x-show="confirmDeleteModalOpen" x-cloak class="pen-modal-overlay p-4" style="display:none" x-transition>
        <div class="pen-modal-danger min-w-0 w-full max-w-[480px] sm:min-w-[480px]" @click.away="confirmDeleteModalOpen = false" @keydown.escape.window="confirmDeleteModalOpen = false">
            <div class="pen-modal-header">
                <h3 class="pen-modal-title">Delete Custom Theme</h3>
                <button @click="confirmDeleteModalOpen = false" class="text-forge-mid hover:text-forge-black">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>
            <div class="pen-modal-body space-y-3">
                <p class="text-sm text-forge-black font-sans">
                    Are you sure you want to delete this site's custom theme (<strong class="font-mono text-xs bg-canvas px-1.5 py-0.5 border border-border" x-text="customLabel"></strong>)?
                </p>
                <p class="text-xs text-forge-muted font-serif leading-prose">
                    This action is immediate and cannot be undone. If Custom is active, the site will revert to the parent base theme (<strong x-text="customParent || installTheme"></strong>).
                </p>
            </div>
            <div class="pen-modal-footer">
                <button @click="confirmDeleteModalOpen = false" class="pen-btn pen-btn-secondary pen-btn-sm">Cancel</button>
                <button @click="confirmDeleteCustom()" class="pen-btn pen-btn-danger pen-btn-sm">Delete Custom Theme</button>
            </div>
        </div>
    </div>

    <!-- Create/Replace Custom Confirmation Modal -->
    <div x-show="confirmReplaceModalOpen" x-cloak class="pen-modal-overlay p-4" style="display:none" x-transition>
        <div class="pen-modal min-w-0 w-full max-w-[480px] sm:min-w-[480px]" @click.away="confirmReplaceModalOpen = false" @keydown.escape.window="confirmReplaceModalOpen = false">
            <div class="pen-modal-header">
                <h3 class="pen-modal-title">Create Custom Theme</h3>
                <button @click="confirmReplaceModalOpen = false" class="text-forge-mid hover:text-forge-black">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>
            <div class="pen-modal-body space-y-3">
                <p class="text-sm text-forge-black font-sans">
                    Create a site-private custom theme based on <strong class="font-mono text-xs bg-canvas px-1.5 py-0.5 border border-border text-rust" x-text="activeTheme"></strong>?
                </p>
                <p class="text-xs text-forge-muted font-serif leading-prose" x-show="customExists">
                    Note: This site already has a custom theme (<strong x-text="customLabel"></strong>). Creating a new custom theme will replace the existing custom theme tree.
                </p>
            </div>
            <div class="pen-modal-footer">
                <button @click="confirmReplaceModalOpen = false" class="pen-btn pen-btn-secondary pen-btn-sm">Cancel</button>
                <button @click="confirmReplaceCustom()" class="pen-btn pen-btn-primary pen-btn-sm">Create & Customize</button>
            </div>
        </div>
    </div>

<?php include "includes/theme-package-modals.php"; ?>

    <!-- Theme screenshot hover viewer (~50% size; pointer-events-none so Activate stays clickable) -->
    <div x-show="shotPreview"
         x-cloak
         x-transition:enter="transition ease-out duration-150"
         x-transition:enter-start="opacity-0"
         x-transition:enter-end="opacity-100"
         x-transition:leave="transition ease-in duration-100"
         x-transition:leave-start="opacity-100"
         x-transition:leave-end="opacity-0"
         class="fixed inset-0 z-[200] pointer-events-none flex items-center justify-center p-6 bg-forge-black/40"
         aria-hidden="true">
        <figure class="relative w-[min(640px,50vw)] max-h-[50vh] bg-card border border-border shadow-2xl overflow-hidden flex flex-col">
            <div class="relative flex-1 min-h-0 bg-forge-dark/[0.03]">
                <img :src="shotPreview?.src"
                     :alt="(shotPreview?.name || 'Theme') + ' preview'"
                     :class="shotPreview?.customized ? 'opacity-50 saturate-50 brightness-[0.97]' : ''"
                     class="block w-full max-h-[calc(50vh-2rem)] h-auto object-contain mx-auto">
                <div x-show="shotPreview?.customized"
                     class="pointer-events-none absolute inset-0 flex items-center justify-center">
                    <span class="-rotate-[28deg] select-none border-2 border-rust/75 text-rust bg-canvas/75 px-4 py-1.5 text-xs font-black uppercase tracking-[0.22em] shadow-sm">
                        CUSTOMIZED
                    </span>
                </div>
            </div>
            <figcaption class="px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-forge-mid border-t border-border/40 bg-card"
                        x-text="shotPreview?.name"></figcaption>
        </figure>
    </div>

    <script src="js/settings-theme-package.js"></script>

    <!-- Footer -->
    <?php include "includes/_admin-footer.php"; ?>
