<?php
$pageTitle = "Translations (PenCMS)";
$currentSection = "translations";
$pageScript = "translations.js";
include "includes/_admin-auth.php";
include "includes/_admin-head.php";
?>

<body class="bg-canvas text-forge-black font-sans antialiased h-screen flex flex-col overflow-hidden"
      x-data="translationsPage">

    <!-- Header / Top Navigation -->
    <?php include "includes/_admin-header.php"; ?>

    <div class="flex flex-1 relative min-h-0 overflow-hidden">
        <!-- Collapsible Left Sidebar -->
        <?php include "includes/_admin-sidebar.php"; ?>

        <!-- Main Workspace Canvas -->
        <main class="flex-1 overflow-y-auto p-8 md:p-12 transition-all duration-300">
            <div class="mb-8 flex flex-col md:flex-row md:items-end md:justify-between gap-4">
                <div>
                    <h1 class="text-3xl text-forge-black font-sans font-black tracking-tight mb-2 pb-2 border-b-2 border-border-weld uppercase">
                        Translations
                    </h1>
                    <p class="text-forge-dark font-serif text-sm">
                        Languages, coverage, and UI strings. 
                        <span class="text-forge-mid font-sans text-xs ml-1">Site: <span class="font-mono font-bold text-rust" x-text="$store.app.activeSiteId"></span></span>
                    </p>
                </div>
                <div class="flex gap-2">
                    <button x-show="activeTab === 'languages'" type="button"
                            @click="saveLanguages()" :disabled="saving || loading"
                            class="pen-btn pen-btn-primary">
                        <span x-text="saving ? 'Saving…' : 'Save languages'"></span>
                    </button>
                    <button x-show="activeTab === 'strings'" type="button"
                            @click="saveStrings()" :disabled="saving || loading || !config.i18n_active"
                            class="pen-btn pen-btn-primary">
                        <span x-text="saving ? 'Saving…' : 'Save UI strings'"></span>
                    </button>
                </div>
            </div>

            <div x-show="message" x-cloak x-transition
                 class="mb-6 p-4 border font-sans font-bold text-xs uppercase tracking-wider shadow-sm"
                 :class="messageType === 'success' ? 'bg-acid-wash border-acid text-acid-text' : 'bg-danger-bg border-danger text-danger'">
                <span x-text="message"></span>
            </div>

            <div x-show="loading" class="py-20 text-center">
                <div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-rust border-t-transparent"></div>
            </div>

            <div x-show="!loading" x-cloak>
            <div class="flex border-b border-border mb-8 gap-1">
                <button type="button"
                        @click="setTab('languages')"
                        class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                        :class="activeTab === 'languages' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                    Languages
                </button>
                <button type="button"
                        @click="setTab('coverage')"
                        class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                        :class="activeTab === 'coverage' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                    Coverage
                </button>
                <button type="button"
                        @click="setTab('strings')"
                        class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                        :class="activeTab === 'strings' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                    UI Strings
                </button>
            </div>

            <!-- Tab: Languages -->
            <div x-show="activeTab === 'languages'" class="space-y-8 max-w-4xl">
                <p class="text-xs text-forge-dark font-serif leading-relaxed -mt-2">
                    Configure exact content languages and labels. i18n stays off until two or more languages include the default.
                </p>

                <div class="pen-card p-6 bg-card flex items-center justify-between gap-4">
                    <div>
                        <p class="text-xs font-black uppercase tracking-wider"
                           :class="config.i18n_active ? 'text-status-live' : 'text-forge-mid'"
                           x-text="config.i18n_active ? 'Internationalization active' : 'Internationalization inactive'"></p>
                        <p class="text-[10px] text-forge-mid font-serif mt-1">
                            Default URLs remain unchanged. Missing language siblings never become public ghost pages.
                        </p>
                    </div>
                    <span class="font-mono text-xs px-3 py-1 border"
                          :class="config.i18n_active ? 'border-status-live bg-status-live-bg text-status-live' : 'border-border bg-canvas text-forge-mid'"
                          x-text="(config.languages || []).length + ' languages'"></span>
                </div>

                <div class="pen-card p-6 bg-card space-y-6">
                    <div>
                        <label class="pen-label">Default language</label>
                        <input type="text" x-model="defaultLanguage"
                               class="pen-input font-mono mt-1 max-w-xs"
                               autocomplete="off" spellcheck="false" placeholder="en">
                        <p class="text-[10px] text-forge-mid mt-1">Normalized BCP-47 code. Existing default-language URLs do not move.</p>
                    </div>

                    <div class="border-t border-border pt-5">
                        <div class="flex items-center justify-between mb-3">
                            <div>
                                <h2 class="text-xs font-black uppercase tracking-wider">Configured languages</h2>
                                <p class="text-[10px] text-forge-mid mt-1">Labels are optional; native names are shown when the browser supports them.</p>
                            </div>
                        </div>
                        <div class="space-y-2">
                            <template x-for="row in languageRows" :key="row.code">
                                <div class="grid grid-cols-[10rem_1fr_auto] gap-2 items-center">
                                    <input type="text" x-model="row.code" class="pen-input font-mono" spellcheck="false">
                                    <input type="text" x-model="row.label" class="pen-input"
                                           :placeholder="'Label override — ' + displayLanguage(row.code)">
                                    <button type="button" @click="removeLanguage(row.code)"
                                            class="pen-btn pen-btn-secondary pen-btn-sm text-danger">Remove</button>
                                </div>
                            </template>
                            <p x-show="!languageRows.length" class="text-xs text-forge-mid font-serif py-3">
                                No configured list. The site remains monolingual in <span class="font-mono" x-text="defaultLanguage"></span>.
                            </p>
                        </div>
                        <div class="flex gap-2 mt-4">
                            <input type="text" x-model="newLanguage" @keydown.enter.prevent="addLanguage()"
                                   class="pen-input font-mono max-w-xs" placeholder="Add code, e.g. fr">
                            <button type="button" @click="addLanguage()" class="pen-btn pen-btn-secondary">Add language</button>
                        </div>
                    </div>
                </div>

                <div class="pen-card p-6 bg-card flex flex-col md:flex-row md:items-center md:justify-between gap-5">
                    <div>
                        <h2 class="text-xs font-black uppercase tracking-wider">Agent automation</h2>
                        <p class="text-[10px] text-forge-mid font-serif mt-1 max-w-xl">
                            Pause blocks agent sibling writes and new automated run starts. Human creation, editing, review, and disk writes continue. AI is not required.
                        </p>
                    </div>
                    <button type="button"
                            @click="setAutomationPaused(!config.translation_automation_paused)"
                            :disabled="actionKey === 'pause'"
                            class="pen-btn"
                            :class="config.translation_automation_paused ? 'pen-btn-primary' : 'pen-btn-secondary'"
                            x-text="config.translation_automation_paused ? 'Resume agents' : 'Pause agents'"></button>
                </div>

                <div class="pen-card p-6 bg-card space-y-5">
                    <div class="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                        <div>
                            <h2 class="text-xs font-black uppercase tracking-wider">External localization policy</h2>
                            <p class="text-[10px] text-forge-mid font-serif mt-1 max-w-2xl">
                                Optional planning for cron or MCP agents. PenCMS validates the selected operation, non-secret model name, named site key, and review rule; the external caller owns model execution and scheduling.
                            </p>
                        </div>
                        <label class="flex items-center gap-2 text-[10px] uppercase font-black whitespace-nowrap">
                            <input type="checkbox" x-model="automationEnabled"
                                   :disabled="!config.i18n_active && languageRows.length < 2">
                            Enable policy
                        </label>
                    </div>

                    <div x-show="config.automation_policy && config.automation_policy.policy_valid === false"
                         class="p-3 border border-danger bg-danger-bg text-danger text-xs">
                        <span class="font-black">Stored policy needs repair:</span>
                        <span x-text="config.automation_policy.policy_error"></span>
                    </div>

                    <div x-show="automationEnabled" class="space-y-3">
                        <p x-show="!compatibleAgentKeys.length"
                           class="p-3 border border-warning bg-warning-bg text-xs text-forge-dark">
                            Create a named key with read + write scopes for this site under Settings → AI. Provider credentials remain outside this policy.
                        </p>
                        <template x-for="row in automationRows" :key="row.language">
                            <div class="border border-border p-4 space-y-3">
                                <div class="flex items-center justify-between gap-3">
                                    <div>
                                        <span class="font-mono text-xs font-black" x-text="row.language"></span>
                                        <span class="text-[10px] text-forge-mid ml-2" x-text="displayLanguage(row.language)"></span>
                                    </div>
                                    <label class="flex items-center gap-2 text-[9px] uppercase font-black">
                                        <input type="checkbox" x-model="row.enabled">
                                        Automate target
                                    </label>
                                </div>
                                <div x-show="row.enabled" class="grid md:grid-cols-2 gap-3">
                                    <div>
                                        <label class="pen-label">Ordered operation</label>
                                        <select x-model="row.operation" class="pen-input mt-1">
                                            <option value="translate">Translate</option>
                                            <option value="transliterate">Transliterate</option>
                                            <option value="translate_then_transliterate">Translate, then transliterate</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label class="pen-label">External model identifier</label>
                                        <input type="text" x-model="row.model" class="pen-input mt-1 font-mono"
                                               placeholder="provider/model">
                                    </div>
                                    <div>
                                        <label class="pen-label">Bound named key</label>
                                        <select x-model="row.agent_key_id" class="pen-input mt-1">
                                            <option value="">Select site key</option>
                                            <template x-for="key in compatibleAgentKeys" :key="key.key_id">
                                                <option :value="key.key_id"
                                                        x-text="key.name + ' · ' + key.key_id"></option>
                                            </template>
                                        </select>
                                    </div>
                                    <div>
                                        <label class="pen-label">Review policy</label>
                                        <select x-model="row.review_policy" class="pen-input mt-1">
                                            <option value="require_review">Draft · human review required</option>
                                            <option value="allow_unreviewed_draft">Draft · review flag optional</option>
                                        </select>
                                        <p class="text-[10px] text-forge-mid font-serif mt-1">Queue flag only. Go-live is Settings → AI Publishing autonomy, not this select.</p>
                                    </div>
                                </div>
                                <p x-show="row.enabled && row.binding_valid === false"
                                   class="text-[10px] text-danger font-bold"
                                   x-text="'Binding invalid: ' + (row.binding_error || 'unknown')"></p>
                            </div>
                        </template>
                    </div>

                    <p class="text-[10px] text-forge-mid font-serif">
                        Disabled policy and missing provider credentials never block manual sibling creation, editing, review, publishing, or direct Markdown work.
                    </p>
                </div>
            </div>

            <!-- Tab: Coverage -->
            <div x-show="activeTab === 'coverage'" class="space-y-8 max-w-4xl">
                <p class="text-xs text-forge-dark font-serif leading-relaxed -mt-2">
                    Gaps, recent agent/cron runs when enabled, human override, and entry points to edit or create siblings by hand.
                </p>

                <div x-show="!config.i18n_active" class="pen-card p-8 bg-card text-center">
                    <p class="text-sm font-black uppercase tracking-wider">Configure at least two languages first</p>
                    <p class="text-xs text-forge-mid font-serif mt-2">Coverage is exact and remains empty while i18n is inactive.</p>
                </div>

                <template x-if="config.i18n_active">
                    <div class="space-y-6">
                        <div class="pen-card p-5 bg-card flex flex-wrap items-end gap-3">
                            <div>
                                <label class="pen-label">Target language</label>
                                <select x-model="targetLanguage" @change="changeTargetLanguage()" class="pen-input mt-1">
                                    <template x-for="code in targetLanguages" :key="code">
                                        <option :value="code" x-text="displayLanguage(code) + ' (' + code + ')'"></option>
                                    </template>
                                </select>
                            </div>
                            <div class="flex-1 min-w-[12rem]">
                                <label class="pen-label">Find slug</label>
                                <input type="search" x-model="coverageSearch" class="pen-input mt-1" placeholder="Search exact source slug">
                            </div>
                            <div>
                                <label class="pen-label">State</label>
                                <select x-model="coverageState" class="pen-input mt-1">
                                    <option value="all">All</option>
                                    <option value="missing">Missing</option>
                                    <option value="draft">Draft</option>
                                    <option value="needs_review">Needs review</option>
                                    <option value="rejected">Rejected</option>
                                    <option value="published">Published</option>
                                    <option value="unpublished">Unpublished</option>
                                </select>
                            </div>
                            <button type="button" @click="forceRepublish()" :disabled="actionKey === 'publish'"
                                    class="pen-btn pen-btn-secondary">Force full publish</button>
                        </div>

                        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                            <template x-for="metric in [
                                ['Eligible', coverage.totals.eligible],
                                ['Published', coverage.totals.published],
                                ['Needs review', coverage.totals.needs_review],
                                ['Missing', coverage.totals.missing]
                            ]" :key="metric[0]">
                                <div class="pen-card p-4 bg-card">
                                    <p class="text-[9px] uppercase tracking-wider text-forge-mid font-bold" x-text="metric[0]"></p>
                                    <p class="text-2xl font-black font-mono mt-1" x-text="metric[1]"></p>
                                </div>
                            </template>
                        </div>

                        <div class="pen-card bg-card overflow-x-auto">
                            <table class="w-full text-left">
                                <thead class="bg-canvas border-b border-border">
                                    <tr class="text-[9px] uppercase tracking-wider text-forge-mid">
                                        <th class="px-4 py-3">Source</th>
                                        <th class="px-4 py-3">Target state</th>
                                        <th class="px-4 py-3 text-right">Manual / review</th>
                                    </tr>
                                </thead>
                                <tbody class="divide-y divide-border">
                                    <template x-for="row in filteredCoverageItems" :key="row.slug">
                                        <tr>
                                            <td class="px-4 py-3">
                                                <p class="font-mono text-xs font-bold" x-text="row.slug"></p>
                                                <p class="text-[9px] text-forge-mid uppercase mt-1"
                                                   x-text="row.collection + ' · ' + (row.source.status || 'draft')"></p>
                                            </td>
                                            <td class="px-4 py-3">
                                                <span class="text-[10px] font-black uppercase tracking-wider px-2 py-1 border"
                                                      :class="rowState(row) === 'published' ? 'border-status-live bg-status-live-bg text-status-live' : 'border-border bg-canvas text-forge-dark'"
                                                      x-text="rowState(row).replace('_', ' ')"></span>
                                            </td>
                                            <td class="px-4 py-3">
                                                <div class="flex flex-wrap justify-end gap-2">
                                                    <button type="button" @click="createOrOpenSibling(row)"
                                                            class="pen-btn pen-btn-secondary pen-btn-sm"
                                                            x-text="rowSibling(row) ? 'Open sibling' : 'Create sibling'"></button>
                                                    <button x-show="rowSibling(row) && ['stub','draft'].includes(rowSibling(row).status)"
                                                            type="button" @click="review(row, 'approve')"
                                                            class="pen-btn pen-btn-secondary pen-btn-sm">Approve</button>
                                                    <button x-show="rowSibling(row)" type="button" @click="review(row, 'reject')"
                                                            class="pen-btn pen-btn-secondary pen-btn-sm text-danger">Reject</button>
                                                </div>
                                            </td>
                                        </tr>
                                    </template>
                                    <tr x-show="!filteredCoverageItems.length">
                                        <td colspan="3" class="px-4 py-10 text-center text-xs text-forge-mid font-serif">No exact coverage rows match this filter.</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>

                        <div class="pen-card p-6 bg-card">
                            <h2 class="text-xs font-black uppercase tracking-wider mb-4">Recent external runs</h2>
                            <div class="space-y-2">
                                <template x-for="run in runs" :key="run.run_id">
                                    <div class="grid grid-cols-[1fr_auto_auto] gap-4 items-center border-b border-border/60 pb-2 text-xs">
                                        <div>
                                            <span class="font-mono font-bold" x-text="run.mode"></span>
                                            <span class="text-forge-mid" x-text="' · ' + (run.actor_id || run.actor)"></span>
                                        </div>
                                        <span class="uppercase text-[9px] font-black" x-text="run.status"></span>
                                        <span class="text-[10px] text-forge-mid" x-text="formatRunTime(run.started_at)"></span>
                                    </div>
                                </template>
                                <p x-show="!runs.length" class="text-xs text-forge-mid font-serif">No agent or cron runs reported. Manual translation remains fully available.</p>
                            </div>
                        </div>
                    </div>
                </template>
            </div>

            <!-- Tab: UI Strings -->
            <div x-show="activeTab === 'strings'" class="space-y-8 max-w-4xl">
                <p class="text-xs text-forge-dark font-serif leading-relaxed -mt-2">
                    Theme and site chrome strings (“Read more”, “Page not found”, and similar) with per-key fallback to the default language.
                </p>

                <div class="pen-card p-5 bg-card flex flex-wrap items-end justify-between gap-4">
                    <div>
                        <label class="pen-label">Exact language</label>
                        <select x-model="stringLanguage" @change="changeStringLanguage()" class="pen-input mt-1 min-w-[14rem]">
                            <template x-for="code in (config.languages.length ? config.languages : [config.language])" :key="code">
                                <option :value="code" x-text="displayLanguage(code) + ' (' + code + ')'"></option>
                            </template>
                        </select>
                    </div>
                    <p class="text-[10px] text-forge-mid font-serif max-w-lg">
                        Effective order: engine → theme → default-site → target-site. Uncheck Override to remove that key from the site JSON file.
                    </p>
                </div>

                <div x-show="!config.i18n_active" class="p-4 border border-warning bg-warning-bg text-xs text-forge-dark">
                    UI strings show engine defaults while i18n is inactive. Configure two languages before saving site overrides.
                </div>

                <div class="pen-card bg-card overflow-x-auto">
                    <table class="w-full text-left">
                        <thead class="bg-canvas border-b border-border">
                            <tr class="text-[9px] uppercase tracking-wider text-forge-mid">
                                <th class="px-4 py-3">Key / effective value</th>
                                <th class="px-4 py-3">Source</th>
                                <th class="px-4 py-3">Sparse site override</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-border">
                            <template x-for="row in stringRows" :key="row.key">
                                <tr>
                                    <td class="px-4 py-3 align-top">
                                        <code class="text-[10px] font-bold text-rust" x-text="row.key"></code>
                                        <p class="text-xs mt-1" x-text="row.effective"></p>
                                    </td>
                                    <td class="px-4 py-3 align-top">
                                        <span class="text-[9px] uppercase tracking-wider border border-border bg-canvas px-2 py-1"
                                              x-text="row.source.replace('_', ' ')"></span>
                                    </td>
                                    <td class="px-4 py-3">
                                        <div class="flex gap-2 items-center">
                                            <label class="flex items-center gap-2 text-[9px] uppercase font-bold whitespace-nowrap">
                                                <input type="checkbox" x-model="row.useOverride" :disabled="!config.i18n_active">
                                                Override
                                            </label>
                                            <input type="text" x-model="row.override"
                                                   :disabled="!config.i18n_active || !row.useOverride"
                                                   class="pen-input text-xs flex-1">
                                            <button type="button" @click="resetString(row)"
                                                    :disabled="!config.i18n_active || !row.useOverride"
                                                    class="pen-btn pen-btn-secondary pen-btn-sm">Reset</button>
                                        </div>
                                    </td>
                                </tr>
                            </template>
                        </tbody>
                    </table>
                </div>
            </div>
            </div>
        </main>
    </div>

    <!-- Footer -->
    <?php include "includes/_admin-footer.php"; ?>
