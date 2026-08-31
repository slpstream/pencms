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

function jsonLdBlocks(string $html): array
{
    preg_match_all(
        '#<script type="application/ld\+json">(.*?)</script>#s',
        $html,
        $matches
    );
    $out = [];
    foreach ($matches[1] as $raw) {
        $decoded = json_decode(str_replace('\u003c', '<', $raw), true);
        if (is_array($decoded)) {
            $out[] = $decoded;
        }
    }
    return $out;
}

function jsonLdByType(array $blocks, string $type): ?array
{
    foreach ($blocks as $block) {
        if (($block['@type'] ?? '') === $type) {
            return $block;
        }
    }
    return null;
}

$root = sys_get_temp_dir() . '/pencms-jsonld-' . bin2hex(random_bytes(6));
$backend = $root . '/backend';
$content = $root . '/content';
$theme = $backend . '/themes/fixture';
$site = $content . '/sites/default';

try {
    @mkdir($theme . '/templates', 0777, true);
    @mkdir($site, 0777, true);

    writeJson($theme . '/theme.json', [
        'type' => 'native',
        'name' => 'Fixture',
        'version' => '1.0.0',
        'variables' => [],
    ]);
    $shell = '<html lang="en"><head></head><body>{{ hero_title|default("") }}</body></html>';
    foreach (['index', 'post', 'page', 'search'] as $name) {
        file_put_contents($theme . '/templates/' . $name . '.html.twig', $shell);
    }
    file_put_contents(
        $theme . '/templates/already.html.twig',
        '<html><head><script type="application/ld+json">{"@type":"WebSite"}</script></head><body></body></html>'
    );
    file_put_contents(
        $site . '/authors.yaml',
        <<<'YAML'
authors:
  - slug: ada-lovelace
    name: Ada Lovelace
    bio: Mathematician and first programmer.
    website: https://ada.example/
    avatar: https://cdn.example.test/ada.jpg
    role: Editor
    sort_order: 0
  - slug: partial-author
    name: Partial Author
    bio: ""
    website: https://partial.example/
    avatar: ""
    role: ""
    sort_order: 1
  - slug: preview-author
    name: Preview Author
    bio: Lives in preview.
    website: https://preview-author.example/
    avatar: images/authors/preview.webp
    role: Correspondent
    sort_order: 2
  - slug: bare-website
    name: Bare Website
    bio: ""
    website: ada.example
    avatar: ""
    role: ""
    sort_order: 3
YAML
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
        'languages' => ['en'],
        'i18n_active' => false,
        'sitename' => 'Example Site',
        'social_links' => [
            ['platform' => 'github', 'url' => 'https://github.com/example'],
            ['platform' => 'x', 'url' => 'https://x.com/example'],
        ],
    ];

    $engine = static function () use ($backend, $presentation): ThemeEngine {
        return ThemeEngine::fromConfig(
            $backend . '/config.ini',
            true,
            './',
            'default',
            $presentation
        );
    };

    $home = $engine()->render('index', [
        'hero_title' => 'Home Hero',
        'sitename' => 'Example Site',
        'tagline' => 'A tagline',
        'body_class' => 'page-front',
        'site_url' => 'https://example.test/',
        'canonical_url' => 'https://example.test/',
    ]);
    $homeBlocks = jsonLdBlocks($home);
    check($homeBlocks !== [] && ($homeBlocks[0]['@type'] ?? '') === 'WebSite', 'home emits WebSite JSON-LD');
    check(
        ($homeBlocks[0]['publisher']['@type'] ?? '') === 'Organization',
        'home nests Organization publisher'
    );
    check(
        ($homeBlocks[0]['publisher']['sameAs'] ?? []) === [
            'https://github.com/example',
            'https://x.com/example',
        ],
        'Organization sameAs comes from social_links'
    );
    check(
        str_contains($home, 'rel="alternate" type="text/plain" href="https://example.test/llms.txt" title="LLM index"'),
        'home has llms.txt alternate when site_url is known'
    );
    check(!str_contains($home, '"@type":"BlogPosting"'), 'home is not BlogPosting');
    check(($homeBlocks[0]['inLanguage'] ?? '') === 'en', 'home WebSite inLanguage');
    $homeAction = $homeBlocks[0]['potentialAction'] ?? [];
    check(($homeAction['@type'] ?? '') === 'SearchAction', 'home emits SearchAction');
    check(
        ($homeAction['target']['urlTemplate'] ?? '') === 'https://example.test/search/?q={search_term_string}',
        'home SearchAction points at /search/?q={search_term_string}'
    );
    check(
        ($homeAction['query-input'] ?? '') === 'required name=search_term_string',
        'home SearchAction query-input'
    );

    $post = $engine()->render('post', [
        'hero_title' => 'Post Title',
        'sitename' => 'Example Site',
        'slug' => 'first-post',
        'author' => 'Ada Lovelace',
        'date' => '2026-08-17',
        'deck' => 'A short deck.',
        'tags' => ['alpha', 'beta'],
        'site_url' => 'https://example.test/',
        'canonical_url' => 'https://example.test/first-post/',
    ]);
    $postBlocks = jsonLdBlocks($post);
    $postTypes = array_map(static fn(array $b): string => (string) ($b['@type'] ?? ''), $postBlocks);
    check(in_array('BlogPosting', $postTypes, true), 'post emits BlogPosting');
    check(in_array('BreadcrumbList', $postTypes, true), 'post emits BreadcrumbList');
    check(!in_array('WebPage', $postTypes, true), 'post is not WebPage');
    $blog = null;
    foreach ($postBlocks as $block) {
        if (($block['@type'] ?? '') === 'BlogPosting') {
            $blog = $block;
            break;
        }
    }
    check(($blog['author']['name'] ?? '') === 'Ada Lovelace', 'post author Person name');
    check(($blog['author']['url'] ?? '') === 'https://ada.example/', 'matched author website becomes Person url');
    check(($blog['author']['description'] ?? '') === 'Mathematician and first programmer.', 'matched author bio becomes Person description');
    check(($blog['author']['jobTitle'] ?? '') === 'Editor', 'matched author role becomes Person jobTitle');
    check(($blog['author']['image'] ?? '') === 'https://cdn.example.test/ada.jpg', 'public avatar URL becomes Person image');
    check(!isset($blog['author']['email']), 'Person does not emit email');
    check(!isset($blog['author']['sameAs']), 'Person does not emit sameAs');
    check(($blog['dateModified'] ?? '') === '2026-08-17T00:00:00Z', 'dateModified falls back to date');
    check(($blog['inLanguage'] ?? '') === 'en', 'post BlogPosting inLanguage');
    check(!isset($blog['potentialAction']), 'post does not emit SearchAction');
    check(($blog['keywords'] ?? '') === 'alpha, beta', 'post keywords from tags');
    check(str_contains($post, '"datePublished":"2026-08-17T00:00:00Z"'), 'post datePublished ISO');
    check(
        str_contains($post, 'property="og:locale" content="en_US"'),
        'post gets og:locale from render language'
    );
    check(
        str_contains($post, 'property="article:published_time" content="2026-08-17T00:00:00Z"'),
        'post gets article:published_time'
    );
    check(
        str_contains($post, 'property="article:modified_time" content="2026-08-17T00:00:00Z"'),
        'post gets article:modified_time falling back to date'
    );

    $page = $engine()->render('page', [
        'hero_title' => 'About',
        'sitename' => 'Example Site',
        'is_page' => true,
        'slug' => 'about',
        'deck' => 'About excerpt',
        'site_url' => 'https://example.test/',
        'canonical_url' => 'https://example.test/about/',
    ]);
    $pageBlocks = jsonLdBlocks($page);
    $pageTypes = array_map(static fn(array $b): string => (string) ($b['@type'] ?? ''), $pageBlocks);
    check(in_array('WebPage', $pageTypes, true), 'page emits WebPage');
    check(in_array('BreadcrumbList', $pageTypes, true), 'page emits BreadcrumbList');
    check(!in_array('BlogPosting', $pageTypes, true), 'page is not BlogPosting');
    check(
        !str_contains($page, 'article:published_time')
            && !str_contains($page, 'article:modified_time'),
        'page does not get article times'
    );
    $webPage = jsonLdByType($pageBlocks, 'WebPage');
    check(($webPage['inLanguage'] ?? '') === 'en', 'page WebPage inLanguage');
    check(!isset($webPage['potentialAction']), 'page does not emit SearchAction');

    $unmatched = $engine()->render('post', [
        'hero_title' => 'Guest Post',
        'sitename' => 'Example Site',
        'slug' => 'guest-post',
        'author' => 'Unknown Writer',
        'date' => '2026-08-17',
        'site_url' => 'https://example.test/',
        'canonical_url' => 'https://example.test/guest-post/',
    ]);
    $unmatchedAuthor = (jsonLdByType(jsonLdBlocks($unmatched), 'BlogPosting') ?? [])['author'] ?? [];
    check(($unmatchedAuthor['name'] ?? '') === 'Unknown Writer', 'unmatched byline keeps the byline name');
    check(
        array_keys($unmatchedAuthor) === ['@type', 'name'],
        'unmatched byline stays name-only Person'
    );

    $partial = $engine()->render('post', [
        'hero_title' => 'Partial Bio',
        'sitename' => 'Example Site',
        'slug' => 'partial-bio',
        'author' => 'Partial Author',
        'date' => '2026-08-17',
        'site_url' => 'https://example.test/',
        'canonical_url' => 'https://example.test/partial-bio/',
    ]);
    $partialAuthor = (jsonLdByType(jsonLdBlocks($partial), 'BlogPosting') ?? [])['author'] ?? [];
    check(($partialAuthor['url'] ?? '') === 'https://partial.example/', 'partial author still emits website url');
    check(!isset($partialAuthor['description']), 'empty bio is omitted');
    check(!isset($partialAuthor['jobTitle']), 'empty role is omitted');
    check(!isset($partialAuthor['image']), 'empty avatar is omitted');

    $bare = $engine()->render('post', [
        'hero_title' => 'Bare Site',
        'sitename' => 'Example Site',
        'slug' => 'bare-site',
        'author' => 'Bare Website',
        'date' => '2026-08-17',
        'site_url' => 'https://example.test/',
        'canonical_url' => 'https://example.test/bare-site/',
    ]);
    $bareAuthor = (jsonLdByType(jsonLdBlocks($bare), 'BlogPosting') ?? [])['author'] ?? [];
    check(!isset($bareAuthor['url']), 'website without http(s) scheme is not Person url');

    $slugMatched = $engine()->render('post', [
        'hero_title' => 'Slug Match',
        'sitename' => 'Example Site',
        'slug' => 'slug-match',
        'author' => 'ada-lovelace',
        'date' => '2026-08-17',
        'site_url' => 'https://example.test/',
        'canonical_url' => 'https://example.test/slug-match/',
    ]);
    $slugAuthor = (jsonLdByType(jsonLdBlocks($slugMatched), 'BlogPosting') ?? [])['author'] ?? [];
    check(($slugAuthor['name'] ?? '') === 'Ada Lovelace', 'byline slug match uses author name');
    check(($slugAuthor['url'] ?? '') === 'https://ada.example/', 'byline slug match still enriches Person');

    $staticPreviewAuthor = (jsonLdByType(jsonLdBlocks($engine()->render('post', [
        'hero_title' => 'Static Preview Author',
        'sitename' => 'Example Site',
        'slug' => 'static-preview-author',
        'author' => 'Preview Author',
        'date' => '2026-08-17',
        'site_url' => 'https://example.test/',
        'canonical_url' => 'https://example.test/static-preview-author/',
    ])), 'BlogPosting') ?? [])['author'] ?? [];
    check(
        ($staticPreviewAuthor['image'] ?? '') === 'https://example.test/images/authors/preview.webp',
        'static relative avatar is absolutized to a public image URL'
    );

    $escaped = $engine()->render('post', [
        'hero_title' => 'A <script> title',
        'sitename' => 'Example Site',
        'slug' => 'lt',
        'canonical_url' => 'https://example.test/lt/',
        'site_url' => 'https://example.test/',
    ]);
    preg_match('#<script type="application/ld\+json">(.*?)</script>#s', $escaped, $escapedMatch);
    $escapedPayload = $escapedMatch[1] ?? '';
    check(str_contains($escapedPayload, '\u003cscript>'), 'JSON-LD escapes < as \\u003c');
    check(!str_contains($escapedPayload, '<script>'), 'raw < is not left in JSON-LD payload');

    $already = $engine()->render('already', [
        'hero_title' => 'Skip',
        'canonical_url' => 'https://example.test/skip/',
        'site_url' => 'https://example.test/',
        'is_page' => true,
    ]);
    check(
        substr_count($already, 'application/ld+json') === 1,
        'existing JSON-LD is not duplicated'
    );

    $search = $engine()->render('search', [
        'hero_title' => 'Search',
        'sitename' => 'Example Site',
        'canonical_url' => 'https://example.test/search/',
        'site_url' => 'https://example.test/',
        'i18n_surface' => 'search',
    ]);
    check(jsonLdBlocks($search) === [], 'search template gets no JSON-LD');
    check(
        str_contains($search, 'href="https://example.test/llms.txt"'),
        'search still gets llms.txt alternate'
    );
    check(
        str_contains($search, 'name="robots" content="noindex,nofollow"'),
        'search HTML prefers noindex'
    );

    $indexed = $engine()->render('post', [
        'hero_title' => 'Public Post',
        'sitename' => 'Example Site',
        'slug' => 'public-post',
        'canonical_url' => 'https://example.test/public-post/',
        'site_url' => 'https://example.test/',
    ]);
    check(
        str_contains($indexed, 'name="robots" content="index,follow,max-image-preview:large"'),
        'indexable URL keeps site-wide robots default plus max-image-preview:large'
    );

    $unlisted = $engine()->render('post', [
        'hero_title' => 'Hidden Post',
        'sitename' => 'Example Site',
        'slug' => 'hidden-post',
        'canonical_url' => 'https://example.test/hidden-post/',
        'site_url' => 'https://example.test/',
        'noindex' => true,
    ]);
    check(
        str_contains($unlisted, 'name="robots" content="noindex,nofollow"'),
        'noindex post overrides site-wide robots'
    );

    $unlistedPage = $engine()->render('page', [
        'hero_title' => 'Secret notes',
        'sitename' => 'Example Site',
        'slug' => 'secret-notes',
        'canonical_url' => 'https://example.test/secret-notes/',
        'site_url' => 'https://example.test/',
        'is_page' => true,
        'noindex' => true,
    ]);
    check(
        str_contains($unlistedPage, 'name="robots" content="noindex,nofollow"'),
        'noindex page overrides site-wide robots'
    );

    $preview = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        $presentation
    )->render('post', [
        'hero_title' => 'Preview Post',
        'sitename' => 'Example Site',
        'slug' => 'preview-post',
        'author' => 'Preview Author',
        'canonical_url' => 'https://example.test/preview-post/',
    ]);
    $previewTypes = array_map(
        static fn(array $b): string => (string) ($b['@type'] ?? ''),
        jsonLdBlocks($preview)
    );
    check(in_array('BlogPosting', $previewTypes, true), 'preview HTML also receives JSON-LD');
    check(
        str_contains($preview, 'href="https://example.test/llms.txt"'),
        'preview derives llms.txt alternate from canonical origin'
    );
    $previewAuthor = (jsonLdByType(jsonLdBlocks($preview), 'BlogPosting') ?? [])['author'] ?? [];
    check(($previewAuthor['url'] ?? '') === 'https://preview-author.example/', 'preview still emits Person url');
    check(!isset($previewAuthor['image']), 'preview /api/ avatar is not Person image');

    $i18nPresentation = array_replace($presentation, [
        'languages' => ['en', 'fr'],
        'i18n_active' => true,
    ]);
    $i18nEngine = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        true,
        '../',
        'default',
        $i18nPresentation
    );
    $i18nPage = [
        'hero_title' => 'Guide',
        'sitename' => 'Example Site',
        'slug' => 'guide',
        'date' => '2026-08-17',
        'updated' => '2026-08-18T15:30:00Z',
        'site_url' => 'https://example.test/',
        'canonical_url' => 'https://example.test/fr/guide/',
        'language' => 'fr',
        'i18n_current_live' => true,
        'translations' => [
            [
                'language' => 'en',
                'status' => 'published',
                'published' => true,
            ],
        ],
    ];
    $frPost = $i18nEngine->render('post', $i18nPage);
    check(
        str_contains(
            $frPost,
            '<link rel="alternate" hreflang="x-default" href="../guide/index.html">'
        ),
        'localized post x-default points at default-language URL'
    );
    check(
        str_contains($frPost, 'property="og:locale" content="fr_FR"'),
        'localized post og:locale is the render language'
    );
    check(
        str_contains($frPost, 'property="og:locale:alternate" content="en_US"'),
        'localized post og:locale:alternate lists published siblings'
    );
    check(
        str_contains($frPost, 'property="article:modified_time" content="2026-08-18T15:30:00Z"'),
        'post article:modified_time uses updated when present'
    );
    $frBlog = jsonLdByType(jsonLdBlocks($frPost), 'BlogPosting');
    check(($frBlog['inLanguage'] ?? '') === 'fr', 'localized post inLanguage is BCP 47 fr');
    check(($frBlog['dateModified'] ?? '') === '2026-08-18T15:30:00Z', 'dateModified matches article:modified_time');

    $frHome = $i18nEngine->render('index', [
        'hero_title' => 'Accueil',
        'sitename' => 'Example Site',
        'tagline' => 'A tagline',
        'body_class' => 'page-front',
        'site_url' => 'https://example.test/',
        'canonical_url' => 'https://example.test/fr/',
        'language' => 'fr',
        'i18n_surface' => 'home',
    ]);
    $frHomeBlock = jsonLdByType(jsonLdBlocks($frHome), 'WebSite');
    check(($frHomeBlock['inLanguage'] ?? '') === 'fr', 'localized home inLanguage is fr');
    check(
        ($frHomeBlock['potentialAction']['target']['urlTemplate'] ?? '')
            === 'https://example.test/fr/search/?q={search_term_string}',
        'localized home SearchAction points at /fr/search/'
    );

    $faqPairs = [
        ['q' => 'What is PenCMS?', 'a' => 'A blog CMS.'],
        ['q' => 'Does empty FAQ emit schema?', 'a' => 'No. Empty is valid and silent.'],
    ];
    $postWithFaqs = $engine()->render('post', [
        'hero_title' => 'Docs Guide',
        'sitename' => 'Example Site',
        'slug' => 'docs-guide',
        'author' => 'Ada Lovelace',
        'date' => '2026-08-17',
        'site_url' => 'https://example.test/',
        'canonical_url' => 'https://example.test/docs-guide/',
        'faqs' => $faqPairs,
    ]);
    $postFaq = jsonLdByType(jsonLdBlocks($postWithFaqs), 'FAQPage');
    check($postFaq !== null, 'non-empty faqs emit FAQPage on a post');
    check(
        ($postFaq['mainEntity'][0]['name'] ?? '') === 'What is PenCMS?'
            && ($postFaq['mainEntity'][0]['acceptedAnswer']['text'] ?? '') === 'A blog CMS.'
            && ($postFaq['mainEntity'][1]['name'] ?? '') === 'Does empty FAQ emit schema?'
            && ($postFaq['mainEntity'][1]['acceptedAnswer']['text'] ?? '') === 'No. Empty is valid and silent.',
        'FAQPage strings match the visible Q&A pairs'
    );
    check(str_contains($postWithFaqs, 'class="pen-qa"'), 'non-empty faqs emit Q&A chrome');
    check(
        str_contains($postWithFaqs, '<h2 class="pen-qa-heading">FAQ</h2>'),
        'default theme labels the Q&A block FAQ'
    );
    check(
        str_contains($postWithFaqs, '<dt>What is PenCMS?</dt>')
            && str_contains($postWithFaqs, '<dd>A blog CMS.</dd>')
            && str_contains($postWithFaqs, '<dt>Does empty FAQ emit schema?</dt>')
            && str_contains($postWithFaqs, '<dd>No. Empty is valid and silent.</dd>'),
        'visible Q&A HTML matches FAQPage strings'
    );
    check(
        jsonLdByType(jsonLdBlocks($postWithFaqs), 'BlogPosting') !== null,
        'FAQPage is in addition to BlogPosting, not a replacement'
    );

    $pageWithFaqs = $engine()->render('page', [
        'hero_title' => 'About FAQs',
        'sitename' => 'Example Site',
        'is_page' => true,
        'slug' => 'about-faqs',
        'site_url' => 'https://example.test/',
        'canonical_url' => 'https://example.test/about-faqs/',
        'faqs' => $faqPairs,
    ]);
    check(
        jsonLdByType(jsonLdBlocks($pageWithFaqs), 'FAQPage') !== null,
        'non-empty faqs emit FAQPage on a page'
    );
    check(str_contains($pageWithFaqs, 'class="pen-qa"'), 'non-empty faqs emit Q&A chrome on a page');
    check(
        str_contains($pageWithFaqs, '<h2 class="pen-qa-heading">FAQ</h2>'),
        'default theme labels the Q&A block FAQ on a page'
    );

    $escapedFaqs = $engine()->render('post', [
        'hero_title' => 'Escaped FAQ',
        'sitename' => 'Example Site',
        'slug' => 'escaped-faq',
        'site_url' => 'https://example.test/',
        'canonical_url' => 'https://example.test/escaped-faq/',
        'faqs' => [
            ['q' => 'What about <script>alert(1)</script>?', 'a' => 'Treat it as <text>.'],
        ],
    ]);
    $escapedFaqPage = jsonLdByType(jsonLdBlocks($escapedFaqs), 'FAQPage');
    check(
        ($escapedFaqPage['mainEntity'][0]['name'] ?? '') === 'What about <script>alert(1)</script>?'
            && ($escapedFaqPage['mainEntity'][0]['acceptedAnswer']['text'] ?? '') === 'Treat it as <text>.',
        'FAQPage keeps the original Q&A strings including <'
    );
    check(
        str_contains($escapedFaqs, '<dt>What about &lt;script&gt;alert(1)&lt;/script&gt;?</dt>')
            && str_contains($escapedFaqs, '<dd>Treat it as &lt;text&gt;.</dd>'),
        'visible Q&A HTML escapes angle brackets'
    );
    preg_match_all('#<script type="application/ld\+json">(.*?)</script>#s', $escapedFaqs, $escapedFaqScripts);
    $escapedFaqPayload = implode("\n", $escapedFaqScripts[1] ?? []);
    check(str_contains($escapedFaqPayload, '\u003cscript>'), 'FAQPage JSON-LD escapes < as \\u003c');
    check(!str_contains($escapedFaqPayload, '<script>alert'), 'raw <script> is not left in FAQPage JSON-LD');

    $missingFaqs = $engine()->render('post', [
        'hero_title' => 'Poem',
        'sitename' => 'Example Site',
        'slug' => 'poem',
        'site_url' => 'https://example.test/',
        'canonical_url' => 'https://example.test/poem/',
    ]);
    check(
        jsonLdByType(jsonLdBlocks($missingFaqs), 'FAQPage') === null
            && !str_contains($missingFaqs, 'class="pen-qa"')
            && !str_contains($missingFaqs, 'pen-qa-heading'),
        'missing faqs emits no FAQPage and no Q&A chrome'
    );

    $emptyFaqs = $engine()->render('post', [
        'hero_title' => 'News Brief',
        'sitename' => 'Example Site',
        'slug' => 'news-brief',
        'site_url' => 'https://example.test/',
        'canonical_url' => 'https://example.test/news-brief/',
        'faqs' => [],
    ]);
    check(
        jsonLdByType(jsonLdBlocks($emptyFaqs), 'FAQPage') === null
            && !str_contains($emptyFaqs, 'class="pen-qa"')
            && !str_contains($emptyFaqs, 'pen-qa-heading'),
        'empty faqs list emits no FAQPage and no Q&A chrome'
    );

    $blankFaqs = $engine()->render('post', [
        'hero_title' => 'Whitespace FAQ',
        'sitename' => 'Example Site',
        'slug' => 'whitespace-faq',
        'site_url' => 'https://example.test/',
        'canonical_url' => 'https://example.test/whitespace-faq/',
        'faqs' => [
            ['q' => '   ', 'a' => 'still blank question'],
            ['q' => 'Only question', 'a' => ''],
            ['q' => '', 'a' => 'Only answer'],
        ],
    ]);
    check(
        jsonLdByType(jsonLdBlocks($blankFaqs), 'FAQPage') === null
            && !str_contains($blankFaqs, 'class="pen-qa"'),
        'whitespace-only or incomplete pairs emit no FAQPage and no Q&A chrome'
    );

    $mixedFaqs = $engine()->render('post', [
        'hero_title' => 'Mixed FAQ',
        'sitename' => 'Example Site',
        'slug' => 'mixed-faq',
        'site_url' => 'https://example.test/',
        'canonical_url' => 'https://example.test/mixed-faq/',
        'faqs' => [
            ['q' => '', 'a' => 'drop me'],
            ['q' => 'Keep this?', 'a' => 'Yes.'],
            ['q' => '   ', 'a' => 'nope'],
        ],
    ]);
    $mixedFaqPage = jsonLdByType(jsonLdBlocks($mixedFaqs), 'FAQPage');
    check(
        is_array($mixedFaqPage)
            && count($mixedFaqPage['mainEntity'] ?? []) === 1
            && ($mixedFaqPage['mainEntity'][0]['name'] ?? '') === 'Keep this?'
            && ($mixedFaqPage['mainEntity'][0]['acceptedAnswer']['text'] ?? '') === 'Yes.',
        'mixed list emits only complete Q&A pairs'
    );
    check(
        str_contains($mixedFaqs, '<dt>Keep this?</dt>')
            && str_contains($mixedFaqs, '<dd>Yes.</dd>')
            && !str_contains($mixedFaqs, 'drop me'),
        'mixed list visible HTML includes only complete pairs'
    );

    $alreadyWithFaqs = $engine()->render('already', [
        'hero_title' => 'Skip with FAQs',
        'canonical_url' => 'https://example.test/skip-faqs/',
        'site_url' => 'https://example.test/',
        'is_page' => true,
        'faqs' => $faqPairs,
    ]);
    check(
        substr_count($alreadyWithFaqs, 'application/ld+json') === 1,
        'existing JSON-LD still skips ThemeEngine FAQPage'
    );
    check(
        jsonLdByType(jsonLdBlocks($alreadyWithFaqs), 'FAQPage') === null,
        'skip-if-present does not add FAQPage'
    );
    check(
        str_contains($alreadyWithFaqs, 'class="pen-qa"')
            && str_contains($alreadyWithFaqs, '<dt>What is PenCMS?</dt>'),
        'skip-if-present still injects visible Q&A HTML'
    );

    $homeWithFaqs = $engine()->render('index', [
        'hero_title' => 'Home Hero',
        'sitename' => 'Example Site',
        'tagline' => 'A tagline',
        'body_class' => 'page-front',
        'site_url' => 'https://example.test/',
        'canonical_url' => 'https://example.test/',
        'faqs' => $faqPairs,
    ]);
    check(
        jsonLdByType(jsonLdBlocks($homeWithFaqs), 'FAQPage') === null
            && !str_contains($homeWithFaqs, 'class="pen-qa"'),
        'home does not emit FAQPage or Q&A chrome even if faqs are stuffed in'
    );

    $searchWithFaqs = $engine()->render('search', [
        'hero_title' => 'Search',
        'sitename' => 'Example Site',
        'canonical_url' => 'https://example.test/search/',
        'site_url' => 'https://example.test/',
        'i18n_surface' => 'search',
        'faqs' => $faqPairs,
    ]);
    check(
        jsonLdByType(jsonLdBlocks($searchWithFaqs), 'FAQPage') === null
            && !str_contains($searchWithFaqs, 'class="pen-qa"'),
        'search does not emit FAQPage or Q&A chrome even if faqs are stuffed in'
    );

    file_put_contents(
        $theme . '/templates/explicit-faq.html.twig',
        '<html lang="en"><head></head><body><main><div class="custom-spot">{{ theme.partial("faqs")|raw }}</div></main></body></html>'
    );
    $explicitFaqs = $engine()->render('explicit-faq', [
        'hero_title' => 'Explicit Partial FAQs',
        'canonical_url' => 'https://example.test/explicit-faqs/',
        'site_url' => 'https://example.test/',
        'is_page' => true,
        'faqs' => $faqPairs,
    ]);
    check(
        substr_count($explicitFaqs, 'class="pen-qa"') === 1,
        'explicit theme.partial("faqs") does not double-inject at </main>'
    );
    check(
        str_contains($explicitFaqs, '<div class="custom-spot"><section class="pen-qa"')
            || str_contains($explicitFaqs, '<div class="custom-spot">' . "\n" . '<section class="pen-qa"'),
        'explicit theme.partial("faqs") renders at the designated template position'
    );
    check(
        jsonLdByType(jsonLdBlocks($explicitFaqs), 'FAQPage') !== null,
        'explicit theme.partial("faqs") still emits FAQPage JSON-LD schema'
    );

    writeJson($theme . '/theme.json', [
        'type' => 'native',
        'name' => 'Fixture',
        'version' => '1.0.0',
        'variables' => [],
        'qa_heading' => 'backgrounder',
    ]);
    $newsExplainer = $engine()->render('post', [
        'hero_title' => 'News Explainer',
        'sitename' => 'Example Site',
        'slug' => 'news-explainer',
        'site_url' => 'https://example.test/',
        'canonical_url' => 'https://example.test/news-explainer/',
        'faqs' => $faqPairs,
    ]);
    $newsFaq = jsonLdByType(jsonLdBlocks($newsExplainer), 'FAQPage');
    check(
        str_contains($newsExplainer, '<h2 class="pen-qa-heading">Backgrounder</h2>'),
        'qa_heading backgrounder labels the Q&A block Backgrounder'
    );
    check(
        !str_contains($newsExplainer, '<h2 class="pen-qa-heading">FAQ</h2>'),
        'Backgrounder chrome does not also say FAQ'
    );
    check(
        $newsFaq !== null && ($newsFaq['@type'] ?? '') === 'FAQPage',
        'Backgrounder chrome still emits FAQPage'
    );
    check(
        !str_contains($newsExplainer, '"@type":"Backgrounder"'),
        'Backgrounder is chrome, not a second schema type'
    );
} finally {
    removeTree($root);
}

echo "JSON-LD injection: {$passed} passed, {$failed} failed\n";
if ($failed > 0) {
    foreach ($failures as $failure) {
        echo "  FAIL: {$failure}\n";
    }
    exit(1);
}
echo "OK\n";
