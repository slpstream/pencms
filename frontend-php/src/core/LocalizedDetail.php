<?php

declare(strict_types=1);

namespace Dossier;

/**
 * URL and request helpers for exact non-default-language detail pages.
 */
final class LocalizedDetail
{
    /**
     * @param array<string, mixed> $presentation
     * @return array{language: string, slug: string}|null
     */
    public static function matchPath(
        string $uri,
        string $publicBase,
        array $presentation
    ): ?array {
        if (empty($presentation['i18n_active'])) {
            return null;
        }

        $basePart = trim($publicBase, '/');
        $base = $basePart === '' ? '/' : '/' . $basePart . '/';
        $path = '/' . ltrim((string) (parse_url($uri, PHP_URL_PATH) ?? ''), '/');
        if (!str_starts_with($path, $base)) {
            return null;
        }

        $relative = trim(substr($path, strlen($base)), '/');
        $parts = $relative === '' ? [] : explode('/', $relative);
        if (count($parts) !== 2) {
            return null;
        }

        $language = self::normalizeLanguage(rawurldecode($parts[0]));
        $slug = rawurldecode($parts[1]);
        if (!self::isTranslatedLanguage($language, $presentation) || !self::validSlug($slug)) {
            return null;
        }

        return ['language' => $language, 'slug' => $slug];
    }

    /**
     * Resolve an optional language/lang query value.
     *
     * The default language maps to null so legacy query URLs retain their
     * existing unlocalized behavior.
     *
     * @param array<string, mixed> $presentation
     */
    public static function queryLanguage(array $query, array $presentation): ?string
    {
        $raw = $query['language'] ?? $query['lang'] ?? null;
        if ($raw === null || trim((string) $raw) === '') {
            return null;
        }

        $language = self::normalizeLanguage((string) $raw);
        $default = self::normalizeLanguage((string) ($presentation['language'] ?? 'en'));
        if ($language === $default) {
            return null;
        }

        return self::isTranslatedLanguage($language, $presentation)
            ? $language
            : null;
    }

    /**
     * @param array<string, mixed> $presentation
     */
    public static function hasLanguageQuery(array $query): bool
    {
        return array_key_exists('language', $query) || array_key_exists('lang', $query);
    }

    public static function publicPath(string $publicBase, string $language, string $slug): string
    {
        $base = trim($publicBase, '/');
        return '/' . ($base !== '' ? $base . '/' : '')
            . rawurlencode(self::normalizeLanguage($language)) . '/'
            . rawurlencode($slug) . '/';
    }

    public static function staticRelativeRoot(): string
    {
        return '../../';
    }

    /**
     * @param array<string, mixed> $presentation
     */
    private static function isTranslatedLanguage(string $language, array $presentation): bool
    {
        if ($language === '' || empty($presentation['i18n_active'])) {
            return false;
        }
        $default = self::normalizeLanguage((string) ($presentation['language'] ?? 'en'));
        $configured = array_map(
            static fn ($value): string => self::normalizeLanguage((string) $value),
            is_array($presentation['languages'] ?? null) ? $presentation['languages'] : []
        );
        return $language !== $default && in_array($language, $configured, true);
    }

    private static function normalizeLanguage(string $language): string
    {
        return strtolower(str_replace('_', '-', trim($language)));
    }

    private static function validSlug(string $slug): bool
    {
        return $slug !== ''
            && $slug !== '.'
            && $slug !== '..'
            && preg_match('/^[\p{L}\p{N}_-]+$/u', $slug) === 1;
    }
}
