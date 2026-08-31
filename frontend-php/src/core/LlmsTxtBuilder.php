<?php

namespace Dossier;

require_once __DIR__ . '/DossierDiscovery.php';

/**
 * Published-site llmstxt.org index and concatenated markdown corpus.
 * Default-language only in i18n v1 (no /<lang>/llms.txt or llms-full.txt).
 */
class LlmsTxtBuilder
{
    public const FULL_MAX_BYTES = 2097152; // 2 MiB

    public static function isPublicHttpsSiteUrl(string $siteUrl): bool
    {
        if (!preg_match('#^https://#i', $siteUrl)) {
            return false;
        }
        $host = strtolower((string) parse_url($siteUrl, PHP_URL_HOST));
        if ($host === '' || $host === 'localhost' || $host === '127.0.0.1' || $host === '::1') {
            return false;
        }
        return true;
    }

    public static function absoluteOrRelative(string $siteUrl, string $path): string
    {
        $path = ltrim($path, '/');
        if (self::isPublicHttpsSiteUrl($siteUrl)) {
            return rtrim($siteUrl, '/') . '/' . $path;
        }
        return './' . $path;
    }

    public static function oneLineExcerpt(string $deck): string
    {
        $text = trim(strip_tags($deck));
        $text = trim((string) preg_replace('/\s+/u', ' ', $text));
        return $text;
    }

    /**
     * llmstxt.org index: pages + posts with excerpts and archive links.
     *
     * @param list<array<string, mixed>> $allPagesAndPosts
     */
    public static function buildIndex(
        string $sitename,
        string $tagline,
        string $siteUrl,
        array $allPagesAndPosts
    ): string {
        $lines = ['# ' . $sitename];
        $tagline = trim($tagline);
        if ($tagline !== '') {
            $lines[] = '> ' . $tagline;
        }

        $pages = [];
        $posts = [];
        foreach ($allPagesAndPosts as $item) {
            if (DossierDiscovery::isNoindex($item)) {
                continue;
            }
            if (!empty($item['page'])) {
                $pages[] = $item;
            } else {
                $posts[] = $item;
            }
        }

        $formatItem = static function (array $item) use ($siteUrl): string {
            $slug = trim((string) ($item['slug'] ?? ''), '/');
            $title = self::itemTitle($item, $slug);
            $href = self::absoluteOrRelative($siteUrl, $slug . '/index.md');
            $line = '- [' . $title . '](' . $href . ')';
            $excerpt = self::oneLineExcerpt((string) ($item['deck'] ?? ''));
            if ($excerpt !== '') {
                $line .= ': ' . $excerpt;
            }
            return $line;
        };

        if ($pages !== []) {
            $lines[] = '';
            $lines[] = '## Pages';
            foreach ($pages as $page) {
                $lines[] = $formatItem($page);
            }
        }
        if ($posts !== []) {
            $lines[] = '';
            $lines[] = '## Posts';
            foreach ($posts as $post) {
                $lines[] = $formatItem($post);
            }
        }

        $homeHref = self::isPublicHttpsSiteUrl($siteUrl) ? rtrim($siteUrl, '/') . '/' : './';
        $lines[] = '';
        $lines[] = '## Optional';
        $lines[] = '- [HTML home](' . $homeHref . ')';
        $lines[] = '- [Markdown home](' . self::absoluteOrRelative($siteUrl, 'index.md') . ')';
        $lines[] = '';
        $lines[] = '## Full corpus & archives';
        $lines[] = '- [llms-full.txt](' . self::absoluteOrRelative($siteUrl, 'llms-full.txt') . ')';
        $lines[] = '- [content.jsonl](' . self::absoluteOrRelative($siteUrl, 'content.jsonl') . ')';
        $lines[] = '- [RSS](' . self::absoluteOrRelative($siteUrl, 'feed.xml') . ')';
        $lines[] = '- [Sitemap](' . self::absoluteOrRelative($siteUrl, 'sitemap.xml') . ')';
        $lines[] = '';
        return implode("\n", $lines);
    }

    /**
     * Concatenated native markdown corpus (pages + posts).
     *
     * @param list<array{title: string, url: string, published?: string, author?: string, markdown: string}> $items
     */
    public static function buildFull(
        string $sitename,
        string $tagline,
        array $items,
        int $maxBytes = self::FULL_MAX_BYTES
    ): string {
        $header = ['# ' . $sitename];
        $tagline = trim($tagline);
        if ($tagline !== '') {
            $header[] = '> ' . $tagline;
        }
        $header[] = '';
        $out = implode("\n", $header);
        $truncated = false;

        foreach ($items as $item) {
            $chunk = self::formatFullItem($item);
            if (strlen($out) + strlen($chunk) > $maxBytes) {
                $truncated = true;
                break;
            }
            $out .= $chunk;
        }

        if ($truncated) {
            $out .= "---\n"
                . "[truncated] Corpus exceeded ~2 MiB; remaining pages/posts omitted. "
                . "Use content.jsonl or per-slug index.md for the rest.\n";
        }

        return $out;
    }

    /**
     * @param array<string, mixed> $item
     */
    public static function itemTitle(array $item, string $fallback = ''): string
    {
        $title = trim((string) ($item['hero_title'] ?? ''));
        if ($title === '') {
            $title = trim((string) ($item['title'] ?? ''));
        }
        if ($title === '') {
            $title = $fallback;
        }
        return $title;
    }

    /**
     * @param array<string, mixed> $item
     */
    private static function formatFullItem(array $item): string
    {
        $title = trim((string) ($item['title'] ?? ''));
        $url = trim((string) ($item['url'] ?? ''));
        $published = trim((string) ($item['published'] ?? ''));
        $author = trim((string) ($item['author'] ?? ''));
        $markdown = (string) ($item['markdown'] ?? '');

        $lines = ['---', '# ' . $title, 'URL: ' . $url];
        if ($published !== '') {
            $lines[] = 'Published: ' . $published;
        }
        if ($author !== '') {
            $lines[] = 'Author: ' . $author;
        }
        $lines[] = '';

        return implode("\n", $lines) . "\n" . rtrim($markdown) . "\n\n";
    }
}
