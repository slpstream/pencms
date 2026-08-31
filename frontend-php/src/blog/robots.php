<?php

/**
 * Site-scoped robots.txt for PHP preview / dynamic front.
 * Public path: /robots.txt → this script (via router.php).
 */

require_once __DIR__ . '/../core/PublicSiteContext.php';

use Dossier\PublicSiteContext;

$ctx = PublicSiteContext::bootstrap();
$p = $ctx->presentation;

$custom = trim((string) ($p['robots_txt'] ?? ''));
if ($custom !== '') {
    $body = $custom;
    if (!str_ends_with($body, "\n")) {
        $body .= "\n";
    }
} else {
    $robotsIndex = array_key_exists('robots_index', $p)
        ? (bool) $p['robots_index']
        : true;
    $sitemapEnabled = array_key_exists('sitemap_enabled', $p)
        ? (bool) $p['sitemap_enabled']
        : true;

    $lines = [
        'User-agent: *',
        $robotsIndex ? 'Allow: /' : 'Disallow: /',
    ];

    if ($sitemapEnabled) {
        $siteRecord = $ctx->registry->getSite($ctx->siteId);
        $domain = '';
        if ($siteRecord !== null && !empty($siteRecord['domain'])) {
            $domain = trim((string) $siteRecord['domain']);
        }
        if ($domain !== '') {
            $lines[] = 'Sitemap: https://' . $domain . '/sitemap.xml';
        }
    }

    $body = implode("\n", $lines) . "\n";
}

header('Content-Type: text/plain; charset=UTF-8');
header('Cache-Control: no-cache');
echo $body;
