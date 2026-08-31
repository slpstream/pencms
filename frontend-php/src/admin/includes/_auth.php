<?php
/**
 * Auth Context for PenCMS
 * 
 * Sets up authentication context from cookies and exposes to JS.
 */

// Simple user identification
$userId = $_COOKIE['pen_user_id'] ?? null;
$userRole = $_COOKIE['pen_role'] ?? null;

// Determine if we are on an auth page
$currentScript = basename($_SERVER['PHP_SELF']);
$isAuthPage = in_array($currentScript, ['login.php', 'setup.php']);

if (!$isAuthPage && !$userId) {
    header("Location: login.php?error=unauthorized");
    exit;
}

// Read port from backend config.ini
$configPath = dirname(__DIR__, 4) . '/backend-python/config.ini';
$apiPort = 8008; // default fallback
if (file_exists($configPath)) {
    $ini = parse_ini_file($configPath, true);
    if (isset($ini['Server']['api_port'])) {
        $apiPort = (int)$ini['Server']['api_port'];
    }
}

// Build auth context for JS
$authContext = [
    'userId' => $userId,
    'role' => $userRole,
    'apiBase' => '/api/v1',
];
?>
