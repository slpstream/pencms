<?php
$pageTitle = "SEO Settings (PenCMS)";
$currentSection = "seo";
$pageScript = "settings-seo.js";
include "includes/_admin-auth.php";
include "includes/_admin-head.php";
?>

<body class="bg-canvas text-forge-black font-sans antialiased h-screen flex flex-col overflow-hidden"
      x-data="settingsSeo" x-init="init()">

    <!-- Header / Top Navigation -->
    <?php include "includes/_admin-header.php"; ?>

    <div class="flex flex-1 relative min-h-0 overflow-hidden">
        <!-- Collapsible Left Sidebar -->
        <?php include "includes/_admin-sidebar.php"; ?>

        <!-- Main Workspace Canvas -->
        <main class="flex-1 overflow-y-auto p-8 md:p-12 transition-all duration-300">
            <!-- Title Section -->
            <div class="mb-8 flex flex-col md:flex-row md:items-end md:justify-between gap-4">
                <div>
                    <h1 class="text-3xl text-forge-black font-sans font-black tracking-tight mb-2 pb-2 border-b-2 border-border-weld uppercase">
                        SEO Settings
                    </h1>
                    <p class="text-forge-dark font-serif text-sm">
                        Configure site-wide search appearance, social sharing defaults, and crawler indexing.
                        <span class="text-forge-mid font-sans text-xs ml-1">Site: <span class="font-mono font-bold text-rust" x-text="$store.app.activeSiteId"></span></span>
                    </p>
                </div>
                <div class="flex-shrink-0">
                    <button @click="save()" class="pen-btn-primary flex items-center gap-2" :disabled="saving || loading">
                        <svg x-show="saving" class="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                        <span x-text="saving ? 'Saving...' : 'Save SEO Settings'"></span>
                    </button>
                </div>
            </div>

            <div x-show="message"
                 x-cloak
                 x-transition
                 class="mb-6 p-4 border font-sans font-bold text-xs uppercase tracking-wider shadow-sm"
                 :class="messageType === 'success' ? 'bg-acid-wash border-acid text-acid-text' : 'bg-danger-bg border-danger text-danger'">
                <span x-text="message"></span>
            </div>

            <!-- Workspace Tabs -->
            <div class="flex border-b border-border mb-8 gap-1">
                <button @click="activeTab = 'meta'"
                        class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                        :class="activeTab === 'meta' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                    Site Meta
                </button>
                <button @click="activeTab = 'social'"
                        class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                        :class="activeTab === 'social' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                    Social Previews
                </button>
                <button @click="activeTab = 'indexing'"
                        class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                        :class="activeTab === 'indexing' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                    Indexing
                </button>
            </div>

            <!-- Tab: Site Meta -->
            <div x-show="activeTab === 'meta'" class="space-y-8 max-w-4xl">
                <p class="text-xs text-forge-dark font-serif leading-relaxed -mt-2">
                    Defaults for how this site appears in search results: identity fields, title pattern, meta description, and keywords.
                </p>

                <div x-show="loading" class="py-12 text-center text-xs font-sans font-bold uppercase tracking-wider text-forge-mid">
                    Loading…
                </div>

                <div class="space-y-8" x-show="!loading">
                    <!-- Site Identity -->
                    <div class="pen-card p-6 space-y-5 bg-card">
                        <div class="flex items-center gap-2 border-b border-border pb-2">
                            <svg class="w-4 h-4 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                            </svg>
                            <h3 class="text-xs font-black uppercase tracking-wider text-forge-black">Site Identity</h3>
                        </div>
                        <p class="text-[10px] text-forge-mid font-serif leading-prose">
                            Also editable under Settings → Site and Settings → Sites. Changes sync across all three.
                        </p>

                        <div class="flex flex-col gap-0.5">
                            <label class="pen-label !mb-0">Public Sitename</label>
                            <input type="text"
                                   x-model="$store.app.sitename"
                                   :placeholder="registryName ? ('fallback: ' + registryName) : 'e.g. PenCMS Blog'"
                                   class="pen-input">
                            <p class="text-[10px] text-forge-mid mt-0.5">Public site title used in search results and the admin header while this site is active.</p>
                        </div>

                        <div class="flex flex-col gap-0.5">
                            <label class="pen-label !mb-0">Tagline</label>
                            <input type="text"
                                   x-model="tagline"
                                   placeholder="e.g. Markdown-first static site engine"
                                   class="pen-input">
                            <p class="text-[10px] text-forge-mid mt-0.5">Short subtitle used in headers and as a meta-description fallback.</p>
                        </div>

                        <div class="flex flex-col gap-0.5">
                            <label class="pen-label !mb-0">Index Hero Title</label>
                            <input type="text"
                                   x-model="hero_title"
                                   placeholder="e.g. How-To & Docs"
                                   class="pen-input">
                            <p class="text-[10px] text-forge-mid mt-0.5">Main heading displayed in the homepage/index banner.</p>
                        </div>
                    </div>

                    <!-- Search Appearance -->
                    <div class="pen-card p-6 space-y-5 bg-card">
                        <div class="flex items-center gap-2 border-b border-border pb-2">
                            <svg class="w-4 h-4 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                            <h3 class="text-xs font-black uppercase tracking-wider text-forge-black">Search Appearance</h3>
                        </div>
                        <p class="text-[10px] text-forge-mid font-serif leading-prose">
                            Site-wide defaults when a post or page does not set its own SEO fields.
                        </p>

                        <div class="flex flex-col gap-0.5">
                            <label class="pen-label !mb-0">Title template</label>
                            <input type="text"
                                   x-model="title_template"
                                   placeholder="%page% | %site%"
                                   class="pen-input font-mono"
                                   spellcheck="false">
                            <p class="text-[10px] text-forge-mid mt-0.5">How page titles compose with the site name. Placeholders: <span class="font-mono">%page%</span>, <span class="font-mono">%site%</span>.</p>
                        </div>

                        <div class="flex flex-col gap-0.5">
                            <label class="pen-label !mb-0">Default meta description</label>
                            <textarea x-model="meta_description"
                                      rows="3"
                                      maxlength="320"
                                      placeholder="A concise summary of what this site is about…"
                                      class="pen-input resize-y min-h-[4.5rem]"></textarea>
                            <div class="flex items-start justify-between gap-4 mt-0.5">
                                <p class="text-[10px] text-forge-mid">
                                    Fallback when a post/page has no description. Aim for about 150–160 characters.
                                </p>
                                <span class="text-[10px] font-mono text-forge-mid/80 shrink-0 tabular-nums" x-text="(meta_description || '').length + ' chars'"></span>
                            </div>
                        </div>

                        <div class="flex flex-col gap-0.5">
                            <label class="pen-label !mb-0">Keywords <span class="font-normal normal-case tracking-normal text-forge-mid">(optional / legacy)</span></label>
                            <input type="text"
                                   x-model="keywords"
                                   placeholder="e.g. docs, markdown, publishing"
                                   class="pen-input">
                            <p class="text-[10px] text-forge-mid mt-0.5">Comma-separated. Not used by Google for ranking; kept for completeness and other consumers.</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Tab: Social Previews -->
            <div x-show="activeTab === 'social'" class="space-y-8 max-w-7xl" x-cloak>
                <p class="text-xs text-forge-dark font-serif leading-relaxed -mt-2">
                    Defaults for how links look when shared (Open Graph / Twitter). Unset fields inherit the active theme’s Social presets — zero visits here still works.
                </p>

                <div x-show="loading" class="py-12 text-center text-xs font-sans font-bold uppercase tracking-wider text-forge-mid">
                    Loading…
                </div>

                <div class="space-y-8" x-show="!loading">
                    <!-- Share defaults -->
                    <div class="pen-card p-6 space-y-5 bg-card">
                        <div class="flex items-center gap-2 border-b border-border pb-2">
                            <svg class="w-4 h-4 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                            </svg>
                            <h3 class="text-xs font-black uppercase tracking-wider text-forge-black">Share defaults</h3>
                        </div>
                        <p class="text-[10px] text-forge-mid font-serif leading-prose">
                            Site-wide meta fallbacks when a page has no OG title, description, or image. Theme supplies defaults until you override.
                        </p>

                        <div class="flex flex-col gap-0.5">
                            <label class="pen-label !mb-0">Twitter card type</label>
                            <select x-model="twitter_card" class="pen-input">
                                <option value="" x-text="'Theme default (' + (themeDefault('twitter_card') || 'summary_large_image') + ')'"></option>
                                <option value="summary_large_image">summary_large_image</option>
                                <option value="summary">summary</option>
                            </select>
                            <p class="text-[10px] text-forge-mid mt-0.5" x-text="sourceTip('twitter_card')"></p>
                        </div>

                        <div class="flex flex-col gap-0.5">
                            <label class="pen-label !mb-0">OG title fallback</label>
                            <input type="text"
                                   x-model="og_title_fallback"
                                   :placeholder="themeDefault('og_title_fallback') || 'Use page / site title'"
                                   class="pen-input">
                            <p class="text-[10px] text-forge-mid mt-0.5" x-text="sourceTip('og_title_fallback')"></p>
                        </div>

                        <div class="flex flex-col gap-0.5">
                            <label class="pen-label !mb-0">OG description fallback</label>
                            <textarea x-model="og_description_fallback"
                                      rows="3"
                                      maxlength="320"
                                      :placeholder="themeDefault('og_description_fallback') || 'Use site meta description'"
                                      class="pen-input resize-y min-h-[4.5rem]"></textarea>
                            <p class="text-[10px] text-forge-mid mt-0.5" x-text="sourceTip('og_description_fallback')"></p>
                        </div>

                        <div class="flex flex-col gap-0.5" x-data="{ dragging: false }">
                            <label class="pen-label !mb-0">Default share image</label>
                            <div class="relative group w-full min-h-[120px] border-2 border-dashed bg-canvas flex flex-col items-center justify-center p-4 transition-all duration-200 cursor-pointer select-none"
                                 :class="dragging ? 'border-rust bg-rust-wash' : 'border-border hover:border-rust hover:bg-rust-wash/50'"
                                 @dragover.prevent="dragging = true"
                                 @dragleave.prevent="dragging = false"
                                 @drop.prevent="dragging = false; handleSocialImageDrop($event, 'og_default_image')"
                                 @click="$refs.ogDefaultInput.click()">
                                <button type="button"
                                        x-show="previewUrl('og_default_image')"
                                        @click.stop="clearSocialImage('og_default_image')"
                                        class="absolute top-2 right-2 z-10 px-2 py-1 text-[10px] font-bold uppercase tracking-wider bg-card border border-border text-forge-mid hover:text-rust hover:border-rust">
                                    Clear
                                </button>
                                <template x-if="previewUrl('og_default_image')">
                                    <img :src="previewUrl('og_default_image')" alt="Default share preview" class="max-h-24 object-contain">
                                </template>
                                <template x-if="!previewUrl('og_default_image')">
                                    <div class="text-center flex flex-col items-center gap-2">
                                        <span class="block text-forge-mid text-[10px] uppercase font-bold tracking-wider">Drag share image here</span>
                                        <span class="text-[8px] text-forge-mid/70">1200×630 recommended · or click to browse</span>
                                    </div>
                                </template>
                            </div>
                            <input type="file" x-ref="ogDefaultInput" class="hidden" accept="image/png,image/jpeg,image/webp,image/gif" @change="handleSocialImageSelect($event, 'og_default_image')">
                            <p class="text-[10px] text-forge-mid mt-0.5">Classic site-wide <span class="font-mono">og:image</span> when no per-page or generated slug image applies. <span x-text="sourceTip('og_default_image')"></span></p>
                        </div>
                    </div>

                    <!-- Generated image look -->
                    <div class="pen-card p-6 space-y-5 bg-card">
                        <div class="flex items-center gap-2 border-b border-border pb-2">
                            <svg class="w-4 h-4 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                            <h3 class="text-xs font-black uppercase tracking-wider text-forge-black">Generated image look</h3>
                        </div>
                        <p class="text-[10px] text-forge-mid font-serif leading-prose">
                            How <span class="font-mono">og-image-maker</span> styles per-slug share images. Leave blank to keep the theme preset.
                        </p>

                        <div class="lg:grid lg:grid-cols-2 lg:gap-8 lg:items-start">
                        <div class="space-y-5">
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div class="flex flex-col gap-0.5">
                                <label class="pen-label !mb-0">Accent color</label>
                                <div class="flex gap-2 items-center">
                                    <input type="color" :value="colorInputValue('og_accent_color')" @input="og_accent_color = $event.target.value" class="h-9 w-12 p-0.5 border border-border bg-card cursor-pointer">
                                    <input type="text" x-model="og_accent_color" :placeholder="themeDefault('og_accent_color')" class="pen-input font-mono text-xs flex-1" spellcheck="false">
                                </div>
                                <p class="text-[10px] text-forge-mid mt-0.5" x-text="sourceTip('og_accent_color')"></p>
                            </div>
                            <div class="flex flex-col gap-0.5">
                                <label class="pen-label !mb-0">Vignette color</label>
                                <div class="flex gap-2 items-center">
                                    <input type="color" :value="colorInputValue('og_vignette_color')" @input="og_vignette_color = $event.target.value" class="h-9 w-12 p-0.5 border border-border bg-card cursor-pointer">
                                    <input type="text" x-model="og_vignette_color" :placeholder="themeDefault('og_vignette_color')" class="pen-input font-mono text-xs flex-1" spellcheck="false">
                                </div>
                                <p class="text-[10px] text-forge-mid mt-0.5" x-text="sourceTip('og_vignette_color')"></p>
                                <p class="text-[10px] text-forge-mid">Vignette tint applies to noir, clean, warm, and dusk only.</p>
                            </div>
                            <div class="flex flex-col gap-0.5">
                                <label class="pen-label !mb-0">Headline text color</label>
                                <div class="flex gap-2 items-center">
                                    <input type="color" :value="colorInputValue('og_text_color')" @input="og_text_color = $event.target.value" class="h-9 w-12 p-0.5 border border-border bg-card cursor-pointer">
                                    <input type="text" x-model="og_text_color" :placeholder="themeDefault('og_text_color')" class="pen-input font-mono text-xs flex-1" spellcheck="false">
                                </div>
                            </div>
                            <div class="flex flex-col gap-0.5">
                                <label class="pen-label !mb-0">Bar color</label>
                                <div class="flex gap-2 items-center">
                                    <input type="color" :value="colorInputValue('og_bar_color')" @input="og_bar_color = $event.target.value" class="h-9 w-12 p-0.5 border border-border bg-card cursor-pointer">
                                    <input type="text" x-model="og_bar_color" :placeholder="themeDefault('og_bar_color')" class="pen-input font-mono text-xs flex-1" spellcheck="false">
                                </div>
                            </div>
                        </div>

                        <div class="flex flex-col gap-0.5">
                            <label class="pen-label !mb-0">Font</label>
                            <select x-model="og_font" class="pen-input">
                                <option value="" x-text="'Theme default (' + (themeDefault('og_font') || '—') + ')'"></option>
                                <option disabled>── Theme ──</option>
                                <template x-for="f in themeFontCatalog()" :key="'t-' + f.id">
                                    <option :value="f.id" x-text="f.label"></option>
                                </template>
                                <option disabled>── Registry ──</option>
                                <template x-for="f in registryFontCatalog()" :key="'r-' + f.id">
                                    <option :value="f.id" x-text="f.label"></option>
                                </template>
                            </select>
                            <p class="text-[10px] text-forge-mid mt-0.5" x-text="sourceTip('og_font')"></p>
                        </div>

                        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                            <div class="flex flex-col gap-0.5">
                                <label class="pen-label !mb-0">Headline style</label>
                                <select x-model="og_headline_style" class="pen-input">
                                    <option value="">Theme default</option>
                                    <option value="redacted">Redacted</option>
                                    <option value="shadow">Shadow</option>
                                    <option value="plain">Plain</option>
                                    <option value="left">Left</option>
                                    <option value="left_redacted">Left redacted</option>
                                    <option value="center">Center</option>
                                    <option value="center_redacted">Center redacted</option>
                                    <option value="outline">Outline</option>
                                    <option value="banner">Banner</option>
                                    <option value="boxed">Boxed</option>
                                    <option value="underline">Underline</option>
                                    <option value="caption">Caption</option>
                                    <option value="poster">Poster</option>
                                </select>
                            </div>
                            <div class="flex flex-col gap-0.5">
                                <label class="pen-label !mb-0">Text casing</label>
                                <select x-model="og_text_case" class="pen-input">
                                    <option value="">Theme default</option>
                                    <option value="upper">UPPERCASE</option>
                                    <option value="title">Title Case</option>
                                    <option value="as_is">As-is</option>
                                </select>
                            </div>
                            <div class="flex flex-col gap-0.5">
                                <label class="pen-label !mb-0">Color grade</label>
                                <select x-model="og_grade_preset" class="pen-input">
                                    <option value="">Theme default</option>
                                    <option value="noir">Noir</option>
                                    <option value="clean">Clean</option>
                                    <option value="none">None</option>
                                    <option value="vibrant">Vibrant</option>
                                    <option value="warm">Warm</option>
                                    <option value="cool">Cool</option>
                                    <option value="fade">Fade</option>
                                    <option value="high_contrast">High contrast</option>
                                    <option value="sepia">Sepia</option>
                                    <option value="mono">Mono</option>
                                    <option value="dusk">Dusk</option>
                                    <option value="night">Night</option>
                                    <option value="paper">Paper</option>
                                </select>
                            </div>
                        </div>

                        <div class="flex flex-col gap-0.5">
                            <label class="pen-label !mb-0">Accent bar</label>
                            <select x-model="og_accent_bar" class="pen-input">
                                <option value="">Theme default</option>
                                <option value="true">On</option>
                                <option value="false">Off</option>
                            </select>
                            <p class="text-[10px] text-forge-mid mt-0.5">Slanted accent strip along the bottom of generated images.</p>
                        </div>

                        <div class="flex flex-col gap-0.5">
                            <label class="pen-label !mb-0">Fallback title text</label>
                            <input type="text"
                                   x-model="og_fallback_title"
                                   :placeholder="themeDefault('og_fallback_title') || 'ARCHIVAL RECORD'"
                                   class="pen-input">
                            <p class="text-[10px] text-forge-mid mt-0.5">Used by the image generator when a page has no title. <span x-text="sourceTip('og_fallback_title')"></span></p>
                        </div>
                        </div>

                        <div class="lg:sticky lg:top-4 self-start space-y-3 max-w-xl mt-5 lg:mt-0 border-t border-border pt-4 lg:border-t-0 lg:pt-0">
                            <label class="pen-label !mb-0">Generate preview</label>
                            <div class="flex flex-col gap-0.5">
                                <label class="pen-label !mb-0 font-normal normal-case tracking-normal text-forge-mid">Sample title</label>
                                <input type="text"
                                       x-model="ogPreviewTitle"
                                       @blur="onOgPreviewTitleBlur()"
                                       :placeholder="(og_fallback_title || themeDefault('og_fallback_title') || 'ARCHIVAL RECORD')"
                                       class="pen-input">
                            </div>
                            <label class="flex items-center gap-2 text-xs text-forge-dark cursor-pointer select-none"
                                   :class="hero_image ? '' : 'opacity-60'">
                                <input type="checkbox"
                                       x-model="ogPreviewUseSiteHero"
                                       :disabled="!hero_image"
                                       class="rounded border-border text-rust focus:ring-rust w-3.5 h-3.5">
                                Use site hero when present
                            </label>
                            <button type="button"
                                    @click="generateOgPreview({ toast: true })"
                                    class="pen-btn-secondary text-xs uppercase tracking-wider font-bold"
                                    :disabled="saving">
                                <span x-text="ogPreviewing ? 'Generating…' : 'Generate preview'"></span>
                            </button>
                            <template x-if="ogPreviewObjectUrl">
                                <img :src="ogPreviewObjectUrl"
                                     alt="Generated Open Graph preview"
                                     width="1200"
                                     height="630"
                                     class="w-full max-w-xl border border-border bg-canvas object-contain">
                            </template>
                            <p class="text-[10px] text-forge-mid">Uses the current form, including unsaved fallback hero / watermark. Save to persist.</p>
                        </div>
                        </div>
                    </div>

                    <!-- Generator assets -->
                    <div class="pen-card p-6 space-y-5 bg-card">
                        <div class="flex items-center gap-2 border-b border-border pb-2">
                            <svg class="w-4 h-4 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                            </svg>
                            <h3 class="text-xs font-black uppercase tracking-wider text-forge-black">Generator assets</h3>
                        </div>
                        <p class="text-[10px] text-forge-mid font-serif leading-prose">
                            Distinct from the share image above: these feed the OG image maker when a post lacks a hero, plus the full-canvas watermark overlay.
                        </p>

                        <div class="flex flex-col gap-0.5" x-data="{ dragging: false }">
                            <label class="pen-label !mb-0">Generator fallback hero</label>
                            <div class="relative group w-full min-h-[120px] border-2 border-dashed bg-canvas flex flex-col items-center justify-center p-4 transition-all duration-200 cursor-pointer select-none"
                                 :class="dragging ? 'border-rust bg-rust-wash' : 'border-border hover:border-rust hover:bg-rust-wash/50'"
                                 @dragover.prevent="dragging = true"
                                 @dragleave.prevent="dragging = false"
                                 @drop.prevent="dragging = false; handleSocialImageDrop($event, 'og_default_hero')"
                                 @click="$refs.ogHeroInput.click()">
                                <button type="button"
                                        x-show="previewUrl('og_default_hero')"
                                        @click.stop="clearSocialImage('og_default_hero')"
                                        class="absolute top-2 right-2 z-10 px-2 py-1 text-[10px] font-bold uppercase tracking-wider bg-card border border-border text-forge-mid hover:text-rust hover:border-rust">
                                    Clear
                                </button>
                                <template x-if="previewUrl('og_default_hero')">
                                    <img :src="previewUrl('og_default_hero')" alt="Default hero preview" class="max-h-24 object-contain">
                                </template>
                                <template x-if="!previewUrl('og_default_hero')">
                                    <div class="text-center flex flex-col items-center gap-2">
                                        <span class="block text-forge-mid text-[10px] uppercase font-bold tracking-wider">Drag fallback hero here</span>
                                        <span class="text-[8px] text-forge-mid/70">or click to browse</span>
                                    </div>
                                </template>
                            </div>
                            <input type="file" x-ref="ogHeroInput" class="hidden" accept="image/*" @change="handleSocialImageSelect($event, 'og_default_hero')">
                            <p class="text-[10px] text-forge-mid mt-0.5" x-text="sourceTip('og_default_hero')"></p>
                        </div>

                        <div class="flex flex-col gap-0.5">
                            <label class="pen-label !mb-0">Include watermark</label>
                            <select x-model="og_watermark_enabled" class="pen-input">
                                <option value="">Theme default</option>
                                <option value="true">On</option>
                                <option value="false">Off</option>
                            </select>
                            <p class="text-[10px] text-forge-mid mt-0.5">Composite the watermark PNG on generated images.</p>
                        </div>

                        <div class="flex flex-col gap-0.5">
                            <label class="pen-label !mb-0">Watermark source</label>
                            <select x-model="og_watermark_source" class="pen-input">
                                <option value="">Theme default</option>
                                <option value="logo">Site logo</option>
                                <option value="custom">Custom file</option>
                            </select>
                            <p class="text-[10px] text-forge-mid mt-0.5">Site logo is referenced at generate time — not copied. <span x-text="sourceTip('og_watermark_source')"></span></p>
                        </div>

                        <div class="flex flex-col gap-0.5" x-show="og_watermark_source !== 'logo'">
                            <label class="pen-label !mb-0">Placement</label>
                            <select x-model="og_watermark_layout" class="pen-input">
                                <option value="" x-text="'Theme default (' + (themeDefault('og_watermark_layout') || 'full_canvas') + ')'"></option>
                                <option value="full_canvas">Full canvas</option>
                                <option value="corner">Corner</option>
                            </select>
                            <p class="text-[10px] text-forge-mid mt-0.5">Full-canvas overlays stay 1200×630. Corner fits a small logo. <span x-text="sourceTip('og_watermark_layout')"></span></p>
                        </div>
                        <p class="text-[10px] text-forge-mid" x-show="og_watermark_source === 'logo'">Site logo always uses corner placement.</p>

                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4" x-show="watermarkUsesCorner()">
                            <div class="flex flex-col gap-0.5">
                                <label class="pen-label !mb-0">Corner</label>
                                <select x-model="og_watermark_corner" class="pen-input">
                                    <option value="" x-text="'Theme default (' + (themeDefault('og_watermark_corner') || 'br') + ')'"></option>
                                    <option value="tl">Top left</option>
                                    <option value="tr">Top right</option>
                                    <option value="bl">Bottom left</option>
                                    <option value="br">Bottom right</option>
                                </select>
                            </div>
                            <div class="flex flex-col gap-0.5">
                                <label class="pen-label !mb-0">Size</label>
                                <select x-model="og_watermark_scale" class="pen-input">
                                    <option value="" x-text="'Theme default (' + (themeDefault('og_watermark_scale') || 'md') + ')'"></option>
                                    <option value="sm">Small</option>
                                    <option value="md">Medium</option>
                                    <option value="lg">Large</option>
                                </select>
                            </div>
                        </div>

                        <div class="flex flex-col gap-0.5" x-show="og_watermark_source === 'logo'">
                            <template x-if="hasRasterSiteLogo()">
                                <img :src="logoBrandingUrl" alt="Site logo" class="max-h-16 object-contain bg-[repeating-conic-gradient(#ccc_0_25%,#fff_0_50%)] bg-[length:16px_16px] border border-border p-2">
                            </template>
                            <p class="text-[10px] text-forge-mid" x-show="hasSvgOnlySiteLogo()">OG watermark needs a PNG or WebP logo — SVG is skipped.</p>
                            <p class="text-[10px] text-forge-mid" x-show="!hasRasterSiteLogo() && !hasSvgOnlySiteLogo()">No raster site logo yet. Upload a PNG or WebP under Settings → Site.</p>
                        </div>

                        <div class="flex flex-col gap-0.5" x-show="og_watermark_source === 'custom'" x-data="{ dragging: false }">
                            <label class="pen-label !mb-0">Watermark overlay</label>
                            <div class="relative group w-full min-h-[120px] border-2 border-dashed bg-canvas flex flex-col items-center justify-center p-4 transition-all duration-200 cursor-pointer select-none"
                                 :class="dragging ? 'border-rust bg-rust-wash' : 'border-border hover:border-rust hover:bg-rust-wash/50'"
                                 @dragover.prevent="dragging = true"
                                 @dragleave.prevent="dragging = false"
                                 @drop.prevent="dragging = false; handleSocialImageDrop($event, 'og_watermark')"
                                 @click="$refs.ogWatermarkInput.click()">
                                <button type="button"
                                        x-show="previewUrl('og_watermark')"
                                        @click.stop="clearSocialImage('og_watermark')"
                                        class="absolute top-2 right-2 z-10 px-2 py-1 text-[10px] font-bold uppercase tracking-wider bg-card border border-border text-forge-mid hover:text-rust hover:border-rust">
                                    Clear
                                </button>
                                <template x-if="previewUrl('og_watermark')">
                                    <img :src="previewUrl('og_watermark')" alt="Watermark preview" class="max-h-24 object-contain bg-[repeating-conic-gradient(#ccc_0_25%,#fff_0_50%)] bg-[length:16px_16px]">
                                </template>
                                <template x-if="!previewUrl('og_watermark')">
                                    <div class="text-center flex flex-col items-center gap-2">
                                        <span class="block text-forge-mid text-[10px] uppercase font-bold tracking-wider">Drag watermark PNG here</span>
                                        <span class="text-[8px] text-forge-mid/70">PNG or WebP · full-canvas 1200×630 or a small logo</span>
                                    </div>
                                </template>
                            </div>
                            <input type="file" x-ref="ogWatermarkInput" class="hidden" accept="image/png,image/webp" @change="handleSocialImageSelect($event, 'og_watermark')">
                            <p class="text-[10px] text-forge-mid mt-0.5" x-text="sourceTip('og_watermark')"></p>
                        </div>

                        <div class="border-t border-border pt-4">
                            <button type="button"
                                    @click="resetSocialToTheme()"
                                    class="pen-btn-secondary text-xs uppercase tracking-wider font-bold"
                                    :disabled="saving">
                                Reset to theme defaults
                            </button>
                            <p class="text-[10px] text-forge-mid mt-1.5">Clears all Social overrides for this site. Theme presets apply again on next save.</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Tab: Indexing -->
            <div x-show="activeTab === 'indexing'" class="space-y-8 max-w-4xl" x-cloak>
                <p class="text-xs text-forge-dark font-serif leading-relaxed -mt-2">
                    Controls for how search engines crawl and index the site: robots defaults, sitemap discovery, ownership verification, IndexNow, AI-training signal, and static redirects.
                </p>

                <div x-show="loading" class="py-12 text-center text-xs font-sans font-bold uppercase tracking-wider text-forge-mid">
                    Loading…
                </div>

                <div class="space-y-8" x-show="!loading">
                    <!-- Robots -->
                    <div class="pen-card p-6 space-y-5 bg-card">
                        <div class="flex items-center gap-2 border-b border-border pb-2">
                            <svg class="w-4 h-4 text-rust" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" fill="none" aria-hidden="true">
                                <circle cx="88" cy="104" r="16" fill="currentColor"/>
                                <circle cx="168" cy="104" r="16" fill="currentColor"/>
                                <rect x="32" y="56" width="192" height="160" rx="24" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                                <line x1="128" y1="56" x2="128" y2="16" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                                <rect x="68" y="144" width="120" height="36" rx="18" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                                <line x1="148" y1="144" x2="148" y2="180" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                                <line x1="108" y1="144" x2="108" y2="180" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/>
                            </svg>
                            <h3 class="text-xs font-black uppercase tracking-wider text-forge-black">Robots</h3>
                        </div>
                        <p class="text-[10px] text-forge-mid font-serif leading-prose">
                            Site-wide defaults for crawlers. Per-post overrides stay in the editor when needed.
                        </p>

                        <div class="flex items-center gap-3">
                            <button type="button"
                                    @click="robots_index = !robots_index"
                                    class="pen-toggle"
                                    :class="robots_index ? 'active' : ''"
                                    role="switch"
                                    :aria-checked="robots_index"
                                    id="robots_index_toggle">
                                <span class="pen-toggle-knob"></span>
                            </button>
                            <div class="flex flex-col gap-0.5">
                                <label @click="robots_index = !robots_index" class="font-sans font-bold text-xs uppercase tracking-wider text-forge-black cursor-pointer select-none">
                                    Allow indexing
                                </label>
                                <span class="text-[10px] text-forge-mid leading-relaxed">When off, pages emit <span class="font-mono">noindex</span> and generated robots.txt disallows crawling.</span>
                            </div>
                        </div>

                        <div class="flex items-center gap-3">
                            <button type="button"
                                    @click="robots_follow = !robots_follow"
                                    class="pen-toggle"
                                    :class="robots_follow ? 'active' : ''"
                                    role="switch"
                                    :aria-checked="robots_follow"
                                    id="robots_follow_toggle">
                                <span class="pen-toggle-knob"></span>
                            </button>
                            <div class="flex flex-col gap-0.5">
                                <label @click="robots_follow = !robots_follow" class="font-sans font-bold text-xs uppercase tracking-wider text-forge-black cursor-pointer select-none">
                                    Allow following links
                                </label>
                                <span class="text-[10px] text-forge-mid leading-relaxed">Controls the <span class="font-mono">follow</span> / <span class="font-mono">nofollow</span> meta robots directive.</span>
                            </div>
                        </div>

                        <div class="flex flex-col gap-0.5">
                            <label class="pen-label !mb-0">Custom robots.txt <span class="font-normal normal-case tracking-normal text-forge-mid">(optional)</span></label>
                            <textarea x-model="robots_txt"
                                      rows="6"
                                      placeholder="Leave empty to auto-generate from the toggles above…"
                                      class="pen-input resize-y min-h-[7rem] font-mono text-xs"
                                      spellcheck="false"></textarea>
                            <p class="text-[10px] text-forge-mid mt-0.5">Empty body generates a sensible default from indexing + sitemap settings. Clear the field to restore auto-generation.</p>
                        </div>
                    </div>

                    <!-- Sitemap -->
                    <div class="pen-card p-6 space-y-5 bg-card">
                        <div class="flex items-center gap-2 border-b border-border pb-2">
                            <svg class="w-4 h-4 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                            </svg>
                            <h3 class="text-xs font-black uppercase tracking-wider text-forge-black">Sitemap</h3>
                        </div>
                        <p class="text-[10px] text-forge-mid font-serif leading-prose">
                            Lists live-published post and page URLs at <span class="font-mono">/sitemap.xml</span>. When off, that URL returns 404 and robots.txt omits the Sitemap line.
                        </p>

                        <div class="flex items-center gap-3">
                            <button type="button"
                                    @click="sitemap_enabled = !sitemap_enabled"
                                    class="pen-toggle"
                                    :class="sitemap_enabled ? 'active' : ''"
                                    role="switch"
                                    :aria-checked="sitemap_enabled"
                                    id="sitemap_enabled_toggle">
                                <span class="pen-toggle-knob"></span>
                            </button>
                            <div class="flex flex-col gap-0.5">
                                <label @click="sitemap_enabled = !sitemap_enabled" class="font-sans font-bold text-xs uppercase tracking-wider text-forge-black cursor-pointer select-none">
                                    Include sitemap in robots.txt
                                </label>
                                <span class="text-[10px] text-forge-mid leading-relaxed">When on, <span class="font-mono">/sitemap.xml</span> is public and robots.txt advertises it.</span>
                            </div>
                        </div>

                        <div class="flex flex-col gap-0.5">
                            <label class="pen-label !mb-0">Public sitemap URL</label>
                            <input type="text"
                                   :value="sitemapPublicUrl()"
                                   readonly
                                   class="pen-input font-mono text-xs bg-canvas/60 text-forge-dark cursor-default"
                                   tabindex="-1">
                            <p class="text-[10px] text-forge-mid mt-0.5">Fixed path <span class="font-mono">/sitemap.xml</span>. Static builds emit this file into dist when the toggle is on.</p>
                        </div>
                    </div>

                    <!-- Ownership verification -->
                    <div class="pen-card p-6 space-y-5 bg-card">
                        <div class="flex items-center gap-2 border-b border-border pb-2">
                            <svg class="w-4 h-4 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                            </svg>
                            <h3 class="text-xs font-black uppercase tracking-wider text-forge-black">Ownership verification</h3>
                        </div>
                        <p class="text-[10px] text-forge-mid font-serif leading-prose">
                            Paste the meta tag <span class="font-mono">content</span> value from Search Console or Bing Webmaster. Emitted in the public site head when set.
                        </p>

                        <div class="flex flex-col gap-0.5">
                            <label class="pen-label !mb-0">Google site verification</label>
                            <input type="text"
                                   x-model="google_site_verification"
                                   placeholder="e.g. AbCdEf123…"
                                   class="pen-input font-mono text-xs"
                                   spellcheck="false"
                                   autocomplete="off">
                            <p class="text-[10px] text-forge-mid mt-0.5">Becomes <span class="font-mono">&lt;meta name="google-site-verification"&gt;</span>. Leave empty to remove.</p>
                        </div>

                        <div class="flex flex-col gap-0.5">
                            <label class="pen-label !mb-0">Bing site verification</label>
                            <input type="text"
                                   x-model="bing_site_verification"
                                   placeholder="e.g. 1234567890ABCDEF…"
                                   class="pen-input font-mono text-xs"
                                   spellcheck="false"
                                   autocomplete="off">
                            <p class="text-[10px] text-forge-mid mt-0.5">Becomes <span class="font-mono">&lt;meta name="msvalidate.01"&gt;</span>. Leave empty to remove.</p>
                        </div>
                    </div>

                    <!-- IndexNow -->
                    <div class="pen-card p-6 space-y-5 bg-card">
                        <div class="flex items-center gap-2 border-b border-border pb-2">
                            <svg class="w-4 h-4 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                            </svg>
                            <h3 class="text-xs font-black uppercase tracking-wider text-forge-black">IndexNow</h3>
                        </div>
                        <p class="text-[10px] text-forge-mid font-serif leading-prose">
                            After a successful public HTTPS publish, notify Bing, Yandex, Seznam, and Naver of URL changes.
                            This does <span class="font-bold">not</span> update Google. Localhost and private hosts are skipped. A ping failure never blocks publish.
                        </p>

                        <div class="flex items-center gap-3">
                            <button type="button"
                                    @click="indexnow_enabled = !indexnow_enabled"
                                    class="pen-toggle"
                                    :class="indexnow_enabled ? 'active' : ''"
                                    role="switch"
                                    :aria-checked="indexnow_enabled"
                                    id="indexnow_enabled_toggle">
                                <span class="pen-toggle-knob"></span>
                            </button>
                            <div class="flex flex-col gap-0.5">
                                <label @click="indexnow_enabled = !indexnow_enabled" class="font-sans font-bold text-xs uppercase tracking-wider text-forge-black cursor-pointer select-none">
                                    Ping IndexNow after publish
                                </label>
                                <span class="text-[10px] text-forge-mid leading-relaxed">Writes <span class="font-mono">dist/&lt;key&gt;.txt</span> on build. Requires a public <span class="font-mono">https</span> site URL.</span>
                            </div>
                        </div>

                        <div class="flex flex-col gap-0.5" x-show="indexnow_enabled || indexnow_key">
                            <label class="pen-label !mb-0">Site key</label>
                            <div class="flex gap-2">
                                <input type="text"
                                       :value="indexnow_key"
                                       readonly
                                       class="pen-input font-mono text-xs bg-canvas/60 text-forge-dark cursor-default flex-1"
                                       tabindex="-1"
                                       placeholder="Saved on first enable…">
                                <button type="button"
                                        class="pen-btn-secondary text-xs uppercase tracking-wider font-bold shrink-0"
                                        @click="regenerateIndexNow = true; showNotification('Key will regenerate on Save.', 'success')">
                                    Regenerate
                                </button>
                            </div>
                            <p class="text-[10px] text-forge-mid mt-0.5" x-show="regenerateIndexNow">A new key will be minted when you save.</p>
                        </div>
                    </div>

                    <!-- Content-Signal -->
                    <div class="pen-card p-6 space-y-5 bg-card">
                        <div class="flex items-center gap-2 border-b border-border pb-2">
                            <svg class="w-4 h-4 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                            </svg>
                            <h3 class="text-xs font-black uppercase tracking-wider text-forge-black">AI training signal</h3>
                        </div>
                        <p class="text-[10px] text-forge-mid font-serif leading-prose">
                            Static <span class="font-mono">Content-Signal</span> on markdown and <span class="font-mono">llms*.txt</span>. Retrieval (<span class="font-mono">search</span>, <span class="font-mono">ai-input</span>) stays on. Training is opt-in.
                            Default robots.txt does not block GPTBot, ClaudeBot, or PerplexityBot.
                        </p>

                        <div class="flex items-center gap-3">
                            <button type="button"
                                    @click="content_signal_ai_train = !content_signal_ai_train"
                                    class="pen-toggle"
                                    :class="content_signal_ai_train ? 'active' : ''"
                                    role="switch"
                                    :aria-checked="content_signal_ai_train"
                                    id="content_signal_ai_train_toggle">
                                <span class="pen-toggle-knob"></span>
                            </button>
                            <div class="flex flex-col gap-0.5">
                                <label @click="content_signal_ai_train = !content_signal_ai_train" class="font-sans font-bold text-xs uppercase tracking-wider text-forge-black cursor-pointer select-none">
                                    Allow AI training
                                </label>
                                <span class="text-[10px] text-forge-mid leading-relaxed">When on, headers include <span class="font-mono">ai-train=yes</span>. When off, <span class="font-mono">ai-train=no</span>.</span>
                            </div>
                        </div>
                    </div>

                    <!-- Redirects -->
                    <div class="pen-card p-6 space-y-5 bg-card">
                        <div class="flex items-center gap-2 border-b border-border pb-2">
                            <svg class="w-4 h-4 text-rust" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                            </svg>
                            <h3 class="text-xs font-black uppercase tracking-wider text-forge-black">Static redirects</h3>
                        </div>
                        <p class="text-[10px] text-forge-mid font-serif leading-prose">
                            One same-site 301 per line as <span class="font-mono">/old-slug/ -&gt; /new-slug/</span>. Emitted into <span class="font-mono">.htaccess</span> and <span class="font-mono">_redirects</span> when the list is not empty.
                        </p>
                        <textarea x-model="seo_redirects_text"
                                  rows="5"
                                  placeholder="/old-post/ -> /new-post/"
                                  class="pen-input resize-y min-h-[6rem] font-mono text-xs"
                                  spellcheck="false"></textarea>
                        <p class="text-[10px] text-forge-mid mt-0.5">Paths must start with <span class="font-mono">/</span>. Absolute URLs are rejected.</p>
                    </div>
                </div>
            </div>
        </main>
    </div>

    <!-- Footer -->
    <?php include "includes/_admin-footer.php"; ?>
</body>
</html>
