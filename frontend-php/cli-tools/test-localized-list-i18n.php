<?php

declare(strict_types=1);

require_once __DIR__ . '/../vendor/autoload.php';
require_once __DIR__ . '/../src/core/DossierDiscovery.php';
require_once __DIR__ . '/../src/core/InternalAPIClient.php';
require_once __DIR__ . '/../src/core/LocalizedList.php';
require_once __DIR__ . '/../src/core/SearchIndexBuilder.php';
require_once __DIR__ . '/../src/core/ThemeEngine.php';

use Dossier\DossierDiscovery;
use Dossier\InternalAPIClient;
use Dossier\LocalizedList;
use Dossier\SearchIndexBuilder;
use Dossier\ThemeEngine;

$passed = 0;
$failed = 0;
$failures = [];

function checkList(bool $condition, string $label): void
{
    global $passed, $failed, $failures;
    if ($condition) {
        $passed++;
        return;
    }
    $failed++;
    $failures[] = $label;
}

function removeListTree(string $path): void
{
    if (!is_dir($path)) {
        return;
    }
    foreach (scandir($path) ?: [] as $item) {
        if ($item === '.' || $item === '..') {
            continue;
        }
        $child = $path . '/' . $item;
        if (is_dir($child)) {
            removeListTree($child);
        } else {
            unlink($child);
        }
    }
    rmdir($path);
}

final class MergedListFakeApi extends InternalAPIClient
{
    public function __construct()
    {
    }

    public function get($endpoint, $params = [])
    {
        if ($endpoint !== '/pages/') {
            throw new Exception('not found');
        }
        return [
            [
                'id' => 'first',
                'frontmatter' => [
                    'name' => 'Premier',
                    'category' => 'summer',
                    'domain' => 'blog',
                    'status' => 'published',
                    'published' => true,
                    'date' => '2020-01-01',
                ],
                'content' => 'Français',
                'language' => 'fr',
                'is_fallback' => false,
            ],
            [
                'id' => 'second',
                'frontmatter' => [
                    'name' => 'Second',
                    'category' => 'summer',
                    'domain' => 'blog',
                    'status' => 'published',
                    'published' => true,
                    'date' => '2030-01-01',
                ],
                'content' => 'English',
                'language' => 'en',
                'is_fallback' => true,
            ],
        ];
    }

    public function assetExists($path)
    {
        return true;
    }
}

final class SearchRendererFixture
{
    public array $calls = [];

    public function renderMarkdown(
        string $section,
        string $slug,
        ?string $language = null,
        bool $publicOnly = false
    ): string {
        $this->calls[] = [$slug, $language, $publicOnly];
        return $language . ' body for ' . $slug;
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
$otherLanguages = [
    'language' => 'en',
    'languages' => ['en', 'de'],
    'i18n_active' => true,
];

checkList(
    LocalizedList::matchPath('/blog/fr/', '/blog/', $active)
        === ['language' => 'fr', 'surface' => 'home', 'category' => null],
    'localized home route matches'
);
checkList(
    LocalizedList::matchPath('/blog/fr/search/', '/blog/', $active)
        === ['language' => 'fr', 'surface' => 'search', 'category' => null],
    'localized search route matches'
);
checkList(
    LocalizedList::matchPath('/blog/fr/category/summer/', '/blog/', $active)
        === ['language' => 'fr', 'surface' => 'archive', 'category' => 'summer'],
    'localized canonical archive route matches'
);
checkList(
    LocalizedList::matchPath('/blog/fr/', '/blog/', $inactive) === null,
    'inactive gate rejects localized lists'
);
checkList(
    LocalizedList::matchPath('/blog/fr/', '/blog/', $otherLanguages) === null,
    'site language configuration remains isolated'
);
checkList(
    LocalizedList::publicPath('/blog/', 'fr', 'archive', 'summer')
        === '/blog/fr/category/summer/',
    'localized archive path keeps canonical term slug'
);
checkList(
    LocalizedList::staticRelativeRoot('home') === '../'
        && LocalizedList::staticRelativeRoot('search') === '../../'
        && LocalizedList::staticRelativeRoot('archive', 'summer') === '../../../',
    'localized static depths are surface-aware'
);

$merged = (new DossierDiscovery(new MergedListFakeApi()))
    ->getAllDossiers('blog', false, 'fr', 'default');
checkList(
    array_column($merged, 'slug') === ['first', 'second'],
    'merged discovery retains backend default skeleton order'
);
checkList(
    $merged[0]['language'] === 'fr'
        && $merged[0]['is_fallback'] === false
        && $merged[1]['language'] === 'en'
        && $merged[1]['is_fallback'] === true,
    'merged discovery preserves actual language and fallback flags'
);

$renderer = new SearchRendererFixture();
$searchRows = [
    [
        'slug' => 'translated',
        'section' => 'summer',
        'title' => 'Traduit',
        'hero_title' => 'Traduit',
        'language' => 'fr',
        'is_fallback' => false,
        'term_labels' => ['summer' => 'Summer'],
    ],
    [
        'slug' => 'default-only',
        'section' => 'summer',
        'title' => 'Default',
        'hero_title' => 'Default',
        'language' => 'en',
        'is_fallback' => true,
        'term_labels' => ['summer' => 'Summer'],
    ],
];
$searchDocs = SearchIndexBuilder::buildFromDossiers(
    $searchRows,
    $renderer,
    static fn (array $row): string => !empty($row['is_fallback'])
        ? '../../default-only/index.html'
        : '../../fr/translated/index.html'
);
checkList(
    array_map(
        static fn (array $doc): array => [$doc['id'], $doc['lang'], $doc['url']],
        $searchDocs
    ) === [
        ['translated', 'fr', '../../fr/translated/index.html'],
        ['default-only', 'en', '../../default-only/index.html'],
    ],
    'search documents carry actual language and resolved fallback URLs'
);
checkList(
    $renderer->calls === [
        ['translated', 'fr', true],
        ['default-only', 'en', true],
    ],
    'search renders each merged row in its actual language'
);

$legacyDefaultDoc = SearchIndexBuilder::documentFromDossier(
    ['slug' => 'default-only', 'title' => 'Default'],
    'Default body',
    '/default-only/'
);
$activeDefaultDoc = SearchIndexBuilder::documentFromDossier(
    ['slug' => 'default-only', 'title' => 'Default'],
    'Default body',
    '/default-only/',
    'en'
);
checkList(
    is_array($legacyDefaultDoc)
        && !array_key_exists('lang', $legacyDefaultDoc)
        && is_array($activeDefaultDoc)
        && ($activeDefaultDoc['lang'] ?? null) === 'en',
    'default search language metadata is additive and active-gated by the caller'
);

$root = sys_get_temp_dir() . '/pencms-list-i18n-' . bin2hex(random_bytes(6));
$backend = $root . '/backend';
$content = $root . '/content';
$themeDir = $backend . '/themes/fixture';

try {
    @mkdir($backend . '/data', 0777, true);
    @mkdir($themeDir . '/templates', 0777, true);
    @mkdir($content . '/sites/default', 0777, true);
    @mkdir($content . '/sites/other', 0777, true);
    file_put_contents(
        $backend . '/config.ini',
        "[Paths]\ncontent_dir = ../content\n"
        . "[Server]\napi_port = 1\n"
        . "[theme]\nactive = fixture\ndirectory = themes\nweb_root = /blog/\n"
    );
    file_put_contents(
        $themeDir . '/theme.json',
        json_encode([
            'type' => 'native',
            'name' => 'Fixture',
            'version' => '1.0.0',
            'variables' => [],
        ])
    );
    file_put_contents(
        $themeDir . '/templates/page.html.twig',
        '<html lang="en"><head></head><body>'
        . '{{ contentUrl(exact) }}|{{ contentUrl(fallback) }}|{{ archiveUrl("summer") }}|'
        . '{% for item in menu("primary") %}{{ item.label }}={{ item.url }};{% endfor %}'
        . '</body></html>'
    );
    file_put_contents(
        $content . '/sites/default/menus.yaml',
        "primary:\n"
        . "  - id: home\n    label: Home\n    labels: {fr: Accueil}\n"
        . "    target: {type: system, content_slug: home}\n"
        . "  - id: archive\n    label: Summer\n    labels: {fr: Menu été}\n"
        . "    target: {type: taxonomy, content_slug: primary/Summer}\n"
        . "  - id: external\n    label: External\n    labels: {fr: Externe}\n"
        . "    target: {type: custom, url: https://example.test/path}\n"
        . "secondary: []\nfooter: []\n"
    );
    file_put_contents(
        $content . '/sites/other/menus.yaml',
        "primary:\n"
        . "  - id: home\n    label: Other Home\n    labels: {fr: Autre accueil}\n"
        . "    target: {type: system, content_slug: home}\n"
        . "secondary: []\nfooter: []\n"
    );

    $presentation = [
        'site_id' => 'default',
        'theme' => 'fixture',
        'content_relpath' => 'sites/default',
        'language' => 'en',
        'languages' => ['en', 'fr'],
        'i18n_active' => true,
    ];
    $rows = [
        'exact' => [
            'slug' => 'translated',
            'page' => false,
            'language' => 'fr',
            'is_fallback' => false,
        ],
        'fallback' => [
            'slug' => 'default-only',
            'page' => false,
            'language' => 'en',
            'is_fallback' => true,
        ],
        'language' => 'fr',
        'hero_title' => 'Fixture',
    ];
    $dynamic = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        $presentation
    )->render('page', $rows);
    checkList(
        str_contains($dynamic, '/blog/fr/translated/')
            && str_contains($dynamic, '/blog/post.php?slug=default-only')
            && str_contains($dynamic, '/blog/fr/category/summer/'),
        'dynamic exact, fallback, and canonical archive URLs are correct'
    );
    checkList(
        str_contains($dynamic, 'Accueil=/blog/fr/')
            && str_contains($dynamic, 'Summer=/blog/fr/category/summer/')
            && str_contains($dynamic, 'Externe=https://example.test/path'),
        'menu labels localize per entry while taxonomy keeps its canonical label'
    );

    $static = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        true,
        '../../../',
        'default',
        $presentation
    )->render('page', $rows);
    checkList(
        str_contains($static, '../../../fr/translated/index.html')
            && str_contains($static, '../../../default-only/index.html')
            && str_contains($static, '../../../fr/category/summer/index.html'),
        'static exact, fallback, and archive URLs match dynamic semantics'
    );

    $otherPresentation = array_replace($presentation, [
        'site_id' => 'other',
        'content_relpath' => 'sites/other',
    ]);
    $other = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'other',
        $otherPresentation
    )->render('page', $rows);
    checkList(
        str_contains($other, 'Autre accueil=')
            && !str_contains($other, 'Accueil=/blog/fr/'),
        'menu label resolution remains site-scoped'
    );

    $inactivePresentation = array_replace($presentation, [
        'languages' => [],
        'i18n_active' => false,
    ]);
    $inactiveHtml = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        $inactivePresentation
    )->render('page', $rows);
    checkList(
        str_contains($inactiveHtml, '<html lang="en">')
            && str_contains($inactiveHtml, 'Home=/blog/index.php')
            && !str_contains($inactiveHtml, 'Accueil='),
        'inactive gate keeps legacy document language, menu label, and URL'
    );
} finally {
    removeListTree($root);
}

foreach ($failures as $failure) {
    fwrite(STDERR, "[FAIL] {$failure}\n");
}
echo "Localized list i18n: {$passed} passed, {$failed} failed\n";
exit($failed > 0 ? 1 : 0);
