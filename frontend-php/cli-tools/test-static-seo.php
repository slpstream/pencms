<?php

declare(strict_types=1);

require_once __DIR__ . '/../src/core/StaticSeo.php';

use Dossier\StaticSeo;

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

check(
    StaticSeo::contentSignalHeader(false) === 'search=yes, ai-input=yes, ai-train=no',
    'default Content-Signal omits training'
);
check(
    StaticSeo::contentSignalHeader(true) === 'search=yes, ai-input=yes, ai-train=yes',
    'training Content-Signal sets ai-train=yes'
);

check(StaticSeo::isValidIndexNowKey(str_repeat('a', 32)), '32-char key is valid');
check(!StaticSeo::isValidIndexNowKey('short'), 'short key is invalid');

check(StaticSeo::isSkippedHost('localhost'), 'localhost skipped');
check(StaticSeo::isSkippedHost('127.0.0.1'), 'loopback skipped');
check(StaticSeo::isSkippedHost('192.168.1.10'), 'RFC1918 skipped');
check(StaticSeo::isSkippedHost('example.test'), '.test skipped');
check(!StaticSeo::isSkippedHost('example.com'), 'public host allowed');
check(!StaticSeo::isPublicHttpsUrl('http://example.com/'), 'http is not public https');
check(StaticSeo::isPublicHttpsUrl('https://example.com/'), 'https example.com is public');

$redirects = StaticSeo::sanitizeRedirects([
    ['from' => '/old-slug/', 'to' => '/new-slug/'],
    ['from' => 'https://evil.example/', 'to' => '/nope/'],
    ['from' => '/ok', 'to' => '//evil.example'],
]);
check(count($redirects) === 1, 'only same-site redirects kept');
check($redirects[0]['from'] === '/old-slug/' && $redirects[0]['to'] === '/new-slug/', 'redirect pair preserved');

$apache = StaticSeo::apacheRewriteRules($redirects);
check(str_contains($apache, 'RewriteRule ^old-slug/?$ /new-slug/ [R=301,L]'), 'Apache RewriteRule 301');
check(StaticSeo::apacheRewriteRules([]) === '', 'empty redirects emit no Apache rules');

$netlify = StaticSeo::netlifyRedirectsFile($redirects);
check($netlify === "/old-slug/  /new-slug/  301\n", 'Netlify _redirects line');

$locs = StaticSeo::sitemapHtmlLocs(
    '<urlset><url><loc>https://example.com/post/</loc></url>'
    . '<url><loc>https://example.com/post.md</loc></url></urlset>'
);
check($locs === ['https://example.com/post/'], 'sitemap locs skip .md mirrors');

echo "StaticSeo: {$passed} passed, {$failed} failed\n";
if ($failures) {
    foreach ($failures as $label) {
        echo "FAIL: {$label}\n";
    }
    exit(1);
}
exit(0);
