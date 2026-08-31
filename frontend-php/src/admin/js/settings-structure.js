/**
 * PenCMS Taxonomy/Structure Settings Logic
 */
document.addEventListener('alpine:init', () => {
    Alpine.data('settingsStructure', () => ({
        loading: true,
        saving: false,
        activeTab: 'required',
        config: null,
        taxonomy: {
            vocabularies: {},
            primary_vocabulary: '',
            required_fields: []
        },
        message: '',
        isError: false,
        deleteVocabModalOpen: false,
        vocabToDelete: '',
        alertModalOpen: false,
        alertModalTitle: '',
        alertModalMessage: '',

        showAlert(title, message) {
            this.alertModalTitle = title;
            this.alertModalMessage = message;
            this.alertModalOpen = true;
        },

        // Inline vocab form state
        showNewVocabForm: false,
        newVocabName: '',
        newVocabControlled: true,

        // Inline term input state mapping: { vocabKey: currentInputValue }
        newTermInputs: {},

        async init() {
            try {
                const response = await window.api.getTaxonomy();
                this.taxonomy = response.raw;
                this.config = await window.api.getConfig();
                
                // Initialize term input placeholder fields
                Object.keys(this.taxonomy.vocabularies || {}).forEach(k => {
                    this.newTermInputs[k] = '';
                });

                this.loading = false;

                this.$watch(
                    () => this.$store.app.activeSiteId,
                    async (next, prev) => {
                        if (!next || next === prev) return;
                        this.loading = true;
                        try {
                            const response = await window.api.getTaxonomy();
                            this.taxonomy = response.raw;
                            this.config = await window.api.getConfig();
                            Object.keys(this.taxonomy.vocabularies || {}).forEach(k => {
                                if (!(k in this.newTermInputs)) this.newTermInputs[k] = '';
                            });
                        } catch (err) {
                            console.error("Failed to reload taxonomy for site change:", err);
                        } finally {
                            this.loading = false;
                        }
                    }
                );
            } catch (err) {
                console.error("Failed to load taxonomy structure:", err);
                this.isError = true;
                this.message = "Error loading structure settings.";
            }
        },

        async save() {
            this.saving = true;
            this.message = '';
            if (this.taxonomy && this.taxonomy.vocabularies && 'category' in this.taxonomy.vocabularies) {
                this.isError = true;
                this.message = "Failed to save: 'category' is a reserved vocabulary name.";
                this.saving = false;
                return;
            }
            try {
                await window.api.updateTaxonomy(this.taxonomy);
                this.isError = false;
                this.message = "Structure configuration saved successfully.";
                // Refresh local config state
                this.config = await window.api.getConfig();
            } catch (err) {
                console.error("Save failed:", err);
                this.isError = true;
                this.message = "Failed to save structure: " + err.message;
            } finally {
                this.saving = false;
            }
        },

        addVocabularyInline() {
            const name = this.newVocabName.trim();
            if (!name) {
                this.showAlert("Validation Error", "Please enter a vocabulary name.");
                return;
            }
            const slug = name.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '');
            if (!slug) {
                this.showAlert("Validation Error", "Invalid vocabulary name.");
                return;
            }
            if (slug === 'category') {
                this.showAlert("Reserved Name", "The vocabulary name 'category' is reserved to prevent conflicts with the primary classification field.");
                return;
            }
            if (this.taxonomy.vocabularies[slug]) {
                this.showAlert("Duplicate Key", "A vocabulary with this key already exists.");
                return;
            }

            this.taxonomy.vocabularies[slug] = {
                label: name,
                type: 'flat',
                controlled: this.newVocabControlled,
                required: false,
                terms: []
            };

            // Initialize term input field for the new vocabulary
            this.newTermInputs[slug] = '';

            // Reset form
            this.newVocabName = '';
            this.newVocabControlled = true;
            this.showNewVocabForm = false;
            this.message = `Vocabulary "${name}" created. Remember to save changes.`;
            this.isError = false;
        },

        removeVocabulary(key) {
            if (key === this.taxonomy.primary_vocabulary) {
                this.showAlert("Error", "Cannot remove the primary vocabulary. Switch the primary vocabulary first.");
                return;
            }
            this.vocabToDelete = key;
            this.deleteVocabModalOpen = true;
        },
        confirmRemoveVocabulary() {
            const key = this.vocabToDelete;
            if (!key) return;
            delete this.taxonomy.vocabularies[key];
            delete this.newTermInputs[key];
            this.message = "Vocabulary removed. Remember to save changes.";
            this.isError = false;
            this.deleteVocabModalOpen = false;
            this.vocabToDelete = '';
        },

        addTermInline(vocabKey) {
            const term = (this.newTermInputs[vocabKey] || '').trim();
            if (!term) return;

            const vocab = this.taxonomy.vocabularies[vocabKey];
            if (!vocab.terms) {
                vocab.terms = [];
            }

            if (vocab.terms.includes(term)) {
                this.showAlert("Duplicate Term", "This term already exists in this vocabulary.");
                return;
            }

            vocab.terms.push(term);
            this.newTermInputs[vocabKey] = ''; // clear input
        },

        removeTerm(vocabKey, index) {
            this.taxonomy.vocabularies[vocabKey].terms.splice(index, 1);
        },

        moveTerm(vocabKey, index, direction) {
            const terms = this.taxonomy.vocabularies[vocabKey].terms;
            const newIndex = index + direction;
            if (newIndex >= 0 && newIndex < terms.length) {
                const temp = terms[index];
                terms[index] = terms[newIndex];
                terms[newIndex] = temp;
            }
        },

        toggleRequiredField(field) {
            const index = this.taxonomy.required_fields.indexOf(field);
            if (index === -1) {
                this.taxonomy.required_fields.push(field);
            } else {
                this.taxonomy.required_fields.splice(index, 1);
            }
        }
    }));
});
