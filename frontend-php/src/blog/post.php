<?php

require_once __DIR__ . '/../core/PostRenderer.php';
require_once __DIR__ . '/../core/InternalAPIClient.php';
require_once __DIR__ . '/../core/ThemeEngine.php';
require_once __DIR__ . '/../core/PublicSiteContext.php';
require_once __DIR__ . '/../core/LocalizedDetail.php';

use Dossier\PostRenderer;
use Dossier\ShortcodeProcessor;
use Dossier\PublicSiteContext;
use Dossier\LocalizedDetail;

// Simple routing logic: Discover section by slug
$slug = $_GET['slug'] ?? $_GET['page'] ?? $_GET['p'] ?? 'archangel';
$section = isset($_GET['section']) ? strtolower(trim($_GET['section'])) : null;

$ctx = PublicSiteContext::bootstrap();
$api = $ctx->newApiClient();
$theme = $ctx->newThemeEngine();
$language = LocalizedDetail::queryLanguage($_GET, $ctx->presentation);
$hasLanguageQuery = LocalizedDetail::hasLanguageQuery($_GET);
$invalidLanguageQuery = $hasLanguageQuery
    && $language === null
    && strtolower(str_replace('_', '-', trim((string) ($_GET['language'] ?? $_GET['lang'] ?? ''))))
        !== strtolower((string) ($ctx->presentation['language'] ?? 'en'));
$localizedPublicOnly = $language !== null;
$isLocalizedPath = !empty($_GET['_localized_detail']);

// Initialize paths
$asset_path = $api->getAssetBaseUrl();
$theme->setContentBaseUrl($asset_path);
ShortcodeProcessor::$basePath = $asset_path;

// Smart Discovery: If section is not provided, we can either fetch it from the API or assume it's valid
if (!$section) {
    try {
        $params = [];
        if ($language !== null) {
            $params['language'] = $language;
            $params['live_only'] = true;
        }
        $page = $api->get("/pages/{$slug}", $params);
        $section = $page['frontmatter']['category'] ?? $page['frontmatter']['type'] ?? 'event';
    } catch (\Exception $e) {
        $section = 'event';
    }
}
$section = strtolower(trim($section));

$renderer = new PostRenderer($api, !empty($ctx->presentation['comments_enabled']));

$tagline = $ctx->presentation['tagline'] ?? '';
$sitename = $ctx->presentation['sitename'];

try {
    if ($invalidLanguageQuery) {
        throw new \Exception('Requested language is not active for this site.');
    }

    // Check if the client is requesting Markdown (Markdown for Agents)
    $acceptHeader = $_SERVER['HTTP_ACCEPT'] ?? '';
    if (stripos($acceptHeader, 'text/markdown') !== false) {
        $markdown = $renderer->renderMarkdown(
            $section,
            $slug,
            $language,
            $localizedPublicOnly
        );
        
        $tokenCount = (int) round(str_word_count($markdown) / 0.75);

        header('Content-Type: text/markdown; charset=utf-8');
        header('Vary: Accept');
        header("x-markdown-tokens: {$tokenCount}");
        header('Content-Signal: ai-train=yes, search=yes, ai-input=yes');
        
        echo $markdown;
        exit;
    }

    $pageData = $renderer->renderPage(
        $section,
        $slug,
        $language,
        $localizedPublicOnly
    );
    
    // Extract SEO variables for the theme contract
    $pageMeta = $pageData['seo']['og_description'] ?? null;
    $siteMeta = $ctx->presentation['meta_description'] !== ''
        ? $ctx->presentation['meta_description']
        : null;
    $seoData = [
        'page_title' => $pageData['seo']['title'] ?? null,
        'og_title' => $pageData['seo']['og_title'] ?? null,
        'og_description' => $pageData['seo']['og_description'] ?? null,
        'og_image' => $pageData['seo']['og_image'] ?? null,
        'meta_description' => ($pageMeta !== null && $pageMeta !== '') ? $pageMeta : $siteMeta,
        'keywords' => $ctx->presentation['keywords'] !== ''
            ? $ctx->presentation['keywords']
            : null,
        'title_template' => $ctx->presentation['title_template'] !== ''
            ? $ctx->presentation['title_template']
            : null,
    ];
    $canonicalPath = $language !== null
        ? LocalizedDetail::publicPath('/blog/', $language, $slug)
        : '/blog/post.php?slug=' . rawurlencode($slug)
            . ($section !== '' ? '&section=' . rawurlencode($section) : '');

    $renderData = array_merge($pageData, $seoData, [
        'canonical_url' => $ctx->canonicalUrl($canonicalPath),
        'tagline' => $tagline,
        'sitename' => $sitename,
        'slug' => $slug,
        'section' => $section
    ]);

    if ($isLocalizedPath && !empty($pageData['is_page'])) {
        $pageContent = '';
        foreach ($pageData['posts'] as $post) {
            $pageContent .= $post['content_html'];
        }
        $renderData['page_content'] = $pageContent;
        echo $theme->render('page', $renderData, $slug);
    } else {
        // Existing post.php query URLs retain the post template.
        echo $theme->render('post', $renderData);
    }

} catch (\Dossier\UiStringsException $e) {
    error_log($e->getMessage());
    http_response_code(500);
    echo 'Render configuration error.';
} catch (\Exception $e) {
    // Basic error handling
    http_response_code(404);
    echo $theme->render('post', [
        'page_title' => '404 - Not Found',
        'hero_title' => 'Dossier Not Found',
        'hero_image' => 'images/defaulthero.jpg',
        'tagline' => $tagline,
        'sitename' => $sitename,
        'posts' => [[
            'id' => '404',
            'title' => 'Access Denied or File Missing',
            'content_html' => "<p>The requested dossier could not be retrieved from the archives.</p><p>{$e->getMessage()}</p>",
            'metadata' => ['ERROR 404', 'CLASSIFIED'],
            'tags' => []
        ]]
    ]);
}
