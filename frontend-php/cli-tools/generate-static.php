<?php

/**
 * Static Site Generator for PenCMS
 *
 * Converts dossiers into a zero-config HTML archive, scoped to one site or all
 * live registry sites.
 *
 * Usage:
 *   php generate-static.php [--site=<id>] [--domain=<host>] [--output=<dir>]
 *   php generate-static.php --all-sites [--domain=<host>] [--output=<dir>]  (Pro)
 *
 * Default (neither --site nor --all-sites): builds site "default" only.
 * --all-sites writes each site under {output}/{site_id}/. Core refuses
 * --all-sites with a Pro pointer (edition from GET /api/config).
 * Canonical URL order: --domain → registry domain → localhost.
 */

require_once __DIR__ . '/../vendor/autoload.php';
require_once __DIR__ . '/../src/core/PostRenderer.php';
require_once __DIR__ . '/../src/core/DossierDiscovery.php';
require_once __DIR__ . '/../src/core/ShortcodeProcessor.php';
require_once __DIR__ . '/../src/core/InternalAPIClient.php';
require_once __DIR__ . '/../src/core/ThemeEngine.php';
require_once __DIR__ . '/../src/core/TaxonomySlug.php';
require_once __DIR__ . '/../src/core/RssFeedBuilder.php';
require_once __DIR__ . '/../src/core/SitemapBuilder.php';
require_once __DIR__ . '/../src/core/SearchIndexBuilder.php';
require_once __DIR__ . '/../src/core/SiteRegistry.php';
require_once __DIR__ . '/../src/core/LocalizedDetail.php';
require_once __DIR__ . '/../src/core/LocalizedList.php';
require_once __DIR__ . '/../src/core/LlmsTxtBuilder.php';
require_once __DIR__ . '/../src/core/StaticSeo.php';

use Dossier\PostRenderer;
use Dossier\DossierDiscovery;
use Dossier\ShortcodeProcessor;
use Dossier\InternalAPIClient;
use Dossier\ThemeEngine;
use Dossier\RssFeedBuilder;
use Dossier\SitemapBuilder;
use Dossier\SearchIndexBuilder;
use Dossier\SiteRegistry;
use Dossier\LocalizedDetail;
use Dossier\LocalizedList;
use Dossier\LlmsTxtBuilder;
use Dossier\StaticSeo;

define('STATIC_BUILD', true);

$options = getopt("", ["domain:", "output:", "site:", "all-sites"]);

if (isset($options['output'])) {
    $outputRoot = rtrim($options['output'], '/');
} else {
    $outputRoot = __DIR__ . '/../dist';
}

$configOverride = getenv('PENCMS_CONFIG_PATH');
$configPath = $configOverride !== false && trim($configOverride) !== ''
    ? trim($configOverride)
    : __DIR__ . '/../../backend-python/config.ini';
$ini = parse_ini_file($configPath, true) ?: [];
$registry = SiteRegistry::fromConfigPath($configPath);

$hasSite = isset($options['site']);
$hasAllSites = array_key_exists('all-sites', $options);

if ($hasSite && $hasAllSites) {
    fwrite(STDERR, "Error: pass either --site=<id> or --all-sites, not both.\n");
    exit(1);
}

if ($hasAllSites) {
    $edition = 'core';
    try {
        $api = new InternalAPIClient();
        $cfg = $api->get('/config');
        if (is_array($cfg) && (($cfg['edition'] ?? '') === 'pro')) {
            $edition = 'pro';
        }
    } catch (\Throwable $e) {
        $edition = 'core';
    }
    if ($edition !== 'pro') {
        fwrite(
            STDERR,
            "Error: --all-sites requires PenCMS Pro (overlay; GET /api/config edition=pro).\n"
        );
        exit(1);
    }
}

$siteIds = [];
$allSitesMode = false;

if ($hasAllSites) {
    $allSitesMode = true;
    foreach ($registry->listSites() as $site) {
        $id = strtolower(trim((string) ($site['id'] ?? '')));
        if ($id !== '') {
            $siteIds[] = $id;
        }
    }
    if ($siteIds === []) {
        fwrite(STDERR, "Error: no live sites found in registry.\n");
        exit(1);
    }
} elseif ($hasSite) {
    $requested = strtolower(trim((string) $options['site']));
    if ($requested === '') {
        fwrite(STDERR, "Error: --site= requires a non-empty site id.\n");
        exit(1);
    }
    if ($registry->getSite($requested) === null) {
        fwrite(STDERR, "Error: unknown site '{$requested}' (not in registry).\n");
        exit(1);
    }
    $siteIds[] = $requested;
} else {
    $siteIds[] = SiteRegistry::DEFAULT_SITE_ID;
    fwrite(STDERR, "Note: building site 'default' only. Use --site=<id> for other sites (--all-sites is Pro).\n");
}

$domainFlag = isset($options['domain']) ? trim((string) $options['domain']) : null;
$promptedDomain = null;

// Interactive domain prompt only for single-site runs when --domain is absent
if ($domainFlag === null && !$allSitesMode) {
    echo "🌐 Remote Domain (e.g., history-archive.org or leave blank for registry/install/localhost): ";
    $promptedDomain = trim((string) fgets(STDIN));
    if ($promptedDomain === '') {
        $promptedDomain = null;
    }
} elseif ($domainFlag !== null) {
    echo "🌐 Using provided domain: " . $domainFlag . "\n";
}

$startTime = microtime(true);

// Clean output root once, then flush cache once (install-wide)
if (is_dir($outputRoot)) {
    echo "🧹 Cleaning previous build...\n";
    system('rm -rf ' . escapeshellarg($outputRoot));
}
mkdir($outputRoot, 0777, true);

echo "⚡ Flushing and rebuilding content cache via API...\n";
try {
    $cacheApi = new InternalAPIClient(SiteRegistry::DEFAULT_SITE_ID);
    $cacheApi->post('/storage/rebuild-cache');
    echo "   - Content cache successfully flushed!\n";
} catch (\Exception $e) {
    echo "   - Warning: Could not flush content cache: " . $e->getMessage() . "\n";
}

$totalPages = 0;
foreach ($siteIds as $siteId) {
    $presentation = $registry->resolvePresentation($siteId, $ini);
    $siteRecord = $registry->getSite($siteId);
    $registryDomain = null;
    if ($siteRecord !== null && !empty($siteRecord['domain'])) {
        $registryDomain = (string) $siteRecord['domain'];
    }

    $siteUrl = resolveCanonicalSiteUrl($domainFlag, $promptedDomain, $registryDomain);
    $siteOutputDir = $allSitesMode ? ($outputRoot . '/' . $siteId) : $outputRoot;

    echo "\n🚀 Starting Static Build for site '{$siteId}': {$siteUrl}\n";
    if (!is_dir($siteOutputDir)) {
        mkdir($siteOutputDir, 0777, true);
    }

    $totalPages += buildStaticSite(
        $siteId,
        $presentation,
        $siteUrl,
        $siteOutputDir,
        $configPath,
        $ini
    );
}

$endTime = microtime(true);
$duration = round($endTime - $startTime, 2);

echo "\n✨ Build Complete!";
echo "\n📂 Location: {$outputRoot}";
echo "\n📄 Pages: " . $totalPages;
echo "\n⏱️  Time: {$duration} seconds\n";

/**
 * Resolve canonical base URL for links.
 * Order: --domain → interactive prompt → registry domain → localhost.
 */
function resolveCanonicalSiteUrl(
    ?string $domainFlag,
    ?string $promptedDomain,
    ?string $registryDomain
): string {
    $input = $domainFlag;
    if ($input === null || $input === '') {
        $input = $promptedDomain;
    }
    if ($input === null || $input === '') {
        $input = $registryDomain;
    }
    if ($input === null || trim((string) $input) === '') {
        return 'http://localhost/';
    }
    $clean = preg_replace('~^https?://~', '', trim((string) $input));
    $clean = rtrim((string) $clean, '/');
    return 'https://' . $clean . '/';
}

/**
 * Guessable /slug.md next to canonical /slug/index.md (byte copy).
 */
function copyMarkdownAlias(string $indexMdPath, string $aliasPath): void
{
    if (!is_file($indexMdPath)) {
        return;
    }
    copy($indexMdPath, $aliasPath);
}

/**
 * Apache / Caddy / nginx snippets for markdown MIME, Vary, and X-Robots-Tag.
 * Content-Signal training bit comes from the site SEO setting.
 *
 * @param array<string, mixed> $presentation
 */
function writeStaticAgentHeaders(string $outputDir, array $presentation): void
{
    $signal = StaticSeo::contentSignalHeader(!empty($presentation['content_signal_ai_train']));
    $redirects = StaticSeo::sanitizeRedirects(
        is_array($presentation['seo_redirects'] ?? null) ? $presentation['seo_redirects'] : []
    );
    $rewriteBlock = StaticSeo::apacheRewriteRules($redirects);

    $htaccessContent = <<<EOT
# PenCMS - Agent-First Content Negotiation
RewriteEngine On
RewriteCond %{HTTP:Accept} text/markdown [NC]
RewriteCond %{REQUEST_FILENAME}index.md -f [OR]
RewriteCond %{REQUEST_FILENAME}/index.md -f
RewriteRule ^(.*)$ \$1index.md [L]

<FilesMatch "\\.md$">
    Header set Content-Type "text/markdown; charset=utf-8"
    Header set Vary "Accept"
    Header set X-Robots-Tag "noindex"
    Header set Content-Signal "{$signal}"
</FilesMatch>

<FilesMatch "^llms.*\\.txt$">
    Header set Content-Type "text/plain; charset=utf-8"
    Header set X-Robots-Tag "noindex"
    Header set Content-Signal "{$signal}"
</FilesMatch>

<FilesMatch "\\.html$">
    Header set Vary "Accept"
</FilesMatch>
EOT;
    $htaccessContent .= $rewriteBlock;

    $caddyContent = <<<EOT
# Example: serve this dist/ as the site document root.
# Not the PenCMS API reverse-proxy (see deploy/Caddyfile).

:80 {
	root * .
	file_server

	@markdown path_regexp \\.md$
	header @markdown Content-Type "text/markdown; charset=utf-8"
	header @markdown Vary "Accept"
	header @markdown X-Robots-Tag "noindex"
	header @markdown Content-Signal "{$signal}"

	@llms path_regexp ^/llms[^/]*\\.txt$
	header @llms Content-Type "text/plain; charset=utf-8"
	header @llms X-Robots-Tag "noindex"
	header @llms Content-Signal "{$signal}"

	@html path_regexp \\.html$
	header @html Vary "Accept"
}
EOT;

    $nginxContent = <<<EOT
# Example snippet for a server that serves this dist/ as root.
# Merge into your existing server { } block.

location ~* \\.md$ {
    default_type "text/markdown; charset=utf-8";
    add_header X-Robots-Tag "noindex" always;
    add_header Vary "Accept" always;
    add_header Content-Signal "{$signal}" always;
}

location ~* ^/llms[^/]*\\.txt$ {
    default_type "text/plain; charset=utf-8";
    add_header X-Robots-Tag "noindex" always;
    add_header Content-Signal "{$signal}" always;
}

location ~* \\.html$ {
    add_header Vary "Accept" always;
}
EOT;

    file_put_contents($outputDir . '/.htaccess', $htaccessContent);
    file_put_contents($outputDir . '/Caddyfile', $caddyContent);
    file_put_contents($outputDir . '/nginx.conf.example', $nginxContent);

    if ($redirects !== []) {
        file_put_contents($outputDir . '/_redirects', StaticSeo::netlifyRedirectsFile($redirects));
    }
}

function writeIndexNowKeyFile(string $outputDir, array $presentation): void
{
    if (empty($presentation['indexnow_enabled'])) {
        return;
    }
    $key = trim((string) ($presentation['indexnow_key'] ?? ''));
    if (!StaticSeo::isValidIndexNowKey($key)) {
        echo "   ⚠️ IndexNow enabled but key is missing or invalid; skipping key file.\n";
        return;
    }
    file_put_contents($outputDir . '/' . $key . '.txt', $key . "\n");
}

/**
 * Best-effort IndexNow ping after a standalone public HTTPS build.
 * Skipped when PENCMS_SKIP_INDEXNOW=1 (publish pings after deploy instead).
 * Never fails the build.
 */
function maybePingIndexNowAfterBuild(array $presentation, string $siteUrl, string $outputDir): void
{
    $skip = getenv('PENCMS_SKIP_INDEXNOW');
    if ($skip !== false && trim((string) $skip) !== '' && trim((string) $skip) !== '0') {
        return;
    }
    if (empty($presentation['indexnow_enabled'])) {
        return;
    }
    if (!StaticSeo::isPublicHttpsUrl($siteUrl)) {
        return;
    }
    $key = trim((string) ($presentation['indexnow_key'] ?? ''));
    if (!StaticSeo::isValidIndexNowKey($key)) {
        return;
    }
    $host = parse_url($siteUrl, PHP_URL_HOST);
    if (!is_string($host) || $host === '') {
        return;
    }
    $origin = 'https://' . $host;
    $port = parse_url($siteUrl, PHP_URL_PORT);
    if (is_int($port) && $port !== 443) {
        $origin .= ':' . $port;
    }
    $urls = [];
    $sitemapPath = $outputDir . '/sitemap.xml';
    if (is_file($sitemapPath)) {
        $urls = StaticSeo::sitemapHtmlLocs((string) file_get_contents($sitemapPath));
    }
    if ($urls === []) {
        return;
    }
    echo "📡 IndexNow ping (" . count($urls) . " URL(s))...\n";
    $ok = StaticSeo::pingIndexNow($host, $key, $origin . '/' . $key . '.txt', $urls);
    if (!$ok) {
        echo "   ⚠️ IndexNow ping failed (build continues).\n";
    }
}

/**
 * Build robots.txt for static dist (mirrors src/blog/robots.php).
 *
 * @param array<string, mixed> $presentation
 */
function buildStaticRobotsTxt(array $presentation, string $siteUrl): string
{
    $custom = trim((string) ($presentation['robots_txt'] ?? ''));
    if ($custom !== '') {
        $body = $custom;
        if (!str_ends_with($body, "\n")) {
            $body .= "\n";
        }
        return $body;
    }

    $robotsIndex = array_key_exists('robots_index', $presentation)
        ? (bool) $presentation['robots_index']
        : true;
    $sitemapEnabled = array_key_exists('sitemap_enabled', $presentation)
        ? (bool) $presentation['sitemap_enabled']
        : true;

    $lines = [
        'User-agent: *',
        $robotsIndex ? 'Allow: /' : 'Disallow: /',
    ];

    if ($sitemapEnabled && !isLocalhostCanonicalUrl($siteUrl)) {
        $normalized = RssFeedBuilder::normalizeSiteUrl($siteUrl);
        $lines[] = 'Sitemap: ' . rtrim($normalized, '/') . '/sitemap.xml';
    }

    return implode("\n", $lines) . "\n";
}

function isLocalhostCanonicalUrl(string $siteUrl): bool
{
    $host = parse_url($siteUrl, PHP_URL_HOST);
    if (!is_string($host) || $host === '') {
        return true;
    }
    $host = strtolower($host);

    return $host === 'localhost' || $host === '127.0.0.1' || $host === '::1';
}

/**
 * Build one site's static tree into $outputDir.
 *
 * @param array<string, mixed> $presentation
 * @param array<string, mixed> $ini
 * @return int Number of dossier/page HTML files rendered (plus home counted separately by caller via +1 in sum — returns dossier count + 1 for home)
 */
function buildStaticSite(
    string $siteId,
    array $presentation,
    string $siteUrl,
    string $outputDir,
    string $configPath,
    array $ini
): int {
    $sitename = (string) ($presentation['sitename'] ?? '');
    $tagline = (string) ($presentation['tagline'] ?? '');
    $heroTitle = $presentation['hero_title'] ?? null;
    if ($heroTitle === '') {
        $heroTitle = null;
    }
    $heroImage = $presentation['hero_image'] ?? null;
    if ($heroImage === '') {
        $heroImage = null;
    }
    $activeTheme = (string) ($presentation['theme'] ?? ($ini['theme']['active'] ?? 'starter'));

    // Bake public relay action + submission_key into Twig. Never the fetch token.
    $presentation = array_merge($presentation, SiteRegistry::feedbackBakeContext($presentation));

    $api = new InternalAPIClient($siteId);

    // 1.5 Agent-first headers: .htaccess + Caddy/nginx examples
    echo "🌐 Generating .htaccess / Caddyfile / nginx.conf.example...\n";
    writeStaticAgentHeaders($outputDir, $presentation);
    writeIndexNowKeyFile($outputDir, $presentation);

    // 2. Fetch all dossiers via API
    echo "🔍 Fetching dossiers via API (site={$siteId})...\n";
    $discovery = new DossierDiscovery($api);
    $allDossiers = $discovery->getAllDossiers('blog', false);
    $allPagesAndPosts = $discovery->getAllDossiers('blog', true);
    $localizedPagesByLanguage = [];
    $localizedMergedByLanguage = [];
    $defaultLanguage = strtolower((string) ($presentation['language'] ?? 'en'));
    if (!empty($presentation['i18n_active'])) {
        foreach (($presentation['languages'] ?? []) as $configuredLanguage) {
            $configuredLanguage = strtolower((string) $configuredLanguage);
            if ($configuredLanguage === '' || $configuredLanguage === $defaultLanguage) {
                continue;
            }
            $exactLocalized = $discovery->getAllDossiers(
                'blog',
                true,
                $configuredLanguage,
                'none'
            );
            $localizedPagesByLanguage[$configuredLanguage] = $exactLocalized;
            if ($exactLocalized !== []) {
                $localizedMergedByLanguage[$configuredLanguage] = $discovery->getAllDossiers(
                    'blog',
                    true,
                    $configuredLanguage,
                    'default'
                );
            }
        }
    }

    $lookupTable = [];
    foreach ($allPagesAndPosts as $d) {
        $lookupTable[$d['slug']] = $d['section'];
    }
    ShortcodeProcessor::$linkLookup = $lookupTable;

    // 3. Render Home Page
    echo "📄 Rendering Home Page...\n";
    $theme = ThemeEngine::fromConfig($configPath, true, './', $siteId, $presentation);
    ShortcodeProcessor::$basePath = './';

    $homeHtml = $theme->render('index', [
        'dossiers' => $allDossiers,
        'site_url' => $siteUrl,
        'canonical_url' => $siteUrl,
        'hero_title' => $heroTitle,
        'hero_image' => $heroImage,
        'tagline' => $tagline,
        'sitename' => $sitename,
        'page_title' => $heroTitle,
        'body_class' => 'page-front',
    ]);
    file_put_contents($outputDir . '/index.html', $homeHtml);

    // Generate index.md (posts archive) and llmstxt.org index (pages + posts).
    $homeMd = "# " . $sitename . " - Archive\n\n";
    foreach ($allDossiers as $d) {
        $homeMd .= "- [{$d['hero_title']}](./{$d['slug']}/index.md)\n";
    }
    file_put_contents($outputDir . '/index.md', $homeMd);
    file_put_contents(
        $outputDir . '/llms.txt',
        LlmsTxtBuilder::buildIndex($sitename, $tagline, $siteUrl, $allPagesAndPosts)
    );

    // Site-wide RSS 2.0
    echo "📡 Generating feed.xml...\n";
    $rssDossiers = $allDossiers;
    usort($rssDossiers, static function ($a, $b) {
        return strtotime($b['date'] ?? '') <=> strtotime($a['date'] ?? '');
    });
    $rssXml = RssFeedBuilder::build(
        $rssDossiers,
        $siteUrl,
        $sitename,
        $tagline,
        $theme->getLogoUrl()
    );
    file_put_contents($outputDir . '/feed.xml', $rssXml);

    $sitemapEnabled = array_key_exists('sitemap_enabled', $presentation)
        ? (bool) $presentation['sitemap_enabled']
        : true;

    if ($sitemapEnabled) {
        echo "🗺️  Generating sitemap.xml...\n";
        $sitemapXml = SitemapBuilder::build(
            $allPagesAndPosts,
            $siteUrl,
            !empty($presentation['i18n_active'])
                ? $localizedPagesByLanguage
                : [],
            (string) ($presentation['language'] ?? 'en')
        );
        file_put_contents($outputDir . '/sitemap.xml', $sitemapXml);
    }

    echo "🤖 Generating robots.txt...\n";
    $robotsBody = buildStaticRobotsTxt($presentation, $siteUrl);
    file_put_contents($outputDir . '/robots.txt', $robotsBody);

    $jsonlFile = @fopen($outputDir . '/content.jsonl', 'w');
    $searchDocs = [];

    // 4. Render each Dossier/Page
    echo "📄 Rendering Dossiers/Pages (" . count($allPagesAndPosts) . ")...\n";
    $renderer = new PostRenderer($api, !empty($presentation['comments_enabled']));
    $total = count($allPagesAndPosts);
    $count = 0;
    $llmsFullItems = [];

    foreach ($allPagesAndPosts as $d) {
        $count++;
        $section = $d['section'];
        $slug = $d['slug'];

        echo sprintf("[%d/%d] Rendering Dossier/Page: %s/%s\n", $count, $total, $section, $slug);

        $dossierDir = $outputDir . '/' . $slug;
        mkdir($dossierDir, 0777, true);

        $theme = ThemeEngine::fromConfig($configPath, true, '../', $siteId, $presentation);
        ShortcodeProcessor::$basePath = '../';

        try {
            $pageData = $renderer->renderPage($section, $slug);

            $seoData = [
                'page_title' => $pageData['seo']['title'] ?? null,
                'og_title' => $pageData['seo']['og_title'] ?? null,
                'og_description' => $pageData['seo']['og_description'] ?? null,
                'og_image' => $pageData['seo']['og_image'] ?? null,
                'meta_description' => $pageData['seo']['og_description'] ?? null,
            ];

            $pageData = array_merge($pageData, $seoData, [
                'site_url' => $siteUrl,
                'canonical_url' => $siteUrl . $slug . '/',
                'sitename' => $sitename,
                'tagline' => $tagline,
                'slug' => $slug,
                'section' => $section,
                'noindex' => !empty($pageData['noindex']) || DossierDiscovery::isNoindex($d),
            ]);

            $markdown = $renderer->renderMarkdown($section, $slug);
            file_put_contents($dossierDir . '/index.md', $markdown);
            copyMarkdownAlias($dossierDir . '/index.md', $outputDir . '/' . $slug . '.md');
            if (!DossierDiscovery::isNoindex($d)) {
                $llmsFullItems[] = [
                    'title' => LlmsTxtBuilder::itemTitle($d, $slug),
                    'url' => rtrim($siteUrl, '/') . '/' . $slug . '/',
                    'published' => (string) ($d['date'] ?? ''),
                    'author' => trim((string) ($d['author'] ?? '')),
                    'markdown' => $markdown,
                ];
            }

            $searchDoc = SearchIndexBuilder::documentFromDossier(
                $d,
                $markdown,
                '../' . rawurlencode($slug) . '/index.html',
                !empty($presentation['i18n_active']) ? $defaultLanguage : null
            );
            if ($searchDoc !== null) {
                $searchDocs[] = $searchDoc;
            }

            if ($jsonlFile && !DossierDiscovery::isNoindex($d)) {
                $jsonLine = json_encode([
                    'id' => $slug,
                    'url' => '/' . $slug . '/index.md',
                    'title' => $pageData['seo']['title'] ?? ($pageData['hero_title'] ?? $slug),
                    'content' => $markdown
                ]);
                fwrite($jsonlFile, $jsonLine . "\n");
            }

            if ($d['page'] ?? false) {
                $pageContent = '';
                foreach ($pageData['posts'] as $p) {
                    $pageContent .= $p['content_html'];
                }
                $pageData['page_content'] = $pageContent;
                $html = $theme->render('page', $pageData);
            } else {
                $html = $theme->render('post', $pageData);
            }
            file_put_contents($dossierDir . '/index.html', $html);

        } catch (\Exception $e) {
            echo "❌ Error rendering {$slug}: " . $e->getMessage() . "\n";
        }
    }

    echo "📄 Generating llms-full.txt (default-language corpus)...\n";
    file_put_contents(
        $outputDir . '/llms-full.txt',
        LlmsTxtBuilder::buildFull($sitename, $tagline, $llmsFullItems)
    );

    // 4.1 Render exact translated details only. Merged list surfaces are
    // generated separately; fallback rows never create detail output.
    $localizedCount = 0;
    $localizedSurfaceCount = 0;
    foreach ($localizedPagesByLanguage as $language => $localizedPages) {
        foreach ($localizedPages as $d) {
            $section = $d['section'];
            $slug = $d['slug'];
            $dossierDir = $outputDir . '/' . $language . '/' . $slug;

            $relativeRoot = LocalizedDetail::staticRelativeRoot();
            $localizedTheme = ThemeEngine::fromConfig(
                $configPath,
                true,
                $relativeRoot,
                $siteId,
                $presentation
            );
            ShortcodeProcessor::$basePath = $relativeRoot;

            try {
                $pageData = $renderer->renderPage(
                    $section,
                    $slug,
                    $language,
                    true
                );
                $seoData = [
                    'page_title' => $pageData['seo']['title'] ?? null,
                    'og_title' => $pageData['seo']['og_title'] ?? null,
                    'og_description' => $pageData['seo']['og_description'] ?? null,
                    'og_image' => $pageData['seo']['og_image'] ?? null,
                    'meta_description' => $pageData['seo']['og_description'] ?? null,
                ];
                $pageData = array_merge($pageData, $seoData, [
                    'site_url' => $siteUrl,
                    'canonical_url' => $siteUrl . $language . '/' . $slug . '/',
                    'sitename' => $sitename,
                    'tagline' => $tagline,
                    'slug' => $slug,
                    'section' => $section,
                    'noindex' => !empty($pageData['noindex']) || DossierDiscovery::isNoindex($d),
                ]);

                $markdown = $renderer->renderMarkdown(
                    $section,
                    $slug,
                    $language,
                    true
                );

                if ($d['page'] ?? false) {
                    $pageContent = '';
                    foreach ($pageData['posts'] as $post) {
                        $pageContent .= $post['content_html'];
                    }
                    $pageData['page_content'] = $pageContent;
                    $html = $localizedTheme->render('page', $pageData);
                } else {
                    $html = $localizedTheme->render('post', $pageData);
                }
                @mkdir($dossierDir, 0777, true);
                file_put_contents($dossierDir . '/index.md', $markdown);
                copyMarkdownAlias(
                    $dossierDir . '/index.md',
                    $outputDir . '/' . $language . '/' . $slug . '.md'
                );
                file_put_contents($dossierDir . '/index.html', $html);
                $localizedCount++;
            } catch (\Dossier\UiStringsException $e) {
                throw $e;
            } catch (\Exception $e) {
                echo "❌ Error rendering {$language}/{$slug}: " . $e->getMessage() . "\n";
            }
        }
    }

    if ($jsonlFile) {
        fclose($jsonlFile);
    }

    // 4.4 Search index + search page
    echo "🔍 Generating search-index.json and search/index.html...\n";
    file_put_contents($outputDir . '/search-index.json', SearchIndexBuilder::toJson($searchDocs));

    $searchDir = $outputDir . '/search';
    @mkdir($searchDir, 0777, true);
    $themeForSearch = ThemeEngine::fromConfig($configPath, true, '../', $siteId, $presentation);
    $searchHtml = $themeForSearch->render('search', [
        'site_url' => $siteUrl,
        'canonical_url' => $siteUrl . 'search/',
        'sitename' => $sitename,
        'tagline' => $tagline,
        'page_title' => $sitename . ' - Search',
        'hero_title' => 'Search',
        'search_index_url' => '../search-index.json',
        'search_index_json' => null,
        'i18n_surface' => 'search',
    ]);
    file_put_contents($searchDir . '/index.html', $searchHtml);

    // 4.5 Render Categories
    echo "📁 Rendering Categories...\n";
    $categoryLabels = [];
    foreach ($allDossiers as $d) {
        foreach ($d['term_slugs'] ?? [] as $slug) {
            if ($slug === '') {
                continue;
            }
            if (!isset($categoryLabels[$slug]) && !empty($d['term_labels'][$slug])) {
                $categoryLabels[$slug] = $d['term_labels'][$slug];
            } elseif (!isset($categoryLabels[$slug])) {
                $categoryLabels[$slug] = ucfirst(str_replace('-', ' ', $slug));
            }
        }
    }
    $categories = array_keys($categoryLabels);

    $themeForCategory = ThemeEngine::fromConfig($configPath, true, '../../', $siteId, $presentation);
    foreach ($categories as $category) {
        $categoryDir = $outputDir . '/category/' . $category;
        @mkdir($categoryDir, 0777, true);
        $filteredDossiers = array_filter($allDossiers, function ($d) use ($category) {
            return in_array($category, $d['term_slugs'] ?? [], true);
        });
        $displayLabel = $categoryLabels[$category] ?? ucfirst(str_replace('-', ' ', $category));

        $html = $themeForCategory->render('archive', [
            'posts' => array_values($filteredDossiers),
            'dossiers' => array_values($filteredDossiers),
            'site_url' => $siteUrl,
            'canonical_url' => $siteUrl . 'category/' . $category . '/',
            'sitename' => $sitename,
            'page_title' => $sitename . ' - ' . $displayLabel,
            'hero_title' => $displayLabel,
            'category' => $category
        ], $category);
        file_put_contents($categoryDir . '/index.html', $html);
    }

    $generalCategoryDir = $outputDir . '/category';
    @mkdir($generalCategoryDir, 0777, true);
    $themeForGeneralCategory = ThemeEngine::fromConfig($configPath, true, '../', $siteId, $presentation);
    $generalHtml = $themeForGeneralCategory->render('archive', [
        'posts' => array_values($allDossiers),
        'dossiers' => array_values($allDossiers),
        'site_url' => $siteUrl,
        'canonical_url' => $siteUrl . 'category/',
        'sitename' => $sitename,
        'page_title' => $sitename . ' - Archives',
        'hero_title' => 'Archives',
        'category' => 'archives',
        'i18n_surface' => 'archive',
    ], 'archives');
    file_put_contents($generalCategoryDir . '/index.html', $generalHtml);

    // 4.6 Eligible localized home, canonical taxonomy archives, and search.
    // RSS, llms.txt, llms-full.txt, and content.jsonl intentionally remain default-only.
    foreach ($localizedMergedByLanguage as $language => $localizedAllRows) {
        $localizedDossiers = array_values(array_filter(
            $localizedAllRows,
            static fn (array $row): bool => empty($row['page'])
        ));
        $languageDir = $outputDir . '/' . $language;
        @mkdir($languageDir, 0777, true);

        $localizedHomeTheme = ThemeEngine::fromConfig(
            $configPath,
            true,
            LocalizedList::staticRelativeRoot('home'),
            $siteId,
            $presentation
        );
        $localizedHomeHtml = $localizedHomeTheme->render('index', [
            'dossiers' => $localizedDossiers,
            'posts' => $localizedDossiers,
            'site_url' => $siteUrl,
            'canonical_url' => $siteUrl . $language . '/',
            'hero_title' => $heroTitle,
            'hero_image' => $heroImage,
            'tagline' => $tagline,
            'sitename' => $sitename,
            'page_title' => $heroTitle,
            'body_class' => 'page-front',
            'language' => $language,
            'i18n_surface' => 'home',
        ]);
        file_put_contents($languageDir . '/index.html', $localizedHomeHtml);
        $localizedSurfaceCount++;

        $localizedSearchTheme = ThemeEngine::fromConfig(
            $configPath,
            true,
            LocalizedList::staticRelativeRoot('search'),
            $siteId,
            $presentation
        );
        $localizedSearchDocs = SearchIndexBuilder::buildFromDossiers(
            $localizedAllRows,
            $renderer,
            static fn (array $dossier): string => $localizedSearchTheme->contentUrl(
                $dossier,
                $language
            )
        );
        file_put_contents(
            $languageDir . '/search-index.json',
            SearchIndexBuilder::toJson($localizedSearchDocs)
        );
        $localizedSearchDir = $languageDir . '/search';
        @mkdir($localizedSearchDir, 0777, true);
        $localizedSearchHtml = $localizedSearchTheme->render('search', [
            'site_url' => $siteUrl,
            'canonical_url' => $siteUrl . $language . '/search/',
            'sitename' => $sitename,
            'tagline' => $tagline,
            'page_title' => $sitename . ' - Search',
            'hero_title' => 'Search',
            'search_index_url' => '../search-index.json',
            'search_index_json' => null,
            'language' => $language,
            'i18n_surface' => 'search',
        ]);
        file_put_contents($localizedSearchDir . '/index.html', $localizedSearchHtml);
        $localizedSurfaceCount++;

        foreach ($categories as $category) {
            $localizedCategoryDir = $languageDir . '/category/' . $category;
            @mkdir($localizedCategoryDir, 0777, true);
            $localizedCategoryRows = array_values(array_filter(
                $localizedDossiers,
                static fn (array $row): bool => in_array(
                    $category,
                    $row['term_slugs'] ?? [],
                    true
                )
            ));
            $displayLabel = $categoryLabels[$category]
                ?? ucfirst(str_replace('-', ' ', $category));
            $localizedCategoryTheme = ThemeEngine::fromConfig(
                $configPath,
                true,
                LocalizedList::staticRelativeRoot('archive', $category),
                $siteId,
                $presentation
            );
            $localizedCategoryHtml = $localizedCategoryTheme->render('archive', [
                'posts' => $localizedCategoryRows,
                'dossiers' => $localizedCategoryRows,
                'site_url' => $siteUrl,
                'canonical_url' => $siteUrl . $language . '/category/' . $category . '/',
                'sitename' => $sitename,
                'page_title' => $sitename . ' - ' . $displayLabel,
                'hero_title' => $displayLabel,
                'category' => $category,
                'language' => $language,
                'i18n_surface' => 'archive',
            ], $category);
            file_put_contents(
                $localizedCategoryDir . '/index.html',
                $localizedCategoryHtml
            );
            $localizedSurfaceCount++;
        }

        $localizedArchiveDir = $languageDir . '/category';
        @mkdir($localizedArchiveDir, 0777, true);
        $localizedArchiveTheme = ThemeEngine::fromConfig(
            $configPath,
            true,
            LocalizedList::staticRelativeRoot('archive'),
            $siteId,
            $presentation
        );
        $localizedArchiveHtml = $localizedArchiveTheme->render('archive', [
            'posts' => $localizedDossiers,
            'dossiers' => $localizedDossiers,
            'site_url' => $siteUrl,
            'canonical_url' => $siteUrl . $language . '/category/',
            'sitename' => $sitename,
            'page_title' => $sitename . ' - Archives',
            'hero_title' => 'Archives',
            'category' => 'archives',
            'language' => $language,
            'i18n_surface' => 'archive',
        ], 'archives');
        file_put_contents($localizedArchiveDir . '/index.html', $localizedArchiveHtml);
        $localizedSurfaceCount++;
    }

    # 5. Mirroring Static Assets from the active theme
    echo "\n📦 Mirroring Static Assets...\n";
    $theme = ThemeEngine::fromConfig($configPath, false, '', $siteId, $presentation);
    $appRoot = dirname($configPath);
    $contentDir = $ini['Paths']['content_dir'] ?? '../pencms-data/content';
    if (strpos($contentDir, '/') !== 0) {
        $contentDir = $appRoot . '/' . $contentDir;
    }
    $contentRelpath = (string) ($presentation['content_relpath'] ?? ('sites/' . $siteId));
    if ($activeTheme === 'custom') {
        $themeAssetsDir = rtrim($contentDir, '/') . '/' . $contentRelpath . '/theme/assets';
    } else {
        $themeAssetsDir = $ini['theme']['directory'] ?? 'apps/blog/themes';
        $themeAssetsDir = dirname($configPath) . '/' . $themeAssetsDir . '/' . $activeTheme . '/assets';
    }

    $assetDirs = ['css', 'js', 'fonts', 'images', 'svg'];
    foreach ($assetDirs as $dir) {
        $src = $themeAssetsDir . '/' . $dir;
        if (is_dir($src)) {
            echo "   - Copying theme {$dir}/\n";
            recurse_copy($src, $outputDir . '/' . $dir);
        }
    }

    // 5.5 Mirroring Shared Assets
    $sharedSrc = dirname($configPath) . '/apps/blog/shared';
    if (is_dir($sharedSrc)) {
        echo "   - Copying shared assets...\n";
        recurse_copy($sharedSrc, $outputDir . '/shared');
    }

    // 5.6 Per-site branding (logo / favicon / hero) from site assets
    $siteImagesDir = rtrim($contentDir, '/') . '/' . $contentRelpath . '/assets/images';
    $faviconExts = ['svg', 'ico', 'png', 'gif', 'webp', 'jpg', 'jpeg'];
    $brandingBases = [
        'logo' => ['png', 'svg', 'webp', 'jpg', 'gif'],
        'hero' => ['png', 'svg', 'webp', 'jpg', 'gif'],
    ];
    $siteFaviconSrc = null;
    $siteFaviconExt = null;
    if (is_dir($siteImagesDir)) {
        foreach ($faviconExts as $ext) {
            $src = $siteImagesDir . '/favicon.' . $ext;
            if (file_exists($src) && is_file($src)) {
                $siteFaviconSrc = $src;
                $siteFaviconExt = $ext;
                break;
            }
        }
        @mkdir($outputDir . '/images', 0777, true);
        foreach ($brandingBases as $base => $exts) {
            foreach ($exts as $ext) {
                $src = $siteImagesDir . '/' . $base . '.' . $ext;
                if (!file_exists($src)) {
                    continue;
                }
                echo "   - Copying site {$base}.{$ext}...\n";
                copy($src, $outputDir . '/images/' . $base . '.' . $ext);
                break; // one ext per basename
            }
        }
    }

    // Operator favicon always replaces theme-bundled images/favicon.*
    if ($siteFaviconSrc !== null && $siteFaviconExt !== null) {
        foreach ($faviconExts as $ext) {
            $themeFav = $outputDir . '/images/favicon.' . $ext;
            if (is_file($themeFav)) {
                unlink($themeFav);
            }
        }
        echo "   - Copying site favicon.{$siteFaviconExt} (overrides theme favicon)...\n";
        @mkdir($outputDir . '/images', 0777, true);
        copy($siteFaviconSrc, $outputDir . '/favicon.' . $siteFaviconExt);
        copy($siteFaviconSrc, $outputDir . '/images/favicon.' . $siteFaviconExt);
    }

    // 5.7 Reader-facing public vendor assets only (not admin Alpine / Marked / Traven editor)
    $publicVendorSrc = __DIR__ . '/../public/assets/vendor';
    if (is_dir($publicVendorSrc)) {
        echo "   - Copying public vendor assets (reader allowlist)...\n";
        copy_public_vendor_assets($publicVendorSrc, $outputDir . '/assets/vendor');
    }

    // 5.8 Shared web font registry (publicAsset('fonts/…') → {webRoot}assets/fonts/…)
    $publicFontsSrc = __DIR__ . '/../public/assets/fonts';
    if (is_dir($publicFontsSrc)) {
        echo "   - Copying public font registry...\n";
        recurse_copy($publicFontsSrc, $outputDir . '/assets/fonts');
    }

    // No install shared favicon fallback — sites without a favicon export with none

    // 6. Sync Shared Images via API
    echo "   - Analyzing referenced images in published dossiers...\n";
    $referencedImages = [];
    $extractImages = static function ($text) use (&$referencedImages) {
        if (empty($text) || !is_string($text)) {
            return;
        }
        if (preg_match_all('#images/[a-zA-Z0-9_\-\.\/]+#i', $text, $matches)) {
            foreach ($matches[0] as $match) {
                $path = parse_url($match, PHP_URL_PATH);
                if ($path) {
                    $referencedImages[strtolower(trim($path))] = true;
                }
            }
        }
    };

    $extractFromMetadata = static function ($data) use (&$extractImages, &$extractFromMetadata) {
        if (is_string($data)) {
            $extractImages($data);
        } elseif (is_array($data)) {
            foreach ($data as $val) {
                $extractFromMetadata($val);
            }
        }
    };

    $assetPages = $allPagesAndPosts;
    foreach ($localizedPagesByLanguage as $localizedPages) {
        foreach ($localizedPages as $localizedPage) {
            $assetPages[] = $localizedPage;
        }
    }
    foreach ($assetPages as $d) {
        $extractFromMetadata($d);
        try {
            $params = ['include_partials' => true];
            if (!empty($d['language'])) {
                $params['language'] = $d['language'];
                $params['live_only'] = true;
            }
            $page = $api->get("/pages/{$d['slug']}", $params);
            if (!empty($page['content'])) {
                $extractImages($page['content']);
            }
            if (!empty($page['partials']) && is_array($page['partials'])) {
                foreach ($page['partials'] as $partialContent) {
                    $extractImages($partialContent);
                }
            }
            if (!empty($page['frontmatter'])) {
                $extractFromMetadata($page['frontmatter']);
            }
        } catch (\Exception $e) {
            // Ignore
        }
    }

    $referencedImages['images/defaulthero.jpg'] = true;
    $referencedImages['images/og-default.jpg'] = true;

    $logoUrl = $theme->getLogoUrl();
    if (!empty($logoUrl)) {
        $extractImages($logoUrl);
    }

    echo "   - Found " . count($referencedImages) . " unique referenced images.\n";
    echo "   - Syncing images from site storage...\n";
    syncAssets($api, $outputDir . '/images', array_keys($referencedImages), $siteImagesDir);

    maybePingIndexNowAfterBuild($presentation, $siteUrl, $outputDir);

    return $count + $localizedCount + $localizedSurfaceCount + 1;
}

/**
 * Copy site images into dist/images/.
 * Prefers filesystem under content/sites/{id}/assets/images/ (multisite).
 * Falls back to API raw URLs with sites/{id}/assets/ prefix.
 *
 * @param list<string> $referencedImages logical paths like images/content/...
 */
function syncAssets($api, $targetDir, array $referencedImages = [], ?string $siteImagesDir = null) {
    if (!is_dir($targetDir)) {
        mkdir($targetDir, 0777, true);
    }

    $lookup = [];
    foreach ($referencedImages as $ref) {
        $lookup[strtolower(trim($ref))] = true;
    }

    $shouldCopy = static function (string $logicalPath) use ($lookup): bool {
        $lower = strtolower($logicalPath);
        // Limit content images to those referenced by published dossiers
        if (str_starts_with($lower, 'images/content/')) {
            return isset($lookup[$lower]);
        }
        return true;
    };

    // Preferred: copy from per-site assets on disk
    if ($siteImagesDir !== null && is_dir($siteImagesDir)) {
        $siteImagesDir = rtrim($siteImagesDir, '/');
        $iterator = new RecursiveIteratorIterator(
            new RecursiveDirectoryIterator($siteImagesDir, FilesystemIterator::SKIP_DOTS)
        );
        $copied = 0;
        foreach ($iterator as $fileInfo) {
            /** @var SplFileInfo $fileInfo */
            if (!$fileInfo->isFile()) {
                continue;
            }
            $abs = $fileInfo->getPathname();
            $relFromImages = ltrim(str_replace('\\', '/', substr($abs, strlen($siteImagesDir))), '/');
            if ($relFromImages === '') {
                continue;
            }
            $logical = 'images/' . $relFromImages;
            if (!$shouldCopy($logical)) {
                continue;
            }

            $localPath = rtrim($targetDir, '/') . '/' . $relFromImages;
            $localParent = dirname($localPath);
            if (!is_dir($localParent)) {
                mkdir($localParent, 0777, true);
            }

            echo "     ↓ Syncing: {$logical}\n";
            if (@copy($abs, $localPath)) {
                $copied++;
            } else {
                echo "   ⚠️ Failed to sync: {$logical}\n";
            }
        }
        echo "   - Copied {$copied} image(s) from site assets.\n";
        return;
    }

    // Fallback: list + download via API (site-scoped raw paths)
    try {
        $siteId = method_exists($api, 'getSiteId') ? $api->getSiteId() : 'default';
        $files = $api->get('/storage/list', ['path' => 'images', 'recursive' => true]);

        foreach ($files as $file) {
            if (str_ends_with($file, '/')) {
                continue;
            }

            $fullStoragePath = 'images/' . ltrim($file, '/');
            if (!$shouldCopy($fullStoragePath)) {
                continue;
            }

            $relativePath = ltrim(str_replace('images/', '', $file), '/');
            $localPath = rtrim($targetDir, '/') . '/' . $relativePath;

            $localParent = dirname($localPath);
            if (!is_dir($localParent)) {
                mkdir($localParent, 0777, true);
            }

            echo "     ↓ Syncing: images/" . $relativePath . "\n";

            $url = $api->getBaseUrl() . '/assets/raw/sites/' . rawurlencode($siteId) . '/assets/images/' . $file;
            $content = @file_get_contents($url);
            if ($content !== false) {
                file_put_contents($localPath, $content);
            } else {
                echo "   ⚠️ Failed to sync: images/" . $relativePath . "\n";
            }
        }
    } catch (\Exception $e) {
        echo "   ⚠️ Warning: Could not sync assets via API: " . $e->getMessage() . "\n";
    }
}

function recurse_copy($src, $dst) {
    $dir = opendir($src);
    @mkdir($dst);
    while (false !== ($file = readdir($dir))) {
        if (($file != '.') && ($file != '..')) {
            if (is_dir($src . '/' . $file)) {
                recurse_copy($src . '/' . $file, $dst . '/' . $file);
            } else {
                copy($src . '/' . $file, $dst . '/' . $file);
            }
        }
    }
    closedir($dir);
}

/**
 * Copy only vendor assets required by published theme pages.
 *
 * Excludes admin-only bundles (Alpine, Marked, Traven editor core/toolbar,
 * expand-embed editor plugin) and unused KaTeX sources/contribs.
 *
 * Paths are relative to public/assets/vendor/. Trailing '/' = copy directory tree.
 */
function copy_public_vendor_assets(string $vendorSrc, string $vendorDst): void
{
    $allowlist = [
        'katex/katex.min.js',
        'katex/katex.min.css',
        'katex/contrib/auto-render.min.js',
        'katex/fonts/',
        'mermaid/mermaid.min.js',
        'minisearch/minisearch.min.js',
        'minisearch/search-ui.js',
        'pencms/language-switcher.js',
        'traven/expand-embed.css',
        'traven/expand-embed-runtime.js',
    ];

    $copied = 0;
    $missing = [];

    foreach ($allowlist as $rel) {
        $isDir = substr($rel, -1) === '/';
        $rel = rtrim($rel, '/');
        $src = $vendorSrc . '/' . $rel;
        $dst = $vendorDst . '/' . $rel;

        if ($isDir) {
            if (!is_dir($src)) {
                $missing[] = $rel . '/';
                continue;
            }
            recurse_copy($src, $dst);
            $copied++;
            continue;
        }

        if (!is_file($src)) {
            $missing[] = $rel;
            continue;
        }
        $parent = dirname($dst);
        if (!is_dir($parent)) {
            mkdir($parent, 0777, true);
        }
        if (copy($src, $dst)) {
            $copied++;
        }
    }

    echo "     → {$copied} allowlisted path(s) copied.\n";
    if ($missing) {
        echo "     ⚠️ Missing allowlisted path(s): " . implode(', ', $missing) . "\n";
    }
}
