<?php

declare(strict_types=1);

namespace Dossier;

/**
 * Request and path helpers for localized generated list surfaces.
 */
final class LocalizedList
{
    /**
     * @param array<string, mixed> $presentation
     * @return array{language:string,surface:string,category:?string}|null
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
        $parts = $relative === '' ? [] : array_map('rawurldecode', explode('/', $relative));
        if ($parts === []) {
            return null;
        }

        $language = self::normalizeLanguage((string) array_shift($parts));
        if (!self::isTranslatedLanguage($language, $presentation)) {
            return null;
        }

        if ($parts === []) {
            return ['language' => $language, 'surface' => 'home', 'category' => null];
        }
        if ($parts === ['search']) {
            return ['language' => $language, 'surface' => 'search', 'category' => null];
        }
        if ($parts === ['category']) {
            return ['language' => $language, 'surface' => 'archive', 'category' => null];
        }
        if (
            count($parts) === 2
            && $parts[0] === 'category'
            && self::validCategorySlug((string) $parts[1])
        ) {
            return [
                'language' => $language,
                'surface' => 'archive',
                'category' => (string) $parts[1],
            ];
        }

        return null;
    }

    /**
     * Resolve an optional language/lang query without changing legacy defaults.
     *
     * @param array<string, mixed> $query
     * @param array<string, mixed> $presentation
     */
    public static function queryLanguage(array $query, array $presentation): ?string
    {
        $raw = $query['language'] ?? $query['lang'] ?? null;
        if ($raw === null || trim((string) $raw) === '') {
            return null;
        }
        $language = self::normalizeLanguage((string) $raw);
        return self::isTranslatedLanguage($language, $presentation)
            ? $language
            : null;
    }

    public static function publicPath(
        string $publicBase,
        string $language,
        string $surface,
        ?string $category = null
    ): string {
        $base = trim($publicBase, '/');
        $path = '/' . ($base !== '' ? $base . '/' : '')
            . rawurlencode(self::normalizeLanguage($language)) . '/';

        if ($surface === 'search') {
            return $path . 'search/';
        }
        if ($surface === 'archive') {
            $path .= 'category/';
            if ($category !== null && $category !== '') {
                $path .= rawurlencode($category) . '/';
            }
        }
        return $path;
    }

    public static function staticRelativeRoot(string $surface, ?string $category = null): string
    {
        if ($surface === 'home') {
            return '../';
        }
        if ($surface === 'archive' && $category !== null && $category !== '') {
            return '../../../';
        }
        return '../../';
    }

    /**
     * @param array<string, mixed> $presentation
     */
    private static function isTranslatedLanguage(
        string $language,
        array $presentation
    ): bool {
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

    private static function validCategorySlug(string $slug): bool
    {
        return $slug !== ''
            && $slug !== '.'
            && $slug !== '..'
            && preg_match('/^[\p{L}\p{N}_-]+$/u', $slug) === 1;
    }
}
