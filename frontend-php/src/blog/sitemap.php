<?php

/**
 * Site-scoped sitemap.xml for PHP preview / dynamic front.
 * Public path: /sitemap.xml → this script (via router.php).
 */

require_once __DIR__ . '/../core/DossierDiscovery.php';
require_once __DIR__ . '/../core/RssFeedBuilder.php';
require_once __DIR__ . '/../core/SitemapBuilder.php';
require_once __DIR__ . '/../core/PublicSiteContext.php';

use Dossier\DossierDiscovery;
use Dossier\RssFeedBuilder;
use Dossier\SitemapBuilder;
use Dossier\PublicSiteContext;

$ctx = PublicSiteContext::bootstrap();
$p = $ctx->presentation;

$sitemapEnabled = array_key_exists('sitemap_enabled', $p)
    ? (bool) $p['sitemap_enabled']
    : true;

if (!$sitemapEnabled) {
    http_response_code(404);
    exit();
}

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

$discovery = new DossierDiscovery($ctx->newApiClient());
$dossiers = $discovery->getAllDossiers('blog', true);
$localizedDossiersByLanguage = [];
if (!empty($p['i18n_active'])) {
    $defaultLanguage = strtolower((string) ($p['language'] ?? 'en'));
    foreach (($p['languages'] ?? []) as $configuredLanguage) {
        $language = strtolower((string) $configuredLanguage);
        if ($language === '' || $language === $defaultLanguage) {
            continue;
        }
        $localizedDossiersByLanguage[$language] = $discovery->getAllDossiers(
            'blog',
            true,
            $language,
            'none'
        );
    }
}

$xml = SitemapBuilder::build(
    $dossiers,
    $siteUrl,
    $localizedDossiersByLanguage,
    (string) ($p['language'] ?? 'en')
);

header('Content-Type: application/xml; charset=UTF-8');
header('Cache-Control: no-cache');
echo $xml;
