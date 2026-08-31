<?php

/**
 * Smoke test for SitemapBuilder.
 *
 * Run: php frontend-php/cli-tools/test-sitemap-builder.php
 *
 * Dynamic route behavior (not exercised here):
 * - sitemap_enabled=false → HTTP 404 from blog/sitemap.php
 * - Static build omits sitemap.xml when disabled
 */

require_once __DIR__ . '/../src/core/RssFeedBuilder.php';
require_once __DIR__ . '/../src/core/SitemapBuilder.php';

use Dossier\RssFeedBuilder;
use Dossier\SitemapBuilder;

function assert_contains(string $haystack, string $needle, string $label): void
{
    if (strpos($haystack, $needle) === false) {
        fwrite(STDERR, "FAIL: {$label}\n  expected substring: {$needle}\n");
        exit(1);
    }
}

function assert_not_contains(string $haystack, string $needle, string $label): void
{
    if (strpos($haystack, $needle) !== false) {
        fwrite(STDERR, "FAIL: {$label}\n  unexpected substring: {$needle}\n");
        exit(1);
    }
}

$dossiers = [
    [
        'slug' => 'hello-world',
        'date' => '2024-06-15',
        'page' => false,
    ],
    [
        'slug' => 'about',
        'date' => '2024-01-01',
        'page' => true,
    ],
    [
        'slug' => 'hello-world',
        'date' => '2024-06-15',
        'page' => false,
    ],
    [
        'slug' => 'unsafe&amp;slug',
        'date' => '2024-07-01',
    ],
    [
        'slug' => 'hidden-post',
        'date' => '2024-08-01',
        'page' => false,
        'noindex' => true,
    ],
    [
        'slug' => 'secret-notes',
        'date' => '2024-08-02',
        'page' => true,
        'noindex' => true,
    ],
];

$xml = SitemapBuilder::build($dossiers, 'example.com');

assert_contains($xml, '<?xml version="1.0" encoding="UTF-8"?>', 'xml declaration');
assert_contains($xml, '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">', 'urlset namespace');
assert_contains($xml, '<loc>https://example.com/</loc>', 'home loc with trailing slash base');
assert_contains($xml, '<loc>https://example.com/hello-world/</loc>', 'post loc');
assert_contains($xml, '<loc>https://example.com/about/</loc>', 'page loc');
assert_not_contains($xml, 'hidden-post', 'noindex post omitted from sitemap');
assert_not_contains($xml, 'secret-notes', 'noindex page omitted from sitemap');
assert_contains($xml, '<lastmod>2024-06-15</lastmod>', 'lastmod from date');
assert_contains($xml, '<loc>https://example.com/unsafe&amp;amp;slug/</loc>', 'xml escaping');
assert_not_contains($xml, 'https://example.com/hello-world/</loc></url><url><loc>https://example.com/hello-world/', 'dedupe duplicate slugs');

// Trailing slash normalization on input base without scheme
$xml2 = SitemapBuilder::build([], 'https://blog.test');
assert_contains($xml2, '<loc>https://blog.test/</loc>', 'normalizeSiteUrl trailing slash');

$localized = [
    'fr' => [
        [
            'slug' => 'hello-world',
            'updated' => '2026-08-11',
        ],
        [
            'slug' => 'hello-world',
            'updated' => '2026-08-12',
        ],
        [
            'slug' => 'unsafe&amp;slug',
            'date' => '2026-08-10',
        ],
        [
            'slug' => 'hidden-fr',
            'updated' => '2026-08-10',
            'noindex' => true,
        ],
    ],
];
$localizedXml = SitemapBuilder::build($dossiers, 'example.com', $localized);
assert_contains(
    $localizedXml,
    '<loc>https://example.com/fr/hello-world/</loc>',
    'exact localized sibling loc'
);
assert_contains(
    $localizedXml,
    '<loc>https://example.com/hello-world/</loc>',
    'default loc remains alongside localized sibling'
);
assert_contains(
    $localizedXml,
    '<lastmod>2026-08-11</lastmod>',
    'localized lastmod comes from exact sibling'
);
assert_contains(
    $localizedXml,
    '<loc>https://example.com/fr/unsafe&amp;amp;slug/</loc>',
    'localized loc is XML escaped'
);
if (substr_count($localizedXml, '<loc>https://example.com/fr/hello-world/</loc>') !== 1) {
    fwrite(STDERR, "FAIL: localized language/slug entries are deduplicated\n");
    exit(1);
}
assert_not_contains($localizedXml, 'hidden-fr', 'localized noindex sibling omitted');
assert_contains(
    $localizedXml,
    'xmlns:xhtml="http://www.w3.org/1999/xhtml"',
    'urlset declares xhtml namespace when translation clusters exist'
);
$helloCluster = [
    '<xhtml:link rel="alternate" hreflang="en" href="https://example.com/hello-world/"/>',
    '<xhtml:link rel="alternate" hreflang="fr" href="https://example.com/fr/hello-world/"/>',
    '<xhtml:link rel="alternate" hreflang="x-default" href="https://example.com/hello-world/"/>',
];
foreach ($helloCluster as $link) {
    assert_contains($localizedXml, $link, 'translation cluster includes ' . $link);
}
if (substr_count($localizedXml, $helloCluster[2]) !== 2) {
    fwrite(STDERR, "FAIL: x-default appears on both default and localized hello-world entries\n");
    exit(1);
}
assert_not_contains(
    $localizedXml,
    '<xhtml:link rel="alternate" hreflang="en" href="https://example.com/about/"/>',
    'default-only about slug has no xhtml cluster'
);
assert_not_contains($xml, 'xmlns:xhtml', 'monolingual sitemap omits xhtml namespace');
assert_not_contains($xml, 'xhtml:link', 'monolingual sitemap omits xhtml links');

$rss = RssFeedBuilder::build(
    $dossiers,
    'https://example.com/',
    'Example Site'
);
assert_contains($rss, 'hello-world', 'indexable post remains in RSS');
assert_not_contains($rss, 'hidden-post', 'noindex post omitted from RSS');
assert_not_contains($rss, 'secret-notes', 'noindex page is not an RSS item');
assert_not_contains($rss, '/about/', 'pages are not RSS items');

echo "OK: SitemapBuilder smoke tests passed\n";
