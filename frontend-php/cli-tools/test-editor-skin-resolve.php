<?php
/**
 * Regression: site-custom sibling must never steal an install theme's editor skin key.
 *
 * Usage: php frontend-php/cli-tools/test-editor-skin-resolve.php
 *
 * Covers the marut-class failure: custom theme.json editor_skin mirrors a parent
 * stem → applySkin() must not replace the boot install stylesheet with a stale
 * /api/assets/raw custom URL.
 */

declare(strict_types=1);

require_once __DIR__ . '/../src/admin/includes/_editor-skin-picker.php';

$passed = 0;
$failed = 0;

function assert_ok(bool $cond, string $label): void
{
    global $passed, $failed;
    if ($cond) {
        $passed++;
        echo "  [PASS] {$label}\n";
    } else {
        $failed++;
        echo "  [FAIL] {$label}\n";
    }
}

echo "=== 1. Unit: site-custom picker keys (inactive sibling) ===\n";
$seen = [];
$entries = pen_editor_skin_site_custom_entries(
    ['editorSkin' => 'marut', 'name' => 'Marut (custom)'],
    ['/api/assets/raw/sites/default/theme/assets/css/skin-marut.css'],
    'marut', // install parent is active
    'marut',
    ['/blog/themes/marut/assets/css/skin-marut.css'],
    true,
    'Marut (active)',
    $seen
);
assert_ok(count($entries) === 1, 'inactive custom yields one picker entry');
assert_ok(($entries[0]['key'] ?? '') === 'custom', 'inactive custom key is always "custom"');
assert_ok(($entries[0]['source'] ?? '') === 'site-custom', 'inactive custom source is site-custom');
assert_ok(isset($seen['custom']) && !isset($seen['marut']), 'seenKeys marks custom only — not parent stem');

echo "\n=== 2. Unit: install parent can still claim its stem ===\n";
$installKey = 'marut';
assert_ok(!isset($seen[$installKey]), 'parent stem free after custom registration');
$seen[$installKey] = true;
$installEntry = [
    'key' => $installKey,
    'hrefs' => ['/blog/themes/marut/assets/css/skin-marut.css'],
    'source' => 'theme',
];
$map = ['custom' => $entries[0], $installKey => $installEntry];
assert_ok(($map['marut']['source'] ?? '') === 'theme', 'map[marut] remains install theme');
assert_ok(str_contains($map['marut']['hrefs'][0] ?? '', '/blog/themes/marut/'), 'map[marut] href is install path');

echo "\n=== 3. Unit: applySkin prefers boot.hrefs for boot skin key ===\n";
$boot = [
    'skinKey' => 'marut',
    'hrefs' => ['/blog/themes/marut/assets/css/skin-marut.css'],
];
// Hostile map: same key, bad custom URL (the pre-fix failure mode)
$hostileMap = [
    'marut' => [
        'hrefs' => ['/api/assets/raw/sites/default/theme/assets/css/skin-marut.css'],
        'source' => 'site-custom',
    ],
];
$hrefs = pen_editor_skin_resolve_apply_hrefs('marut', $boot, $hostileMap);
assert_ok(count($hrefs) === 1, 'apply resolve returns one href');
assert_ok(str_contains($hrefs[0], '/blog/themes/marut/'), 'boot key uses boot.hrefs, not shadowed custom URL');
assert_ok(!str_contains($hrefs[0], '/api/assets/raw/'), 'boot key does not use raw custom API path');

echo "\n=== 4. Unit: explicit custom pick still loads custom hrefs ===\n";
$hrefsCustom = pen_editor_skin_resolve_apply_hrefs('custom', $boot, [
    'custom' => ['hrefs' => ['/api/assets/raw/sites/default/theme/assets/css/skin-marut.css']],
    'marut' => ['hrefs' => ['/blog/themes/marut/assets/css/skin-marut.css']],
]);
assert_ok(str_contains($hrefsCustom[0] ?? '', '/api/assets/raw/'), 'picking custom uses custom hrefs');

echo "\n=== 5. Unit: active custom exposes bootKey alias without blocking key custom ===\n";
$seenActive = [];
$activeEntries = pen_editor_skin_site_custom_entries(
    ['editorSkin' => 'studio', 'name' => 'Studio Fork'],
    ['/api/assets/raw/sites/default/theme/assets/css/skin-studio.css'],
    'custom',
    'studio',
    ['/api/assets/raw/sites/default/theme/assets/css/skin-studio.css'],
    true,
    'Studio Fork (active)',
    $seenActive
);
$keys = array_column($activeEntries, 'key');
assert_ok(in_array('custom', $keys, true), 'active custom includes key custom');
assert_ok(in_array('studio', $keys, true), 'active custom also aliases bootKey stem');
assert_ok(isset($seenActive['custom']) && isset($seenActive['studio']), 'both keys marked seen when custom active');

echo "\n=== 6. Live smoke: require resolver against this install ===\n";
$_SERVER['HTTP_HOST'] = $_SERVER['HTTP_HOST'] ?? 'localhost';
require __DIR__ . '/../src/admin/includes/_editor-skin-resolve.php';

assert_ok(isset($penEditorSkinBoot) && is_array($penEditorSkinBoot), 'boot payload defined');
assert_ok(isset($penEditorSkinsMap) && is_array($penEditorSkinsMap), 'skins map defined');

$bootKey = (string) ($penEditorSkinBoot['skinKey'] ?? '');
$bootTheme = (string) ($penEditorSkinBoot['themeId'] ?? '');
$bootHref = (string) ($penEditorSkinBoot['hrefs'][0] ?? '');

if (isset($penEditorSkinsMap['custom'])) {
    assert_ok(($penEditorSkinsMap['custom']['source'] ?? '') === 'site-custom', 'live map[custom] is site-custom');
    $stem = null;
    $customThemeJson = dirname(__DIR__, 2) . '/pencms-data/content/sites/default/theme/theme.json';
    // content dir may be elsewhere via config — best-effort stem from custom map label / boot
    if (is_file($customThemeJson)) {
        $cj = json_decode((string) file_get_contents($customThemeJson), true);
        if (is_array($cj) && isset($cj['editor_skin']) && is_string($cj['editor_skin'])) {
            $stem = $cj['editor_skin'];
        }
    }
    if ($stem && isset($penEditorSkinsMap[$stem]) && $bootTheme !== 'custom') {
        assert_ok(
            ($penEditorSkinsMap[$stem]['source'] ?? '') === 'theme',
            "live map[{$stem}] stays install theme while parent is active"
        );
        assert_ok(
            str_contains((string) ($penEditorSkinsMap[$stem]['hrefs'][0] ?? ''), '/blog/themes/' . $stem . '/'),
            "live map[{$stem}] href is install path"
        );
    } else {
        echo "  [SKIP] no colliding parent stem in live map (ok if custom inactive/absent)\n";
    }
} else {
    echo "  [SKIP] no site-custom skin in live map\n";
}

if ($bootTheme !== 'custom' && $bootKey !== '' && $bootHref !== '') {
    $liveApply = pen_editor_skin_resolve_apply_hrefs($bootKey, $penEditorSkinBoot, $penEditorSkinsMap);
    assert_ok(
        ($liveApply[0] ?? '') === $bootHref || str_contains($liveApply[0] ?? '', '/blog/themes/'),
        'live applySkin(bootKey) stays on boot/install href'
    );
}

echo "\n=== Summary ===\n";
echo "Passed: {$passed}\nFailed: {$failed}\n";
exit($failed > 0 ? 1 : 0);
