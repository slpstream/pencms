<?php

require_once __DIR__ . '/../core/DossierDiscovery.php';
require_once __DIR__ . '/../core/InternalAPIClient.php';
require_once __DIR__ . '/../core/ShortcodeProcessor.php';
require_once __DIR__ . '/../core/ThemeEngine.php';
require_once __DIR__ . '/../core/PublicSiteContext.php';
require_once __DIR__ . '/../core/LocalizedList.php';

use Dossier\DossierDiscovery;
use Dossier\ShortcodeProcessor;
use Dossier\PublicSiteContext;
use Dossier\LocalizedList;

$ctx = PublicSiteContext::bootstrap();
$api = $ctx->newApiClient();
$theme = $ctx->newThemeEngine();

$asset_path = $api->getAssetBaseUrl();
$theme->setContentBaseUrl($asset_path);
ShortcodeProcessor::$basePath = $asset_path;

$discovery = new DossierDiscovery($api);
$p = $ctx->presentation;
$listLanguage = LocalizedList::queryLanguage($_GET, $p);
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

// Render the index template via ThemeEngine
$canonicalPath = $listLanguage !== null
    ? LocalizedList::publicPath('/blog/', $listLanguage, 'home')
    : '/blog/';
$pageData = [
    'canonical_url' => $ctx->canonicalUrl($canonicalPath),
    'dossiers' => $dossiers,
    'posts' => $dossiers,
    'page_title' => $p['hero_title'],
    'hero_title' => $p['hero_title'],
    'hero_image' => $p['hero_image'],
    'tagline' => $p['tagline'],
    'sitename' => $p['sitename'],
    'meta_description' => $p['meta_description'] !== '' ? $p['meta_description'] : null,
    'keywords' => $p['keywords'] !== '' ? $p['keywords'] : null,
    'title_template' => $p['title_template'] !== '' ? $p['title_template'] : null,
    'body_class' => 'page-front',
];
if ($listLanguage !== null) {
    $pageData['language'] = $listLanguage;
}
echo $theme->render('index', $pageData);
