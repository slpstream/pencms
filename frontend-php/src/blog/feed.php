<?php

/**
 * Site-wide RSS 2.0 feed for PHP preview.
 * Public path (ThemeEngine): /blog/feed.xml → this script.
 */

require_once __DIR__ . '/../core/DossierDiscovery.php';
require_once __DIR__ . '/../core/ThemeEngine.php';
require_once __DIR__ . '/../core/RssFeedBuilder.php';
require_once __DIR__ . '/../core/PublicSiteContext.php';

use Dossier\DossierDiscovery;
use Dossier\RssFeedBuilder;
use Dossier\PublicSiteContext;

$ctx = PublicSiteContext::bootstrap();
$api = $ctx->newApiClient();
$theme = $ctx->newThemeEngine();
$p = $ctx->presentation;

$sitename = $p['sitename'];
$tagline = $p['tagline'];

$siteRecord = $ctx->registry->getSite($ctx->siteId);
$siteDomain = '';
if ($siteRecord !== null && !empty($siteRecord['domain'])) {
    $siteDomain = (string) $siteRecord['domain'];
}

if (trim($siteDomain) !== '') {
    $siteUrl = RssFeedBuilder::normalizeSiteUrl($siteDomain);
} else {
    $https = !empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off';
    $scheme = $https ? 'https' : 'http';
    $host = $_SERVER['HTTP_HOST'] ?? 'localhost';
    $siteUrl = RssFeedBuilder::normalizeSiteUrl($scheme . '://' . $host . '/');
}

$discovery = new DossierDiscovery($api);
$dossiers = $discovery->getAllDossiers('blog', false);
// RSS stays chronological; pin-first listing order must not affect lastBuildDate.
usort($dossiers, function ($a, $b) {
    return strtotime($b['date'] ?? '') <=> strtotime($a['date'] ?? '');
});

$xml = RssFeedBuilder::build(
    $dossiers,
    $siteUrl,
    $sitename,
    $tagline,
    $theme->getLogoUrl()
);

header('Content-Type: application/rss+xml; charset=UTF-8');
header('Cache-Control: no-cache');
echo $xml;
