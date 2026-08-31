<?php

declare(strict_types=1);

namespace Dossier;

if (is_file(__DIR__ . '/../../vendor/autoload.php')) {
    require_once __DIR__ . '/../../vendor/autoload.php';
}

/**
 * Read-only site registry (data/sites.yaml) for public Host → site routing.
 *
 * Mirrors Python services.site_service normalize_domain / resolve_site_id_by_host.
 *
 * YAML: Composer Symfony Yaml (autoload above) first, then ext-yaml
 * ``yaml_parse_file`` if the class is still missing. Admin editor includes
 * this file without going through PublicSiteContext, so autoload must live here.
 */
class SiteRegistry
{
    public const DEFAULT_SITE_ID = 'default';

    /** Default public relay origin when the site field is empty (bake/read time only). */
    public const DEFAULT_FEEDBACK_RELAY_URL = 'https://feedback.pencms.org';

    private string $registryPath;
    /** @var list<array<string, mixed>>|null */
    private ?array $sites = null;

    public function __construct(string $configPath)
    {
        $this->registryPath = dirname($configPath) . '/data/sites.yaml';
    }

    public static function fromConfigPath(string $configPath): self
    {
        return new self($configPath);
    }

    /**
     * Normalize a public hostname for registry matching.
     * Lowercase; strip scheme, path, port, trailing dot.
     */
    public static function normalizeHost(?string $raw): ?string
    {
        if ($raw === null) {
            return null;
        }
        $value = strtolower(trim($raw));
        if ($value === '') {
            return null;
        }
        if (str_contains($value, '://')) {
            $parts = explode('://', $value, 2);
            $value = $parts[1] ?? '';
        }
        $value = explode('/', $value, 2)[0];
        $value = explode('?', $value, 2)[0];
        $value = explode('#', $value, 2)[0];
        if (str_starts_with($value, '[')) {
            $end = strpos($value, ']');
            if ($end !== false) {
                $value = substr($value, 0, $end + 1);
            }
        } elseif (str_contains($value, ':')) {
            $value = explode(':', $value)[0];
        }
        $value = rtrim($value, '.');
        return $value !== '' ? $value : null;
    }

    /**
     * Map HTTP Host to site_id when a registry domain matches.
     * Returns null when Host is empty or does not match any site domain
     * (caller may fall back to ?site= / pen_site_id / default).
     */
    public function matchSiteIdFromHost(?string $host): ?string
    {
        $normalized = self::normalizeHost($host);
        if ($normalized === null) {
            return null;
        }
        foreach ($this->listSites() as $site) {
            $domain = self::normalizeHost(
                isset($site['domain']) ? (string) $site['domain'] : null
            );
            if ($domain !== null && $domain === $normalized) {
                $id = strtolower(trim((string) ($site['id'] ?? '')));
                return $id !== '' ? $id : self::DEFAULT_SITE_ID;
            }
        }
        return null;
    }

    /**
     * Map HTTP Host to site_id; unknown/empty → default.
     */
    public function resolveSiteIdFromHost(?string $host): string
    {
        return $this->matchSiteIdFromHost($host) ?? self::DEFAULT_SITE_ID;
    }

    /**
     * Resolve from current request: Host domain match → ?site= → pen_site_id cookie → default.
     *
     * Host remains authoritative when a registry domain matches. Query/cookie
     * only apply on shared Hosts (e.g. local preview with no per-site domains).
     */
    public function resolveSiteIdFromRequest(): string
    {
        $host = $_SERVER['HTTP_HOST'] ?? null;
        $fromHost = $this->matchSiteIdFromHost(is_string($host) ? $host : null);
        if ($fromHost !== null) {
            return $fromHost;
        }

        $fromQuery = $_GET['site'] ?? null;
        if (is_string($fromQuery)) {
            $qid = strtolower(trim($fromQuery));
            if ($qid !== '' && $this->getSite($qid) !== null) {
                return $qid;
            }
        }

        $fromCookie = $_COOKIE['pen_site_id'] ?? null;
        if (is_string($fromCookie)) {
            $cid = strtolower(trim($fromCookie));
            if ($cid !== '' && $this->getSite($cid) !== null) {
                return $cid;
            }
        }

        return self::DEFAULT_SITE_ID;
    }

    /**
     * @return array<string, mixed>|null
     */
    public function getSite(string $siteId): ?array
    {
        $sid = strtolower(trim($siteId));
        foreach ($this->listSites() as $site) {
            if (strtolower(trim((string) ($site['id'] ?? ''))) === $sid) {
                return $site;
            }
        }
        return null;
    }

    public function contentRelpath(string $siteId): string
    {
        $site = $this->getSite($siteId);
        if ($site !== null && !empty($site['content_relpath'])) {
            return rtrim((string) $site['content_relpath'], '/');
        }
        return 'sites/' . strtolower(trim($siteId) ?: self::DEFAULT_SITE_ID);
    }

    /**
     * Return safe per-site language defaults from the Python-owned registry.
     *
     * PHP intentionally does not perform semantic BCP-47 validation. It only
     * normalizes container/string shapes defensively and applies the shared
     * activation rule to values already validated by Python.
     *
     * @return array{
     *   language: string,
     *   languages: list<string>,
     *   language_labels: array<string, string>,
     *   translation_automation_paused: bool,
     *   i18n_active: bool
     * }
     */
    public function resolveI18nConfig(string $siteId): array
    {
        $language = 'en';
        $languages = [];
        $languageLabels = [];
        $automationPaused = false;

        $site = $this->getSite($siteId);
        if (is_array($site)) {
            if (isset($site['language']) && is_string($site['language']) && trim($site['language']) !== '') {
                $language = strtolower(trim($site['language']));
            }
            if (isset($site['languages']) && is_array($site['languages'])) {
                foreach ($site['languages'] as $tag) {
                    if (!is_string($tag) || trim($tag) === '') {
                        continue;
                    }
                    $normalized = strtolower(trim($tag));
                    if (!in_array($normalized, $languages, true)) {
                        $languages[] = $normalized;
                    }
                }
            }
            if (isset($site['language_labels']) && is_array($site['language_labels'])) {
                foreach ($site['language_labels'] as $tag => $label) {
                    if (!is_string($tag) || trim($tag) === '' || !is_string($label) || trim($label) === '') {
                        continue;
                    }
                    $languageLabels[strtolower(trim($tag))] = trim($label);
                }
            }
            if (array_key_exists('translation_automation_paused', $site)) {
                $automationPaused = filter_var(
                    $site['translation_automation_paused'],
                    FILTER_VALIDATE_BOOLEAN
                );
            }
        }

        return [
            'language' => $language,
            'languages' => $languages,
            'language_labels' => $languageLabels,
            'translation_automation_paused' => $automationPaused,
            'i18n_active' => count($languages) >= 2 && in_array($language, $languages, true),
        ];
    }

    public function isI18nActive(string $siteId): bool
    {
        return $this->resolveI18nConfig($siteId)['i18n_active'];
    }

    /**
     * Relay origin for bake/register. Empty site field → default origin. No trailing slash.
     */
    public static function resolveFeedbackRelayUrl(?string $raw): string
    {
        $text = $raw !== null ? trim($raw) : '';
        if ($text === '') {
            return self::DEFAULT_FEEDBACK_RELAY_URL;
        }
        return rtrim($text, '/');
    }

    /**
     * Baked form POST target: {resolved origin}/submit.
     */
    public static function resolveFeedbackSubmitEndpoint(?string $rawRelayUrl): string
    {
        return self::resolveFeedbackRelayUrl($rawRelayUrl) . '/submit';
    }

    /**
     * Twig vars for a static bake. Never includes feedback_fetch_token.
     *
     * @param array<string, mixed> $presentation
     * @return array<string, mixed>
     */
    public static function feedbackBakeContext(array $presentation): array
    {
        $key = trim((string) ($presentation['feedback_submission_key'] ?? ''));
        $fallbackRaw = strtolower(trim((string) ($presentation['feedback_static_fallback'] ?? '')));
        $fallback = $fallbackRaw === 'hidden' ? 'hidden' : 'mailto';
        if ($key === '') {
            return [
                'feedback_static_fallback' => $fallback,
            ];
        }
        $endpoint = trim((string) ($presentation['feedback_endpoint'] ?? ''));
        if ($endpoint === '') {
            $relay = null;
            if (
                array_key_exists('feedback_relay_url', $presentation)
                && $presentation['feedback_relay_url'] !== null
                && trim((string) $presentation['feedback_relay_url']) !== ''
            ) {
                $relay = (string) $presentation['feedback_relay_url'];
            }
            $endpoint = self::resolveFeedbackSubmitEndpoint($relay);
        }
        return [
            'feedback_endpoint' => $endpoint,
            'feedback_submission_key' => $key,
        ];
    }

    /**
     * Resolve public presentation for a site from the registry + install theme fallback.
     *
     * Text/branding come only from the site record (empty when unset).
     * Theme falls back to install [theme] active when site.theme is empty.
     *
     * @param array<string, mixed> $ini parse_ini_file(..., true) result
     * @return array{
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
     *   language: string,
     *   languages: list<string>,
     *   language_labels: array<string, string>,
     *   translation_automation_paused: bool,
     *   i18n_active: bool
     * }
     */
    public function resolvePresentation(string $siteId, array $ini): array
    {
        $themeBlock = $ini['theme'] ?? [];

        $sitename = '';
        $tagline = '';
        $heroTitle = '';
        $heroImage = '';
        $contactEmail = '';
        $titleTemplate = '';
        $metaDescription = '';
        $keywords = '';
        $robotsIndex = true;
        $robotsFollow = true;
        $robotsTxt = '';
        $sitemapEnabled = true;
        $googleSiteVerification = '';
        $bingSiteVerification = '';
        $indexNowEnabled = false;
        $indexNowKey = '';
        $feedbackRelayUrl = '';
        $feedbackSubmissionKey = '';
        $feedbackStaticFallback = '';
        $contentSignalAiTrain = false;
        $seoRedirects = [];
        $displayLogo = false;
        $commentsEnabled = false;
        $theme = (string) ($themeBlock['active'] ?? 'starter');
        $twitterCard = 'summary_large_image';
        $ogTitleFallback = '';
        $ogDescriptionFallback = '';
        $ogDefaultImage = '';
        $styleOverrides = null;
        $i18n = $this->resolveI18nConfig($siteId);

        $site = $this->getSite($siteId);
        if ($site !== null) {
            if (!empty($site['sitename'])) {
                $sitename = $this->stripQuotes((string) $site['sitename']);
            } elseif (!empty($site['name'])) {
                $sitename = $this->stripQuotes((string) $site['name']);
            }
            if (array_key_exists('tagline', $site) && $site['tagline'] !== null && $site['tagline'] !== '') {
                $tagline = $this->stripQuotes((string) $site['tagline']);
            }
            if (array_key_exists('hero_title', $site) && $site['hero_title'] !== null && $site['hero_title'] !== '') {
                $heroTitle = $this->stripQuotes((string) $site['hero_title']);
            }
            if (array_key_exists('hero_image', $site) && $site['hero_image'] !== null && $site['hero_image'] !== '') {
                $heroImage = $this->stripQuotes((string) $site['hero_image']);
            }
            if (array_key_exists('contact_email', $site) && $site['contact_email'] !== null && $site['contact_email'] !== '') {
                $contactEmail = $this->stripQuotes((string) $site['contact_email']);
            }
            if (array_key_exists('title_template', $site) && $site['title_template'] !== null && $site['title_template'] !== '') {
                $titleTemplate = $this->stripQuotes((string) $site['title_template']);
            }
            if (array_key_exists('meta_description', $site) && $site['meta_description'] !== null && $site['meta_description'] !== '') {
                $metaDescription = $this->stripQuotes((string) $site['meta_description']);
            }
            if (array_key_exists('keywords', $site) && $site['keywords'] !== null && $site['keywords'] !== '') {
                $keywords = $this->stripQuotes((string) $site['keywords']);
            }
            if (array_key_exists('robots_index', $site) && $site['robots_index'] !== null) {
                $robotsIndex = filter_var($site['robots_index'], FILTER_VALIDATE_BOOLEAN);
            }
            if (array_key_exists('robots_follow', $site) && $site['robots_follow'] !== null) {
                $robotsFollow = filter_var($site['robots_follow'], FILTER_VALIDATE_BOOLEAN);
            }
            if (array_key_exists('robots_txt', $site) && $site['robots_txt'] !== null && $site['robots_txt'] !== '') {
                $robotsTxt = $this->stripQuotes((string) $site['robots_txt']);
            }
            if (array_key_exists('sitemap_enabled', $site) && $site['sitemap_enabled'] !== null) {
                $sitemapEnabled = filter_var($site['sitemap_enabled'], FILTER_VALIDATE_BOOLEAN);
            }
            if (array_key_exists('google_site_verification', $site) && $site['google_site_verification'] !== null && $site['google_site_verification'] !== '') {
                $googleSiteVerification = $this->stripQuotes((string) $site['google_site_verification']);
            }
            if (array_key_exists('bing_site_verification', $site) && $site['bing_site_verification'] !== null && $site['bing_site_verification'] !== '') {
                $bingSiteVerification = $this->stripQuotes((string) $site['bing_site_verification']);
            }
            if (array_key_exists('indexnow_enabled', $site) && $site['indexnow_enabled'] !== null) {
                $indexNowEnabled = filter_var($site['indexnow_enabled'], FILTER_VALIDATE_BOOLEAN);
            }
            if (array_key_exists('indexnow_key', $site) && $site['indexnow_key'] !== null && $site['indexnow_key'] !== '') {
                $indexNowKey = $this->stripQuotes((string) $site['indexnow_key']);
            }
            if (array_key_exists('feedback_relay_url', $site) && $site['feedback_relay_url'] !== null && $site['feedback_relay_url'] !== '') {
                $feedbackRelayUrl = $this->stripQuotes((string) $site['feedback_relay_url']);
            }
            if (array_key_exists('feedback_submission_key', $site) && $site['feedback_submission_key'] !== null && $site['feedback_submission_key'] !== '') {
                $feedbackSubmissionKey = $this->stripQuotes((string) $site['feedback_submission_key']);
            }
            if (array_key_exists('feedback_static_fallback', $site) && $site['feedback_static_fallback'] !== null && $site['feedback_static_fallback'] !== '') {
                $feedbackStaticFallback = $this->stripQuotes((string) $site['feedback_static_fallback']);
            }
            if (array_key_exists('content_signal_ai_train', $site) && $site['content_signal_ai_train'] !== null) {
                $contentSignalAiTrain = filter_var($site['content_signal_ai_train'], FILTER_VALIDATE_BOOLEAN);
            }
            if (!empty($site['seo_redirects']) && is_array($site['seo_redirects'])) {
                $seoRedirects = $site['seo_redirects'];
            }
            if (array_key_exists('display_logo', $site) && $site['display_logo'] !== null) {
                $displayLogo = filter_var($site['display_logo'], FILTER_VALIDATE_BOOLEAN);
            }
            if (array_key_exists('comments_enabled', $site) && $site['comments_enabled'] !== null) {
                $commentsEnabled = filter_var($site['comments_enabled'], FILTER_VALIDATE_BOOLEAN);
            }
            if (!empty($site['theme'])) {
                $theme = (string) $site['theme'];
            }
            if (!empty($site['style_overrides']) && is_array($site['style_overrides']) && ($site['style_overrides']['theme'] ?? '') === $theme) {
                $styleOverrides = $site['style_overrides'];
            }
        }

        $social = $this->resolveSocialPreview($theme, is_array($site) ? $site : null);
        if (!empty($social['twitter_card'])) {
            $twitterCard = (string) $social['twitter_card'];
        }
        if (!empty($social['og_title_fallback'])) {
            $ogTitleFallback = (string) $social['og_title_fallback'];
        }
        if (!empty($social['og_description_fallback'])) {
            $ogDescriptionFallback = (string) $social['og_description_fallback'];
        }
        if (!empty($social['og_default_image'])) {
            $ogDefaultImage = (string) $social['og_default_image'];
        } elseif (!empty($social['og_default_hero'])) {
            // Prefer static share image; else generator hero as last-resort site image
            $hero = (string) $social['og_default_hero'];
            if (str_starts_with($hero, 'images/') || str_starts_with($hero, 'assets/')) {
                $ogDefaultImage = $hero;
            }
        }

        return [
            'site_id' => $siteId,
            'sitename' => $sitename,
            'tagline' => $tagline,
            'hero_title' => $heroTitle,
            'hero_image' => $heroImage,
            'contact_email' => $contactEmail,
            'display_logo' => $displayLogo,
            'comments_enabled' => $commentsEnabled,
            'theme' => $theme,
            'content_relpath' => $this->contentRelpath($siteId),
            'title_template' => $titleTemplate,
            'meta_description' => $metaDescription,
            'keywords' => $keywords,
            'robots_index' => $robotsIndex,
            'robots_follow' => $robotsFollow,
            'robots_txt' => $robotsTxt,
            'sitemap_enabled' => $sitemapEnabled,
            'google_site_verification' => $googleSiteVerification,
            'bing_site_verification' => $bingSiteVerification,
            'indexnow_enabled' => $indexNowEnabled,
            'indexnow_key' => $indexNowKey,
            'feedback_relay_url' => $feedbackRelayUrl,
            'feedback_submission_key' => $feedbackSubmissionKey,
            'feedback_static_fallback' => $feedbackStaticFallback,
            'content_signal_ai_train' => $contentSignalAiTrain,
            'seo_redirects' => $seoRedirects,
            'social_links' => (is_array($site) && isset($site['social_links']) && is_array($site['social_links'])) ? $site['social_links'] : [],
            'style_overrides' => $styleOverrides,
            'twitter_card' => $twitterCard,
            'og_title_fallback' => $ogTitleFallback,
            'og_description_fallback' => $ogDescriptionFallback,
            'og_default_image' => $ogDefaultImage,
            'language' => $i18n['language'],
            'languages' => $i18n['languages'],
            'language_labels' => $i18n['language_labels'],
            'translation_automation_paused' => $i18n['translation_automation_paused'],
            'i18n_active' => $i18n['i18n_active'],
        ];
    }

    /**
     * Merge engine ← theme social_preview ← site overrides (PHP mirror of Python).
     *
     * @param array<string, mixed>|null $site
     * @return array<string, mixed>
     */
    public function resolveSocialPreview(string $themeName, ?array $site): array
    {
        $engine = [
            'og_accent_color' => '#C12929',
            'og_vignette_color' => '#FF8000',
            'og_text_color' => '#FFFFFF',
            'og_bar_color' => '#000000',
            'og_font' => 'CourierPrime-Bold',
            'og_headline_style' => 'redacted',
            'og_text_case' => 'upper',
            'og_grade_preset' => 'noir',
            'og_accent_bar' => true,
            'og_watermark_enabled' => true,
            'og_watermark' => null,
            'og_watermark_source' => null,
            'og_watermark_layout' => 'full_canvas',
            'og_watermark_corner' => 'br',
            'og_watermark_scale' => 'md',
            'og_default_hero' => null,
            'og_default_image' => null,
            'og_fallback_title' => 'ARCHIVAL RECORD',
            'og_title_fallback' => null,
            'og_description_fallback' => null,
            'twitter_card' => 'summary_large_image',
        ];

        $themeBlock = $this->loadThemeSocialPreview($themeName);
        $merged = $engine;
        foreach ($themeBlock as $key => $val) {
            if ($key === 'og_fonts') {
                continue;
            }
            if ($val === null) {
                continue;
            }
            if (is_string($val) && trim($val) === '') {
                continue;
            }
            $merged[$key] = $val;
        }

        $stringKeys = [
            'og_accent_color', 'og_vignette_color', 'og_text_color', 'og_bar_color',
            'og_font', 'og_headline_style', 'og_text_case', 'og_grade_preset',
            'og_watermark', 'og_watermark_source', 'og_watermark_layout',
            'og_watermark_corner', 'og_watermark_scale',
            'og_default_hero', 'og_default_image',
            'og_fallback_title', 'og_title_fallback', 'og_description_fallback',
            'twitter_card',
        ];
        if (is_array($site)) {
            foreach ($stringKeys as $key) {
                if (!array_key_exists($key, $site) || $site[$key] === null) {
                    continue;
                }
                $text = trim((string) $site[$key]);
                if ($text === '') {
                    continue;
                }
                $merged[$key] = $this->stripQuotes($text);
            }
            if (array_key_exists('og_accent_bar', $site) && $site['og_accent_bar'] !== null) {
                $merged['og_accent_bar'] = filter_var($site['og_accent_bar'], FILTER_VALIDATE_BOOLEAN);
            }
            if (array_key_exists('og_watermark_enabled', $site) && $site['og_watermark_enabled'] !== null) {
                $merged['og_watermark_enabled'] = filter_var($site['og_watermark_enabled'], FILTER_VALIDATE_BOOLEAN);
            }
        }

        return $merged;
    }

    /**
     * @return array<string, mixed>
     */
    private function loadThemeSocialPreview(string $themeName): array
    {
        $name = trim($themeName) !== '' ? trim($themeName) : 'starter';
        // registryPath is {BASE_DIR}/data/sites.yaml → BASE_DIR is two levels up from the file
        $baseDir = dirname($this->registryPath, 2);
        $configPath = $baseDir . '/config.ini';
        $themesDir = '../frontend-php/src/blog/themes';
        if (is_file($configPath)) {
            $ini = parse_ini_file($configPath, true) ?: [];
            $themesDir = $ini['theme']['directory'] ?? $themesDir;
        }
        if (!str_starts_with($themesDir, '/')) {
            $themesRoot = $baseDir . '/' . $themesDir;
        } else {
            $themesRoot = $themesDir;
        }
        $path = rtrim($themesRoot, '/') . '/' . $name . '/theme.json';
        if (!is_file($path)) {
            return [];
        }
        $raw = @file_get_contents($path);
        if ($raw === false) {
            return [];
        }
        $data = json_decode($raw, true);
        if (!is_array($data) || !isset($data['social_preview']) || !is_array($data['social_preview'])) {
            return [];
        }
        return $data['social_preview'];
    }

    /**
     * @return list<array<string, mixed>>
     */
    public function listSites(): array
    {
        if ($this->sites !== null) {
            return $this->sites;
        }
        $this->sites = [];
        if (!is_file($this->registryPath)) {
            return $this->sites;
        }
        $decoded = null;
        try {
            if (class_exists('\Symfony\Component\Yaml\Yaml')) {
                $decoded = \Symfony\Component\Yaml\Yaml::parseFile($this->registryPath);
            } elseif (function_exists('yaml_parse_file')) {
                $decoded = @yaml_parse_file($this->registryPath);
            } else {
                error_log('PenCMS SiteRegistry: no YAML parser for ' . $this->registryPath);
            }
        } catch (\Throwable $e) {
            error_log('PenCMS SiteRegistry: failed to parse ' . $this->registryPath . ': ' . $e->getMessage());
            $decoded = null;
        }
        if (!is_array($decoded) || !isset($decoded['sites']) || !is_array($decoded['sites'])) {
            if ($decoded !== null) {
                error_log('PenCMS SiteRegistry: ' . $this->registryPath . ' has no sites list');
            }
            return $this->sites;
        }
        foreach ($decoded['sites'] as $site) {
            if (is_array($site) && !empty($site['id'])) {
                $this->sites[] = $site;
            }
        }
        return $this->sites;
    }

    private function stripQuotes(string $value): string
    {
        $value = trim($value);
        if (
            (str_starts_with($value, '"') && str_ends_with($value, '"'))
            || (str_starts_with($value, "'") && str_ends_with($value, "'"))
        ) {
            return substr($value, 1, -1);
        }
        return $value;
    }
}
