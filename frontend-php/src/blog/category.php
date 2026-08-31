<?php

require_once __DIR__ . '/../core/DossierDiscovery.php';
require_once __DIR__ . '/../core/InternalAPIClient.php';
require_once __DIR__ . '/../core/ShortcodeProcessor.php';
require_once __DIR__ . '/../core/ThemeEngine.php';
require_once __DIR__ . '/../core/TaxonomySlug.php';
require_once __DIR__ . '/../core/PublicSiteContext.php';
require_once __DIR__ . '/../core/LocalizedList.php';

use Dossier\DossierDiscovery;
use Dossier\ShortcodeProcessor;
use Dossier\TaxonomySlug;
use Dossier\PublicSiteContext;
use Dossier\LocalizedList;

$category = isset($_GET['category']) ? TaxonomySlug::termToCategorySlug($_GET['category']) : null;
if ($category === '') {
    $category = null;
}

$ctx = PublicSiteContext::bootstrap();
$api = $ctx->newApiClient();
$theme = $ctx->newThemeEngine();

$asset_path = $api->getAssetBaseUrl();
$theme->setContentBaseUrl($asset_path);
ShortcodeProcessor::$basePath = $asset_path;

$discovery = new DossierDiscovery($api);
$listLanguage = LocalizedList::queryLanguage($_GET, $ctx->presentation);
if ($listLanguage !== null) {
    $eligible = $discovery->getAllDossiers('blog', true, $listLanguage, 'none');
    if ($eligible === []) {
        http_response_code(404);
        echo 'Not Found';
        exit;
    }
    $dossiers = $discovery->getAllDossiers('blog', false, $listLanguage, 'default');
} else {
    $dossiers = $discovery->getAllDossiers('blog');
}

$sitename = $ctx->presentation['sitename'];

if ($category) {
    // Filter dossiers by any taxonomy term slug (primary category + taxonomy_*)
    $filteredDossiers = array_filter($dossiers, function($d) use ($category) {
        return in_array($category, $d['term_slugs'] ?? [], true);
    });
    $filteredDossiers = array_values($filteredDossiers);

    $displayLabel = null;
    foreach ($filteredDossiers as $d) {
        if (!empty($d['term_labels'][$category])) {
            $displayLabel = $d['term_labels'][$category];
            break;
        }
    }
    if ($displayLabel === null) {
        $displayLabel = ucfirst(str_replace('-', ' ', $category));
    }

    $page_title = $sitename . ' - ' . $displayLabel;
    $hero_title = $displayLabel;
} else {
    $filteredDossiers = $dossiers;
    $page_title = $sitename . ' - Archives';
    $hero_title = 'Archives';
    $category = 'archives';
}

// Render the archive template via ThemeEngine
$canonicalCategory = $category === 'archives' ? null : $category;
$canonicalPath = $listLanguage !== null
    ? LocalizedList::publicPath(
        '/blog/',
        $listLanguage,
        'archive',
        $canonicalCategory
    )
    : '/blog/category/'
        . ($canonicalCategory !== null ? rawurlencode($canonicalCategory) . '/' : '');
$pageData = [
    'canonical_url' => $ctx->canonicalUrl($canonicalPath),
    'posts' => array_values($filteredDossiers),
    'dossiers' => array_values($filteredDossiers), // Keep for backward compatibility just in case
    'page_title' => $page_title,
    'hero_title' => $hero_title,
    'sitename' => $sitename,
    'tagline' => $ctx->presentation['tagline'],
    'meta_description' => $ctx->presentation['meta_description'] !== '' ? $ctx->presentation['meta_description'] : null,
    'keywords' => $ctx->presentation['keywords'] !== '' ? $ctx->presentation['keywords'] : null,
    'title_template' => $ctx->presentation['title_template'] !== '' ? $ctx->presentation['title_template'] : null,
    'category' => $category,
    'i18n_surface' => 'archive',
];
if ($listLanguage !== null) {
    $pageData['language'] = $listLanguage;
}
echo $theme->render('archive', $pageData, $category);
