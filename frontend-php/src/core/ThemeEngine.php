<?php

declare(strict_types=1);

namespace Dossier;

require_once __DIR__ . '/SiteRegistry.php';
require_once __DIR__ . '/PreviewUrl.php';
require_once __DIR__ . '/TwigSandboxPolicy.php';
require_once __DIR__ . '/UiStrings.php';
require_once __DIR__ . '/CommentBody.php';
require_once __DIR__ . '/LocalizedDetail.php';
require_once __DIR__ . '/LocalizedList.php';
require_once __DIR__ . '/DossierDiscovery.php';

/**
 * ThemeEngine
 *
 * Centralizes all theme resolution, asset path math, and template loading.
 * Entry points (index.php, post.php, generate-static.php) should bootstrap
 * one instance of this class and never reference the filesystem directly.
 */
class ThemeEngine
{
    private ?string $cdnBase = null;
    private ?string $contentBaseUrl = null;
    private array $currentPageData = [];
    private string $currentTemplateName = '';
    private ?\Twig\Environment $twig = null;
    public ?string $configPath = null;
    private string $themeType = 'native';
    private array $authorProfile = [];
    private ?array $menuCache = null;
    /** @var array<string, array<string, array<string, mixed>>> */
    private array $exactLocalizedContentCache = [];
    private ?array $authorsCache = null;
    private string $siteId = 'default';
    private string $contentRelpath = 'sites/default';
    private string $contentDir = '';
    private string $defaultLanguage = 'en';
    /** @var list<string> */
    private array $activeLanguages = [];
    /** @var array<string, string> */
    private array $languageLabels = [];
    private bool $i18nActive = false;
    private string $renderLanguage = 'en';
    private bool $robotsIndex = true;
    private bool $robotsFollow = true;
    private string $googleSiteVerification = '';
    private string $bingSiteVerification = '';
    private string $twitterCard = 'summary_large_image';
    private string $ogTitleFallback = '';
    private string $ogDescriptionFallback = '';
    private string $ogDefaultImage = '';
    /** Absolute path when activeTheme is ``custom`` (site content tree). */
    public array $socialLinks = [];
    /** Site identity Index Hero Title (Settings → Site), not the page hero_title. */
    private string $indexHeroTitle = '';
    private ?string $themeDirOverride = null;
    /** Per-site style overrides loaded from the registry (null when none or theme mismatch). */
    private ?array $styleOverrides = null;
    /** Site contact email (Settings → Site), used by the feedback-form mailto fallback. */
    private string $contactEmail = '';
    /** Raw optional relay origin from presentation; empty means default at bake time. */
    private string $feedbackRelayUrl = '';
    /** Public 32-char hex queue routing key. Never the fetch token. */
    private string $feedbackSubmissionKey = '';
    /** Static missing-key fallback: mailto | hidden. */
    private string $feedbackStaticFallback = '';
    /** Pre-resolved bake POST URL ({origin}/submit); empty until static bake. */
    private string $feedbackEndpoint = '';
    /** Site Settings reader comments; missing/false means no thread or comment form. */
    private bool $commentsEnabled = false;

    private function __construct(
        private readonly string $themesRoot,   // e.g. /var/www/app/apps/blog/themes
        private readonly string $activeTheme,  // e.g. "starter"
        private readonly string $webRoot,      // e.g. "/blog/" (dynamic) or "../../" (static)
        private readonly bool   $isStatic,
        private readonly bool   $displayLogo,  // Toggle display site logo
    ) {}

    /**
     * Resolve absolute content directory from config.ini [Paths] content_dir.
     */
    private static function resolveContentDir(string $configPath, array $cfg): string
    {
        $appRoot = dirname($configPath);
        $contentDir = $cfg['Paths']['content_dir'] ?? '../pencms-data/content';
        if (strpos($contentDir, '/') !== 0) {
            $contentDir = $appRoot . '/' . $contentDir;
        }
        return rtrim($contentDir, '/');
    }

    /**
     * Primary factory method. Reads [theme] block from config.ini.
     *
     * Optional $siteId / $presentation apply per-site theme and display_logo
     * overrides (Host routing). When omitted, install-wide config is used and
     * menus load from sites/default.
     *
     * @param array{
     *   site_id?: string,
     *   theme?: string,
     *   display_logo?: bool,
     *   content_relpath?: string,
     *   robots_index?: bool,
     *   robots_follow?: bool,
     *   google_site_verification?: string,
     *   bing_site_verification?: string
     * }|null $presentation
     */
    public static function fromConfig(
        string $configPath,
        bool $isStatic = false,
        string $staticWebRoot = '',
        ?string $siteId = null,
        ?array $presentation = null
    ): self {
        if (!file_exists($configPath)) {
            throw new \RuntimeException("Config not found: {$configPath}");
        }

        $cfg = parse_ini_file($configPath, true);

        // PenCMS defaults
        $themesDir   = rtrim($cfg['theme']['directory'] ?? 'apps/blog/themes', '/');
        $activeTheme = $cfg['theme']['active']    ?? 'starter';
        $appRoot     = dirname($configPath);

        $themesRoot = $appRoot . '/' . $themesDir;

        // In PenCMS, the dynamic blog usually lives under /blog/
        $webRoot = $isStatic ? $staticWebRoot : ($cfg['theme']['web_root'] ?? '/blog/');
        $webRoot = rtrim($webRoot, '/') . '/';

        // Per-site only (presentation); never seed from install [General]
        $displayLogo = false;

        $resolvedSiteId = $siteId ?? SiteRegistry::DEFAULT_SITE_ID;
        $contentRelpath = 'sites/' . $resolvedSiteId;
        $robotsIndex = true;
        $robotsFollow = true;
        $googleSiteVerification = '';
        $bingSiteVerification = '';
        $twitterCard = 'summary_large_image';
        $ogTitleFallback = '';
        $ogDescriptionFallback = '';
        $ogDefaultImage = '';
        $defaultLanguage = 'en';
        $activeLanguages = [];
        $languageLabels = [];
        $i18nActive = false;
        if (is_array($presentation)) {
            if (!empty($presentation['theme'])) {
                $activeTheme = (string) $presentation['theme'];
            }
            if (array_key_exists('display_logo', $presentation) && $presentation['display_logo'] !== null) {
                $displayLogo = (bool) $presentation['display_logo'];
            }
            if (!empty($presentation['content_relpath'])) {
                $contentRelpath = rtrim((string) $presentation['content_relpath'], '/');
            }
            if (!empty($presentation['site_id'])) {
                $resolvedSiteId = (string) $presentation['site_id'];
            }
            if (array_key_exists('robots_index', $presentation) && $presentation['robots_index'] !== null) {
                $robotsIndex = (bool) $presentation['robots_index'];
            }
            if (array_key_exists('robots_follow', $presentation) && $presentation['robots_follow'] !== null) {
                $robotsFollow = (bool) $presentation['robots_follow'];
            }
            if (!empty($presentation['google_site_verification'])) {
                $googleSiteVerification = (string) $presentation['google_site_verification'];
            }
            if (!empty($presentation['bing_site_verification'])) {
                $bingSiteVerification = (string) $presentation['bing_site_verification'];
            }
            if (!empty($presentation['twitter_card'])) {
                $twitterCard = (string) $presentation['twitter_card'];
            }
            if (!empty($presentation['og_title_fallback'])) {
                $ogTitleFallback = (string) $presentation['og_title_fallback'];
            }
            if (!empty($presentation['og_description_fallback'])) {
                $ogDescriptionFallback = (string) $presentation['og_description_fallback'];
            }
            if (!empty($presentation['og_default_image'])) {
                $ogDefaultImage = (string) $presentation['og_default_image'];
            }
            if (!empty($presentation['language']) && is_string($presentation['language'])) {
                $defaultLanguage = self::normalizeLanguage($presentation['language']);
            }
            if (!empty($presentation['languages']) && is_array($presentation['languages'])) {
                foreach ($presentation['languages'] as $language) {
                    if (!is_string($language)) {
                        continue;
                    }
                    $language = self::normalizeLanguage($language);
                    if ($language !== '' && !in_array($language, $activeLanguages, true)) {
                        $activeLanguages[] = $language;
                    }
                }
            }
            if (!empty($presentation['language_labels']) && is_array($presentation['language_labels'])) {
                foreach ($presentation['language_labels'] as $language => $label) {
                    if (!is_string($language) || !is_string($label) || trim($label) === '') {
                        continue;
                    }
                    $language = self::normalizeLanguage($language);
                    if ($language !== '') {
                        $languageLabels[$language] = trim($label);
                    }
                }
            }
            $i18nActive = !empty($presentation['i18n_active']);
        }

        $themeDirOverride = null;
        if ($activeTheme === 'custom') {
            $contentDirAbs = self::resolveContentDir($configPath, $cfg ?: []);
            $themeDir = $contentDirAbs . '/' . $contentRelpath . '/theme';
            if (!is_dir($themeDir) || !is_file($themeDir . '/theme.json')) {
                throw new \RuntimeException(
                    "Site theme 'custom' is missing under content/{$contentRelpath}/theme/. "
                    . "Fork a base theme before setting presentation.theme to custom."
                );
            }
            $themeDirOverride = $themeDir;
        } else {
            $themeDir = $themesRoot . '/' . $activeTheme;
            if (!is_dir($themeDir) || !is_file($themeDir . '/theme.json')) {
                throw new \RuntimeException(
                    "Theme '{$activeTheme}' is not installed under themes/. "
                    . "Archived themes live under themes/_deprecated/. "
                    . "Set [theme] active or site presentation.theme to a keeper "
                    . "(starter, editorial, casper-lite)."
                );
            }
        }

        $instance = new self($themesRoot, $activeTheme, $webRoot, $isStatic, $displayLogo);
        $instance->configPath = $configPath;
        $instance->siteId = $resolvedSiteId;
        $instance->contentRelpath = $contentRelpath;
        $instance->contentDir = self::resolveContentDir($configPath, $cfg ?: []);
        $instance->defaultLanguage = $defaultLanguage !== '' ? $defaultLanguage : 'en';
        $instance->activeLanguages = $activeLanguages;
        $instance->languageLabels = $languageLabels;
        $instance->i18nActive = $i18nActive;
        $instance->renderLanguage = $instance->defaultLanguage;
        $instance->themeDirOverride = $themeDirOverride;
        $instance->robotsIndex = $robotsIndex;
        $instance->robotsFollow = $robotsFollow;
        $instance->googleSiteVerification = $googleSiteVerification;
        $instance->bingSiteVerification = $bingSiteVerification;
        $instance->twitterCard = $twitterCard;
        $instance->ogTitleFallback = $ogTitleFallback;
        $instance->ogDescriptionFallback = $ogDescriptionFallback;
        $instance->ogDefaultImage = $ogDefaultImage;
        if (is_array($presentation) && !empty($presentation['social_links']) && is_array($presentation['social_links'])) {
            $instance->socialLinks = $presentation['social_links'];
        }
        if (is_array($presentation) && !empty($presentation['hero_title']) && is_string($presentation['hero_title'])) {
            $instance->indexHeroTitle = trim($presentation['hero_title']);
        }
        if (is_array($presentation) && !empty($presentation['style_overrides']) && is_array($presentation['style_overrides'])) {
            $instance->styleOverrides = $presentation['style_overrides'];
        }
        if (is_array($presentation) && array_key_exists('contact_email', $presentation)) {
            $instance->contactEmail = trim((string) $presentation['contact_email']);
        }
        if (is_array($presentation) && array_key_exists('feedback_relay_url', $presentation) && $presentation['feedback_relay_url'] !== null) {
            $instance->feedbackRelayUrl = trim((string) $presentation['feedback_relay_url']);
        }
        if (is_array($presentation) && array_key_exists('feedback_submission_key', $presentation) && $presentation['feedback_submission_key'] !== null) {
            $instance->feedbackSubmissionKey = trim((string) $presentation['feedback_submission_key']);
        }
        if (is_array($presentation) && array_key_exists('feedback_static_fallback', $presentation) && $presentation['feedback_static_fallback'] !== null) {
            $instance->feedbackStaticFallback = trim((string) $presentation['feedback_static_fallback']);
        }
        if (is_array($presentation) && array_key_exists('feedback_endpoint', $presentation) && $presentation['feedback_endpoint'] !== null) {
            $instance->feedbackEndpoint = trim((string) $presentation['feedback_endpoint']);
        }
        if (is_array($presentation) && array_key_exists('comments_enabled', $presentation) && $presentation['comments_enabled'] !== null) {
            $instance->commentsEnabled = (bool) $presentation['comments_enabled'];
        }

                        if (!empty($cfg['theme']['cdn_base'])) {
            $instance->cdnBase = $cfg['theme']['cdn_base'];
        }

        $instance->initTwig($configPath);

        // Auto-register this theme engine in ShortcodeProcessor
        if (class_exists('Dossier\ShortcodeProcessor')) {
            ShortcodeProcessor::setThemeEngine($instance);
        }

        return $instance;
    }

    public function getSiteId(): string
    {
        return $this->siteId;
    }

    public function uiString(
        string $key,
        ?string $language = null,
        string $fallback = ''
    ): string {
        $candidate = $language !== null
            ? self::normalizeLanguage($language)
            : $this->renderLanguage;
        if (
            $candidate === ''
            || !$this->i18nActive
            || !in_array($candidate, $this->activeLanguages, true)
        ) {
            $candidate = $this->defaultLanguage;
        }
        $resolver = new UiStrings(
            __DIR__ . '/i18n/strings.json',
            $this->themeDir(),
            $this->contentDir . '/' . $this->contentRelpath,
            $this->defaultLanguage,
            $this->i18nActive,
        );
        $strings = $resolver->resolve($candidate);
        return isset($strings[$key]) && is_string($strings[$key])
            ? $strings[$key]
            : $fallback;
    }

    public function setContentBaseUrl(string $url): void
    {
        $this->contentBaseUrl = rtrim($url, '/') . '/';
    }

    /**
     * Render a named template with the provided page data.
     */
    public function render(string $templateName, array $pageData, ?string $key = null): string
    {
        $currentSlug = $pageData['slug'] ?? null;
        $requestedLanguage = isset($pageData['language']) && is_string($pageData['language'])
            ? $pageData['language']
            : null;
        $pageData['related_dossiers'] = $currentSlug !== null
            ? $this->getRelatedDossiers($currentSlug, $requestedLanguage)
            : [];

        // Baseline defaults for Twig strict_variables
        $pageData['slug'] = $currentSlug !== null ? (string) $currentSlug : '';
        $pageData['hero_title'] = $pageData['hero_title'] ?? ($pageData['title'] ?? '');
        $pageData['page_title'] = $pageData['page_title'] ?? ($pageData['hero_title'] !== '' ? $pageData['hero_title'] : ($pageData['sitename'] ?? ''));
        $pageData['tagline'] = $pageData['tagline'] ?? '';
        $pageData['meta_description'] = $pageData['meta_description'] ?? '';
        $pageData['canonical_url'] = $pageData['canonical_url'] ?? '';
        $pageData['is_composite'] = $pageData['is_composite'] ?? (isset($pageData['posts']) && is_array($pageData['posts']) && count($pageData['posts']) > 1);
        $pageData['comments'] = isset($pageData['comments']) && is_array($pageData['comments'])
            ? $pageData['comments']
            : [];
        $pageData['pen_site_id'] = $this->siteId !== ''
            ? $this->siteId
            : SiteRegistry::DEFAULT_SITE_ID;

        // Legacy shim: keep $asset_path and $base_path available
        $pageData['asset_path'] = $this->webRoot;
        $pageData['base_path'] = $this->webRoot;

        if ($templateName === 'post' && $key === null) {
            $key = isset($pageData['category']) ? strtolower(trim((string) $pageData['category'])) : null;
        }

        if ($key !== null) {
            $key = strtolower(trim((string) $key));
        }

        if (isset($pageData['category'])) {
            $pageData['category'] = strtolower(trim((string) $pageData['category']));
        } else {
            $pageData['category'] = $key !== null ? (string) $key : '';
        }

        $pageData = $this->withRenderContext($pageData);
        $this->currentPageData = $pageData;
        $this->currentTemplateName = $templateName;
        $pageData = $this->validateAndNormalise($pageData);

        // Inject the engine itself so templates can call $theme->asset(...)
        $pageData['theme'] = $this;

        $twigTpl = $this->resolveTwigTemplate($templateName, $key);
        if ($this->twig && $twigTpl) {
            try {
                $html = $this->twig->render($twigTpl, $pageData);
                return $this->injectHeadExtras($html);
            } catch (\Twig\Sandbox\SecurityError $e) {
                error_log("Twig Sandbox Security Violation: " . $e->getMessage());
                if (!$this->isStatic && !headers_sent()) {
                    http_response_code(500);
                }
                throw $e;
            }
        }

        $templatePath = $this->resolveTemplate($templateName, $key);
        ob_start();
        (static function (string $_tpl, array $_data): void {
            extract($_data, EXTR_SKIP);
            include $_tpl;
        })($templatePath, $pageData);

        $html = ob_get_clean() ?: '';
        return $this->injectHeadExtras($html);
    }

    /**
     * Absolute path to this site's assets/images directory (may not exist yet).
     */
    private function siteAssetsImagesDir(): ?string
    {
        $contentDir = $this->contentDir;
        if ($contentDir === '') {
            if (!$this->configPath || !file_exists($this->configPath)) {
                return null;
            }
            $cfg = parse_ini_file($this->configPath, true) ?: [];
            $contentDir = self::resolveContentDir($this->configPath, $cfg);
        }
        return $contentDir . '/' . $this->contentRelpath . '/assets/images';
    }

    /**
     * Live URL for a file under the active theme's assets/ folder.
     */
    private function themeAssetLiveUrl(string $relativePath): string
    {
        $relativePath = ltrim($relativePath, '/');
        if ($this->activeTheme === 'custom') {
            $siteId = $this->siteId !== '' ? $this->siteId : SiteRegistry::DEFAULT_SITE_ID;
            return '/api/assets/raw/sites/' . rawurlencode($siteId)
                . '/theme/assets/' . $relativePath;
        }
        return $this->webRoot . 'themes/' . $this->activeTheme . '/assets/' . $relativePath;
    }

    /**
     * Inject favicon + SEO indexing meta tags into <head> when missing.
     */
    private function injectHeadExtras(string $html): string
    {
        $html = $this->injectDocumentLanguage($html);
        $html = $this->injectCanonical($html);
        $html = $this->injectLanguageAlternates($html);
        $html = $this->injectOpenGraphLocale($html);
        $html = $this->injectArticleTimes($html);
        $html = $this->injectSeoMeta($html);
        $html = $this->injectJsonLd($html);
        $html = $this->injectQaMarkup($html);
        $html = $this->injectCommentsMarkup($html);
        $html = $this->injectLlmsAlternate($html);
        $html = $this->injectFavicon($html);
        return $this->injectStyleOverrides($html);
    }

    private function injectCanonical(string $html): string
    {
        $url = trim((string) ($this->currentPageData['canonical_url'] ?? ''));
        if (
            $url === ''
            || preg_match('/<head\b[^>]*>/i', $html) !== 1
            || preg_match('/<link\b[^>]*\brel\s*=\s*(["\'])canonical\1/i', $html)
        ) {
            return $html;
        }
        $tag = "\n    <link rel=\"canonical\" href=\""
            . htmlspecialchars($url, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8')
            . '">';
        return preg_replace('/(<head\b[^>]*>)/i', '$1' . $tag, $html, 1) ?? $html;
    }

    /**
     * Build active-i18n Twig context without changing registry presentation.
     *
     * @param array<string, mixed> $pageData
     * @return array<string, mixed>
     */
    private function withRenderContext(array $pageData): array
    {
        $requestedLanguage = isset($pageData['language']) && is_string($pageData['language'])
            ? self::normalizeLanguage($pageData['language'])
            : '';
        $currentLanguage = $this->defaultLanguage;
        if (
            $this->i18nActive
            && $requestedLanguage !== ''
            && in_array($requestedLanguage, $this->activeLanguages, true)
        ) {
            $currentLanguage = $requestedLanguage;
        }
        $this->renderLanguage = $currentLanguage;

        $resolver = new UiStrings(
            __DIR__ . '/i18n/strings.json',
            $this->themeDir(),
            $this->contentDir . '/' . $this->contentRelpath,
            $this->defaultLanguage,
            $this->i18nActive,
        );
        $pageData['strings'] = $resolver->resolve($currentLanguage);
        if (isset($pageData['reading_minutes']) && is_numeric($pageData['reading_minutes'])) {
            $pageData['reading_time'] = sprintf(
                (string) ($pageData['strings']['minuteRead'] ?? '%d min read'),
                (int) $pageData['reading_minutes']
            );
        }
        if (!empty($pageData['date'])) {
            $pageData['dateline'] = $this->localizedDate(
                (string) $pageData['date'],
                $currentLanguage
            );
        }
        $surface = isset($pageData['i18n_surface'])
            ? (string) $pageData['i18n_surface']
            : '';
        if ($surface === 'search') {
            $pageData['hero_title'] = $pageData['strings']['search'];
            if (!empty($pageData['sitename'])) {
                $pageData['page_title'] = $pageData['sitename']
                    . ' - ' . $pageData['strings']['search'];
            }
        } elseif (
            $surface === 'archive'
            && ($pageData['category'] ?? null) === 'archives'
        ) {
            $pageData['hero_title'] = $pageData['strings']['archives'];
            if (!empty($pageData['sitename'])) {
                $pageData['page_title'] = $pageData['sitename']
                    . ' - ' . $pageData['strings']['archives'];
            }
        }

        if ($this->i18nActive) {
            $site = isset($pageData['site']) && is_array($pageData['site'])
                ? $pageData['site']
                : [];
            $pageData['site'] = array_replace($site, [
                'id' => $this->siteId,
                'language' => $currentLanguage,
                'default_language' => $this->defaultLanguage,
                'languages' => $this->activeLanguages,
                'language_labels' => $this->languageLabels,
                'i18n_active' => true,
            ]);
            // Compatibility for themes that predated the `site` context.
            $pageData['site_language'] = $currentLanguage;
            $pageData['alternates'] = $this->resolveLanguageAlternates($pageData);
        }
        if (!array_key_exists('contact_email', $pageData)) {
            $pageData['contact_email'] = $this->contactEmail;
        }
        $pageData['comments_enabled'] = $this->commentsEnabled;
        if ($this->isStatic()) {
            $bake = SiteRegistry::feedbackBakeContext([
                'feedback_relay_url' => $this->feedbackRelayUrl,
                'feedback_submission_key' => $this->feedbackSubmissionKey,
                'feedback_static_fallback' => $this->feedbackStaticFallback,
                'feedback_endpoint' => $this->feedbackEndpoint,
            ]);
            foreach ($bake as $name => $value) {
                if (!array_key_exists($name, $pageData)) {
                    $pageData[$name] = $value;
                }
            }
        }
        return $pageData;
    }

    private function localizedDate(string $value, string $language): string
    {
        $timestamp = strtotime($value);
        if ($timestamp === false) {
            return $value;
        }
        if (class_exists('\IntlDateFormatter')) {
            $formatter = new \IntlDateFormatter(
                $language,
                \IntlDateFormatter::MEDIUM,
                \IntlDateFormatter::NONE,
                date_default_timezone_get()
            );
            $formatted = $formatter->format($timestamp);
            if (is_string($formatted) && $formatted !== '') {
                return $formatted;
            }
        }
        return date('F d, Y', $timestamp);
    }

    /**
     * Resolve exact published detail siblings through the existing API peer
     * relationship and URL helpers. This never performs its own discovery.
     *
     * @param array<string, mixed> $pageData
     * @return list<array{
     *   language: string,
     *   url: string,
     *   label: string,
     *   label_override: bool,
     *   current: bool
     * }>
     */
    private function resolveLanguageAlternates(array $pageData): array
    {
        if (
            !$this->i18nActive
            || !empty($pageData['i18n_surface'])
            || (array_key_exists('i18n_current_live', $pageData)
                && !$pageData['i18n_current_live'])
        ) {
            return [];
        }

        $slug = trim((string) ($pageData['slug'] ?? ''));
        $translations = $pageData['translations'] ?? null;
        if ($slug === '' || !is_array($translations)) {
            return [];
        }

        $visible = [$this->renderLanguage => true];
        foreach ($translations as $peer) {
            if (!is_array($peer)) {
                continue;
            }
            $language = isset($peer['language']) && is_string($peer['language'])
                ? self::normalizeLanguage($peer['language'])
                : '';
            if (
                $language === ''
                || !in_array($language, $this->activeLanguages, true)
                || ($peer['status'] ?? null) !== 'published'
                || empty($peer['published'])
            ) {
                continue;
            }
            $visible[$language] = true;
        }

        if (count($visible) < 2) {
            return [];
        }

        $alternates = [];
        $isPage = !empty($pageData['is_page']);
        foreach ($this->activeLanguages as $language) {
            if (empty($visible[$language])) {
                continue;
            }
            $hasOverride = isset($this->languageLabels[$language])
                && trim($this->languageLabels[$language]) !== '';
            $alternates[] = [
                'language' => $language,
                'url' => $this->contentUrl([
                    'slug' => $slug,
                    'page' => $isPage,
                    'language' => $language,
                    'is_fallback' => false,
                ], $language),
                'label' => $hasOverride
                    ? $this->languageLabels[$language]
                    : $language,
                'label_override' => $hasOverride,
                'current' => $language === $this->renderLanguage,
            ];
        }

        return count($alternates) >= 2 ? $alternates : [];
    }

    /**
     * Publish the same exact alternate set used by the optional switcher.
     */
    private function injectLanguageAlternates(string $html): string
    {
        $alternates = $this->currentPageData['alternates'] ?? null;
        if (
            !$this->i18nActive
            || !is_array($alternates)
            || count($alternates) < 2
            || !preg_match('/<head\b[^>]*>/i', $html)
        ) {
            return $html;
        }

        $tags = [];
        $defaultUrl = '';
        foreach ($alternates as $alternate) {
            if (!is_array($alternate)) {
                continue;
            }
            $language = (string) ($alternate['language'] ?? '');
            $url = (string) ($alternate['url'] ?? '');
            if ($language === '' || $url === '') {
                continue;
            }
            if ($language === $this->defaultLanguage) {
                $defaultUrl = $url;
            }
            if (preg_match(
                '/<link\b[^>]*\bhreflang\s*=\s*(["\'])'
                    . preg_quote($language, '/')
                    . '\1[^>]*>/i',
                $html
            )) {
                continue;
            }
            $tags[] = '    <link rel="alternate" hreflang="'
                . htmlspecialchars($language, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8')
                . '" href="'
                . htmlspecialchars($url, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8')
                . '">';
        }

        if (
            $defaultUrl !== ''
            && !preg_match(
                '/<link\b[^>]*\bhreflang\s*=\s*(["\'])x-default\1/i',
                $html
            )
        ) {
            $tags[] = '    <link rel="alternate" hreflang="x-default" href="'
                . htmlspecialchars($defaultUrl, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8')
                . '">';
        }

        if ($tags === []) {
            return $html;
        }

        $block = "\n" . implode("\n", $tags);
        return preg_replace(
            '/(<head\b[^>]*>)/i',
            '$1' . $block,
            $html,
            1
        ) ?? $html;
    }

    /**
     * Facebook OG locale tags. og:locale:alternate follows published
     * hreflang siblings only.
     */
    private function injectOpenGraphLocale(string $html): string
    {
        if (!preg_match('/<head\b[^>]*>/i', $html)) {
            return $html;
        }

        $tags = [];
        $current = self::ogLocaleFromLanguage($this->renderLanguage);
        if (
            $current !== ''
            && !preg_match('/property\s*=\s*(["\'])og:locale\1/i', $html)
        ) {
            $tags[] = '    <meta property="og:locale" content="'
                . htmlspecialchars($current, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8')
                . '">';
        }

        $alternates = $this->currentPageData['alternates'] ?? null;
        if (is_array($alternates)) {
            foreach ($alternates as $alternate) {
                if (!is_array($alternate)) {
                    continue;
                }
                $language = (string) ($alternate['language'] ?? '');
                if ($language === '' || $language === $this->renderLanguage) {
                    continue;
                }
                $locale = self::ogLocaleFromLanguage($language);
                if ($locale === '' || $locale === $current) {
                    continue;
                }
                $quoted = preg_quote($locale, '/');
                if (preg_match(
                    '/property\s*=\s*(["\'])og:locale:alternate\1[^>]*content\s*=\s*(["\'])'
                        . $quoted
                        . '\2/i',
                    $html
                )) {
                    continue;
                }
                $tags[] = '    <meta property="og:locale:alternate" content="'
                    . htmlspecialchars($locale, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8')
                    . '">';
            }
        }

        if ($tags === []) {
            return $html;
        }

        $block = "\n" . implode("\n", $tags);
        return preg_replace('/(<head\b[^>]*>)/i', '$1' . $block, $html, 1) ?? $html;
    }

    /**
     * article:published_time / article:modified_time on posts only.
     */
    private function injectArticleTimes(string $html): string
    {
        if (
            $this->currentTemplateName !== 'post'
            || !empty($this->currentPageData['is_page'])
            || !preg_match('/<head\b[^>]*>/i', $html)
        ) {
            return $html;
        }

        $published = $this->isoDateTime(
            isset($this->currentPageData['date'])
                ? (string) $this->currentPageData['date']
                : null
        );
        $modifiedRaw = $this->currentPageData['updated']
            ?? $this->currentPageData['modified_at']
            ?? $this->currentPageData['date']
            ?? null;
        $modified = $this->isoDateTime(
            $modifiedRaw !== null ? (string) $modifiedRaw : null
        );
        if ($modified === null) {
            $modified = $published;
        }

        $tags = [];
        if (
            $published !== null
            && !preg_match(
                '/property\s*=\s*(["\'])article:published_time\1/i',
                $html
            )
        ) {
            $tags[] = '    <meta property="article:published_time" content="'
                . htmlspecialchars($published, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8')
                . '">';
        }
        if (
            $modified !== null
            && !preg_match(
                '/property\s*=\s*(["\'])article:modified_time\1/i',
                $html
            )
        ) {
            $tags[] = '    <meta property="article:modified_time" content="'
                . htmlspecialchars($modified, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8')
                . '">';
        }

        if ($tags === []) {
            return $html;
        }

        $block = "\n" . implode("\n", $tags);
        return preg_replace('/(<head\b[^>]*>)/i', '$1' . $block, $html, 1) ?? $html;
    }

    /**
     * Convert a BCP 47 language tag to Facebook og:locale (en_US).
     */
    private static function ogLocaleFromLanguage(string $language): string
    {
        $normalized = strtolower(str_replace('_', '-', trim($language)));
        if ($normalized === '') {
            return 'en_US';
        }
        $parts = explode('-', $normalized);
        $primary = $parts[0];
        $region = $parts[1] ?? '';
        if ($primary !== '' && $region !== '') {
            return $primary . '_' . strtoupper($region);
        }

        $map = [
            'en' => 'en_US',
            'fr' => 'fr_FR',
            'de' => 'de_DE',
            'es' => 'es_ES',
            'pt' => 'pt_PT',
            'it' => 'it_IT',
            'nl' => 'nl_NL',
            'ja' => 'ja_JP',
            'zh' => 'zh_CN',
            'ko' => 'ko_KR',
            'ru' => 'ru_RU',
            'pl' => 'pl_PL',
            'sv' => 'sv_SE',
            'da' => 'da_DK',
            'fi' => 'fi_FI',
            'nb' => 'nb_NO',
            'nn' => 'nn_NO',
            'no' => 'nb_NO',
            'tr' => 'tr_TR',
            'ar' => 'ar_AR',
            'he' => 'he_IL',
            'cs' => 'cs_CZ',
            'hu' => 'hu_HU',
            'ro' => 'ro_RO',
            'uk' => 'uk_UA',
            'el' => 'el_GR',
            'id' => 'id_ID',
            'vi' => 'vi_VN',
            'th' => 'th_TH',
            'hi' => 'hi_IN',
            'ca' => 'ca_ES',
        ];
        if (isset($map[$primary])) {
            return $map[$primary];
        }
        if ($primary === '') {
            return 'en_US';
        }
        return $primary . '_' . strtoupper($primary);
    }

    private function isoDateTime(?string $raw): ?string
    {
        if ($raw === null) {
            return null;
        }
        $raw = trim($raw);
        if ($raw === '') {
            return null;
        }
        if (preg_match('/^\d{4}-\d{2}-\d{2}$/', $raw)) {
            return $raw . 'T00:00:00Z';
        }
        try {
            $dt = new \DateTimeImmutable($raw);
            return $dt->setTimezone(new \DateTimeZone('UTC'))->format('Y-m-d\TH:i:s\Z');
        } catch (\Exception $e) {
            return null;
        }
    }

    /**
     * Centrally correct the document language for every active theme.
     */
    private function injectDocumentLanguage(string $html): string
    {
        if (!$this->i18nActive || !preg_match('/<html\b[^>]*>/i', $html)) {
            return $html;
        }

        $language = htmlspecialchars(
            $this->renderLanguage,
            ENT_QUOTES | ENT_SUBSTITUTE,
            'UTF-8'
        );
        return preg_replace_callback(
            '/<html\b[^>]*>/i',
            static function (array $matches) use ($language): string {
                $opening = $matches[0];
                if (preg_match('/\slang\s*=\s*(["\']).*?\1/i', $opening)) {
                    return preg_replace(
                        '/\slang\s*=\s*(["\']).*?\1/i',
                        ' lang="' . $language . '"',
                        $opening,
                        1
                    ) ?? $opening;
                }
                return substr($opening, 0, -1) . ' lang="' . $language . '">';
            },
            $html,
            1
        ) ?? $html;
    }

    private static function normalizeLanguage(string $language): string
    {
        return strtolower(str_replace('_', '-', trim($language)));
    }

    /**
     * Inject robots + ownership verification meta tags when not already present.
     * Per-URL noindex (frontmatter or search surface) overrides the site default.
     */
    private function injectSeoMeta(string $html): string
    {
        if (!preg_match('/<head>/i', $html)) {
            return $html;
        }

        $tags = [];
        $pageNoindex = $this->pageForcesNoindex();
        $indexable = !$pageNoindex && $this->robotsIndex;
        $directive = ($indexable ? 'index' : 'noindex')
            . ','
            . ($pageNoindex || !$this->robotsFollow ? 'nofollow' : 'follow');
        if ($indexable) {
            $directive .= ',max-image-preview:large';
        }
        $robotsTag = '    <meta name="robots" content="'
            . htmlspecialchars($directive, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8')
            . '">';
        $hasRobots = (bool) preg_match('/<meta\s+[^>]*name=["\']robots["\']/i', $html);

        if ($pageNoindex && $hasRobots) {
            $html = preg_replace(
                '/<meta\s+[^>]*name=["\']robots["\'][^>]*>/i',
                trim($robotsTag),
                $html,
                1
            ) ?? $html;
        } elseif (!$hasRobots) {
            $tags[] = $robotsTag;
        }

        if (
            $this->googleSiteVerification !== ''
            && !preg_match('/<meta\s+[^>]*name=["\']google-site-verification["\']/i', $html)
        ) {
            $tags[] = '    <meta name="google-site-verification" content="'
                . htmlspecialchars($this->googleSiteVerification, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8')
                . '">';
        }

        if (
            $this->bingSiteVerification !== ''
            && !preg_match('/<meta\s+[^>]*name=["\']msvalidate\.01["\']/i', $html)
        ) {
            $tags[] = '    <meta name="msvalidate.01" content="'
                . htmlspecialchars($this->bingSiteVerification, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8')
                . '">';
        }

        if ($tags === []) {
            return $html;
        }

        $block = "\n" . implode("\n", $tags);
        return preg_replace('/(<head>)/i', '$1' . $block, $html, 1) ?? $html;
    }

    private function pageForcesNoindex(): bool
    {
        $surface = (string) ($this->currentPageData['i18n_surface'] ?? '');
        if ($surface === 'search') {
            return true;
        }
        return DossierDiscovery::isNoindex($this->currentPageData);
    }

    /**
     * Inject Schema.org JSON-LD for home, posts, and pages when missing.
     */
    private function injectJsonLd(string $html): string
    {
        if (
            preg_match('/<head\b[^>]*>/i', $html) !== 1
            || preg_match('/application\/ld\+json/i', $html)
        ) {
            return $html;
        }

        $canonical = trim((string) ($this->currentPageData['canonical_url'] ?? ''));
        if ($canonical === '') {
            return $html;
        }

        $template = $this->currentTemplateName;
        $isPage = !empty($this->currentPageData['is_page']);
        $bodyClass = (string) ($this->currentPageData['body_class'] ?? '');
        $isHome = $template === 'index'
            || ($bodyClass === 'page-front' && $template !== 'post' && $template !== 'page');

        $payloads = [];
        if ($isHome) {
            $payloads[] = $this->websiteJsonLd($canonical);
        } elseif ($isPage || $template === 'page') {
            $payloads[] = $this->webPageJsonLd($canonical);
            $payloads[] = $this->breadcrumbJsonLd($canonical);
            $faqPage = $this->faqPageJsonLd();
            if ($faqPage !== null) {
                $payloads[] = $faqPage;
            }
        } elseif ($template === 'post') {
            $payloads[] = $this->blogPostingJsonLd($canonical);
            $payloads[] = $this->breadcrumbJsonLd($canonical);
            $faqPage = $this->faqPageJsonLd();
            if ($faqPage !== null) {
                $payloads[] = $faqPage;
            }
        } else {
            return $html;
        }

        $block = '';
        foreach ($payloads as $payload) {
            $script = $this->jsonLdScriptTag($payload);
            if ($script !== '') {
                $block .= $script;
            }
        }
        if ($block === '') {
            return $html;
        }

        return preg_replace('/(<head\b[^>]*>)/i', '$1' . $block, $html, 1) ?? $html;
    }

    /**
     * Visible Q&A from frontmatter `faqs` when the list is non-empty.
     * Inserted before `</main>` (else `</body>`). Skip-if-present JSON-LD
     * does not suppress this chrome.
     */
    private function injectQaMarkup(string $html): string
    {
        if (!$this->qaSurfaceAllowsMarkup()) {
            return $html;
        }
        if (str_contains($html, 'class="pen-qa"') || str_contains($html, 'class=\'pen-qa\'') || str_contains($html, 'data-pen-qa')) {
            return $html;
        }
        $pairs = $this->normalizeFaqs($this->currentPageData['faqs'] ?? null);
        if ($pairs === []) {
            return $html;
        }
        $markup = $this->renderQaMarkup($pairs);
        if ($markup === '') {
            return $html;
        }
        if (preg_match('/<\/main\b/i', $html) === 1) {
            return preg_replace('/<\/main\b/i', $markup . '</main', $html, 1) ?? $html;
        }
        if (preg_match('/<\/body\b/i', $html) === 1) {
            return preg_replace('/<\/body\b/i', $markup . '</body', $html, 1) ?? $html;
        }
        return $html;
    }

    /**
     * Comment thread + comment form when Site Settings comments are on.
     * Skip-if-present: theme already emitted .pen-comments or a kind=comment form.
     * Posts only — never home, search, archive, or pages.
     */
    private function injectCommentsMarkup(string $html): string
    {
        if (!$this->commentsEnabled || !$this->commentSurfaceAllowsMarkup()) {
            return $html;
        }
        if ($this->htmlHasCommentChrome($html)) {
            return $html;
        }
        $markup = $this->renderCommentPairMarkup();
        if ($markup === '') {
            return $html;
        }
        if (preg_match('/<\/main\b/i', $html) === 1) {
            return preg_replace('/<\/main\b/i', $markup . '</main', $html, 1) ?? $html;
        }
        if (preg_match('/<\/article\b/i', $html) === 1) {
            return preg_replace('/<\/article\b/i', $markup . '</article', $html, 1) ?? $html;
        }
        if (preg_match('/<\/body\b/i', $html) === 1) {
            return preg_replace('/<\/body\b/i', $markup . '</body', $html, 1) ?? $html;
        }
        return $html;
    }

    private function commentSurfaceAllowsMarkup(): bool
    {
        return $this->currentTemplateName === 'post';
    }

    private function htmlHasCommentChrome(string $html): bool
    {
        if (
            str_contains($html, 'class="pen-comments"')
            || str_contains($html, "class='pen-comments'")
            || str_contains($html, 'data-pen-comments')
        ) {
            return true;
        }
        if (preg_match('/name\s*=\s*(["\'])kind\1[^>]*value\s*=\s*(["\'])comment\2/i', $html) === 1) {
            return true;
        }
        if (preg_match('/value\s*=\s*(["\'])comment\1[^>]*name\s*=\s*(["\'])kind\2/i', $html) === 1) {
            return true;
        }
        return false;
    }

    private function renderCommentPairMarkup(): string
    {
        if (
            $this->resolveTwigPartial('comment-thread') === null
            || $this->resolveTwigPartial('feedback-form') === null
        ) {
            return '';
        }
        $slug = (string) ($this->currentPageData['slug'] ?? '');
        $thread = $this->partial('comment-thread');
        $form = $this->partial('feedback-form', [
            'kind' => 'comment',
            'parent_slug' => $slug,
        ]);
        $combined = trim($thread . $form);
        if ($combined === '') {
            return '';
        }
        return "\n" . $combined . "\n";
    }

    /**
     * Q&A chrome belongs on post/page detail URLs only — never home, search, or archives.
     */
    private function qaSurfaceAllowsMarkup(): bool
    {
        $template = $this->currentTemplateName;
        if ($template === 'index' || $template === 'search' || $template === 'archive') {
            return false;
        }
        $bodyClass = (string) ($this->currentPageData['body_class'] ?? '');
        if ($bodyClass === 'page-front' && $template !== 'post' && $template !== 'page') {
            return false;
        }
        return $template === 'post'
            || $template === 'page'
            || !empty($this->currentPageData['is_page']);
    }

    /**
     * Theme chrome for the Q&A block: "faq" (default) or "backgrounder".
     * Same `faqs` list either way; schema stays FAQPage.
     */
    private function qaHeadingVariant(): string
    {
        $raw = $this->manifest()['qa_heading'] ?? 'faq';
        $token = is_string($raw) ? strtolower(trim($raw)) : '';
        return $token === 'backgrounder' ? 'backgrounder' : 'faq';
    }

    /**
     * Visible heading for `.pen-qa`. Words come from i18n; the variant is theme.json.
     */
    private function qaHeadingLabel(): string
    {
        $variant = $this->qaHeadingVariant();
        $fallback = $variant === 'backgrounder' ? 'Backgrounder' : 'FAQ';
        $strings = $this->currentPageData['strings'] ?? [];
        $fromPage = is_array($strings) ? ($strings[$variant] ?? null) : null;
        if (is_string($fromPage) && trim($fromPage) !== '') {
            return $fromPage;
        }
        return $this->uiString($variant, null, $fallback);
    }

    /**
     * @param list<array{q: string, a: string}> $pairs
     */
    private function renderQaMarkup(array $pairs): string
    {
        $heading = $this->qaHeadingLabel();
        if ($this->twig !== null) {
            try {
                $twigTpl = $this->resolveTwigPartial('faqs') ?? '@pencms/_faqs.html.twig';
                $html = $this->twig->render($twigTpl, [
                    'faqs' => $pairs,
                    'heading' => $heading,
                ]);
                if (is_string($html) && trim($html) !== '') {
                    return "\n" . trim($html) . "\n";
                }
            } catch (\Throwable $e) {
                // Fall through to the PHP markup so a missing Twig path never hides Q&A.
            }
        }
        return $this->qaMarkupHtml($pairs, $heading);
    }

    /**
     * Inline structure CSS for Q&A markup (keep in sync with `core/partials/_faqs.html.twig`).
     */
    private function qaMarkupInlineStyles(): string
    {
        return <<<'HTML'
  <style>
    /* Structure + pair spacing — themes style .pen-qa / .pen-qa-heading / dt|dd in CSS (see theme-dev docs). */
    .pen-qa {
      font: inherit;
      --pen-qa-pair-gap: 1.25rem;
      --pen-qa-heading-weight: 700;
    }
    section.pen-qa[data-pen-qa] > .pen-qa-heading {
      font-weight: var(--pen-qa-heading-weight);
    }
    section.pen-qa[data-pen-qa] > dl {
      display: flex;
      flex-direction: column;
      gap: 0;
      margin: 0;
      padding: 0;
    }
    section.pen-qa[data-pen-qa] > dl > dt,
    section.pen-qa[data-pen-qa] > dl > dd {
      margin: 0;
    }
    section.pen-qa[data-pen-qa] > dl > dd {
      margin-top: 0.25rem;
      margin-bottom: var(--pen-qa-pair-gap);
    }
    section.pen-qa[data-pen-qa] > dl > dd:last-child {
      margin-bottom: 0;
    }
  </style>
HTML;
    }

    /**
     * Theme-agnostic Q&A markup matching `core/partials/_faqs.html.twig`.
     *
     * @param list<array{q: string, a: string}> $pairs
     */
    private function qaMarkupHtml(array $pairs, string $heading): string
    {
        $lines = [
            '',
            '<section class="pen-qa" data-pen-qa>',
            $this->qaMarkupInlineStyles(),
            '  <h2 class="pen-qa-heading">'
                . htmlspecialchars($heading, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8')
                . '</h2>',
            '  <dl>',
        ];
        foreach ($pairs as $item) {
            $lines[] = '    <dt>'
                . htmlspecialchars($item['q'], ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8')
                . '</dt>';
            $lines[] = '    <dd>'
                . htmlspecialchars($item['a'], ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8')
                . '</dd>';
        }
        $lines[] = '  </dl>';
        $lines[] = '</section>';
        $lines[] = '';
        return implode("\n", $lines);
    }

    /**
     * FAQPage JSON-LD from the same normalized pairs as the visible HTML.
     * Empty / missing list → null (do not emit).
     *
     * @return array<string, mixed>|null
     */
    private function faqPageJsonLd(): ?array
    {
        $pairs = $this->normalizeFaqs($this->currentPageData['faqs'] ?? null);
        if ($pairs === []) {
            return null;
        }
        $entities = [];
        foreach ($pairs as $item) {
            $entities[] = [
                '@type' => 'Question',
                'name' => $item['q'],
                'acceptedAnswer' => [
                    '@type' => 'Answer',
                    'text' => $item['a'],
                ],
            ];
        }
        return [
            '@context' => 'https://schema.org',
            '@type' => 'FAQPage',
            'mainEntity' => $entities,
        ];
    }

    /**
     * @return list<array{q: string, a: string}>
     */
    private function normalizeFaqs(mixed $raw): array
    {
        if (!is_array($raw)) {
            return [];
        }
        $out = [];
        foreach ($raw as $item) {
            if (!is_array($item)) {
                continue;
            }
            $q = trim((string) ($item['q'] ?? ''));
            $a = trim((string) ($item['a'] ?? ''));
            if ($q === '' || $a === '') {
                continue;
            }
            $out[] = ['q' => $q, 'a' => $a];
        }
        return $out;
    }

    /**
     * Advertise the published-site llmstxt.org index when a public origin is known.
     */
    private function injectLlmsAlternate(string $html): string
    {
        if (preg_match('/<head\b[^>]*>/i', $html) !== 1) {
            return $html;
        }
        if (
            preg_match('/rel\s*=\s*(["\'])alternate\1[^>]*(?:type\s*=\s*(["\'])text\/plain\2[^>]*)?href\s*=\s*(["\'])[^\'"]*llms\.txt\3/i', $html)
            || preg_match('/href\s*=\s*(["\'])[^\'"]*llms\.txt\1[^>]*rel\s*=\s*(["\'])alternate\2/i', $html)
        ) {
            return $html;
        }

        $origin = $this->publicSiteOrigin();
        if ($origin === '') {
            return $html;
        }

        $tag = "\n    <link rel=\"alternate\" type=\"text/plain\" href=\""
            . htmlspecialchars($origin . 'llms.txt', ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8')
            . '" title="LLM index">';
        return preg_replace('/(<head\b[^>]*>)/i', '$1' . $tag, $html, 1) ?? $html;
    }

    /**
     * @return array<string, mixed>
     */
    private function websiteJsonLd(string $canonical): array
    {
        $sitename = $this->jsonLdSiteName();
        $origin = $this->publicSiteOrigin();
        $url = $origin !== '' ? $origin : $canonical;
        $data = [
            '@context' => 'https://schema.org',
            '@type' => 'WebSite',
            'name' => $sitename !== '' ? $sitename : $this->jsonLdHeadline(),
            'url' => $url,
        ];
        $description = $this->jsonLdDescription(true);
        if ($description !== null) {
            $data['description'] = $description;
        }
        $inLanguage = $this->jsonLdInLanguage();
        if ($inLanguage !== null) {
            $data['inLanguage'] = $inLanguage;
        }
        $searchAction = $this->websiteSearchAction($origin);
        if ($searchAction !== null) {
            $data['potentialAction'] = $searchAction;
        }
        $data['publisher'] = $this->organizationJsonLd($origin, $data['name']);
        return $data;
    }

    /**
     * @return array<string, mixed>
     */
    private function blogPostingJsonLd(string $canonical): array
    {
        $sitename = $this->jsonLdSiteName();
        $origin = $this->publicSiteOrigin();
        $headline = $this->jsonLdHeadline();
        $data = [
            '@context' => 'https://schema.org',
            '@type' => 'BlogPosting',
            'headline' => $headline,
            'url' => $canonical,
            'mainEntityOfPage' => $canonical,
        ];
        $description = $this->jsonLdDescription(false);
        if ($description !== null) {
            $data['description'] = $description;
        }
        $published = $this->jsonLdDatePublished();
        if ($published !== null) {
            $data['datePublished'] = $published;
        }
        $modified = $this->jsonLdDateModified();
        if ($modified !== null) {
            $data['dateModified'] = $modified;
        }
        $inLanguage = $this->jsonLdInLanguage();
        if ($inLanguage !== null) {
            $data['inLanguage'] = $inLanguage;
        }
        $image = $this->jsonLdImageUrl($origin);
        if ($image !== null) {
            $data['image'] = $image;
        }
        $author = $this->jsonLdAuthor();
        if ($author !== null) {
            $data['author'] = $author;
        }
        $keywords = $this->jsonLdKeywords();
        if ($keywords !== null) {
            $data['keywords'] = $keywords;
        }
        $publisherName = $sitename !== '' ? $sitename : $headline;
        $data['publisher'] = $this->organizationJsonLd($origin, $publisherName);
        return $data;
    }

    /**
     * @return array<string, mixed>
     */
    private function webPageJsonLd(string $canonical): array
    {
        $sitename = $this->jsonLdSiteName();
        $origin = $this->publicSiteOrigin();
        $headline = $this->jsonLdHeadline();
        $data = [
            '@context' => 'https://schema.org',
            '@type' => 'WebPage',
            'name' => $headline,
            'url' => $canonical,
        ];
        $description = $this->jsonLdDescription(false);
        if ($description !== null) {
            $data['description'] = $description;
        }
        $inLanguage = $this->jsonLdInLanguage();
        if ($inLanguage !== null) {
            $data['inLanguage'] = $inLanguage;
        }
        $publisherName = $sitename !== '' ? $sitename : $headline;
        $data['publisher'] = $this->organizationJsonLd($origin, $publisherName);
        return $data;
    }

    /**
     * @return array<string, mixed>
     */
    private function breadcrumbJsonLd(string $canonical): array
    {
        $sitename = $this->jsonLdSiteName();
        $origin = $this->publicSiteOrigin();
        $homeUrl = $origin !== '' ? $origin : $canonical;
        $headline = $this->jsonLdHeadline();
        return [
            '@context' => 'https://schema.org',
            '@type' => 'BreadcrumbList',
            'itemListElement' => [
                [
                    '@type' => 'ListItem',
                    'position' => 1,
                    'name' => $sitename !== '' ? $sitename : 'Home',
                    'item' => $homeUrl,
                ],
                [
                    '@type' => 'ListItem',
                    'position' => 2,
                    'name' => $headline !== '' ? $headline : $canonical,
                    'item' => $canonical,
                ],
            ],
        ];
    }

    /**
     * @return array<string, mixed>
     */
    private function organizationJsonLd(string $origin, string $name): array
    {
        $org = [
            '@type' => 'Organization',
            'name' => $name,
        ];
        if ($origin !== '') {
            $org['url'] = $origin;
        }
        $logo = $this->absoluteLogoUrl($origin);
        if ($logo !== null) {
            $org['logo'] = $logo;
        }
        $sameAs = [];
        foreach ($this->socialLinks as $link) {
            if (!is_array($link)) {
                continue;
            }
            $url = trim((string) ($link['url'] ?? ''));
            if ($url !== '') {
                $sameAs[] = $url;
            }
        }
        if ($sameAs !== []) {
            $org['sameAs'] = array_values(array_unique($sameAs));
        }
        return $org;
    }

    private function jsonLdScriptTag(array $data): string
    {
        $json = json_encode($data, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
        if (!is_string($json) || $json === '') {
            return '';
        }
        $json = str_replace('<', '\u003c', $json);
        return "\n    <script type=\"application/ld+json\">" . $json . '</script>';
    }

    private function publicSiteOrigin(): string
    {
        $candidates = [
            trim((string) ($this->currentPageData['site_url'] ?? '')),
            trim((string) ($this->currentPageData['canonical_url'] ?? '')),
        ];
        foreach ($candidates as $url) {
            if (!preg_match('#^https?://#i', $url)) {
                continue;
            }
            $parts = parse_url($url);
            if (!is_array($parts) || empty($parts['scheme']) || empty($parts['host'])) {
                continue;
            }
            $origin = $parts['scheme'] . '://' . $parts['host'];
            if (!empty($parts['port'])) {
                $origin .= ':' . $parts['port'];
            }
            return $origin . '/';
        }
        return '';
    }

    private function jsonLdSiteName(): string
    {
        return trim((string) ($this->currentPageData['sitename'] ?? ''));
    }

    private function jsonLdHeadline(): string
    {
        foreach (['hero_title', 'page_title', 'sitename'] as $key) {
            $value = trim((string) ($this->currentPageData[$key] ?? ''));
            if ($value !== '') {
                return $value;
            }
        }
        return '';
    }

    private function jsonLdDescription(bool $isHome): ?string
    {
        if ($isHome) {
            $text = trim((string) ($this->currentPageData['tagline'] ?? ''));
            if ($text === '') {
                $text = trim((string) ($this->currentPageData['meta_description'] ?? ''));
            }
        } else {
            $text = trim(strip_tags((string) ($this->currentPageData['deck'] ?? '')));
            if ($text === '') {
                $text = trim((string) ($this->currentPageData['meta_description'] ?? ''));
            }
            if ($text === '') {
                $seo = $this->currentPageData['seo'] ?? [];
                $text = trim((string) ($this->currentPageData['og_description']
                    ?? ((is_array($seo) ? ($seo['og_description'] ?? '') : ''))));
            }
        }
        $text = trim((string) preg_replace('/\s+/u', ' ', $text));
        return $text !== '' ? $text : null;
    }

    private function jsonLdDatePublished(): ?string
    {
        $date = $this->currentPageData['date'] ?? null;
        if ($date === null || $date === '') {
            return null;
        }
        return $this->isoDateTime((string) $date);
    }

    private function jsonLdDateModified(): ?string
    {
        $modifiedRaw = $this->currentPageData['updated']
            ?? $this->currentPageData['modified_at']
            ?? $this->currentPageData['date']
            ?? null;
        $modified = $this->isoDateTime(
            $modifiedRaw !== null ? (string) $modifiedRaw : null
        );
        if ($modified !== null) {
            return $modified;
        }
        return $this->jsonLdDatePublished();
    }

    private function jsonLdInLanguage(): ?string
    {
        $language = self::normalizeLanguage($this->renderLanguage);
        return $language !== '' ? $language : null;
    }

    /**
     * @return array<string, mixed>|null
     */
    private function websiteSearchAction(string $origin): ?array
    {
        if ($origin === '') {
            return null;
        }
        $path = 'search/?q={search_term_string}';
        if (
            $this->i18nActive
            && $this->renderLanguage !== ''
            && $this->renderLanguage !== $this->defaultLanguage
        ) {
            $path = rawurlencode($this->renderLanguage) . '/' . $path;
        }
        return [
            '@type' => 'SearchAction',
            'target' => [
                '@type' => 'EntryPoint',
                'urlTemplate' => $origin . $path,
            ],
            'query-input' => 'required name=search_term_string',
        ];
    }

    private function jsonLdAuthor(): ?array
    {
        $byline = trim((string) ($this->currentPageData['author'] ?? ''));
        if ($byline === '') {
            return null;
        }
        $name = $byline;
        $matched = null;
        foreach ($this->getSiteAuthors() as $author) {
            $slug = (string) ($author['slug'] ?? '');
            $authorName = (string) ($author['name'] ?? '');
            if (strcasecmp($slug, $byline) === 0 || strcasecmp($authorName, $byline) === 0) {
                $matched = $author;
                if ($authorName !== '') {
                    $name = $authorName;
                }
                break;
            }
        }
        $person = [
            '@type' => 'Person',
            'name' => $name,
        ];
        if (!is_array($matched)) {
            return $person;
        }
        $website = trim((string) ($matched['website'] ?? ''));
        if (preg_match('#^https?://#i', $website) === 1) {
            $person['url'] = $website;
        }
        $bio = trim((string) ($matched['bio'] ?? ''));
        if ($bio !== '') {
            $person['description'] = $bio;
        }
        $role = trim((string) ($matched['role'] ?? ''));
        if ($role !== '') {
            $person['jobTitle'] = $role;
        }
        $avatar = $matched['avatar'] ?? null;
        $image = $this->jsonLdAuthorImage(is_string($avatar) ? $avatar : null);
        if ($image !== null) {
            $person['image'] = $image;
        }
        return $person;
    }

    private function jsonLdAuthorImage(?string $avatar): ?string
    {
        $avatar = trim((string) $avatar);
        if ($avatar === '' || str_starts_with($avatar, 'data:') || str_starts_with($avatar, '//')) {
            return null;
        }
        if (str_starts_with($avatar, '/api/') || str_starts_with($avatar, 'api/')) {
            return null;
        }
        $absolute = $this->absolutizePublicUrl($avatar, $this->publicSiteOrigin());
        if ($absolute === null || preg_match('#^https?://#i', $absolute) !== 1) {
            return null;
        }
        return $absolute;
    }

    private function jsonLdKeywords(): ?string
    {
        $tags = $this->currentPageData['tags'] ?? null;
        if (is_array($tags) && $tags !== []) {
            $labels = [];
            foreach ($tags as $tag) {
                if (is_string($tag) && trim($tag) !== '') {
                    $labels[] = trim($tag);
                } elseif (is_array($tag) && !empty($tag['label'])) {
                    $labels[] = trim((string) $tag['label']);
                }
            }
            if ($labels !== []) {
                return implode(', ', $labels);
            }
        }
        $keywords = trim((string) ($this->currentPageData['keywords'] ?? ''));
        return $keywords !== '' ? $keywords : null;
    }

    private function jsonLdImageUrl(string $origin): ?string
    {
        $seo = $this->currentPageData['seo'] ?? [];
        $image = $this->currentPageData['og_image']
            ?? (is_array($seo) ? ($seo['og_image'] ?? null) : null);
        if (is_string($image) && trim($image) !== '') {
            $absolute = $this->absolutizePublicUrl(trim($image), $origin);
            if ($absolute !== null) {
                return $absolute;
            }
        }
        $slug = trim((string) ($this->currentPageData['slug'] ?? ''));
        if ($origin !== '' && $slug !== '') {
            return rtrim($origin, '/') . '/images/og/' . $slug . '.jpg';
        }
        return null;
    }

    private function absoluteLogoUrl(string $origin): ?string
    {
        $logo = $this->getLogoUrl();
        if ($logo === null || $logo === '') {
            return null;
        }
        if (str_starts_with($logo, '/api/')) {
            return null;
        }
        return $this->absolutizePublicUrl($logo, $origin);
    }

    private function absolutizePublicUrl(string $url, string $origin): ?string
    {
        if (preg_match('#^https?://#i', $url)) {
            return $url;
        }
        if ($origin === '') {
            return null;
        }
        if (str_starts_with($url, '/')) {
            $parts = parse_url($origin);
            if (!is_array($parts) || empty($parts['scheme']) || empty($parts['host'])) {
                return null;
            }
            $base = $parts['scheme'] . '://' . $parts['host'];
            if (!empty($parts['port'])) {
                $base .= ':' . $parts['port'];
            }
            return $base . $url;
        }
        $relative = (string) preg_replace('#^(?:\./)+#', '', $url);
        $relative = (string) preg_replace('#^(?:\.\./)+#', '', $relative);
        return rtrim($origin, '/') . '/' . ltrim($relative, '/');
    }

    /**
     * MIME type for a favicon filename extension.
     */
    private static function faviconMimeType(string $ext): string
    {
        return match (strtolower($ext)) {
            'svg' => 'image/svg+xml',
            'ico' => 'image/x-icon',
            'png' => 'image/png',
            'gif' => 'image/gif',
            'webp' => 'image/webp',
            'jpg', 'jpeg' => 'image/jpeg',
            default => 'image/png',
        };
    }

    /**
     * Site-uploaded favicon (operator branding). Empty when the site has none.
     *
     * @return array{ext: string, type: string}|null
     */
    private function resolveSiteFavicon(): ?array
    {
        $siteImagesDir = $this->siteAssetsImagesDir();
        if ($siteImagesDir === null) {
            return null;
        }
        foreach (['svg', 'ico', 'png', 'gif', 'webp', 'jpg', 'jpeg'] as $ext) {
            if (is_file($siteImagesDir . '/favicon.' . $ext)) {
                return ['ext' => $ext, 'type' => self::faviconMimeType($ext)];
            }
        }
        return null;
    }

    /**
     * Remove every document icon link so a later insert cannot sit beside a
     * theme-shipped SVG (browsers often prefer SVG over ICO when both exist).
     */
    private function stripDocumentIconLinks(string $html): string
    {
        $pattern = '/<link\b[^>]*\brel\s*=\s*["\'](?:shortcut\s+)?icon["\'][^>]*>\s*/i';
        $stripped = preg_replace($pattern, '', $html);
        return is_string($stripped) ? $stripped : $html;
    }

    /**
     * Insert a favicon link immediately after the opening <head> tag.
     */
    private function insertHeadLink(string $html, string $linkTag): string
    {
        if (preg_match('/<head\b[^>]*>/i', $html) !== 1) {
            return $html;
        }
        $inserted = preg_replace(
            '/(<head\b[^>]*>)/i',
            "$1\n    " . $linkTag,
            $html,
            1
        );
        return is_string($inserted) ? $inserted : $html;
    }

    /**
     * Inject the active favicon link tag into the HTML <head>.
     * A site upload always wins: every existing icon link is stripped first.
     * If the site has no favicon, keep a theme-shipped icon; otherwise inject
     * the active theme's assets/images/favicon.svg as last resort.
     */
    private function injectFavicon(string $html): string
    {
        $siteFavicon = $this->resolveSiteFavicon();
        if ($siteFavicon !== null) {
            $html = $this->stripDocumentIconLinks($html);
            if ($this->isStatic()) {
                $url = $this->webRoot . 'favicon.' . $siteFavicon['ext'];
            } else {
                $siteId = $this->siteId !== '' ? $this->siteId : SiteRegistry::DEFAULT_SITE_ID;
                $url = '/api/assets/raw/sites/' . rawurlencode($siteId)
                    . '/assets/images/favicon.' . $siteFavicon['ext'];
            }
            $linkTag = '<link rel="icon" type="' . $siteFavicon['type'] . '" href="'
                . htmlspecialchars($url, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8') . '">';
            return $this->insertHeadLink($html, $linkTag);
        }

        $iconLinkPattern = '/<link\b[^>]*\brel\s*=\s*["\'](?:shortcut\s+)?icon["\']/i';
        if (preg_match($iconLinkPattern, $html)) {
            return $html;
        }

        $themeSvg = $this->themeDir() . '/assets/images/favicon.svg';
        if (!is_file($themeSvg)) {
            return $html;
        }

        $url = $this->asset('images/favicon.svg');
        $linkTag = '<link rel="icon" type="image/svg+xml" href="'
            . htmlspecialchars($url, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8') . '">';
        return $this->insertHeadLink($html, $linkTag);
    }

    /**
     * Inject a site-scoped style override block into the HTML <head>.
     *
     * Overrides are defined by the active theme's theme.json ``style`` schema
     * and stored in the site registry. They are rendered as CSS custom properties
     * so every theme gets them without template edits.
     */
    private function injectStyleOverrides(string $html): string
    {
        $css = $this->buildStyleOverridesCss();
        if ($css === '') {
            return $html;
        }
        $pos = stripos($html, '</head>');
        if ($pos === false) {
            return $html;
        }
        // Declarations carry !important so operator choices beat theme-internal
        // layering (e.g. gazette's html[data-theme="light"] color blocks); end of
        // <head> keeps our own light-vs-dark ordering deterministic.
        $styleTag = "    <style id=\"pen-style-overrides\">\n" . $css . "\n    </style>\n";
        return substr($html, 0, $pos) . $styleTag . substr($html, $pos);
    }

    /**
     * Build CSS for per-site style overrides from the active theme's schema.
     *
     * @return string CSS with no surrounding <style> tags.
     */
    private function buildStyleOverridesCss(): string
    {
        if (empty($this->styleOverrides) || !is_array($this->styleOverrides)) {
            return '';
        }
        $themeDir = $this->themeDir();
        $manifestPath = $themeDir . '/theme.json';
        if (!is_file($manifestPath)) {
            return '';
        }
        $manifest = json_decode(file_get_contents($manifestPath), true);
        if (!is_array($manifest) || empty($manifest['style']) || !is_array($manifest['style'])) {
            return '';
        }
        $schema = $manifest['style'];
        $index = [];
        foreach ($schema['groups'] ?? [] as $group) {
            if (!is_array($group)) {
                continue;
            }
            foreach ($group['fields'] ?? [] as $field) {
                if (!is_array($field) || empty($field['id'])) {
                    continue;
                }
                $index[$field['id']] = $this->enrichStyleFieldOptions($field);
            }
        }
        if (empty($index)) {
            return '';
        }

        $values = $this->styleOverrides['values'] ?? [];
        $dark = $this->styleOverrides['dark'] ?? [];
        if (!is_array($values)) {
            $values = [];
        }
        if (!is_array($dark)) {
            $dark = [];
        }

        $lightRules = [];
        foreach ($values as $id => $value) {
            if (!is_string($id) || $id === '' || !is_string($value) || $value === '') {
                continue;
            }
            if (!isset($index[$id])) {
                continue;
            }
            if (!$this->isValidStyleValue($index[$id], $value)) {
                continue;
            }
            $var = $index[$id]['var'] ?? '';
            if (!is_string($var) || $var === '') {
                continue;
            }
            $lightRules[] = '  ' . $var . ': ' . $value . ' !important;';

            // Light rules apply on :root !important. Pin dark_default when the
            // stored dark map omitted this field so dark mode does not inherit
            // the customized light color.
            if (
                array_key_exists('dark_default', $index[$id])
                && is_string($index[$id]['dark_default'])
                && $index[$id]['dark_default'] !== ''
                && (!isset($dark[$id]) || !is_string($dark[$id]) || $dark[$id] === '')
            ) {
                $dark[$id] = $index[$id]['dark_default'];
            }
        }

        $darkRules = [];
        foreach ($dark as $id => $value) {
            if (!is_string($id) || $id === '' || !is_string($value) || $value === '') {
                continue;
            }
            if (!isset($index[$id]) || !isset($index[$id]['dark_default'])) {
                continue;
            }
            if (!$this->isValidStyleValue($index[$id], $value)) {
                continue;
            }
            $var = $index[$id]['var'] ?? '';
            if (!is_string($var) || $var === '') {
                continue;
            }
            $darkRules[] = '  ' . $var . ': ' . $value . ' !important;';
        }

        if (empty($lightRules) && empty($darkRules)) {
            return '';
        }

        $css = '';
        if (!empty($lightRules)) {
            $css .= ":root {\n" . implode("\n", $lightRules) . "\n}\n";
        }
        if (!empty($darkRules)) {
            $darkScope = $schema['dark_scope'] ?? [];
            if (!empty($darkScope['selector']) && is_string($darkScope['selector'])) {
                $selector = $darkScope['selector'];
                $css .= $selector . " {\n" . implode("\n", $darkRules) . "\n}\n";
            } elseif (!empty($darkScope['media']) && is_string($darkScope['media'])) {
                $media = $darkScope['media'];
                $css .= "@media " . $media . " {\n  :root {\n" . implode("\n", $darkRules) . "\n  }\n}\n";
            } else {
                $css .= ":root {\n" . implode("\n", $darkRules) . "\n}\n";
            }
        }
        return rtrim($css);
    }

    /**
     * Path to the central font registry JSON (sibling of themes under public/).
     */
    private function fontRegistryPath(): string
    {
        return dirname($this->themesRoot, 3) . '/public/assets/fonts/fonts.json';
    }

    /**
     * @return list<array{value: string, label: string}>
     */
    private function loadFontRegistryOptions(): array
    {
        static $cached = null;
        if (is_array($cached)) {
            return $cached;
        }
        $cached = [];
        $path = $this->fontRegistryPath();
        if (!is_file($path)) {
            return $cached;
        }
        $raw = file_get_contents($path);
        if ($raw === false) {
            return $cached;
        }
        $data = json_decode($raw, true);
        if (!is_array($data)) {
            return $cached;
        }
        $options = [];
        foreach ($data as $entry) {
            if (!is_array($entry)) {
                continue;
            }
            $stack = $entry['stack'] ?? null;
            $label = $entry['label'] ?? ($entry['family'] ?? null);
            if (!is_string($stack) || trim($stack) === '' || !is_string($label) || trim($label) === '') {
                continue;
            }
            $options[] = ['value' => $stack, 'label' => $label];
        }
        usort($options, static function (array $a, array $b): int {
            return strcasecmp($a['label'], $b['label']);
        });
        $cached = $options;
        return $cached;
    }

    /**
     * @param array<string, mixed> $field
     */
    private function isFontSelectField(array $field): bool
    {
        if (($field['type'] ?? '') !== 'select') {
            return false;
        }
        $id = strtolower((string) ($field['id'] ?? ''));
        $var = strtolower((string) ($field['var'] ?? ''));
        return str_starts_with($id, 'font') || str_contains($var, 'font');
    }

    /**
     * Append central registry stacks onto theme-authored font select options.
     *
     * @param array<string, mixed> $field
     * @return array<string, mixed>
     */
    private function enrichStyleFieldOptions(array $field): array
    {
        if (!$this->isFontSelectField($field)) {
            return $field;
        }
        $existing = $field['options'] ?? [];
        if (!is_array($existing)) {
            $existing = [];
        }
        $seen = [];
        $merged = [];
        foreach ($existing as $opt) {
            if (!is_array($opt) || !array_key_exists('value', $opt) || !isset($opt['label'])) {
                continue;
            }
            $value = (string) $opt['value'];
            if (isset($seen[$value])) {
                continue;
            }
            $seen[$value] = true;
            $merged[] = [
                'value' => $value,
                'label' => (string) $opt['label'],
            ];
        }
        foreach ($this->loadFontRegistryOptions() as $opt) {
            if (isset($seen[$opt['value']])) {
                continue;
            }
            $seen[$opt['value']] = true;
            $merged[] = $opt;
        }
        $field['options'] = $merged;
        return $field;
    }

    /**
     * Validate a single style value against its field schema.
     *
     * @param array<string, mixed> $field
     */
    private function isValidStyleValue(array $field, string $value): bool
    {
        $type = $field['type'] ?? '';
        if ($type === 'color') {
            return (bool) preg_match(
                '/^(?:#[0-9a-fA-F]{3,8}|rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)|rgba\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*(?:0?\.\d+|1(?:\.0)?)\s*\)|hsl\(\s*\d+\s*,\s*\d+%?\s*,\s*\d+%?\s*\)|hsla\(\s*\d+\s*,\s*\d+%?\s*,\s*\d+%?\s*,\s*(?:0?\.\d+|1(?:\.0)?)\s*\))$/',
                $value
            );
        }
        if ($type === 'select') {
            $allowed = [];
            foreach ($field['options'] ?? [] as $opt) {
                if (is_array($opt) && array_key_exists('value', $opt)) {
                    $allowed[] = (string) $opt['value'];
                }
            }
            return in_array($value, $allowed, true);
        }
        return false;
    }

    /**
     * Render a partial by name. Called from within templates.
     */
    public function partial(string $name, array $extra = []): string
    {
        $cleanName = ltrim($name, '_');
        $twigTpl = $this->resolveTwigPartial($name);
        $mergedData = array_merge($this->currentPageData, $extra, ['theme' => $this]);

        $kind = $extra['kind'] ?? ($mergedData['kind'] ?? 'contact');
        if ($cleanName === 'comment-thread' && !$this->commentsEnabled) {
            return '';
        }
        if ($cleanName === 'feedback-form' && (string) $kind === 'comment' && !$this->commentsEnabled) {
            return '';
        }

        // Page context may expose frontmatter byline as string `author`, which shadows
        // the Twig global profile object. Re-inject a profile array for sidebar partials,
        // resolved from the byline when possible (see resolveSidebarAuthorProfile).
        if (!isset($mergedData['author']) || !is_array($mergedData['author'])) {
            $byline = null;
            if (isset($this->currentPageData['author']) && is_string($this->currentPageData['author'])) {
                $byline = $this->currentPageData['author'];
            }
            $mergedData['author'] = $this->resolveSidebarAuthorProfile($byline);
        }

        if ($cleanName === 'comment-thread') {
            $rawComments = $mergedData['comments'] ?? [];
            $mergedData['comments'] = is_array($rawComments)
                ? CommentBody::enrichComments($rawComments)
                : [];
        }

        if ($cleanName === 'faqs') {
            $rawFaqs = $mergedData['faqs'] ?? $this->currentPageData['faqs'] ?? null;
            $mergedData['faqs'] = $this->normalizeFaqs($rawFaqs);
            if (empty($mergedData['heading']) || !is_string($mergedData['heading'])) {
                $mergedData['heading'] = $this->qaHeadingLabel();
            }
        }

        if ($this->twig && $twigTpl) {
            return $this->twig->render($twigTpl, $mergedData);
        }

        $path = $this->resolvePartial($name);
        ob_start();
        (static function (string $_tpl, array $_data): void {
            extract($_data, EXTR_SKIP);
            include $_tpl;
        })($path, $mergedData);

        return ob_get_clean() ?: '';
    }

    /**
     * Resolve a theme-relative asset path to a web-addressable URL/path.
     */
    public function asset(string $relativePath): string
    {
        $relativePath = ltrim($relativePath, '/');

        if (!empty($this->cdnBase)) {
            return rtrim($this->cdnBase, '/') . '/' . $relativePath;
        }

        // Check if file exists in the active theme's assets folder
        $themeAssetPath = $this->themeDir() . '/assets/' . $relativePath;
        if (file_exists($themeAssetPath)) {
            if ($this->isStatic()) {
                return $this->webRoot . $relativePath;
            }
            return $this->themeAssetLiveUrl($relativePath);
        }

        // Check if file exists in the shared folder
        $sharedAssetPath = dirname($this->themesRoot) . '/shared/' . $relativePath;
        if (file_exists($sharedAssetPath)) {
            return $this->webRoot . 'shared/' . $relativePath;
        }

        // Fallback to active theme asset path if not found anywhere
        if ($this->isStatic()) {
            return $this->webRoot . $relativePath;
        }
        return $this->themeAssetLiveUrl($relativePath);
    }

    /**
     * Resolve the site logo dynamically, scanning for standard formats (.png, .svg, .webp, .jpg, .gif).
     * Order: site assets → theme assets (no install shared — avoids cross-site bleed).
     * Returns null if "display_logo" is disabled, or if no logo file is found.
     */
    public function getLogoUrl(): ?string
    {
        if (!$this->displayLogo) {
            return null;
        }

        $formats = ['png', 'svg', 'webp', 'jpg', 'gif'];
        $siteImagesDir = $this->siteAssetsImagesDir();

        foreach ($formats as $ext) {
            $relativePath = 'images/logo.' . $ext;

            // 1) Per-site assets (content/sites/{id}/assets/images/logo.*)
            if ($siteImagesDir !== null && file_exists($siteImagesDir . '/logo.' . $ext)) {
                if ($this->isStatic()) {
                    return $this->webRoot . $relativePath;
                }
                $siteId = $this->siteId !== '' ? $this->siteId : SiteRegistry::DEFAULT_SITE_ID;
                return '/api/assets/raw/sites/' . rawurlencode($siteId) . '/assets/images/logo.' . $ext;
            }

            // 2) Active theme assets
            $themeAssetPath = $this->themeDir() . '/assets/' . $relativePath;
            if (file_exists($themeAssetPath)) {
                if ($this->isStatic()) {
                    return $this->webRoot . $relativePath;
                }
                return $this->themeAssetLiveUrl($relativePath);
            }
        }

        return null;
    }


    /**
     * Resolve a content asset (e.g., an article image) to a web-addressable URL.
     */
    public function contentAsset(string $relativePath): string
    {
        $relativePath = ltrim($relativePath, '/');

        // Absolute remote or data URLs
        if (preg_match('~^(https?:)?//~i', $relativePath) || str_starts_with($relativePath, 'data:')) {
            return $relativePath;
        }

        // Normalize API proxy / sites/{id}/assets/ URLs down to logical paths
        // (e.g. images/content/...) so static builds can emit relative URLs.
        if (str_starts_with($relativePath, 'api/assets/raw/')) {
            $relativePath = substr($relativePath, strlen('api/assets/raw/'));
        }
        if (preg_match('#^sites/[^/]+/assets/(.+)$#', $relativePath, $m)) {
            $relativePath = $m[1];
        }

        // Check if it's a theme fallback (exists in theme folder). Manifest
        // social_preview paths conventionally include the theme-relative
        // `assets/` prefix, while ThemeEngine::asset() accepts paths relative
        // to the theme's assets directory.
        $themeRelativePath = $relativePath;
        if (str_starts_with($themeRelativePath, 'assets/')) {
            $themeRelativePath = substr($themeRelativePath, strlen('assets/'));
        }
        $themePath = $this->themeDir() . '/assets/' . $themeRelativePath;
        if (file_exists($themePath)) {
            return $this->asset($themeRelativePath);
        }

        // Special handling for shared assets so they bypass dynamic assets base URL (/assets/)
        if (strpos($relativePath, 'shared/') === 0) {
            return $this->webRoot . $relativePath;
        }

        if ($this->isStatic()) {
            return $this->webRoot . $relativePath;
        }

        // Logical site asset (e.g. images/content/.../hero.png) → site-scoped API proxy
        $siteId = $this->siteId !== '' ? $this->siteId : SiteRegistry::DEFAULT_SITE_ID;

        return '/api/assets/raw/sites/' . $siteId . '/assets/' . $relativePath;
    }

    /**
     * Resolve a site-root public asset (e.g. vendor/katex) to a web-addressable URL.
     * Live preview serves these from /assets/; static builds use a relative webRoot.
     */
    public function publicAsset(string $relativePath): string
    {
        $relativePath = ltrim($relativePath, '/');

        if ($this->isStatic()) {
            return $this->webRoot . 'assets/' . $relativePath;
        }

        return '/assets/' . $relativePath;
    }

    /**
     * Inline a CSS file with asset-path tokens already resolved.
     */
    public function inlineCss(string $relativeCssPath): string
    {
        $absPath = $this->themeDir() . '/assets/' . ltrim($relativeCssPath, '/');

        if (!file_exists($absPath)) {
            return "/* ThemeEngine: asset not found: {$relativeCssPath} */";
        }

        $css       = file_get_contents($absPath);

        // Normalise images/ and fonts/ references
        $css = preg_replace(
            "/url\(['\"]?images\//",
            "url('{$this->asset('images/')}",
            $css
        );
        $css = preg_replace(
            "/url\(['\"]?fonts\//",
            "url('{$this->asset('fonts/')}",
            $css
        );

        return "<style>\n{$css}\n</style>";
    }

    /**
     * Emit an external <link> tag for a CSS file, with the href resolved
     * through asset() so it works in both dynamic-PHP and static-build modes.
     */
    public function linkCss(string $relativeCssPath): string
    {
        $href = $this->asset(ltrim($relativeCssPath, '/'));
        return '<link rel="stylesheet" href="' . htmlspecialchars($href, ENT_QUOTES, 'UTF-8') . '">';
    }

    /**
     * True when running a static build.
     */
    public function isStatic(): bool
    {
        return $this->isStatic || (defined('STATIC_BUILD') && STATIC_BUILD);
    }

    /**
     * Returns the theme type from theme.json ('native' or 'ghost-import').
     */
    public function getThemeType(): string
    {
        return 'native';
    }

    public function manifest(): array
    {
        $path = $this->themeDir() . '/theme.json';
        if (!file_exists($path)) {
            return [];
        }
        return json_decode(file_get_contents($path), true) ?? [];
    }

    private function themeDir(): string
    {
        if ($this->themeDirOverride !== null) {
            return $this->themeDirOverride;
        }
        return $this->themesRoot . '/' . $this->activeTheme;
    }

    private function resolveTemplate(string $name, ?string $key = null): string
    {
        if ($key !== null) {
            $pathKey = $this->themeDir() . '/templates/' . $name . '-' . $key . '.php';
            if (file_exists($pathKey)) {
                return $pathKey;
            }
            $lowerKey = strtolower($key);
            if ($lowerKey !== $key) {
                $pathKeyLower = $this->themeDir() . '/templates/' . $name . '-' . $lowerKey . '.php';
                if (file_exists($pathKeyLower)) {
                    return $pathKeyLower;
                }
            }
        }
        $path = $this->themeDir() . '/templates/' . $name . '.php';

        if (!file_exists($path)) {
            throw new \RuntimeException(
                "Theme '{$this->activeTheme}' is missing required template: templates/{$name}.php"
            );
        }

        return $path;
    }

    private function resolvePartial(string $name): string
    {
        $cleanName = ltrim($name, '_');
        
        $paths = [
            $this->themeDir() . '/partials/' . $name . '.php',
            $this->themeDir() . '/partials/_' . $cleanName . '.php',
            $this->themeDir() . '/partials/' . $cleanName . '.php',
        ];

        foreach ($paths as $path) {
            if (file_exists($path)) {
                return $path;
            }
        }

        throw new \RuntimeException(
            "Theme '{$this->activeTheme}' is missing partial: {$name}"
        );
    }

    private function validateAndNormalise(array $pageData): array
    {
        $contract = $this->loadContract();

        foreach ($contract['variables'] as $name => $spec) {
            $required = $spec['required'] ?? false;

            if (!array_key_exists($name, $pageData)) {
                if ($required) {
                    throw new \RuntimeException(
                        "ThemeEngine: required page variable '\${$name}' was not provided."
                    );
                }
                $pageData[$name] = $this->defaultFor($spec['type'] ?? 'string');
            }
        }

        return $pageData;
    }

    private function loadContract(): array
    {
        $manifest = $this->manifest();

        if (!empty($manifest['variables'])) {
            return ['variables' => $manifest['variables']];
        }

        return [
            'variables' => [
                'hero_title'   => ['type' => 'string', 'required' => true],
                'posts'     => ['type' => 'array',  'required' => false],
                'hero_image'   => ['type' => 'string', 'required' => false],
                'deck'         => ['type' => 'html',   'required' => false],
                'trumpet'      => ['type' => 'string', 'required' => false],
                'is_composite' => ['type' => 'bool',   'required' => false],
                'date'         => ['type' => 'string', 'required' => false],
                'author'       => ['type' => 'string', 'required' => false],
                'dateline'     => ['type' => 'string', 'required' => false],
                'page_title'   => ['type' => 'string', 'required' => false],
                'tagline'      => ['type' => 'string', 'required' => false],
                'sitename'     => ['type' => 'string', 'required' => false],
                'og_title'     => ['type' => 'string', 'required' => false],
                'og_description'=>['type' => 'string', 'required' => false],
                'og_image'     => ['type' => 'string', 'required' => false],
                'meta_description'=>['type' => 'string', 'required' => false],
            ],
        ];
    }

    private function defaultFor(string $type): mixed
    {
        return match ($type) {
            'array'        => [],
            'bool'         => false,
            'int'          => 0,
            'html', 'path',
            'string'       => '',
            default        => null,
        };
    }

    private function initTwig(string $configPath): void
    {
        if (!class_exists('\Twig\Environment')) {
            return;
        }

        $loader = new \Twig\Loader\FilesystemLoader($this->themeDir());
        if (is_dir($this->themeDir() . '/templates')) {
            $loader->addPath($this->themeDir() . '/templates', 'templates');
        }
        if (is_dir($this->themeDir() . '/partials')) {
            $loader->addPath($this->themeDir() . '/partials', 'partials');
        }
        $coreI18nPartials = __DIR__ . '/i18n/partials';
        if (is_dir($coreI18nPartials)) {
            $loader->addPath($coreI18nPartials, 'pencms');
        }
        $corePartials = __DIR__ . '/partials';
        if (is_dir($corePartials)) {
            $loader->addPath($corePartials, 'pencms');
        }
        $globalPartials = $this->themesRoot . '/international/partials';
        if (!is_dir($globalPartials)) {
            $globalPartials = $this->themesRoot . '/global/partials';
        }
        if (is_dir($globalPartials)) {
            $loader->addPath($globalPartials, 'global');
            $loader->addPath($globalPartials, 'international');
        }

        // Read Twig cache option from config.ini
        $twigCache = false;
        if (file_exists($configPath)) {
            $cfg = parse_ini_file($configPath, true);
            $cacheEnabled = $cfg['theme']['twig_cache'] ?? 'false';
            if ($cacheEnabled !== 'false' && $cacheEnabled !== '' && $cacheEnabled !== '0') {
                if ($cacheEnabled === 'true' || $cacheEnabled === '1') {
                    $twigCache = __DIR__ . '/../blog/cache';
                } else {
                    $twigCache = $cacheEnabled;
                }
                if (!is_dir($twigCache)) {
                    @mkdir($twigCache, 0777, true);
                }
            }
        }

        $this->twig = new \Twig\Environment($loader, [
            'cache' => $twigCache,
            'debug' => $this->isStatic,
            'auto_reload' => true,
            'strict_variables' => true,
        ]);

        $policy = \Dossier\TwigSandboxPolicy::create();
        $this->twig->addExtension(new \Twig\Extension\SandboxExtension($policy, true));

        // Add extensions/functions for asset and contentAsset
        $this->twig->addFunction(new \Twig\TwigFunction('asset', function (string $path) {
            return $this->asset($path);
        }));

        $this->twig->addFunction(new \Twig\TwigFunction('contentAsset', function (string $path) {
            return $this->contentAsset($path);
        }));

        $this->twig->addFunction(new \Twig\TwigFunction('publicAsset', function (string $path) {
            return $this->publicAsset($path);
        }));

        $this->twig->addFunction(new \Twig\TwigFunction('contentUrl', function (array $dossier) {
            return $this->contentUrl($dossier);
        }));

        $this->twig->addFunction(new \Twig\TwigFunction('archiveUrl', function (?string $category = null) {
            return $this->archiveUrl($category);
        }));

        $this->twig->addFunction(new \Twig\TwigFunction('partial', function (string $name, array $extra = []) {
            return $this->partial($name, $extra);
        }));

        $this->twig->addFunction(new \Twig\TwigFunction('inlineCss', function (string $path) {
            return $this->inlineCss($path);
        }));

        $this->twig->addFunction(new \Twig\TwigFunction('linkCss', function (string $path) {
            return $this->linkCss($path);
        }));

        // Load category_colors config for themes (e.g. editorial)
        $categoryColors = [];
        $appRoot = dirname($configPath);
        $cfg = file_exists($configPath) ? parse_ini_file($configPath, true) : [];
        $contentDir = $cfg['Paths']['content_dir'] ?? '../pencms-data/content';
        if (strpos($contentDir, '/') !== 0) {
            $contentDir = $appRoot . '/' . $contentDir;
        }
        $globalCatPath = dirname($contentDir) . '/category_colors.json';
        $themeCatPath  = $this->themeDir() . '/category_colors.json';

        if (file_exists($globalCatPath)) {
            $categoryColors = json_decode((string) file_get_contents($globalCatPath), true) ?: [];
        } elseif (file_exists($themeCatPath)) {
            $categoryColors = json_decode((string) file_get_contents($themeCatPath), true) ?: [];
        }
        $this->twig->addGlobal('category_colors', $categoryColors);

        $this->twig->addFunction(new \Twig\TwigFunction('menu', function (string $slot) {
            return $this->getMenu($slot);
        }));

        // Author globals:
        // - `authors` = list from content/sites/{id}/authors.yaml (site-scoped)
        // - `author`  = site-default sidebar profile (first site author by sort_order, else data/users)
        // Note: page/post context may also expose `author` as a free-text byline string —
        // that collides with this global. theme.partial() re-injects a profile array via
        // resolveSidebarAuthorProfile() (byline → authors[].name match).
        $siteAuthors = $this->getSiteAuthors();
        $this->twig->addGlobal('authors', $siteAuthors);
        $authorData = $this->getAuthorProfile($configPath);
        $this->authorProfile = $authorData;
        $this->twig->addGlobal('author', $authorData);
        $this->twig->addGlobal('twitter_card', $this->twitterCard);
        $this->twig->addGlobal('og_title_fallback', $this->ogTitleFallback !== '' ? $this->ogTitleFallback : null);
        $this->twig->addGlobal('og_description_fallback', $this->ogDescriptionFallback !== '' ? $this->ogDescriptionFallback : null);
        $this->twig->addGlobal('og_default_image', $this->ogDefaultImage !== '' ? $this->ogDefaultImage : null);
        $this->twig->addGlobal('social_links', $this->socialLinks);
        $this->twig->addGlobal('index_hero_title', $this->indexHeroTitle !== '' ? $this->indexHeroTitle : null);
    }

    /**
     * Load site-scoped authors from authors.yaml (same path resolution as menus).
     * Bios are plain text — templates should escape; no Markdown pipeline.
     *
     * @return list<array{slug:string,name:string,bio:string,website:string,avatar:?string,email:string,role:string,sort_order:int}>
     */
    public function getSiteAuthors(): array
    {
        if ($this->authorsCache !== null) {
            return $this->authorsCache;
        }

        $this->authorsCache = [];
        if (!$this->configPath || !file_exists($this->configPath)) {
            return $this->authorsCache;
        }

        $appRoot = dirname($this->configPath);
        $cfg = parse_ini_file($this->configPath, true);
        $contentDir = $cfg['Paths']['content_dir'] ?? '../pencms-data/content';
        if (strpos($contentDir, '/') !== 0) {
            $contentDir = $appRoot . '/' . $contentDir;
        }
        $authorsPath = rtrim($contentDir, '/') . '/' . $this->contentRelpath . '/authors.yaml';
        if (!file_exists($authorsPath)) {
            return $this->authorsCache;
        }

        $decoded = null;
        try {
            if (class_exists('\Symfony\Component\Yaml\Yaml')) {
                $decoded = \Symfony\Component\Yaml\Yaml::parseFile($authorsPath);
            } elseif (function_exists('yaml_parse_file')) {
                $decoded = @yaml_parse_file($authorsPath);
            }
        } catch (\Exception $e) {
            return $this->authorsCache;
        }

        if (!is_array($decoded) || !isset($decoded['authors']) || !is_array($decoded['authors'])) {
            return $this->authorsCache;
        }

        $list = [];
        foreach ($decoded['authors'] as $row) {
            if (!is_array($row) || empty($row['slug']) || empty($row['name'])) {
                continue;
            }
            $avatar = $row['avatar'] ?? null;
            if (is_string($avatar) && $avatar !== '') {
                $avatar = $this->contentAsset($avatar);
            } else {
                $avatar = null;
            }
            $list[] = [
                'slug' => (string) $row['slug'],
                'name' => (string) $row['name'],
                'bio' => (string) ($row['bio'] ?? ''),
                'website' => (string) ($row['website'] ?? ''),
                'avatar' => $avatar,
                'email' => (string) ($row['email'] ?? ''),
                'role' => (string) ($row['role'] ?? ''),
                'sort_order' => (int) ($row['sort_order'] ?? 0),
            ];
        }

        usort($list, static function (array $a, array $b): int {
            if ($a['sort_order'] === $b['sort_order']) {
                return strcasecmp($a['name'], $b['name']);
            }
            return $a['sort_order'] <=> $b['sort_order'];
        });

        $this->authorsCache = $list;
        return $this->authorsCache;
    }

    /**
     * Map a site-author list row to the sidebar profile shape used by themes.
     *
     * @param array{slug?:string,name:string,bio?:string,website?:string,avatar?:?string} $row
     * @return array{display_name:string,bio:string,website:string,avatar:?string}
     */
    private function siteAuthorToProfile(array $row): array
    {
        return [
            'display_name' => (string) ($row['name'] ?? ''),
            'bio' => (string) ($row['bio'] ?? ''),
            'website' => (string) ($row['website'] ?? ''),
            'avatar' => $row['avatar'] ?? null,
        ];
    }

    /**
     * Sidebar profile for theme.partial('sidebar-profile').
     *
     * - Byline matches authors[].name (case-insensitive) → that author's profile
     * - Byline present but unmatched (custom) → display_name only; empty bio/website; null avatar
     * - No byline → site-default authorProfile
     *
     * @return array{display_name:string,bio:string,website:string,avatar:?string}
     */
    public function resolveSidebarAuthorProfile(?string $byline): array
    {
        $trimmed = $byline !== null ? trim($byline) : '';
        if ($trimmed === '') {
            return !empty($this->authorProfile)
                ? $this->authorProfile
                : [
                    'display_name' => '',
                    'bio' => '',
                    'website' => '',
                    'avatar' => null,
                ];
        }

        foreach ($this->getSiteAuthors() as $row) {
            if (strcasecmp((string) ($row['name'] ?? ''), $trimmed) === 0) {
                return $this->siteAuthorToProfile($row);
            }
        }

        return [
            'display_name' => $trimmed,
            'bio' => '',
            'website' => '',
            'avatar' => null,
        ];
    }

    /**
     * Sidebar / Twig global `author` profile.
     * Prefer first site author from authors.yaml when present; else first data/users YAML.
     */
    public function getAuthorProfile(string $configPath): array
    {
        $siteAuthors = $this->getSiteAuthors();
        if (!empty($siteAuthors)) {
            return $this->siteAuthorToProfile($siteAuthors[0]);
        }

        $author = [
            'display_name' => 'PenCMS', // Safe default fallback matching original theme context
            'bio' => 'A Blog About the History of the Cold War and What Came After',
            'website' => '',
            'avatar' => null
        ];

        $appRoot = dirname($configPath);
        $usersDir = $appRoot . '/data/users';

        if (is_dir($usersDir)) {
            $files = glob($usersDir . '/*.yaml');
            if (!empty($files)) {
                // Read the first user profile YAML file
                $userFile = $files[0];
                try {
                    if (class_exists('\Symfony\Component\Yaml\Yaml')) {
                        $userData = \Symfony\Component\Yaml\Yaml::parseFile($userFile);
                        if (!empty($userData['public'])) {
                            $pub = $userData['public'];
                            $author['display_name'] = $pub['display_name'] ?? $pub['username'] ?? $author['display_name'];
                            $author['bio'] = $pub['bio'] ?? $author['bio'];
                            $author['website'] = $pub['website'] ?? $author['website'];
                            
                            $avatar = $pub['avatar'] ?? null;
                            if (!empty($avatar)) {
                                $cfg = file_exists($configPath) ? parse_ini_file($configPath, true) : [];
                                $configuredWebRoot = $cfg['theme']['web_root'] ?? '/blog/';
                                $configuredWebRootClean = '/' . trim($configuredWebRoot, '/') . '/';
                                if (strpos($avatar, $configuredWebRootClean) === 0) {
                                    $avatar = $this->webRoot . substr($avatar, strlen($configuredWebRootClean));
                                } elseif (strpos($avatar, '/shared/') === 0) {
                                    $avatar = $this->webRoot . substr($avatar, 1);
                                }
                                $author['avatar'] = $avatar;
                            }
                        }
                    }
                } catch (\Exception $e) {
                    // Fallback gracefully
                }
            }
        }

        // If no explicit avatar URL was stored, search for a local avatar image in shared images
        if (empty($author['avatar'])) {
            $sharedDir = $appRoot . '/apps/blog/shared/images/';
            $formats = ['png', 'svg', 'webp', 'jpg', 'jpeg', 'gif'];
            foreach ($formats as $ext) {
                if (file_exists($sharedDir . 'avatar.' . $ext)) {
                    $author['avatar'] = $this->webRoot . 'shared/images/avatar.' . $ext;
                    break;
                }
            }
        }

        return $author;
    }

    /**
     * Dynamically loads a list of related dossiers, excluding the active one.
     * Scoped to this theme engine's site — never crosses sites.
     */
    public function getRelatedDossiers(
        ?string $currentSlug = null,
        ?string $language = null
    ): array
    {
        try {
            if (!class_exists('\Dossier\DossierDiscovery')) {
                require_once __DIR__ . '/DossierDiscovery.php';
            }
            if (class_exists('\Dossier\DossierDiscovery')) {
                $discovery = new \Dossier\DossierDiscovery(new InternalAPIClient($this->siteId));
                $language = $language !== null
                    ? self::normalizeLanguage($language)
                    : '';
                $localized = $this->i18nActive
                    && $language !== ''
                    && $language !== $this->defaultLanguage
                    && in_array($language, $this->activeLanguages, true);
                $all = $discovery->getAllDossiers(
                    'blog',
                    false,
                    $localized ? $language : null,
                    $localized ? 'default' : 'none'
                );
                
                $currentDossier = null;
                if ($currentSlug !== null) {
                    foreach ($all as $d) {
                        if ($d['slug'] === $currentSlug) {
                            $currentDossier = $d;
                            break;
                        }
                    }
                }

                if (!$currentDossier) {
                    // Fallback to top 4 published if active dossier isn't found
                    $related = [];
                    foreach ($all as $d) {
                        if ($currentSlug !== null && $d['slug'] === $currentSlug) {
                            continue;
                        }
                        $related[] = $d;
                        if (count($related) >= 4) {
                            break;
                        }
                    }
                    return $related;
                }

                // Similarity Engine Scoring
                $scored = [];
                $stopWords = ['a', 'an', 'the', 'and', 'or', 'but', 'is', 'are', 'was', 'were', 'to', 'for', 'in', 'on', 'at', 'by', 'of', 'with', 'from', 'about'];

                foreach ($all as $d) {
                    if ($d['slug'] === $currentSlug) {
                        continue;
                    }

                    $score = 0;

                    // 1. Category/Type Match (+5 points)
                    if (($d['category'] ?? '') === ($currentDossier['category'] ?? '')) {
                        $score += 5;
                    }

                    // 2. Tag Label Overlaps (+10 points per matched label, case-insensitive)
                    $currentTags = array_map('strtolower', $currentDossier['tags'] ?? []);
                    $candidateTags = array_map('strtolower', $d['tags'] ?? []);
                    $sharedTags = array_intersect($currentTags, $candidateTags);
                    $score += count($sharedTags) * 10;

                    // 3. Metadata Block Overlaps (+15 points per matched metadata label, case-insensitive)
                    $currentMeta = array_map('strtolower', $currentDossier['metadata'] ?? []);
                    $candidateMeta = array_map('strtolower', $d['metadata'] ?? []);
                    $sharedMeta = array_intersect($currentMeta, $candidateMeta);
                    $score += count($sharedMeta) * 15;

                    // 4. Title Word Overlaps (+3 points per matched word)
                    $currentWords = array_diff(
                        str_word_count(strtolower($currentDossier['title'] ?? ''), 1),
                        $stopWords
                    );
                    $candidateWords = array_diff(
                        str_word_count(strtolower($d['title'] ?? ''), 1),
                        $stopWords
                    );
                    $sharedWords = array_intersect($currentWords, $candidateWords);
                    $score += count($sharedWords) * 3;

                    // 5. Exponential Time Decay Weight
                    $timeDeltaDays = abs(strtotime($currentDossier['date']) - strtotime($d['date'])) / 86400;
                    $decayFactor = exp(-0.0005 * $timeDeltaDays); // halflife is approx 3.8 years
                    
                    // Add a tiny baseline score (0.01) so date sorting naturally applies even to zero-match dossiers
                    $finalScore = ($score + 0.01) * $decayFactor;

                    $scored[] = [
                        'dossier' => $d,
                        'score' => $finalScore,
                        'timestamp' => strtotime($d['date'])
                    ];
                }

                // Sort by final score descending, breaking ties with newer dates
                usort($scored, function($a, $b) {
                    if (abs($a['score'] - $b['score']) < 0.0001) {
                        return $b['timestamp'] <=> $a['timestamp'];
                    }
                    return $b['score'] <=> $a['score'];
                });

                // Take top 4
                $related = [];
                foreach (array_slice($scored, 0, 4) as $item) {
                    $related[] = $item['dossier'];
                }

                return $related;
            }
            return [];
        } catch (\Exception $e) {
            return [];
        }
    }

    /**
     * Dynamically loads a list of all publishable dossiers for this site only.
     */
    public function getAllDossiers(): array
    {
        try {
            if (!class_exists('\Dossier\DossierDiscovery')) {
                require_once __DIR__ . '/DossierDiscovery.php';
            }
            if (class_exists('\Dossier\DossierDiscovery')) {
                $discovery = new \Dossier\DossierDiscovery(new InternalAPIClient($this->siteId));
                $localized = $this->i18nActive
                    && $this->renderLanguage !== $this->defaultLanguage;
                return $discovery->getAllDossiers(
                    'blog',
                    false,
                    $localized ? $this->renderLanguage : null,
                    $localized ? 'default' : 'none'
                );
            }
            return [];
        } catch (\Exception $e) {
            return [];
        }
    }

    /**
     * Resolve one dossier card to an exact localized detail or its real
     * default-language URL.
     *
     * @param array<string, mixed> $dossier
     */
    public function contentUrl(
        array $dossier,
        ?string $contextLanguage = null
    ): string
    {
        $slug = trim((string) ($dossier['slug'] ?? ''));
        if ($slug === '') {
            return '';
        }

        $currentLanguage = $this->renderLanguage;
        if ($contextLanguage !== null) {
            $candidate = self::normalizeLanguage($contextLanguage);
            if (
                $this->i18nActive
                && in_array($candidate, $this->activeLanguages, true)
            ) {
                $currentLanguage = $candidate;
            }
        }
        $isFallback = !empty($dossier['is_fallback']);
        $actualLanguage = isset($dossier['language']) && is_string($dossier['language'])
            ? self::normalizeLanguage($dossier['language'])
            : $this->defaultLanguage;
        $localized = $this->i18nActive
            && $currentLanguage !== $this->defaultLanguage
            && $actualLanguage === $currentLanguage
            && !$isFallback;

        if ($localized) {
            $url = $this->isStatic()
                ? $this->webRoot . rawurlencode($currentLanguage) . '/'
                    . rawurlencode($slug) . '/index.html'
                : LocalizedDetail::publicPath(
                    $this->webRoot,
                    $currentLanguage,
                    $slug
                );
        } else {
            $isPage = !empty($dossier['page']);
            $url = $this->webRoot . (
                $this->isStatic()
                    ? rawurlencode($slug) . '/index.html'
                    : ($isPage ? 'page.php?slug=' : 'post.php?slug=') . rawurlencode($slug)
            );
        }

        return PreviewUrl::appendPreviewSiteQuery(
            $url,
            $this->siteId,
            $this->isStatic()
        );
    }

    public function contentUrlForSlug(
        string $slug,
        ?string $section = null,
        ?string $contextLanguage = null
    ): string {
        $language = $contextLanguage !== null
            ? self::normalizeLanguage($contextLanguage)
            : $this->renderLanguage;
        $localized = $this->i18nActive
            && $language !== $this->defaultLanguage
            && in_array($language, $this->activeLanguages, true);
        $exact = $localized ? $this->exactLocalizedContent($language) : [];
        if (isset($exact[$slug])) {
            return $this->contentUrl($exact[$slug], $language);
        }
        return $this->contentUrl([
            'slug' => $slug,
            'page' => strtolower(trim((string) $section)) === 'general',
            'language' => $this->defaultLanguage,
            'is_fallback' => $localized,
        ], $language);
    }

    public function archiveUrl(?string $category = null): string
    {
        $category = $category !== null ? trim($category) : null;
        $localized = $this->i18nActive
            && $this->renderLanguage !== $this->defaultLanguage;

        if ($localized) {
            $url = $this->isStatic()
                ? $this->webRoot . rawurlencode($this->renderLanguage)
                    . '/category/'
                    . ($category !== null && $category !== ''
                        ? rawurlencode($category) . '/'
                        : '')
                    . 'index.html'
                : LocalizedList::publicPath(
                    $this->webRoot,
                    $this->renderLanguage,
                    'archive',
                    $category
                );
        } else {
            $url = $this->isStatic()
                ? $this->webRoot . 'category/'
                    . ($category !== null && $category !== ''
                        ? rawurlencode($category) . '/'
                        : '')
                    . 'index.html'
                : $this->webRoot . 'category.php'
                    . ($category !== null && $category !== ''
                        ? '?category=' . rawurlencode($category)
                        : '');
        }

        return PreviewUrl::appendPreviewSiteQuery(
            $url,
            $this->siteId,
            $this->isStatic()
        );
    }

    private function systemUrl(string $systemId): string
    {
        $localized = $this->i18nActive
            && $this->renderLanguage !== $this->defaultLanguage;
        if ($localized && in_array($systemId, ['home', 'blog', 'search'], true)) {
            $surface = $systemId === 'blog' ? 'archive' : $systemId;
            $url = $this->isStatic()
                ? $this->webRoot . rawurlencode($this->renderLanguage) . '/'
                    . ($surface === 'archive' ? 'category/' : '')
                    . ($surface === 'search' ? 'search/' : '')
                    . 'index.html'
                : LocalizedList::publicPath(
                    $this->webRoot,
                    $this->renderLanguage,
                    $surface
                );
            return PreviewUrl::appendPreviewSiteQuery(
                $url,
                $this->siteId,
                $this->isStatic()
            );
        }

        if ($systemId === 'home') {
            $url = $this->webRoot . ($this->isStatic() ? 'index.html' : 'index.php');
        } elseif ($systemId === 'blog') {
            $url = $this->webRoot . ($this->isStatic() ? 'category/index.html' : 'category.php');
        } elseif ($systemId === 'search') {
            $url = $this->webRoot . ($this->isStatic() ? 'search/index.html' : 'search.php');
        } elseif ($systemId === 'rss') {
            $url = $this->webRoot . 'feed.xml';
        } else {
            return '';
        }
        return PreviewUrl::appendPreviewSiteQuery(
            $url,
            $this->siteId,
            $this->isStatic()
        );
    }

    /**
     * @return array<string, array<string, mixed>>
     */
    private function exactLocalizedContent(string $language): array
    {
        if (isset($this->exactLocalizedContentCache[$language])) {
            return $this->exactLocalizedContentCache[$language];
        }
        $this->exactLocalizedContentCache[$language] = [];
        if (
            !$this->i18nActive
            || $language === $this->defaultLanguage
            || !in_array($language, $this->activeLanguages, true)
        ) {
            return [];
        }

        try {
            $api = new InternalAPIClient($this->siteId);
            $rows = $api->get('/pages/', [
                'language' => $language,
                'fallback' => 'none',
                'live_only' => 'true',
            ]);
            foreach ($rows as $row) {
                $slug = trim((string) ($row['id'] ?? ''));
                if ($slug !== '') {
                    $row['slug'] = $slug;
                    $this->exactLocalizedContentCache[$language][$slug] = $row;
                }
            }
        } catch (\Exception $e) {
            return [];
        }
        return $this->exactLocalizedContentCache[$language];
    }

    private function resolveTwigTemplate(string $name, ?string $key = null): ?string
    {
        $relativePaths = [];
        if ($key !== null) {
            $relativePaths[] = 'templates/' . $name . '-' . $key . '.html.twig';
            $relativePaths[] = 'templates/' . $name . '-' . $key . '.twig';
            
            $lowerKey = strtolower($key);
            if ($lowerKey !== $key) {
                $relativePaths[] = 'templates/' . $name . '-' . $lowerKey . '.html.twig';
                $relativePaths[] = 'templates/' . $name . '-' . $lowerKey . '.twig';
            }
        }
        $relativePaths[] = 'templates/' . $name . '.html.twig';
        $relativePaths[] = 'templates/' . $name . '.twig';

        foreach ($relativePaths as $rel) {
            if (file_exists($this->themeDir() . '/' . $rel)) {
                return $rel;
            }
        }
        return null;
    }

    private function resolveTwigPartial(string $name): ?string
    {
        $cleanName = ltrim($name, '_');
        $relativePaths = [
            'partials/' . $name . '.html.twig',
            'partials/' . $name . '.twig',
            'partials/_' . $cleanName . '.html.twig',
            'partials/_' . $cleanName . '.twig',
            'partials/' . $cleanName . '.html.twig',
            'partials/' . $cleanName . '.twig',
        ];
        foreach ($relativePaths as $rel) {
            if (file_exists($this->themeDir() . '/' . $rel)) {
                return $rel;
            }
        }
        if (
            $cleanName === 'language-switcher'
            && file_exists(__DIR__ . '/i18n/partials/_language-switcher.html.twig')
        ) {
            return '@pencms/_language-switcher.html.twig';
        }
        if (
            $cleanName === 'faqs'
            && file_exists(__DIR__ . '/partials/_faqs.html.twig')
        ) {
            return '@pencms/_faqs.html.twig';
        }
        $globalNames = ['feedback-form', 'comment-thread'];
        foreach ($globalNames as $globalName) {
            $globalFile = $this->themesRoot . '/international/partials/_' . $globalName . '.html.twig';
            if (!file_exists($globalFile)) {
                $globalFile = $this->themesRoot . '/global/partials/_' . $globalName . '.html.twig';
            }
            if ($cleanName === $globalName && file_exists($globalFile)) {
                return '@global/_' . $globalName . '.html.twig';
            }
        }
        return null;
    }

    /**
     * Fetch the tree of menu items for a slot, with URLs resolved.
     */
    public function getMenu(string $slot): array
    {
        if ($this->menuCache === null) {
            $this->menuCache = [];
            if ($this->configPath && file_exists($this->configPath)) {
                $appRoot = dirname($this->configPath);
                $cfg = parse_ini_file($this->configPath, true);
                $contentDir = $cfg['Paths']['content_dir'] ?? '../pencms-data/content';
                if (strpos($contentDir, '/') !== 0) {
                    $contentDir = $appRoot . '/' . $contentDir;
                }
                // Per-site menus: Host-resolved site (see SiteRegistry / PublicSiteContext).
                $menusPath = rtrim($contentDir, '/') . '/' . $this->contentRelpath . '/menus.yaml';
                if (file_exists($menusPath)) {
                    $decoded = null;
                    if (class_exists('\Symfony\Component\Yaml\Yaml')) {
                        $decoded = \Symfony\Component\Yaml\Yaml::parseFile($menusPath);
                    } elseif (function_exists('yaml_parse_file')) {
                        $decoded = @yaml_parse_file($menusPath);
                    }
                    if (is_array($decoded)) {
                        $this->menuCache = $decoded;
                    }
                }
            }
        }

        $rawItems = $this->menuCache[$slot] ?? [];

        // If primary menu is empty/non-existent, fall back to a default "Home" link
        if (empty($rawItems) && $slot === 'primary') {
            return [
                [
                    'id' => 'default-home',
                    'label' => (string) (
                        $this->currentPageData['strings']['home'] ?? 'Home'
                    ),
                    'url' => $this->systemUrl('home'),
                    'open_in_new_tab' => false,
                    'target_type' => 'custom',
                    'children' => []
                ]
            ];
        }

        $itemsById = [];
        foreach ($rawItems as $item) {
            if (!isset($item['id']) || !isset($item['label']) || !isset($item['target']['type'])) {
                continue;
            }
            $target = $item['target'];
            $url = '';
            $label = (string) $item['label'];
            if (
                ($target['type'] ?? '') !== 'taxonomy'
                && $this->i18nActive
                && $this->renderLanguage !== $this->defaultLanguage
                && isset($item['labels'][$this->renderLanguage])
                && is_string($item['labels'][$this->renderLanguage])
                && trim($item['labels'][$this->renderLanguage]) !== ''
            ) {
                $label = trim($item['labels'][$this->renderLanguage]);
            }

            if ($target['type'] === 'content' && isset($target['content_slug'])) {
                $slug = (string) $target['content_slug'];
                $localizedRows = $this->exactLocalizedContent($this->renderLanguage);
                $hasExact = isset($localizedRows[$slug]);
                $url = $this->contentUrl([
                    'slug' => $slug,
                    'page' => ($target['content_type'] ?? 'post') === 'page',
                    'language' => $hasExact
                        ? $this->renderLanguage
                        : $this->defaultLanguage,
                    'is_fallback' => !$hasExact
                        && $this->renderLanguage !== $this->defaultLanguage,
                ]);
            } elseif ($target['type'] === 'custom' && isset($target['url'])) {
                $url = PreviewUrl::appendPreviewSiteQuery(
                    (string) $target['url'],
                    $this->siteId,
                    $this->isStatic()
                );
            } elseif ($target['type'] === 'system' && isset($target['content_slug'])) {
                $url = $this->systemUrl((string) $target['content_slug']);
                if ($url === '' && !empty($target['url'])) {
                    $url = PreviewUrl::appendPreviewSiteQuery(
                        (string) $target['url'],
                        $this->siteId,
                        $this->isStatic()
                    );
                }
            } elseif ($target['type'] === 'taxonomy' && isset($target['content_slug'])) {
                // content_slug is "{vocab}/{term}" — category archives key off the term leaf.
                require_once __DIR__ . '/TaxonomySlug.php';
                $slug = TaxonomySlug::termToCategorySlug($target['content_slug']);
                if ($slug !== '') {
                    $url = $this->archiveUrl($slug);
                } elseif (!empty($target['url'])) {
                    $url = PreviewUrl::appendPreviewSiteQuery(
                        (string) $target['url'],
                        $this->siteId,
                        $this->isStatic()
                    );
                }
            }

            $itemsById[$item['id']] = [
                'id' => $item['id'],
                'label' => $label,
                'url' => $url,
                'open_in_new_tab' => (bool)($item['open_in_new_tab'] ?? false),
                'target_type' => $target['type'],
                'parent_id' => $item['parent_id'] ?? null,
                'children' => []
            ];
        }

        $rootItems = [];
        foreach ($itemsById as $id => &$item) {
            $parentId = $item['parent_id'];
            if ($parentId !== null && isset($itemsById[$parentId])) {
                $itemsById[$parentId]['children'][] = &$item;
            } else {
                $rootItems[] = &$item;
            }
        }
        unset($item);

        return $rootItems;
    }
}
