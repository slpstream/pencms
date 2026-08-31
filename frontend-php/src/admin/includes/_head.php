<?php
/**
 * PenCMS Public Auth Head Layout
 */
include_once __DIR__ . "/_auth.php"; ?>
<!DOCTYPE html>
<html lang="en" class="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo $pageTitle ?? "PenCMS Auth"; ?></title>
    <link rel="icon" type="image/x-icon" href="/blog/favicon.ico">
    <style>[x-cloak]{display:none!important}</style>
    <link rel="stylesheet" href="css/admin.css">

    <!-- Auth Context -->
    <script src="js/vault.js"></script>
    <script>
        window.AUTH = <?= json_encode(
            $authContext ?? ["apiBase" => "/api/v1"],
        ) ?>;
        window.AUTH.getHeaders = () => {
            return {
                'Content-Type': 'application/json',
                'X-User-ID': window.AUTH.userId || 'author'
            };
        };
    </script>

    <!-- Alpine.js -->
    <script defer src="/assets/vendor/alpine.min.js"></script>
</head>
