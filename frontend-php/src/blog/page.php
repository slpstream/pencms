<?php

require_once __DIR__ . '/../../vendor/autoload.php';
require_once __DIR__ . '/../core/PostRenderer.php';
require_once __DIR__ . '/../core/ThemeEngine.php';
require_once __DIR__ . '/../core/PublicSiteContext.php';
require_once __DIR__ . '/../core/LocalizedDetail.php';

use Dossier\PostRenderer;
use Dossier\PublicSiteContext;
use Dossier\LocalizedDetail;

$slug = $_GET['slug'] ?? $_GET['page'] ?? null;

if (!$slug) {
    http_response_code(404);
    echo "Page not specified.";
    exit;
}

$ctx = PublicSiteContext::bootstrap();
$api = $ctx->newApiClient();
$theme = $ctx->newThemeEngine();
$language = LocalizedDetail::queryLanguage($_GET, $ctx->presentation);
$hasLanguageQuery = LocalizedDetail::hasLanguageQuery($_GET);
$invalidLanguageQuery = $hasLanguageQuery
    && $language === null
    && strtolower(str_replace('_', '-', trim((string) ($_GET['language'] ?? $_GET['lang'] ?? ''))))
        !== strtolower((string) ($ctx->presentation['language'] ?? 'en'));

$asset_path = $api->getAssetBaseUrl();
$theme->setContentBaseUrl($asset_path);
\Dossier\ShortcodeProcessor::$basePath = $asset_path;

$renderer = new PostRenderer($api, !empty($ctx->presentation['comments_enabled']));
$sitename = $ctx->presentation['sitename'];

try {
    if ($invalidLanguageQuery) {
        throw new \Exception('Requested language is not active for this site.');
    }
    $pageData = $renderer->renderPage(
        'general',
        $slug,
        $language,
        $language !== null
    );
    
    $pageContent = '';
    foreach ($pageData['posts'] as $p) {
        $pageContent .= $p['content_html'];
    }
    $canonicalPath = $language !== null
        ? LocalizedDetail::publicPath('/blog/', $language, $slug)
        : '/blog/page.php?slug=' . rawurlencode($slug);

    echo $theme->render('page', [
        'canonical_url' => $ctx->canonicalUrl($canonicalPath),
        'hero_title' => $pageData['hero_title'] ?? $slug,
        'page_content' => $pageContent,
        'hero_image' => $pageData['hero_image'] ?? '',
        'deck' => $pageData['deck'] ?? '',
        'page_title' => $pageData['seo']['title'] ?? $slug,
        'sitename' => $sitename,
        'tagline' => $ctx->presentation['tagline'] ?? '',
        'slug' => $slug,
        'language' => $pageData['language'] ?? null,
        'translation_group' => $pageData['translation_group'] ?? null,
        'translations' => $pageData['translations'] ?? [],
        'i18n_current_live' => $pageData['i18n_current_live'] ?? false,
        'is_page' => true,
        'meta_description' => ($pageData['seo']['og_description'] ?? null)
            ?: ($ctx->presentation['meta_description'] !== '' ? $ctx->presentation['meta_description'] : null),
        'keywords' => $ctx->presentation['keywords'] !== '' ? $ctx->presentation['keywords'] : null,
        'title_template' => $ctx->presentation['title_template'] !== '' ? $ctx->presentation['title_template'] : null,
    ], $slug);
} catch (\Dossier\UiStringsException $e) {
    error_log($e->getMessage());
    http_response_code(500);
    echo 'Render configuration error.';
} catch (\Exception $e) {
    http_response_code(404);
    echo $theme->render('page', [
        'page_title' => 'Page Not Found',
        'hero_title' => 'Page Not Found',
        'page_content' => '<p>The requested page could not be found.</p>',
        'sitename' => $sitename,
        'tagline' => $ctx->presentation['tagline'] ?? '',
    ]);
}
