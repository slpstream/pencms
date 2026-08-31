<?php
/**
 * Author-facing health check for [expand]/[embed] references.
 * Scans markdown for shortcodes and reports missing / unpublished targets.
 */
namespace Dossier;

require_once __DIR__ . '/ExpandResolver.php';
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

        if (!preg_match_all('/\[(expand|embed)\s*(.*?)\]/is', $markdown, $matches, PREG_SET_ORDER)) {
            return ['ok' => true, 'broken' => []];
        }

        $api = new InternalAPIClient($siteId);
        $resolver = new ExpandResolver($api);

        foreach ($matches as $m) {
            $mode = strtolower($m[1]);
            $attrs = self::parseAttrs($m[2]);
            $slug = trim((string)($attrs['slug'] ?? $attrs['default'] ?? ''), "=\"' ");
            $heading = isset($attrs['heading']) ? trim((string)$attrs['heading']) : null;
            if ($slug !== '' && str_contains($slug, '#') && ($heading === null || $heading === '')) {
                $parts = explode('#', $slug, 2);
                $slug = $parts[0];
                $heading = $parts[1] !== '' ? $parts[1] : null;
            }
            if ($slug === '') {
                $broken[] = ['slug' => '', 'heading' => $heading, 'mode' => $mode, 'reason' => 'missing_slug'];
                continue;
            }
            $html = $resolver->resolve($slug, $heading, $mode);
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

    private static function parseAttrs(string $attrString): array {
        // Mirror ShortcodeProcessor::parseAttributes enough for slug/heading/default
        $attrs = [];
        if (preg_match('/^\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s\]]+))/', $attrString, $m)) {
            $attrs['default'] = $m[1] ?? $m[2] ?? $m[3] ?? '';
        }
        if (preg_match_all('/([a-zA-Z0-9_-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s\]]+))/', $attrString, $ms, PREG_SET_ORDER)) {
            foreach ($ms as $m) {
                $attrs[$m[1]] = $m[2] !== '' ? $m[2] : ($m[3] !== '' ? $m[3] : ($m[4] ?? ''));
            }
        }
        return $attrs;
    }
}
