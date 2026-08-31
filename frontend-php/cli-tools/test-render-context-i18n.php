<?php

declare(strict_types=1);

require_once __DIR__ . '/../vendor/autoload.php';
require_once __DIR__ . '/../src/core/UiStrings.php';
require_once __DIR__ . '/../src/core/ThemeEngine.php';

use Dossier\ThemeEngine;
use Dossier\UiStrings;

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

function writeJson(string $path, array $value): void
{
    @mkdir(dirname($path), 0777, true);
    file_put_contents(
        $path,
        json_encode($value, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE)
    );
}

function removeTree(string $path): void
{
    if (!is_dir($path)) {
        return;
    }
    $items = scandir($path);
    if ($items === false) {
        return;
    }
    foreach ($items as $item) {
        if ($item === '.' || $item === '..') {
            continue;
        }
        $child = $path . '/' . $item;
        if (is_dir($child)) {
            removeTree($child);
        } else {
            unlink($child);
        }
    }
    rmdir($path);
}

$root = sys_get_temp_dir() . '/pencms-render-i18n-' . bin2hex(random_bytes(6));
$backend = $root . '/backend';
$content = $root . '/content';
$theme = $backend . '/themes/fixture';
$site = $content . '/sites/default';

try {
    @mkdir($theme . '/templates', 0777, true);
    @mkdir($theme . '/partials', 0777, true);
    @mkdir($site . '/strings', 0777, true);

    $enginePath = $root . '/engine.json';
    writeJson($enginePath, [
        'engineOnly' => 'engine',
        'fallback' => 'engine fallback',
        'shared' => 'engine shared',
    ]);
    writeJson($theme . '/strings.json', [
        'themeOnly' => 'theme',
        'shared' => 'theme shared',
    ]);
    writeJson($site . '/strings/en.json', [
        'defaultOnly' => 'default',
        'shared' => 'default shared',
    ]);
    writeJson($site . '/strings/fr.json', [
        'targetOnly' => 'target',
        'shared' => 'target shared',
    ]);

    $strings = (new UiStrings(
        $enginePath,
        $theme,
        $site,
        'en',
        true
    ))->resolve('fr');
    check($strings['engineOnly'] === 'engine', 'engine defaults survive');
    check($strings['themeOnly'] === 'theme', 'theme strings merge');
    check($strings['defaultOnly'] === 'default', 'default site strings merge');
    check($strings['targetOnly'] === 'target', 'target site strings merge');
    check($strings['shared'] === 'target shared', 'target layer has final precedence');
    check($strings['fallback'] === 'engine fallback', 'sparse keys fall back per key');

    $otherSite = $content . '/sites/other';
    writeJson($otherSite . '/strings/fr.json', ['shared' => 'other target']);
    $otherStrings = (new UiStrings(
        $enginePath,
        $theme,
        $otherSite,
        'en',
        true
    ))->resolve('fr');
    check($otherStrings['shared'] === 'other target', 'other site uses its own target strings');
    check($strings['shared'] === 'target shared', 'site string resolution remains isolated');

    file_put_contents($site . '/strings/fr.json', '{"shared":');
    $malformedRaised = false;
    try {
        (new UiStrings($enginePath, $theme, $site, 'en', true))->resolve('fr');
    } catch (RuntimeException $e) {
        $malformedRaised = str_contains($e->getMessage(), $site . '/strings/fr.json')
            && str_contains($e->getMessage(), 'Fix:');
    }
    check($malformedRaised, 'malformed target file raises a path-specific teaching error');

    writeJson($site . '/strings/fr.json', ['shared' => ['not flat']]);
    $nonFlatRaised = false;
    try {
        (new UiStrings($enginePath, $theme, $site, 'en', true))->resolve('fr');
    } catch (RuntimeException $e) {
        $nonFlatRaised = str_contains($e->getMessage(), 'flat string value');
    }
    check($nonFlatRaised, 'non-flat target values are rejected');

    file_put_contents($theme . '/strings.json', '{bad');
    file_put_contents($site . '/strings/en.json', '{bad');
    $inactiveStrings = (new UiStrings(
        $enginePath,
        $theme,
        $site,
        'en',
        false
    ))->resolve('fr');
    check(
        $inactiveStrings === [
            'engineOnly' => 'engine',
            'fallback' => 'engine fallback',
            'shared' => 'engine shared',
        ],
        'inactive gate ignores malformed theme and site layers'
    );

    writeJson($theme . '/strings.json', [
        'shared' => 'theme shared',
        'targetOnly' => 'theme target fallback',
    ]);
    writeJson($site . '/strings/en.json', ['shared' => 'default shared']);
    writeJson($site . '/strings/fr.json', [
        'shared' => 'target shared',
        'targetOnly' => 'target value',
        'minuteRead' => '%d min lecture',
    ]);
    writeJson($theme . '/theme.json', [
        'type' => 'native',
        'name' => 'Fixture',
        'version' => '1.0.0',
        'variables' => [],
    ]);
    file_put_contents(
        $theme . '/templates/page.html.twig',
        '<html class="fixture" lang="en"><head></head><body>'
        . '{{ site.language }}|{{ site.default_language }}|{{ strings.shared }}|'
        . '{{ theme.partial("label") }}|{{ reading_time|default("") }}|'
        . '{{ dateline|default("") }}</body></html>'
    );
    file_put_contents($theme . '/partials/_label.html.twig', '{{ strings.targetOnly }}');
    file_put_contents(
        $theme . '/templates/inactive.html.twig',
        '<html lang="en"><head></head><body>{{ strings.home }}</body></html>'
    );
    @mkdir($backend . '/data', 0777, true);
    file_put_contents(
        $backend . '/config.ini',
        "[Paths]\ncontent_dir = ../content\n"
        . "[Server]\napi_port = 1\n"
        . "[theme]\nactive = fixture\ndirectory = themes\nweb_root = /blog/\n"
    );

    $presentation = [
        'site_id' => 'default',
        'theme' => 'fixture',
        'content_relpath' => 'sites/default',
        'language' => 'en',
        'languages' => ['en', 'fr'],
        'i18n_active' => true,
    ];
    $pageData = [
        'hero_title' => 'Fixture',
        'language' => 'fr',
        'reading_minutes' => 2,
        'date' => '2026-08-01',
    ];
    $dynamic = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        $presentation
    )->render('page', $pageData);
    $static = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        true,
        '../../',
        'default',
        $presentation
    )->render('page', $pageData);
    check(
        str_contains($dynamic, '<html class="fixture" lang="fr">'),
        'dynamic localized detail replaces html lang'
    );
    check(
        str_contains($dynamic, 'fr|en|target shared|target value'),
        'dynamic detail exposes current/default language and merged strings to partials'
    );
    check(
        str_contains($dynamic, '2 min lecture'),
        'localized reading time uses the target string dictionary'
    );
    if (class_exists('IntlDateFormatter')) {
        check(
            !str_contains($dynamic, 'August 01, 2026'),
            'localized dateline uses Intl locale formatting'
        );
    }
    check(
        str_contains($static, '<html class="fixture" lang="fr">')
            && str_contains($static, 'fr|en|target shared|target value'),
        'static localized detail matches dynamic render context'
    );

    $defaultHtml = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        $presentation
    )->render('page', ['hero_title' => 'Fixture', 'language' => 'en']);
    check(
        str_contains($defaultHtml, 'en|en|default shared|theme target fallback'),
        'default-language render keeps default context and per-key fallback'
    );
    foreach ([
        'starter',
        'academic',
    ] as $keeper) {
        $head = file_get_contents(
            __DIR__ . '/../src/blog/themes/' . $keeper . '/partials/_head.html.twig'
        );
        check(
            is_string($head)
                && !str_contains($head, 'lang="en"')
                && str_contains($head, 'site.language'),
            "keeper theme {$keeper} derives the document language"
        );
    }

    $customSite = $content . '/sites/custom';
    $customTheme = $customSite . '/theme';
    @mkdir($customTheme . '/templates', 0777, true);
    writeJson($customTheme . '/theme.json', [
        'type' => 'native',
        'name' => 'Custom Fixture',
        'version' => '1.0.0',
        'variables' => [],
    ]);
    writeJson($customTheme . '/strings.json', ['shared' => 'custom theme']);
    writeJson($customSite . '/strings/fr.json', ['shared' => 'custom target']);
    file_put_contents(
        $customTheme . '/templates/page.html.twig',
        '<html lang="en"><head></head><body>'
        . '{{ site.id }}|{{ site.language }}|{{ strings.shared }}</body></html>'
    );
    $customHtml = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'custom',
        [
            'site_id' => 'custom',
            'theme' => 'custom',
            'content_relpath' => 'sites/custom',
            'language' => 'en',
            'languages' => ['en', 'fr'],
            'i18n_active' => true,
        ]
    )->render('page', ['hero_title' => 'Custom', 'language' => 'fr']);
    check(
        str_contains($customHtml, 'custom|fr|custom target'),
        'custom theme and site string paths remain site-scoped'
    );

    file_put_contents($theme . '/strings.json', '{bad');
    file_put_contents($site . '/strings/en.json', '{bad');
    $inactiveHtml = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        [
            'site_id' => 'default',
            'theme' => 'fixture',
            'content_relpath' => 'sites/default',
            'language' => 'fr',
            'languages' => [],
            'i18n_active' => false,
        ]
    )->render('inactive', ['hero_title' => 'Fixture', 'language' => 'fr']);
    check(
        str_contains($inactiveHtml, '<html lang="en">')
            && str_contains($inactiveHtml, '>Home</body>'),
        'inactive render ignores optional strings and leaves html lang unchanged'
    );
} finally {
    removeTree($root);
}

foreach ($failures as $failure) {
    fwrite(STDERR, "[FAIL] {$failure}\n");
}
echo "Render context i18n: {$passed} passed, {$failed} failed\n";
exit($failed > 0 ? 1 : 0);
