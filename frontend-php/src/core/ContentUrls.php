<?php

namespace Dossier;

require_once __DIR__ . '/PreviewUrl.php';

/**
 * Shared content/asset URL helpers for the MDX + wikilink pipeline.
 *
 * Single home for static URL state used by the MDX + wikilink pipeline:
 * - WikilinkProcessor (internal link hrefs)
 * - ComponentProcessor (media src resolution)
 * - ExpandResolver (Read more CTA)
 * - PostRenderer (img src rewrite, language)
 * - Blog entrypoints / generate-static.php (basePath wiring)
 */
class ContentUrls {
    public static $basePath = '/assets/';
    public static $linkLookup = [];
    private static $themeEngine = null;
    private static ?string $language = null;

    public static function setThemeEngine($engine) {
        self::$themeEngine = $engine;
    }

    public static function getThemeEngine() {
        return self::$themeEngine;
    }

    public static function setLanguage(?string $language): void {
        self::$language = $language !== null && trim($language) !== ''
            ? strtolower(str_replace('_', '-', trim($language)))
            : null;
    }

    public static function getLanguage(): ?string {
        return self::$language;
    }

    /**
     * Public content URL for an entry slug.
     * Dynamic preview: post.php?slug=… (+ ?site= when applicable).
     * Static build: {basePath}{slug}/
     */
    public static function resolveContentUrl(string $slug, ?string $section = null): string {
        $slug = trim($slug);
        if ($slug === '') {
            return '';
        }
        if (
            self::$themeEngine !== null
            && method_exists(self::$themeEngine, 'contentUrlForSlug')
        ) {
            return self::$themeEngine->contentUrlForSlug(
                $slug,
                $section,
                self::$language
            );
        }
        if (defined('STATIC_BUILD') && STATIC_BUILD) {
            return self::$basePath . $slug . '/';
        }
        $url = 'post.php?slug=' . urlencode($slug);
        if ($section !== null && $section !== '') {
            $url .= '&section=' . urlencode(strtolower(trim($section)));
        }
        $siteId = '';
        if (self::$themeEngine !== null && method_exists(self::$themeEngine, 'getSiteId')) {
            $siteId = (string) self::$themeEngine->getSiteId();
        }
        return PreviewUrl::appendPreviewSiteQuery($url, $siteId, false);
    }

    /**
     * Resolves an asset path based on the current context.
     */
    public static function resolveAsset($path) {
        if (empty($path)) return '';
        if (preg_match('~^https?://~', $path)) return $path;

        $cleanPath = ltrim($path, '/');
        if (str_starts_with($cleanPath, 'data:')) return $path;

        // Reject javascript: / vbscript: disguised as relative paths
        $noSpace = preg_replace('/[\s\x00-\x1F\x7F-\x9F]/u', '', (string) $cleanPath) ?? '';
        $lower = strtolower($noSpace);
        if (str_starts_with($lower, 'javascript:') || str_starts_with($lower, 'vbscript:')) {
            return '';
        }

        // Prefer ThemeEngine when available (site-scoped live URLs)
        if (self::$themeEngine !== null && method_exists(self::$themeEngine, 'contentAsset')) {
            return self::$themeEngine->contentAsset($cleanPath);
        }

        // Strip legacy 'assets/' prefix if it exists, as basePath already represents the assets root
        if (str_starts_with($cleanPath, 'assets/')) {
            $cleanPath = substr($cleanPath, 7);
        }

        // Strip API raw assets prefix if it exists
        if (str_starts_with($cleanPath, 'api/assets/raw/')) {
            $cleanPath = substr($cleanPath, 15);
        }

        // Strip sites/{id}/assets/ so joining basePath does not double the site segment
        if (preg_match('#^sites/[^/]+/assets/(.+)$#', $cleanPath, $m)) {
            $cleanPath = $m[1];
        }

        // If the base path ends with 'images/' and the path starts with 'images/', remove the redundancy
        if (str_ends_with(self::$basePath, 'images/') && str_starts_with($cleanPath, 'images/')) {
            $cleanPath = substr($cleanPath, 7);
        }

        return self::$basePath . $cleanPath;
    }
}
