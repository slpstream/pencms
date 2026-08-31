<?php

declare(strict_types=1);

require_once __DIR__ . '/../vendor/autoload.php';
require_once __DIR__ . '/../src/core/ThemeEngine.php';

use Dossier\ThemeEngine;

$passed = 0;
$failed = 0;
/** @var list<string> $failures */
$failures = [];

function checkInject(bool $condition, string $label): void
{
    global $passed, $failed, $failures;
    if ($condition) {
        $passed++;
        return;
    }
    $failed++;
    $failures[] = $label;
}

function removeInjectTree(string $path): void
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
            removeInjectTree($child);
        } else {
            unlink($child);
        }
    }
    rmdir($path);
}

$root = sys_get_temp_dir() . '/pencms-comment-inject-' . getmypid();
$backend = $root . '/backend';
$themes = $backend . '/themes';
$fixture = $themes . '/fixture';
$international = $themes . '/international/partials';
$content = $root . '/content';
$threadSrc = __DIR__ . '/../src/blog/themes/international/partials/_comment-thread.html.twig';
$formSrc = __DIR__ . '/../src/blog/themes/international/partials/_feedback-form.html.twig';

try {
    @mkdir($backend . '/data', 0777, true);
    @mkdir($fixture . '/templates', 0777, true);
    @mkdir($international, 0777, true);
    @mkdir($content . '/sites/default', 0777, true);

    file_put_contents(
        $backend . '/config.ini',
        "[Paths]\ncontent_dir = ../content\n"
        . "[Server]\napi_port = 1\n"
        . "[theme]\nactive = fixture\ndirectory = themes\nweb_root = /blog/\n"
    );
    file_put_contents(
        $fixture . '/theme.json',
        json_encode([
            'type' => 'native',
            'name' => 'Comment Inject Fixture',
            'version' => '1.0.0',
            'variables' => [],
        ], JSON_PRETTY_PRINT)
    );
    if (!copy($threadSrc, $international . '/_comment-thread.html.twig')) {
        throw new RuntimeException('Could not copy comment-thread partial');
    }
    if (!copy($formSrc, $international . '/_feedback-form.html.twig')) {
        throw new RuntimeException('Could not copy feedback-form partial');
    }

    $pair = "{{ theme.partial('comment-thread') | raw }}\n"
        . "{{ theme.partial('feedback-form', { kind: 'comment', parent_slug: slug is defined ? slug : '' }) | raw }}\n";
    $contact = "{{ theme.partial('feedback-form', { kind: 'contact' }) | raw }}\n";

    file_put_contents(
        $fixture . '/templates/post.html.twig',
        '<html><body><main><article>BODY</article></main></body></html>'
    );
    file_put_contents(
        $fixture . '/templates/post-with-pair.html.twig',
        '<html><body><main><article>BODY</article>' . $pair . '</main></body></html>'
    );
    file_put_contents(
        $fixture . '/templates/page.html.twig',
        '<html><body><main>' . $contact . '</main></body></html>'
    );

    $basePresentation = [
        'site_id' => 'default',
        'theme' => 'fixture',
        'content_relpath' => 'sites/default',
        'language' => 'en',
        'languages' => ['en'],
        'language_labels' => [],
        'i18n_active' => false,
        'contact_email' => 'ops@example.com',
    ];
    $page = [
        'hero_title' => 'Guide',
        'slug' => 'guide',
        'canonical_url' => 'https://example.test/blog/post.php?slug=guide',
    ];

    $offWithPair = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        array_merge($basePresentation, ['comments_enabled' => false])
    );
    // ThemeEngine resolves post.html.twig; write the pair into post.html.twig for this case.
    file_put_contents(
        $fixture . '/templates/post.html.twig',
        '<html><body><main><article>BODY</article>' . $pair . $contact . '</main></body></html>'
    );
    $htmlOff = $offWithPair->render('post', $page);
    checkInject(
        !str_contains($htmlOff, 'data-pen-comments')
            && !str_contains($htmlOff, 'class="pen-comments"')
            && !str_contains($htmlOff, 'name="kind" value="comment"')
            && str_contains($htmlOff, 'name="kind" value="contact"')
            && str_contains($htmlOff, 'data-pen-feedback'),
        'flag off + theme partials: no comment chrome; contact form still renders'
    );

    file_put_contents(
        $fixture . '/templates/post.html.twig',
        '<html><body><main><article>BODY</article></main></body></html>'
    );
    $htmlOnInject = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        array_merge($basePresentation, ['comments_enabled' => true])
    )->render('post', $page);
    $threadCount = substr_count($htmlOnInject, 'data-pen-comments');
    $formCount = substr_count($htmlOnInject, 'name="kind" value="comment"');
    checkInject(
        $threadCount === 1 && $formCount === 1
            && str_contains($htmlOnInject, '</article>')
            && strpos($htmlOnInject, 'data-pen-comments') < strpos($htmlOnInject, '</main'),
        'flag on + theme omits pair: injected once before </main>'
    );

    file_put_contents(
        $fixture . '/templates/post.html.twig',
        '<html><body><main><article>BODY</article>' . $pair . '</main></body></html>'
    );
    $htmlOnPresent = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        array_merge($basePresentation, ['comments_enabled' => true])
    )->render('post', $page);
    checkInject(
        substr_count($htmlOnPresent, 'data-pen-comments') === 1
            && substr_count($htmlOnPresent, 'name="kind" value="comment"') === 1,
        'flag on + theme already has the pair: not duplicated'
    );

    $htmlPageContactOff = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        array_merge($basePresentation, ['comments_enabled' => false])
    )->render('page', $page);
    checkInject(
        str_contains($htmlPageContactOff, 'name="kind" value="contact"')
            && !str_contains($htmlPageContactOff, 'name="kind" value="comment"')
            && !str_contains($htmlPageContactOff, 'data-pen-comments'),
        'comments off does not inject comment chrome onto pages; contact form unchanged'
    );

    $htmlStatic = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        true,
        '../',
        'default',
        array_merge($basePresentation, [
            'comments_enabled' => true,
            'feedback_submission_key' => 'bakekey0123456789abcdef01234567',
        ])
    )->render('post', $page);
    checkInject(
        str_contains($htmlStatic, 'action="https://feedback.pencms.org/submit"')
            && str_contains($htmlStatic, 'name="submission_key" value="bakekey0123456789abcdef01234567"')
            && !str_contains($htmlStatic, 'action="/api/v1/feedback"'),
        'static bake with comments on still POSTs to the default relay with submission_key'
    );
} finally {
    removeInjectTree($root);
}

echo "Comment injection: {$passed} passed, {$failed} failed\n";
if ($failures !== []) {
    foreach ($failures as $label) {
        echo "  FAIL: {$label}\n";
    }
    exit(1);
}
