<?php

namespace Dossier;

require_once __DIR__ . '/PreviewUrl.php';
require_once __DIR__ . '/ExpandResolver.php';
require_once __DIR__ . '/InternalAPIClient.php';

class ShortcodeProcessor {
    public static $basePath = '/assets/';
    public static $linkLookup = [];
    private static $themeEngine = null;
    private static ?string $language = null;

    public static function setThemeEngine($engine) {
        self::$themeEngine = $engine;
    }

    public static function setLanguage(?string $language): void {
        self::$language = $language !== null && trim($language) !== ''
            ? strtolower(str_replace('_', '-', trim($language)))
            : null;
    }

    /**
     * Public content URL for an entry slug — same rules as [link] shortcodes.
     * Dynamic preview: post.php?slug=… (+ ?site= when applicable).
     * Static build: {basePath}{slug}/
     */
    public static function resolveContentUrl(string $slug, ?string $section = null): string {
        $slug = trim($slug);
        if ($slug === '') {
            return '';
        }
        if (
            self::$themeEngine !== null
            && method_exists(self::$themeEngine, 'contentUrlForSlug')
        ) {
            return self::$themeEngine->contentUrlForSlug(
                $slug,
                $section,
                self::$language
            );
        }
        if (defined('STATIC_BUILD') && STATIC_BUILD) {
            return self::$basePath . $slug . '/';
        }
        $url = 'post.php?slug=' . urlencode($slug);
        if ($section !== null && $section !== '') {
            $url .= '&section=' . urlencode(strtolower(trim($section)));
        }
        $siteId = '';
        if (self::$themeEngine !== null && method_exists(self::$themeEngine, 'getSiteId')) {
            $siteId = (string) self::$themeEngine->getSiteId();
        }
        return PreviewUrl::appendPreviewSiteQuery($url, $siteId, false);
    }

    /**
     * Process all shortcodes in the given content.
     */
    public static function process($content) {
        if (empty($content)) return '';

        // 1. Stash code blocks and inline code to prevent shortcode processing inside them
        $placeholders = [];
        $placeholderIndex = 0;

        // Match <pre><code ...>...</code></pre> blocks
        $content = preg_replace_callback('/(<pre\b[^>]*><code\b[^>]*>.*?<\/code><\/pre>)/is', function($matches) use (&$placeholders, &$placeholderIndex) {
            $key = "<!--CODE_BLOCK_PLACEHOLDER_{$placeholderIndex}-->";
            $placeholders[$key] = $matches[1];
            $placeholderIndex++;
            return $key;
        }, $content);

        // Match <code ...>...</code> blocks
        $content = preg_replace_callback('/(<code\b[^>]*>.*?<\/code>)/is', function($matches) use (&$placeholders, &$placeholderIndex) {
            $key = "<!--CODE_BLOCK_PLACEHOLDER_{$placeholderIndex}-->";
            $placeholders[$key] = $matches[1];
            $placeholderIndex++;
            return $key;
        }, $content);

        // 1. [redact]content[/redact]
        $content = preg_replace('/\[redact\](.*?)\[\/redact\]/is', '<span class="redact">$1</span>', $content);

        // 2. [image src="..." alt="..." caption="..." class="..." size="..." align="..."]
        $content = preg_replace_callback('/\[image\s+(.*?)\]/is', function($matches) {
            $attrs = self::parseAttributes($matches[1]);
            
            $src = self::resolveAsset($attrs['src'] ?? '');
            $alt = $attrs['alt'] ?? '';
            $caption = $attrs['caption'] ?? '';
            $class = $attrs['class'] ?? '';
            $size = $attrs['size'] ?? 'medium';
            $align = $attrs['align'] ?? '';
            
            $sizeClass = 'img--' . $size . ' size-' . $size;
            
            if ($align) {
                $class = trim($class . ' align-' . $align . ' inline-image-' . $align);
            }
            
            $html = '<div class="gallery-single ' . htmlspecialchars($class) . ' ' . $sizeClass . '">';
            $html .= '<div class="photo-wrapper">';
            $html .= '<img src="' . htmlspecialchars($src) . '" alt="' . htmlspecialchars($alt) . '">';
            $html .= '</div>';
            if ($caption) {
                $html .= '<span class="caption">' . htmlspecialchars($caption) . '</span>';
            }
            $html .= '</div>';
            
            return $html;
        }, $content);

        // 3. [figure src="..." alt="..." caption="..." class="..." width="..."]
        $content = preg_replace_callback('/\[figure\s+(.*?)\](?:(.*?)\[\/figure\])?/is', function($matches) {
            $attrs = self::parseAttributes($matches[1]);
            $innerContent = $matches[2] ?? ''; 
            
            $src = self::resolveAsset($attrs['src'] ?? '');
            $alt = $attrs['alt'] ?? '';
            $caption = ($attrs['caption'] ?? '') ?: $innerContent;
            $class = ($attrs['class'] ?? '') ?: 'figure-full';
            $width = $attrs['width'] ?? '';
            
            $style = $width ? 'style="max-width: ' . htmlspecialchars($width) . 'px; width: 100%;"' : '';
            
            $html = '<div class="' . htmlspecialchars($class) . '" ' . $style . '>';
            $html .= '<div class="photo-wrapper">';
            $html .= '<img src="' . htmlspecialchars($src) . '" alt="' . htmlspecialchars($alt) . '">';
            $html .= '</div>';
            if ($caption) {
                $html .= '<span class="caption">' . htmlspecialchars($caption) . '</span>';
            }
            $html .= '</div>';
            
            return $html;
        }, $content);

        // 3.6. [video] and [youtube] shortcodes
        $content = preg_replace_callback('/\[(video|youtube)\s+(.*?)\]/is', function($matches) {
            $tag = strtolower($matches[1]);
            $attrs = self::parseAttributes($matches[2]);
            
            $src = $attrs['src'] ?? '';
            $caption = $attrs['caption'] ?? '';
            $align = $attrs['align'] ?? 'center';
            $size = $attrs['size'] ?? 'medium';
            $class = isset($attrs['class']) ? ' ' . $attrs['class'] : '';
            
            $platform = 'native';
            $videoId = '';
            if ($tag === 'youtube') {
                $platform = 'youtube';
                $videoId = $src;
            } else {
                if (preg_match('/(?:youtube\.com\/(?:watch\?v=|embed\/|v\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/', $src, $m)) {
                    $platform = 'youtube';
                    $videoId = $m[1];
                } elseif (preg_match('/(?:vimeo\.com\/|player\.vimeo\.com\/video\/)(\d+)/', $src, $m)) {
                    $platform = 'vimeo';
                    $videoId = $m[1];
                }
            }
            
            $playerHtml = '';
            if ($platform === 'youtube') {
                $playerHtml = '<iframe src="https://www.youtube-nocookie.com/embed/' . htmlspecialchars($videoId) . '" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>';
            } elseif ($platform === 'vimeo') {
                $playerHtml = '<iframe src="https://player.vimeo.com/video/' . htmlspecialchars($videoId) . '" frameborder="0" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen></iframe>';
            } else {
                $resolvedSrc = self::resolveAsset($src);
                $playerHtml = '<video src="' . htmlspecialchars($resolvedSrc) . '" controls class="traven-video-shortcode"></video>';
            }
            
            $html = '<figure class="traven-video-figure align-' . htmlspecialchars($align) . ' size-' . htmlspecialchars($size) . htmlspecialchars($class) . '">';
            $html .= '<div class="traven-video-container">' . $playerHtml . '</div>';
            if ($caption !== '') {
                $html .= '<figcaption class="traven-video-caption">' . htmlspecialchars($caption) . '</figcaption>';
            }
            $html .= '</figure>';
            
            return $html;
        }, $content);

        // 3.7. [audio] shortcode
        $content = preg_replace_callback('/\[audio\s+(.*?)\]/is', function($matches) {
            $attrs = self::parseAttributes($matches[1]);
            
            $src = $attrs['src'] ?? '';
            $caption = $attrs['caption'] ?? '';
            $align = $attrs['align'] ?? 'center';
            $size = $attrs['size'] ?? 'medium';
            $class = isset($attrs['class']) ? ' ' . $attrs['class'] : '';
            
            $resolvedSrc = self::resolveAsset($src);
            $playerHtml = '<audio class="traven-audio-shortcode" controls="" src="' . htmlspecialchars($resolvedSrc) . '"></audio>';
            
            $html = '<figure class="traven-audio-figure align-' . htmlspecialchars($align) . ' size-' . htmlspecialchars($size) . htmlspecialchars($class) . '">';
            $html .= '<div class="traven-audio-container">' . $playerHtml . '</div>';
            if ($caption !== '') {
                $html .= '<figcaption class="traven-audio-caption">' . htmlspecialchars($caption) . '</figcaption>';
            }
            $html .= '</figure>';
            
            return $html;
        }, $content);

        // 4. [quote class="..." author="..."]content[/quote]
        $content = preg_replace_callback('/\[quote\s*(.*?)\](.*?)\[\/quote\]/is', function($matches) {
            $attrs = self::parseAttributes($matches[1]);
            $text = $matches[2];
            $class = $attrs['class'] ?? '';
            $author = $attrs['author'] ?? '';
            
            $html = '<blockquote class="' . htmlspecialchars($class) . '">';
            $html .= trim($text);
            if ($author) {
                $html .= '<cite class="attribution">' . htmlspecialchars($author) . '</cite>';
            }
            $html .= '</blockquote>';
            return $html;
        }, $content);

        // 5. [align center|right]content[/align]
        $content = preg_replace_callback('/\[align\s+(.*?)\](.*?)\[\/align\]/is', function($matches) {
            $attrString = html_entity_decode($matches[1]);
            $alignment = trim(str_replace('=', '', $attrString), '"\' ');
            $text = $matches[2];
            
            $flexAlign = 'items-start';
            if ($alignment === 'center') $flexAlign = 'items-center';
            elseif ($alignment === 'right') $flexAlign = 'items-end';
 
            return '<div class="w-full flex flex-col ' . $flexAlign . '" style="text-align: ' . htmlspecialchars($alignment) . ';">' . $text . '</div>';
        }, $content);

        // 6. [highlight intent="..." color="..."]content[/highlight]
        $content = preg_replace_callback('/\[highlight\s*(.*?)\](.*?)\[\/highlight\]/is', function($matches) {
            $attrs = self::parseAttributes($matches[1]);
            $text = $matches[2];
            $intent = $attrs['intent'] ?? $attrs['default'] ?? '';
            $color = $attrs['color'] ?? '';
            
            $class = $intent ? 'intent-' . $intent : '';
            $style = $color ? 'background-color: ' . htmlspecialchars($color) . ';' : '';
            
            return '<mark class="' . $class . '" style="' . $style . '">' . $text . '</mark>';
        }, $content);

        // 7. [color intent="..." color="..."]content[/color]
        $content = preg_replace_callback('/\[color\s*(.*?)\](.*?)\[\/color\]/is', function($matches) {
            $attrs = self::parseAttributes($matches[1]);
            $text = $matches[2];
            $intent = $attrs['intent'] ?? '';
            
            // Decoded fallback for positional color
            $attrString = html_entity_decode($matches[1]);
            $color = trim($attrs['color'] ?? $attrString, '"\' '); 
            
            if (empty($color) && !empty($attrString) && strpos($attrString, '=') === false) {
                 $color = trim($attrString, '"\' ');
            }

            $class = $intent ? 'intent-' . $intent : '';
            $style = ($color && $color != $intent) ? 'color: ' . htmlspecialchars($color) . ';' : '';
            
            return '<span class="' . $class . '" style="' . $style . '">' . $text . '</span>';
        }, $content);

        // 8. [span class="..." color="..." highlight="..."]content[/span]
        $content = preg_replace_callback('/\[span\s*(.*?)\](.*?)\[\/span\]/is', function($matches) {
            $attrs = self::parseAttributes($matches[1]);
            $text = $matches[2];
            $class = $attrs['class'] ?? '';
            $color = $attrs['color'] ?? '';
            $highlight = $attrs['highlight'] ?? '';
            
            $style = '';
            if ($color) $style .= 'color: ' . htmlspecialchars($color) . ';';
            if ($highlight) $style .= 'background-color: ' . htmlspecialchars($highlight) . ';';
            
            return '<span class="' . htmlspecialchars($class) . '" style="' . $style . '">' . $text . '</span>';
        }, $content);

        // 9. [typewriter] / [sidebar] / [note] alias
        $content = preg_replace_callback('/\[(typewriter|sidebar|note)\](.*?)\[\/\1\]/is', function($matches) {
            $inner = trim($matches[2]);
            // Clean up Markdown-induced paragraph tags that often wrap shortcode boundaries
            $inner = preg_replace('/^<\/p>\s*/i', '', $inner);
            $inner = preg_replace('/\s*<p>$/i', '', $inner);
            return '<div class="typewriter-text">' . $inner . '</div>';
        }, $content);

        // 10. [info ...] / [warning ...] / [blockquote ...] / [pullquote ...] / [infobox ...] aliases
        $content = preg_replace_callback('/\[(infobox|info|warning|blockquote|pullquote)\s*(.*?)\](.*?)\[\/\1\]/is', function($matches) {
            $tag = strtolower($matches[1]);
            $attrString = $matches[2];
            $inner = trim($matches[3]);
            
            // Clean up Markdown-induced paragraph tags that often wrap shortcode boundaries
            $inner = preg_replace('/^<\/p>\s*/i', '', $inner);
            $inner = preg_replace('/\s*<p>$/i', '', $inner);
            
            $attrs = self::parseAttributes($attrString);
            
            return self::renderComponentHtml($tag, $attrs, $inner);
        }, $content);

        // 11. [component ...]content[/component]
        $content = preg_replace_callback('/\[component\s*(.*?)\](.*?)\[\/component\]/is', function($matches) {
            $attrs = self::parseAttributes($matches[1]);
            $name = $attrs['name'] ?? '';
            $slot = trim($matches[2]);
            
            // Clean up Markdown-induced paragraph tags that often wrap shortcode boundaries
            $slot = preg_replace('/^<\/p>\s*/i', '', $slot);
            $slot = preg_replace('/\s*<p>$/i', '', $slot);

            if (self::$themeEngine) {
                try {
                    $rendered = self::$themeEngine->partial($name, array_merge(['slot' => $slot], $attrs));
                    return self::process($rendered);
                } catch (\Exception $e) {
                    // Fall back to hardcoded defaults if no layout file matches
                }
            }
            
            if ($name === 'info' || $name === 'warning' || $name === 'blockquote' || $name === 'pullquote') {
                return self::renderComponentHtml($name, $attrs, $slot);
            }
            
            if ($name === 'typewriter' || $name === 'sidebar' || $name === 'note') {
                return '<div class="typewriter-text">' . $slot . '</div>';
            }
            
            if ($name === 'alertbox' || $name === 'warning_box') {
                $type = ($name === 'warning_box') ? 'intent-danger' : 'intent-warning';
                return '<div class="infobox-text p-6 my-6 border-2 border-dashed border-border-color ' . $type . '">' . $slot . '</div>';
            }

            if ($name === 'team_bio') {
                return '<div class="component-team_bio">' . $slot . '</div>';
            }

            if ($name === 'report_cta' || $name === 'reportCTA') {
                // Match simple pattern for title and buttons if they exist
                return '<div class="component-report_cta">' . $slot . '</div>';
            }

            if ($name === 'specialCTA') {
                return '<div class="component-specialCTA">' . $slot . '</div>';
            }

            if ($name === 'report_header') {
                return '<div class="component-report_header">' . $slot . '</div>';
            }
            
            return '<div class="custom-component component-' . htmlspecialchars($name) . '">' . $slot . '</div>';
        }, $content);

        // 12. [link="slug" section="..."]Link Text[/link]
        $content = preg_replace_callback('/\[link\s*(.*?)\](.*?)\[\/link\]/is', function($matches) {
            $attrString = $matches[1];
            $text = $matches[2];
            
            $attrs = self::parseAttributes($attrString);
            
            // Handle [link="slug"] or [link slug="slug"]
            $slug = $attrs['default'] ?? $attrs['slug'] ?? '';
            
            // If it was [link="slug"], 'default' will be '="slug"' in some cases, so we clean it
            $slug = trim($slug, '="\' ');
            
            $isExternal = preg_match('~^https?://~', $slug);
            $targetAttr = '';

            if ($isExternal) {
                $url = $slug;
                $targetAttr = ' target="_blank" rel="noopener noreferrer"';
            } else {
                $section = isset($attrs['section']) ? strtolower(trim((string)$attrs['section'])) : null;
                $url = self::resolveContentUrl($slug, $section);
            }
            
            return '<a href="' . $url . '"' . $targetAttr . '>' . $text . '</a>';
        }, $content);

        // 13. [expand] / [embed] — site-owned post transclusion
        $content = preg_replace_callback('/\[(expand|embed)\s*(.*?)\]/is', function ($matches) {
            $mode = strtolower($matches[1]);
            $attrs = self::parseAttributes($matches[2]);

            $slug = trim((string)($attrs['slug'] ?? $attrs['default'] ?? ''), "=\"' ");
            $heading = isset($attrs['heading']) ? trim((string)$attrs['heading']) : null;
            $linkText = isset($attrs['text']) ? trim((string)$attrs['text']) : null;
            $source = isset($attrs['source']) ? trim((string)$attrs['source']) : null;
            if ($heading === '') {
                $heading = null;
            }
            if ($linkText === '') {
                $linkText = null;
            }
            if ($source === '') {
                $source = null;
            }

            if ($slug !== '' && str_contains($slug, '#') && ($heading === null || $heading === '')) {
                $parts = explode('#', $slug, 2);
                $slug = $parts[0];
                $heading = $parts[1] !== '' ? $parts[1] : null;
            }

            if ($slug === '') {
                return '';
            }

            // source + heading together is invalid; unknown source → silent omit
            if ($source !== null && $heading !== null) {
                return '';
            }
            if ($source !== null && $source !== 'deck' && $source !== 'summary') {
                return '';
            }

            $siteId = 'default';
            if (self::$themeEngine !== null && method_exists(self::$themeEngine, 'getSiteId')) {
                $siteId = (string) self::$themeEngine->getSiteId();
            }
            $readMore = 'Read more';
            if (
                self::$themeEngine !== null
                && method_exists(self::$themeEngine, 'uiString')
            ) {
                $readMore = (string) self::$themeEngine->uiString(
                    'readMore',
                    self::$language,
                    $readMore
                );
            }
            $resolver = new ExpandResolver(
                new InternalAPIClient($siteId),
                self::$language,
                $readMore
            );
            $bodyHtml = $resolver->resolve($slug, $heading, $mode, $source);

            // Missing / unpublished / empty summary|deck → silent omit (reader-facing)
            if ($bodyHtml === null) {
                return '';
            }

            // Label: text → heading → post display title → slug
            $labelSource = $linkText ?: $heading ?: $resolver->resolveDisplayTitle($slug) ?: $slug;
            $label = htmlspecialchars($labelSource, ENT_QUOTES, 'UTF-8');
            $slugAttr = htmlspecialchars($slug, ENT_QUOTES, 'UTF-8');
            $headingAttr = $heading
                ? ' data-heading="' . htmlspecialchars($heading, ENT_QUOTES, 'UTF-8') . '"'
                : '';
            $sourceAttr = $source
                ? ' data-source="' . htmlspecialchars($source, ENT_QUOTES, 'UTF-8') . '"'
                : '';

            if ($mode === 'embed') {
                return '<div class="traven-embed" data-slug="' . $slugAttr . '"' . $headingAttr . $sourceAttr . '>'
                    . '<div class="traven-embed-content">' . $bodyHtml . '</div></div>';
            }

            // Phrasing-safe: button + template stay inside <p>; initExpandEmbed() inserts the panel.
            $id = 'traven-ee-' . bin2hex(random_bytes(6));
            return '<button type="button" class="traven-expand-trigger" data-traven-expand="' . $id . '"'
                . ' data-slug="' . $slugAttr . '"' . $headingAttr . $sourceAttr . ' aria-expanded="false">' . $label . '</button>'
                . '<template id="' . $id . '">' . $bodyHtml . '</template>';
        }, $content);

        // Cleanup: Remove <p> tags that wrap block-level elements generated by shortcodes
        $content = preg_replace('/<p>\s*(<(?:div|blockquote|section|article|figure|details).*?>.*?<\/(?:div|blockquote|section|article|figure|details)>)\s*<\/p>/is', '$1', $content);

        // Restore code block placeholders
        if (!empty($placeholders)) {
            $content = str_replace(array_keys($placeholders), array_values($placeholders), $content);
        }

        return $content;
    }

    /**
     * Process shortcodes for raw Markdown output, stripping structural tags
     * and converting elements to pure Markdown equivalents.
     */
    public static function processForMarkdown($content) {
        if (empty($content)) return '';

        $placeholders = [];
        $placeholderIndex = 0;

        // Match fenced code blocks (``` ... ```)
        $content = preg_replace_callback('/(```[a-z]*\n.*?\n```)/is', function($matches) use (&$placeholders, &$placeholderIndex) {
            $key = "<!--MD_CODE_BLOCK_PLACEHOLDER_{$placeholderIndex}-->";
            $placeholders[$key] = $matches[1];
            $placeholderIndex++;
            return $key;
        }, $content);

        // Match inline backtick code blocks (`...`)
        $content = preg_replace_callback('/(`[^`\n]+`)/is', function($matches) use (&$placeholders, &$placeholderIndex) {
            $key = "<!--MD_CODE_BLOCK_PLACEHOLDER_{$placeholderIndex}-->";
            $placeholders[$key] = $matches[1];
            $placeholderIndex++;
            return $key;
        }, $content);

        // [image src="..." alt="..." caption="..." ...] -> ![alt](src)\n_caption_
        $content = preg_replace_callback('/\[image\s+(.*?)\]/is', function($matches) {
            $attrs = self::parseAttributes($matches[1]);
            $src = $attrs['src'] ?? '';
            $alt = $attrs['alt'] ?? '';
            $caption = $attrs['caption'] ?? '';
            
            $md = "![" . $alt . "](" . $src . ")";
            if ($caption) {
                $md .= "\n\n*" . trim($caption) . "*\n";
            }
            return $md;
        }, $content);

        // [figure src="..." alt="..." caption="..." ...] -> ![alt](src)\n_caption_
        $content = preg_replace_callback('/\[figure\s+(.*?)\](?:(.*?)\[\/figure\])?/is', function($matches) {
            $attrs = self::parseAttributes($matches[1]);
            $innerContent = $matches[2] ?? ''; 
            
            $src = $attrs['src'] ?? '';
            $alt = $attrs['alt'] ?? '';
            $caption = ($attrs['caption'] ?? '') ?: $innerContent;
            
            $md = "![" . $alt . "](" . $src . ")";
            if (trim($caption)) {
                $md .= "\n\n*" . trim($caption) . "*\n";
            }
            return $md;
        }, $content);

        // [youtube src="..." ...] -> [Video](https://www.youtube.com/watch?v=...)
        $content = preg_replace_callback('/\[youtube\s+(.*?)\]/is', function($matches) {
            $attrs = self::parseAttributes($matches[1]);
            $src = $attrs['src'] ?? '';
            $caption = $attrs['caption'] ?? 'Video';
            return "[" . $caption . "](https://www.youtube.com/watch?v=" . $src . ")";
        }, $content);

        // [video src="..." ...] -> [Video](src)
        $content = preg_replace_callback('/\[video\s+(.*?)\]/is', function($matches) {
            $attrs = self::parseAttributes($matches[1]);
            $src = $attrs['src'] ?? '';
            $caption = $attrs['caption'] ?? 'Video';
            return "[" . $caption . "](" . $src . ")";
        }, $content);

        // [audio src="..." ...] -> [Audio](src)
        $content = preg_replace_callback('/\[audio\s+(.*?)\]/is', function($matches) {
            $attrs = self::parseAttributes($matches[1]);
            $src = $attrs['src'] ?? '';
            $caption = $attrs['caption'] ?? 'Audio';
            return "[" . $caption . "](" . $src . ")";
        }, $content);

        // [component ...]content[/component] -> content
        $content = preg_replace('/\[component\s*(.*?)\](.*?)\[\/component\]/is', '$2', $content);

        // Structural tags that have content inside we want to keep
        $content = preg_replace('/\[(typewriter|sidebar|note|infobox|info|warning)\s*(.*?)\](.*?)\[\/\1\]/is', '$3', $content);
        $content = preg_replace('/\[(blockquote|pullquote|quote)\s*(.*?)\](.*?)\[\/\1\]/is', '> $3', $content);
        $content = preg_replace('/\[align\s+(.*?)\](.*?)\[\/align\]/is', '$2', $content);
        $content = preg_replace('/\[highlight\s*(.*?)\](.*?)\[\/highlight\]/is', '$2', $content);
        $content = preg_replace('/\[color\s*(.*?)\](.*?)\[\/color\]/is', '$2', $content);
        $content = preg_replace('/\[span\s*(.*?)\](.*?)\[\/span\]/is', '$2', $content);
        $content = preg_replace('/\[redact\](.*?)\[\/redact\]/is', '$1', $content);

        // [link="slug"]Link Text[/link] -> [Link Text](url)
        $content = preg_replace_callback('/\[link\s*(.*?)\](.*?)\[\/link\]/is', function($matches) {
            $attrString = $matches[1];
            $text = trim($matches[2]);
            
            $attrs = self::parseAttributes($attrString);
            
            $slug = $attrs['default'] ?? $attrs['slug'] ?? '';
            $slug = trim($slug, '="\' ');
            
            $isExternal = preg_match('~^https?://~', $slug);

            if ($isExternal) {
                $url = $slug;
            } elseif (defined('STATIC_BUILD') && STATIC_BUILD) {
                // Point to index.md for agents
                $url = self::$basePath . $slug . '/index.md';
            } else {
                $url = "post.php?slug=" . urlencode($slug);
                if (isset($attrs['section'])) {
                    $url .= "&section=" . urlencode(strtolower(trim($attrs['section'])));
                }
            }
            
            return '[' . $text . '](' . $url . ')';
        }, $content);

        // [expand]/[embed] → readable markdown reference for agents
        $content = preg_replace_callback('/\[(expand|embed)\s*(.*?)\]/is', function ($matches) {
            $mode = strtolower($matches[1]);
            $attrs = self::parseAttributes($matches[2]);
            $slug = trim((string)($attrs['slug'] ?? $attrs['default'] ?? ''), "=\"' ");
            $heading = isset($attrs['heading']) ? trim((string)$attrs['heading']) : '';
            if ($slug !== '' && str_contains($slug, '#') && $heading === '') {
                $parts = explode('#', $slug, 2);
                $slug = $parts[0];
                $heading = $parts[1] ?? '';
            }
            if ($slug === '') {
                return '';
            }
            $label = $heading !== '' ? "{$slug}#{$heading}" : $slug;
            return "[{$mode}: {$label}](post.php?slug=" . rawurlencode($slug) . ")";
        }, $content);

        // Restore markdown code block placeholders
        if (!empty($placeholders)) {
            $content = str_replace(array_keys($placeholders), array_values($placeholders), $content);
        }

        return $content;
    }

    /**
     * Resolves an asset path based on the current context.
     */
    public static function resolveAsset($path) {
        if (empty($path)) return '';
        if (preg_match('~^https?://~', $path)) return $path;
        
        $cleanPath = ltrim($path, '/');
        if (str_starts_with($cleanPath, 'data:')) return $path;

        // Prefer ThemeEngine when available (site-scoped live URLs)
        if (self::$themeEngine !== null && method_exists(self::$themeEngine, 'contentAsset')) {
            return self::$themeEngine->contentAsset($cleanPath);
        }
        
        // Strip legacy 'assets/' prefix if it exists, as basePath already represents the assets root
        if (str_starts_with($cleanPath, 'assets/')) {
            $cleanPath = substr($cleanPath, 7);
        }
        
        // Strip API raw assets prefix if it exists
        if (str_starts_with($cleanPath, 'api/assets/raw/')) {
            $cleanPath = substr($cleanPath, 15);
        }

        // Strip sites/{id}/assets/ so joining basePath does not double the site segment
        if (preg_match('#^sites/[^/]+/assets/(.+)$#', $cleanPath, $m)) {
            $cleanPath = $m[1];
        }
        
        // If the base path ends with 'images/' and the path starts with 'images/', remove the redundancy
        if (str_ends_with(self::$basePath, 'images/') && str_starts_with($cleanPath, 'images/')) {
            $cleanPath = substr($cleanPath, 7);
        }
        
        return self::$basePath . $cleanPath;
    }

    private static function formatComponentBody($content) {
        $lines = preg_split('/\r?\n/', $content);
        $paragraphs = [];
        foreach ($lines as $line) {
            $line = trim($line);
            if ($line === '') {
                continue;
            }
            if (preg_match('/^<p\b[^>]*>(.*?)<\/p>$/is', $line, $matches)) {
                $line = $matches[1];
            }
            $paragraphs[] = '<p>' . $line . '</p>';
        }
        return implode("\n", $paragraphs);
    }

    public static function renderComponentHtml($tag, $attrs, $innerContent) {
        $formattedBody = self::formatComponentBody($innerContent);

        if ($tag === 'blockquote') {
            $author = $attrs['author'] ?? '';
            $source = $attrs['source'] ?? '';
            $citation = '';
            if ($author && $source) {
                $citation = '&mdash; ' . htmlspecialchars($author) . ', ' . htmlspecialchars($source);
            } elseif ($author || $source) {
                $citation = '&mdash; ' . htmlspecialchars($author ?: $source);
            }
            
            $html = '<blockquote class="traven-component-blockquote">';
            $html .= '<div class="component-body">' . $formattedBody . '</div>';
            if ($citation) {
                $html .= '<cite class="attribution">' . $citation . '</cite>';
            }
            $html .= '</blockquote>';
            return $html;
        }
        
        if ($tag === 'pullquote') {
            return '<blockquote class="traven-component-pullquote"><div class="component-body">' . $formattedBody . '</div></blockquote>';
        }
        
        if ($tag === 'info' || $tag === 'warning' || $tag === 'infobox') {
            $mappedTag = ($tag === 'infobox') ? 'info' : $tag;
            $title = $attrs['title'] ?? '';
            $collapsible = isset($attrs['collapsible']) && ($attrs['collapsible'] === 'true');
            $headerText = $title ?: ($collapsible ? ucfirst($mappedTag) : '');
            
            if ($collapsible) {
                $html = '<details class="traven-component traven-component-' . $mappedTag . '" open>';
                $html .= '<summary class="component-header"><span class="component-title">' . htmlspecialchars($headerText) . '</span></summary>';
                $html .= '<div class="component-body">' . $formattedBody . '</div>';
                $html .= '</details>';
            } else {
                $html = '<div class="traven-component traven-component-' . $mappedTag . '">';
                if ($headerText !== '') {
                    $html .= '<div class="component-header"><span class="component-title">' . htmlspecialchars($headerText) . '</span></div>';
                }
                $html .= '<div class="component-body">' . $formattedBody . '</div>';
                $html .= '</div>';
            }
            return $html;
        }
        
        return $formattedBody;
    }

    private static function parseAttributes($attrString) {
        $attributes = [];
        
        // Match attribute="value", attribute='value', attribute=&quot;value&quot;, or attribute=&#039;value&#039;
        // The closing quote must be followed by another attribute (whitespace + word + "=") OR the end of the string
        $pattern = '/(\w+)\s*=\s*(["\']|&quot;|&#039;)(.*?)\2(?=\s+\w+\s*=|\s*$)/i';
        
        if (preg_match_all($pattern, $attrString, $matches)) {
            for ($i = 0; $i < count($matches[1]); $i++) {
                $attributes[$matches[1][$i]] = html_entity_decode($matches[3][$i]);
            }
        }
        
        // Remove the matched attributes from the string to find any remaining default/positional value
        $remaining = trim(preg_replace($pattern, '', $attrString));
        
        // Fallback for positional values like [align center] or [link="slug"] where '="slug"' is left over
        if (!empty($remaining)) {
             $default = html_entity_decode($remaining);
             $attributes['default'] = trim($default, '"\' ');
        }
        
        return $attributes;
    }
}
