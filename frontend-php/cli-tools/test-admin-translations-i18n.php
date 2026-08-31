<?php

declare(strict_types=1);

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

function contains(string $haystack, string $needle, string $label): void
{
    check(str_contains($haystack, $needle), $label);
}

$admin = file_get_contents(__DIR__ . '/../src/admin/admin-translations.php');
$editor = file_get_contents(__DIR__ . '/../src/admin/admin-editor.php');
$controller = file_get_contents(__DIR__ . '/../src/admin/js/translations.js');
$wizard = file_get_contents(__DIR__ . '/../src/admin/js/wizard4.js');

check(is_string($admin), 'translations admin template readable');
check(is_string($editor), 'editor template readable');
check(is_string($controller), 'translations controller readable');
check(is_string($wizard), 'editor controller readable');

contains($admin, '$pageScript = "translations.js"', 'translations controller loaded');
contains($admin, 'x-data="translationsPage"', 'translations Alpine workspace wired');
contains($admin, "setTab('languages')", 'Languages tab wired');
contains($admin, "setTab('coverage')", 'Coverage tab wired');
contains($admin, "setTab('strings')", 'UI Strings tab wired');
contains($admin, 'saveLanguages()', 'language configuration save present');
contains($admin, 'setAutomationPaused(', 'agent pause control present');
contains($admin, 'External localization policy', 'optional external policy controls present');
contains($admin, 'allow_unreviewed_draft', 'explicit draft review policy present');
contains($admin, 'row.agent_key_id', 'immutable named-key binding control present');
contains($admin, 'external caller owns model execution and scheduling', 'no internal orchestration promise');
contains($admin, 'filteredCoverageItems', 'exact coverage table present');
contains($admin, 'createOrOpenSibling(row)', 'manual sibling entry present');
contains($admin, "review(row, 'approve')", 'approve override present');
contains($admin, "review(row, 'reject')", 'reject override present');
contains($admin, 'forceRepublish()', 'force full publish override present');
contains($admin, 'stringRows', 'UI string matrix present');
contains($admin, 'resetString(row)', 'sparse fallback reset present');
check(!str_contains($admin, 'Coming Soon'), 'all three placeholders removed');

contains($editor, 'Language siblings', 'editor sibling state bar present');
contains($editor, 'openOrCreateSibling(state)', 'editor create/open sibling action present');
contains($editor, ':disabled="isTranslation"', 'translation identity controls locked');
contains($editor, 'Locked group', 'translation group identity shown');
contains($wizard, "urlParams.get('lang')", 'exact lang query parsed');
contains($wizard, 'window.api.getPage(', 'exact editor load uses API wrapper');
contains($wizard, 'this.currentLanguage', 'exact editor language retained');
contains($wizard, 'enforceTranslationIdentity(metadata)', 'structural identity restored before save');
contains($wizard, "'translation_group'", 'server-owned group omitted from writes');
contains($wizard, 'createTranslationSibling(', 'manual empty sibling uses Slice 6 endpoint');

check(!str_contains($admin, 'language-switcher'), 'Slice 8 switcher not added');
contains($admin, 'translate_then_transliterate', 'ordered localization operation policy added');
contains($controller, 'automationPolicyPayload()', 'policy payload is serialized explicitly');
contains($controller, 'getAgentKeys()', 'sanitized named keys are loaded');
check(!str_contains($controller, 'hreflang'), 'no SEO alternate behavior added');

printf(
    "Admin translations PHP: %d passed, %d failed\n",
    $passed,
    $failed
);
if ($failures !== []) {
    foreach ($failures as $failure) {
        fwrite(STDERR, "FAIL: {$failure}\n");
    }
    exit(1);
}
