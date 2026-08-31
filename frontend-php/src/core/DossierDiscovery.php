<?php

namespace Dossier;

require_once __DIR__ . '/../../vendor/autoload.php';
require_once __DIR__ . '/InternalAPIClient.php';
require_once __DIR__ . '/TaxonomySlug.php';

use Spatie\YamlFrontMatter\YamlFrontMatter;

class DossierDiscovery
{
    private $api;

    public function __construct(?InternalAPIClient $api = null)
    {
        $this->api = $api ?? new InternalAPIClient();
    }

    /**
     * Fetch all publishable dossiers via the API.
     */
    public function getAllDossiers(
        $filterDomain = 'blog',
        $includePages = false,
        ?string $language = null,
        string $fallback = 'none'
    )
    {
        try {
            // Fetch only published pages for the specified domain
            $params = [
                'status' => 'published',
                'domain' => $filterDomain,
                'live_only' => 'true',
            ];
            if ($language !== null && $language !== '') {
                $params['language'] = $language;
                $params['fallback'] = $fallback;
            }
            $pages = $this->api->get('/pages/', $params);

            // Build a slug → raw-content lookup from the already-fetched
            // pages so computeReadingTime can resolve [embed] without extra
            // API calls.
            $contentBySlug = [];
            foreach ($pages as $p) {
                $contentBySlug[$p['id']] = trim((string) ($p['content'] ?? ''));
            }

            $dossiers = [];
            foreach ($pages as $page) {
                $fm = $page['frontmatter'];

                $isPage = !empty($fm['page']) && ($fm['page'] === true || $fm['page'] === 'true' || $fm['page'] === 1 || $fm['page'] === '1');
                if (!$includePages && $isPage) {
                    continue;
                }

                // Handle taxonomy_ prefixed keys by copying them to unprefixed keys for template compatibility.
                // Also collect every taxonomy assignment for category-archive matching.
                $taxonomyLabels = [];
                foreach ($fm as $key => $val) {
                    if (strpos($key, 'taxonomy_') === 0) {
                        $unprefixed = substr($key, 9);
                        $fm[$unprefixed] = $val;
                        if (is_string($val) && trim($val) !== '') {
                            $taxonomyLabels[] = trim($val);
                        }
                    }
                }

                $heroImage = $fm['hero_image'] ?? 'images/defaulthero.jpg';
                if (!empty($heroImage) && $heroImage !== 'images/defaulthero.jpg') {
                    if (!$this->api->assetExists($heroImage)) {
                        $heroImage = 'images/defaulthero.jpg';
                    }
                }

                // Parse and collect all tags/metadata across top-level and fragments
                $tags = [];
                if (!empty($fm['tags']) && is_array($fm['tags'])) {
                    foreach ($fm['tags'] as $t) {
                        if (is_array($t) && !empty($t['label'])) {
                            $tags[] = $t['label'];
                        } elseif (is_string($t)) {
                            $tags[] = $t;
                        }
                    }
                }

                $metadata = [];
                if (!empty($fm['metadata']) && is_array($fm['metadata'])) {
                    foreach ($fm['metadata'] as $m) {
                        $metadata[] = trim(str_replace('//', '', $m));
                    }
                }

                if (!empty($fm['articles']) && empty($fm['posts'])) {
                    $fm['posts'] = $fm['articles'];
                }

                if (!empty($fm['posts']) && is_array($fm['posts'])) {
                    foreach ($fm['posts'] as $art) {
                        if (!empty($art['tags']) && is_array($art['tags'])) {
                            foreach ($art['tags'] as $t) {
                                if (is_array($t) && !empty($t['label'])) {
                                    $tags[] = $t['label'];
                                } elseif (is_string($t)) {
                                    $tags[] = $t;
                                }
                            }
                        }
                        if (!empty($art['metadata']) && is_array($art['metadata'])) {
                            foreach ($art['metadata'] as $m) {
                                $metadata[] = trim(str_replace('//', '', $m));
                            }
                        }
                    }
                }

                $tags = array_values(array_unique(array_filter($tags)));
                $metadata = array_values(array_unique(array_filter($metadata)));

                $categoryRaw = trim((string) ($fm['category'] ?? $fm['type'] ?? 'event'));
                $categoryVal = strtolower($categoryRaw);

                // Primary category + all taxonomy_* terms → flat archive slugs (nav-compatible).
                $termLabels = [];
                $allTermLabels = array_merge([$categoryRaw], $taxonomyLabels);
                foreach ($allTermLabels as $label) {
                    if ($label === '') {
                        continue;
                    }
                    $slug = TaxonomySlug::termToCategorySlug($label);
                    if ($slug === '') {
                        continue;
                    }
                    if (!isset($termLabels[$slug])) {
                        $termLabels[$slug] = $label;
                        // Prefer hierarchical leaf as display label when present
                        if (($sep = strrpos($label, ' / ')) !== false) {
                            $termLabels[$slug] = substr($label, $sep + 3);
                        }
                    }
                }
                $termSlugs = array_keys($termLabels);

                // Map API response to the format expected by the blog templates
                $dossier = [
                    'section' => $categoryVal,
                    'category' => $categoryVal,
                    'term_slugs' => $termSlugs,
                    'term_labels' => $termLabels,
                    'slug' => $page['id'],
                    'domain' => $fm['domain'] ?? 'blog',
                    'composite' => $page['composite'] ?? false,
                    'title' => $fm['title'] ?? $fm['name'] ?? ucfirst($page['id']),
                    'hero_title' => $fm['hero_title'] ?? $fm['title'] ?? $fm['name'] ?? ucfirst($page['id']),
                    'hero_image' => $heroImage,
                    'deck' => $fm['deck'] ?? '',
                    'date' => $fm['date'] ?? '',
                    'trumpet' => $fm['trumpet'] ?? '',
                    'tags' => $tags,
                    'metadata' => $metadata,
                    'page' => $isPage,
                    'author' => $fm['author'] ?? $fm['byline'] ?? null,
                    'reading_time' => $this->computeReadingTime($fm, $page, $contentBySlug),
                    'pinned' => !empty($fm['pinned']),
                    'noindex' => self::isNoindex($fm),
                ];
                if ($language !== null && $language !== '') {
                    $dossier['language'] = $page['language'] ?? $language;
                    $dossier['is_fallback'] = (bool) ($page['is_fallback'] ?? false);
                }
                $dossiers[] = $dossier;
            }

            // Merged localized rows already arrive in the default-row skeleton
            // order. Re-sorting by translated dates would move substitutions.
            if ($language === null || $language === '' || $fallback !== 'default') {
                usort($dossiers, function ($a, $b) {
                    $pinDiff = (int) !empty($b['pinned']) <=> (int) !empty($a['pinned']);
                    if ($pinDiff !== 0) {
                        return $pinDiff;
                    }
                    return strtotime($b['date']) <=> strtotime($a['date']);
                });
            }

            return $dossiers;

        } catch (\Exception $e) {
            error_log("DossierDiscovery Error: " . $e->getMessage());
            return [];
        }
    }

    /**
     * Frontmatter or discovery-row noindex (posts and pages).
     */
    public static function isNoindex(array $item): bool
    {
        $raw = $item['noindex'] ?? null;
        return $raw === true
            || $raw === 1
            || $raw === '1'
            || (is_string($raw) && strtolower(trim($raw)) === 'true');
    }

    /**
     * Compute a human-readable reading time string for a dossier.
     *
     * Uses an explicit frontmatter value when present; otherwise estimates
     * from the page's markdown content at ~200 words per minute.
     */
    private function computeReadingTime(array $fm, array $page, array $contentBySlug = []): string
    {
        // Honour explicit frontmatter overrides
        $explicit = $fm['reading_time'] ?? $fm['read_time'] ?? null;
        if ($explicit !== null && trim((string) $explicit) !== '') {
            return (string) $explicit;
        }

        $text = trim((string) ($page['content'] ?? ''));
        if ($text === '') {
            return '1 MIN READ';
        }

        // Strip [expand …] markers entirely — that content is lazy-loaded
        // behind a click and shouldn't count toward reading time.
        $text = preg_replace('/\[expand\s+[^\]]*\]/i', '', $text);

        // Resolve [embed slug="…"] markers: look up each embedded page's
        // raw markdown from the pre-built map (zero extra API calls).
        // When a heading="…" attribute is present, slice to just that
        // section — mirrors ExpandResolver::sliceByHeading().
        $text = preg_replace_callback('/\[embed\s+([^\]]*)\]/i', function ($m) use ($contentBySlug) {
            $attrStr = $m[1];
            if (!preg_match('/slug\s*=\s*["\']?([^\s"\']+)/i', $attrStr, $sm)) {
                return '';
            }
            $slug = trim($sm[1], "\"' ");
            if (!isset($contentBySlug[$slug])) {
                return '';
            }
            $body = $contentBySlug[$slug];

            // Heading-aware slicing
            $heading = null;
            if (preg_match('/heading\s*=\s*"([^"]*)"/i', $attrStr, $hm)) {
                $heading = trim($hm[1]);
            } elseif (preg_match('/heading\s*=\s*\'([^\']*)\'/i', $attrStr, $hm)) {
                $heading = trim($hm[1]);
            }
            if ($heading !== null && $heading !== '') {
                $sliced = $this->sliceMarkdownByHeading($body, $heading);
                if ($sliced !== null) {
                    $body = $sliced;
                }
            }

            return ' ' . $body;
        }, $text);

        // Strip any residual HTML / shortcode syntax, then count words
        $plain = strip_tags($text);
        $wordCount = str_word_count($plain);
        $mins = (int) ceil($wordCount / 200);
        if ($mins < 1) {
            $mins = 1;
        }

        return $mins . ' MIN READ';
    }

    /**
     * Extract the markdown section under a specific heading, through to the
     * next same-or-higher-level heading.  Mirrors ExpandResolver::sliceByHeading().
     *
     * @return string|null  The sliced markdown, or null if the heading wasn't found.
     */
    private function sliceMarkdownByHeading(string $markdown, string $heading): ?string
    {
        $needle = $this->normalizeHeading($heading);
        $lines = preg_split('/\R/', $markdown) ?: [];
        $start = -1;
        $level = 0;

        foreach ($lines as $i => $line) {
            if (preg_match('/^(#{1,6})\s+(.+?)\s*$/', $line, $m)) {
                if ($this->normalizeHeading($m[2]) === $needle) {
                    $start = $i;
                    $level = strlen($m[1]);
                    break;
                }
            }
        }
        if ($start < 0) {
            return null;
        }

        $end = count($lines);
        for ($j = $start + 1; $j < count($lines); $j++) {
            if (preg_match('/^(#{1,6})\s+/', $lines[$j], $m)) {
                if (strlen($m[1]) <= $level) {
                    $end = $j;
                    break;
                }
            }
        }

        return trim(implode("\n", array_slice($lines, $start, $end - $start)));
    }

    private function normalizeHeading(string $text): string
    {
        $t = strtolower(trim($text));
        $t = preg_replace('/[^\p{L}\p{N}\s-]+/u', '', $t) ?? $t;
        $t = preg_replace('/\s+/', '-', trim($t)) ?? $t;
        return $t;
    }
}
