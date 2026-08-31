<aside x-data="{ 
           sidebarCollapsed: localStorage.getItem('pen-sidebar-collapsed') === 'true',
           init() {
               const handleResize = () => {
                   if (window.innerWidth < 1024) {
                       this.sidebarCollapsed = true;
                   } else {
                       this.sidebarCollapsed = localStorage.getItem('pen-sidebar-collapsed') === 'true';
                   }
               };
               handleResize();
               window.addEventListener('resize', handleResize);
               this.$watch('sidebarCollapsed', val => {
                   if (window.innerWidth >= 1024) {
                       localStorage.setItem('pen-sidebar-collapsed', val);
                   }
               });
           }
       }" x-init="init()"
    class="pen-sidebar transition-all duration-300 scrollbar-acid flex-shrink-0 flex flex-col justify-between px-2 py-4"
    :class="sidebarCollapsed ? 'pen-sidebar-collapsed' : ''"
    :style="sidebarCollapsed ? 'width: 48px !important; padding: 1rem 0 !important;' : 'width: 180px !important; padding: 1rem 0.5rem 1rem 0 !important;'">

    <!-- Upper Scrollable Navigation Menu -->
    <div class="flex-1 min-h-0 overflow-y-auto scrollbar-acid flex flex-col gap-4 pr-1">
        <!-- Section: Content -->
        <div>
            <p class="pen-sidebar-section-label transition-opacity duration-300 select-none" x-show="!sidebarCollapsed"
                x-transition:enter="delay-100 duration-200" x-transition:leave="duration-100">Content</p>

            <hr class="border-border-chassis my-2 opacity-30" x-show="sidebarCollapsed">

            <nav>
                <ul class="list-none p-0 m-0 flex flex-col gap-0.5">
                    <li>
                        <a href="admin-dashboard.php"
                            class="pen-sidebar-link flex items-center gap-2 <?= ($currentSection ?? '') === 'dashboard' ? 'active' : '' ?>"
                            title="Dashboard">
                            <svg class="w-5 h-5 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
                                <rect width="256" height="256" fill="none" />
                                <rect x="132" y="100" width="124" height="92" rx="16"
                                    transform="translate(340 -48) rotate(90)" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
                                <line x1="112" y1="208" x2="88" y2="208" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
                                <path d="M148,168H40a16,16,0,0,1-16-16V64A16,16,0,0,1,40,48H184a16,16,0,0,1,16,16V84"
                                    fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"
                                    stroke-width="24" />
                                <line x1="188" y1="124" x2="200" y2="124" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
                            </svg>
                            <span class="truncate transition-opacity duration-300 font-sans" x-show="!sidebarCollapsed"
                                x-transition.opacity>Dashboard</span>
                        </a>
                    </li>
                    <li x-show="$store.app.hasCap('write:posts')" x-cloak>
                        <a href="admin-posts.php"
                            class="pen-sidebar-link flex items-center gap-2 <?= ($currentSection ?? '') === 'posts' ? 'active' : '' ?>"
                            title="Posts">
                            <svg class="w-5 h-5 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
                                <rect width="256" height="256" fill="none" />
                                <path
                                    d="M32,216V56a8,8,0,0,1,8-8H216a8,8,0,0,1,8,8V216l-32-16-32,16-32-16L96,216,64,200Z"
                                    fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"
                                    stroke-width="24" />
                                <line x1="148" y1="108" x2="184" y2="108" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
                                <line x1="148" y1="148" x2="184" y2="148" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
                                <rect x="72" y="96" width="40" height="64" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
                            </svg>
                            <span class="truncate transition-opacity duration-300 font-sans" x-show="!sidebarCollapsed"
                                x-transition.opacity>Posts</span>
                        </a>
                    </li>
                    <li x-show="$store.app.hasCap('write:pages')" x-cloak>
                        <a href="admin-pages.php"
                            class="pen-sidebar-link flex items-center gap-2 <?= ($currentSection ?? '') === 'pages' ? 'active' : '' ?>"
                            title="Pages">
                            <svg class="w-5 h-5 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
                                <rect width="256" height="256" fill="none" />
                                <rect x="28" y="84" width="160" height="128" rx="8" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="20" />
                                <path d="M68,84V52a8,8,0,0,1,8-8H220a8,8,0,0,1,8,8V164a8,8,0,0,1-8,8H188" fill="none"
                                    stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"
                                    stroke-width="24" />
                                <line x1="28" y1="124" x2="188" y2="124" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
                            </svg>
                            <span class="truncate transition-opacity duration-300 font-sans" x-show="!sidebarCollapsed"
                                x-transition.opacity>Pages</span>
                        </a>
                    </li>
                    <li x-show="$store.app.hasCap('write:posts')" x-cloak>
                        <a href="admin-feedback.php"
                            class="pen-sidebar-link flex items-center gap-2 <?= ($currentSection ?? '') === 'feedback' ? 'active' : '' ?>"
                            title="Feedback">
                            <svg class="w-5 h-5 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
                                <rect width="256" height="256" fill="none"/>
                                <path d="M32.5,138A72,72,0,1,1,62,167.5l-27.76,8.16a8,8,0,0,1-9.93-9.93Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="20"/>
                                <path d="M163.94,80.11A72,72,0,0,1,223.5,186l8.16,27.76a8,8,0,0,1-9.93,9.93L194,215.5A72.05,72.05,0,0,1,92.06,175.89" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="20"/>
                            </svg>
                            <span class="truncate transition-opacity duration-300 font-sans" x-show="!sidebarCollapsed"
                                x-transition.opacity>Feedback</span>
                        </a>
                    </li>
                    <li x-show="$store.app.hasCap('write:posts')" x-cloak>
                        <a href="admin-comments.php"
                            class="pen-sidebar-link flex items-center gap-2 <?= ($currentSection ?? '') === 'comments' ? 'active' : '' ?>"
                            title="Comments">
                            <svg class="w-5 h-5 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
                                <rect width="256" height="256" fill="none"/>
                                <path d="M45.15,230.11A8,8,0,0,1,32,224V64a8,8,0,0,1,8-8H216a8,8,0,0,1,8,8V192a8,8,0,0,1-8,8H80Z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="20"/>
                                <line x1="96" y1="112" x2="160" y2="112" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="20"/>
                                <line x1="96" y1="144" x2="160" y2="144" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="20"/>
                            </svg>
                            <span class="truncate transition-opacity duration-300 font-sans" x-show="!sidebarCollapsed"
                                x-transition.opacity>Comments</span>
                        </a>
                    </li>
                    <li x-show="$store.app.hasCap('write:posts')" x-cloak>
                        <a :href="$store.app.adminPath('admin-editor.php')"
                            class="pen-sidebar-link flex items-center gap-2 <?= ($currentSection ?? '') === 'editor' ? 'active' : '' ?>"
                            title="New Post">
                            <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="2"
                                viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round"
                                    d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
                            </svg>
                            <span class="truncate transition-opacity duration-300 font-sans" x-show="!sidebarCollapsed"
                                x-transition.opacity>New Post</span>
                        </a>
                    </li>
                    <li x-show="$store.app.hasCap('write:media')" x-cloak>
                        <a href="admin-media.php"
                            class="pen-sidebar-link flex items-center gap-2 <?= ($currentSection ?? '') === 'media' ? 'active' : '' ?>"
                            title="Media Library">
                            <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="2"
                                viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round"
                                    d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z">
                                </path>
                            </svg>
                            <span class="truncate transition-opacity duration-300 font-sans" x-show="!sidebarCollapsed"
                                x-transition.opacity>Media Library</span>
                        </a>
                    </li>
                    <li x-show="$store.app.hasCap('publish')" x-cloak>
                        <a href="admin-publish.php"
                            class="pen-sidebar-link flex items-center gap-2 <?= ($currentSection ?? '') === 'publish' ? 'active' : '' ?>"
                            title="Publish">
                            <svg class="w-5 h-5 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
                                <rect width="256" height="256" fill="none" />
                                <path
                                    d="M180,104h20a8,8,0,0,1,8,8v96a8,8,0,0,1-8,8H56a8,8,0,0,1-8-8V112a8,8,0,0,1,8-8H76"
                                    fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"
                                    stroke-width="24" />
                                <polyline points="88 64 128 24 168 64" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
                                <line x1="128" y1="24" x2="128" y2="136" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="24" />
                            </svg>
                            <span class="truncate transition-opacity duration-300 font-sans" x-show="!sidebarCollapsed"
                                x-transition.opacity>Publish</span>
                        </a>
                    </li>
                </ul>
            </nav>
        </div>

        <!-- Section: Settings -->
        <div>
            <p class="pen-sidebar-section-label transition-opacity duration-300 select-none" x-show="!sidebarCollapsed"
                x-transition:enter="delay-100 duration-200" x-transition:leave="duration-100">Settings</p>

            <hr class="border-border-chassis my-2 opacity-30" x-show="sidebarCollapsed">

            <nav>
                <ul class="list-none p-0 m-0 flex flex-col gap-0.5">
                    <li x-show="$store.app.edition === 'pro' && $store.app.hasCap('manage:sites')" x-cloak>
                        <a href="admin-settings-sites.php"
                            class="pen-sidebar-link flex items-center gap-2 <?= ($currentSection ?? '') === 'sites' ? 'active' : '' ?>"
                            title="Sites">
                            <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="2"
                                viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round"
                                    d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z">
                                </path>
                            </svg>
                            <span class="truncate transition-opacity duration-300 font-sans" x-show="!sidebarCollapsed"
                                x-transition.opacity>Sites</span>
                        </a>
                    </li>
                    <li x-show="$store.app.edition === 'pro' && ($store.app.isAdmin() || $store.app.hasCap('users:manage'))"
                        x-cloak>
                        <a href="admin-users.php"
                            class="pen-sidebar-link flex items-center gap-2 <?= ($currentSection ?? '') === 'users' ? 'active' : '' ?>"
                            title="Users">
                            <svg class="w-5 h-5 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
                                <rect width="256" height="256" fill="none"/>
                                <circle cx="84" cy="108" r="52" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="20"/>
                                <path d="M13,196a88,88,0,0,1,142,0" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="20"/>
                                <path d="M172,160a87.86,87.86,0,0,1,71,36" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="20"/>
                                <path d="M158.62,57.74A52,52,0,1,1,172,160" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="20"/>
                            </svg>
                            <span class="truncate transition-opacity duration-300 font-sans" x-show="!sidebarCollapsed"
                                x-transition.opacity>Users</span>
                        </a>
                    </li>
                    <li x-show="$store.app.hasAnyCap('write:seo', 'write:authors')" x-cloak>
                        <a href="admin-settings-site.php"
                            class="pen-sidebar-link flex items-center gap-2 <?= ($currentSection ?? '') === 'site-settings' ? 'active' : '' ?>"
                            title="Site Settings">
                            <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="2"
                                viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round"
                                    d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z">
                                </path>
                                <path stroke-linecap="round" stroke-linejoin="round"
                                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                            </svg>
                            <span class="truncate transition-opacity duration-300 font-sans" x-show="!sidebarCollapsed"
                                x-transition.opacity>Site Settings</span>
                        </a>
                    </li>
                    <li x-show="$store.app.hasCap('write:theme')" x-cloak>
                        <a href="admin-settings-theme.php"
                            class="pen-sidebar-link flex items-center gap-2 <?= ($currentSection ?? '') === 'themes' ? 'active' : '' ?>"
                            title="Themes">
                            <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="2"
                                viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round"
                                    d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01">
                                </path>
                            </svg>
                            <span class="truncate transition-opacity duration-300 font-sans" x-show="!sidebarCollapsed"
                                x-transition.opacity>Themes</span>
                        </a>
                    </li>
                    <li x-show="$store.app.hasCap('write:theme')" x-cloak>
                        <a href="admin-customize.php"
                            class="pen-sidebar-link flex items-center gap-2 <?= ($currentSection ?? '') === 'customize' ? 'active' : '' ?>"
                            title="Site Customization">
                            <svg class="w-5 h-5 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
                                <rect width="256" height="256" fill="none" />
                                <rect x="152" y="40" width="64" height="176" rx="8" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="20" />
                                <line x1="152" y1="88" x2="180" y2="88" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="20" />
                                <line x1="152" y1="128" x2="180" y2="128" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="20" />
                                <line x1="152" y1="168" x2="180" y2="168" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="20" />
                                <path d="M40,64,72,32l32,32V208a8,8,0,0,1-8,8H48a8,8,0,0,1-8-8Z" fill="none"
                                    stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"
                                    stroke-width="20" />
                                <line x1="104" y1="80" x2="40" y2="80" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="20" />
                                <line x1="104" y1="176" x2="40" y2="176" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="20" />
                            </svg>
                            <span class="truncate transition-opacity duration-300 font-sans" x-show="!sidebarCollapsed"
                                x-transition.opacity>Customize</span>
                        </a>
                    </li>
                    <li x-show="$store.app.isAdmin()" x-cloak>
                        <a href="admin-settings-structure.php"
                            class="pen-sidebar-link flex items-center gap-2 <?= ($currentSection ?? '') === 'settings' ? 'active' : '' ?>"
                            title="Structure">
                            <svg class="w-5 h-5 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
                                <rect width="256" height="256" fill="none" />
                                <rect x="16" y="104" width="48" height="48" rx="8" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
                                <rect x="152" y="40" width="64" height="64" rx="8" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
                                <rect x="152" y="152" width="64" height="64" rx="8" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
                                <line x1="64" y1="128" x2="112" y2="128" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="16" />
                                <path d="M152,184H128a16,16,0,0,1-16-16V88a16,16,0,0,1,16-16h24" fill="none"
                                    stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"
                                    stroke-width="16" />
                            </svg>
                            <span class="truncate transition-opacity duration-300 font-sans" x-show="!sidebarCollapsed"
                                x-transition.opacity>Structure</span>
                        </a>
                    </li>
                    <li x-show="$store.app.hasCap('write:menus')" x-cloak>
                        <a href="admin-settings-navigation.php"
                            class="pen-sidebar-link flex items-center gap-2 <?= ($currentSection ?? '') === 'navigation' ? 'active' : '' ?>"
                            title="Navigation">
                            <svg class="w-5 h-5 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
                                <rect width="256" height="256" fill="none" />
                                <line x1="96" y1="184" x2="96" y2="40" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="20" />
                                <line x1="160" y1="72" x2="160" y2="216" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="20" />
                                <polygon points="96 184 32 200 32 56 96 40 160 72 224 56 224 200 160 216 96 184"
                                    fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"
                                    stroke-width="20" />
                            </svg>
                            <span class="truncate transition-opacity duration-300 font-sans" x-show="!sidebarCollapsed"
                                x-transition.opacity>Navigation</span>
                        </a>
                    </li>
                    <li x-show="$store.app.hasCap('write:seo')" x-cloak>
                        <a href="admin-settings-seo.php"
                            class="pen-sidebar-link flex items-center gap-2 <?= ($currentSection ?? '') === 'seo' ? 'active' : '' ?>"
                            title="SEO">
                            <svg class="w-5 h-5 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
                                <rect width="256" height="256" fill="none" />
                                <circle cx="112" cy="112" r="76" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="20" />
                                <line x1="166" y1="166" x2="220" y2="220" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="20" />
                                <polyline points="72 140 96 116 116 128 152 84" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="20" />
                            </svg>
                            <span class="truncate transition-opacity duration-300 font-sans" x-show="!sidebarCollapsed"
                                x-transition.opacity>SEO</span>
                        </a>
                    </li>
                    <li x-show="$store.app.isAdmin()" x-cloak>
                        <a href="admin-translations.php"
                            :href="$store.app.adminPath('admin-translations.php')"
                            class="pen-sidebar-link flex items-center gap-2 <?= ($currentSection ?? '') === 'translations' ? 'active' : '' ?>"
                            title="Translations">
                            <svg class="w-5 h-5 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
                                <rect width="256" height="256" fill="none" />
                                <polyline points="240 216 184 104 128 216" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="20" />
                                <line x1="144" y1="184" x2="224" y2="184" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="20" />
                                <line x1="96" y1="32" x2="96" y2="56" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="20" />
                                <line x1="32" y1="56" x2="160" y2="56" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="20" />
                                <path d="M128,56a96,96,0,0,1-96,96" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="20" />
                                <path d="M72.7,96A96,96,0,0,0,160,152" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="20" />
                            </svg>
                            <span class="truncate transition-opacity duration-300 font-sans" x-show="!sidebarCollapsed"
                                x-transition.opacity>Translations</span>
                        </a>
                    </li>
                    <li x-show="$store.app.isAdmin()" x-cloak>
                        <a href="admin-settings-storage.php"
                            class="pen-sidebar-link flex items-center gap-2 <?= ($currentSection ?? '') === 'storage' ? 'active' : '' ?>"
                            title="File Storage">
                            <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="2"
                                viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round"
                                    d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4">
                                </path>
                            </svg>
                            <span class="truncate transition-opacity duration-300 font-sans" x-show="!sidebarCollapsed"
                                x-transition.opacity>File Storage</span>
                        </a>
                    </li>
                    <li x-show="$store.app.isAdmin()" x-cloak>
                        <a href="admin-settings-ai.php"
                            class="pen-sidebar-link flex items-center gap-2 <?= ($currentSection ?? '') === 'ai-settings' ? 'active' : '' ?>"
                            title="AI Settings">
                            <svg class="w-5 h-5 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
                                <rect width="256" height="256" fill="none" />
                                <path d="M88,136a40,40,0,1,1-40,40v-6.73" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="20" />
                                <path d="M168,136a40,40,0,1,0,40,40v-6.73" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="20" />
                                <path d="M72,172H64A48,48,0,0,1,48,78.73V72a40,40,0,0,1,80,0V176" fill="none"
                                    stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"
                                    stroke-width="20" />
                                <path d="M184,172h8a48,48,0,0,0,16-93.27V72a40,40,0,0,0-80,0" fill="none"
                                    stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"
                                    stroke-width="20" />
                                <path d="M200,112h-4a28,28,0,0,1-28-28V80" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="20" />
                                <path d="M56,112h4A28,28,0,0,0,88,84V80" fill="none" stroke="currentColor"
                                    stroke-linecap="round" stroke-linejoin="round" stroke-width="20" />
                            </svg>
                            <span class="truncate transition-opacity duration-300 font-sans" x-show="!sidebarCollapsed"
                                x-transition.opacity>AI</span>
                        </a>
                    </li>
                </ul>
            </nav>
        </div>
    </div>

    <!-- Bottom Section: Pinned User Profile & Collapse Toggle -->
    <div class="flex-none mt-auto pt-3 border-t border-border-chassis flex flex-col gap-2"
        :class="sidebarCollapsed ? '' : 'pl-2'" x-data="{
             profile: {
                 display_name: '',
                 username: '',
                 avatar: '',
                 website: '',
                 uuid: ''
             },
             async init() {
                 try {
                     const data = await window.AUTH.getMe();
                     if (data && data.user) {
                         this.profile = data.user;
                     }
                 } catch (e) {
                     console.warn('Could not fetch user profile details in sidebar', e);
                 }
             },
             getUserSubInfo() {
                 if (!this.profile) return '';
                 const displayName = this.profile.display_name;
                 const username = this.profile.username;

                 if (displayName && displayName !== username) {
                     return username;
                 }
                 if (this.profile.website) {
                     return this.profile.website;
                 }
                 return this.profile.uuid || window.AUTH.userId || '';
             }
         }">
        <!-- Authorized User Profile Card Widget -->
        <a href="admin-settings-user.php"
            class="flex items-center text-steel-light no-underline hover:text-rust-bright transition-colors duration-200 overflow-hidden"
            :class="sidebarCollapsed ? 'justify-center p-0 border-0 bg-transparent' : 'gap-3 p-3 bg-nav/50 border border-border-chassis hover:border-rust'"
            :title="sidebarCollapsed ? 'User Profile & Vault: ' + (profile.display_name || profile.username || window.AUTH.userId) : ''">

            <!-- Rounded 2px Avatar Block -->
            <div
                class="h-8 w-8 flex-shrink-0 bg-rust/20 border border-rust/40 rounded-[2px] flex items-center justify-center text-rust-bright font-sans font-bold text-sm select-none overflow-hidden">
                <template x-if="profile.avatar">
                    <img :src="profile.avatar" alt="Avatar" class="h-full w-full object-cover">
                </template>
                <template x-if="!profile.avatar">
                    <span x-text="((profile.display_name || profile.username || 'A')[0]).toUpperCase()"></span>
                </template>
            </div>

            <!-- User Text Details (hidden when collapsed) -->
            <div class="flex flex-col min-w-0" x-show="!sidebarCollapsed" x-transition.opacity>
                <span class="font-sans font-bold text-xs uppercase tracking-wider truncate"
                    x-text="profile.display_name || profile.username || 'Author'"></span>
                <span class="font-sans text-[10px] text-steel-muted truncate" x-text="getUserSubInfo()"></span>
            </div>
        </a>

        <!-- Sidebar Collapse Toggle Button -->
        <div class="flex" :class="sidebarCollapsed ? 'justify-center' : 'justify-end'">
            <button
                class="h-8 w-8 border border-border-chassis hover:border-rust text-steel-bright hover:text-rust-bright flex items-center justify-center bg-transparent cursor-pointer transition-colors duration-200 rounded-[2px] focus:outline-none"
                @click="sidebarCollapsed = !sidebarCollapsed"
                :title="sidebarCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'">
                <svg class="w-4 h-4 transition-transform duration-300" :class="sidebarCollapsed ? 'rotate-180' : ''"
                    fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"></path>
                </svg>
            </button>
        </div>
    </div>
</aside>