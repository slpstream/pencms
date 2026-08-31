<?php

namespace Dossier;

require_once __DIR__ . '/../../vendor/autoload.php';
require_once __DIR__ . '/ShortcodeProcessor.php';
require_once __DIR__ . '/PreviewUrl.php';
require_once __DIR__ . '/template-helpers.php';
require_once __DIR__ . '/InternalAPIClient.php';
require_once __DIR__ . '/DossierDiscovery.php';

use League\CommonMark\GithubFlavoredMarkdownConverter;
use Spatie\YamlFrontMatter\YamlFrontMatter;
use Symfony\Component\Yaml\Yaml;

class PostRenderer {
    private $converter;
    private $api;
    private bool $commentsEnabled;

    public function __construct(?InternalAPIClient $api = null, bool $commentsEnabled = false) {
        $this->api = $api ?? new InternalAPIClient();
        $this->commentsEnabled = $commentsEnabled;
        $this->converter = new GithubFlavoredMarkdownConverter([
            'html_input' => 'allow',
            'allow_unsafe_links' => false,
            'disallowed_raw_html' => [
                'disallowed_tags' => [],
            ],
        ]);
    }

    /**
     * Renders a full dossier page based on a section and slug.
     */
    public function renderPage(
        $section,
        $slug,
        ?string $language = null,
        bool $publicOnly = false
    ) {
        $params = ['include_partials' => true];
        if ($language !== null && $language !== '') {
            $params['language'] = $language;
        }
        if ($publicOnly) {
            $params['live_only'] = true;
        }
        try {
            $page = $this->api->get("/pages/{$slug}", $params);
        } catch (\Exception $e) {
            throw new \Exception("Dossier not found: {$slug} (" . $e->getMessage() . ")");
        }

        $data = $page['frontmatter'];
        $actualLanguage = $page['language'] ?? ($data['language'] ?? $language);
        if (!is_string($actualLanguage) || trim($actualLanguage) === '') {
            $actualLanguage = null;
        }
        ShortcodeProcessor::setLanguage($actualLanguage);
        $isComposite = $page['composite'] ?? false;
        
        $posts = [];

        // 1. Process main content
        $bodyContent = trim($page['content'] ?? '');
        if (!empty($bodyContent)) {
            $html = $this->renderHtml($bodyContent);
            if (!empty($data['is_legacy'])) {
                $html = preg_replace('/^<h1>.*?<\/h1>\s*/s', '', $html, 1);
            }
            
            // Retrieve metadata/tags for the index entry
            $indexEntry = null;
            if (isset($data['posts']) && is_array($data['posts'])) {
                foreach ($data['posts'] as $a) {
                    if (($a['id'] ?? '') === 'index') {
                        $indexEntry = $a;
                        break;
                    }
                }
            }

            $indexMetadata = [];
            if (!empty($indexEntry['metadata']) && is_array($indexEntry['metadata'])) {
                $indexMetadata = array_map(function($m) {
                    return trim(str_replace('//', '', $m));
                }, $indexEntry['metadata']);
            }
            $indexTags = $indexEntry['tags'] ?? ($data['tags'] ?? []);

            $posts[] = [
                'id'           => $isComposite ? 'intro' : 'main',
                'title'        => '',
                'content_html' => $html,
                'metadata'     => $indexMetadata,
                'tags'         => $indexTags,
            ];
        }

        // 2. Process additional posts if composite
        if ($isComposite && isset($data['posts']) && is_array($data['posts'])) {
            foreach ($data['posts'] as $postData) {
                if (($postData['id'] ?? '') === 'index') continue;

                $partialId = $postData['id'];
                $rawMarkdown = $page['partials'][$partialId] ?? '';
                
                if (!empty($rawMarkdown)) {
                    $postData['content_html'] = $this->renderHtml($rawMarkdown);

                    if (isset($postData['trumpet'])) {
                        $postData['trumpet'] = $this->renderPlainHtml($postData['trumpet']);
                    }

                    if (isset($postData['metadata']) && is_array($postData['metadata'])) {
                        $postData['metadata'] = array_map(function($m) {
                            return trim(str_replace('//', '', $m));
                        }, $postData['metadata']);
                    }

                    if (isset($postData['title'])) {
                        $postData['title'] = smart_title_case($postData['title']);
                    }
                    $posts[] = $postData;
                }
            }
        }

        $deckHtml = $this->renderPlainHtml($data['deck'] ?? '');
        $trumpetHtml = $this->renderPlainHtml($data['trumpet'] ?? '');

        $isPage = !empty($data['page']) && ($data['page'] === true || $data['page'] === 'true');
        $heroImage = $data['hero_image'] ?? ($isPage ? '' : 'images/defaulthero.jpg');
        if (!empty($heroImage) && $heroImage !== 'images/defaulthero.jpg') {
            if (!$this->api->assetExists($heroImage)) {
                $heroImage = $isPage ? '' : 'images/defaulthero.jpg';
            }
        }

        // Compute reading time from assembled HTML.
        // Strip <template> blocks (expand content — lazy-loaded, not part of
        // the visible article) before counting.  Embed content lives in plain
        // <div> wrappers and IS visible, so it naturally remains.
        $readingMinutes = null;
        $readingTime = $this->computeReadingTime($data, $posts, $readingMinutes);
        $translations = isset($page['translations']) && is_array($page['translations'])
            ? $page['translations']
            : [];
        $currentTranslationLive = ($data['status'] ?? 'published') === 'published';
        if ($currentTranslationLive && !empty($data['publish_at'])) {
            $publishAt = strtotime((string) $data['publish_at']);
            $currentTranslationLive = $publishAt !== false && $publishAt <= time();
        }

        return [
            'is_composite' => (count($posts) > 1),
            'is_page' => $isPage,
            'language' => $actualLanguage,
            'translation_group' => $page['translation_group'] ?? null,
            'translations' => $translations,
            'i18n_current_live' => $currentTranslationLive,
            'hero_image' => $heroImage,
            'hero_title' => smart_title_case($data['hero_title'] ?? ($data['title'] ?? 'Untitled Dossier')),
            'name' => (string) ($data['name'] ?? $data['title'] ?? $slug),
            'category' => $data['category'] ?? $data['type'] ?? null,
            'deck' => $deckHtml,
            'faqs' => $this->normalizeFaqs($data['faqs'] ?? []),
            'trumpet' => $trumpetHtml,
            'posts' => $posts,
            'reading_time' => $readingTime,
            'reading_minutes' => $readingMinutes,
            'date' => $data['date'] ?? null,
            'updated' => $data['updated'] ?? null,
            'modified_at' => $page['modified_at'] ?? null,
            'author' => $data['author'] ?? null,
            'dateline' => isset($data['date']) ? date("F d, Y", strtotime($data['date'])) : null,
            'noindex' => DossierDiscovery::isNoindex($data),
            'comments' => $this->fetchVisibleComments((string) $slug),
            'seo' => [
                'title' => smart_title_case($data['title'] ?? ($data['name'] ?? ($data['hero_title'] ?? ($data['headline'] ?? 'Dossier')))),
                'og_title' => smart_title_case($data['og_title'] ?? ($data['hero_title'] ?? ($data['title'] ?? ($data['name'] ?? 'Dossier')))),
                'og_description' => $data['og_description'] ?? strip_tags($deckHtml),
                'og_image' => $data['og_image'] ?? ($data['hero_image'] ?? $heroImage),
            ]
        ];
    }

    /**
     * Compute a human-readable reading time string for a rendered post.
     *
     * Respects explicit frontmatter overrides (reading_time / read_time).
     * Otherwise estimates from the assembled HTML at ~200 WPM, stripping
     * <template> blocks (expand/nutshell content that is lazy-loaded behind
     * a click) so only inline visible text is counted.
     */
    private function computeReadingTime(
        array $fm,
        array $posts,
        ?int &$minutes = null
    ): string
    {
        // Honour explicit frontmatter overrides
        $explicit = $fm['reading_time'] ?? $fm['read_time'] ?? null;
        if ($explicit !== null && trim((string) $explicit) !== '') {
            $minutes = null;
            return (string) $explicit;
        }

        // Concatenate all rendered post HTML
        $allHtml = '';
        foreach ($posts as $p) {
            $allHtml .= ' ' . ($p['content_html'] ?? '');
        }

        // Strip <template>…</template> blocks (expand content — not visible
        // until the reader clicks, analogous to external links).
        $allHtml = preg_replace('/<template\b[^>]*>.*?<\/template>/is', '', $allHtml);

        // Strip remaining HTML tags and count words
        $plain = trim(strip_tags($allHtml));
        $wordCount = str_word_count($plain);
        $mins = (int) ceil($wordCount / 200);
        if ($mins < 1) {
            $mins = 1;
        }

        $minutes = $mins;
        return $mins . ' MIN READ';
    }

    /**
     * Frontmatter `faqs: [{q, a}]` → list of non-empty string pairs.
     * Empty list is valid. Incomplete rows are dropped.
     *
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
     * Visible comments for the public thread. Failures return [] so a comments
     * outage never 404s the article. Pending/hidden are filtered by the API.
     *
     * @return list<array{slug:string,author_name:string,author_kind:string,body:string,in_reply_to:?string,received_at:string}>
     */
    private function fetchVisibleComments(string $slug): array
    {
        if (!$this->commentsEnabled || $slug === '') {
            return [];
        }
        try {
            $payload = $this->api->get('/v1/comments', ['post_slug' => $slug]);
        } catch (\Exception $e) {
            return [];
        }
        $rows = is_array($payload) ? ($payload['comments'] ?? []) : [];
        if (!is_array($rows)) {
            return [];
        }
        $out = [];
        foreach ($rows as $row) {
            if (!is_array($row)) {
                continue;
            }
            $reply = $row['in_reply_to'] ?? null;
            if ($reply === '' || $reply === false) {
                $reply = null;
            } elseif ($reply !== null) {
                $reply = (string) $reply;
            }
            $out[] = [
                'slug' => (string) ($row['slug'] ?? ''),
                'author_name' => (string) ($row['author_name'] ?? 'Anonymous'),
                'author_kind' => (string) ($row['author_kind'] ?? 'public'),
                'body' => (string) ($row['body'] ?? ''),
                'in_reply_to' => $reply,
                'received_at' => (string) ($row['received_at'] ?? ''),
            ];
        }
        return $out;
    }

    /**
     * Renders a full dossier page as a single Markdown string for AI agents.
     */
    public function renderMarkdown(
        $section,
        $slug,
        ?string $language = null,
        bool $publicOnly = false
    ) {
        $params = ['include_partials' => true];
        if ($language !== null && $language !== '') {
            $params['language'] = $language;
        }
        if ($publicOnly) {
            $params['live_only'] = true;
        }
        try {
            $page = $this->api->get("/pages/{$slug}", $params);
        } catch (\Exception $e) {
            throw new \Exception("Dossier not found: {$slug}");
        }

        $data = $page['frontmatter'];
        $isComposite = $page['composite'] ?? false;

        $markdown = [];

        // Simple Frontmatter for agents
        $markdown[] = "---";
        $markdown[] = "title: " . ($data['title'] ?? $page['id']);
        $markdown[] = "date: " . ($data['date'] ?? 'unknown');
        $markdown[] = "---";
        $markdown[] = "";

        $title = smart_title_case($data['hero_title'] ?? ($data['title'] ?? 'Untitled Dossier'));
        $markdown[] = "# {$title}\n";

        if (!empty($data['deck'])) {
            $markdown[] = "> {$data['deck']}\n";
        }

        $markdown[] = trim($page['content'] ?? '') . "\n";

        if ($isComposite && isset($data['posts']) && is_array($data['posts'])) {
            foreach ($data['posts'] as $postData) {
                if (($postData['id'] ?? '') === 'index') continue;
                
                $partialId = $postData['id'];
                if (!empty($postData['title'])) {
                    $markdown[] = "## {$postData['title']}\n";
                }
                $markdown[] = trim($page['partials'][$partialId] ?? '') . "\n";
            }
        }

        $finalMarkdown = implode("\n", $markdown);
        $finalMarkdown = $this->transcodeLegacyLinks($finalMarkdown);
        return ShortcodeProcessor::processForMarkdown($finalMarkdown);
    }

    private function restoreMath($html, $placeholders) {
        if (empty($placeholders)) return $html;
        $keys = array_keys($placeholders);
        $vals = array_values($placeholders);
        return str_replace($keys, $vals, $html);
    }

    /**
     * Add classic-markdown class to CommonMark <img> tags and, for block images
     * with caption-worthy alt text, wrap as figure + figcaption.caption (matches
     * Traven WYSIWYM alt-as-caption UX; shortcodes run later and are untouched).
     */
    private function enhanceClassicMarkdownImages($html) {
        // Block images: CommonMark wraps lone images in <p> — replace the paragraph
        // so we never nest <figure> inside <p>.
        $html = preg_replace_callback(
            '/<p>\s*(<img\b[^>]*>)\s*<\/p>/is',
            function ($matches) {
                return $this->formatClassicMarkdownImage($matches[1], true);
            },
            $html
        );

        // Remaining imgs (e.g. inline): class only — no figure wrap (invalid inside <p>).
        $html = preg_replace_callback(
            '/<img\b[^>]*>/i',
            function ($matches) {
                $img = $matches[0];
                if (preg_match('/\bclassic-markdown\b/', $img)) {
                    return $img;
                }
                return $this->formatClassicMarkdownImage($img, false);
            },
            $html
        );

        return $html;
    }

    /**
     * @param string $imgTag Full <img …> tag from CommonMark
     * @param bool $allowFigure When true, wrap caption-worthy alts in figure.classic-markdown-figure
     */
    private function formatClassicMarkdownImage(string $imgTag, bool $allowFigure): string {
        if (!preg_match('/<img\b([^>]*)>/i', $imgTag, $m)) {
            return $imgTag;
        }
        // CommonMark often emits <img ... />; keep "/" out of the attribute string.
        $attrs = rtrim($m[1]);
        if (substr($attrs, -1) === '/') {
            $attrs = rtrim(substr($attrs, 0, -1));
        }

        $alt = '';
        if (preg_match('/\balt=["\']([^"\']*)["\']/i', $attrs, $altM)) {
            $alt = html_entity_decode($altM[1], ENT_QUOTES | ENT_HTML5, 'UTF-8');
        }

        if (preg_match('/\bclass=["\']([^"\']*)["\']/i', $attrs, $classM)) {
            $classes = preg_split('/\s+/', trim($classM[1]), -1, PREG_SPLIT_NO_EMPTY);
            if (!in_array('classic-markdown', $classes, true)) {
                $classes[] = 'classic-markdown';
            }
            $attrs = preg_replace(
                '/\bclass=["\']([^"\']*)["\']/i',
                'class="' . htmlspecialchars(implode(' ', $classes), ENT_QUOTES | ENT_HTML5, 'UTF-8') . '"',
                $attrs,
                1
            );
        } else {
            $attrs = rtrim($attrs) . ' class="classic-markdown"';
        }

        $attrs = trim($attrs);
        $img = $attrs === '' ? '<img>' : '<img ' . $attrs . '>';

        if ($allowFigure && $this->isCaptionWorthyAlt($alt)) {
            $caption = htmlspecialchars($alt, ENT_QUOTES | ENT_HTML5, 'UTF-8');
            return '<figure class="classic-markdown-figure">' . $img
                . '<figcaption class="caption">' . $caption . '</figcaption></figure>';
        }

        return $img;
    }

    /** Match Traven WYSIWYM: caption from alt unless empty or literally "image". */
    private function isCaptionWorthyAlt(string $alt): bool {
        $trimmed = trim($alt);
        return $trimmed !== '' && strtolower($trimmed) !== 'image';
    }

    private function renderHtml($markdown) {
        $mathPlaceholders = [];
        $markdown = $this->preprocessMarkdown($markdown, $mathPlaceholders);
        $markdown = $this->transcodeLegacyLinks($markdown);
        $html = $this->converter->convert($markdown)->getContent();
        $html = $this->restoreMath($html, $mathPlaceholders);
        $html = $this->enhanceClassicMarkdownImages($html);
        $html = ShortcodeProcessor::process($html);
        $html = $this->postprocessHtml($html);
        return apply_dropcap($html);
    }

    /**
     * Render a markdown fragment to HTML (used by ExpandResolver).
     * Skips dropcap so nested expands don't steal styling from the host post.
     */
    public function renderMarkdownFragment(string $markdown): string {
        $mathPlaceholders = [];
        $markdown = $this->preprocessMarkdown($markdown, $mathPlaceholders);
        $markdown = $this->transcodeLegacyLinks($markdown);
        $html = $this->converter->convert($markdown)->getContent();
        $html = $this->restoreMath($html, $mathPlaceholders);
        $html = $this->enhanceClassicMarkdownImages($html);
        $html = ShortcodeProcessor::process($html);
        $html = $this->postprocessHtml($html);
        return $html;
    }

    private function renderPlainHtml($markdown) {
        $mathPlaceholders = [];
        $markdown = $this->preprocessMarkdown($markdown, $mathPlaceholders);
        $markdown = $this->transcodeLegacyLinks($markdown);
        $html = $this->converter->convert($markdown)->getContent();
        $html = $this->restoreMath($html, $mathPlaceholders);
        $html = $this->enhanceClassicMarkdownImages($html);
        $html = ShortcodeProcessor::process($html);
        $html = $this->postprocessHtml($html);
        return preg_replace('/^<p>(.*?)<\/p>$/s', '$1', trim($html));
    }

    private function postprocessHtml($html) {
        if (empty($html)) return '';
        
        // Post-process GitHub-style alerts: replace <blockquote> with styled one and strip marker
        $html = preg_replace_callback('/<blockquote>\s*<p>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\](?:\s*<br\s*\/?>)?\s*(.*?)(?:\s*<\/p>)/is', function($matches) {
            $type = strtolower($matches[1]);
            $content = $matches[2];
            return '<blockquote class="traven-alert traven-alert-' . $type . '"><p>' . $content . '</p>';
        }, $html);
        
        // Post-process task lists: add class and inline style to li elements containing checkboxes
        $html = preg_replace_callback('/<li([^>]*)>(\s*<input[^>]*type="checkbox"[^>]*>)/i', function($matches) {
            $liAttrs = $matches[1];
            $inputHtml = $matches[2];
            
            // Check if class already exists
            if (preg_match('/class=["\']([^"\']*)["\']/i', $liAttrs, $classMatches)) {
                $classes = explode(' ', $classMatches[1]);
                if (!in_array('task-list-item', $classes)) {
                    $classes[] = 'task-list-item';
                }
                $liAttrs = preg_replace('/class=["\']([^"\']*)["\']/i', 'class="' . implode(' ', $classes) . '"', $liAttrs);
            } else {
                $liAttrs .= ' class="task-list-item"';
            }
            
            // Check if style already exists
            if (preg_match('/style=["\']([^"\']*)["\']/i', $liAttrs, $styleMatches)) {
                $style = rtrim($styleMatches[1], '; ') . '; list-style-type: none;';
                $liAttrs = preg_replace('/style=["\']([^"\']*)["\']/i', 'style="' . $style . '"', $liAttrs);
            } else {
                $liAttrs .= ' style="list-style-type: none;"';
            }
            
            return "<li{$liAttrs}>{$inputHtml}";
        }, $html);

        // Resolve standard image paths in img tags (skip already-resolved paths)
        $html = preg_replace_callback('/<img\b([^>]*)src=["\']([^"\']*)["\']([^>]*)/i', function($matches) {
            $beforeSrc = $matches[1];
            $src = $matches[2];
            $afterSrc = $matches[3];
            // Skip paths already resolved by ShortcodeProcessor or absolute URLs
            if (preg_match('~^(\.\./|\./|https?://|data:)~', $src)) {
                return $matches[0];
            }
            $resolvedSrc = ShortcodeProcessor::resolveAsset($src);
            return '<img' . $beforeSrc . 'src="' . htmlspecialchars($resolvedSrc) . '"' . $afterSrc;
        }, $html);

        // Preserve ?site= on same-app relative anchors (dynamic preview only)
        $siteId = $this->api ? $this->api->getSiteId() : '';
        $isStatic = defined('STATIC_BUILD') && STATIC_BUILD;
        if ($siteId !== '' && !$isStatic) {
            $html = preg_replace_callback('/<a\b([^>]*)\bhref=(["\'])([^"\']*)\2([^>]*)>/i', function ($matches) use ($siteId) {
                $before = $matches[1];
                $quote = $matches[2];
                $href = $matches[3];
                $after = $matches[4];
                $next = PreviewUrl::appendPreviewSiteQuery($href, $siteId, false);
                if ($next === $href) {
                    return $matches[0];
                }
                return '<a' . $before . 'href=' . $quote . htmlspecialchars($next, ENT_QUOTES) . $quote . $after . '>';
            }, $html);
        }

        return $html;
    }

    private function preprocessMarkdown($markdown, &$mathPlaceholders) {
        if (empty($markdown)) return '';

        // Protect code blocks, inline code, and math equations by replacing them with placeholders
        $placeholders = [];
        $placeholderIndex = 0;

        // 1. Protect fenced code blocks (both ``` and ~~~)
        $markdown = preg_replace_callback('/(^(?:```|~~~)[a-zA-Z0-9-]*\s*$.*?^(?:```|~~~)\s*$)/ms', function($matches) use (&$placeholders, &$placeholderIndex) {
            $key = "%%CODEBLOCK_" . $placeholderIndex++ . "%%";
            $placeholders[$key] = $matches[1];
            return $key;
        }, $markdown);

        // 2. Protect inline code spans (e.g. `code` or ``code``)
        $markdown = preg_replace_callback('/(`+.*?`+)/s', function($matches) use (&$placeholders, &$placeholderIndex) {
            $key = "%%CODESPAN_" . $placeholderIndex++ . "%%";
            $placeholders[$key] = $matches[1];
            return $key;
        }, $markdown);

        // 3. Protect display math ($$ ... $$)
        $mathPlaceholderIndex = 0;
        $markdown = preg_replace_callback('/(\$\$.*?\$\$)/s', function($matches) use (&$mathPlaceholders, &$mathPlaceholderIndex) {
            $key = "%%DISPLAYMATH_" . $mathPlaceholderIndex++ . "%%";
            $mathPlaceholders[$key] = $matches[1];
            return $key;
        }, $markdown);

        // 4. Protect inline math ($ ... $)
        $markdown = preg_replace_callback('/(?<!\$)\$([^$\s](?:[^$]*[^$\s])?)\$(?!\$)/', function($matches) use (&$mathPlaceholders, &$mathPlaceholderIndex) {
            $key = "%%INLINEMATH_" . $mathPlaceholderIndex++ . "%%";
            $mathPlaceholders[$key] = $matches[0];
            return $key;
        }, $markdown);

        // 5. Replace subscript ~text~ with <sub>text</sub>
        $markdown = preg_replace('/(?<!~)~([^~\s](?:[^~]*[^~\s])?)~(?!~)/', '<sub>$1</sub>', $markdown);

        // 6. Replace superscript ^text^ with <sup>text</sup>
        $markdown = preg_replace('/(?<!\^)\^([^\^\s](?:[^^]*[^\^\s])?)\^(?!\^)/', '<sup>$1</sup>', $markdown);

        // 7. Replace highlight ==text== with <mark>text</mark>
        $markdown = preg_replace('/(?<!=)==([^=\s](?:[^=]*[^=\s])?)==(?!=)/', '<mark>$1</mark>', $markdown);

        // 8. Restore code blocks and spans
        if (!empty($placeholders)) {
            $keys = array_keys($placeholders);
            $vals = array_values($placeholders);
            $markdown = str_replace($keys, $vals, $markdown);
        }

        return $markdown;
    }

    private function transcodeLegacyLinks($content) {
        if (empty($content)) return '';
        return preg_replace_callback('/(?<!\!)\[([^\]]+)\]\(([^\)]+)\)/', function($matches) {
            $text = $matches[1];
            $url = $matches[2];
            return "[link=\"{$url}\"]{$text}[/link]";
        }, $content);
    }
}

