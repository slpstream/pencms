<?php

namespace Dossier;

require_once __DIR__ . '/DossierDiscovery.php';

/**
 * Builds a site-wide RSS 2.0 feed from published posts.
 *
 * Posts only (page: true excluded). Item link/guid = SITE_URL/{slug}/.
 */
class RssFeedBuilder
{
    /**
     * @param array  $dossiers   From DossierDiscovery::getAllDossiers('blog', false)
     * @param string $siteUrl    Absolute site root with trailing slash (e.g. https://example.com/)
     * @param string $sitename   Channel title
     * @param string $tagline    Channel description
     * @param string|null $logoUrl Relative or absolute logo URL from ThemeEngine::getLogoUrl()
     */
    public static function build(
        array $dossiers,
        string $siteUrl,
        string $sitename,
        string $tagline = '',
        ?string $logoUrl = null
    ): string {
        $siteUrl = self::normalizeSiteUrl($siteUrl);
        $channelLink = $siteUrl;
        $title = $sitename !== '' ? $sitename : 'Feed';
        $description = $tagline !== '' ? $tagline : $title;

        $lastBuild = !empty($dossiers)
            ? self::rfc822Date($dossiers[0]['date'] ?? 'now')
            : self::rfc822Date('now');

        $xml = '<?xml version="1.0" encoding="UTF-8"?>' . "\n";
        $xml .= '<rss version="2.0">' . "\n";
        $xml .= "  <channel>\n";
        $xml .= '    <title>' . self::esc($title) . "</title>\n";
        $xml .= '    <link>' . self::esc($channelLink) . "</link>\n";
        $xml .= '    <description>' . self::esc($description) . "</description>\n";
        $xml .= '    <lastBuildDate>' . self::esc($lastBuild) . "</lastBuildDate>\n";

        $logoPath = self::normalizeLogoPath($logoUrl);
        if ($logoPath !== null) {
            $imageUrl = $siteUrl . $logoPath;
            $xml .= "    <image>\n";
            $xml .= '      <url>' . self::esc($imageUrl) . "</url>\n";
            $xml .= '      <title>' . self::esc($title) . "</title>\n";
            $xml .= '      <link>' . self::esc($channelLink) . "</link>\n";
            $xml .= "    </image>\n";
        }

        foreach ($dossiers as $d) {
            if (!empty($d['page']) || DossierDiscovery::isNoindex($d)) {
                continue;
            }
            $slug = (string)($d['slug'] ?? '');
            if ($slug === '') {
                continue;
            }
            $permalink = $siteUrl . $slug . '/';
            $itemTitle = (string)($d['hero_title'] ?? $d['title'] ?? $slug);
            $itemDesc = (string)($d['deck'] ?? '');
            $pubDate = self::rfc822Date($d['date'] ?? 'now');

            $xml .= "    <item>\n";
            $xml .= '      <title>' . self::esc($itemTitle) . "</title>\n";
            $xml .= '      <link>' . self::esc($permalink) . "</link>\n";
            $xml .= '      <guid isPermaLink="true">' . self::esc($permalink) . "</guid>\n";
            $xml .= '      <pubDate>' . self::esc($pubDate) . "</pubDate>\n";
            if ($itemDesc !== '') {
                $xml .= '      <description>' . self::esc($itemDesc) . "</description>\n";
            }
            $xml .= "    </item>\n";
        }

        $xml .= "  </channel>\n";
        $xml .= "</rss>\n";

        return $xml;
    }

    public static function normalizeSiteUrl(string $siteUrl): string
    {
        $siteUrl = trim($siteUrl);
        if ($siteUrl === '') {
            return 'http://localhost/';
        }
        if (!preg_match('#^https?://#i', $siteUrl)) {
            $siteUrl = 'https://' . preg_replace('#^//#', '', $siteUrl);
        }
        return rtrim($siteUrl, '/') . '/';
    }

    /**
     * Map ThemeEngine logo URLs (static or preview) to a published-site relative path.
     */
    public static function normalizeLogoPath(?string $logoUrl): ?string
    {
        if ($logoUrl === null || $logoUrl === '') {
            return null;
        }
        if (preg_match('#(?:^|/)(shared/images/logo\.[a-z0-9]+)$#i', $logoUrl, $m)) {
            return $m[1];
        }
        if (preg_match('#(?:^|/)(images/logo\.[a-z0-9]+)$#i', $logoUrl, $m)) {
            return $m[1];
        }
        return null;
    }

    private static function esc(string $value): string
    {
        return htmlspecialchars($value, ENT_XML1 | ENT_QUOTES, 'UTF-8');
    }

    private static function rfc822Date(string $date): string
    {
        $ts = strtotime($date);
        if ($ts === false) {
            $ts = time();
        }
        return date('D, d M Y H:i:s O', $ts);
    }
}
