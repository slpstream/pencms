<?php

namespace Dossier;

/**
 * Append ?site= / &site= to internal dynamic preview URLs so shared links and
 * cross-browser navigation keep Host→query→cookie resolution working.
 * Static builds stay query-free (Host / --site= already scopes them).
 */
class PreviewUrl
{
    /**
     * @param string $url      Relative or absolute URL
     * @param string $siteId   Active content site id
     * @param bool   $isStatic When true, return $url unchanged
     */
    public static function appendPreviewSiteQuery(string $url, string $siteId, bool $isStatic = false): string
    {
        if ($isStatic) {
            return $url;
        }
        if (defined('STATIC_BUILD') && STATIC_BUILD) {
            return $url;
        }

        $url = trim($url);
        $siteId = strtolower(trim($siteId));
        if ($url === '' || $siteId === '') {
            return $url;
        }

        // Fragments, schemes that are not navigable site paths
        if ($url[0] === '#' || preg_match('~^(?:javascript|mailto|tel|data):~i', $url)) {
            return $url;
        }

        // Absolute http(s) — external or dedicated-domain custom links; leave alone
        if (preg_match('~^https?://~i', $url)) {
            return $url;
        }

        // Protocol-relative
        if (str_starts_with($url, '//')) {
            return $url;
        }

        // Already has site=
        $parts = parse_url($url);
        if ($parts === false) {
            return $url;
        }
        if (!empty($parts['query'])) {
            parse_str($parts['query'], $query);
            if (isset($query['site']) && $query['site'] !== '') {
                return $url;
            }
        }

        $sep = str_contains($url, '?') ? '&' : '?';
        // Preserve fragment if present after query
        if (isset($parts['fragment'])) {
            $base = preg_replace('/#.*$/', '', $url);
            return $base . $sep . 'site=' . rawurlencode($siteId) . '#' . $parts['fragment'];
        }

        return $url . $sep . 'site=' . rawurlencode($siteId);
    }
}
