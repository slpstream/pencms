<?php

namespace Dossier;

require_once __DIR__ . '/DossierDiscovery.php';

/**
 * Builds a client-side search index (JSON array) for MiniSearch.
 *
 * Includes published posts and pages. Body is plain text truncated to BODY_MAX.
 */
class SearchIndexBuilder
{
    public const BODY_MAX = 2000;
    public const EXCERPT_MAX = 200;

    /**
     * Build one index document from discovery metadata + Markdown body text.
     *
     * @param array  $dossier  Item from DossierDiscovery (includePages = true)
     * @param string $markdown Markdown to index (content + partials; agent wrappers OK)
     * @param string|null $languageWhenMissing Active-site default language metadata.
     */
    public static function documentFromDossier(
        array $dossier,
        string $markdown = '',
        ?string $resolvedUrl = null,
        ?string $languageWhenMissing = null
    ): ?array
    {
        $slug = (string)($dossier['slug'] ?? '');
        if ($slug === '' || DossierDiscovery::isNoindex($dossier)) {
            return null;
        }

        $isPage = !empty($dossier['page']);
        $title = (string)($dossier['hero_title'] ?? $dossier['title'] ?? $slug);
        $deck = strip_tags((string)($dossier['deck'] ?? ''));
        $bodyPlain = self::markdownToPlainText($markdown);

        $excerpt = self::truncate(trim($deck), self::EXCERPT_MAX);
        if ($excerpt === '' && $bodyPlain !== '') {
            $excerpt = self::truncate($bodyPlain, self::EXCERPT_MAX);
        }

        $tags = [];
        foreach ($dossier['tags'] ?? [] as $t) {
            if (is_string($t) && $t !== '') {
                $tags[] = $t;
            } elseif (is_array($t) && !empty($t['label'])) {
                $tags[] = (string)$t['label'];
            }
        }
        $tags = array_values(array_unique($tags));

        $categories = [];
        foreach ($dossier['term_labels'] ?? [] as $label) {
            if (is_string($label) && trim($label) !== '') {
                $categories[] = trim($label);
            }
        }
        if ($categories === [] && !empty($dossier['category'])) {
            $categories[] = (string)$dossier['category'];
        }
        $categories = array_values(array_unique($categories));

        $document = [
            'id' => $slug,
            'title' => $title,
            'url' => $resolvedUrl ?? (string) ($dossier['url'] ?? ('/' . $slug . '/')),
            'type' => $isPage ? 'page' : 'post',
            'excerpt' => $excerpt,
            'body' => self::truncate($bodyPlain, self::BODY_MAX),
            'tags' => $tags,
            'categories' => $categories,
            'pinned' => !empty($dossier['pinned']),
        ];
        if (isset($dossier['language']) && is_string($dossier['language'])) {
            $document['lang'] = $dossier['language'];
        } elseif ($languageWhenMissing !== null && $languageWhenMissing !== '') {
            $document['lang'] = $languageWhenMissing;
        }
        return $document;
    }

    /**
     * Build index documents for all dossiers, loading Markdown from the API.
     *
     * @param array $dossiers From DossierDiscovery::getAllDossiers('blog', true)
     * @param string|null $languageWhenMissing Active-site default language metadata.
     * @return array<int, array>
     */
    public static function buildFromDossiers(
        array $dossiers,
        $renderer = null,
        ?callable $urlResolver = null,
        ?string $languageWhenMissing = null
    ): array
    {
        require_once __DIR__ . '/PostRenderer.php';
        $renderer = $renderer ?? new PostRenderer();
        $docs = [];

        foreach ($dossiers as $d) {
            $slug = (string)($d['slug'] ?? '');
            if ($slug === '') {
                continue;
            }
            $section = (string)($d['section'] ?? 'blog');
            try {
                if (isset($d['language']) && is_string($d['language'])) {
                    $markdown = $renderer->renderMarkdown(
                        $section,
                        $slug,
                        $d['language'],
                        true
                    );
                } else {
                    $markdown = $renderer->renderMarkdown($section, $slug);
                }
            } catch (\Exception $e) {
                $markdown = '';
            }
            $resolvedUrl = $urlResolver !== null
                ? (string) $urlResolver($d)
                : null;
            $doc = self::documentFromDossier(
                $d,
                $markdown,
                $resolvedUrl,
                $languageWhenMissing
            );
            if ($doc !== null) {
                $docs[] = $doc;
            }
        }

        return $docs;
    }

    /**
     * @param array<int, array> $docs
     */
    public static function toJson(array $docs): string
    {
        $json = json_encode($docs, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
        if ($json === false) {
            return '[]';
        }
        // Safe to embed in <script type="application/json">
        return str_replace('</', '<\/', $json);
    }

    /**
     * Rough Markdown → plain text for indexing (not a full MD parser).
     */
    public static function markdownToPlainText(string $markdown): string
    {
        $text = $markdown;

        // Strip YAML frontmatter
        if (preg_match('/\A---\r?\n.*?\r?\n---\r?\n/s', $text, $m)) {
            $text = substr($text, strlen($m[0]));
        }

        // Strip shortcodes like [shortcode ...]...[/shortcode] and {{ ... }}
        $text = preg_replace('/\{\{[^}]*\}\}/', ' ', $text) ?? $text;
        $text = preg_replace('/\[[^\]]+\]/', ' ', $text) ?? $text;

        // Images / links → alt or link text
        $text = preg_replace('/!\[([^\]]*)\]\([^)]+\)/', '$1', $text) ?? $text;
        $text = preg_replace('/\[([^\]]+)\]\([^)]+\)/', '$1', $text) ?? $text;

        // Headings, emphasis, code fences, inline code, blockquotes
        $text = preg_replace('/^#{1,6}\s+/m', '', $text) ?? $text;
        $text = preg_replace('/^>\s?/m', '', $text) ?? $text;
        $text = preg_replace('/```[\s\S]*?```/', ' ', $text) ?? $text;
        $text = preg_replace('/`([^`]+)`/', '$1', $text) ?? $text;
        $text = preg_replace('/(\*\*|__)(.*?)\1/', '$2', $text) ?? $text;
        $text = preg_replace('/(\*|_)(.*?)\1/', '$2', $text) ?? $text;

        // HTML tags if any
        $text = strip_tags($text);
        $text = html_entity_decode($text, ENT_QUOTES | ENT_HTML5, 'UTF-8');

        // Collapse whitespace
        $text = preg_replace('/[ \t]+/', ' ', $text) ?? $text;
        $text = preg_replace('/\n{3,}/', "\n\n", $text) ?? $text;

        return trim($text);
    }

    private static function truncate(string $text, int $max): string
    {
        if ($max <= 0 || mb_strlen($text) <= $max) {
            return $text;
        }
        return rtrim(mb_substr($text, 0, $max));
    }
}
