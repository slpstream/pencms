<?php
/**
 * Editor skin picker helpers (pure).
 *
 * Invariant: a site-custom theme must never register under an install theme's
 * editor_skin stem (e.g. both "marut"). Custom always uses picker key "custom".
 * See KB sticky A9b / cli-tools/test-editor-skin-resolve.php.
 */

declare(strict_types=1);

/**
 * Build site-custom picker entry/entries without shadowing install theme keys.
 *
 * @param array{editorSkin?: string, name?: string} $customMeta
 * @param list<string> $customHrefs
 * @param array<string, true> $seenKeys
 * @return list<array{key: string, label: string, hrefs: list<string>, source: string, themeId: string}>
 */
function pen_editor_skin_site_custom_entries(
    array $customMeta,
    array $customHrefs,
    string $themeId,
    string $bootKey,
    array $bootHrefs,
    bool $bootFromActiveTheme,
    string $bootLabel,
    array &$seenKeys
): array {
    if ($customHrefs === []) {
        return [];
    }

    $entries = [];
    $key = 'custom';
    $isActive = ($themeId === 'custom');
    $baseName = isset($customMeta['name']) && is_string($customMeta['name']) && $customMeta['name'] !== ''
        ? $customMeta['name']
        : 'Custom';
    $label = $isActive
        ? ($baseName . (str_contains($baseName, '(active)') ? '' : ' (active)'))
        : (str_contains(strtolower($baseName), 'custom') ? $baseName : ($baseName . ' (custom)'));
    $entryHrefs = $customHrefs;
    if ($isActive && $bootFromActiveTheme) {
        $entryHrefs = $bootHrefs;
        $label = $bootLabel;
    }

    if (!isset($seenKeys[$key])) {
        $entries[] = [
            'key' => $key,
            'label' => $label,
            'hrefs' => $entryHrefs,
            'source' => 'site-custom',
            'themeId' => 'custom',
        ];
        $seenKeys[$key] = true;
    }

    // When custom is the active site theme, also expose boot.skinKey (often the
    // parent editor_skin stem) so applySkin(boot.skinKey) resolves to custom hrefs
    // without falling through to the install theme of the same stem.
    if ($isActive && $bootKey !== '' && $bootKey !== $key && !isset($seenKeys[$bootKey])) {
        $entries[] = [
            'key' => $bootKey,
            'label' => $bootLabel,
            'hrefs' => $bootHrefs,
            'source' => 'site-custom',
            'themeId' => 'custom',
        ];
        $seenKeys[$bootKey] = true;
    }

    return $entries;
}

/**
 * Resolve which stylesheet hrefs applySkin should load for a picked skin key.
 * Active boot skin always prefers boot.hrefs (never a shadowed map entry).
 *
 * @param array{skinKey?: string, hrefs?: list<string>}|array $boot
 * @param array<string, array{hrefs?: list<string>}> $skinsMap
 * @return list<string>
 */
function pen_editor_skin_resolve_apply_hrefs(string $skin, array $boot, array $skinsMap): array
{
    $bootSkinKey = isset($boot['skinKey']) && is_string($boot['skinKey']) && $boot['skinKey'] !== ''
        ? $boot['skinKey']
        : 'starter';
    $bootHrefs = isset($boot['hrefs']) && is_array($boot['hrefs']) ? $boot['hrefs'] : [];

    if ($skin === $bootSkinKey && $bootHrefs !== []) {
        return array_values(array_filter($bootHrefs, static fn($h) => is_string($h) && $h !== ''));
    }
    if (isset($skinsMap[$skin]['hrefs']) && is_array($skinsMap[$skin]['hrefs'])) {
        return array_values(array_filter(
            $skinsMap[$skin]['hrefs'],
            static fn($h) => is_string($h) && $h !== ''
        ));
    }
    if ($skin === ($boot['skinKey'] ?? null) && $bootHrefs !== []) {
        return array_values(array_filter($bootHrefs, static fn($h) => is_string($h) && $h !== ''));
    }
    if (isset($skinsMap[$bootSkinKey]['hrefs']) && is_array($skinsMap[$bootSkinKey]['hrefs'])) {
        return array_values(array_filter(
            $skinsMap[$bootSkinKey]['hrefs'],
            static fn($h) => is_string($h) && $h !== ''
        ));
    }
    return array_values(array_filter($bootHrefs, static fn($h) => is_string($h) && $h !== ''));
}
