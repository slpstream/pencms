<?php
/**
 * Author-facing health check for [[slug]] / [[!slug]] / [[>slug]] references.
 * Scans markdown for wikilinks and reports missing / unpublished targets.
 */
namespace Dossier;

require_once __DIR__ . '/ExpandResolver.php';
require_once __DIR__ . '/WikilinkProcessor.php';
require_once __DIR__ . '/InternalAPIClient.php';

class ExpandReferenceHealth {
    /**
     * @param string $markdown
     * @param string|null $siteId
     * @return array{ok: bool, broken: list<array{slug: string, heading: ?string, mode: string, reason: string}>}
     */
    public static function check(string $markdown, ?string $siteId = null): array {
        $broken = [];
        if ($markdown === '') {
            return ['ok' => true, 'broken' => []];
        }

        $refs = self::scanWikilinks($markdown);
        if ($refs === []) {
            return ['ok' => true, 'broken' => []];
        }

        $api = new InternalAPIClient($siteId);
        $resolver = new ExpandResolver($api);

        foreach ($refs as $ref) {
            $slug = $ref['slug'];
            $heading = $ref['heading'];
            $mode = $ref['mode'];
            if ($slug === '') {
                $broken[] = ['slug' => '', 'heading' => $heading, 'mode' => $mode, 'reason' => 'missing_slug'];
                continue;
            }
            $html = $resolver->resolve($slug, $heading, $mode === 'link' ? 'expand' : $mode);
            if ($html === null) {
                $broken[] = [
                    'slug' => $slug,
                    'heading' => $heading,
                    'mode' => $mode,
                    'reason' => 'not_found_or_unpublished',
                ];
            }
        }

        return ['ok' => count($broken) === 0, 'broken' => $broken];
    }

    /**
     * Linear same-line scan for [[…]] spans (code spans not stashed here;
     * fenced/inline code hits are best-effort and resolve the same either way).
     * @return list<array{slug: string, heading: ?string, mode: string}>
     */
    private static function scanWikilinks(string $markdown): array {
        $refs = [];
        $len = strlen($markdown);
        $i = 0;
        while ($i < $len) {
            $open = strpos($markdown, '[[', $i);
            if ($open === false) {
                break;
            }
            $lineEnd = strpos($markdown, "\n", $open);
            if ($lineEnd === false) {
                $lineEnd = $len;
            }
            $close = strpos($markdown, ']]', $open + 2);
            if ($close === false || $close > $lineEnd) {
                $i = $open + 2;
                continue;
            }
            $parsed = WikilinkProcessor::parseWikilinkAttrs(substr($markdown, $open, $close + 2 - $open));
            if (trim((string) ($parsed['slug'] ?? '')) !== '') {
                $refs[] = [
                    'slug' => trim((string) $parsed['slug']),
                    'heading' => $parsed['heading'] ?? null,
                    'mode' => $parsed['mode'] ?? 'link',
                ];
            }
            $i = $close + 2;
        }
        return $refs;
    }
}
