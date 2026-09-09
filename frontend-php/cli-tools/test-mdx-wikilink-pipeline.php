<?php

declare(strict_types=1);

/**
 * Pipeline coverage for the MDX + wikilink migration.
 *
 * Usage: php cli-tools/test-mdx-wikilink-pipeline.php
 */

require_once __DIR__ . '/../src/core/PostRenderer.php';
require_once __DIR__ . '/../src/core/ContentUrls.php';
require_once __DIR__ . '/../src/core/ComponentProcessor.php';
require_once __DIR__ . '/../src/core/WikilinkProcessor.php';
require_once __DIR__ . '/../src/core/InternalAPIClient.php';

use Dossier\ComponentProcessor;
use Dossier\ContentUrls;
use Dossier\InternalAPIClient;
use Dossier\PostRenderer;
use Dossier\WikilinkProcessor;

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

final class MdxFakeApi extends InternalAPIClient
{
    public function __construct()
    {
    }

    public function getSiteId(): string
    {
        return 'default';
    }

    public function get($endpoint, $params = [])
    {
        if ($endpoint === '/pages/target-post') {
            return [
                'frontmatter' => [
                    'status' => 'published',
                    'hero_title' => 'Target Title',
                    'title' => 'Target Title',
                ],
                'content' => "# Hello\n\nTarget body text.",
                'composite' => false,
                'partials' => [],
            ];
        }
        throw new \Exception('not found: ' . $endpoint);
    }
}

ContentUrls::$basePath = '/assets/';
ContentUrls::setLanguage(null);

$renderer = new PostRenderer(new MdxFakeApi());

// 1. Built-in MDX components → Session 5 HTML
$html = $renderer->renderMarkdownFragment(
    '<Image src="images/content/a.jpg" caption="A photo" alt="Alt" />'
);
check(str_contains($html, '<figure class="traven-image-figure'), 'Image caption figure class');
check(str_contains($html, 'class="traven-image"'), 'Image img class');
check(str_contains($html, 'traven-image-caption'), 'Image caption class');
check(!str_contains($html, 'gallery-single'), 'Image emits no gallery-single');

$html = $renderer->renderMarkdownFragment('<Image src="images/content/a.jpg" alt="Alt" />');
check(str_contains($html, 'class="traven-image align-center size-medium"'), 'Bare Image exact classes');

$html = $renderer->renderMarkdownFragment('<Quote author="Jane">Hello **world**</Quote>');
check(str_contains($html, 'traven-component-blockquote'), 'Quote blockquote class');
check(str_contains($html, '<cite>'), 'Quote cite');
check(str_contains($html, '<strong>world</strong>'), 'Quote inner markdown compiled');

$html = $renderer->renderMarkdownFragment('<Callout type="info" title="Note">Some *tip*</Callout>');
check(str_contains($html, 'traven-component traven-component-info'), 'Callout info class');
check(str_contains($html, '<em>tip</em>'), 'Callout inner markdown compiled');

$html = $renderer->renderMarkdownFragment('<Video src="https://www.youtube.com/watch?v=dQw4w9WgXcQ" />');
check(str_contains($html, 'youtube-nocookie.com/embed/dQw4w9WgXcQ'), 'Published YouTube keeps nocookie');

$html = $renderer->renderMarkdownFragment('<Figure>Inner *text*</Figure>');
check(str_contains($html, '<figure class="traven-figure'), 'Figure wrapper class');
check(str_contains($html, '<em>text</em>'), 'Figure inner markdown compiled');

// Lowercase HTML tags stay untouched
$html = $renderer->renderMarkdownFragment('<video src="a.mp4" controls></video>');
check(str_contains($html, '<video src="a.mp4" controls></video>'), 'Lowercase video untouched');

// 2. Wikilink link → real href
$html = $renderer->renderMarkdownFragment('See [[target-post|Target]] now.');
check(str_contains($html, 'class="traven-wikilink"'), 'Wikilink class');
check(str_contains($html, 'post.php?slug=target-post'), 'Wikilink real href');
check(str_contains($html, 'data-slug="target-post"'), 'Wikilink data-slug');
check(!str_contains($html, 'href="#"'), 'Wikilink never preview href');

// 3. Embed omit for missing/unpublished
$html = $renderer->renderMarkdownFragment('Before [[!missing-slug]] after.');
check(!str_contains($html, 'traven-embed'), 'Missing embed omitted');
check(str_contains($html, 'Before') && str_contains($html, 'after'), 'Missing embed leaves text');

// 4. Expand trigger + template / embed body for published targets
$html = $renderer->renderMarkdownFragment('Open [[>target-post|Label]] end.');
check(str_contains($html, 'class="traven-expand-trigger"'), 'Expand trigger class');
check(str_contains($html, '<template id="traven-ee-'), 'Expand template present');
check(str_contains($html, '>Label</button>'), 'Expand label');

$html = $renderer->renderMarkdownFragment('Open [[>target-post]] end.');
check(str_contains($html, '>Target Title</button>'), 'Expand label falls back to display title');

$html = $renderer->renderMarkdownFragment('See [[!target-post]] end.');
check(str_contains($html, '<div class="traven-embed"'), 'Embed wrapper');
check(str_contains($html, 'Target body text.'), 'Embed body resolved');

// Invalid combos omit without API surprises
$html = $renderer->renderMarkdownFragment('X [[>target-post#H^summary|L]] Y.');
check(!str_contains($html, 'traven-expand-trigger'), 'source+heading omits');
$html = $renderer->renderMarkdownFragment('X [[>target-post^bogus|L]] Y.');
check(!str_contains($html, 'traven-expand-trigger'), 'unknown source omits');

// 5. Code fences + inline code are protected
$html = $renderer->renderMarkdownFragment("```\n[[target-post]] and <Image src=\"x\" />\n```");
check(str_contains($html, '[[target-post]]'), 'Fenced wikilink untouched');
$html = $renderer->renderMarkdownFragment('Inline `[[target-post]]` stays.');
check(str_contains($html, '<code>[[target-post]]</code>'), 'Inline code untouched');

// 6. CommonMark single brackets untouched
$html = $renderer->renderMarkdownFragment('[normal link](https://example.com)');
check(str_contains($html, '<a href="https://example.com">normal link</a>'), 'Markdown link normal');
$html = $renderer->renderMarkdownFragment("- [ ] task item");
check(str_contains($html, 'task-list-item'), 'Task list intact');
check(!str_contains($html, '[link='), 'No link transcode resurrection');

// 7. Legacy shortcodes are NOT compiled
$html = $renderer->renderMarkdownFragment('[expand slug="x"]');
check(!str_contains($html, 'traven-expand-trigger'), 'Legacy expand not compiled');
$html = $renderer->renderMarkdownFragment('[image src="a.jpg"]');
check(!str_contains($html, 'gallery-single') && !str_contains($html, 'traven-image'), 'Legacy image not compiled');

// 8. Agent flattening emits readable Markdown, never shortcodes
$flat = ComponentProcessor::flattenForMarkdown('<Image src="a.jpg" alt="Alt" caption="Cap" />');
check(str_contains($flat, '![Alt](a.jpg)'), 'Image flattens to markdown image');
$flat = ComponentProcessor::flattenForMarkdown('<Quote author="J">Hi</Quote>');
check(str_contains($flat, '> Hi'), 'Quote flattens to blockquote');
$flat = WikilinkProcessor::flattenForMarkdown('See [[target-post|Target]] and [[>other|L]] and [[!emb]].');
check(str_contains($flat, '[Target](post.php?slug=target-post'), 'Wikilink flattens to markdown link');
check(!str_contains($flat, '[expand ') && !str_contains($flat, '[embed ') && !str_contains($flat, '[image '), 'Flatten emits no shortcodes');
check(str_contains($flat, '[expand: other]'), 'Expand flattens to labeled reference');

foreach ($failures as $failure) {
    fwrite(STDERR, "[FAIL] {$failure}\n");
}
echo "MDX wikilink pipeline: {$passed} passed, {$failed} failed\n";
exit($failed > 0 ? 1 : 0);
