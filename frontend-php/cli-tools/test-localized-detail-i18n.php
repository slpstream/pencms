<?php

declare(strict_types=1);

require_once __DIR__ . '/../src/core/LocalizedDetail.php';
require_once __DIR__ . '/../src/core/PublicSiteContext.php';
require_once __DIR__ . '/../src/core/PostRenderer.php';
require_once __DIR__ . '/../src/core/ShortcodeProcessor.php';

use Dossier\InternalAPIClient;
use Dossier\ExpandResolver;
use Dossier\LocalizedDetail;
use Dossier\PostRenderer;
use Dossier\PublicSiteContext;
use Dossier\ShortcodeProcessor;

$passed = 0;
$failed = 0;
$failures = [];

function check(bool $condition, string $label): void
{
    global $passed, $failed, $failures;
    if ($condition) {
        $passed++;
        return;
    }
    $failed++;
    $failures[] = $label;
}

final class LocalizedFakeApi extends InternalAPIClient
{
    /** @var list<array{endpoint: string, params: array}> */
    public array $calls = [];

    public function __construct()
    {
    }

    public function get($endpoint, $params = [])
    {
        $this->calls[] = ['endpoint' => $endpoint, 'params' => $params];
        if (
            $endpoint === '/pages/summary'
            && ($params['language'] ?? null) === 'fr'
            && ($params['live_only'] ?? false)
        ) {
            return [
                'frontmatter' => [
                    'name' => 'Résumé',
                    'summary' => 'Résumé français.',
                    'status' => 'published',
                    'published' => true,
                ],
                'content' => 'Corps résumé.',
                'composite' => false,
                'partials' => [],
            ];
        }
        if ($endpoint !== '/pages/about' || ($params['language'] ?? null) !== 'fr') {
            throw new Exception('not found');
        }
        return [
            'id' => 'about',
            'language' => 'fr',
            'translation_group' => 'tg_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
            'translations' => [
                [
                    'language' => 'en',
                    'status' => 'published',
                    'published' => true,
                    'needs_review' => false,
                ],
            ],
            'frontmatter' => [
                'name' => 'À propos',
                'hero_title' => 'À propos',
                'category' => '',
                'page' => true,
                'status' => 'published',
                'published' => true,
                'composite' => true,
                'posts' => [
                    ['id' => 'index'],
                    ['id' => 'bio', 'title' => 'Biographie'],
                ],
            ],
            'content' => 'Corps français.',
            'file_path' => 'sites/default/about/fr/index.md',
            'composite' => true,
            'partials' => ['bio' => 'Partiel français exact.'],
        ];
    }

    public function assetExists($path)
    {
        return true;
    }

    public function getSiteId(): string
    {
        return 'default';
    }
}

$active = [
    'language' => 'en',
    'languages' => ['en', 'fr'],
    'i18n_active' => true,
];
$inactive = [
    'language' => 'en',
    'languages' => [],
    'i18n_active' => false,
];
$otherSite = [
    'language' => 'en',
    'languages' => ['en', 'de'],
    'i18n_active' => true,
];

$match = LocalizedDetail::matchPath('/blog/fr/about/', '/blog/', $active);
check($match === ['language' => 'fr', 'slug' => 'about'], 'matches exact preview path');
check(
    LocalizedDetail::matchPath('/blog/en/about/', '/blog/', $active) === null,
    'default language prefix is rejected'
);
check(
    LocalizedDetail::matchPath('/blog/fr/about/extra/', '/blog/', $active) === null,
    'additional path depth is rejected'
);
check(
    LocalizedDetail::matchPath('/blog/fr/about/', '/blog/', $inactive) === null,
    'inactive gate rejects localized path'
);
check(
    LocalizedDetail::matchPath('/blog/fr/about/', '/blog/', $otherSite) === null,
    'site-specific language config is isolated'
);
check(
    LocalizedDetail::matchPath('/fr/about/', '/', $active)
        === ['language' => 'fr', 'slug' => 'about'],
    'root public base matches localized detail'
);
check(
    LocalizedDetail::queryLanguage(['lang' => 'fr'], $active) === 'fr',
    'legacy lang query resolves exact sibling'
);
check(
    LocalizedDetail::queryLanguage(['language' => 'en'], $active) === null,
    'default language query remains unlocalized'
);
check(
    LocalizedDetail::queryLanguage([], $active) === null,
    'existing query URL without language is unchanged'
);
check(
    LocalizedDetail::publicPath('/blog/', 'fr', 'about') === '/blog/fr/about/',
    'preview public base is preserved'
);
check(
    LocalizedDetail::publicPath('/', 'fr', 'about') === '/fr/about/',
    'static public base is preserved'
);
$oldHost = $_SERVER['HTTP_HOST'] ?? null;
$oldHttps = $_SERVER['HTTPS'] ?? null;
$oldForwardedProto = $_SERVER['HTTP_X_FORWARDED_PROTO'] ?? null;
$_SERVER['HTTP_HOST'] = 'cms.example';
$_SERVER['HTTPS'] = 'on';
$_SERVER['HTTP_X_FORWARDED_PROTO'] = 'https';
$publicContext = (new ReflectionClass(PublicSiteContext::class))
    ->newInstanceWithoutConstructor();
check(
    $publicContext->canonicalUrl('/blog/fr/about/')
        === 'https://cms.example/blog/fr/about/',
    'dynamic canonical URL preserves the localized public path'
);
if ($oldHost === null) {
    unset($_SERVER['HTTP_HOST']);
} else {
    $_SERVER['HTTP_HOST'] = $oldHost;
}
if ($oldHttps === null) {
    unset($_SERVER['HTTPS']);
} else {
    $_SERVER['HTTPS'] = $oldHttps;
}
if ($oldForwardedProto === null) {
    unset($_SERVER['HTTP_X_FORWARDED_PROTO']);
} else {
    $_SERVER['HTTP_X_FORWARDED_PROTO'] = $oldForwardedProto;
}

$api = new LocalizedFakeApi();
$renderer = new PostRenderer($api);
$page = $renderer->renderPage('general', 'about', 'fr', true);
check($page['language'] === 'fr', 'renderer propagates exact response language');
check($page['is_page'] === true, 'localized route can select page template');
check(
    $page['translation_group'] === 'tg_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
        && $page['translations'][0]['language'] === 'en'
        && $page['i18n_current_live'] === true,
    'renderer propagates the existing published sibling relationship'
);
check(count($page['posts']) === 2, 'localized composite includes controller and partial');
check(
    str_contains($page['posts'][1]['content_html'], 'artiel français exact.'),
    'localized composite uses locale-local partial'
);
check(
    ($api->calls[0]['params']['include_partials'] ?? false) === true
        && ($api->calls[0]['params']['language'] ?? null) === 'fr'
        && ($api->calls[0]['params']['live_only'] ?? false) === true,
    'renderer requests exact public locale with partials'
);

$markdown = $renderer->renderMarkdown('general', 'about', 'fr', true);
check(str_contains($markdown, 'Corps français.'), 'localized Markdown uses exact body');
check(str_contains($markdown, 'Partiel français exact.'), 'localized Markdown uses exact partial');

$missingRaised = false;
try {
    $renderer->renderPage('general', 'missing', 'fr', true);
} catch (Exception $e) {
    $missingRaised = true;
}
check($missingRaised, 'missing exact sibling does not fall back');

$expandApi = new LocalizedFakeApi();
$expand = new ExpandResolver($expandApi, 'fr', 'Lire la suite');
$expanded = $expand->resolve('summary', null, 'expand', 'summary');
check(
    $expanded !== null
        && str_contains($expanded, 'Résumé français.')
        && str_contains($expanded, 'Lire la suite'),
    'localized expand uses exact locale and translated CTA'
);
$expandCall = $expandApi->calls[0] ?? [];
check(
    ($expandCall['params']['language'] ?? null) === 'fr'
        && ($expandCall['params']['live_only'] ?? false) === true,
    'localized expand requests an exact live sibling'
);

ShortcodeProcessor::$basePath = '/api/assets/raw/';
check(
    ShortcodeProcessor::resolveContentUrl('about') === 'post.php?slug=about',
    'default dynamic content URL remains query-based'
);

define('STATIC_BUILD', true);
ShortcodeProcessor::$basePath = LocalizedDetail::staticRelativeRoot();
check(
    ShortcodeProcessor::resolveAsset('images/content/photo.jpg')
        === '../../images/content/photo.jpg',
    'localized static asset uses additional URL depth'
);
check(
    ShortcodeProcessor::resolveContentUrl('other') === '../../other/',
    'localized static content link reaches site root'
);

foreach ($failures as $failure) {
    fwrite(STDERR, "[FAIL] {$failure}\n");
}
echo "Localized detail i18n: {$passed} passed, {$failed} failed\n";
exit($failed > 0 ? 1 : 0);
