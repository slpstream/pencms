<nav class="pen-nav flex items-center justify-between !pl-0">
    <div class="flex items-center gap-2">
        <!-- Brand Logo/Title -->
        <a href="admin-dashboard.php" class="pen-nav-brand flex items-center pl-3 text-steel-light no-underline">
            <img src="/admin/images/pencms-512x512.png" alt="PenCMS" title="PenCMS" class="h-7 w-auto object-contain opacity-60 invert hover:opacity-100 transition-opacity duration-200">
        </a>

        <?php
        $configIniPath = dirname(__DIR__, 4) . '/backend-python/config.ini';
        $siteName = 'PenCMS';
        require_once dirname(__DIR__, 2) . '/core/SiteRegistry.php';
        $registry = \Dossier\SiteRegistry::fromConfigPath($configIniPath);
        $activeId = isset($_COOKIE['pen_site_id']) ? strtolower(trim((string) $_COOKIE['pen_site_id'])) : '';
        if ($activeId === '' || $registry->getSite($activeId) === null) {
            $activeId = \Dossier\SiteRegistry::DEFAULT_SITE_ID;
        }
        $activeSite = $registry->getSite($activeId);
        if ($activeSite !== null) {
            $public = trim((string) ($activeSite['sitename'] ?? ''));
            $display = trim((string) ($activeSite['name'] ?? ''));
            if ($public !== '') {
                $siteName = $public;
            } elseif ($display !== '') {
                $siteName = $display;
            }
        }
        ?>
            <!-- Active Content site name → public preview (Host domain or ?site=) -->
            <div class="flex items-center gap-1.5 group select-none relative">
                <a :href="$store.app.previewUrl()"
                   target="_blank"
                   class="font-sans font-bold text-sm tracking-wide text-steel-light hover:text-rust-bright transition-colors duration-200 no-underline truncate max-w-[200px]"
                   :title="'View Site: ' + ($store.app.sitename || '<?= htmlspecialchars($siteName, ENT_QUOTES) ?>')"
                   x-text="$store.app.sitename || '<?= htmlspecialchars($siteName, ENT_QUOTES) ?>'">
                    <?= htmlspecialchars($siteName) ?>
                </a>
                <a href="admin-settings-site.php" 
                   x-show="$store.app.hasAnyCap('write:seo', 'write:authors')"
                   x-cloak
                   class="opacity-0 group-hover:opacity-100 focus:opacity-100 text-steel-muted hover:text-rust-bright p-1 transition-all duration-200"
                   title="Edit Site Settings">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"></path>
                    </svg>
                </a>
            </div>
    </div>
    
    <div class="flex items-center gap-4 px-4 text-steel-muted text-xs select-none">
        <!-- Site switcher (multisite active site) — Pro. Preview stays on Core. -->
        <div class="flex items-center gap-1.5"
             title="Active site — pages/posts for this site only">
            <label for="pen-content-site"
                   x-show="$store.app.edition === 'pro'"
                   x-cloak
                   class="text-[10px] uppercase tracking-wider text-steel-muted font-sans whitespace-nowrap">
                Site
            </label>
            <select id="pen-content-site"
                    x-show="$store.app.edition === 'pro'"
                    x-cloak
                    class="bg-nav border border-border-chassis text-steel-light text-xs font-sans rounded-minimal px-2 py-1 max-w-[160px] focus:outline-none focus:border-rust"
                    :value="$store.app.activeSiteId"
                    @change="$store.app.setActiveSite($event.target.value)">
                <template x-for="s in $store.app.sites" :key="s.id">
                    <option :value="s.id"
                            :selected="s.id === $store.app.activeSiteId"
                            x-text="s.name ? (s.id + ' — ' + s.name) : s.id"></option>
                </template>
            </select>
            <a href="admin-settings-sites.php"
               x-show="$store.app.edition === 'pro' && $store.app.hasCap('manage:sites')"
               x-cloak
               class="h-6 w-6 border border-border-chassis hover:border-rust text-steel-light hover:text-rust-bright bg-nav rounded-minimal flex items-center justify-center transition-colors duration-200 no-underline"
               title="Create New Site">
                <svg class="w-3.5 h-3.5" viewBox="0 0 256 256">
                    <rect width="256" height="256" fill="none"/>
                    <line x1="128" y1="40" x2="128" y2="216" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                    <line x1="40" y1="128" x2="216" y2="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                </svg>
            </a>
            <a :href="$store.app.previewUrl()"
               target="_blank"
               rel="noopener"
               class="h-6 w-6 border border-border-chassis hover:border-rust text-steel-light hover:text-rust-bright bg-nav rounded-minimal flex items-center justify-center transition-colors duration-200 no-underline"
               title="Preview Site">
                <svg class="w-3.5 h-3.5" viewBox="0 0 256 256">
                    <rect width="256" height="256" fill="none"/>
                    <line x1="136" y1="120" x2="216" y2="40" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                    <polyline points="216 104 215.99 40.01 152 40" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                    <path d="M184,140v68a8,8,0,0,1-8,8H48a8,8,0,0,1-8-8V80a8,8,0,0,1,8-8h68" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                </svg>
            </a>
            <button type="button"
                    @click="window.AUTH.logout()"
                    class="h-6 w-6 border border-border-chassis hover:border-rust text-steel-light hover:text-rust-bright bg-nav rounded-minimal flex items-center justify-center transition-colors duration-200 cursor-pointer focus:outline-none"
                    title="Sign Out">
                <svg class="w-3.5 h-3.5" viewBox="0 0 256 256">
                    <rect width="256" height="256" fill="none"/>
                    <polyline points="112 40 48 40 48 216 112 216" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                    <line x1="112" y1="128" x2="224" y2="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                    <polyline points="184 88 224 128 184 168" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                </svg>
            </button>
        </div>
    </div>
</nav>
<div x-show="$store.app.mustChangePassword" x-cloak
     class="px-4 py-3 bg-warning-bg border-b border-warning border-l-4 border-l-rust">
    <div class="max-w-5xl mx-auto flex flex-col md:flex-row md:items-end gap-3">
        <div class="flex-1 min-w-0">
            <p class="text-[10px] font-sans font-black uppercase tracking-wider text-forge-black mb-1">
                Password change required
            </p>
            <p class="text-[11px] text-forge-dark font-serif leading-relaxed">
                You must change your password before using the editor. Other admin actions stay locked until you do.
            </p>
            <p x-show="$store.app.changePasswordError" class="text-[11px] text-danger font-sans mt-1"
               x-text="$store.app.changePasswordError"></p>
        </div>
        <form class="flex flex-wrap items-end gap-2" @submit.prevent="$store.app.submitChangePassword()">
            <div>
                <label class="pen-label !mb-0.5" for="pen-must-change-current">Current</label>
                <input id="pen-must-change-current" type="password" autocomplete="current-password"
                       class="pen-input text-xs min-w-[10rem]"
                       x-model="$store.app.changePasswordCurrent">
            </div>
            <div>
                <label class="pen-label !mb-0.5" for="pen-must-change-new">New</label>
                <input id="pen-must-change-new" type="password" autocomplete="new-password"
                       class="pen-input text-xs min-w-[10rem]"
                       x-model="$store.app.changePasswordNew">
            </div>
            <button type="submit" class="pen-btn pen-btn-primary pen-btn-sm"
                    :disabled="$store.app.changingPassword">
                <span x-text="$store.app.changingPassword ? 'Saving…' : 'Change password'"></span>
            </button>
        </form>
    </div>
</div>

