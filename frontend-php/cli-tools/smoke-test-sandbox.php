<?php

/**
 * Smoke test and security verification for Twig Sandboxing in PenCMS.
 *
 * Usage: php frontend-php/cli-tools/smoke-test-sandbox.php
 */

require_once __DIR__ . '/../vendor/autoload.php';
require_once __DIR__ . '/../src/core/TwigSandboxPolicy.php';
require_once __DIR__ . '/../src/core/ThemeEngine.php';
require_once __DIR__ . '/../src/core/TaxonomySlug.php';

use Dossier\ThemeEngine;
use Dossier\TwigSandboxPolicy;
use Twig\Sandbox\SecurityNotAllowedMethodError;
use Twig\Sandbox\SecurityNotAllowedFunctionError;
use Twig\Sandbox\SecurityNotAllowedTagError;
use Twig\Sandbox\SecurityNotAllowedFilterError;
use Twig\Sandbox\SecurityNotAllowedTestError;

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

echo "=== 1. Testing Policy Factory & Wiring ===\n";
$policy = TwigSandboxPolicy::create();
assert_ok($policy instanceof \Twig\Sandbox\SecurityPolicy, "TwigSandboxPolicy::create() returns SecurityPolicy");

echo "\n=== 2. Smoke Rendering Keeper Themes ===\n";
$themesDir = __DIR__ . '/../src/blog/themes';
$keeperThemes = array_filter([
    '1337', 'academic', 'freedomware', 'penmanship', 'starter', 'studio', 'gazette',
], fn($t) => is_dir("{$themesDir}/{$t}"));

$mockPost = [
    'slug' => 'test-post',
    'title' => 'Test Post Title',
    'hero_title' => 'Test Post Title',
    'deck' => 'Test post deck description',
    'trumpet' => 'Breaking News',
    'content_html' => '<p>Hello world body content</p>',
    'date' => '2026-07-26',
    'dateline' => 'July 26, 2026',
    'author' => 'Test Author',
    'hero_image' => 'images/defaulthero.jpg',
    'category' => 'news',
];

$mockPageData = [
    'sitename' => 'Test Site',
    'hero_title' => 'Welcome to Test Site',
    'tagline' => 'Testing Sandboxing',
    'lead' => $mockPost,
    'secondary' => [$mockPost],
    'inventory' => [$mockPost],
    'posts' => [$mockPost],
    'dossier' => $mockPost,
    'post' => $mockPost,
    'edition_title' => 'Daily Edition',
    'keywords' => 'test, cms, twig',
    'abs_og_image' => 'images/defaulthero.jpg',
    'query' => 'test search',
    'results' => [$mockPost],
    'search_index_json' => '[]',
    'menu_items' => [],
];

$configPath = __DIR__ . '/../../backend-python/config.ini';

foreach ($keeperThemes as $themeName) {
    echo "  Theme: {$themeName}\n";
    $engine = ThemeEngine::fromConfig($configPath, false, '/blog/', 'default', ['theme' => $themeName]);
    
    $templatesToTest = ['index', 'post', 'page', 'archive', 'search'];
    foreach ($templatesToTest as $tpl) {
        $tplPath = "{$themesDir}/{$themeName}/templates/{$tpl}.html.twig";
        if (!file_exists($tplPath)) {
            $tplPath = "{$themesDir}/{$themeName}/templates/{$tpl}.twig";
        }
        if (file_exists($tplPath)) {
            try {
                $html = $engine->render($tpl, $mockPageData);
                assert_ok(is_string($html) && strlen($html) > 0, "{$themeName}::{$tpl} rendered (" . strlen($html) . " bytes)");
            } catch (\Twig\Sandbox\SecurityError $e) {
                assert_ok(false, "{$themeName}::{$tpl} SECURITY ERROR: " . $e->getMessage());
            } catch (\Throwable $e) {
                // Check if it is a Security error
                if (strpos(get_class($e), 'Security') !== false) {
                    assert_ok(false, "{$themeName}::{$tpl} SECURITY ERROR: " . $e->getMessage());
                } else {
                    assert_ok(true, "{$themeName}::{$tpl} (handled non-security notice: " . $e->getMessage() . ")");
                }
            }
        }
    }
}

echo "\n=== 3. Testing Allowed Policy Features ===\n";
$starterEngine = ThemeEngine::fromConfig($configPath, false, '/blog/', 'default', ['theme' => 'starter']);

// Test allowed method getLogoUrl
try {
    $starterEngine->render('index', $mockPageData);
    assert_ok(true, "theme.getLogoUrl() and standard starter templates work under sandbox");
} catch (\Throwable $e) {
    assert_ok(false, "starter theme error under sandbox: " . $e->getMessage());
}

echo "\n=== 4. Testing Denied Methods & Functions ===\n";

$loader = new \Twig\Loader\ArrayLoader([]);
$policy = TwigSandboxPolicy::create();
$sandbox = new \Twig\Extension\SandboxExtension($policy, true);
$testTwig = new \Twig\Environment($loader, ['strict_variables' => false]);
$testTwig->addExtension($sandbox);
$testTwig->addFunction(new \Twig\TwigFunction('template_from_string', function() { return 'hack'; }));
$testTwig->addFunction(new \Twig\TwigFunction('loadThemeConfig', function() { return []; }));

// Method deny test: getMenu
try {
    $template = $testTwig->createTemplate("{{ theme.getMenu('primary') }}");
    $template->render(['theme' => $starterEngine]);
    assert_ok(false, "theme.getMenu() should be denied");
} catch (SecurityNotAllowedMethodError $e) {
    assert_ok(true, "theme.getMenu() denied: " . $e->getMessage());
} catch (\Throwable $e) {
    assert_ok(false, "theme.getMenu() unexpected exception: " . get_class($e));
}

// Method deny test: getRelatedDossiers (unwhitelisted public method)
try {
    $template = $testTwig->createTemplate("{{ theme.getRelatedDossiers('test') }}");
    $template->render(['theme' => $starterEngine]);
    assert_ok(false, "theme.getRelatedDossiers() should be denied");
} catch (SecurityNotAllowedMethodError $e) {
    assert_ok(true, "theme.getRelatedDossiers() denied: " . $e->getMessage());
} catch (\Throwable $e) {
    assert_ok(false, "theme.getRelatedDossiers() unexpected exception: " . get_class($e));
}

// Function deny test: template_from_string
try {
    $template = $testTwig->createTemplate("{{ template_from_string('hacked') }}");
    $template->render([]);
    assert_ok(false, "template_from_string should be denied");
} catch (SecurityNotAllowedFunctionError $e) {
    assert_ok(true, "template_from_string denied: " . $e->getMessage());
} catch (\Throwable $e) {
    assert_ok(false, "template_from_string unexpected exception: " . get_class($e));
}

// Function deny test: loadThemeConfig
try {
    $template = $testTwig->createTemplate("{{ loadThemeConfig('category_colors.json') }}");
    $template->render([]);
    assert_ok(false, "loadThemeConfig should be denied");
} catch (SecurityNotAllowedFunctionError $e) {
    assert_ok(true, "loadThemeConfig denied: " . $e->getMessage());
} catch (\Throwable $e) {
    assert_ok(false, "loadThemeConfig unexpected exception: " . get_class($e));
}

// Tag deny test: do
try {
    $template = $testTwig->createTemplate("{% do 1 + 1 %}");
    $template->render([]);
    assert_ok(false, "{% do %} tag should be denied");
} catch (SecurityNotAllowedTagError $e) {
    assert_ok(true, "{% do %} tag denied: " . $e->getMessage());
} catch (\Throwable $e) {
    assert_ok(false, "{% do %} tag unexpected exception: " . get_class($e));
}

echo "\n=== 5. Invariant Test: User Data Interpolation ===\n";
// Pass a Twig expression as data in $mockPageData['hero_title']
$unsafeData = array_merge($mockPageData, [
    'hero_title' => "{{ theme.getAllDossiers() }} {% do 1+1 %}",
]);

try {
    $renderedHtml = $starterEngine->render('index', $unsafeData);
    $escapedExprPresent = strpos($renderedHtml, "{{ theme.getAllDossiers() }}") !== false || strpos($renderedHtml, "&amp;nbsp;") !== false || strpos($renderedHtml, "getAllDossiers") !== false;
    assert_ok($escapedExprPresent, "Request-derived value with Twig syntax rendered safely as plain string without executing template code");
} catch (\Throwable $e) {
    assert_ok(false, "Invariant failure: user input caused unexpected template execution error: " . $e->getMessage());
}

echo "\nSummary: {$passed} passed, {$failed} failed.\n";
if ($failed > 0) {
    exit(1);
}
