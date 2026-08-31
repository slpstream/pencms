<?php

declare(strict_types=1);

require_once __DIR__ . '/../src/core/PublicSiteContext.php';

use Dossier\PublicSiteContext;
use Dossier\SiteRegistry;

$passed = 0;
$failed = 0;
$failures = [];

function assert_same(mixed $expected, mixed $actual, string $label): void
{
    global $passed, $failed, $failures;
    if ($expected === $actual) {
        $passed++;
        return;
    }
    $failed++;
    $failures[] = sprintf(
        "%s\n  expected: %s\n  actual:   %s",
        $label,
        var_export($expected, true),
        var_export($actual, true)
    );
}

function remove_tree(string $path): void
{
    if (!is_dir($path)) {
        return;
    }
    foreach (scandir($path) ?: [] as $entry) {
        if ($entry === '.' || $entry === '..') {
            continue;
        }
        $child = $path . '/' . $entry;
        if (is_dir($child)) {
            remove_tree($child);
        } else {
            unlink($child);
        }
    }
    rmdir($path);
}

$root = sys_get_temp_dir() . '/pencms-i18n-' . bin2hex(random_bytes(6));
mkdir($root . '/data', 0777, true);
$configPath = $root . '/config.ini';
file_put_contents($configPath, "[theme]\nactive = starter\n");
file_put_contents(
    $root . '/data/sites.yaml',
    <<<'YAML'
sites:
  - id: default
    name: Legacy
    domain: default.test
    content_relpath: sites/default
    sitename: Legacy Site
  - id: staged
    name: Staged
    content_relpath: sites/staged
    language: en
    languages: [en]
    language_labels:
      en: English
  - id: global
    name: Global
    domain: global.test
    content_relpath: sites/global
    language: en
    languages: [en, fr]
    language_labels:
      fr: Français
    translation_automation_paused: true
  - id: relay
    name: Relay
    content_relpath: sites/relay
    sitename: Relay Site
    feedback_relay_url: https://feedback.pencms.org
    feedback_submission_key: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    feedback_fetch_token: ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
    feedback_relay_cursor: "9"
YAML
);

try {
    $registry = SiteRegistry::fromConfigPath($configPath);

    $legacy = $registry->resolveI18nConfig('default');
    assert_same('en', $legacy['language'], 'legacy default language');
    assert_same([], $legacy['languages'], 'legacy empty languages');
    assert_same([], $legacy['language_labels'], 'legacy empty labels');
    assert_same(false, $legacy['translation_automation_paused'], 'legacy automation active');
    assert_same(false, $legacy['i18n_active'], 'legacy site inactive');

    $staged = $registry->resolveI18nConfig('staged');
    assert_same(['en'], $staged['languages'], 'single language propagated');
    assert_same(false, $staged['i18n_active'], 'single language remains inactive');

    $global = $registry->resolveI18nConfig('global');
    assert_same(['en', 'fr'], $global['languages'], 'active languages propagated');
    assert_same(['fr' => 'Français'], $global['language_labels'], 'labels propagated');
    assert_same(true, $global['translation_automation_paused'], 'pause propagated');
    assert_same(true, $global['i18n_active'], 'two-language gate active');
    assert_same(true, $registry->isI18nActive('global'), 'registry gate accessor');

    $presentation = $registry->resolvePresentation('default', ['theme' => ['active' => 'starter']]);
    assert_same('Legacy Site', $presentation['sitename'], 'legacy presentation unchanged');
    assert_same('starter', $presentation['theme'], 'theme fallback unchanged');
    assert_same('sites/default', $presentation['content_relpath'], 'content path unchanged');
    assert_same(false, $presentation['i18n_active'], 'inactive gate added to presentation');

    $relayPresentation = $registry->resolvePresentation('relay', ['theme' => ['active' => 'starter']]);
    assert_same(
        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
        $relayPresentation['feedback_submission_key'],
        'presentation exposes public submission_key'
    );
    assert_same(
        'https://feedback.pencms.org',
        $relayPresentation['feedback_relay_url'],
        'presentation exposes optional relay origin without inventing a default write'
    );
    assert_same(
        false,
        array_key_exists('feedback_fetch_token', $relayPresentation),
        'presentation never includes feedback_fetch_token'
    );
    assert_same(
        false,
        array_key_exists('feedback_relay_cursor', $relayPresentation),
        'presentation never includes feedback_relay_cursor'
    );

    $_SERVER['HTTP_HOST'] = 'global.test';
    $_GET = [];
    $_COOKIE = [];
    $context = PublicSiteContext::bootstrap($configPath);
    assert_same('global', $context->siteId, 'Host routing unchanged');
    assert_same('en', $context->presentation['language'], 'context default language');
    assert_same(['en', 'fr'], $context->presentation['languages'], 'context languages');
    assert_same(true, $context->isI18nActive(), 'context active gate accessor');

    $_SERVER['HTTP_HOST'] = 'shared.test';
    $_GET = ['site' => 'default'];
    $_COOKIE = [];
    $inactiveContext = PublicSiteContext::bootstrap($configPath);
    assert_same('default', $inactiveContext->siteId, 'query site fallback unchanged');
    assert_same(false, $inactiveContext->isI18nActive(), 'legacy context inactive');
} finally {
    remove_tree($root);
}

foreach ($failures as $failure) {
    fwrite(STDERR, "[FAIL] {$failure}\n");
}
echo "SiteRegistry i18n: {$passed} passed, {$failed} failed\n";
exit($failed > 0 ? 1 : 0);
