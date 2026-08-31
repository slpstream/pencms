<?php
$pageTitle = "Structure Settings (PenCMS)";
$currentSection = "settings";
include "includes/_admin-auth.php";
include "includes/_admin-head.php";
?>

<body class="bg-canvas text-forge-black font-sans antialiased h-screen flex flex-col overflow-hidden"
      x-data="settingsStructure">

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
                        System Structure & Taxonomy
                    </h1>
                    <p class="text-forge-dark font-serif text-sm">
                        Configure the directory architecture, taxonomy vocabularies, and mandatory metadata validation rules.
                        <span class="text-forge-mid font-sans text-xs ml-1">Site: <span class="font-mono font-bold text-rust" x-text="$store.app.activeSiteId"></span></span>
                    </p>
                </div>
                <div class="flex-shrink-0">
                    <button @click="save()" class="pen-btn-primary flex items-center gap-2" :disabled="saving">
                        <svg x-show="saving" class="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                        <span x-text="saving ? 'Saving...' : 'Save Structure'"></span>
                    </button>
                </div>
            </div>

            <!-- Alert Banners via Alpine -->
            <div x-show="message" x-cloak x-transition class="mb-8 p-4 flex items-center space-x-3 pen-card"
                 :class="isError ? 'bg-danger-bg border-danger text-danger' : 'bg-acid-wash border-l-4 border-acid-deep text-acid-text'">
                <span x-show="!isError" class="text-xl w-6 h-6 text-acid"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-6 h-6"><rect width="256" height="256" fill="none"/><polyline points="88 136 112 160 168 104" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/><rect x="40" y="40" width="176" height="176" rx="8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="16"/></svg></span>
                <span x-show="isError" x-text="'❌'" class="text-xl text-danger"></span>
                <span x-html="message" class="text-xs font-bold uppercase tracking-label"></span>
            </div>

            <!-- Loading Spinner -->
            <div x-show="loading" class="py-20 text-center flex flex-col items-center justify-center gap-3">
                <div class="w-10 h-10 border-4 border-rust border-t-transparent rounded-full animate-spin"></div>
                <p class="text-xs text-forge-mid font-mono uppercase tracking-wider">Loading Taxonomy Manifest...</p>
            </div>

            <!-- Workspace Tabs -->
            <template x-if="!loading">
                <div class="flex flex-col h-full">
                <!-- Navigation Subtabs -->
                <div class="flex border-b border-border mb-8 gap-1">
                    <button @click="activeTab = 'required'"
                            class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                            :class="activeTab === 'required' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                        Publishing Rules
                    </button>
                    <button @click="activeTab = 'vocabularies'"
                            class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                            :class="activeTab === 'vocabularies' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                        Vocabularies
                    </button>
                    <button @click="activeTab = 'general'"
                            class="px-5 py-2.5 font-sans font-bold text-xs uppercase tracking-wider border-t-2 transition-all duration-150"
                            :class="activeTab === 'general' ? 'border-rust bg-card text-rust font-black' : 'border-transparent text-forge-mid hover:text-primary hover:bg-black/[0.01]'">
                        Primary Category
                    </button>
                </div>

                <!-- Tab: Publishing Rules -->
                <div x-show="activeTab === 'required'" class="space-y-6 max-w-4xl">
                    <div class="pb-2 border-b border-border/40">
                        <h3 class="text-xl font-bold uppercase tracking-tight text-primary">Mandatory Publishing Fields</h3>
                        <p class="text-sm text-forge-dark font-serif mt-1">
                            Select the frontmatter metadata fields required before a document can be published. Drafts and stubs are automatically exempted.
                        </p>
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <template x-for="item in [
                            { key: 'name', title: 'Name', desc: 'The name of the post.' },
                            { key: 'status', title: 'Status', desc: 'The current publishing workflow status (e.g. Published, Draft).' },
                            { key: 'deck', title: 'Deck', desc: 'Editorial dek / teaser under the title on the public page.' },
                            { key: 'summary', title: 'Summary', desc: 'Expand/Embed nutshell body (source=summary). Distinct from deck.' },
                            { key: 'hero_image', title: 'Hero Image', desc: 'Relative path of the header image in the workspace.' },
                            { key: 'hero_title', title: 'Hero Title', desc: 'Dispay title for hero banner/header.' },
                            { key: 'trumpet', title: 'Trumpet / Eyebrow Callout', desc: 'Highlight sentence/callout line featured at page start.' },
                            { key: 'author', title: 'Author / Byline', desc: 'The author name or byline of the post.' },
                            { key: 'date', title: 'Publishing Date', desc: 'The ISO standard publication timestamp date.' }
                        ]" :key="item.key">
                            <div @click="toggleRequiredField(item.key)"
                                 class="pen-card p-5 cursor-pointer transition-all duration-200 flex items-start justify-between bg-card"
                                 :class="taxonomy.required_fields.includes(item.key) ? 'border-rust bg-rust-wash' : 'border-border hover:border-rust/40 hover:bg-black/[0.01]'">
                                <div>
                                    <h4 class="text-sm font-bold uppercase tracking-wider transition-colors"
                                        :class="taxonomy.required_fields.includes(item.key) ? 'text-rust' : 'text-primary'"
                                        x-text="item.title"></h4>
                                    <p class="text-xs text-forge-mid mt-1 font-serif" x-text="item.desc"></p>
                                </div>
                                <div class="w-5 h-5 rounded-full border-2 flex items-center justify-center mt-0.5 flex-shrink-0 transition-all duration-200"
                                     :class="taxonomy.required_fields.includes(item.key) ? 'border-rust bg-rust' : 'border-border bg-canvas'">
                                    <svg x-show="taxonomy.required_fields.includes(item.key)" class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                                    </svg>
                                </div>
                            </div>
                        </template>
                    </div>
                </div>

                <!-- Tab: Vocabularies -->
                <div x-show="activeTab === 'vocabularies'" class="space-y-6">
                    <div class="flex justify-between items-center pb-2 border-b border-border/40">
                        <h3 class="text-xl font-bold uppercase tracking-tight text-primary">Manage Vocabularies</h3>
                        <button @click="showNewVocabForm = true" x-show="!showNewVocabForm"
                                class="pen-btn-primary pen-btn-sm">
                            + Add Vocabulary
                        </button>
                    </div>

                    <!-- Inline Add Vocabulary Form -->
                    <div x-show="showNewVocabForm" x-cloak x-transition class="pen-card p-6 bg-rust-wash border-rust/60 max-w-xl">
                        <h4 class="text-sm font-bold uppercase tracking-wide text-rust mb-4">Create New Vocabulary</h4>
                        <div class="space-y-4">
                            <div>
                                <label class="pen-label block mb-1">Vocabulary Name</label>
                                <input type="text" x-model="newVocabName" placeholder="e.g. Topics, Habitat, Author Rank" class="pen-input w-full bg-card border-2 border-border focus:border-rust">
                                <span class="text-[10px] text-forge-mid font-mono mt-1 block">
                                    Machine key generated dynamically: <span class="font-bold" x-text="newVocabName.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '') || '(none)'"></span>
                                </span>
                            </div>
                            <div class="flex items-center gap-2">
                                <input type="checkbox" x-model="newVocabControlled" id="new-vocab-ctrl" class="rounded border-border text-rust focus:ring-rust">
                                <label for="new-vocab-ctrl" class="text-xs font-bold uppercase tracking-wide text-forge-dark cursor-pointer select-none flex items-center gap-1.5"
                                       title="When enabled, writers must choose from the predefined terms list below and cannot type in custom tags on the fly. This prevents duplicate/messy tags (e.g. 'co-work' vs 'cowork').">
                                    Restricted to Listed Terms
                                    <svg class="w-3.5 h-3.5 text-forge-mid cursor-help hover:text-rust" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z"></path>
                                    </svg>
                                </label>
                            </div>
                            <div class="flex gap-2 pt-2">
                                <button @click="addVocabularyInline()" class="pen-btn-primary pen-btn-sm">
                                    Create
                                </button>
                                <button @click="showNewVocabForm = false; newVocabName = ''" class="px-3 py-1.5 border border-border text-xs uppercase tracking-wider font-bold hover:bg-black/[0.02]">
                                    Cancel
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- Vocabularies Cards Grid -->
                    <div class="grid grid-cols-1 gap-8">
                        <template x-for="(vocab, key) in taxonomy.vocabularies" :key="key">
                            <div class="pen-card p-8 bg-card flex flex-col justify-between"
                                 :class="key === taxonomy.primary_vocabulary ? 'border-rust shadow-sm' : 'border-border'">

                                <div>
                                    <!-- Card Header -->
                                    <div class="flex justify-between items-start mb-6 border-b border-border/40 pb-4">
                                        <div>
                                            <div class="flex items-center gap-2">
                                                <!-- Editable Label -->
                                                <input type="text" x-model="vocab.label"
                                                       :title="'Machine Name: ' + key"
                                                       class="text-xl font-bold font-sans uppercase tracking-tight bg-transparent border-b-2 border-transparent hover:border-border/60 focus:border-rust focus:outline-none transition-colors duration-150 py-0.5">

                                                <span x-show="key === taxonomy.primary_vocabulary"
                                                      class="pen-badge-acid text-[9px] px-2 py-0.5 font-bold uppercase tracking-wider flex-shrink-0">
                                                    Primary Category
                                                  </span>
                                              </div>
                                          </div>
                                        <div class="flex items-center gap-6">
                                            <!-- Controlled Toggle Switch -->
                                             <div class="flex items-center gap-2">
                                                 <input type="checkbox" x-model="vocab.controlled" :id="'ctrl-' + key" class="rounded border-border text-rust focus:ring-rust">
                                                 <label :for="'ctrl-' + key" class="text-[10px] font-bold uppercase tracking-wider text-forge-dark cursor-pointer select-none flex items-center gap-1"
                                                        title="When enabled, writers must choose from the predefined terms list below and cannot type in custom tags on the fly. This prevents duplicate/messy tags (e.g. 'co-work' vs 'cowork').">
                                                     Restricted to Listed Terms
                                                     <svg class="w-3 h-3 text-forge-mid cursor-help hover:text-rust" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                                                         <path stroke-linecap="round" stroke-linejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z"></path>
                                                     </svg>
                                                 </label>
                                             </div>

                                            <!-- Delete vocabulary -->
                                            <button @click="removeVocabulary(key)" class="text-forge-mid hover:text-danger transition-colors p-1" title="Delete Vocabulary">
                                                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                                </svg>
                                            </button>
                                        </div>
                                    </div>

                                    <!-- Terms Chip Builder -->
                                    <div class="space-y-3">
                                        <label class="pen-label block">Vocabulary Terms</label>
                                        <div class="flex flex-wrap gap-3 items-center">
                                            <template x-for="(term, index) in vocab.terms" :key="index">
                                                <div class="group inline-flex items-center px-3 py-1.5 bg-canvas border border-border text-xs font-bold font-sans transition-all select-none">
                                                    <span x-text="term"></span>
                                                    <!-- Sorting and deleting controls -->
                                                    <div class="ml-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                                        <button @click="moveTerm(key, index, -1)" class="text-forge-mid hover:text-rust p-0.5" title="Move Left">
                                                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" /></svg>
                                                        </button>
                                                        <button @click="moveTerm(key, index, 1)" class="text-forge-mid hover:text-rust p-0.5" title="Move Right">
                                                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" /></svg>
                                                        </button>
                                                        <button @click="removeTerm(key, index)" class="text-forge-mid hover:text-danger p-0.5" title="Remove">
                                                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
                                                        </button>
                                                    </div>
                                                </div>
                                            </template>

                                            <!-- Inline Add Term Form -->
                                            <div class="flex items-center border border-border bg-canvas focus-within:border-rust transition-colors duration-150 h-8">
                                                <input type="text" x-model="newTermInputs[key]" @keydown.enter.prevent="addTermInline(key)" placeholder="Add term..." class="bg-transparent text-xs px-3 py-1 focus:outline-none w-28">
                                                <button @click="addTermInline(key)" class="px-2.5 h-full text-[10px] font-bold uppercase tracking-wider text-forge-dark hover:text-rust border-l border-border hover:bg-black/[0.02] flex items-center justify-center" title="Add Term">
                                                    + Add
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </template>
                    </div>
                </div>

                <!-- Tab: Primary Category -->
                <div x-show="activeTab === 'general'" class="space-y-8 max-w-4xl">
                    <div class="pen-card p-8 bg-card">
                        <h3 class="text-xl font-bold uppercase tracking-tight text-primary mb-4 pb-2 border-b border-border/40">
                            Primary Category Configuration
                        </h3>

                        <!-- Visual Directory Maker Path Preview -->
                        <div class="mb-8">
                            <label class="pen-label block mb-2">Live Directory Path Preview</label>
                            <p class="text-xs text-forge-dark font-serif mb-3 leading-relaxed">
                                The folder organization on the web server disk is flat. Articles are stored in folders matching their slug, while the primary vocabulary determines their taxonomy grouping in dashboards.
                            </p>
                            <div class="bg-canvas border-2 border-border p-4 font-mono text-xs flex items-center gap-2 text-forge-black relative overflow-x-auto">
                                <svg class="w-4 h-4 text-rust flex-shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-18.75 0a2.25 2.25 0 00-2.25 2.25v4.5A2.25 2.25 0 003 21.75h18a2.25 2.25 0 002.25-2.25v-4.5a2.25 2.25 0 00-2.25-2.25m-18.75 0V7.5A2.25 2.25 0 015.25 5.25h13.5A2.25 2.25 0 0121 7.5v5.25" />
                                </svg>
                                <span class="font-bold text-forge-dark">content/</span>
                                <span class="bg-rust-wash text-rust border border-rust/30 px-1.5 py-0.5 rounded font-black lowercase text-[10px]">post-slug</span>
                                <span class="font-bold text-forge-dark">/</span>
                                <span class="text-forge-mid">index.md</span>
                            </div>
                        </div>

                        <!-- Dropdown Selector -->
                        <div class="space-y-2">
                            <label class="pen-label block">Primary Category Vocabulary</label>
                            <p class="text-[11px] text-forge-mid font-serif leading-relaxed">
                                Select which vocabulary defines the primary category for content pages. We recommend choosing a vocabulary that categorizes core topics or sections.
                            </p>
                            <select x-model="taxonomy.primary_vocabulary" class="pen-input bg-canvas max-w-md w-full border-2 focus:border-rust">
                                <template x-for="(vocab, key) in taxonomy.vocabularies" :key="key">
                                    <option :value="key" x-text="vocab.label || key" :selected="key === taxonomy.primary_vocabulary"></option>
                                </template>
                            </select>
                        </div>
                    </div>
                </div>
            </template>
        </main>
    </div>

    <!-- Delete Vocabulary Confirmation Modal -->
    <div x-show="deleteVocabModalOpen" x-cloak class="pen-modal-overlay p-4" style="display:none" x-transition>
        <div class="pen-modal-danger min-w-0 w-full max-w-[480px] sm:min-w-[480px]" @click.away="deleteVocabModalOpen = false" @keydown.escape.window="deleteVocabModalOpen = false">
            <div class="pen-modal-header">
                <h3 class="pen-modal-title">Delete Vocabulary</h3>
                <button @click="deleteVocabModalOpen = false" class="text-forge-mid hover:text-forge-black">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>
            <div class="pen-modal-body space-y-3">
                <p class="text-sm text-forge-black font-sans">
                    Are you sure you want to delete the vocabulary <strong class="font-mono text-xs bg-canvas px-1.5 py-0.5 border border-border" x-text="taxonomy.vocabularies[vocabToDelete]?.label || vocabToDelete"></strong>?
                </p>
                <p class="text-xs text-forge-muted font-serif leading-prose">
                    This action is immediate and cannot be undone.
                </p>
            </div>
            <div class="pen-modal-footer">
                <button @click="deleteVocabModalOpen = false" class="pen-btn pen-btn-secondary pen-btn-sm">Cancel</button>
                <button @click="confirmRemoveVocabulary()" class="pen-btn pen-btn-danger pen-btn-sm">Delete Vocabulary</button>
            </div>
        </div>
    </div>

    <!-- Generic Warning Alert Modal -->
    <div x-show="alertModalOpen" x-cloak class="pen-modal-overlay p-4" style="display:none" x-transition>
        <div class="pen-modal min-w-0 w-full max-w-[480px] sm:min-w-[480px]" @click.away="alertModalOpen = false" @keydown.escape.window="alertModalOpen = false">
            <div class="pen-modal-header">
                <h3 class="pen-modal-title" x-text="alertModalTitle || 'Attention'"></h3>
                <button @click="alertModalOpen = false" class="text-forge-mid hover:text-forge-black">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>
            <div class="pen-modal-body space-y-3">
                <p class="text-sm text-forge-black font-sans" x-text="alertModalMessage"></p>
            </div>
            <div class="pen-modal-footer">
                <button @click="alertModalOpen = false" class="pen-btn pen-btn-primary pen-btn-sm">Dismiss</button>
            </div>
        </div>
    </div>

    <!-- Footer -->
    <?php include "includes/_admin-footer.php"; ?>

    <!-- JS Logic -->
    <script src="js/settings-structure.js"></script>
</body>
</html>
