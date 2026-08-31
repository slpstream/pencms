<?php

namespace Dossier;

/**
 * Shared slug rules for taxonomy term → category archive URLs.
 * Must stay in sync with admin nav (settings-navigation.js) leaf slugification.
 */
class TaxonomySlug
{
    /**
     * Convert a taxonomy term (or "{vocab}/{term}" content_slug) to a category archive slug.
     * Takes the hierarchical leaf ("A / B" → "B"), lowercases, and replaces spaces with hyphens.
     * Punctuation like () and & is preserved to match nav/ThemeEngine URLs.
     */
    public static function termToCategorySlug(string $term): string
    {
        $leaf = trim($term);
        // content_slug form: "{vocab}/{term}" — vocab keys are [a-z0-9_]+; strip first segment only
        // so hierarchical " / " inside the term is not treated as a path separator.
        if (preg_match('#^([a-z0-9_]+)/(.+)$#i', $leaf, $m)) {
            $leaf = $m[2];
        }
        // Hierarchical path leaf: "Parent / Child" → "Child"
        if (($sep = strrpos($leaf, ' / ')) !== false) {
            $leaf = substr($leaf, $sep + 3);
        }
        return strtolower(str_replace(' ', '-', trim($leaf)));
    }
}
