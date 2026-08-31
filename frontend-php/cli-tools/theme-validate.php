<?php

/**
 * PenCMS Theme Validator
 * Checks a theme for structural integrity, dual-duty markup/skin,
 * and social_preview manifest correctness.
 */

if ($argc < 2) {
    echo "Usage: php theme-validate.php <theme-name>\n";
    exit(1);
}

$themeName = preg_replace('/[^a-z0-9-]/', '', strtolower($argv[1]));
$themesDir = __DIR__ . '/../src/blog/themes';
$targetDir = $themesDir . '/' . $themeName;

if (!is_dir($targetDir)) {
    echo "❌ Error: Theme '{$themeName}' not found in {$themesDir}\n";
    exit(1);
}

echo "🔍 Validating theme: {$themeName}...\n";

$errors = 0;
$warnings = 0;

/**
 * Resolve a template path under templates/ (html.twig, twig, or php).
 */
function themeValidateFindTemplate(string $targetDir, string $basename): ?string
{
    $candidates = [
        $targetDir . '/templates/' . $basename . '.html.twig',
        $targetDir . '/templates/' . $basename . '.twig',
        $targetDir . '/templates/' . $basename . '.php',
    ];
    foreach ($candidates as $path) {
        if (file_exists($path)) {
            return $path;
        }
    }
    return null;
}

/**
 * Require traven-preview in a template file; bump $errors on failure.
 */
function themeValidateRequireTravenPreview(string $path, string $label, int &$errors): void
{
    $contents = file_get_contents($path);
    if ($contents === false || strpos($contents, 'traven-preview') === false) {
        echo "❌ Missing 'traven-preview' in {$label} (body wrappers need class=\"article-content traven-preview\")\n";
        $errors++;
    } else {
        echo "✅ {$label} includes traven-preview\n";
    }
}

// ── Manifest ──

$data = null;
if (!file_exists($targetDir . '/theme.json')) {
    echo "❌ Missing mandatory file: theme.json\n";
    $errors++;
} else {
    $json = file_get_contents($targetDir . '/theme.json');
    $data = json_decode($json, true);
    if (json_last_error() !== JSON_ERROR_NONE) {
        echo "❌ Invalid JSON in theme.json: " . json_last_error_msg() . "\n";
        $errors++;
        $data = null;
    } else {
        if (!isset($data['name'])) {
            echo "⚠️ Warning: 'name' missing in theme.json\n";
            $warnings++;
        }
    }
}

$themeType = 'native';

// ── Native theme validation ──

// Check for post template
$hasPost = themeValidateFindTemplate($targetDir, 'post') !== null;
if (!$hasPost) {
    echo "❌ Missing mandatory template: templates/post.php or templates/post.html.twig\n";
    $errors++;
} else {
    echo "✅ post template exists\n";
}

// Check for index template
$hasIndex = themeValidateFindTemplate($targetDir, 'index') !== null;
if (!$hasIndex) {
    echo "❌ Missing mandatory template: templates/index.php or templates/index.html.twig\n";
    $errors++;
} else {
    echo "✅ index template exists\n";
}

// Check for page template
$hasPage = themeValidateFindTemplate($targetDir, 'page') !== null;
if (!$hasPage) {
    echo "❌ Missing mandatory template: templates/page.php or templates/page.html.twig\n";
    $errors++;
} else {
    echo "✅ page template exists\n";
}

// Check for search template (required by static publish → search/index.html)
$hasSearch = themeValidateFindTemplate($targetDir, 'search') !== null;
if (!$hasSearch) {
    echo "❌ Missing mandatory template: templates/search.php or templates/search.html.twig (static publish renders search/index.html)\n";
    $errors++;
} else {
    echo "✅ search template exists\n";
}

// Check category overrides
$postOverrides = glob($targetDir . '/templates/post-*.html.twig') ?: [];
$archiveOverrides = glob($targetDir . '/templates/archive-*.html.twig') ?: [];
$pageOverrides = glob($targetDir . '/templates/page-*.html.twig') ?: [];

foreach ($postOverrides as $po) {
    $cat = preg_replace('/^post-(.*)\.html\.twig$/', '$1', basename($po));
    if (!file_exists($targetDir . '/templates/archive-' . $cat . '.html.twig')) {
        echo "⚠️ Warning: templates/post-{$cat}.html.twig exists but templates/archive-{$cat}.html.twig does not. The '{$cat}' category will have themed posts but a generic listing page. This may be intentional.\n";
        $warnings++;
    }
}
foreach ($archiveOverrides as $ao) {
    $cat = preg_replace('/^archive-(.*)\.html\.twig$/', '$1', basename($ao));
    if (!file_exists($targetDir . '/templates/post-' . $cat . '.html.twig')) {
        echo "⚠️ Warning: templates/archive-{$cat}.html.twig exists but templates/post-{$cat}.html.twig does not.\n";
        $warnings++;
    }
}

// Check for archive template (optional)
$hasArchive = themeValidateFindTemplate($targetDir, 'archive') !== null;
if (!$hasArchive) {
    echo "⚠️ Warning: 'archive' template missing (optional, falls back to index)\n";
    $warnings++;
} else {
    echo "✅ archive template exists\n";
}

// Check for header partial
$hasHeader = false;
$headerPaths = [
    '/partials/_header.php', '/partials/_header.html.twig', '/partials/_header.twig',
    '/partials/header.php', '/partials/header.html.twig', '/partials/header.twig'
];
foreach ($headerPaths as $p) {
    if (file_exists($targetDir . $p)) {
        $hasHeader = true;
        break;
    }
}
if (!$hasHeader) {
    echo "❌ Missing mandatory partial: _header.php or _header.html.twig\n";
    $errors++;
} else {
    echo "✅ header partial exists\n";
}

// Check for footer partial
$hasFooter = false;
$footerPaths = [
    '/partials/_footer.php', '/partials/_footer.html.twig', '/partials/_footer.twig',
    '/partials/footer.php', '/partials/footer.html.twig', '/partials/footer.twig'
];
foreach ($footerPaths as $p) {
    if (file_exists($targetDir . $p)) {
        $hasFooter = true;
        break;
    }
}
if (!$hasFooter) {
    echo "❌ Missing mandatory partial: _footer.php or _footer.html.twig\n";
    $errors++;
} else {
    echo "✅ footer partial exists\n";
}

// Variables block (recommended for native themes)
if ($data !== null && !isset($data['variables'])) {
    echo "⚠️ Warning: 'variables' block missing in theme.json\n";
    $warnings++;
}

// ── Content skin (Layer B) ──

$skinFiles = glob($targetDir . '/assets/css/skin-*.css') ?: [];
if (count($skinFiles) === 0) {
    echo "❌ Missing content skin: assets/css/skin-*.css (at least one required; overlay themes may ship base + overlay)\n";
    $errors++;
} else {
    $names = array_map('basename', $skinFiles);
    echo "✅ content skin present: " . implode(', ', $names) . "\n";
}

// ── Markup contract: traven-preview ──

$postPath = themeValidateFindTemplate($targetDir, 'post');
if ($postPath !== null) {
    themeValidateRequireTravenPreview($postPath, 'templates/' . basename($postPath), $errors);
}

$pagePath = themeValidateFindTemplate($targetDir, 'page');
if ($pagePath !== null) {
    themeValidateRequireTravenPreview($pagePath, 'templates/' . basename($pagePath), $errors);
}

foreach ($postOverrides as $po) {
    themeValidateRequireTravenPreview($po, 'templates/' . basename($po), $errors);
}
foreach ($pageOverrides as $po) {
    themeValidateRequireTravenPreview($po, 'templates/' . basename($po), $errors);
}

// ── editor_skin (dual-duty; warn if missing) ──

if ($data !== null) {
    $editorSkin = $data['editor_skin'] ?? null;
    if ($editorSkin === null || $editorSkin === '') {
        echo "⚠️ Warning: 'editor_skin' missing in theme.json (required for dual-duty / active-theme editor parity)\n";
        $warnings++;
    } else {
        echo "✅ editor_skin declared: {$editorSkin}\n";
    }

    // ── editor_image_aspect (optional; soft-warn on bad shape) ──
    if (array_key_exists('editor_image_aspect', $data)) {
        $aspect = $data['editor_image_aspect'];
        if (!is_array($aspect)) {
            echo "⚠️ Warning: 'editor_image_aspect' must be an array of {value,label} objects\n";
            $warnings++;
        } else {
            $bad = false;
            foreach ($aspect as $item) {
                if (!is_array($item)
                    || !array_key_exists('value', $item)
                    || !array_key_exists('label', $item)
                    || !is_string($item['value'])
                    || !is_string($item['label'])
                    || trim($item['label']) === ''
                ) {
                    $bad = true;
                    break;
                }
            }
            if ($bad) {
                echo "⚠️ Warning: 'editor_image_aspect' entries must be { \"value\": string, \"label\": non-empty string }\n";
                $warnings++;
            } elseif ($aspect === []) {
                echo "✅ editor_image_aspect declared (empty — no Aspect UI)\n";
            } else {
                echo "✅ editor_image_aspect declared (" . count($aspect) . " options)\n";
            }
        }
    }
}

// ── social_preview completeness ──

$requiredSocialKeys = [
    'og_accent_color',
    'og_vignette_color',
    'og_text_color',
    'og_bar_color',
    'og_font',
    'og_fonts',
    'og_headline_style',
    'og_text_case',
    'og_grade_preset',
    'og_accent_bar',
    'og_watermark',
    'og_default_hero',
    'og_default_image',
    'og_fallback_title',
    'og_title_fallback',
    'og_description_fallback',
    'twitter_card',
];

$headlineStyles = [
    'redacted', 'shadow', 'plain', 'left', 'left_redacted', 'center',
    'center_redacted', 'outline', 'banner', 'boxed', 'underline', 'caption', 'poster',
];
$textCases = ['upper', 'title', 'as_is'];
$gradePresets = [
    'noir', 'clean', 'none', 'vibrant', 'warm', 'cool', 'fade',
    'high_contrast', 'sepia', 'mono', 'dusk', 'night', 'paper',
];

$social = null;
if ($data !== null) {
    if (!isset($data['social_preview']) || !is_array($data['social_preview'])) {
        echo "❌ Missing or invalid 'social_preview' object in theme.json\n";
        $errors++;
    } else {
        $social = $data['social_preview'];
        $missingKeys = [];
        foreach ($requiredSocialKeys as $key) {
            if (!array_key_exists($key, $social)) {
                $missingKeys[] = $key;
            }
        }
        if (count($missingKeys) > 0) {
            echo "❌ Incomplete social_preview; missing keys: " . implode(', ', $missingKeys) . "\n";
            $errors++;
        } else {
            $socialOk = true;

            if (!is_array($social['og_fonts'])) {
                echo "❌ social_preview.og_fonts must be an object/map\n";
                $errors++;
                $socialOk = false;
            }

            if (!in_array($social['og_headline_style'], $headlineStyles, true)) {
                echo "❌ social_preview.og_headline_style must be one of: " . implode('|', $headlineStyles) . "\n";
                $errors++;
                $socialOk = false;
            }
            if (!in_array($social['og_text_case'], $textCases, true)) {
                echo "❌ social_preview.og_text_case must be one of: " . implode('|', $textCases) . "\n";
                $errors++;
                $socialOk = false;
            }
            if (!in_array($social['og_grade_preset'], $gradePresets, true)) {
                echo "❌ social_preview.og_grade_preset must be one of: " . implode('|', $gradePresets) . "\n";
                $errors++;
                $socialOk = false;
            }
            if (!is_bool($social['og_accent_bar'])) {
                echo "❌ social_preview.og_accent_bar must be a boolean\n";
                $errors++;
                $socialOk = false;
            }
            if (array_key_exists('og_watermark_enabled', $social)
                && !is_bool($social['og_watermark_enabled'])) {
                echo "❌ social_preview.og_watermark_enabled must be a boolean\n";
                $errors++;
                $socialOk = false;
            }
            $wmEnums = [
                'og_watermark_source' => ['theme', 'logo', 'custom'],
                'og_watermark_layout' => ['full_canvas', 'corner'],
                'og_watermark_corner' => ['tl', 'tr', 'bl', 'br'],
                'og_watermark_scale' => ['sm', 'md', 'lg'],
            ];
            foreach ($wmEnums as $key => $allowed) {
                if (!array_key_exists($key, $social)) {
                    continue;
                }
                $val = $social[$key];
                if ($val === null || $val === '') {
                    continue;
                }
                if (!in_array($val, $allowed, true)) {
                    echo "❌ social_preview.{$key} must be one of: " . implode('|', $allowed) . "\n";
                    $errors++;
                    $socialOk = false;
                }
            }

            if ($socialOk) {
                echo "✅ social_preview block is complete\n";
            }
        }
    }
}

// ── OG fonts warning ──

if ($social !== null && is_array($social['og_fonts'] ?? null)) {
    $ogFonts = $social['og_fonts'];
    if (count($ogFonts) === 0) {
        echo "⚠️ Warning: social_preview.og_fonts is empty — engine falls back to frontend-php/fonts/CourierPrime-Bold.ttf\n";
        $warnings++;
    } else {
        $allOk = true;
        foreach ($ogFonts as $fontId => $fontPath) {
            if (!is_string($fontPath) || $fontPath === '') {
                echo "⚠️ Warning: og_fonts['{$fontId}'] path is empty or not a string\n";
                $warnings++;
                $allOk = false;
                continue;
            }
            $ext = strtolower(pathinfo($fontPath, PATHINFO_EXTENSION));
            if ($ext !== 'ttf' && $ext !== 'otf') {
                echo "⚠️ Warning: og_fonts['{$fontId}'] is not TTF/OTF ({$fontPath}) — Pillow needs local TTF/OTF\n";
                $warnings++;
                $allOk = false;
            }
            $abs = $targetDir . '/' . ltrim($fontPath, '/');
            if (!file_exists($abs)) {
                echo "⚠️ Warning: og_fonts['{$fontId}'] file missing: {$fontPath}\n";
                $warnings++;
                $allOk = false;
            }
        }
        if ($allOk) {
            echo "✅ og_fonts map points at TTF/OTF under the theme\n";
        }
    }
}

// ── Shared font registry + style select fonts ──

$fontsDir = __DIR__ . '/../public/assets/fonts';
$fontsJsonPath = $fontsDir . '/fonts.json';
$registryFamilies = []; // lowercased family name => true
$registryOk = true;

if (!is_file($fontsJsonPath)) {
    echo "❌ Missing core font registry: public/assets/fonts/fonts.json\n";
    $errors++;
    $registryOk = false;
} else {
    $registry = json_decode((string) file_get_contents($fontsJsonPath), true);
    if (!is_array($registry) || $registry === []) {
        echo "❌ Invalid or empty fonts.json in public/assets/fonts/\n";
        $errors++;
        $registryOk = false;
    } else {
        $missingFiles = [];
        foreach ($registry as $key => $entry) {
            if (!is_array($entry)) {
                echo "❌ fonts.json entry '{$key}' must be an object\n";
                $errors++;
                $registryOk = false;
                continue;
            }
            $family = $entry['family'] ?? null;
            if (!is_string($family) || $family === '') {
                echo "❌ fonts.json entry '{$key}' missing family\n";
                $errors++;
                $registryOk = false;
            } else {
                $registryFamilies[strtolower($family)] = true;
            }
            $files = $entry['files'] ?? null;
            if (!is_array($files) || $files === []) {
                echo "❌ fonts.json entry '{$key}' missing files map\n";
                $errors++;
                $registryOk = false;
                continue;
            }
            foreach ($files as $faceKey => $filename) {
                if (!is_string($filename) || $filename === '') {
                    echo "❌ fonts.json['{$key}'].files['{$faceKey}'] must be a filename\n";
                    $errors++;
                    $registryOk = false;
                    continue;
                }
                if (!is_file($fontsDir . '/' . $filename)) {
                    $missingFiles[] = "{$key}/{$filename}";
                }
            }
        }
        if ($missingFiles) {
            echo "❌ fonts.json references missing files: " . implode(', ', $missingFiles) . "\n";
            $errors++;
            $registryOk = false;
        }
        if ($registryOk) {
            echo "✅ core font registry present (" . count($registry) . " families)\n";
        }
    }
}

/** System / generic stacks that need no self-hosted files (primary family only). */
$systemFontPrimaries = [
    'georgia' => true,
    'times new roman' => true,
    'times' => true,
    'arial' => true,
    'helvetica' => true,
    'courier new' => true,
    'courier' => true,
    'ui-monospace' => true,
    'ui-sans-serif' => true,
    'ui-serif' => true,
    'system-ui' => true,
    'sans-serif' => true,
    'serif' => true,
    'monospace' => true,
    '-apple-system' => true,
    'blinkmacsystemfont' => true,
    'segoe ui' => true,
    'sfmono-regular' => true,
    'menlo' => true,
    'monaco' => true,
    'consolas' => true,
    'liberation mono' => true,
];

/**
 * Extract primary font-family token from a CSS font stack.
 */
$themeValidatePrimaryFamily = static function (string $stack): string {
    $first = trim(explode(',', $stack, 2)[0]);
    if ($first === '') {
        return '';
    }
    if (
        (str_starts_with($first, "'") && str_ends_with($first, "'"))
        || (str_starts_with($first, '"') && str_ends_with($first, '"'))
    ) {
        $first = substr($first, 1, -1);
    }
    return trim($first);
};

/**
 * Collect font-family names declared in theme skin @font-face rules.
 *
 * @return array<string, true>
 */
$themeValidateLocalSkinFamilies = static function (string $themeDir): array {
    $local = [];
    $skinDir = $themeDir . '/assets/css';
    if (!is_dir($skinDir)) {
        return $local;
    }
    foreach (glob($skinDir . '/skin-*.css') ?: [] as $skinPath) {
        $css = file_get_contents($skinPath);
        if ($css === false) {
            continue;
        }
        if (preg_match_all('/@font-face\s*\{(.*?)\}/is', $css, $blocks)) {
            foreach ($blocks[1] as $block) {
                if (preg_match('/font-family\s*:\s*([\'"]?)([^\'";]+)\1/i', $block, $m)) {
                    $name = strtolower(trim($m[2]));
                    if ($name !== '') {
                        $local[$name] = true;
                    }
                }
            }
        }
    }
    return $local;
};

if (is_array($data) && isset($data['style']) && is_array($data['style'])) {
    $localFamilies = $themeValidateLocalSkinFamilies($targetDir);
    $styleFontErrors = 0;
    foreach ($data['style']['groups'] ?? [] as $group) {
        if (!is_array($group)) {
            continue;
        }
        foreach ($group['fields'] ?? [] as $field) {
            if (!is_array($field) || ($field['type'] ?? '') !== 'select') {
                continue;
            }
            $fieldId = (string) ($field['id'] ?? '(unknown)');
            foreach ($field['options'] ?? [] as $opt) {
                if (!is_array($opt)) {
                    continue;
                }
                $value = $opt['value'] ?? null;
                if (!is_string($value) || $value === '') {
                    continue; // Theme default
                }
                $primary = $themeValidatePrimaryFamily($value);
                if ($primary === '') {
                    continue;
                }
                $key = strtolower($primary);
                if (isset($registryFamilies[$key]) || isset($systemFontPrimaries[$key]) || isset($localFamilies[$key])) {
                    continue;
                }
                echo "❌ style select '{$fieldId}' option primary font '{$primary}' is not in the core registry,"
                    . " system allowlist, or theme skin @font-face"
                    . " (see public/assets/fonts/fonts.json)\n";
                $errors++;
                $styleFontErrors++;
            }
        }
    }
    if ($styleFontErrors === 0) {
        echo "✅ style select fonts resolve via registry / system / local @font-face\n";
    }
}

// ── Hero / defaulthero warning ──

$supportsHero = is_array($data) && !empty($data['supports']['hero_image']);
if ($supportsHero) {
    $heroFile = $targetDir . '/assets/images/defaulthero.jpg';
    $ogDefaultHero = is_array($social) ? ($social['og_default_hero'] ?? null) : null;
    $missingHeroFile = !file_exists($heroFile);
    $missingHeroKey = ($ogDefaultHero === null || $ogDefaultHero === '');

    if ($missingHeroFile || $missingHeroKey) {
        $bits = [];
        if ($missingHeroFile) {
            $bits[] = 'assets/images/defaulthero.jpg missing';
        }
        if ($missingHeroKey) {
            $bits[] = 'social_preview.og_default_hero is null/empty';
        }
        echo "⚠️ Warning: supports.hero_image is true but " . implode('; ', $bits) . "\n";
        $warnings++;
    } else {
        // Also warn if declared path does not exist
        $heroAbs = $targetDir . '/' . ltrim((string) $ogDefaultHero, '/');
        if (!file_exists($heroAbs)) {
            echo "⚠️ Warning: social_preview.og_default_hero path missing: {$ogDefaultHero}\n";
            $warnings++;
        } else {
            echo "✅ defaulthero present for hero_image support\n";
        }
    }
}

// ── Result ──

echo "\n" . str_repeat('─', 50) . "\n";

if ($errors === 0) {
    $warnNote = $warnings > 0 ? " ({$warnings} warning(s))" : '';
    echo "✅ Theme '{$themeName}' ({$themeType}) is structurally sound{$warnNote}.\n";
} else {
    echo "❌ Validation failed with {$errors} error(s)";
    if ($warnings > 0) {
        echo " and {$warnings} warning(s)";
    }
    echo ".\n";
    exit(1);
}
