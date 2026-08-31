<?php

namespace Dossier;

/**
 * Resolves [expand]/[embed] targets for the active site.
 *
 * Returns rendered HTML for a published post (optionally sliced by heading,
 * or frontmatter summary/deck when source=summary|deck), or null when the
 * slug is missing / unpublished / empty chosen field (reader-facing silent omit).
 * Heading-not-found falls back to the whole post body (summary/deck do not).
 */
class ExpandResolver {
    /** @var InternalAPIClient */
    private $api;
    /** @var string|null */
    private $language;
    /** @var string */
    private $readMore;
    /** @var int */
    private static $depth = 0;
    private const MAX_DEPTH = 2;

    public function __construct(
        ?InternalAPIClient $api = null,
        ?string $language = null,
        string $readMore = 'Read more'
    ) {
        $this->api = $api ?? new InternalAPIClient();
        $this->language = $language !== null && trim($language) !== ''
            ? strtolower(str_replace('_', '-', trim($language)))
            : null;
        $this->readMore = trim($readMore) !== '' ? $readMore : 'Read more';
    }

    /**
     * @param string $slug
     * @param string|null $heading
     * @param string $mode 'expand'|'embed'
     * @param string|null $source 'summary'|'deck' for frontmatter nutshell; null/omitted = body
     * @return string|null HTML body or null if not found
     */
    public function resolve(string $slug, ?string $heading = null, string $mode = 'expand', ?string $source = null): ?string {
        $slug = trim($slug);
        if ($slug === '') {
            return null;
        }

        if (self::$depth >= self::MAX_DEPTH) {
            return null;
        }

        try {
            $params = ['include_partials' => true, 'live_only' => true];
            if ($this->language !== null) {
                $params['language'] = $this->language;
            }
            $page = $this->api->get("/pages/{$slug}", $params);
        } catch (\Exception $e) {
            return null;
        }

        $fm = $page['frontmatter'] ?? [];
        $status = strtolower((string)($fm['status'] ?? 'published'));
        if ($status !== 'published') {
            return null;
        }

        // live_only-style: skip future publish_at
        $publishAt = $fm['publish_at'] ?? null;
        if ($publishAt) {
            $ts = strtotime((string)$publishAt);
            if ($ts !== false && $ts > time()) {
                return null;
            }
        }

        // source=summary|deck: frontmatter nutshell + Read more CTA (no whole-post / cross-field fallback)
        if ($source === 'summary' || $source === 'deck') {
            $field = trim((string)($fm[$source] ?? ''));
            if ($field === '') {
                return null;
            }

            self::$depth++;
            try {
                $renderer = new PostRenderer($this->api);
                $html = $renderer->renderMarkdownFragment($field);
                return $this->appendReadMore($html, $slug);
            } finally {
                self::$depth--;
            }
        }

        $markdown = trim((string)($page['content'] ?? ''));

        // Composite: also consider named partials as heading targets
        if ($heading && !empty($page['composite']) && !empty($page['partials']) && is_array($page['partials'])) {
            $partialMd = $this->findPartialByHeading($page, $heading);
            if ($partialMd !== null) {
                $markdown = $partialMd;
                $heading = null; // already selected fragment
            }
        }

        if ($heading) {
            $sliced = $this->sliceByHeading($markdown, $heading);
            // Product default: heading miss → whole post
            if ($sliced !== null) {
                $markdown = $sliced;
            }
        }

        if ($markdown === '') {
            return null;
        }

        self::$depth++;
        try {
            $renderer = new PostRenderer($this->api);
            // Use reflection-free path: render via a public-friendly helper
            return $renderer->renderMarkdownFragment($markdown);
        } finally {
            self::$depth--;
        }
    }

    /**
     * Inject inline Read more CTA (same line as last paragraph when present).
     */
    private function appendReadMore(string $html, string $slug): string {
        $href = htmlspecialchars(
            ShortcodeProcessor::resolveContentUrl($slug),
            ENT_QUOTES,
            'UTF-8'
        );
        $readMore = ' <a class="traven-expand-read-more" href="' . $href
            . '" target="_blank" rel="noopener">'
            . htmlspecialchars($this->readMore, ENT_QUOTES, 'UTF-8')
            . '</a>';
        if (preg_match('/<\/p>\s*$/i', $html)) {
            return preg_replace('/<\/p>\s*$/i', $readMore . '</p>', $html, 1) ?? ($html . $readMore);
        }
        return $html . $readMore;
    }

    /**
     * Display title for expand link labels when text/heading are omitted.
     * Prefers hero_title → name → title from published frontmatter.
     *
     * @param string $slug
     * @return string|null
     */
    public function resolveDisplayTitle(string $slug): ?string {
        $slug = trim($slug);
        if ($slug === '') {
            return null;
        }

        try {
            $params = ['live_only' => true];
            if ($this->language !== null) {
                $params['language'] = $this->language;
            }
            $page = $this->api->get("/pages/{$slug}", $params);
        } catch (\Exception $e) {
            return null;
        }

        $fm = $page['frontmatter'] ?? [];
        $status = strtolower((string)($fm['status'] ?? 'published'));
        if ($status !== 'published') {
            return null;
        }

        $publishAt = $fm['publish_at'] ?? null;
        if ($publishAt) {
            $ts = strtotime((string)$publishAt);
            if ($ts !== false && $ts > time()) {
                return null;
            }
        }

        foreach (['hero_title', 'name', 'title'] as $key) {
            $val = trim((string)($fm[$key] ?? ''));
            if ($val !== '') {
                return $val;
            }
        }

        return null;
    }

    /**
     * Match a composite partial by id or title (case-insensitive).
     */
    private function findPartialByHeading(array $page, string $heading): ?string {
        $needle = $this->normalizeHeading($heading);
        $fm = $page['frontmatter'] ?? [];
        $posts = $fm['posts'] ?? [];
        if (!is_array($posts)) {
            return null;
        }
        foreach ($posts as $postData) {
            $id = (string)($postData['id'] ?? '');
            if ($id === '' || $id === 'index') {
                continue;
            }
            $title = (string)($postData['title'] ?? $id);
            if ($this->normalizeHeading($id) === $needle || $this->normalizeHeading($title) === $needle) {
                return trim((string)($page['partials'][$id] ?? ''));
            }
        }
        return null;
    }

    /**
     * Extract markdown from a heading through the next same-or-higher-level heading.
     * @return string|null
     */
    private function sliceByHeading(string $markdown, string $heading): ?string {
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

    private function normalizeHeading(string $text): string {
        $t = strtolower(trim($text));
        $t = preg_replace('/[^\p{L}\p{N}\s-]+/u', '', $t) ?? $t;
        $t = preg_replace('/\s+/', '-', trim($t)) ?? $t;
        return $t;
    }
}
