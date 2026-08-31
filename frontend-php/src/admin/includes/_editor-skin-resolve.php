<?php
/**
 * Resolve Traven editor content skins from installed site themes
 * (and this site's custom theme tree when presentation theme is ``custom``).
 *
 * Theme-owned assets/css/skin-*.css are the source of truth.
 * Missing active-theme stacks fall back to themes/starter only.
 * When theme is ``custom``, skins load via /api/assets/raw/sites/{id}/theme/assets/…
 *
 * Sets:
 *   $penEditorSkinBoot  — default skin for this page load
 *   $penEditorSkinsList — picker entries [{key,label,hrefs,source}, ...]
 *   $penEditorSkinsMap  — key => entry (for JS lookup)
 *   $penEditorImageAspect — theme.json editor_image_aspect for Traven image modal (list or [])
 */

declare(strict_types=1);

$configPath = dirname(__DIR__, 4) . '/backend-python/config.ini';
if (!file_exists($configPath)) {
    $alt = dirname(__DIR__, 3) . '/../../backend-python/config.ini';
    if (file_exists($alt)) {
        $configPath = $alt;
    }
}

$ini = file_exists($configPath) ? (parse_ini_file($configPath, true) ?: []) : [];
$themesDir = $ini['theme']['directory'] ?? '../frontend-php/src/blog/themes';
$themesRoot = dirname($configPath) . '/' . $themesDir;
if (!is_dir($themesRoot)) {
    $themesRoot = dirname(__DIR__, 2) . '/blog/themes';
}

$webRoot = rtrim((string) ($ini['theme']['web_root'] ?? '/blog'), '/') . '/';

$contentDirRel = $ini['Paths']['content_dir'] ?? '../pencms-data/content';
$contentDirAbs = $contentDirRel;
if (strpos($contentDirRel, '/') !== 0) {
    $contentDirAbs = dirname($configPath) . '/' . $contentDirRel;
}
$contentDirAbs = rtrim($contentDirAbs, '/');

require_once dirname(__DIR__, 2) . '/core/SiteRegistry.php';

$themeId = (string) ($ini['theme']['active'] ?? 'starter');
$siteId = \Dossier\SiteRegistry::DEFAULT_SITE_ID;
$contentRelpath = 'sites/' . $siteId;
$registry = null;

if (file_exists($configPath)) {
    try {
        $registry = \Dossier\SiteRegistry::fromConfigPath($configPath);
        $siteId = $registry->resolveSiteIdFromRequest();
        $presentation = $registry->resolvePresentation($siteId, $ini);
        if (!empty($presentation['theme'])) {
            $themeId = (string) $presentation['theme'];
        }
        if (!empty($presentation['content_relpath'])) {
            $contentRelpath = rtrim((string) $presentation['content_relpath'], '/');
        } else {
            $contentRelpath = $registry->contentRelpath($siteId);
        }
    } catch (\Throwable $e) {
        // Keep install theme fallback
    }
}

$siteCustomThemeRoot = $contentDirAbs . '/' . $contentRelpath . '/theme';

/**
 * @param mixed $base
 * @return list<string>
 */
$normalizeSkinBase = static function ($base): array {
    if ($base === null || $base === '' || $base === []) {
        return [];
    }
    if (is_string($base)) {
        $stem = trim($base);
        return $stem !== '' ? [$stem] : [];
    }
    if (!is_array($base)) {
        return [];
    }
    $out = [];
    foreach ($base as $item) {
        if (!is_string($item)) {
            continue;
        }
        $stem = trim($item);
        if ($stem !== '') {
            $out[] = $stem;
        }
    }
    return $out;
};

/**
 * @return list<string>
 */
$themeSkinHrefs = static function (
    string $themesRoot,
    string $themeId,
    string $webRoot,
    array $stems
): array {
    $hrefs = [];
    foreach ($stems as $stem) {
        $rel = 'css/skin-' . $stem . '.css';
        $abs = rtrim($themesRoot, '/') . '/' . $themeId . '/assets/' . $rel;
        if (!is_file($abs)) {
            return [];
        }
        $hrefs[] = $webRoot . 'themes/' . rawurlencode($themeId) . '/assets/' . $rel;
    }
    return $hrefs;
};

/**
 * Site-custom theme skins via the assets raw proxy.
 *
 * @return list<string>
 */
$siteCustomSkinHrefs = static function (
    string $siteThemeRoot,
    string $siteId,
    array $stems
): array {
    $hrefs = [];
    $prefix = '/api/assets/raw/sites/' . rawurlencode($siteId) . '/theme/assets/';
    foreach ($stems as $stem) {
        $rel = 'css/skin-' . $stem . '.css';
        $abs = rtrim($siteThemeRoot, '/') . '/assets/' . $rel;
        if (!is_file($abs)) {
            return [];
        }
        $hrefs[] = $prefix . $rel;
    }
    return $hrefs;
};

$skinLabel = static function (string $key, string $suffix = ''): string {
    $display = ucwords(str_replace('-', ' ', $key));
    return $suffix !== '' ? $display . $suffix : $display;
};

/**
 * Read skin meta from an absolute theme directory (install or site custom).
 *
 * @return array{manifest: array, editorSkin: string, stackStems: list<string>, name: string}|null
 */
$readThemeSkinMetaAt = static function (
    string $themeDirAbs,
    string $fallbackId,
    callable $normalizeSkinBase
): ?array {
    $manifestPath = rtrim($themeDirAbs, '/') . '/theme.json';
    if (!is_file($manifestPath)) {
        return null;
    }
    $decoded = json_decode((string) file_get_contents($manifestPath), true);
    if (!is_array($decoded)) {
        return null;
    }
    $editorSkin = isset($decoded['editor_skin']) && is_string($decoded['editor_skin'])
        ? trim($decoded['editor_skin'])
        : '';
    if ($editorSkin === '') {
        $editorSkin = $fallbackId;
    }
    $baseStems = $normalizeSkinBase($decoded['editor_skin_base'] ?? null);
    $stackStems = array_values(array_unique(array_merge($baseStems, [$editorSkin])));
    $name = isset($decoded['name']) && is_string($decoded['name']) && $decoded['name'] !== ''
        ? $decoded['name']
        : ucwords(str_replace('-', ' ', $fallbackId));

    return [
        'manifest' => $decoded,
        'editorSkin' => $editorSkin,
        'stackStems' => $stackStems,
        'name' => $name,
    ];
};

/**
 * @return array{manifest: array, editorSkin: string, stackStems: list<string>, name: string}|null
 */
$readThemeSkinMeta = static function (
    string $themesRoot,
    string $id,
    callable $normalizeSkinBase
) use ($readThemeSkinMetaAt): ?array {
    return $readThemeSkinMetaAt(
        rtrim($themesRoot, '/') . '/' . $id,
        $id,
        $normalizeSkinBase
    );
};

/**
 * Normalize theme.json editor_image_aspect for the Traven image modal.
 *
 * @param mixed $raw
 * @return list<array{value: string, label: string}>
 */
$normalizeEditorImageAspect = static function ($raw): array {
    if (!is_array($raw) || $raw === []) {
        return [];
    }
    $out = [];
    foreach ($raw as $item) {
        if (!is_array($item)) {
            continue;
        }
        if (!array_key_exists('value', $item) || !array_key_exists('label', $item)) {
            continue;
        }
        if (!is_string($item['value']) || !is_string($item['label'])) {
            continue;
        }
        $label = trim($item['label']);
        if ($label === '') {
            continue;
        }
        $out[] = [
            'value' => $item['value'],
            'label' => $label,
        ];
    }
    return $out;
};

// ── Active theme skin (boot default) ──
$bootSource = 'theme';
$bootHrefs = [];
$bootKey = $themeId;
$bootFromActiveTheme = false;
$themeName = ucwords(str_replace('-', ' ', $themeId));
$editorSkin = $themeId;
$stackStems = [$themeId];
$customMeta = null;
$customHrefs = [];
$activeThemeManifest = null;

if ($themeId === 'custom') {
    $customMeta = $readThemeSkinMetaAt($siteCustomThemeRoot, 'custom', $normalizeSkinBase);
    if ($customMeta !== null) {
        $activeThemeManifest = $customMeta['manifest'] ?? null;
        $editorSkin = $customMeta['editorSkin'];
        $stackStems = $customMeta['stackStems'];
        $themeName = $customMeta['name'];
        $customHrefs = $siteCustomSkinHrefs($siteCustomThemeRoot, $siteId, $stackStems);
        if ($customHrefs !== []) {
            $bootHrefs = $customHrefs;
            $bootKey = $editorSkin;
            $bootFromActiveTheme = true;
            $bootSource = 'site-custom';
        }
    }
} else {
    $activeMeta = $readThemeSkinMeta($themesRoot, $themeId, $normalizeSkinBase);
    $activeThemeManifest = is_array($activeMeta) ? ($activeMeta['manifest'] ?? null) : null;
    $editorSkin = $activeMeta['editorSkin'] ?? $themeId;
    $stackStems = $activeMeta['stackStems'] ?? [$themeId];
    $themeName = $activeMeta['name'] ?? $themeName;
    $themeHrefs = $themeSkinHrefs($themesRoot, $themeId, $webRoot, $stackStems);
    $bootHrefs = $themeHrefs;
    $bootKey = $editorSkin;
    $bootFromActiveTheme = ($themeHrefs !== []);
}

if ($bootHrefs === []) {
    // Theme has no usable stack — fall back to starter theme assets
    $bootKey = 'starter';
    $starterThemeHrefs = $themeSkinHrefs($themesRoot, 'starter', $webRoot, ['starter']);
    if ($starterThemeHrefs !== []) {
        $bootHrefs = $starterThemeHrefs;
        $bootSource = 'theme';
    } else {
        $bootHrefs = [];
        $bootSource = 'none';
    }
}

if ($bootFromActiveTheme) {
    $bootLabel = $themeName . ' (active)';
} else {
    $bootLabel = $skinLabel($bootKey, ' (fallback)');
}

$penEditorSkinBoot = [
    'themeId' => $themeId,
    'siteId' => $siteId,
    'skinKey' => $bootKey,
    'label' => $bootLabel,
    'hrefs' => $bootHrefs,
    'source' => $bootSource,
];

// Theme-declared Aspect pills for Traven Edit/Insert Image (opt-in; empty = no UI).
$penEditorImageAspect = $normalizeEditorImageAspect(
    is_array($activeThemeManifest) ? ($activeThemeManifest['editor_image_aspect'] ?? null) : null
);

// ── Picker list: install themes + this site's custom (never install folder named custom) ──
$penEditorSkinsList = [];
$seenKeys = [];
$otherEntries = [];

// Prefer site custom entry first when active / present
require_once __DIR__ . '/_editor-skin-picker.php';
if (is_dir($siteCustomThemeRoot) && is_file($siteCustomThemeRoot . '/theme.json')) {
    if ($customMeta === null) {
        $customMeta = $readThemeSkinMetaAt($siteCustomThemeRoot, 'custom', $normalizeSkinBase);
    }
    if ($customMeta !== null) {
        if ($customHrefs === []) {
            $customHrefs = $siteCustomSkinHrefs(
                $siteCustomThemeRoot,
                $siteId,
                $customMeta['stackStems']
            );
        }
        $customEntries = pen_editor_skin_site_custom_entries(
            $customMeta,
            $customHrefs,
            $themeId,
            $bootKey,
            $bootHrefs,
            $bootFromActiveTheme,
            $bootLabel,
            $seenKeys
        );
        $isActiveCustom = ($themeId === 'custom');
        foreach ($customEntries as $entry) {
            if ($isActiveCustom) {
                array_unshift($penEditorSkinsList, $entry);
            } else {
                $otherEntries[] = $entry;
            }
        }
    }
}

if (is_dir($themesRoot)) {
    $dirs = scandir($themesRoot) ?: [];
    foreach ($dirs as $dir) {
        if ($dir === '.' || $dir === '..' || str_starts_with($dir, '_') || $dir === 'custom') {
            continue;
        }
        $themePath = rtrim($themesRoot, '/') . '/' . $dir;
        if (!is_dir($themePath)) {
            continue;
        }

        $meta = $readThemeSkinMeta($themesRoot, $dir, $normalizeSkinBase);
        if ($meta === null) {
            continue;
        }

        $hrefs = $themeSkinHrefs($themesRoot, $dir, $webRoot, $meta['stackStems']);
        if ($hrefs === []) {
            continue;
        }

        $key = $meta['editorSkin'];
        if ($key === '' || isset($seenKeys[$key])) {
            continue;
        }

        $isActive = ($dir === $themeId);
        $label = $isActive ? ($meta['name'] . ' (active)') : $meta['name'];
        $entry = [
            'key' => $key,
            'label' => $label,
            'hrefs' => $hrefs,
            'source' => 'theme',
            'themeId' => $dir,
        ];

        $seenKeys[$key] = true;
        if ($isActive) {
            // Prefer boot hrefs when active theme resolved via theme assets
            if ($bootFromActiveTheme && $bootKey === $key) {
                $entry['hrefs'] = $bootHrefs;
                $entry['label'] = $bootLabel;
            }
            array_unshift($penEditorSkinsList, $entry);
        } else {
            $otherEntries[] = $entry;
        }
    }
}

// If active theme had no SoT files but boot still resolved (starter fallback),
// ensure the boot key appears first in the picker.
if ($bootKey !== '' && !isset($seenKeys[$bootKey]) && ($bootHrefs !== [] || $bootFromActiveTheme)) {
    array_unshift($penEditorSkinsList, [
        'key' => $bootKey,
        'label' => $bootLabel,
        'hrefs' => $bootHrefs,
        'source' => $bootSource,
        'themeId' => $themeId,
    ]);
    $seenKeys[$bootKey] = true;
}

usort($otherEntries, static function (array $a, array $b): int {
    return strcasecmp($a['label'], $b['label']);
});
foreach ($otherEntries as $entry) {
    $penEditorSkinsList[] = $entry;
}

$penEditorSkinsMap = [];
foreach ($penEditorSkinsList as $entry) {
    $penEditorSkinsMap[$entry['key']] = $entry;
}
