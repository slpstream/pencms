<?php

declare(strict_types=1);

require_once __DIR__ . '/../vendor/autoload.php';
require_once __DIR__ . '/../src/core/ThemeEngine.php';
require_once __DIR__ . '/../src/core/SiteRegistry.php';

use Dossier\SiteRegistry;
use Dossier\ThemeEngine;

$passed = 0;
$failed = 0;
/** @var list<string> $failures */
$failures = [];

function checkFeedback(bool $condition, string $label): void
{
    global $passed, $failed, $failures;
    if ($condition) {
        $passed++;
        return;
    }
    $failed++;
    $failures[] = $label;
}

function removeFeedbackTree(string $path): void
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
            removeFeedbackTree($child);
        } else {
            unlink($child);
        }
    }
    rmdir($path);
}

$root = sys_get_temp_dir() . '/pencms-feedback-form-' . getmypid();
$backend = $root . '/backend';
$themes = $backend . '/themes';
$fixture = $themes . '/fixture';
$globalPartials = $themes . '/global/partials';
$content = $root . '/content';
$realPartial = __DIR__ . '/../src/blog/themes/international/partials/_feedback-form.html.twig';

try {
    @mkdir($backend . '/data', 0777, true);
    @mkdir($fixture . '/templates', 0777, true);
    @mkdir($fixture . '/partials', 0777, true);
    @mkdir($globalPartials, 0777, true);
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
            'name' => 'Feedback Fixture',
            'version' => '1.0.0',
            'variables' => [],
        ], JSON_PRETTY_PRINT)
    );
    if (!copy($realPartial, $globalPartials . '/_feedback-form.html.twig')) {
        throw new RuntimeException('Could not copy global feedback-form partial into fixture tree');
    }
    file_put_contents(
        $fixture . '/templates/page.html.twig',
        '<html><body>'
        . '{{ theme.partial("feedback-form", { kind: "comment", parent_slug: "my-post" })|raw }}'
        . '</body></html>'
    );
    file_put_contents(
        $fixture . '/templates/post.html.twig',
        '<html><body>'
        . "{{ theme.partial('feedback-form', { kind: 'comment', parent_slug: slug is defined ? slug : '' }) | raw }}\n"
        . '</body></html>'
    );

    $presentation = [
        'site_id' => 'default',
        'theme' => 'fixture',
        'content_relpath' => 'sites/default',
        'language' => 'en',
        'languages' => ['en'],
        'language_labels' => [],
        'i18n_active' => false,
        'contact_email' => 'ops@example.com',
        'comments_enabled' => true,
    ];
    $page = [
        'hero_title' => 'Guide',
        'slug' => 'guide',
        'canonical_url' => 'https://example.test/blog/post.php?slug=guide',
    ];

    $html = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        $presentation
    )->render('page', $page);

    checkFeedback(
        str_contains($html, 'data-pen-feedback')
            && str_contains($html, 'action="/api/v1/feedback"')
            && str_contains($html, "form.getAttribute('action')")
            && str_contains($html, 'name="kind" value="comment"')
            && str_contains($html, 'name="parent_slug" value="my-post"'),
        'non-global theme falls back to global feedback-form posting to this origin'
    );
    checkFeedback(
        str_contains($html, 'data-pen-site-id="default"')
            && str_contains($html, "site=' + encodeURIComponent(siteId)")
            && !str_contains($html, "credentials: 'omit'")
            && !str_contains($html, "headers['X-Pen-Site-Id']")
            && !str_contains($html, 'payload.site_id'),
        'live preview appends ?site= and does not add site_id to the POST body'
    );
    checkFeedback(
        !str_contains($html, 'feedback.pencms.org'),
        'live preview does not bake the relay origin'
    );
    checkFeedback(
        str_contains($html, 'mailto:ops@example.com'),
        'mailto uses contact_email'
    );
    checkFeedback(
        str_contains($html, 'class="pen-feedback__receipt"')
            && str_contains($html, 'Thanks for commenting.')
            && str_contains($html, 'spam stays off the page')
            && str_contains($html, 'You don')
            && str_contains($html, 'title.hidden = true')
            && !str_contains($html, 'pen-feedback__status--ok')
            && !str_contains($html, '>received<'),
        'comment success is a receipt card, not received'
    );
    checkFeedback(
        str_contains($html, '>Post comment</button>')
            && !str_contains($html, '>Send</button>'),
        'comment form submit label is Post comment'
    );
    checkFeedback(
        str_contains($html, 'background: transparent')
            && str_contains($html, 'justify-self: end')
            && str_contains($html, 'border: 1px solid currentColor')
            && !str_contains($html, 'max-width: 40rem')
            && str_contains($html, 'data-pen-feedback-rate-limited=')
            && str_contains($html, 'data-pen-feedback-send-failed='),
        'global form is outline-button, measure-agnostic, and exposes i18n error data attributes'
    );

    file_put_contents(
        $fixture . '/templates/contact.html.twig',
        '<html><body>'
        . '{{ theme.partial("feedback-form", { kind: "contact" })|raw }}'
        . '</body></html>'
    );
    $contactHtml = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        $presentation
    )->render('contact', $page);
    checkFeedback(
        str_contains($contactHtml, '>Send</button>')
            && !str_contains($contactHtml, '>Post comment</button>')
            && str_contains($contactHtml, 'name="kind" value="contact"'),
        'contact form submit label stays Send'
    );
    checkFeedback(
        str_contains($contactHtml, 'name="kind" value="contact"')
            && str_contains($contactHtml, 'class="pen-feedback__receipt"')
            && str_contains($contactHtml, 'Thanks for reaching out.')
            && str_contains($contactHtml, 'We received your message')
            && !str_contains($contactHtml, 'pen-feedback__status--ok')
            && !str_contains($contactHtml, '>received</p>')
            && !str_contains($contactHtml, 'Thanks for commenting.')
            && !str_contains($contactHtml, 'spam stays off the page'),
        'contact success is a receipt card, not received'
    );

    $postHook = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        $presentation
    )->render('post', $page);
    checkFeedback(
        str_contains($postHook, 'name="parent_slug" value="guide"')
            && str_contains($postHook, 'action="/api/v1/feedback"'),
        'post-template include expression resolves slug under strict_variables'
    );

    $submissionKey = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
    $fetchToken = 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff';
    $liveSecrets = array_merge($presentation, [
        'feedback_relay_url' => 'https://feedback.pencms.org',
        'feedback_submission_key' => $submissionKey,
        'feedback_fetch_token' => $fetchToken,
    ]);
    $liveWithKeys = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        $liveSecrets
    )->render('post', $page);
    checkFeedback(
        str_contains($liveWithKeys, 'action="/api/v1/feedback"')
            && !str_contains($liveWithKeys, 'feedback.pencms.org')
            && !str_contains($liveWithKeys, 'name="submission_key"')
            && !str_contains($liveWithKeys, $fetchToken)
            && !str_contains($liveWithKeys, $submissionKey),
        'live preview with site keys still posts same-origin and never bakes tokens'
    );

    $staticWithKey = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        true,
        '../',
        'default',
        array_merge($presentation, [
            'feedback_submission_key' => $submissionKey,
            'feedback_fetch_token' => $fetchToken,
        ])
    )->render('post', $page);
    checkFeedback(
        str_contains($staticWithKey, 'action="https://feedback.pencms.org/submit"')
            && str_contains($staticWithKey, 'name="submission_key" value="' . $submissionKey . '"')
            && str_contains($staticWithKey, "form.getAttribute('action')")
            && !str_contains($staticWithKey, $fetchToken)
            && !str_contains($staticWithKey, 'feedback_fetch_token')
            && !str_contains($staticWithKey, 'action="/api/v1/feedback"'),
        'static bake uses default relay submit URL and public key, never fetch token'
    );
    checkFeedback(
        str_contains($staticWithKey, 'data-pen-site-id="default"')
            && str_contains($staticWithKey, '!(keyField && keyField.value)')
            && !str_contains($staticWithKey, "credentials: 'omit'")
            && !str_contains($staticWithKey, 'payload.site_id')
            && !str_contains($staticWithKey, "headers['X-Pen-Site-Id']"),
        'static bake skips ?site= when submission_key is present; relay POST keys unchanged'
    );

    $staticCustomRelay = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        true,
        '../',
        'default',
        array_merge($presentation, [
            'feedback_relay_url' => 'https://relay.example.com/',
            'feedback_submission_key' => $submissionKey,
        ])
    )->render('post', $page);
    checkFeedback(
        str_contains($staticCustomRelay, 'action="https://relay.example.com/submit"')
            && !str_contains($staticCustomRelay, 'action="https://relay.example.com//submit"'),
        'static bake rstrips trailing slash before appending /submit'
    );

    $staticMailto = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        true,
        '../',
        'default',
        $presentation
    )->render('post', $page);
    checkFeedback(
        str_contains($staticMailto, 'mailto:ops@example.com')
            && !str_contains($staticMailto, 'data-pen-feedback-form')
            && !str_contains($staticMailto, 'feedback.pencms.org')
            && !str_contains($staticMailto, 'action="/api/v1/feedback"'),
        'static bake without submission key falls back to mailto and omits the POST form'
    );

    $staticHidden = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        true,
        '../',
        'default',
        array_merge($presentation, [
            'feedback_static_fallback' => 'hidden',
        ])
    )->render('post', $page);
    checkFeedback(
        !str_contains($staticHidden, 'data-pen-feedback')
            && !str_contains($staticHidden, 'mailto:ops@example.com')
            && !str_contains($staticHidden, 'feedback.pencms.org'),
        'static bake without key and hidden fallback omits the feedback section'
    );

    checkFeedback(
        SiteRegistry::resolveFeedbackSubmitEndpoint(null) === 'https://feedback.pencms.org/submit',
        'empty relay origin resolves to default /submit'
    );
    checkFeedback(
        SiteRegistry::resolveFeedbackSubmitEndpoint('https://relay.example.com/') === 'https://relay.example.com/submit',
        'resolver rstrips slash then appends /submit'
    );

    file_put_contents(
        $backend . '/data/sites.yaml',
        <<<YAML
sites:
  - id: default
    name: Default
    content_relpath: sites/default
    sitename: Bake Site
    feedback_relay_url: https://feedback.pencms.org
    feedback_submission_key: {$submissionKey}
    feedback_fetch_token: {$fetchToken}
    feedback_relay_cursor: "42"
YAML
    );
    $registryPresentation = SiteRegistry::fromConfigPath($backend . '/config.ini')
        ->resolvePresentation('default', ['theme' => ['active' => 'fixture']]);
    checkFeedback(
        ($registryPresentation['feedback_submission_key'] ?? '') === $submissionKey
            && ($registryPresentation['feedback_relay_url'] ?? '') === 'https://feedback.pencms.org'
            && !array_key_exists('feedback_fetch_token', $registryPresentation)
            && !array_key_exists('feedback_relay_cursor', $registryPresentation)
            && !str_contains(json_encode($registryPresentation), $fetchToken),
        'presentation mirrors public feedback fields and never the fetch token'
    );

    file_put_contents(
        $fixture . '/partials/_feedback-form.html.twig',
        '<div id="theme-override">local override</div>'
    );
    $overridden = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        $presentation
    )->render('page', $page);
    checkFeedback(
        str_contains($overridden, 'id="theme-override"')
            && !str_contains($overridden, 'data-pen-feedback'),
        'active-theme feedback-form partial wins over the global fallback'
    );
} finally {
    removeFeedbackTree($root);
}

/** @var string $failure */
foreach ($failures as $failure) {
    fwrite(STDERR, "[FAIL] {$failure}\n");
}
echo "Feedback form partial: {$passed} passed, {$failed} failed\n";
exit($failed > 0 ? 1 : 0);
