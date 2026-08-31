<?php
/**
 * Regression: SiteRegistry must parse sites.yaml when included alone
 * (admin-editor / _editor-skin-resolve), not only via PublicSiteContext.
 *
 * Usage: php frontend-php/cli-tools/test-site-registry-autoload.php
 */

declare(strict_types=1);

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

function assert_ok(bool $cond, string $label): void
{
    global $passed, $failed, $failures;
    if ($cond) {
        $passed++;
        return;
    }
    $failed++;
    $failures[] = $label;
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

echo "=== 1. Include SiteRegistry.php only ===\n";
require_once __DIR__ . '/../src/core/SiteRegistry.php';

use Dossier\SiteRegistry;

assert_ok(
    class_exists('\Symfony\Component\Yaml\Yaml'),
    'Composer Symfony Yaml is autoloaded from SiteRegistry.php alone'
);
assert_ok(
    function_exists('yaml_parse_file') || class_exists('\Symfony\Component\Yaml\Yaml'),
    'at least one YAML parser is available (ext-yaml and/or Symfony Yaml)'
);

$root = sys_get_temp_dir() . '/pencms-registry-autoload-' . bin2hex(random_bytes(6));
mkdir($root . '/data', 0777, true);
$configPath = $root . '/config.ini';
file_put_contents($configPath, "[theme]\nactive = daily\n");
file_put_contents(
    $root . '/data/sites.yaml',
    <<<'YAML'
sites:
  - id: default
    name: Default Site
    content_relpath: sites/default
    theme: 1337
YAML
);

echo "=== 2. Site theme wins over install daily fallback ===\n";
try {
    $registry = SiteRegistry::fromConfigPath($configPath);
    $presentation = $registry->resolvePresentation('default', [
        'theme' => ['active' => 'daily'],
    ]);
    assert_same(1, count($registry->listSites()), 'parsed one site from sites.yaml');
    assert_same('1337', $presentation['theme'], 'site.theme, not config.ini daily');
} finally {
    remove_tree($root);
}

foreach ($failures as $failure) {
    fwrite(STDERR, "[FAIL] {$failure}\n");
}
echo "SiteRegistry autoload: {$passed} passed, {$failed} failed\n";
exit($failed > 0 ? 1 : 0);
