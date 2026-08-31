<?php

declare(strict_types=1);

/**
 * Smoke: Comments admin is a dedicated page, not the fb-* inbox.
 *
 * Run: php frontend-php/cli-tools/test-admin-comments-page.php
 */

$passed = 0;
$failed = 0;
/** @var list<string> $failures */
$failures = [];

function checkCommentsAdmin(bool $condition, string $label): void
{
    global $passed, $failed, $failures;
    if ($condition) {
        $passed++;
        return;
    }
    $failed++;
    $failures[] = $label;
}

$root = dirname(__DIR__);
$page = $root . '/src/admin/admin-comments.php';
$js = $root . '/src/admin/js/comments.js';
$api = $root . '/src/admin/js/api.js';
$feedbackPage = $root . '/src/admin/admin-feedback.php';
$feedbackJs = $root . '/src/admin/js/feedback.js';
$sidebar = $root . '/src/admin/includes/_admin-sidebar.php';
$editor = $root . '/src/admin/admin-editor.php';

checkCommentsAdmin(is_file($page), 'admin-comments.php exists');
checkCommentsAdmin(is_file($js), 'comments.js exists');

$pageSrc = is_file($page) ? (string) file_get_contents($page) : '';
$jsSrc = is_file($js) ? (string) file_get_contents($js) : '';
$apiSrc = is_file($api) ? (string) file_get_contents($api) : '';
$feedbackPageSrc = is_file($feedbackPage) ? (string) file_get_contents($feedbackPage) : '';
$feedbackJsSrc = is_file($feedbackJs) ? (string) file_get_contents($feedbackJs) : '';
$sidebarSrc = is_file($sidebar) ? (string) file_get_contents($sidebar) : '';
$editorSrc = is_file($editor) ? (string) file_get_contents($editor) : '';

checkCommentsAdmin(
    str_contains($pageSrc, 'x-data="commentsAdmin"'),
    'admin-comments.php uses commentsAdmin Alpine data'
);
checkCommentsAdmin(
    str_contains($pageSrc, 'New reader comments, grouped by post'),
    'admin-comments.php copy mentions reader comments grouped by post'
);
checkCommentsAdmin(
    !str_contains($pageSrc, 'getPage(') && !str_contains($jsSrc, 'getPage('),
    'Comments admin does not call getPage'
);
checkCommentsAdmin(
    !str_contains($jsSrc, 'deletePage('),
    'comments.js does not call deletePage'
);
checkCommentsAdmin(
    str_contains($jsSrc, 'listAdminComments')
    && str_contains($jsSrc, 'setCommentVisibility')
    && str_contains($jsSrc, 'deleteComment')
    && str_contains($jsSrc, 'createAdminComment')
    && str_contains($jsSrc, 'patchComment'),
    'comments.js uses admin comment API methods'
);
checkCommentsAdmin(
    str_contains($apiSrc, "startsWith('/admin/')")
    && str_contains($apiSrc, 'listAdminComments')
    && str_contains($apiSrc, 'setCommentVisibility')
    && str_contains($apiSrc, 'deleteComment')
    && str_contains($apiSrc, 'createAdminComment')
    && str_contains($apiSrc, 'patchComment'),
    'api.js routes /admin/ to v1 and exposes comment methods'
);
checkCommentsAdmin(
    str_contains($feedbackJsSrc, 'startsWith("fb-")'),
    'feedback.js isInboxItem still requires fb- prefix'
);
checkCommentsAdmin(
    str_contains($feedbackPageSrc, 'fb-*')
    && str_contains($feedbackPageSrc, 'x-data="feedbackInbox"'),
    'admin-feedback.php remains the fb-* contact inbox'
);
checkCommentsAdmin(
    str_contains($sidebarSrc, 'admin-comments.php')
    && str_contains($sidebarSrc, "currentSection ?? '') === 'comments'"),
    'sidebar has a Comments link distinct from Feedback'
);
checkCommentsAdmin(
    str_contains($pageSrc, 'All posts'),
    'admin-comments.php defaults the post filter to All posts'
);
checkCommentsAdmin(
    !str_contains($pageSrc, 'Select a post to moderate'),
    'admin-comments.php no longer requires selecting a post first'
);
checkCommentsAdmin(
    str_contains($pageSrc, 'No new comments.'),
    'admin-comments.php empty pending copy does not require a post'
);
checkCommentsAdmin(
    str_contains($pageSrc, 'Approve and reply')
    && str_contains($jsSrc, 'submitReply')
    && str_contains($jsSrc, 'submitEdit'),
    'comments admin offers approve-and-reply and edit'
);
checkCommentsAdmin(
    !str_contains($editorSrc, 'commentsAdmin')
    && !str_contains($editorSrc, 'listAdminComments'),
    'admin-editor.php was not given a comments panel'
);

echo "Admin comments page smoke: {$passed} passed, {$failed} failed\n";
if ($failures) {
    foreach ($failures as $label) {
        echo "  FAIL: {$label}\n";
    }
    exit(1);
}
exit(0);
