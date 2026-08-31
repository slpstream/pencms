<?php

namespace Dossier;

/**
 * Static dist SEO helpers: Content-Signal, IndexNow key/host rules, 301 emit.
 */
class StaticSeo
{
    public static function contentSignalHeader(bool $aiTrain): string
    {
        return $aiTrain
            ? 'search=yes, ai-input=yes, ai-train=yes'
            : 'search=yes, ai-input=yes, ai-train=no';
    }

    public static function isValidIndexNowKey(string $key): bool
    {
        return (bool) preg_match('/^[A-Za-z0-9-]{8,128}$/', $key);
    }

    /**
     * True when IndexNow / public sitemap advertising should be skipped.
     */
    public static function isSkippedHost(?string $host): bool
    {
        if (!is_string($host) || $host === '') {
            return true;
        }
        $host = strtolower(trim($host, '[]'));
        if ($host === 'localhost' || $host === '::1') {
            return true;
        }
        if (filter_var($host, FILTER_VALIDATE_IP)) {
            return self::isPrivateOrLocalIp($host);
        }
        $suffixes = [
            '.localhost',
            '.local',
            '.lan',
            '.internal',
            '.test',
            '.example',
            '.invalid',
        ];
        foreach ($suffixes as $suffix) {
            if ($host === ltrim($suffix, '.') || str_ends_with($host, $suffix)) {
                return true;
            }
        }

        return false;
    }

    public static function isPrivateOrLocalIp(string $ip): bool
    {
        if ($ip === '127.0.0.1' || $ip === '::1') {
            return true;
        }
        $filtered = filter_var(
            $ip,
            FILTER_VALIDATE_IP,
            FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE
        );

        return $filtered === false;
    }

    public static function isPublicHttpsUrl(string $url): bool
    {
        $parts = parse_url($url);
        if (!is_array($parts)) {
            return false;
        }
        $scheme = strtolower((string) ($parts['scheme'] ?? ''));
        if ($scheme !== 'https') {
            return false;
        }
        $host = $parts['host'] ?? null;

        return !self::isSkippedHost(is_string($host) ? $host : null);
    }

    /**
     * @param list<array<string, mixed>> $raw
     * @return list<array{from: string, to: string}>
     */
    public static function sanitizeRedirects(array $raw): array
    {
        $out = [];
        foreach ($raw as $item) {
            if (!is_array($item)) {
                continue;
            }
            $from = self::sanitizeRedirectPath((string) ($item['from'] ?? ''));
            $to = self::sanitizeRedirectPath((string) ($item['to'] ?? ''));
            if ($from === null || $to === null) {
                continue;
            }
            $out[] = ['from' => $from, 'to' => $to];
        }

        return $out;
    }

    public static function sanitizeRedirectPath(string $raw): ?string
    {
        $path = trim($raw);
        if ($path === '' || !str_starts_with($path, '/') || str_starts_with($path, '//')) {
            return null;
        }
        $lower = strtolower($path);
        if (str_contains($path, '://') || str_starts_with($lower, 'http:') || str_starts_with($lower, 'https:')) {
            return null;
        }
        if (str_contains($path, "\\") || str_contains($path, "\n") || str_contains($path, "\r")) {
            return null;
        }

        return $path;
    }

    /**
     * @param list<array{from: string, to: string}> $redirects
     */
    public static function apacheRewriteRules(array $redirects): string
    {
        if ($redirects === []) {
            return '';
        }
        $lines = ['', '# PenCMS static 301s'];
        foreach ($redirects as $row) {
            $pattern = self::apachePattern($row['from']);
            $target = self::apacheTarget($row['to']);
            $lines[] = 'RewriteRule ^' . $pattern . '$ ' . $target . ' [R=301,L]';
        }

        return implode("\n", $lines) . "\n";
    }

    /**
     * @param list<array{from: string, to: string}> $redirects
     */
    public static function netlifyRedirectsFile(array $redirects): string
    {
        $lines = [];
        foreach ($redirects as $row) {
            $lines[] = $row['from'] . '  ' . $row['to'] . '  301';
        }

        return implode("\n", $lines) . "\n";
    }

    /**
     * Best-effort IndexNow POST. Returns true on HTTP 2xx. Never throws.
     *
     * @param list<string> $urlList
     */
    public static function pingIndexNow(string $host, string $key, string $keyLocation, array $urlList): bool
    {
        $urlList = array_values(array_unique(array_filter($urlList, 'is_string')));
        if ($urlList === [] || !self::isValidIndexNowKey($key)) {
            return false;
        }
        $payload = json_encode([
            'host' => $host,
            'key' => $key,
            'keyLocation' => $keyLocation,
            'urlList' => array_slice($urlList, 0, 10000),
        ], JSON_UNESCAPED_SLASHES);
        if (!is_string($payload)) {
            return false;
        }
        $ctx = stream_context_create([
            'http' => [
                'method' => 'POST',
                'header' => "Content-Type: application/json\r\n",
                'content' => $payload,
                'timeout' => 8,
                'ignore_errors' => true,
            ],
        ]);
        $result = @file_get_contents('https://api.indexnow.org/indexnow', false, $ctx);
        if ($result === false) {
            return false;
        }
        $code = 0;
        if (isset($http_response_header[0]) && preg_match('/\s(\d{3})\s/', $http_response_header[0], $m)) {
            $code = (int) $m[1];
        }

        return $code >= 200 && $code < 300;
    }

    /**
     * HTML loc values from a sitemap.xml string.
     *
     * @return list<string>
     */
    public static function sitemapHtmlLocs(string $xml): array
    {
        $locs = [];
        if (preg_match_all('/<loc>\s*([^<]+)\s*<\/loc>/i', $xml, $matches)) {
            foreach ($matches[1] as $loc) {
                $url = html_entity_decode(trim($loc), ENT_QUOTES | ENT_XML1, 'UTF-8');
                if ($url === '') {
                    continue;
                }
                $path = parse_url($url, PHP_URL_PATH);
                if (is_string($path) && preg_match('/\.(md|txt|xml|jsonl|json)$/i', $path)) {
                    continue;
                }
                $locs[] = $url;
            }
        }

        return array_values(array_unique($locs));
    }

    private static function apachePattern(string $from): string
    {
        $path = ltrim($from, '/');
        if (str_ends_with($path, '/')) {
            $path = substr($path, 0, -1);
        }
        $escaped = str_replace('\\-', '-', preg_quote($path, '#'));

        return $escaped . '/?';
    }

    private static function apacheTarget(string $to): string
    {
        return str_replace([' ', '%'], ['%20', '%25'], $to);
    }
}
