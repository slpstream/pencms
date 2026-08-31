#!/usr/bin/env php
<?php

/**
 * Rebuild static sites that have recently due scheduled posts.
 *
 * When a post has status=published and publish_at in the past (within the
 * lookback window), PHP preview already lists it. Static dist/ trees do not
 * update until a build runs — this CLI finds sites with due publishes and
 * invokes build.sh for each.
 *
 * Usage:
 *   php rebuild-due.php [--hours=6] [--dry-run] [--domain=<host>] [--output=<dir>]
 *
 * Cron example (every 5 minutes):
 *   0-59/5 * * * * cd /path/to/pencms/frontend-php/cli-tools && php rebuild-due.php >> /var/log/pencms-rebuild-due.log 2>&1
 *
 * Skip this entirely if you only use PHP preview (no static export).
 */

require_once __DIR__ . '/../vendor/autoload.php';
require_once __DIR__ . '/../src/core/InternalAPIClient.php';
require_once __DIR__ . '/../src/core/SiteRegistry.php';

use Dossier\InternalAPIClient;
use Dossier\SiteRegistry;

$options = getopt('', ['hours::', 'dry-run', 'domain::', 'output::']);
$hours = isset($options['hours']) ? max(1, (int) $options['hours']) : 6;
$dryRun = array_key_exists('dry-run', $options);

$extraBuildArgs = [];
if (!empty($options['domain'])) {
    $extraBuildArgs[] = '--domain=' . $options['domain'];
}
if (!empty($options['output'])) {
    $extraBuildArgs[] = '--output=' . $options['output'];
}

$configPath = __DIR__ . '/../../backend-python/config.ini';
$registry = SiteRegistry::fromConfigPath($configPath);

$siteIds = [];
foreach ($registry->listSites() as $site) {
    $id = strtolower(trim((string) ($site['id'] ?? '')));
    if ($id !== '') {
        $siteIds[] = $id;
    }
}
if ($siteIds === []) {
    $siteIds = ['default'];
}

$dueSites = [];
foreach ($siteIds as $siteId) {
    $api = new InternalAPIClient($siteId);
    try {
        $pages = $api->get('/pages/', [
            'due_within_hours' => $hours,
            'live_only' => 'true',
        ]);
    } catch (Throwable $e) {
        fwrite(STDERR, "warn: could not query site '{$siteId}': " . $e->getMessage() . "\n");
        continue;
    }
    if (!is_array($pages)) {
        continue;
    }
    $count = count($pages);
    if ($count > 0) {
        $dueSites[$siteId] = $count;
        echo "site={$siteId} due_posts={$count}\n";
    }
}

if (empty($dueSites)) {
    echo "No sites with publish_at due in the last {$hours}h.\n";
    exit(0);
}

if ($dryRun) {
    echo "Dry run — would rebuild: " . implode(', ', array_keys($dueSites)) . "\n";
    exit(0);
}

$buildSh = __DIR__ . '/build.sh';
if (!is_file($buildSh)) {
    fwrite(STDERR, "error: build.sh not found at {$buildSh}\n");
    exit(1);
}

$failed = 0;
foreach (array_keys($dueSites) as $siteId) {
    $cmd = array_merge(['bash', $buildSh, '--site=' . $siteId], $extraBuildArgs);
    echo "Rebuilding site={$siteId} …\n";
    $escaped = implode(' ', array_map('escapeshellarg', $cmd));
    passthru($escaped, $code);
    if ($code !== 0) {
        fwrite(STDERR, "error: build failed for site={$siteId} (exit {$code})\n");
        $failed++;
    }
}

exit($failed > 0 ? 1 : 0);
