<?php

namespace Dossier;

require_once __DIR__ . '/ContentUrls.php';

/**
 * Compiles Traven MDX components in Markdown into published reader HTML.
 *
 * Capitalization invariant: only `<[A-Z][A-Za-z0-9_-]*…>` is a component.
 * Lowercase `<video>` / `<audio>` / `<image>` stay plain HTML/CommonMark.
 *
 * Two-phase use (mirrors the blueprint pipeline):
 *   1. extract(): pre-CommonMark — replace MDX tags with
 *      `<!--__PEN_COMPONENT_N__-->` placeholders so CommonMark neither
 *      wraps them in <p> nor processes inner bodies as top-level MDX.
 *   2. restore(): post-CommonMark — replace placeholders with Session 5 HTML
 *      (or theme Twig components), compiling inner Markdown via the
 *      caller-supplied fragment renderer.
 *
 * Published YouTube embeds keep youtube-nocookie (unlike Traven preview).
 */
class ComponentProcessor {
    public const PLACEHOLDER_PREFIX = '<!--__PEN_COMPONENT_';
    public const PLACEHOLDER_SUFFIX = '__-->';
    private const MAX_RESTORE_DEPTH = 10;
    private static int $restoreDepth = 0;

    /**
     * Extract MDX tags from Markdown (code must already be stashed by caller).
     * @return array{0:string,1:list<array{tag:string,attrs:array<string,string>,inner:string,raw:string}>}
     */
    public static function extract(string $markdown): array {
        $components = [];
        $out = '';
        $len = strlen($markdown);
        $i = 0;
        while ($i < $len) {
            $lt = strpos($markdown, '<', $i);
            if ($lt === false) {
                $out .= substr($markdown, $i);
                break;
            }
            // Only `<[A-Z]` opens a component; `</…` never opens one
            $next1 = $lt + 1 < $len ? $markdown[$lt + 1] : '';
            if ($next1 === '' || $next1 < 'A' || $next1 > 'Z') {
                $out .= substr($markdown, $i, $lt - $i + 1);
                $i = $lt + 1;
                continue;
            }
            $parsed = self::parseOpenTag($markdown, $lt);
            if ($parsed === null) {
                $out .= substr($markdown, $i, $lt - $i + 1);
                $i = $lt + 1;
                continue;
            }
            [$tag, $attrs, $openEnd, $selfClosing] = $parsed;
            if ($selfClosing) {
                $raw = substr($markdown, $lt, $openEnd - $lt);
                $idx = count($components);
                $components[] = ['tag' => $tag, 'attrs' => $attrs, 'inner' => '', 'raw' => $raw];
                $out .= substr($markdown, $i, $lt - $i);
                $out .= "\n\n" . self::placeholder($idx) . "\n\n";
                $i = $openEnd;
                continue;
            }
            $found = self::findMatchingClose($markdown, $tag, $openEnd);
            if ($found === null) {
                // Unclosed tag — leave as text
                $out .= substr($markdown, $i, $lt - $i + 1);
                $i = $lt + 1;
                continue;
            }
            [$closeStart, $closeEnd] = $found;
            $inner = substr($markdown, $openEnd, $closeStart - $openEnd);
            $raw = substr($markdown, $lt, $closeEnd - $lt);
            $idx = count($components);
            $components[] = ['tag' => $tag, 'attrs' => $attrs, 'inner' => $inner, 'raw' => $raw];
            $out .= substr($markdown, $i, $lt - $i);
            $out .= "\n\n" . self::placeholder($idx) . "\n\n";
            $i = $closeEnd;
        }
        return [$out, $components];
    }

    /**
     * Restore placeholders in post-CommonMark HTML to component HTML.
     *
     * @param list<array{tag:string,attrs:array<string,string>,inner:string,raw:string}> $components
     * @param callable(string):string|null $fragmentRenderer Compiles inner Markdown (null = keep raw text)
     */
    public static function restore(string $html, array $components, ?callable $fragmentRenderer = null): string {
        if ($html === '' || $components === []) {
            return $html;
        }
        if (self::$restoreDepth >= self::MAX_RESTORE_DEPTH) {
            return $html;
        }
        self::$restoreDepth++;
        try {
            foreach ($components as $idx => $c) {
                $ph = self::placeholder($idx);
                $rendered = self::renderComponent(
                    (string) ($c['tag'] ?? ''),
                    is_array($c['attrs'] ?? null) ? $c['attrs'] : [],
                    (string) ($c['inner'] ?? ''),
                    $fragmentRenderer
                );
                // CommonMark may wrap a lone comment in <p>…</p>
                $html = preg_replace(
                    '/<p>\s*' . preg_quote($ph, '/') . '\s*<\/p>/i',
                    $rendered,
                    $html
                ) ?? $html;
                if (strpos($html, $ph) !== false) {
                    $html = str_replace($ph, $rendered, $html);
                }
            }
            return $html;
        } finally {
            self::$restoreDepth--;
        }
    }

    /**
     * Flatten MDX to readable Markdown for agents (no HTML, no shortcodes).
     * Code must already be stashed by the caller.
     */
    public static function flattenForMarkdown(string $markdown): string {
        if ($markdown === '') {
            return '';
        }
        [$extracted, $components] = self::extract($markdown);
        $flat = [];
        foreach ($components as $idx => $c) {
            $flat[$idx] = self::flattenComponent(
                (string) ($c['tag'] ?? ''),
                is_array($c['attrs'] ?? null) ? $c['attrs'] : [],
                (string) ($c['inner'] ?? '')
            );
        }
        $out = $extracted;
        foreach ($flat as $idx => $replacement) {
            $ph = self::placeholder($idx);
            $out = preg_replace('/[ \t]*\n?[ \t]*' . preg_quote($ph, '/') . '[ \t]*\n?[ \t]*/', "\n\n" . $replacement . "\n\n", $out) ?? $out;
        }
        // Collapse excess blank lines left by placeholder swaps
        $out = preg_replace("/\n{3,}/", "\n\n", $out) ?? $out;
        return $out;
    }

    /**
     * Render one component to published HTML.
     *
     * @param array<string,string> $attrs
     */
    public static function renderComponent(string $tag, array $attrs, string $inner, ?callable $fragmentRenderer = null): string {
        $lower = strtolower($tag);
        $renderInner = function () use ($inner, $fragmentRenderer) {
            $trimmed = trim($inner);
            if ($trimmed === '') {
                return '';
            }
            if ($fragmentRenderer !== null) {
                return (string) $fragmentRenderer($trimmed);
            }
            return '<p>' . htmlspecialchars($trimmed, ENT_QUOTES, 'UTF-8') . '</p>';
        };

        if ($lower === 'image') {
            return self::renderImage($attrs);
        }
        if ($lower === 'video') {
            return self::renderVideo($attrs);
        }
        if ($lower === 'audio') {
            return self::renderAudio($attrs);
        }
        if ($lower === 'figure') {
            $align = self::attr($attrs, 'align', 'center');
            $bodyHtml = $renderInner();
            return '<figure class="traven-figure align-' . htmlspecialchars($align, ENT_QUOTES, 'UTF-8') . '">'
                . $bodyHtml . '</figure>';
        }
        if ($lower === 'quote' || $lower === 'blockquote') {
            $bodyHtml = $renderInner();
            $html = '<blockquote class="traven-component-blockquote">';
            $html .= '<div class="component-body">' . $bodyHtml . '</div>';
            $cite = self::renderQuoteCite($attrs);
            if ($cite !== '') {
                $html .= $cite;
            }
            $html .= '</blockquote>';
            return $html;
        }
        if ($lower === 'pullquote') {
            return '<blockquote class="traven-component-pullquote"><div class="component-body">'
                . $renderInner() . '</div></blockquote>';
        }
        if ($lower === 'highlight') {
            $bodyHtml = $renderInner();
            $text = trim(strip_tags($bodyHtml) === '' ? $inner : $bodyHtml);
            if ($bodyHtml !== '') {
                // Keep compiled inline content when available
                $innerInline = preg_replace('/^<p>(.*)<\/p>$/s', '$1', trim($bodyHtml)) ?? $bodyHtml;
                return '<mark>' . $innerInline . '</mark>';
            }
            return '<mark>' . htmlspecialchars(trim($inner), ENT_QUOTES, 'UTF-8') . '</mark>';
        }
        if ($lower === 'callout') {
            $compName = self::attr($attrs, 'type', 'info');
            if ($compName === '') {
                $compName = 'info';
            }
            return self::renderGenericCard($compName, $attrs, $renderInner);
        }
        if ($lower === 'component') {
            $name = self::attr($attrs, 'name', '');
            if ($name === 'quote') {
                $name = 'blockquote';
            }
            if ($name === '') {
                $name = strtolower($tag);
            }
            // Named Twig slot first
            $slotHtml = $renderInner();
            $twigHtml = self::renderThemeComponent($name, $attrs, $slotHtml);
            if ($twigHtml !== null) {
                return $twigHtml;
            }
            $lowerName = strtolower($name);
            if ($lowerName === 'blockquote' || $lowerName === 'quote') {
                $html = '<blockquote class="traven-component-blockquote">';
                $html .= '<div class="component-body">' . $slotHtml . '</div>';
                $cite = self::renderQuoteCite($attrs);
                if ($cite !== '') {
                    $html .= $cite;
                }
                return $html . '</blockquote>';
            }
            if ($lowerName === 'pullquote') {
                return '<blockquote class="traven-component-pullquote"><div class="component-body">'
                    . $slotHtml . '</div></blockquote>';
            }
            if ($lowerName === 'highlight') {
                $innerInline = preg_replace('/^<p>(.*)<\/p>$/s', '$1', trim($slotHtml)) ?? $slotHtml;
                return '<mark>' . $innerInline . '</mark>';
            }
            return self::renderGenericCard($name, $attrs, function () use ($slotHtml) {
                return $slotHtml;
            });
        }

        // Unknown capitalized tag — generic component card (never raw-tag passthrough)
        return self::renderGenericCard($lower !== '' ? $lower : $tag, $attrs, $renderInner);
    }

    // ---- built-ins ----

    /** @param array<string,string> $attrs */
    private static function renderImage(array $attrs): string {
        $src = ContentUrls::resolveAsset(self::attr($attrs, 'src', ''));
        $caption = self::attr($attrs, 'caption', '');
        $alt = self::attr($attrs, 'alt', $caption);
        $align = self::attr($attrs, 'align', 'center');
        $size = self::attr($attrs, 'size', 'medium');
        $customClass = self::attr($attrs, 'class', '');
        $customClass = $customClass !== '' ? ' ' . $customClass : '';
        if ($caption !== '') {
            return '<figure class="traven-image-figure align-' . htmlspecialchars($align, ENT_QUOTES, 'UTF-8')
                . ' size-' . htmlspecialchars($size, ENT_QUOTES, 'UTF-8') . htmlspecialchars($customClass, ENT_QUOTES, 'UTF-8') . '">'
                . '<img src="' . htmlspecialchars($src, ENT_QUOTES, 'UTF-8') . '" alt="' . htmlspecialchars($alt, ENT_QUOTES, 'UTF-8') . '" class="traven-image">'
                . '<figcaption class="traven-image-caption">' . htmlspecialchars($caption, ENT_QUOTES, 'UTF-8') . '</figcaption></figure>';
        }
        return '<img src="' . htmlspecialchars($src, ENT_QUOTES, 'UTF-8') . '" alt="' . htmlspecialchars($alt, ENT_QUOTES, 'UTF-8')
            . '" class="traven-image align-' . htmlspecialchars($align, ENT_QUOTES, 'UTF-8')
            . ' size-' . htmlspecialchars($size, ENT_QUOTES, 'UTF-8') . htmlspecialchars($customClass, ENT_QUOTES, 'UTF-8') . '">';
    }

    /** @param array<string,string> $attrs */
    private static function renderVideo(array $attrs): string {
        $rawSrc = self::attr($attrs, 'src', '');
        $caption = self::attr($attrs, 'caption', '');
        $align = self::attr($attrs, 'align', 'center');
        $size = self::attr($attrs, 'size', 'medium');
        $customClass = self::attr($attrs, 'class', '');
        $customClass = $customClass !== '' ? ' ' . $customClass : '';

        [$platform, $videoId] = self::parseVideoUrl($rawSrc);
        if ($platform === 'youtube') {
            $playerHtml = '<iframe src="https://www.youtube-nocookie.com/embed/' . htmlspecialchars($videoId, ENT_QUOTES, 'UTF-8')
                . '" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>';
        } elseif ($platform === 'vimeo') {
            $playerHtml = '<iframe src="https://player.vimeo.com/video/' . htmlspecialchars($videoId, ENT_QUOTES, 'UTF-8')
                . '" frameborder="0" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen></iframe>';
        } else {
            $src = ContentUrls::resolveAsset($rawSrc);
            $playerHtml = '<video src="' . htmlspecialchars($src, ENT_QUOTES, 'UTF-8') . '" controls class="traven-video"></video>';
        }

        $wrapClass = $customClass !== '' ? htmlspecialchars($customClass, ENT_QUOTES, 'UTF-8') : '';
        if ($caption !== '') {
            return '<figure class="traven-video-figure align-' . htmlspecialchars($align, ENT_QUOTES, 'UTF-8')
                . ' size-' . htmlspecialchars($size, ENT_QUOTES, 'UTF-8') . $wrapClass . '">'
                . '<div class="traven-video-container">' . $playerHtml . '</div>'
                . '<figcaption class="traven-video-caption">' . htmlspecialchars($caption, ENT_QUOTES, 'UTF-8') . '</figcaption></figure>';
        }
        return '<div class="traven-video-container align-' . htmlspecialchars($align, ENT_QUOTES, 'UTF-8')
            . ' size-' . htmlspecialchars($size, ENT_QUOTES, 'UTF-8') . $wrapClass . '">' . $playerHtml . '</div>';
    }

    /** @param array<string,string> $attrs */
    private static function renderAudio(array $attrs): string {
        $src = ContentUrls::resolveAsset(self::attr($attrs, 'src', ''));
        $caption = self::attr($attrs, 'caption', '');
        $align = self::attr($attrs, 'align', 'center');
        $size = self::attr($attrs, 'size', 'medium');
        $customClass = self::attr($attrs, 'class', '');
        $customClass = $customClass !== '' ? ' ' . $customClass : '';
        $audioHtml = '<audio src="' . htmlspecialchars($src, ENT_QUOTES, 'UTF-8') . '" controls class="traven-audio"></audio>';
        if ($caption !== '') {
            return '<figure class="traven-audio-figure align-' . htmlspecialchars($align, ENT_QUOTES, 'UTF-8')
                . ' size-' . htmlspecialchars($size, ENT_QUOTES, 'UTF-8') . htmlspecialchars($customClass, ENT_QUOTES, 'UTF-8') . '">'
                . '<div class="traven-audio-container">' . $audioHtml . '</div>'
                . '<figcaption class="traven-audio-caption">' . htmlspecialchars($caption, ENT_QUOTES, 'UTF-8') . '</figcaption></figure>';
        }
        return '<div class="traven-audio-container align-' . htmlspecialchars($align, ENT_QUOTES, 'UTF-8')
            . ' size-' . htmlspecialchars($size, ENT_QUOTES, 'UTF-8') . htmlspecialchars($customClass, ENT_QUOTES, 'UTF-8') . '">'
            . $audioHtml . '</div>';
    }

    /**
     * @param array<string,string> $attrs
     * @param callable():string $renderInner
     */
    private static function renderGenericCard(string $compName, array $attrs, callable $renderInner): string {
        $safe = preg_replace('/[^a-z0-9_-]/i', '', $compName) ?? 'component';
        if ($safe === '') {
            $safe = 'component';
        }
        $bodyHtml = $renderInner();
        $title = self::attr($attrs, 'title', '');
        $collapsible = self::attr($attrs, 'collapsible', '') === 'true';
        $displayTitle = $title !== '' ? $title : ($collapsible ? ucfirst($safe) : '');
        $html = '<div class="traven-component traven-component-' . htmlspecialchars($safe, ENT_QUOTES, 'UTF-8') . '">';
        if ($collapsible) {
            $html .= '<details open><summary class="component-header"><span class="component-title">'
                . htmlspecialchars($displayTitle, ENT_QUOTES, 'UTF-8')
                . '</span><span class="component-toggle-icon"></span></summary>'
                . '<div class="component-body">' . $bodyHtml . '</div></details>';
        } else {
            if ($displayTitle !== '') {
                $html .= '<div class="component-header"><span class="component-title">'
                    . htmlspecialchars($displayTitle, ENT_QUOTES, 'UTF-8') . '</span></div>';
            }
            $html .= '<div class="component-body">' . $bodyHtml . '</div>';
        }
        $html .= '</div>';
        return $html;
    }

    /** @param array<string,string> $attrs */
    private static function renderQuoteCite(array $attrs): string {
        $author = self::attr($attrs, 'author', '');
        $source = self::attr($attrs, 'source', '');
        if ($author === '' && $source === '') {
            return '';
        }
        $citeText = '— ';
        if ($author !== '' && $source !== '') {
            $citeText .= $author . ', ' . $source;
        } else {
            $citeText .= $author !== '' ? $author : $source;
        }
        return '<cite>' . htmlspecialchars($citeText, ENT_QUOTES, 'UTF-8') . '</cite>';
    }

    /**
     * @param array<string,string> $attrs
     */
    private static function renderThemeComponent(string $name, array $attrs, string $slotHtml): ?string {
        $engine = ContentUrls::getThemeEngine();
        if ($engine === null || !method_exists($engine, 'renderNamedComponent')) {
            return null;
        }
        try {
            $rendered = $engine->renderNamedComponent($name, $attrs, $slotHtml);
        } catch (\Throwable $e) {
            return null;
        }
        if (!is_string($rendered) || trim($rendered) === '') {
            return null;
        }
        return $rendered;
    }

    /** @param array<string,string> $attrs */
    private static function flattenComponent(string $tag, array $attrs, string $inner): string {
        $lower = strtolower($tag);
        if ($lower === 'image') {
            $src = self::attr($attrs, 'src', '');
            $alt = self::attr($attrs, 'alt', self::attr($attrs, 'caption', ''));
            $md = '![' . $alt . '](' . $src . ')';
            $caption = self::attr($attrs, 'caption', '');
            if ($caption !== '' && $caption !== $alt) {
                $md .= "\n\n*" . trim($caption) . "*";
            }
            return $md;
        }
        if ($lower === 'video' || $lower === 'audio') {
            $src = self::attr($attrs, 'src', '');
            $caption = self::attr($attrs, 'caption', ucfirst($lower));
            return '[' . $caption . '](' . $src . ')';
        }
        $trimmed = trim($inner);
        if (($lower === 'quote' || $lower === 'blockquote') && $trimmed !== '') {
            $lines = preg_split('/\r?\n/', $trimmed) ?: [];
            $quoted = array_map(fn($l) => '> ' . $l, $lines);
            $author = self::attr($attrs, 'author', '');
            $source = self::attr($attrs, 'source', '');
            if ($author !== '' || $source !== '') {
                $quoted[] = '>';
                $quoted[] = '> — ' . trim($author . ($author !== '' && $source !== '' ? ', ' : '') . $source);
            }
            return implode("\n", $quoted);
        }
        return $trimmed;
    }

    // ---- scanning / parsing ----

    private static function placeholder(int $idx): string {
        return self::PLACEHOLDER_PREFIX . $idx . self::PLACEHOLDER_SUFFIX;
    }

    /** @param array<string,string> $attrs */
    private static function attr(array $attrs, string $key, string $default): string {
        return isset($attrs[$key]) ? (string) $attrs[$key] : $default;
    }

    /**
     * Parse `<Tag …>` or `<Tag …/>` at $lt. Returns [tag, attrs, openEnd, selfClosing].
     * @return array{0:string,1:array<string,string>,2:int,3:bool}|null
     */
    private static function parseOpenTag(string $markdown, int $lt): ?array {
        $len = strlen($markdown);
        $i = $lt + 1;
        $nameStart = $i;
        while ($i < $len && self::isTagNameChar($markdown[$i])) {
            $i++;
        }
        $tag = substr($markdown, $nameStart, $i - $nameStart);
        if ($tag === '' || $tag[0] < 'A' || $tag[0] > 'Z') {
            return null;
        }
        // Scan to matching `>` respecting quotes
        $attrStart = $i;
        $quote = null;
        while ($i < $len) {
            $c = $markdown[$i];
            if ($quote !== null) {
                if ($c === $quote) {
                    $quote = null;
                }
                $i++;
                continue;
            }
            if ($c === '"' || $c === "'") {
                $quote = $c;
                $i++;
                continue;
            }
            if ($c === '>') {
                break;
            }
            if ($c === "\n") {
                // Traven parity: MDX tags must be single-line
                return null;
            }
            $i++;
        }
        if ($i >= $len || $markdown[$i] !== '>') {
            return null;
        }
        $openEnd = $i + 1;
        $attrString = substr($markdown, $attrStart, $i - $attrStart);
        $selfClosing = false;
        if (preg_match('/\/\s*$/', $attrString)) {
            $selfClosing = true;
            $attrString = preg_replace('/\/\s*$/', '', $attrString) ?? '';
        }
        return [$tag, self::parseAttributes($attrString), $openEnd, $selfClosing];
    }

    /**
     * Find matching `</Tag>` honoring same-tag nesting (case-sensitive).
     * @return array{0:int,1:int}|null [closeStart, closeEnd]
     */
    private static function findMatchingClose(string $markdown, string $tag, int $from): ?array {
        $len = strlen($markdown);
        $depth = 1;
        $i = $from;
        $openNeedle = '<' . $tag;
        $closeNeedle = '</' . $tag;
        while ($i < $len) {
            $lt = strpos($markdown, '<', $i);
            if ($lt === false) {
                return null;
            }
            if (substr($markdown, $lt, strlen($closeNeedle)) === $closeNeedle) {
                $j = $lt + strlen($closeNeedle);
                while ($j < $len && ($markdown[$j] === ' ' || $markdown[$j] === "\t")) {
                    $j++;
                }
                if ($j < $len && $markdown[$j] === '>') {
                    $depth--;
                    if ($depth === 0) {
                        return [$lt, $j + 1];
                    }
                    $i = $j + 1;
                    continue;
                }
            } elseif (substr($markdown, $lt, strlen($openNeedle)) === $openNeedle) {
                // Nested open of the same tag (must be followed by boundary char)
                $after = $lt + strlen($openNeedle);
                $boundary = $after < $len ? $markdown[$after] : '';
                if ($boundary === '' || $boundary === ' ' || $boundary === "\t" || $boundary === "\n" || $boundary === '>' || $boundary === '/') {
                    $parsed = self::parseOpenTag($markdown, $lt);
                    if ($parsed !== null) {
                        [$nestedTag, , $nestedEnd, $nestedSelfClosing] = $parsed;
                        if ($nestedTag === $tag && !$nestedSelfClosing) {
                            $depth++;
                        }
                        $i = $nestedEnd;
                        continue;
                    }
                }
            }
            $i = $lt + 1;
        }
        return null;
    }

    private static function isTagNameChar(string $c): bool {
        return ($c >= 'A' && $c <= 'Z') || ($c >= 'a' && $c <= 'z') || ($c >= '0' && $c <= '9') || $c === '_' || $c === '-' || $c === '.';
    }

    /**
     * Linear attribute parser (Traven-style): keys [a-zA-Z0-9_-]+, `=`, then
     * double/single-quoted (\" / \') or unquoted until whitespace, `>`, `/`.
     * @return array<string,string>
     */
    public static function parseAttributes(string $attrString): array {
        $attrs = [];
        $len = strlen($attrString);
        $i = 0;
        while ($i < $len) {
            while ($i < $len && ($attrString[$i] === ' ' || $attrString[$i] === "\t" || $attrString[$i] === "\n" || $attrString[$i] === "\r" || $attrString[$i] === '/')) {
                $i++;
            }
            if ($i >= $len || $attrString[$i] === '>') {
                break;
            }
            $keyStart = $i;
            while ($i < $len && self::isAttrKeyChar($attrString[$i])) {
                $i++;
            }
            $key = substr($attrString, $keyStart, $i - $keyStart);
            if ($key === '') {
                $i++;
                continue;
            }
            while ($i < $len && ($attrString[$i] === ' ' || $attrString[$i] === "\t")) {
                $i++;
            }
            if ($i >= $len || $attrString[$i] !== '=') {
                continue;
            }
            $i++;
            while ($i < $len && ($attrString[$i] === ' ' || $attrString[$i] === "\t")) {
                $i++;
            }
            if ($i >= $len) {
                $attrs[$key] = '';
                break;
            }
            $q = $attrString[$i];
            if ($q === '"' || $q === "'") {
                $i++;
                $val = '';
                while ($i < $len) {
                    $c = $attrString[$i];
                    if ($c === '\\' && $i + 1 < $len && ($attrString[$i + 1] === $q || $attrString[$i + 1] === '\\')) {
                        $val .= $attrString[$i + 1];
                        $i += 2;
                        continue;
                    }
                    if ($c === $q) {
                        $i++;
                        break;
                    }
                    $val .= $c;
                    $i++;
                }
                $attrs[$key] = $val;
            } else {
                $valStart = $i;
                while ($i < $len && $attrString[$i] !== ' ' && $attrString[$i] !== "\t" && $attrString[$i] !== "\n" && $attrString[$i] !== "\r" && $attrString[$i] !== '>' && $attrString[$i] !== '/' && $attrString[$i] !== ']') {
                    $i++;
                }
                $attrs[$key] = substr($attrString, $valStart, $i - $valStart);
            }
        }
        return $attrs;
    }

    private static function isAttrKeyChar(string $c): bool {
        return ($c >= 'A' && $c <= 'Z') || ($c >= 'a' && $c <= 'z') || ($c >= '0' && $c <= '9') || $c === '_' || $c === '-';
    }

    /**
     * @return array{0:string,1:?string} [platform, id]
     */
    private static function parseVideoUrl(string $src): array {
        if ($src === '') {
            return ['native', null];
        }
        if (preg_match('/(?:youtube\.com\/(?:watch\?v=|embed\/|v\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/', $src, $m)) {
            return ['youtube', $m[1]];
        }
        if (preg_match('/(?:vimeo\.com\/|player\.vimeo\.com\/video\/)(\d+)/', $src, $m)) {
            return ['vimeo', $m[1]];
        }
        return ['native', null];
    }
}
