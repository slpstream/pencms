<?php

/**
 * Automatically applies a dropcap to the first letter of the first paragraph in a string of HTML.
 * 
 * @param string $html The HTML content to process.
 * @return string The processed HTML with the dropcap applied.
 */
function apply_dropcap($html) {
    if (empty($html)) return $html;

    // Pattern to match the first <p> tag and capture its content
    // We look for the first <p> that isn't inside a div or other container that might not be the main body
    // However, in our architecture, the content is already the body of the article.
    
    $pattern = '/<p>(.*?)<\/p>/is';
    
    return preg_replace_callback($pattern, function($matches) {
        static $count = 0;
        if ($count > 0) return $matches[0]; // Only apply to the first paragraph
        
        $text = $matches[1];
        
        // Find the first alphanumeric character
        if (preg_match('/^(\s*(?:<[^>]+>)*\s*)([a-zA-Z])(.*)$/us', $text, $parts)) {
            $prefix = $parts[1]; // Any leading tags or whitespace
            $first_letter = $parts[2];
            $remainder = $parts[3];
            
            $count++;
            return "<p>{$prefix}<span class=\"dropcap\">{$first_letter}</span>{$remainder}</p>";
        }
        
        return $matches[0];
    }, $html, 1);
}

/**
 * Smart title casing that preserves acronyms and handles common small words.
 * 
 * @param string $title The title to process.
 * @return string The processed title.
 */
function smart_title_case($title) {
    if (empty($title)) return $title;

    $words = explode(' ', $title);
    $acronyms = ['IBM', 'CIA', 'FBI', 'NSA', 'KGB', 'MI6', 'OSS', 'RKK', 'ACS'];
    $small_words = ['at', 'in', 'the', 'of', 'and', 'a', 'an', 'to', 'for', 'by', 'on'];

    foreach ($words as $i => &$word) {
        $upper = strtoupper($word);
        if (in_array($upper, $acronyms)) {
            $word = $upper;
        } elseif ($i > 0 && in_array(strtolower($word), $small_words)) {
            $word = strtolower($word);
        } else {
            // Only capitalize if it's not already mixed case or all caps
            if ($word === strtolower($word)) {
                $word = ucfirst($word);
            }
        }
    }

    return implode(' ', $words);
}
