<?php

namespace Dossier;

require_once __DIR__ . '/ContentUrls.php';
require_once __DIR__ . '/ExpandResolver.php';
require_once __DIR__ . '/InternalAPIClient.php';

/**
 * Compiles Traven wikilinks in Markdown into published reader HTML.
 *
 * Forms (mirrors Traven parseWikilinkAttrs, linear scan, no nested regex):
 *   [[slug]] / [[slug|Label]]            → link
 *   [[!slug]] (+ #Heading, ^summary|^deck, |Label) → embed
 *   [[>slug]] (+ #Heading, ^summary|^deck, |Label) → expand
 *
 * Extras parse left-to-right after the slug: #Section → heading,
 * ^[a-z]+ → source, first | starts the label.
 *
 * Callers must stash fenced/inline code before calling process().
 * Incomplete [[… without ]] on the same line is left as text.
 */
class WikilinkProcessor {
    /**
     * Compile wikilinks in Markdown to HTML (link/expand/embed).
     *
     * @param string $markdown Markdown with code already stashed
     * @param InternalAPIClient|null $api
     * @param string|null $language
     * @param string|null $readMore Localized "Read more" label (null = theme default)
     */
    public static function process(
        string $markdown,
        ?InternalAPIClient $api = null,
        ?string $language = null,
        ?string $readMore = null
    ): string {
        if ($markdown === '') {
            return '';
        }
        [$resolvedApi, $resolvedLanguage, $resolvedReadMore] = self::resolveContext($api, $language, $readMore);
        $resolver = null;
        $getResolver = function () use (&$resolver, $resolvedApi, $resolvedLanguage, $resolvedReadMore) {
            if ($resolver === null) {
                $resolver = new ExpandResolver($resolvedApi, $resolvedLanguage, $resolvedReadMore);
            }
            return $resolver;
        };

        return self::scan($markdown, function (array $attrs, string $raw) use ($getResolver) {
            return self::renderHtml($attrs, $raw, $getResolver);
        });
    }

    /**
     * Flatten wikilinks to readable Markdown for agents (no HTML, no shortcodes).
     *   [[slug|Label]] → [Label](url)
     *   [[>slug]] / [[!slug]] → [expand: slug](url) / [embed: slug](url)
     */
    public static function flattenForMarkdown(string $markdown): string {
        if ($markdown === '') {
            return '';
        }
        return self::scan($markdown, function (array $attrs) {
            $slug = trim((string) ($attrs['slug'] ?? ''));
            if ($slug === '') {
                return '';
            }
            $heading = $attrs['heading'] ?? null;
            $source = $attrs['source'] ?? null;
            $label = $attrs['text'] ?? null;
            if ($label === null || $label === '') {
                $label = $heading ?: $slug;
            }
            $section = null;
            if (is_string($heading) && $heading !== '' && preg_match('/^[a-z]+$/', strtolower($heading))) {
                $section = $heading;
            }
            $url = ContentUrls::resolveContentUrl($slug, $section);
            if ($url === '') {
                $url = 'post.php?slug=' . rawurlencode($slug);
            }
            $mode = $attrs['mode'] ?? 'link';
            if ($mode === 'link') {
                return '[' . $label . '](' . $url . ')';
            }
            $ref = $slug;
            if (is_string($heading) && $heading !== '') {
                $ref .= '#' . $heading;
            } elseif (is_string($source) && $source !== '') {
                $ref .= ' ^' . $source;
            }
            return '[' . $mode . ': ' . $ref . '](' . $url . ')';
        });
    }

    /**
     * Scan Markdown for complete same-line [[…]] spans and replace via callback.
     * Linear scan; never spans newlines.
     *
     * @param callable(array,string):string $replace Receives (attrs, raw)
     */
    private static function scan(string $markdown, callable $replace): string {
        $out = '';
        $len = strlen($markdown);
        $i = 0;
        while ($i < $len) {
            $open = strpos($markdown, '[[', $i);
            if ($open === false) {
                $out .= substr($markdown, $i);
                break;
            }
            // Find closing ]] on the same line
            $lineEnd = strpos($markdown, "\n", $open);
            if ($lineEnd === false) {
                $lineEnd = $len;
            }
            $close = strpos($markdown, ']]', $open + 2);
            if ($close === false || $close > $lineEnd) {
                // Incomplete wikilink on this line — emit through $open verbatim
                // and keep scanning (a later line may hold a valid wikilink).
                $out .= substr($markdown, $i, $open + 2 - $i);
                $i = $open + 2;
                continue;
            }
            $raw = substr($markdown, $open, $close + 2 - $open);
            $attrs = self::parseWikilinkAttrs($raw);
            if (trim((string) ($attrs['slug'] ?? '')) === '' && ($attrs['mode'] ?? 'link') !== 'link') {
                // Keep empty-slug expands/embeds silent (reader-facing omit)
                $out .= substr($markdown, $i, $open - $i);
                $i = $close + 2;
                continue;
            }
            if (trim((string) ($attrs['slug'] ?? '')) === '') {
                // Not a real wikilink (e.g. [[]]) — leave as text
                $out .= substr($markdown, $i, $close + 2 - $i);
                $i = $close + 2;
                continue;
            }
            $out .= substr($markdown, $i, $open - $i);
            $out .= (string) $replace($attrs, $raw);
            $i = $close + 2;
        }
        return $out;
    }

    /**
     * Mirror of Traven parseWikilinkAttrs (linear scan, no regex).
     * @return array{mode:string, slug:string, heading:?string, text:?string, source:?string}
     */
    public static function parseWikilinkAttrs(string $raw): array {
        $empty = ['mode' => 'link', 'slug' => '', 'heading' => null, 'text' => null, 'source' => null];
        $text = trim((string) $raw);
        if (strlen($text) < 5 || substr($text, 0, 2) !== '[[' || substr($text, -2) !== ']]') {
            return $empty;
        }
        $inner = substr($text, 2, -2);
        $mode = 'link';
        if ($inner !== '' && ($inner[0] === '!' || $inner[0] === '>')) {
            $mode = $inner[0] === '!' ? 'embed' : 'expand';
            $inner = substr($inner, 1);
        }
        $n = strlen($inner);
        $i = 0;
        while ($i < $n && ($inner[$i] === ' ' || $inner[$i] === "\t")) {
            $i++;
        }
        $slugStart = $i;
        while ($i < $n && $inner[$i] !== '#' && $inner[$i] !== '^' && $inner[$i] !== '|') {
            $i++;
        }
        $slug = trim(substr($inner, $slugStart, $i - $slugStart));
        $heading = null;
        $source = null;
        $label = null;
        while ($i < $n) {
            $c = $inner[$i];
            if ($c === '|') {
                $label = substr($inner, $i + 1);
                break;
            }
            if ($c === '#') {
                $i++;
                $hStart = $i;
                while ($i < $n && $inner[$i] !== '^' && $inner[$i] !== '|') {
                    $i++;
                }
                $h = trim(substr($inner, $hStart, $i - $hStart));
                if ($h !== '') {
                    $heading = $h;
                }
                continue;
            }
            if ($c === '^') {
                $i++;
                $sStart = $i;
                while ($i < $n) {
                    $d = $inner[$i];
                    if ($d < 'a' || $d > 'z') {
                        break;
                    }
                    $i++;
                }
                $s = substr($inner, $sStart, $i - $sStart);
                if ($s !== '') {
                    $source = $s;
                }
                continue;
            }
            $i++;
        }
        $linkText = $label !== null ? trim($label) : null;
        if ($linkText === '') {
            $linkText = null;
        }
        return ['mode' => $mode, 'slug' => $slug, 'heading' => $heading, 'text' => $linkText, 'source' => $source];
    }

    /**
     * @param callable():ExpandResolver $getResolver
     */
    private static function renderHtml(array $attrs, string $raw, callable $getResolver): string {
        $mode = $attrs['mode'] ?? 'link';
        $slug = trim((string) ($attrs['slug'] ?? ''));
        if ($slug === '') {
            return $mode === 'link' ? $raw : '';
        }
        $heading = $attrs['heading'] ?? null;
        $source = $attrs['source'] ?? null;
        if (is_string($heading) && trim($heading) === '') {
            $heading = null;
        }
        if (is_string($source) && trim($source) === '') {
            $source = null;
        }

        $slugAttr = htmlspecialchars($slug, ENT_QUOTES, 'UTF-8');
        $headingAttr = $heading !== null
            ? ' data-heading="' . htmlspecialchars($heading, ENT_QUOTES, 'UTF-8') . '"'
            : '';
        $sourceAttr = $source !== null
            ? ' data-source="' . htmlspecialchars($source, ENT_QUOTES, 'UTF-8') . '"'
            : '';

        if ($mode === 'link') {
            $labelSource = $attrs['text'] ?? null;
            if (!is_string($labelSource) || trim($labelSource) === '') {
                $labelSource = $heading ?: $slug;
            }
            $label = htmlspecialchars($labelSource, ENT_QUOTES, 'UTF-8');
            $section = null;
            if (is_string($heading) && $heading !== '' && preg_match('/^[A-Za-z]+$/', $heading)) {
                $section = $heading;
            }
            $href = ContentUrls::resolveContentUrl($slug, $section);
            if ($href === '') {
                $href = 'post.php?slug=' . urlencode($slug);
            }
            return '<a class="traven-wikilink" href="' . htmlspecialchars($href, ENT_QUOTES, 'UTF-8')
                . '" data-slug="' . $slugAttr . '"' . $headingAttr . $sourceAttr . '>' . $label . '</a>';
        }

        // expand / embed — same validation as the retired [expand]/[embed] handler
        if ($source !== null && $heading !== null) {
            return '';
        }
        if ($source !== null && $source !== 'deck' && $source !== 'summary') {
            return '';
        }

        $resolver = $getResolver();
        $bodyHtml = $resolver->resolve($slug, $heading, $mode, $source);
        if ($bodyHtml === null) {
            return '';
        }

        if ($mode === 'embed') {
            return '<div class="traven-embed" data-slug="' . $slugAttr . '"' . $headingAttr . $sourceAttr . '>'
                . '<div class="traven-embed-content">' . $bodyHtml . '</div></div>';
        }

        $linkText = $attrs['text'] ?? null;
        $labelSource = (is_string($linkText) && trim($linkText) !== '')
            ? trim($linkText)
            : ($heading ?: ($resolver->resolveDisplayTitle($slug) ?: $slug));
        $label = htmlspecialchars($labelSource, ENT_QUOTES, 'UTF-8');
        $id = 'traven-ee-' . bin2hex(random_bytes(6));
        return '<button type="button" class="traven-expand-trigger" data-traven-expand="' . $id . '"'
            . ' data-slug="' . $slugAttr . '"' . $headingAttr . $sourceAttr . ' aria-expanded="false">' . $label . '</button>'
            . '<template id="' . $id . '">' . $bodyHtml . '</template>';
    }

    /**
     * @return array{0:InternalAPIClient,1:?string,2:string}
     */
    private static function resolveContext(?InternalAPIClient $api, ?string $language, ?string $readMore): array {
        $engine = ContentUrls::getThemeEngine();
        $siteId = 'default';
        if ($engine !== null && method_exists($engine, 'getSiteId')) {
            $siteId = (string) $engine->getSiteId();
        }
        if ($api === null) {
            $api = new InternalAPIClient($siteId !== '' ? $siteId : 'default');
        }
        if ($language === null) {
            $language = ContentUrls::getLanguage();
        } elseif (trim($language) !== '') {
            $language = strtolower(str_replace('_', '-', trim($language)));
        } else {
            $language = null;
        }
        if ($readMore === null || trim($readMore) === '') {
            $readMore = 'Read more';
            if ($engine !== null && method_exists($engine, 'uiString')) {
                $readMore = (string) $engine->uiString('readMore', $language, $readMore);
            }
        }
        return [$api, $language, $readMore];
    }
}
