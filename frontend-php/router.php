<?php
/**
 * PenCMS Local Development Router (router.php)
 * Resolves docroot mismatch between public/ and src/admin/ for php -S,
 * and proxies /api/* requests to FastAPI backend to resolve CORS.
 */

$uri = parse_url($_SERVER["REQUEST_URI"], PHP_URL_PATH);

// Intercept root favicon requests: per-site assets only (Host → ?site= → cookie → default)
if ($uri === "/favicon.ico" || $uri === "/favicon.svg" || $uri === "/favicon.png" || $uri === "/favicon.gif") {
    $ext = pathinfo($uri, PATHINFO_EXTENSION);
    $formats = ["svg", "ico", "png", "gif"];
    $filePath = null;

    $configPath = __DIR__ . "/../backend-python/config.ini";
    $contentDir = __DIR__ . "/../pencms-data/content";
    if (file_exists($configPath)) {
        $cfg = parse_ini_file($configPath, true) ?: [];
        $rawContent = $cfg["Paths"]["content_dir"] ?? "../pencms-data/content";
        if (strpos($rawContent, "/") !== 0) {
            $contentDir = __DIR__ . "/../backend-python/" . $rawContent;
        } else {
            $contentDir = $rawContent;
        }
        $alt = __DIR__ . "/" . $rawContent;
        if (!is_dir($contentDir) && is_dir($alt)) {
            $contentDir = $alt;
        }
        $alt2 = dirname(__DIR__) . "/pencms-data/content";
        if (!is_dir($contentDir) && is_dir($alt2)) {
            $contentDir = $alt2;
        }

        require_once __DIR__ . "/src/core/SiteRegistry.php";
        $registry = \Dossier\SiteRegistry::fromConfigPath($configPath);
        $siteId = $registry->resolveSiteIdFromRequest();
        $rel = $registry->contentRelpath($siteId);
        $siteImages = rtrim($contentDir, "/") . "/" . $rel . "/assets/images";

        $candidate = $siteImages . "/favicon." . $ext;
        if (file_exists($candidate) && is_file($candidate)) {
            $filePath = $candidate;
        } else {
            foreach ($formats as $fmt) {
                $testPath = $siteImages . "/favicon." . $fmt;
                if (file_exists($testPath) && is_file($testPath)) {
                    $filePath = $testPath;
                    break;
                }
            }
        }
    }

    if ($filePath !== null && file_exists($filePath) && is_file($filePath)) {
        $mimeType = get_mime_type($filePath);
        header("Content-Type: $mimeType");
        readfile($filePath);
        exit();
    }
    // No install shared fallback — site without a favicon gets 404 (no cross-site bleed)
    http_response_code(404);
    exit();
}

// Intercept /robots.txt: site-scoped body from registry (Host → ?site= → cookie → default)
if ($uri === "/robots.txt") {
    $_SERVER["SCRIPT_FILENAME"] = __DIR__ . "/src/blog/robots.php";
    $_SERVER["SCRIPT_NAME"] = "/blog/robots.php";
    $_SERVER["PHP_SELF"] = "/blog/robots.php";
    chdir(__DIR__ . "/src/blog");
    require __DIR__ . "/src/blog/robots.php";
    exit();
}

// Intercept /sitemap.xml: site-scoped urlset from live-published posts/pages
if ($uri === "/sitemap.xml") {
    $_SERVER["SCRIPT_FILENAME"] = __DIR__ . "/src/blog/sitemap.php";
    $_SERVER["SCRIPT_NAME"] = "/blog/sitemap.php";
    $_SERVER["PHP_SELF"] = "/blog/sitemap.php";
    chdir(__DIR__ . "/src/blog");
    require __DIR__ . "/src/blog/sitemap.php";
    exit();
}

// Helper to get request headers
function get_request_headers()
{
    if (function_exists("getallheaders")) {
        $headers = [];
        foreach (getallheaders() as $name => $value) {
            $headers[] = "$name: $value";
        }
        return $headers;
    }

    $headers = [];
    foreach ($_SERVER as $name => $value) {
        if (substr($name, 0, 5) == "HTTP_") {
            $headers[] =
                str_replace(
                    " ",
                    "-",
                    ucwords(
                        strtolower(str_replace("_", " ", substr($name, 5))),
                    ),
                ) .
                ": " .
                $value;
        } elseif ($name == "CONTENT_TYPE") {
            $headers[] = "Content-Type: " . $value;
        } elseif ($name == "CONTENT_LENGTH") {
            $headers[] = "Content-Length: " . $value;
        }
    }
    return $headers;
}

/**
 * Reconstruct a multipart/form-data request body from $_POST and $_FILES.
 *
 * The PHP built-in server consumes the raw request body to populate the
 * $_POST/$_FILES superglobals when enable_post_data_reading is on (the
 * default). After that, php://input returns an empty string for multipart
 * requests, so we cannot forward the original body directly and must
 * rebuild it from the parsed superglobals.
 */
function build_multipart_body($boundary)
{
    $eol = "\r\n";
    $body = "";

    foreach ($_FILES as $name => $file) {
        $err = is_array($file["error"]) ? ($file["error"][0] ?? 0) : $file["error"];
        if ($err === UPLOAD_ERR_INI_SIZE || $err === UPLOAD_ERR_FORM_SIZE) {
            http_response_code(413);
            header("Content-Type: application/json");
            echo json_encode([
                "detail" => "File size exceeds PHP upload_max_filesize limit. Increase upload_max_filesize in php.ini/.user.ini or upload a smaller file."
            ]);
            exit;
        }
    }

    foreach ($_POST as $name => $value) {
        $body .= "--{$boundary}{$eol}";
        $body .= "Content-Disposition: form-data; name=\"{$name}\"{$eol}{$eol}";
        $body .= $value . $eol;
    }

    foreach ($_FILES as $name => $file) {
        // Handle both single-file and multi-file (nested array) uploads.
        $isMulti = is_array($file["tmp_name"]);
        $count = $isMulti ? count($file["tmp_name"]) : 1;
        for ($i = 0; $i < $count; $i++) {
            $tmpName = $isMulti ? $file["tmp_name"][$i] : $file["tmp_name"];
            $origName = $isMulti ? $file["name"][$i] : $file["name"];
            $type = $isMulti ? $file["type"][$i] : $file["type"];
            if (!is_uploaded_file($tmpName)) {
                continue;
            }
            $contents = file_get_contents($tmpName);
            $dispName = $isMulti ? "{$name}[{$i}]" : $name;
            $body .= "--{$boundary}{$eol}";
            $body .= "Content-Disposition: form-data; name=\"{$dispName}\"; filename=\"{$origName}\"{$eol}";
            $body .= "Content-Type: {$type}{$eol}{$eol}";
            $body .= $contents . $eol;
        }
    }

    $body .= "--{$boundary}--{$eol}";
    return $body;
}

/**
 * Extract the multipart boundary from a Content-Type header.
 */
function parse_multipart_boundary($contentType)
{
    if (
        preg_match('/boundary=(?:(?:"([^"]+)")|([^;\s]+))/i', $contentType, $m)
    ) {
        return isset($m[1]) && $m[1] !== "" ? $m[1] : $m[2] ?? null;
    }
    return null;
}

// Helper to resolve mime types for files outside docroot
function get_mime_type($filename)
{
    $ext = strtolower(pathinfo($filename, PATHINFO_EXTENSION));
    $mimes = [
        "css" => "text/css",
        "js" => "application/javascript",
        "mjs" => "application/javascript",
        "json" => "application/json",
        "png" => "image/png",
        "jpg" => "image/jpeg",
        "jpeg" => "image/jpeg",
        "gif" => "image/gif",
        "svg" => "image/svg+xml",
        "woff" => "font/woff",
        "woff2" => "font/woff2",
        "ttf" => "font/ttf",
    ];
    return $mimes[$ext] ?? "application/octet-stream";
}

/**
 * Resolve $relPath under $baseDir. Rejects traversal and missing files.
 */
function resolve_under_base($baseDir, $relPath)
{
    if ($relPath === "" || strpos($relPath, "..") !== false) {
        return null;
    }
    $base = realpath($baseDir);
    if ($base === false) {
        return null;
    }
    $full = realpath($baseDir . "/" . $relPath);
    if ($full === false || !is_file($full)) {
        return null;
    }
    if (strpos($full, $base . DIRECTORY_SEPARATOR) !== 0 && $full !== $base) {
        return null;
    }
    return $full;
}

/**
 * Serve an immutable-ish static file with Cache-Control and Last-Modified / 304.
 * Always exits.
 */
function serve_cached_file($filePath, $cacheControl)
{
    $mtime = filemtime($filePath);
    $lastModified = gmdate("D, d M Y H:i:s", $mtime) . " GMT";
    $mime = get_mime_type($filePath);
    header("Content-Type: " . $mime);
    header("Cache-Control: " . $cacheControl);
    header("Last-Modified: " . $lastModified);
    // @font-face / preload (crossorigin) use CORS; without ACAO Chrome
    // may skip the HTTP cache on the next navigation.
    if (strpos($mime, "font/") === 0) {
        header("Access-Control-Allow-Origin: *");
    }
    if (isset($_SERVER["HTTP_IF_MODIFIED_SINCE"])) {
        $since = strtotime($_SERVER["HTTP_IF_MODIFIED_SINCE"]);
        if ($since !== false && $since >= $mtime) {
            http_response_code(304);
            exit();
        }
    }
    $size = filesize($filePath);
    if ($size !== false) {
        header("Content-Length: " . $size);
    }
    if (($_SERVER["REQUEST_METHOD"] ?? "") === "HEAD") {
        exit();
    }
    readfile($filePath);
    exit();
}

function static_not_found()
{
    http_response_code(404);
    header("Content-Type: text/plain; charset=UTF-8");
    echo "Not Found";
    exit();
}

/**
 * If $uri is under $uriPrefix, serve from $diskDir or 404. No-op if prefix does not match.
 * php -S fallthrough cannot set Cache-Control; these prefixes must be handled here.
 */
function try_serve_cached_prefix($uri, $uriPrefix, $diskDir, $cacheControl)
{
    if (strpos($uri, $uriPrefix) !== 0) {
        return;
    }
    $rel = substr($uri, strlen($uriPrefix));
    $full = resolve_under_base($diskDir, $rel);
    if ($full) {
        serve_cached_file($full, $cacheControl);
    }
    static_not_found();
}

// 1. Proxy /api/* requests to FastAPI (127.0.0.1:8008)
if (strpos($uri, "/api/") === 0) {
    $backendUrl = "http://127.0.0.1:8008" . $_SERVER["REQUEST_URI"];

    if (function_exists("curl_init")) {
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $backendUrl);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_HEADER, true);
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, $_SERVER["REQUEST_METHOD"]);

        $headers = [];
        $contentType = $_SERVER["CONTENT_TYPE"] ?? "";
        foreach (get_request_headers() as $hdr) {
            // Drop Host (curl sets it) and Content-Length (curl recomputes it
            // from the body so a stale value can never deadlock the proxy).
            if (
                stripos($hdr, "Host:") === 0 ||
                stripos($hdr, "Content-Length:") === 0
            ) {
                continue;
            }
            $headers[] = $hdr;
        }
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

        // Reconstruct the request body. For multipart/form-data the raw
        // php://input stream is unavailable (consumed by PHP to populate
        // $_FILES/$_POST), so the body must be rebuilt from those superglobals.
        $body = "";
        if (stripos($contentType, "multipart/form-data") !== false) {
            $boundary = parse_multipart_boundary($contentType);
            if ($boundary) {
                $body = build_multipart_body($boundary);
            }
        } else {
            $body = file_get_contents("php://input");
        }
        if ($body !== "") {
            curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
        }

        // Safety net: never let a proxied request block the (single-threaded)
        // built-in server indefinitely.
        curl_setopt($ch, CURLOPT_TIMEOUT, 60);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 10);

        $response = curl_exec($ch);
        $header_size = curl_getinfo($ch, CURLINFO_HEADER_SIZE);
        $res_headers = substr($response, 0, $header_size);
        $res_body = substr($response, $header_size);

        foreach (explode("\r\n", $res_headers) as $header) {
            if (
                !empty($header) &&
                stripos($header, "Transfer-Encoding:") !== 0
            ) {
                header($header);
            }
        }
        echo $res_body;
    } else {
        $contentType = $_SERVER["CONTENT_TYPE"] ?? "";
        $body = "";
        if (stripos($contentType, "multipart/form-data") !== false) {
            $boundary = parse_multipart_boundary($contentType);
            if ($boundary) {
                $body = build_multipart_body($boundary);
            }
        } else {
            $body = file_get_contents("php://input");
        }

        $opts = [
            "http" => [
                "method" => $_SERVER["REQUEST_METHOD"],
                "header" => implode("\r\n", get_request_headers()),
                "content" => $body,
                "ignore_errors" => true,
                "timeout" => 60,
            ],
        ];

        $context = stream_context_create($opts);
        $response = file_get_contents($backendUrl, false, $context);

        if (isset($http_response_header)) {
            foreach ($http_response_header as $header) {
                if (stripos($header, "Transfer-Encoding:") === 0) {
                    continue;
                }
                header($header);
            }
        }
        echo $response;
    }
    exit();
}

// 1.8. Handle /blog/shared/images/* requests
if (strpos($uri, "/blog/shared/images/") === 0) {
    $subPath = substr($uri, 20); // strip '/blog/shared/images/'
    $filePath = dirname(__FILE__) . "/../backend-python/apps/blog/shared/images/" . $subPath;
    if (file_exists($filePath) && is_file($filePath)) {
        $mimeType = get_mime_type($filePath);
        header("Content-Type: $mimeType");
        readfile($filePath);
        exit();
    }
    // Missing shared assets must 404 immediately. Falling through lets the
    // single-threaded PHP built-in server queue dozens of probes for minutes.
    http_response_code(404);
    header("Content-Type: text/plain; charset=UTF-8");
    echo "Not Found";
    exit();
}

// Localized public preview surfaces. The registry gate keeps monolingual and
// staged sites on legacy routing; entry points enforce live-sibling eligibility.
if (strpos($uri, "/blog/") === 0) {
    $configPath = __DIR__ . "/../backend-python/config.ini";
    if (file_exists($configPath)) {
        require_once __DIR__ . "/src/core/SiteRegistry.php";
        require_once __DIR__ . "/src/core/LocalizedDetail.php";
        require_once __DIR__ . "/src/core/LocalizedList.php";
        $registry = \Dossier\SiteRegistry::fromConfigPath($configPath);
        $siteId = $registry->resolveSiteIdFromRequest();
        $ini = parse_ini_file($configPath, true) ?: [];
        $presentation = $registry->resolvePresentation($siteId, $ini);
        $localizedList = \Dossier\LocalizedList::matchPath(
            $uri,
            "/blog/",
            $presentation
        );
        if ($localizedList !== null) {
            $_GET["language"] = $localizedList["language"];
            $_GET["_localized_list"] = "1";
            $script = "index.php";
            if ($localizedList["surface"] === "archive") {
                $script = "category.php";
                $_GET["category"] = $localizedList["category"] ?? "";
            } elseif ($localizedList["surface"] === "search") {
                $script = "search.php";
            }
            $_SERVER["SCRIPT_FILENAME"] = __DIR__ . "/src/blog/" . $script;
            $_SERVER["SCRIPT_NAME"] = "/blog/" . $script;
            $_SERVER["PHP_SELF"] = "/blog/" . $script;
            chdir(__DIR__ . "/src/blog");
            require __DIR__ . "/src/blog/" . $script;
            exit();
        }

        $localized = \Dossier\LocalizedDetail::matchPath(
            $uri,
            "/blog/",
            $presentation
        );
        if ($localized !== null) {
            $_GET["slug"] = $localized["slug"];
            $_GET["language"] = $localized["language"];
            $_GET["_localized_detail"] = "1";
            $_SERVER["SCRIPT_FILENAME"] = __DIR__ . "/src/blog/post.php";
            $_SERVER["SCRIPT_NAME"] = "/blog/post.php";
            $_SERVER["PHP_SELF"] = "/blog/post.php";
            chdir(__DIR__ . "/src/blog");
            require __DIR__ . "/src/blog/post.php";
            exit();
        }
    }
}

// 1.8.5 Handle /blog/category and /blog/category/* (empty slug = all-posts Archives)
if ($uri === "/blog/category" || $uri === "/blog/category/" || strpos($uri, "/blog/category/") === 0) {
    $categorySlug = ($uri === "/blog/category" || $uri === "/blog/category/")
        ? ""
        : trim(substr($uri, strlen("/blog/category/")), "/");
    $_GET["category"] = $categorySlug;
    $_SERVER["SCRIPT_FILENAME"] = __DIR__ . "/src/blog/category.php";
    $_SERVER["SCRIPT_NAME"] = "/blog/category.php";
    $_SERVER["PHP_SELF"] = "/blog/category.php";
    chdir(__DIR__ . "/src/blog");
    require __DIR__ . "/src/blog/category.php";
    exit();
}

// 1.8.6 Handle /blog/feed.xml (RSS 2.0; ThemeEngine system target "rss")
if ($uri === "/blog/feed.xml" || $uri === "/blog/feed.xml/") {
    $_SERVER["SCRIPT_FILENAME"] = __DIR__ . "/src/blog/feed.php";
    $_SERVER["SCRIPT_NAME"] = "/blog/feed.php";
    $_SERVER["PHP_SELF"] = "/blog/feed.php";
    chdir(__DIR__ . "/src/blog");
    require __DIR__ . "/src/blog/feed.php";
    exit();
}

// 1.8.7 Handle /blog/search/ (ThemeEngine system target "search")
if ($uri === "/blog/search" || $uri === "/blog/search/") {
    $_SERVER["SCRIPT_FILENAME"] = __DIR__ . "/src/blog/search.php";
    $_SERVER["SCRIPT_NAME"] = "/blog/search.php";
    $_SERVER["PHP_SELF"] = "/blog/search.php";
    chdir(__DIR__ . "/src/blog");
    require __DIR__ . "/src/blog/search.php";
    exit();
}

// 1.9. Handle /blog/* requests
if (strpos($uri, "/blog/") === 0 || $uri === "/blog") {
    if ($uri === "/blog") {
        header("Location: /blog/");
        exit();
    }

    $subPath = substr($uri, 6); // strip '/blog/'
    if ($subPath === "") {
        $subPath = "index.php";
    }

    $filePath = __DIR__ . "/src/blog/" . $subPath;

    if (is_dir($filePath)) {
        $filePath = rtrim($filePath, "/") . "/index.php";
    }

    if (file_exists($filePath)) {
        if (pathinfo($filePath, PATHINFO_EXTENSION) === "php") {
            $_SERVER["SCRIPT_FILENAME"] = $filePath;
            $_SERVER["SCRIPT_NAME"] = "/blog/" . $subPath;
            $_SERVER["PHP_SELF"] = "/blog/" . $subPath;

            chdir(dirname($filePath));
            require $filePath;
        } else {
            serve_cached_file($filePath, "public, max-age=3600");
        }
        exit();
    }
}

// Product static under public/ — php -S fallthrough cannot set Cache-Control.
try_serve_cached_prefix($uri, "/fonts/", __DIR__ . "/public/fonts", "public, max-age=604800");
try_serve_cached_prefix($uri, "/assets/vendor/", __DIR__ . "/public/assets/vendor", "public, max-age=604800");
try_serve_cached_prefix($uri, "/assets/fonts/", __DIR__ . "/public/assets/fonts", "public, max-age=604800");

// Handle /assets/* requests (per-site under content/sites/{id}/assets/, plus legacy).
// Vendor + font registry are handled above; leftover /assets/ is author content — no long TTL.
if (strpos($uri, "/assets/") === 0) {
    $subPath = substr($uri, 8); // strip '/assets/'
    $appRoot = dirname(__FILE__);
    $contentDir = $appRoot . "/../pencms-data/content";
    $configPath = $appRoot . "/../backend-python/config.ini";
    if (file_exists($configPath)) {
        $cfg = parse_ini_file($configPath, true);
        $rawContent = $cfg['Paths']['content_dir'] ?? '../pencms-data/content';
        if (strpos($rawContent, '/') !== 0) {
            $contentDir = $appRoot . "/../backend-python/" . $rawContent;
        } else {
            $contentDir = $rawContent;
        }
        // Prefer path relative to repo root (sibling of frontend-php)
        $alt = $appRoot . "/" . $rawContent;
        if (!is_dir($contentDir) && is_dir($alt)) {
            $contentDir = $alt;
        }
        $alt2 = dirname($appRoot) . "/pencms-data/content";
        if (!is_dir($contentDir) && is_dir($alt2)) {
            $contentDir = $alt2;
        }
    }

    $filePath = null;
    // Canonical: /assets/sites/{id}/assets/...
    if (strpos($subPath, "sites/") === 0) {
        $filePath = rtrim($contentDir, "/") . "/" . $subPath;
    } else {
        // Legacy: /assets/images/... → Host-resolved site assets (else default)
        require_once __DIR__ . "/src/core/SiteRegistry.php";
        $registry = \Dossier\SiteRegistry::fromConfigPath($configPath);
        $siteId = $registry->resolveSiteIdFromRequest();
        $rel = $registry->contentRelpath($siteId);
        $filePath = rtrim($contentDir, "/") . "/" . $rel . "/assets/" . $subPath;
        if (!file_exists($filePath)) {
            // Fall back to old install-wide assets root
            $legacy = $appRoot . "/../pencms-data/assets/" . $subPath;
            if (file_exists($legacy) && is_file($legacy)) {
                $filePath = $legacy;
            }
        }
    }

    if ($filePath && file_exists($filePath) && is_file($filePath)) {
        $mimeType = get_mime_type($filePath);
        header("Content-Type: $mimeType");
        readfile($filePath);
        exit();
    }
}

// 2. Handle /admin/* requests
if (strpos($uri, "/admin/") === 0 || $uri === "/admin") {
    if ($uri === "/admin") {
        header("Location: /admin/");
        exit();
    }

    $subPath = substr($uri, 7); // strip '/admin/'
    if ($subPath === "") {
        $subPath = "index.php";
    }

    $coreAdminDir = __DIR__ . "/src/admin";
    $filePath = $coreAdminDir . "/" . $subPath;

    if (is_dir($filePath)) {
        $filePath = rtrim($filePath, "/") . "/index.php";
    }

    if (!file_exists($filePath)) {
        $proAdmin = getenv("PENCMS_PRO_ADMIN");
        if (is_string($proAdmin) && $proAdmin !== "") {
            $proPath = rtrim($proAdmin, "/") . "/" . $subPath;
            if (is_dir($proPath)) {
                $proPath = rtrim($proPath, "/") . "/index.php";
            }
            if (file_exists($proPath) && is_file($proPath)) {
                $filePath = $proPath;
            }
        }
    }

    if (file_exists($filePath)) {
        if (pathinfo($filePath, PATHINFO_EXTENSION) === "php") {
            $_SERVER["SCRIPT_FILENAME"] = $filePath;
            $_SERVER["SCRIPT_NAME"] = "/admin/" . $subPath;
            $_SERVER["PHP_SELF"] = "/admin/" . $subPath;

            // Overlay pages include Core chrome via relative includes/.
            chdir($coreAdminDir);
            require $filePath;
        } else {
            serve_cached_file($filePath, "public, max-age=86400");
        }
        exit();
    }
}

// 3. Fallback: let the built-in server serve the file from the docroot (public/)
return false;
