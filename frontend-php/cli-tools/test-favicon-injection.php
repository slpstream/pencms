<?php

declare(strict_types=1);

require_once __DIR__ . '/../vendor/autoload.php';
require_once __DIR__ . '/../src/core/ThemeEngine.php';

use Dossier\ThemeEngine;

$passed = 0;
$failed = 0;
/** @var list<string> $failures */
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

function iconHrefs(string $html): array
{
    preg_match_all(
        '/<link\b[^>]*\brel\s*=\s*["\'](?:shortcut\s+)?icon["\'][^>]*>/i',
        $html,
        $tags
    );
    $hrefs = [];
    foreach ($tags[0] as $tag) {
        if (preg_match('/\bhref\s*=\s*["\']([^"\']+)["\']/i', $tag, $href)) {
            $hrefs[] = $href[1];
        }
    }
    return $hrefs;
}

$root = sys_get_temp_dir() . '/pencms-favicon-' . bin2hex(random_bytes(6));
$backend = $root . '/backend';
$content = $root . '/content';
$theme = $backend . '/themes/fixture';
$site = $content . '/sites/default';

try {
    @mkdir($theme . '/templates', 0777, true);
    @mkdir($theme . '/assets/images', 0777, true);
    @mkdir($site . '/assets/images', 0777, true);

    writeJson($theme . '/theme.json', [
        'type' => 'native',
        'name' => 'Fixture',
        'version' => '1.0.0',
        'variables' => [],
    ]);
    file_put_contents(
        $theme . '/assets/images/favicon.svg',
        '<svg xmlns="http://www.w3.org/2000/svg"><rect fill="#f00" width="16" height="16"/></svg>'
    );
    $shell = '<html lang="en"><head></head><body>{{ hero_title|default("") }}</body></html>';
    foreach (['index', 'post', 'page', 'search'] as $name) {
        file_put_contents($theme . '/templates/' . $name . '.html.twig', $shell);
    }
    file_put_contents(
        $theme . '/templates/themed-icon.html.twig',
        '<html><head>'
        . '<link rel="icon" type="image/svg+xml" href="images/favicon.svg">'
        . '<link rel="shortcut icon" href="images/old-favicon.ico">'
        . '<link rel="stylesheet" href="css/styles.css">'
        . '</head><body></body></html>'
    );
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
        'languages' => ['en'],
        'i18n_active' => false,
        'sitename' => 'Example Site',
    ];

    $staticEngine = static function () use ($backend, $presentation): ThemeEngine {
        return ThemeEngine::fromConfig(
            $backend . '/config.ini',
            true,
            './',
            'default',
            $presentation
        );
    };
    $liveEngine = static function () use ($backend, $presentation): ThemeEngine {
        return ThemeEngine::fromConfig(
            $backend . '/config.ini',
            false,
            '',
            'default',
            $presentation
        );
    };

    $page = ['hero_title' => 'Home', 'sitename' => 'Example Site'];

    $themeOnly = $staticEngine()->render('index', $page);
    $themeHrefs = iconHrefs($themeOnly);
    check(count($themeHrefs) === 1, 'theme fallback emits a single icon link');
    check(
        $themeHrefs === ['./images/favicon.svg'],
        'theme fallback points at theme images/favicon.svg'
    );

    file_put_contents(
        $site . '/assets/images/favicon.ico',
        'fake-ico'
    );

    $withSiteStatic = $staticEngine()->render('index', $page);
    $siteStaticHrefs = iconHrefs($withSiteStatic);
    check(count($siteStaticHrefs) === 1, 'site favicon emits a single static icon link');
    check(
        $siteStaticHrefs === ['./favicon.ico'],
        'static site favicon points at root favicon.ico, not the theme SVG'
    );
    check(
        !str_contains($withSiteStatic, 'images/favicon.svg'),
        'static site favicon does not leave a theme SVG href'
    );

    $withSiteLive = $liveEngine()->render('index', $page);
    $siteLiveHrefs = iconHrefs($withSiteLive);
    check(count($siteLiveHrefs) === 1, 'site favicon emits a single live icon link');
    check(
        $siteLiveHrefs === ['/api/assets/raw/sites/default/assets/images/favicon.ico'],
        'live site favicon uses the per-site assets URL'
    );
    check(
        !str_contains($withSiteLive, 'themes/fixture/assets/images/favicon.svg'),
        'live site favicon does not keep the theme SVG href'
    );

    $replaced = $staticEngine()->render('themed-icon', $page);
    $replacedHrefs = iconHrefs($replaced);
    check(count($replacedHrefs) === 1, 'hardcoded theme icon links are collapsed to one');
    check(
        $replacedHrefs === ['./favicon.ico'],
        'hardcoded theme icons are replaced by the site favicon'
    );
    check(
        str_contains($replaced, 'css/styles.css'),
        'stylesheet links are left intact when stripping icons'
    );
} finally {
    removeTree($root);
}

echo "Favicon injection: {$passed} passed, {$failed} failed\n";
if ($failures) {
    foreach ($failures as $label) {
        echo "FAIL: {$label}\n";
    }
    exit(1);
}
exit(0);
