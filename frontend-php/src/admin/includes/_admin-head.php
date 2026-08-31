<!DOCTYPE html>
<html lang="en" class="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo $pageTitle ?? "PenCMS Admin"; ?></title>
    <link rel="icon" type="image/x-icon" href="/blog/favicon.ico">
    <!-- Preload UI fonts to avoid FOUC (font-display: swap) on slow admin pages -->
    <link rel="preload" href="/fonts/mozilla-headline-v1-latin-700.woff2" as="font" type="font/woff2" crossorigin>
    <link rel="preload" href="/fonts/AtkinsonHyperlegibleNext-Regular.woff2" as="font" type="font/woff2" crossorigin>

    <style>[x-cloak]{display:none!important}</style>
    <link rel="stylesheet" href="css/admin.css">

    <!-- Auth Context -->
    <script src="js/vault.js"></script>
    <script>
        window.AUTH = <?= json_encode(
            $authContext ?? ["apiBase" => "/api/v1"],
        ) ?>;
        (function () {
            function readCookie(name) {
                const match = document.cookie.match(
                    new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1') + '=([^;]*)')
                );
                return match ? decodeURIComponent(match[1]) : null;
            }
            const fromCookie = readCookie('pen_site_id');
            let fromStorage = null;
            try {
                fromStorage = localStorage.getItem('pen_site_id');
            } catch (e) {}

            // Bookmarkable admin URLs: ?site= wins over sticky cookie/storage
            let fromQuery = null;
            try {
                const q = new URLSearchParams(window.location.search).get('site');
                if (q && String(q).trim()) {
                    fromQuery = String(q).trim().toLowerCase();
                }
            } catch (e) {}

            const ME_TTL_MS = 4000;
            let meCache = { siteId: null, data: null, at: 0 };
            let meFailed = { siteId: null, error: null, at: 0 };
            let meInflight = { siteId: null, promise: null };

            function invalidateMeCache() {
                meCache = { siteId: null, data: null, at: 0 };
                meFailed = { siteId: null, error: null, at: 0 };
                meInflight = { siteId: null, promise: null };
            }

            window.AUTH.setSiteId = function (id) {
                const next = (id && String(id).trim()) || 'default';
                const prev = window.AUTH.siteId;
                window.AUTH.siteId = next;
                document.cookie = 'pen_site_id=' + encodeURIComponent(next) + '; path=/; max-age=604800';
                try {
                    localStorage.setItem('pen_site_id', next);
                } catch (e) {}
                if (next !== prev) {
                    invalidateMeCache();
                }
            };

            if (fromQuery) {
                window.AUTH.setSiteId(fromQuery);
            } else {
                window.AUTH.siteId = fromCookie || fromStorage || 'default';
            }

            window.AUTH.getMe = function (opts) {
                const force = !!(opts && opts.force);
                const siteId = window.AUTH.siteId || 'default';
                const now = Date.now();
                if (!force && meCache.data && meCache.siteId === siteId && (now - meCache.at) < ME_TTL_MS) {
                    return Promise.resolve(meCache.data);
                }
                if (!force && meFailed.error && meFailed.siteId === siteId && (now - meFailed.at) < ME_TTL_MS) {
                    return Promise.reject(meFailed.error);
                }
                if (!force && meInflight.promise && meInflight.siteId === siteId) {
                    return meInflight.promise;
                }
                const base = (window.AUTH.apiBase || '/api/v1').replace(/\/v1\/?$/, '');
                const promise = fetch(base + '/auth/me', { headers: window.AUTH.getHeaders() })
                    .then(function (res) {
                        if (!res.ok) {
                            const err = new Error('HTTP ' + res.status);
                            err.status = res.status;
                            throw err;
                        }
                        return res.json();
                    })
                    .then(function (data) {
                        meFailed = { siteId: null, error: null, at: 0 };
                        meCache = { siteId: siteId, data: data, at: Date.now() };
                        return data;
                    })
                    .catch(function (err) {
                        meCache = { siteId: null, data: null, at: 0 };
                        meFailed = { siteId: siteId, error: err, at: Date.now() };
                        throw err;
                    })
                    .finally(function () {
                        if (meInflight.promise === promise) {
                            meInflight = { siteId: null, promise: null };
                        }
                    });
                meInflight = { siteId: siteId, promise: promise };
                return promise;
            };

            window.AUTH.getHeaders = () => {
                const siteId = window.AUTH.siteId || 'default';
                const headers = {
                    'Content-Type': 'application/json',
                    'X-User-ID': window.AUTH.userId || 'author',
                    'X-Pen-Site-Id': siteId
                };
                if (window.VAULT && window.VAULT.unlocked) {
                    const contentPass = window.VAULT.getSecret('CONTENT_SFTP_PASS');
                    if (contentPass) headers['X-Vault-Content-Pass'] = contentPass;

                    const assetsPass = window.VAULT.getSecret('ASSETS_SFTP_PASS');
                    if (assetsPass) headers['X-Vault-Assets-Pass'] = assetsPass;

                    const publishPass = window.VAULT.getSecret('PUBLISH_SFTP_PASS:' + siteId);
                    if (publishPass) headers['X-Vault-Publish-Pass'] = publishPass;

                    const publishGithubToken = window.VAULT.getSecret('PUBLISH_GITHUB_TOKEN:' + siteId);
                    if (publishGithubToken) headers['X-Vault-Publish-Github-Token'] = publishGithubToken;

                    const extras = window.AUTH.vaultHeaderBindings || [];
                    extras.forEach((binding) => {
                        if (!binding || !binding.alias || !binding.keyTemplate) return;
                        const key = String(binding.keyTemplate).replace('{site}', siteId);
                        const val = window.VAULT.getSecret(key);
                        if (val) headers[binding.alias] = val;
                    });

                    // Load Pen API Key for authentication
                    const apiKey = window.VAULT.getSecret('PEN_API_KEY');
                    if (apiKey) headers['X-Pen-API-Key'] = apiKey;

                    // AI Provider credentials (structured vault entry)
                    const aiConfig = window.VAULT.getSecret('AI_PROVIDER_CONFIG');
                    if (aiConfig && typeof aiConfig === 'object') {
                        if (aiConfig.apiKey) headers['X-Pen-AI-Key'] = aiConfig.apiKey;
                        if (aiConfig.baseUrl) headers['X-Pen-AI-Base-URL'] = aiConfig.baseUrl;
                        if (aiConfig.model) headers['X-Pen-AI-Model'] = aiConfig.model;
                    }
                }
                return headers;
            };

            window.AUTH.logout = async function () {
                const base = (window.AUTH.apiBase || '/api/v1').replace(/\/v1\/?$/, '');
                try {
                    await fetch(base + '/auth/logout', {
                        method: 'POST',
                        headers: typeof window.AUTH.getHeaders === 'function' ? window.AUTH.getHeaders() : { 'Content-Type': 'application/json' }
                    });
                } catch (e) {
                    console.warn('Logout API error:', e);
                }
                // Clear client auth cookies
                document.cookie = 'pen_user_id=; path=/; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT';
                document.cookie = 'pen_role=; path=/; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT';
                document.cookie = 'pen_site_id=; path=/; max-age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT';
                // Clear session storage & master password
                try {
                    sessionStorage.removeItem('pen_master_password');
                    sessionStorage.clear();
                } catch (e) {}
                // Lock and reset vault state
                if (window.VAULT) {
                    window.VAULT.unlocked = false;
                    window.VAULT.secrets = {};
                    window.VAULT.masterPassword = null;
                }
                window.location.href = 'login.php';
            };

            if (window.VAULT && typeof window.VAULT.init === 'function') {
                window.VAULT.init();
            }
        })();
    </script>

    <!-- Traven Workspace Preferences Overrides -->
    <script>
        (function() {
            try {
                const saved = localStorage.getItem('pen_editor_workspace_prefs');
                if (saved) {
                    const prefs = JSON.parse(saved);
                    const html = document.documentElement;
                    if (prefs.leftColumnCollapsed) html.classList.add('pref-left-collapsed');
                    if (prefs.rightColumnCollapsed) html.classList.add('pref-right-collapsed');
                    if (prefs.secondaryRailCollapsed) html.classList.add('pref-secondary-rail-collapsed');
                }
            } catch(e) {}
        })();
    </script>
    <style>
        .hide-main-toolbar .traven-toolbar-container {
            display: none !important;
        }
        .hide-selection-bubble .traven-bubble-menu {
            display: none !important;
        }
        .hide-gutter-insertion .cm-traven-gutter {
            display: none !important;
        }

        /* Prevent layout shift before Alpine hydration */
        html.pref-left-collapsed .resizable-left-column {
            display: none !important;
        }
        html.pref-right-collapsed .resizable-right-column {
            display: none !important;
        }
        html.pref-secondary-rail-collapsed .pref-secondary-rail-item {
            display: none !important;
        }

        /* View Transitions API */
        @view-transition {
            navigation: auto;
        }
    </style>

    <!-- Alpine.js -->
        <script defer src="/assets/vendor/alpine.min.js"></script>

    <?php
    $penLoadTraven = !empty($penLoadTraven);
    $penLoadMarked = !empty($penLoadMarked);
    if ($penLoadMarked):
        ?>
        <!-- Markdown rendering for AI sidebar; vendor copy at assets/vendor/marked/.
             Loaded synchronously (not deferred) because renderMsg() calls
             marked.parse() on first AI response render. ~40 KB minified. -->
        <script src="/assets/vendor/marked/marked.min.js"></script>
        <?php
    endif;
    if ($penLoadTraven):
        ?>
    <!-- Traven Editor (PenCMS rich-text editor) CSS + JS -->
    <link rel="stylesheet" href="/assets/vendor/traven/traven.css" />
    <link rel="stylesheet" href="/assets/vendor/traven/toolbar-expandable.css" />
        <?php
    endif;
    // Shared font registry — same faces as reader publicAsset('fonts/fonts.css').
    // Loaded for the editor (skin boot) and Theme Settings (Style font previews).
    $penEditorSkinBoot = $penEditorSkinBoot ?? null;
    $penLoadFontRegistry = !empty($penLoadFontRegistry) || is_array($penEditorSkinBoot);
    if ($penLoadFontRegistry):
        ?>
    <link rel="stylesheet" href="/assets/fonts/fonts.css" />
        <?php
    endif;
    // Editor page: emit theme (or starter-fallback) skin links early to avoid FOUC.
    // Non-editor pages: no skin injection (theme skins live under /blog/themes/… only).
    if (is_array($penEditorSkinBoot)):
        if (!empty($penEditorSkinBoot['hrefs']) && is_array($penEditorSkinBoot['hrefs'])):
            $travenSkinIdx = 0;
            foreach ($penEditorSkinBoot['hrefs'] as $skinHref):
                if (!is_string($skinHref) || $skinHref === '') {
                    continue;
                }
                ?>
    <link id="traven-skin-<?= (int) $travenSkinIdx ?>" rel="stylesheet" href="<?= htmlspecialchars($skinHref, ENT_QUOTES, 'UTF-8') ?>" />
                <?php
                $travenSkinIdx++;
            endforeach;
        endif;
        // Empty hrefs: no early skin links (theme has no skin / starter with no file).
    endif;
    if ($penLoadTraven):
        ?>
    <link rel="stylesheet" href="/assets/vendor/traven/expand-embed.css" />
    <script type="module">
        // Bridge: expose the ES-module export as a global for non-module scripts (wizard4.js)
        import { TravenEditor, DEFAULT_TOOLBAR, DEFAULT_BUBBLE_TOOLBAR, registerTools } from '/assets/vendor/traven/traven.js';
        import {
            ExpandEmbedPlugin,
            expandEmbedTools,
            EXPAND_EMBED_TOOLBAR,
        } from '/assets/vendor/traven/expand-embed.js';
        registerTools(expandEmbedTools);
        window.TravenEditor = TravenEditor;
        window.DEFAULT_TOOLBAR = DEFAULT_TOOLBAR;
        window.DEFAULT_BUBBLE_TOOLBAR = DEFAULT_BUBBLE_TOOLBAR;
        window.ExpandEmbedPlugin = ExpandEmbedPlugin;
        window.expandEmbedTools = expandEmbedTools;
        window.EXPAND_EMBED_TOOLBAR = EXPAND_EMBED_TOOLBAR;
    </script>
        <?php
    endif;
    ?>
</head>
