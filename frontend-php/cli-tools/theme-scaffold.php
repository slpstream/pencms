<?php

/**
 * PenCMS Theme Scaffolder
 * Creates a new theme with dual-duty stubs: content skin, traven-preview
 * markup, editor_skin, and a complete social_preview block.
 */

if ($argc < 2) {
    echo "Usage: php theme-scaffold.php <theme-name>\n";
    exit(1);
}

$rawName = strtolower(trim((string) $argv[1]));
if ($rawName === '' || str_starts_with($rawName, '_')) {
    echo "❌ Error: Theme name must be non-empty and must not start with '_'\n";
    echo "   (reserved for _deprecated / _asset-kits kit directories).\n";
    exit(1);
}

$themeName = preg_replace('/[^a-z0-9-]/', '', $rawName);
$themesDir = __DIR__ . '/../src/blog/themes';
$targetDir = $themesDir . '/' . $themeName;

if ($themeName === '') {
    echo "❌ Error: Theme name must contain at least one a-z, 0-9, or hyphen.\n";
    exit(1);
}

if ($themeName === 'custom') {
    echo "❌ Error: Theme name 'custom' is reserved for per-site theme forks.\n";
    echo "   (content/sites/{id}/theme/ — do not scaffold an install theme named custom.)\n";
    exit(1);
}

if (is_dir($targetDir)) {
    echo "❌ Error: Theme '{$themeName}' already exists.\n";
    exit(1);
}

echo "🚀 Scaffolding theme: {$themeName}...\n";

$dirs = [
    '',
    '/assets',
    '/assets/css',
    '/assets/js',
    '/assets/fonts',
    '/assets/images',
    '/partials',
    '/templates',
];

foreach ($dirs as $dir) {
    if (!mkdir($targetDir . $dir, 0777, true)) {
        echo "❌ Error: Could not create directory {$targetDir}{$dir}\n";
        exit(1);
    }
}

$displayName = ucwords(str_replace('-', ' ', $themeName));

// Create a baseline theme.json matching the dual-duty / OG contract
$manifest = [
    'type' => 'native',
    'name' => $displayName,
    'version' => '1.0.0',
    'author' => 'Unknown',
    'license' => 'MIT',
    'description' => "Scaffolded PenCMS theme: {$displayName}.",
    'editor_skin' => $themeName,
    'supports' => [
        'toc' => true,
        'hero_image' => true,
        'composite' => true,
        'seo_meta' => true,
        'custom_fonts' => false,
        'sidebars' => false,
        'markdown_alternate' => true,
    ],
    'variables' => [
        'hero_title' => ['type' => 'string', 'required' => true],
        'posts' => ['type' => 'array', 'required' => false],
        'dossiers' => ['type' => 'array', 'required' => false],
        'page_title' => ['type' => 'string', 'required' => false],
    ],
    'social_preview' => [
        'og_accent_color' => '#2563EB',
        'og_vignette_color' => '#64748B',
        'og_text_color' => '#FFFFFF',
        'og_bar_color' => '#0F172A',
        'og_font' => 'CourierPrime-Bold',
        'og_fonts' => new stdClass(),
        'og_headline_style' => 'plain',
        'og_text_case' => 'title',
        'og_grade_preset' => 'clean',
        'og_accent_bar' => true,
        'og_watermark' => null,
        'og_default_hero' => 'assets/images/defaulthero.jpg',
        'og_default_image' => null,
        'og_fallback_title' => 'Untitled',
        'og_title_fallback' => null,
        'og_description_fallback' => null,
        'twitter_card' => 'summary_large_image',
    ],
];

file_put_contents(
    $targetDir . '/theme.json',
    json_encode($manifest, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n"
);

// Create baseline templates (post, index, page, archive)
file_put_contents($targetDir . '/templates/post.html.twig',
    "{{ theme.partial('head') | raw }}\n" .
    "{{ theme.partial('header') | raw }}\n" .
    "{{ theme.partial('navbar') | raw }}\n\n" .
    "<article>\n" .
    "    <h1>{{ hero_title }}</h1>\n" .
    "    {% for post in posts %}\n" .
    "        <div class=\"article-content traven-preview\">{{ post.content_html | raw }}</div>\n" .
    "    {% endfor %}\n" .
    "</article>\n\n" .
    "{{ theme.partial('comment-thread') | raw }}\n" .
    "{{ theme.partial('feedback-form', { kind: 'comment', parent_slug: slug is defined ? slug : '' }) | raw }}\n" .
    "{{ theme.partial('footer') | raw }}\n"
);

file_put_contents($targetDir . '/templates/index.html.twig',
    "{{ theme.partial('head') | raw }}\n" .
    "{{ theme.partial('header') | raw }}\n" .
    "{{ theme.partial('navbar') | raw }}\n\n" .
    "<main>\n" .
    "    <h1>{{ hero_title }}</h1>\n" .
    "    {% for dossier in dossiers %}\n" .
    "        <a href=\"{{ dossier.slug }}\">{{ dossier.hero_title }}</a>\n" .
    "    {% endfor %}\n" .
    "</main>\n\n" .
    "{{ theme.partial('footer') | raw }}\n"
);

file_put_contents($targetDir . '/templates/page.html.twig',
    "{{ theme.partial('head') | raw }}\n" .
    "{{ theme.partial('header') | raw }}\n" .
    "{{ theme.partial('navbar') | raw }}\n\n" .
    "<article>\n" .
    "    <h1>{{ hero_title }}</h1>\n" .
    "    <div class=\"article-content traven-preview\">{{ page_content | raw }}</div>\n" .
    "</article>\n\n" .
    "{{ theme.partial('footer') | raw }}\n"
);

file_put_contents($targetDir . '/templates/archive.html.twig',
    "{{ theme.partial('head') | raw }}\n" .
    "{{ theme.partial('header') | raw }}\n" .
    "{{ theme.partial('navbar') | raw }}\n\n" .
    "<main>\n" .
    "    <h1>{{ hero_title }}</h1>\n" .
    "    {% for item in dossiers %}\n" .
    "        <a href=\"{{ item.slug }}\">{{ item.hero_title }}</a>\n" .
    "    {% endfor %}\n" .
    "</main>\n\n" .
    "{{ theme.partial('footer') | raw }}\n"
);

// Search page — required by static publish (generate-static.php → search/index.html)
file_put_contents($targetDir . '/templates/search.html.twig',
    "{{ theme.partial('head') | raw }}\n" .
    "{{ theme.partial('header') | raw }}\n" .
    "{{ theme.partial('navbar') | raw }}\n\n" .
    "<main>\n" .
    "    <h1>{{ hero_title | default('Search') }}</h1>\n" .
    "    <div\n" .
    "        id=\"pencms-search\"\n" .
    "        class=\"pencms-search\"\n" .
    "        data-search-index-url=\"{{ search_index_url | default('') }}\"\n" .
    "        data-static=\"{{ theme.isStatic() ? '1' : '0' }}\"\n" .
    "        data-base-path=\"{{ base_path }}\"\n" .
    "        data-web-root=\"{{ base_path }}\"\n" .
    "    >\n" .
    "        <label class=\"search-label\" for=\"search-input\">Search</label>\n" .
    "        <input type=\"search\" id=\"search-input\" class=\"search-input\" name=\"q\" placeholder=\"Search posts and pages…\" autocomplete=\"off\" enterkeyhint=\"search\">\n" .
    "        {% if search_index_json is defined and search_index_json is not null %}\n" .
    "        <script type=\"application/json\" id=\"search-index-data\">{{ search_index_json | raw }}</script>\n" .
    "        {% endif %}\n" .
    "        <div id=\"search-results\" class=\"search-results\" aria-live=\"polite\"></div>\n" .
    "    </div>\n" .
    "</main>\n\n" .
    "<script src=\"{{ publicAsset('vendor/minisearch/minisearch.min.js') }}\"></script>\n" .
    "<script src=\"{{ publicAsset('vendor/minisearch/search-ui.js') }}\"></script>\n\n" .
    "{{ theme.partial('footer') | raw }}\n"
);

// Create baseline partials (Sass-style underscored naming)
file_put_contents($targetDir . '/partials/_head.html.twig', "<!DOCTYPE html>
<html>
<head>
    <title>{{ page_title | default('{$displayName}') }}</title>
    {{ theme.linkCss('css/skin-{$themeName}.css') | raw }}
    {{ theme.linkCss('css/styles.css') | raw }}
</head>
<body>
");

file_put_contents($targetDir . '/partials/_header.html.twig', "<header class=\"site-header\">
    <div class=\"header-container\">
        <a href=\"{{ base_path }}\" class=\"site-title\">{{ sitename }}</a>
    </div>
</header>
");

file_put_contents($targetDir . '/partials/_navbar.html.twig', "<button class=\"mobile-menu-toggle\" id=\"mobile-menu-toggle\" aria-label=\"Toggle menu\">
    <svg viewBox=\"0 0 24 24\" class=\"w-6 h-6\"><path d=\"M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z\"/></svg>
</button>

<nav class=\"nav-menu\" id=\"nav-menu\">
    {% set nav_items = menu('primary') %}
    {% for item in nav_items %}
        <div class=\"nav-item{% if item.children is not empty %} has-children{% endif %}\">
            {% if item.target_type == 'label' %}
                <span class=\"nav-label{% if item.children is not empty %} nav-trigger{% endif %}\">{{ item.label }}</span>
            {% else %}
                <a href=\"{{ item.url }}\" class=\"nav-link{% if item.children is not empty %} nav-trigger{% endif %}\" {% if item.open_in_new_tab %}target=\"_blank\" rel=\"noopener\"{% endif %}>{{ item.label }}</a>
            {% endif %}
            {% if item.children is not empty %}
                <div class=\"nav-dropdown\" role=\"menu\">
                    {% for child in item.children %}
                        {% if child.target_type == 'label' %}
                            <span class=\"nav-label\">{{ child.label }}</span>
                        {% else %}
                            <a href=\"{{ child.url }}\" class=\"nav-link\" role=\"menuitem\" {% if child.open_in_new_tab %}target=\"_blank\" rel=\"noopener\"{% endif %}>{{ child.label }}</a>
                        {% endif %}
                    {% endfor %}
                </div>
            {% endif %}
        </div>
    {% endfor %}
</nav>
");

file_put_contents($targetDir . '/partials/_sidebar-secondary.html.twig', "{% set secondary_items = menu('secondary') %}
{% if secondary_items is not empty %}
<div class=\"sidebar-widget secondary-nav-widget\">
    <h3 class=\"sidebar-title\">Navigation</h3>
    <ul class=\"sidebar-list secondary-nav-list\">
        {% for item in secondary_items %}
            <li class=\"sidebar-list-item{% if item.children is not empty %} has-children{% endif %}\">
                {% if item.target_type == 'label' %}
                    <span class=\"sidebar-nav-label\">{{ item.label }}</span>
                {% else %}
                    <a href=\"{{ item.url }}\" class=\"sidebar-list-link\" {% if item.open_in_new_tab %}target=\"_blank\" rel=\"noopener\"{% endif %}>{{ item.label }}</a>
                {% endif %}
                {% if item.children is not empty %}
                    <ul class=\"sidebar-list secondary-nav-children\">
                        {% for child in item.children %}
                            <li class=\"sidebar-list-item\">
                                {% if child.target_type == 'label' %}
                                    <span class=\"sidebar-nav-label\">{{ child.label }}</span>
                                {% else %}
                                    <a href=\"{{ child.url }}\" class=\"sidebar-list-link\" {% if child.open_in_new_tab %}target=\"_blank\" rel=\"noopener\"{% endif %}>{{ child.label }}</a>
                                {% endif %}
                            </li>
                        {% endfor %}
                    </ul>
                {% endif %}
            </li>
        {% endfor %}
    </ul>
</div>
{% endif %}
");

file_put_contents($targetDir . '/partials/_footer.html.twig', "<footer class=\"site-footer\">
    <div class=\"footer-container\">
        {% set footer_items = menu('footer') %}
        {% if footer_items is not empty %}
            <nav class=\"footer-menu\" aria-label=\"Footer\">
                {% for item in footer_items %}
                    <div class=\"footer-menu-group\">
                        {% if item.target_type == 'label' %}
                            <span class=\"footer-menu-label\">{{ item.label }}</span>
                        {% else %}
                            <a href=\"{{ item.url }}\" class=\"footer-menu-link\" {% if item.open_in_new_tab %}target=\"_blank\" rel=\"noopener\"{% endif %}>{{ item.label }}</a>
                        {% endif %}
                        {% if item.children is not empty %}
                            <ul class=\"footer-menu-children\">
                                {% for child in item.children %}
                                    <li>
                                        {% if child.target_type == 'label' %}
                                            <span class=\"footer-menu-label footer-menu-label-child\">{{ child.label }}</span>
                                        {% else %}
                                            <a href=\"{{ child.url }}\" class=\"footer-menu-link\" {% if child.open_in_new_tab %}target=\"_blank\" rel=\"noopener\"{% endif %}>{{ child.label }}</a>
                                        {% endif %}
                                    </li>
                                {% endfor %}
                            </ul>
                        {% endif %}
                    </div>
                {% endfor %}
            </nav>
        {% endif %}
        {{ theme.partial('social-links') | raw }}
        <p class=\"footer-copy\">&copy; {{ \"now\"|date(\"Y\") }} {{ sitename }}</p>
    </div>
</footer>
</body>
</html>
");

file_put_contents($targetDir . '/partials/_social-links.html.twig', '{# Site-scoped social profile links (social_links global from ThemeEngine) #}
{% if social_links is defined and social_links is not empty %}
<div class="footer-social">
    {% for link in social_links %}
        {% if link.url|default(\'\') is not empty %}
            {% set platform = link.platform|default(\'custom\') %}
            {% if platform == \'custom\' %}
                {% set label = link.label|default(\'Link\') %}
            {% elseif platform == \'twitter\' %}
                {% set label = \'X (Twitter)\' %}
            {% elseif platform == \'bluesky\' %}
                {% set label = \'Bluesky\' %}
            {% elseif platform == \'mastodon\' %}
                {% set label = \'Mastodon\' %}
            {% elseif platform == \'instagram\' %}
                {% set label = \'Instagram\' %}
            {% elseif platform == \'facebook\' %}
                {% set label = \'Facebook\' %}
            {% elseif platform == \'vk\' %}
                {% set label = \'VK\' %}
            {% elseif platform == \'linkedin\' %}
                {% set label = \'LinkedIn\' %}
            {% elseif platform == \'github\' %}
                {% set label = \'GitHub\' %}
            {% elseif platform == \'telegram\' %}
                {% set label = \'Telegram\' %}
            {% elseif platform == \'youtube\' %}
                {% set label = \'YouTube\' %}
            {% elseif platform == \'tiktok\' %}
                {% set label = \'TikTok\' %}
            {% elseif platform == \'reddit\' %}
                {% set label = \'Reddit\' %}
            {% elseif platform == \'discord\' %}
                {% set label = \'Discord\' %}
            {% elseif platform == \'slack\' %}
                {% set label = \'Slack\' %}
            {% elseif platform == \'whatsapp\' %}
                {% set label = \'WhatsApp\' %}
            {% else %}
                {% set label = platform|title %}
            {% endif %}
            <a href="{{ link.url }}" target="_blank" rel="noopener noreferrer">{{ label }}</a>
        {% endif %}
    {% endfor %}
</div>
{% endif %}
');

// Chrome CSS
file_put_contents(
    $targetDir . '/assets/css/styles.css',
    "/* Theme chrome: {$themeName} — header, nav, cards (not loaded as editor content CSS) */\n" .
    "body { font-family: system-ui, sans-serif; margin: 0; }\n\n" .
    ".footer-social {\n" .
    "    display: flex;\n" .
    "    flex-wrap: wrap;\n" .
    "    gap: 0.75rem 1rem;\n" .
    "    margin-bottom: 0.5rem;\n" .
    "}\n\n" .
    ".footer-social a {\n" .
    "    color: inherit;\n" .
    "    text-decoration: none;\n" .
    "    font-size: 0.875rem;\n" .
    "}\n\n" .
    ".footer-social a:hover {\n" .
    "    text-decoration: underline;\n" .
    "}\n"
);

// Dual-duty content skin stub
file_put_contents(
    $targetDir . '/assets/css/skin-' . $themeName . '.css',
    "/* Dual-duty content skin: {$themeName}\n" .
    " * Scopes: .cm-editor (admin WYSIWYM) + .traven-preview (published HTML)\n" .
    " * Expand shortcode / alert / align×size rules per pencms-theme-development.md.\n" .
    " */\n\n" .
    ".cm-editor {\n" .
    "    font-family: system-ui, sans-serif;\n" .
    "    color: #1a1a1a;\n" .
    "    background-color: #ffffff;\n" .
    "}\n\n" .
    ".traven-preview {\n" .
    "    font-family: system-ui, sans-serif;\n" .
    "    color: #1a1a1a;\n" .
    "    background-color: #ffffff;\n" .
    "    line-height: 1.7;\n" .
    "}\n\n" .
    ".traven-preview h1,\n" .
    ".traven-preview h2,\n" .
    ".traven-preview h3,\n" .
    ".traven-preview h4,\n" .
    ".traven-preview h5,\n" .
    ".traven-preview h6 {\n" .
    "    line-height: 1.25;\n" .
    "}\n"
);

echo "✅ Theme '{$themeName}' created at themes/{$themeName}\n";
echo "💡 To activate, update config.ini: [theme] active = {$themeName}\n";
echo "💡 Add assets/images/defaulthero.jpg and TTF/OTF under assets/fonts/ (or keep empty og_fonts for engine fallback).\n";
echo "💡 Validate: php frontend-php/cli-tools/theme-validate.php {$themeName}\n";
