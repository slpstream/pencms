<?php

declare(strict_types=1);

require_once __DIR__ . '/../src/core/LlmsTxtBuilder.php';

use Dossier\LlmsTxtBuilder;

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

$index = LlmsTxtBuilder::buildIndex(
    'Example Site',
    'A tagline',
    'https://example.test/',
    [
        ['slug' => 'about', 'hero_title' => 'About', 'page' => true, 'deck' => 'About the site'],
        ['slug' => 'translated', 'hero_title' => 'Default dossier', 'page' => false, 'deck' => ''],
        ['slug' => 'secret-notes', 'hero_title' => 'Secret notes', 'page' => true, 'noindex' => true],
        ['slug' => 'hidden-post', 'hero_title' => 'Hidden post', 'page' => false, 'noindex' => true],
    ]
);

check(str_contains($index, '## Pages'), 'index has Pages');
check(str_contains($index, '## Posts'), 'index has Posts');
check(str_contains($index, 'about/index.md'), 'indexable page is listed');
check(str_contains($index, 'translated/index.md'), 'indexable post is listed');
check(!str_contains($index, 'secret-notes'), 'noindex page omitted from llms.txt');
check(!str_contains($index, 'hidden-post'), 'noindex post omitted from llms.txt');
check(
    str_contains($index, '- [llms-full.txt](https://example.test/llms-full.txt)'),
    'index links llms-full.txt first in archives'
);
check(!str_contains($index, 'llm.txt'), 'index does not invent llm.txt');

$full = LlmsTxtBuilder::buildFull(
    'Example Site',
    'A tagline',
    [
        [
            'title' => 'About',
            'url' => 'https://example.test/about/',
            'published' => '2026-08-01',
            'author' => 'Ada',
            'markdown' => "---\ntitle: About\n---\n\n# About\n\nAbout page body.\n",
        ],
        [
            'title' => 'Default dossier',
            'url' => 'https://example.test/translated/',
            'published' => '2026-08-01',
            'markdown' => "---\ntitle: Default dossier\n---\n\n# Default dossier\n\nEnglish body.\n",
        ],
    ]
);

check(str_starts_with($full, "# Example Site\n> A tagline\n"), 'full corpus has sitename and tagline');
check(str_contains($full, "URL: https://example.test/about/"), 'full corpus has HTML URL header');
check(str_contains($full, 'Published: 2026-08-01'), 'full corpus has Published');
check(str_contains($full, 'Author: Ada'), 'full corpus has Author');
check(str_contains($full, 'About page body.'), 'full corpus keeps native markdown');
check(str_contains($full, 'English body.'), 'full corpus includes later items');

$tiny = LlmsTxtBuilder::buildFull(
    'Cap Site',
    '',
    [
        [
            'title' => 'First',
            'url' => 'https://example.test/first/',
            'markdown' => str_repeat('A', 80),
        ],
        [
            'title' => 'Second',
            'url' => 'https://example.test/second/',
            'markdown' => str_repeat('B', 80),
        ],
    ],
    200
);

check(str_contains($tiny, 'URL: https://example.test/first/'), 'truncation keeps first document that fits');
check(!str_contains($tiny, 'URL: https://example.test/second/'), 'truncation omits documents that would exceed cap');
check(str_contains($tiny, '[truncated]'), 'truncation footer is present');
check(!str_contains($tiny, str_repeat('B', 80)), 'truncated body of omitted doc is absent');

echo "Passed: {$passed}\nFailed: {$failed}\n";
if ($failures !== []) {
    echo "Failures:\n- " . implode("\n- ", $failures) . "\n";
    exit(1);
}
exit(0);
