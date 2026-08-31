<?php

declare(strict_types=1);

require_once __DIR__ . '/../vendor/autoload.php';
require_once __DIR__ . '/../src/core/ThemeEngine.php';

use Dossier\ThemeEngine;

$passed = 0;
$failed = 0;
$failures = [];

function checkSwitcher(bool $condition, string $label): void
{
    global $passed, $failed, $failures;
    if ($condition) {
        $passed++;
        return;
    }
    $failed++;
    $failures[] = $label;
}

function writeSwitcherJson(string $path, array $value): void
{
    @mkdir(dirname($path), 0777, true);
    file_put_contents(
        $path,
        json_encode($value, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE)
    );
}

function removeSwitcherTree(string $path): void
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
            removeSwitcherTree($child);
        } else {
            unlink($child);
        }
    }
    rmdir($path);
}

function switcherPresentation(
    string $siteId = 'default',
    array $labels = ['fr' => 'Français personnalisé']
): array {
    return [
        'site_id' => $siteId,
        'theme' => 'fixture',
        'content_relpath' => 'sites/' . $siteId,
        'language' => 'en',
        'languages' => ['en', 'fr', 'de', 'es'],
        'language_labels' => $labels,
        'i18n_active' => true,
    ];
}

function switcherPage(string $language = 'en'): array
{
    return [
        'hero_title' => 'Guide',
        'slug' => 'guide',
        'language' => $language,
        'is_page' => false,
        'i18n_current_live' => true,
        'translations' => [
            [
                'language' => $language === 'fr' ? 'en' : 'fr',
                'status' => 'published',
                'published' => true,
            ],
            [
                'language' => 'de',
                'status' => 'draft',
                'published' => false,
            ],
            [
                'language' => 'es',
                'status' => 'published',
                'published' => false,
            ],
        ],
    ];
}

$root = sys_get_temp_dir() . '/pencms-switcher-i18n-' . bin2hex(random_bytes(6));
$backend = $root . '/backend';
$content = $root . '/content';
$theme = $backend . '/themes/fixture';

try {
    @mkdir($backend . '/data', 0777, true);
    @mkdir($theme . '/templates', 0777, true);
    @mkdir($theme . '/partials', 0777, true);
    @mkdir($content . '/sites/default', 0777, true);
    @mkdir($content . '/sites/other', 0777, true);

    file_put_contents(
        $backend . '/config.ini',
        "[Paths]\ncontent_dir = ../content\n"
        . "[Server]\napi_port = 1\n"
        . "[theme]\nactive = fixture\ndirectory = themes\nweb_root = /blog/\n"
    );
    writeSwitcherJson($theme . '/theme.json', [
        'type' => 'native',
        'name' => 'Switcher Fixture',
        'version' => '1.0.0',
        'variables' => [],
    ]);
    file_put_contents(
        $theme . '/templates/page.html.twig',
        '<html lang="en"><head></head><body>'
        . '{{ site.language_labels.fr }}'
        . '{{ theme.partial("language-switcher")|raw }}'
        . '</body></html>'
    );
    file_put_contents(
        $theme . '/templates/plain.html.twig',
        '<html lang="en"><head></head><body>Plain theme</body></html>'
    );
    file_put_contents(
        $theme . '/templates/inactive.html.twig',
        '<html lang="en"><head></head><body>'
        . '{{ theme.partial("language-switcher")|raw }}'
        . '</body></html>'
    );
    file_put_contents(
        $theme . '/templates/duplicate.html.twig',
        '<html lang="en"><head>'
        . '<link rel="alternate" hreflang="en" href="/manual/">'
        . '</head><body>{{ theme.partial("language-switcher")|raw }}</body></html>'
    );

    $presentation = switcherPresentation();
    $dynamic = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        $presentation
    )->render('page', switcherPage());

    checkSwitcher(
        substr_count($dynamic, '<link rel="alternate" hreflang="en"') === 1
            && substr_count($dynamic, '<link rel="alternate" hreflang="fr"') === 1,
        'head publishes current and exact published sibling once'
    );
    checkSwitcher(
        !str_contains($dynamic, '<link rel="alternate" hreflang="de"')
            && !str_contains($dynamic, '<link rel="alternate" hreflang="es"')
            && !str_contains($dynamic, 'data-pen-language-code="de"')
            && !str_contains($dynamic, 'data-pen-language-code="es"'),
        'draft, unpublished, and missing siblings are excluded'
    );
    checkSwitcher(
        str_contains(
            $dynamic,
            'href="/blog/post.php?slug=guide&amp;site=default"'
        )
            && str_contains($dynamic, 'href="/blog/fr/guide/?site=default"'),
        'dynamic default and localized detail URLs remain unchanged'
    );
    checkSwitcher(
        str_contains(
            $dynamic,
            '<link rel="alternate" hreflang="x-default" href="/blog/post.php?slug=guide&amp;site=default">'
        ),
        'x-default points at the default-language URL on the default page'
    );
    checkSwitcher(
        str_contains($dynamic, 'Français personnalisé')
            && str_contains($dynamic, 'data-pen-language-code="en"')
            && str_contains($dynamic, '>en</span>'),
        'configured override and safe code fallback are rendered without JS'
    );
    checkSwitcher(
        preg_match(
            '/data-pen-language-code="en"[^>]*aria-current="page"/s',
            $dynamic
        ) === 1,
        'default language link marks current state'
    );
    checkSwitcher(
        str_contains($dynamic, 'data-pen-language-switcher')
            && str_contains($dynamic, '/assets/vendor/pencms/language-switcher.js'),
        'opted-in theme renders shared switcher and enhancer'
    );

    $localized = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        $presentation
    )->render('page', switcherPage('fr'));
    checkSwitcher(
        preg_match(
            '/data-pen-language-code="fr"[^>]*aria-current="page"/s',
            $localized
        ) === 1
            && str_contains(
                $localized,
                'href="/blog/post.php?slug=guide&amp;site=default"'
            )
            && str_contains($localized, 'href="/blog/fr/guide/?site=default"'),
        'localized current state retains exact sibling routes'
    );
    checkSwitcher(
        str_contains(
            $localized,
            '<link rel="alternate" hreflang="x-default" href="/blog/post.php?slug=guide&amp;site=default">'
        )
            && !str_contains(
                $localized,
                '<link rel="alternate" hreflang="x-default" href="/blog/fr/guide/?site=default">'
            ),
        'x-default on localized HTML still points at the default-language URL'
    );

    $static = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        true,
        '../../',
        'default',
        $presentation
    )->render('page', switcherPage('fr'));
    checkSwitcher(
        str_contains($static, 'href="../../guide/index.html"')
            && str_contains($static, 'href="../../fr/guide/index.html"'),
        'static switcher preserves existing relative detail routes'
    );

    $other = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'other',
        switcherPresentation('other', ['fr' => 'Français autre'])
    )->render('page', switcherPage());
    checkSwitcher(
        str_contains($other, 'Français autre')
            && !str_contains($other, 'Français personnalisé')
            && str_contains($other, 'site=other'),
        'labels and preview URLs remain isolated by site'
    );

    $plain = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        $presentation
    )->render('plain', switcherPage());
    checkSwitcher(
        str_contains($plain, '<link rel="alternate" hreflang="en"')
            && !str_contains($plain, 'data-pen-language-switcher')
            && !str_contains($plain, 'language-switcher.js'),
        'SEO alternates remain while switcher chrome stays theme-opt-in'
    );

    $duplicate = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        $presentation
    )->render('duplicate', switcherPage());
    checkSwitcher(
        substr_count($duplicate, 'hreflang="en"') === 2
            && substr_count(
                $duplicate,
                '<link rel="alternate" hreflang="en"'
            ) === 1
            && substr_count(
                $duplicate,
                '<link rel="alternate" hreflang="fr"'
            ) === 1,
        'head injection does not duplicate an existing language alternate'
    );

    $noPeers = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        $presentation
    )->render('inactive', array_replace(switcherPage(), ['translations' => []]));
    checkSwitcher(
        !str_contains($noPeers, 'hreflang=')
            && !str_contains($noPeers, 'data-pen-language-switcher'),
        'current-only page does not show a switcher or hreflang block'
    );

    $draftCurrent = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        $presentation
    )->render(
        'inactive',
        array_replace(switcherPage(), ['i18n_current_live' => false])
    );
    checkSwitcher(
        !str_contains($draftCurrent, 'hreflang=')
            && !str_contains($draftCurrent, 'data-pen-language-switcher'),
        'draft current page withholds switcher and SEO alternates'
    );

    $inactivePresentation = array_replace($presentation, [
        'languages' => ['en'],
        'language_labels' => [],
        'i18n_active' => false,
    ]);
    $inactive = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        $inactivePresentation
    )->render('inactive', switcherPage());
    checkSwitcher(
        str_contains($inactive, '<html lang="en">')
            && !str_contains($inactive, 'hreflang=')
            && !str_contains($inactive, 'data-pen-language-switcher'),
        'inactive and monolingual rendering remains unchanged'
    );
} finally {
    removeSwitcherTree($root);
}

foreach ($failures as $failure) {
    fwrite(STDERR, "[FAIL] {$failure}\n");
}
echo "Language switcher i18n: {$passed} passed, {$failed} failed\n";
exit($failed > 0 ? 1 : 0);
