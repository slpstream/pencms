<?php

namespace Dossier;

require_once __DIR__ . '/DossierDiscovery.php';

/**
 * Builds a sitemap.xml urlset from live-published posts and pages.
 *
 * Posts and pages (page: true included). Each loc = SITE_URL/{slug}/.
 * Home is always included as SITE_URL.
 */
class SitemapBuilder
{
    /**
     * @param array $dossiers From DossierDiscovery::getAllDossiers('blog', true)
     * @param string $siteUrl Absolute site root with trailing slash
     * @param array<string, array<int, array>> $localizedDossiersByLanguage
     *        Exact live siblings grouped by configured non-default language.
     * @param string $defaultLanguage Unprefixed default-language code (e.g. en).
     */
    public static function build(
        array $dossiers,
        string $siteUrl,
        array $localizedDossiersByLanguage = [],
        string $defaultLanguage = 'en'
    ): string {
        $siteUrl = RssFeedBuilder::normalizeSiteUrl($siteUrl);
        $defaultLanguage = strtolower(str_replace('_', '-', trim($defaultLanguage)));
        if ($defaultLanguage === '') {
            $defaultLanguage = 'en';
        }

        $entries = [];
        $locsBySlug = [];
        $seen = [];

        $entries[] = [
            'loc' => $siteUrl,
            'lastmod' => null,
            'slug' => '',
        ];

        foreach ($dossiers as $d) {
            if (DossierDiscovery::isNoindex($d)) {
                continue;
            }
            $slug = (string) ($d['slug'] ?? '');
            $key = 'default:' . $slug;
            if ($slug === '' || isset($seen[$key])) {
                continue;
            }
            $seen[$key] = true;
            $loc = $siteUrl . $slug . '/';
            $entries[] = [
                'loc' => $loc,
                'lastmod' => self::resolveLastmod($d),
                'slug' => $slug,
            ];
            $locsBySlug[$slug][$defaultLanguage] = $loc;
        }

        foreach ($localizedDossiersByLanguage as $language => $localizedDossiers) {
            $language = strtolower(trim((string) $language));
            if ($language === '' || !is_array($localizedDossiers)) {
                continue;
            }
            foreach ($localizedDossiers as $d) {
                if (!is_array($d) || DossierDiscovery::isNoindex($d)) {
                    continue;
                }
                $slug = (string) ($d['slug'] ?? '');
                $key = $language . ':' . $slug;
                if ($slug === '' || isset($seen[$key])) {
                    continue;
                }
                $seen[$key] = true;
                $loc = $siteUrl . rawurlencode($language) . '/' . $slug . '/';
                $entries[] = [
                    'loc' => $loc,
                    'lastmod' => self::resolveLastmod($d),
                    'slug' => $slug,
                ];
                $locsBySlug[$slug][$language] = $loc;
            }
        }

        $clusters = [];
        foreach ($locsBySlug as $slug => $langs) {
            if (count($langs) >= 2) {
                $clusters[$slug] = $langs;
            }
        }

        $xml = '<?xml version="1.0" encoding="UTF-8"?>' . "\n";
        if ($clusters !== []) {
            $xml .= '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
                . ' xmlns:xhtml="http://www.w3.org/1999/xhtml">' . "\n";
        } else {
            $xml .= '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' . "\n";
        }

        foreach ($entries as $entry) {
            $cluster = $clusters[$entry['slug']] ?? [];
            $xml .= self::urlEntry(
                $entry['loc'],
                $entry['lastmod'],
                $cluster,
                $defaultLanguage
            );
        }

        $xml .= "</urlset>\n";

        return $xml;
    }

    /**
     * @param array<string, string> $cluster language => loc
     */
    private static function urlEntry(
        string $loc,
        ?string $lastmod = null,
        array $cluster = [],
        string $defaultLanguage = 'en'
    ): string {
        $entry = '  <url>' . "\n";
        $entry .= '    <loc>' . self::esc($loc) . "</loc>\n";
        if ($lastmod !== null && $lastmod !== '') {
            $entry .= '    <lastmod>' . self::esc($lastmod) . "</lastmod>\n";
        }
        if (count($cluster) >= 2) {
            $langs = array_keys($cluster);
            usort(
                $langs,
                static function (string $a, string $b) use ($defaultLanguage): int {
                    if ($a === $defaultLanguage) {
                        return -1;
                    }
                    if ($b === $defaultLanguage) {
                        return 1;
                    }
                    return strcmp($a, $b);
                }
            );
            foreach ($langs as $lang) {
                $entry .= '    <xhtml:link rel="alternate" hreflang="'
                    . self::esc($lang)
                    . '" href="'
                    . self::esc($cluster[$lang])
                    . "\"/>\n";
            }
            if (isset($cluster[$defaultLanguage])) {
                $entry .= '    <xhtml:link rel="alternate" hreflang="x-default" href="'
                    . self::esc($cluster[$defaultLanguage])
                    . "\"/>\n";
            }
        }
        $entry .= "  </url>\n";

        return $entry;
    }

    /**
     * @param array<string, mixed> $dossier
     */
    private static function resolveLastmod(array $dossier): ?string
    {
        $raw = $dossier['updated'] ?? $dossier['date'] ?? null;
        if ($raw === null || $raw === '') {
            return null;
        }
        $ts = strtotime((string) $raw);
        if ($ts === false) {
            return null;
        }

        return gmdate('Y-m-d', $ts);
    }

    private static function esc(string $value): string
    {
        return htmlspecialchars($value, ENT_XML1 | ENT_QUOTES, 'UTF-8');
    }
}
