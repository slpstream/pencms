<?php

/**
 * Public search page for PHP preview.
 * Public path (ThemeEngine): /blog/search.php (also /blog/search/ via router).
 */

require_once __DIR__ . '/../core/DossierDiscovery.php';
require_once __DIR__ . '/../core/ThemeEngine.php';
require_once __DIR__ . '/../core/SearchIndexBuilder.php';
require_once __DIR__ . '/../core/PublicSiteContext.php';
require_once __DIR__ . '/../core/LocalizedList.php';
require_once __DIR__ . '/../core/PostRenderer.php';

use Dossier\DossierDiscovery;
use Dossier\SearchIndexBuilder;
use Dossier\PublicSiteContext;
use Dossier\LocalizedList;
use Dossier\PostRenderer;

$ctx = PublicSiteContext::bootstrap();
$api = $ctx->newApiClient();
$theme = $ctx->newThemeEngine();
$discovery = new DossierDiscovery($api);
$p = $ctx->presentation;
$listLanguage = LocalizedList::queryLanguage($_GET, $ctx->presentation);
if ($listLanguage !== null) {
    $eligible = $discovery->getAllDossiers('blog', true, $listLanguage, 'none');
    if ($eligible === []) {
        http_response_code(404);
        echo 'Not Found';
        exit;
    }
    $dossiers = $discovery->getAllDossiers('blog', true, $listLanguage, 'default');
} else {
    $dossiers = $discovery->getAllDossiers('blog', true);
}
$renderer = new PostRenderer($api);
$docs = SearchIndexBuilder::buildFromDossiers(
    $dossiers,
    $renderer,
    static fn (array $dossier): string => $theme->contentUrl(
        $dossier,
        $listLanguage
    ),
    $listLanguage === null && !empty($p['i18n_active'])
        ? strtolower((string) ($p['language'] ?? 'en'))
        : null
);
$indexJson = SearchIndexBuilder::toJson($docs);

$canonicalPath = $listLanguage !== null
    ? LocalizedList::publicPath('/blog/', $listLanguage, 'search')
    : '/blog/search/';
$pageData = [
    'canonical_url' => $ctx->canonicalUrl($canonicalPath),
    'sitename' => $p['sitename'],
    'tagline' => $p['tagline'],
    'page_title' => $p['sitename'] . ' - Search',
    'hero_title' => 'Search',
    'meta_description' => $p['meta_description'] !== '' ? $p['meta_description'] : null,
    'keywords' => $p['keywords'] !== '' ? $p['keywords'] : null,
    'title_template' => $p['title_template'] !== '' ? $p['title_template'] : null,
    'search_index_url' => '',
    'search_index_json' => $indexJson,
    'i18n_surface' => 'search',
];
if ($listLanguage !== null) {
    $pageData['language'] = $listLanguage;
}
echo $theme->render('search', $pageData);
