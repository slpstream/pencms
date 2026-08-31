/**
 * PenCMS Admin Translations controller.
 * Human/manual localization remains available without AI and while agents pause.
 */
(function (root) {
  'use strict';

  const helpers = {
    normalizeCode(value) {
      return String(value || '').trim().replace(/_/g, '-').toLowerCase();
    },

    siblingFor(row, language) {
      const code = helpers.normalizeCode(language);
      return (row && Array.isArray(row.siblings) ? row.siblings : [])
        .find((sibling) => helpers.normalizeCode(sibling.language) === code) || null;
    },

    editorParams(row, language) {
      return {
        id: row.slug,
        collection: row.collection || 'general',
        lang: helpers.normalizeCode(language),
      };
    },

    tabFromSearch(search) {
      const tab = new URLSearchParams(search || '').get('tab');
      return ['languages', 'coverage', 'strings'].includes(tab) ? tab : 'languages';
    },
  };

  root.PenTranslations = helpers;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = helpers;
  }

  if (!root.document) return;

  root.document.addEventListener('alpine:init', () => {
    root.Alpine.data('translationsPage', () => ({
      activeTab: helpers.tabFromSearch(root.location.search),
      loading: true,
      saving: false,
      actionKey: '',
      message: '',
      messageType: 'success',

      config: {
        language: 'en',
        languages: [],
        language_labels: {},
        translation_automation_paused: false,
        i18n_active: false,
        automation_policy: {
          enabled: false,
          targets: {},
          policy_valid: true,
          policy_error: null,
        },
      },
      defaultLanguage: 'en',
      languageRows: [],
      newLanguage: '',
      agentKeys: [],
      automationEnabled: false,
      automationRows: [],

      coverage: {
        totals: {
          eligible: 0,
          existing: 0,
          published: 0,
          draft: 0,
          needs_review: 0,
          rejected: 0,
          missing: 0,
        },
        items: [],
      },
      targetLanguage: '',
      coverageSearch: '',
      coverageState: 'all',
      runs: [],

      stringLanguage: '',
      stringRows: [],
      stringBundle: null,

      async init() {
        await this.loadAll();
        this.$watch(
          () => this.$store.app.activeSiteId,
          async (next, previous) => {
            if (next && next !== previous) {
              this.syncUrl();
              await this.loadAll();
            }
          }
        );
      },

      notify(message, type = 'success') {
        this.message = message;
        this.messageType = type;
        root.clearTimeout(this._messageTimer);
        this._messageTimer = root.setTimeout(() => {
          this.message = '';
        }, 5000);
      },

      setTab(tab) {
        this.activeTab = tab;
        this.syncUrl();
      },

      syncUrl() {
        const store = root.Alpine.store('app');
        const href = store && typeof store.adminPath === 'function'
          ? store.adminPath('admin-translations.php', { tab: this.activeTab })
          : `admin-translations.php?tab=${encodeURIComponent(this.activeTab)}`;
        root.history.replaceState(null, '', href);
      },

      async loadAll() {
        this.loading = true;
        this.message = '';
        try {
          const [config, keyResponse] = await Promise.all([
            root.api.getTranslationConfig(),
            root.api.getAgentKeys(),
          ]);
          this.agentKeys = (keyResponse && keyResponse.keys) || [];
          this.applyConfig(config);
          await Promise.all([this.loadCoverage(), this.loadRuns(), this.loadStrings()]);
        } catch (error) {
          console.error('Failed to load translation workspace:', error);
          this.notify(error.message || 'Failed to load translations.', 'error');
        } finally {
          this.loading = false;
        }
      },

      applyConfig(config) {
        this.config = config || this.config;
        this.defaultLanguage = this.config.language || 'en';
        const labels = this.config.language_labels || {};
        this.languageRows = (this.config.languages || []).map((code) => ({
          code,
          label: labels[code] || '',
        }));
        const policy = this.config.automation_policy || { enabled: false, targets: {} };
        this.automationEnabled = policy.enabled === true;
        this.syncAutomationRows(policy.targets || {});
        const targets = this.targetLanguages;
        if (!targets.includes(this.targetLanguage)) {
          this.targetLanguage = targets[0] || '';
        }
        const configured = this.config.languages || [];
        if (!configured.includes(this.stringLanguage)) {
          this.stringLanguage = configured[0] || this.defaultLanguage;
        }
      },

      get targetLanguages() {
        return (this.config.languages || []).filter(
          (code) => code !== this.config.language
        );
      },

      get compatibleAgentKeys() {
        const siteId = this.$store?.app?.activeSiteId
          || root.Alpine.store('app').activeSiteId
          || 'default';
        return this.agentKeys.filter((key) => (
          (key.site_id || 'default') === siteId
          && Array.isArray(key.scopes)
          && key.scopes.includes('read')
          && key.scopes.includes('write')
        ));
      },

      syncAutomationRows(targets = null) {
        const existing = {};
        this.automationRows.forEach((row) => {
          existing[row.language] = row;
        });
        const policyTargets = targets || {};
        const defaultLanguage = helpers.normalizeCode(this.defaultLanguage);
        const targetCodes = this.languageRows
          .map((row) => helpers.normalizeCode(row.code))
          .filter((code) => code && code !== defaultLanguage);
        this.automationRows = [...new Set(targetCodes)].map((language) => {
          const configured = policyTargets[language];
          const prior = existing[language];
          const target = configured || prior || {};
          return {
            language,
            enabled: !!configured || !!prior?.enabled,
            operation: target.operation || 'translate',
            model: target.model || '',
            agent_key_id: target.agent_key_id || '',
            review_policy: target.review_policy || 'require_review',
            binding_valid: configured ? configured.binding_valid !== false : true,
            binding_error: configured?.binding_error || null,
            agent_key_name: configured?.agent_key_name || null,
          };
        });
      },

      automationPolicyPayload() {
        if (!this.automationEnabled) {
          return { enabled: false, targets: {} };
        }
        const targets = {};
        this.automationRows
          .filter((row) => row.enabled)
          .forEach((row) => {
            targets[row.language] = {
              operation: row.operation,
              model: String(row.model || '').trim(),
              agent_key_id: row.agent_key_id,
              review_policy: row.review_policy,
            };
          });
        return { enabled: true, targets };
      },

      displayLanguage(code) {
        const override = (this.config.language_labels || {})[code];
        if (override) return override;
        try {
          if (root.Intl && root.Intl.DisplayNames) {
            const names = new root.Intl.DisplayNames([code], { type: 'language' });
            return names.of(code) || code;
          }
        } catch (_) { /* use code */ }
        return code;
      },

      addLanguage() {
        const code = helpers.normalizeCode(this.newLanguage);
        if (!code) return;
        if (!this.languageRows.some((row) => row.code === code)) {
          this.languageRows.push({ code, label: '' });
          this.syncAutomationRows();
        }
        this.newLanguage = '';
      },

      removeLanguage(code) {
        this.languageRows = this.languageRows.filter((row) => row.code !== code);
        this.syncAutomationRows();
      },

      configPayload(paused = this.config.translation_automation_paused) {
        const defaultLanguage = helpers.normalizeCode(this.defaultLanguage) || 'en';
        const rows = this.languageRows
          .map((row) => ({
            code: helpers.normalizeCode(row.code),
            label: String(row.label || '').trim(),
          }))
          .filter((row) => row.code);
        const languages = [...new Set(rows.map((row) => row.code))];
        if (languages.length && !languages.includes(defaultLanguage)) {
          languages.unshift(defaultLanguage);
        }
        const languageLabels = {};
        rows.forEach((row) => {
          if (row.label) languageLabels[row.code] = row.label;
        });
        return {
          language: defaultLanguage,
          languages,
          language_labels: languageLabels,
          translation_automation_paused: !!paused,
          automation_policy: this.automationPolicyPayload(),
        };
      },

      async saveLanguages() {
        this.saving = true;
        try {
          const config = await root.api.updateTranslationConfig(this.configPayload());
          this.applyConfig(config);
          await Promise.all([this.loadCoverage(), this.loadStrings()]);
          this.notify(
            config.i18n_active
              ? 'Language configuration saved. i18n is active.'
              : 'Language configuration saved. i18n remains inactive.'
          );
        } catch (error) {
          this.notify(error.message || 'Language configuration failed.', 'error');
        } finally {
          this.saving = false;
        }
      },

      async setAutomationPaused(paused) {
        this.actionKey = 'pause';
        try {
          const config = await root.api.updateTranslationConfig({
            language: this.config.language,
            languages: this.config.languages || [],
            language_labels: this.config.language_labels || {},
            translation_automation_paused: !!paused,
          });
          this.config = config;
          this.notify(
            paused
              ? 'Agent translation writes paused. Human edits remain available.'
              : 'Agent translation writes resumed.'
          );
        } catch (error) {
          this.notify(error.message || 'Pause update failed.', 'error');
        } finally {
          this.actionKey = '';
        }
      },

      async loadCoverage() {
        const language = this.targetLanguage || null;
        this.coverage = await root.api.getTranslationCoverage(language);
      },

      async changeTargetLanguage() {
        await this.loadCoverage();
      },

      async loadRuns() {
        try {
          const response = await root.api.getTranslationRuns(10);
          this.runs = response.runs || [];
        } catch (error) {
          console.warn('Translation run history unavailable:', error);
          this.runs = [];
        }
      },

      rowSibling(row) {
        return helpers.siblingFor(row, this.targetLanguage);
      },

      rowState(row) {
        const sibling = this.rowSibling(row);
        if (!sibling) return 'missing';
        if (sibling.needs_review) return 'needs_review';
        if (sibling.review_decision === 'rejected') return 'rejected';
        if (sibling.published) return 'published';
        return sibling.status || 'draft';
      },

      get filteredCoverageItems() {
        const query = this.coverageSearch.trim().toLowerCase();
        return (this.coverage.items || []).filter((row) => {
          if (query && !String(row.slug || '').toLowerCase().includes(query)) {
            return false;
          }
          return this.coverageState === 'all'
            || this.rowState(row) === this.coverageState;
        });
      },

      editorUrl(row, language) {
        const store = root.Alpine.store('app');
        const params = helpers.editorParams(row, language);
        return store && typeof store.adminPath === 'function'
          ? store.adminPath('admin-editor.php', params)
          : `admin-editor.php?${new URLSearchParams(params).toString()}`;
      },

      openSibling(row, language = this.targetLanguage) {
        root.location.href = this.editorUrl(row, language);
      },

      async createOrOpenSibling(row) {
        const language = this.targetLanguage;
        const sibling = helpers.siblingFor(row, language);
        if (sibling) {
          this.openSibling(row, language);
          return;
        }
        this.actionKey = `create:${row.slug}:${language}`;
        try {
          await root.api.createTranslationSibling(
            row.collection || 'general',
            row.slug,
            language
          );
          this.openSibling(row, language);
        } catch (error) {
          this.notify(error.message || 'Could not create sibling.', 'error');
        } finally {
          this.actionKey = '';
        }
      },

      async review(row, decision) {
        const language = this.targetLanguage;
        this.actionKey = `${decision}:${row.slug}:${language}`;
        try {
          await root.api.reviewTranslation(row.slug, language, decision);
          await this.loadCoverage();
          this.notify(`Translation ${decision === 'approve' ? 'approved' : 'rejected'}.`);
        } catch (error) {
          this.notify(error.message || `Could not ${decision} translation.`, 'error');
        } finally {
          this.actionKey = '';
        }
      },

      async forceRepublish() {
        const siteId = root.Alpine.store('app').activeSiteId || 'default';
        this.actionKey = 'publish';
        try {
          await root.api.runPublish(siteId, { force_full: true });
          this.notify('Full site publish started.');
        } catch (error) {
          this.notify(error.message || 'Could not start full publish.', 'error');
        } finally {
          this.actionKey = '';
        }
      },

      async loadStrings() {
        const language = this.stringLanguage || this.defaultLanguage;
        const bundle = await root.api.getUiStrings(language);
        this.stringBundle = bundle;
        this.stringRows = Object.entries(bundle.strings || {}).map(([key, value]) => ({
          key,
          effective: value.effective,
          source: value.source,
          useOverride: Object.prototype.hasOwnProperty.call(
            bundle.overrides || {},
            key
          ),
          override: Object.prototype.hasOwnProperty.call(
            bundle.overrides || {},
            key
          ) ? bundle.overrides[key] : value.effective,
        }));
      },

      async changeStringLanguage() {
        await this.loadStrings();
      },

      resetString(row) {
        row.useOverride = false;
        row.override = row.effective;
      },

      async saveStrings() {
        if (!this.config.i18n_active) return;
        this.saving = true;
        const overrides = {};
        this.stringRows.forEach((row) => {
          if (row.useOverride) overrides[row.key] = String(row.override ?? '');
        });
        try {
          const bundle = await root.api.updateUiStrings(
            this.stringLanguage,
            overrides
          );
          this.stringBundle = bundle;
          await this.loadStrings();
          this.notify('UI string overrides saved to disk.');
        } catch (error) {
          this.notify(error.message || 'UI string save failed.', 'error');
        } finally {
          this.saving = false;
        }
      },

      formatRunTime(value) {
        if (!value) return '—';
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
      },
    }));
  });
})(typeof window !== 'undefined' ? window : globalThis);
