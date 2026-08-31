<?php

declare(strict_types=1);

require_once __DIR__ . '/../vendor/autoload.php';
require_once __DIR__ . '/../src/core/ThemeEngine.php';

use Dossier\ThemeEngine;

$passed = 0;
$failed = 0;
/** @var list<string> $failures */
$failures = [];

function checkThread(bool $condition, string $label): void
{
    global $passed, $failed, $failures;
    if ($condition) {
        $passed++;
        return;
    }
    $failed++;
    $failures[] = $label;
}

function removeThreadTree(string $path): void
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
            removeThreadTree($child);
        } else {
            unlink($child);
        }
    }
    rmdir($path);
}

$root = sys_get_temp_dir() . '/pencms-comment-thread-' . getmypid();
$backend = $root . '/backend';
$themes = $backend . '/themes';
$fixture = $themes . '/fixture';
$globalPartials = $themes . '/global/partials';
$content = $root . '/content';
$realPartial = __DIR__ . '/../src/blog/themes/international/partials/_comment-thread.html.twig';

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
            'name' => 'Comment Thread Fixture',
            'version' => '1.0.0',
            'variables' => [],
        ], JSON_PRETTY_PRINT)
    );
    if (!copy($realPartial, $globalPartials . '/_comment-thread.html.twig')) {
        throw new RuntimeException('Could not copy global comment-thread partial into fixture tree');
    }
    file_put_contents(
        $fixture . '/templates/page.html.twig',
        '<html><body>'
        . '{{ theme.partial("comment-thread")|raw }}'
        . '</body></html>'
    );
    file_put_contents(
        $fixture . '/templates/post.html.twig',
        '<html><body>'
        . "{{ theme.partial('comment-thread') | raw }}\n"
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

    $empty = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        $presentation
    )->render('post', $page);
    checkThread(
        str_contains($empty, 'data-pen-comments')
            && !str_contains($empty, '<h2 class="pen-comments__title">')
            && !str_contains($empty, 'class="pen-comments__list"'),
        'empty comments list still renders the thread landmark and does not fatal'
    );

    $withComments = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        $presentation
    )->render('page', array_merge($page, [
        'comments' => [
            [
                'slug' => 'c-visible',
                'author_name' => '<script>alert(1)</script>Ada',
                'author_kind' => 'public',
                'body' => 'Nice frosting <script>alert(2)</script>',
                'in_reply_to' => null,
                'received_at' => '2026-08-20T15:20:00Z',
            ],
            [
                'slug' => 'c-reply',
                'author_name' => 'Jeanie',
                'author_kind' => 'agent',
                'body' => 'Glad you liked it.',
                'in_reply_to' => 'c-visible',
                'received_at' => '2026-08-20T16:00:00Z',
            ],
        ],
    ]));
    checkThread(
        str_contains($withComments, 'id="c-visible"')
            && str_contains($withComments, 'pen-comment--reply')
            && str_contains($withComments, 'Glad you liked it.')
            && str_contains($withComments, '&lt;script&gt;alert(1)&lt;/script&gt;Ada')
            && str_contains($withComments, 'Nice frosting &lt;script&gt;alert(2)&lt;/script&gt;')
            && !str_contains($withComments, '<script>alert(1)</script>')
            && !str_contains($withComments, '<script>alert(2)</script>'),
        'visible comments render oldest-first order with escaped author/body and reply indent'
    );

    $threadedLateReply = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        $presentation
    )->render('page', array_merge($page, [
        'comments' => [
            [
                'slug' => 'c-kiki',
                'author_name' => 'Kiki',
                'author_kind' => 'public',
                'body' => 'Does Wikipedia own WikiLeaks?',
                'in_reply_to' => null,
                'received_at' => '2026-08-20T15:00:00Z',
            ],
            [
                'slug' => 'c-bot',
                'author_name' => 'synticbot',
                'author_kind' => 'agent',
                'body' => 'No, they are different organizations.',
                'in_reply_to' => 'c-kiki',
                'received_at' => '2026-08-20T15:05:00Z',
            ],
            [
                'slug' => 'c-adamski',
                'author_name' => 'Adamski',
                'author_kind' => 'human',
                'body' => 'Well, Kiki, they are not the same.',
                'in_reply_to' => 'c-kiki',
                'received_at' => '2026-08-25T23:00:00Z',
            ],
            [
                'slug' => 'c-paul',
                'author_name' => 'Paul',
                'author_kind' => 'public',
                'body' => 'What about Norwegian Wikipedia?',
                'in_reply_to' => null,
                'received_at' => '2026-08-20T16:00:00Z',
            ],
        ],
    ]));
    $kikiPos = strpos($threadedLateReply, 'id="c-kiki"');
    $botPos = strpos($threadedLateReply, 'id="c-bot"');
    $adamskiPos = strpos($threadedLateReply, 'id="c-adamski"');
    $paulPos = strpos($threadedLateReply, 'id="c-paul"');
    checkThread(
        $kikiPos !== false
            && $botPos !== false
            && $adamskiPos !== false
            && $paulPos !== false
            && $kikiPos < $botPos
            && $botPos < $adamskiPos
            && $adamskiPos < $paulPos
            && substr_count($threadedLateReply, 'class="pen-comment pen-comment--reply"') === 2,
        'threaded late reply renders after its parent and before the next top-level comment'
    );

    $markdownComments = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        $presentation
    )->render('page', array_merge($page, [
        'comments' => [
            [
                'slug' => 'c-agent-md',
                'author_name' => 'synticbot',
                'author_kind' => 'agent',
                'body' => "Norway is a great example: **Norwegian Bokmål (no.wikipedia.org)**.\n\nSee [Wikipedia](https://example.com/wiki) too.",
                'in_reply_to' => null,
                'received_at' => '2026-08-24T01:12:41Z',
            ],
            [
                'slug' => 'c-reader-link',
                'author_name' => 'Paul',
                'author_kind' => 'public',
                'body' => "I found this: https://example.com/article\n\n![x](https://evil.example/x.png)",
                'in_reply_to' => null,
                'received_at' => '2026-08-24T01:12:20Z',
            ],
        ],
    ]));
    checkThread(
        str_contains($markdownComments, '<strong>Norwegian Bokmål (no.wikipedia.org)</strong>')
            && str_contains($markdownComments, 'href="https://example.com/wiki"')
            && str_contains($markdownComments, 'rel="nofollow noopener"')
            && str_contains($markdownComments, 'target="_blank"')
            && str_contains($markdownComments, '>Wikipedia</a>'),
        'agent markdown renders strong and safe external links'
    );
    checkThread(
        str_contains($markdownComments, 'href="https://example.com/article"')
            && !str_contains($markdownComments, '<img')
            && str_contains($markdownComments, 'class="pen-comment__body"'),
        'public comments autolink URLs and drop image tags'
    );

    checkThread(
        str_contains($withComments, '<h2 class="pen-comments__title">Comments</h2>')
            && !str_contains($withComments, 'max-width: 40rem'),
        'visible thread uses the engine Comments label and no 40rem measure'
    );

    file_put_contents($fixture . '/strings.json', json_encode(['comments' => 'Anmerkungen']));
    $i18nComments = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        array_merge($presentation, [
            'i18n_active' => true,
            'languages' => ['en'],
            'language' => 'en',
        ])
    )->render('page', array_merge($page, [
        'comments' => [
            [
                'slug' => 'c-i18n',
                'author_name' => 'Ada',
                'author_kind' => 'public',
                'body' => 'Hello.',
                'in_reply_to' => null,
                'received_at' => '2026-08-20T15:20:00Z',
            ],
        ],
    ]));
    checkThread(
        str_contains($i18nComments, '<h2 class="pen-comments__title">Anmerkungen</h2>')
            && !str_contains($i18nComments, '<h2 class="pen-comments__title">Comments</h2>'),
        'theme strings.comments overrides the thread heading when i18n is active'
    );

    file_put_contents(
        $fixture . '/partials/_comment-thread.html.twig',
        '<div id="theme-override-thread">local override</div>'
    );
    $overridden = ThemeEngine::fromConfig(
        $backend . '/config.ini',
        false,
        '',
        'default',
        $presentation
    )->render('page', $page);
    checkThread(
        str_contains($overridden, 'id="theme-override-thread"')
            && !str_contains($overridden, 'data-pen-comments'),
        'active-theme comment-thread partial wins over the global fallback'
    );
} finally {
    removeThreadTree($root);
}

/** @var string $failure */
foreach ($failures as $failure) {
    fwrite(STDERR, "[FAIL] {$failure}\n");
}
echo "Comment thread partial: {$passed} passed, {$failed} failed\n";
exit($failed > 0 ? 1 : 0);
