<?php

declare(strict_types=1);

namespace Dossier;

require_once __DIR__ . '/SiteRegistry.php';
require_once __DIR__ . '/InternalAPIClient.php';
require_once __DIR__ . '/ThemeEngine.php';

/**
 * Shared public-front bootstrap: Host → site_id (+ ?site= / pen_site_id fallback) + branding overlay.
 *
 * Blog entry points call PublicSiteContext::bootstrap() once.
 * Resolution: registry Host domain → ?site= → pen_site_id cookie → default.
 */
class PublicSiteContext
{
    public string $configPath;
    public string $siteId;
    /** @var array<string, mixed> */
    public array $ini;
    /** @var array{
     *   site_id: string,
     *   sitename: string,
     *   tagline: string,
     *   hero_title: string,
     *   hero_image: string,
     *   display_logo: bool,
     *   comments_enabled: bool,
     *   theme: string,
     *   content_relpath: string,
     *   title_template: string,
     *   meta_description: string,
     *   keywords: string,
     *   robots_index: bool,
     *   robots_follow: bool,
     *   robots_txt: string,
     *   sitemap_enabled: bool,
     *   google_site_verification: string,
     *   bing_site_verification: string,
     *   social_links: array,
     *   language: string,
     *   languages: list<string>,
     *   language_labels: array<string, string>,
     *   translation_automation_paused: bool,
     *   i18n_active: bool
     * } */
    public array $presentation;
    public SiteRegistry $registry;

    /**
     * @param array{
     *   site_id: string,
     *   sitename: string,
     *   tagline: string,
     *   hero_title: string,
     *   hero_image: string,
     *   display_logo: bool,
     *   comments_enabled: bool,
     *   theme: string,
     *   content_relpath: string,
     *   title_template: string,
     *   meta_description: string,
     *   keywords: string,
     *   robots_index: bool,
     *   robots_follow: bool,
     *   robots_txt: string,
     *   sitemap_enabled: bool,
     *   google_site_verification: string,
     *   bing_site_verification: string,
     *   social_links: array,
     *   language: string,
     *   languages: list<string>,
     *   language_labels: array<string, string>,
     *   translation_automation_paused: bool,
     *   i18n_active: bool
     * } $presentation
     * @param array<string, mixed> $ini
     */
    private function __construct(
        string $configPath,
        string $siteId,
        array $ini,
        array $presentation,
        SiteRegistry $registry
    ) {
        $this->configPath = $configPath;
        $this->siteId = $siteId;
        $this->ini = $ini;
        $this->presentation = $presentation;
        $this->registry = $registry;
    }

    public static function bootstrap(?string $configPath = null): self
    {
        $configPath = $configPath
            ?? dirname(__DIR__, 3) . '/backend-python/config.ini';
        $ini = parse_ini_file($configPath, true) ?: [];
        $registry = SiteRegistry::fromConfigPath($configPath);
        $siteId = $registry->resolveSiteIdFromRequest();
        $presentation = $registry->resolvePresentation($siteId, $ini);

        // Keep pen_site_id in sync so bare /favicon.ico (and similar) resolve to
        // the same site as this page — Host / ?site= / cookie stay aligned.
        if (!headers_sent()) {
            $current = isset($_COOKIE['pen_site_id'])
                ? strtolower(trim((string) $_COOKIE['pen_site_id']))
                : '';
            if ($current !== $siteId) {
                $isSecure = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off')
                    || (isset($_SERVER['SERVER_PORT']) && (int) $_SERVER['SERVER_PORT'] === 443)
                    || (isset($_SERVER['HTTP_X_FORWARDED_PROTO']) && $_SERVER['HTTP_X_FORWARDED_PROTO'] === 'https');
                setcookie('pen_site_id', $siteId, [
                    'expires' => time() + 604800,
                    'path' => '/',
                    'httponly' => false,
                    'samesite' => 'Lax',
                    'secure' => $isSecure,
                ]);
                $_COOKIE['pen_site_id'] = $siteId;
            }
        }

        return new self($configPath, $siteId, $ini, $presentation, $registry);
    }

    public function newApiClient(): InternalAPIClient
    {
        return new InternalAPIClient($this->siteId);
    }

    public function isI18nActive(): bool
    {
        return $this->presentation['i18n_active'];
    }

    public function newThemeEngine(bool $isStatic = false, string $staticWebRoot = ''): ThemeEngine
    {
        return ThemeEngine::fromConfig(
            $this->configPath,
            $isStatic,
            $staticWebRoot,
            $this->siteId,
            $this->presentation
        );
    }

    public function canonicalUrl(string $path): string
    {
        $path = '/' . ltrim($path, '/');
        $host = trim((string) ($_SERVER['HTTP_HOST'] ?? ''));
        if (
            $host === ''
            || preg_match('/^[a-z0-9.-]+(?::[0-9]{1,5})?$/i', $host) !== 1
        ) {
            return $path;
        }
        $forwarded = strtolower(trim(explode(
            ',',
            (string) ($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '')
        )[0]));
        $scheme = in_array($forwarded, ['http', 'https'], true)
            ? $forwarded
            : (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off'
                ? 'https'
                : 'http');
        return $scheme . '://' . $host . $path;
    }
}
