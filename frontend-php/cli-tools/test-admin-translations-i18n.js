'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');

let alpineFactory = null;
let wizardFactory = null;
const apiCalls = [];
const store = {
  activeSiteId: 'default',
  adminPath(file, params = {}) {
    const query = new URLSearchParams({ ...params, site: this.activeSiteId });
    return `${file}?${query.toString()}`;
  },
};

global.window = {
  document: {
    addEventListener(event, callback) {
      if (event === 'alpine:init') callback();
    },
  },
  location: { search: '?tab=coverage', href: '' },
  history: { replaceState() {} },
  setTimeout,
  clearTimeout,
  Intl,
  Alpine: {
    data(name, factory) {
      if (name === 'translationsPage') alpineFactory = factory;
      if (name === 'wizard4') wizardFactory = factory;
    },
    store(name) {
      assert.equal(name, 'app');
      return store;
    },
  },
};
global.Alpine = global.window.Alpine;
global.document = global.window.document;

const helpers = require(path.join(
  __dirname,
  '../src/admin/js/translations.js'
));

assert.equal(helpers.normalizeCode(' PT_BR '), 'pt-br');
assert.equal(helpers.tabFromSearch('?tab=strings'), 'strings');
assert.equal(helpers.tabFromSearch('?tab=switcher'), 'languages');
assert.deepEqual(
  helpers.editorParams({ slug: 'guide', collection: 'summer' }, 'FR'),
  { id: 'guide', collection: 'summer', lang: 'fr' }
);
assert.ok(alpineFactory, 'translations Alpine controller registered');
require(path.join(__dirname, '../src/admin/js/wizard4.js'));
assert.ok(wizardFactory, 'exact-language editor controller registered');

const bundle = {
  config: {
    language: 'en',
    languages: ['en', 'fr'],
    language_labels: {},
    translation_automation_paused: false,
    i18n_active: true,
    automation_policy: {
      enabled: true,
      policy_valid: true,
      policy_error: null,
      targets: {
        fr: {
          operation: 'translate_then_transliterate',
          model: 'provider/localizer',
          agent_key_id: 'ak_localizer',
          agent_key_name: 'nightly-localizer',
          review_policy: 'require_review',
          binding_valid: true,
          binding_error: null,
        },
      },
    },
  },
  language: 'fr',
  strings: {
    home: { effective: 'Home', source: 'engine', override: null },
  },
  overrides: {},
};

window.api = {
  async getTranslationConfig() {
    apiCalls.push(['getConfig']);
    return bundle.config;
  },
  async getAgentKeys() {
    apiCalls.push(['agentKeys']);
    return {
      keys: [{
        key_id: 'ak_localizer',
        name: 'nightly-localizer',
        site_id: 'default',
        scopes: ['read', 'write'],
      }],
    };
  },
  async updateTranslationConfig(payload) {
    apiCalls.push(['config', payload]);
    return { ...bundle.config, ...payload, i18n_active: payload.languages.length >= 2 };
  },
  async getTranslationCoverage(language) {
    apiCalls.push(['coverage', language]);
    return {
      totals: {
        eligible: 1, existing: 0, published: 0, draft: 0,
        needs_review: 0, rejected: 0, missing: 1,
      },
      items: [{
        slug: 'guide',
        collection: 'summer',
        source: { language: 'en', status: 'published' },
        siblings: [],
        gap_codes: ['fr:missing'],
      }],
    };
  },
  async getTranslationRuns(limit) {
    apiCalls.push(['runs', limit]);
    return { runs: [] };
  },
  async createTranslationSibling(collection, slug, language) {
    apiCalls.push(['create', collection, slug, language]);
    return { entry: { language } };
  },
  async reviewTranslation(slug, language, decision) {
    apiCalls.push(['review', slug, language, decision]);
    return {};
  },
  async getUiStrings(language) {
    apiCalls.push(['strings', language]);
    return { ...bundle, language };
  },
  async updateUiStrings(language, overrides) {
    apiCalls.push(['saveStrings', language, overrides]);
    return { ...bundle, language, overrides };
  },
  async runPublish(site, options) {
    apiCalls.push(['publish', site, options]);
    return { task_id: 'task-1' };
  },
  async updatePage(slug, payload, language, collection) {
    apiCalls.push(['updatePage', slug, payload, language, collection]);
    return { id: slug };
  },
};

async function testController() {
  const controller = alpineFactory();
  controller.$store = { app: store };
  controller.notify = () => {};
  controller.applyConfig(bundle.config);
  assert.deepEqual(controller.targetLanguages, ['fr']);
  assert.equal(controller.targetLanguage, 'fr');
  assert.equal(controller.stringLanguage, 'en');
  assert.equal(controller.automationEnabled, true);
  assert.equal(controller.automationRows[0].operation, 'translate_then_transliterate');
  assert.equal(controller.automationRows[0].agent_key_id, 'ak_localizer');

  controller.defaultLanguage = 'EN';
  controller.languageRows = [
    { code: 'fr', label: 'Français' },
    { code: 'en', label: '' },
  ];
  const payload = controller.configPayload(true);
  assert.deepEqual(payload.languages, ['fr', 'en']);
  assert.equal(payload.language, 'en');
  assert.equal(payload.translation_automation_paused, true);
  assert.deepEqual(payload.language_labels, { fr: 'Français' });
  assert.equal(payload.automation_policy.enabled, true);
  assert.equal(
    payload.automation_policy.targets.fr.operation,
    'translate_then_transliterate'
  );
  assert.equal(payload.automation_policy.targets.fr.model, 'provider/localizer');

  await controller.setAutomationPaused(true);
  assert.ok(apiCalls.some((call) => call[0] === 'config'
    && call[1].translation_automation_paused === true));

  await controller.loadCoverage();
  assert.equal(controller.rowState(controller.coverage.items[0]), 'missing');
  await controller.createOrOpenSibling(controller.coverage.items[0]);
  assert.ok(apiCalls.some((call) => (
    call[0] === 'create'
    && call[1] === 'summer'
    && call[2] === 'guide'
    && call[3] === 'fr'
  )));
  assert.match(window.location.href, /admin-editor\.php\?/);
  assert.match(window.location.href, /lang=fr/);
  assert.match(window.location.href, /collection=summer/);

  controller.coverage.items[0].siblings = [{
    language: 'fr',
    status: 'draft',
    published: false,
    needs_review: true,
  }];
  assert.equal(controller.rowState(controller.coverage.items[0]), 'needs_review');
  await controller.review(controller.coverage.items[0], 'approve');
  assert.ok(apiCalls.some((call) => call.join(':') === 'review:guide:fr:approve'));

  controller.stringLanguage = 'fr';
  controller.stringRows = [{
    key: 'home',
    effective: 'Home',
    source: 'engine',
    useOverride: true,
    override: 'Accueil',
  }];
  await controller.saveStrings();
  assert.ok(apiCalls.some((call) => (
    call[0] === 'saveStrings'
    && call[1] === 'fr'
    && call[2].home === 'Accueil'
  )));

  await controller.forceRepublish();
  assert.ok(apiCalls.some((call) => (
    call[0] === 'publish'
    && call[1] === 'default'
    && call[2].force_full === true
  )));

  const wizard = wizardFactory();
  wizard.showToast = () => {};
  wizard.config = { taxonomy: {}, primary_vocabulary: null };
  wizard.translationConfig = {
    language: 'en',
    languages: ['en', 'fr'],
    language_labels: {},
    i18n_active: true,
  };
  wizard.currentLanguage = 'fr';
  wizard.currentCollection = 'summer';
  wizard.isNew = false;
  wizard.captureTranslationIdentity({
    slug: 'guide',
    category: 'summer',
    domain: 'blog',
    page: false,
    tags: ['locked'],
    taxonomy_seasons: 'summer',
    posts: [{ id: 'index' }, { id: 'bio', content: '_bio.md' }],
  }, true);
  wizard.form = {
    ...wizard.form,
    id: 'guide',
    name: 'Guide français',
    category: 'winter',
    domain: 'blog',
    page: false,
    tags: ['changed'],
    taxonomy_seasons: 'winter',
    language: 'fr',
    translation_group: 'tg_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    created_by: 'agent',
    needs_review: true,
    status: 'draft',
    content: 'Manuel',
    composite: false,
    posts: [{ id: 'index' }],
    partials: { bio: 'Biographie', extra: 'Not allowed' },
  };
  await wizard.save({ throwOnError: true });
  const exactSave = apiCalls.find((call) => call[0] === 'updatePage');
  assert.ok(exactSave, 'exact sibling save reached API');
  assert.equal(exactSave[3], 'fr');
  assert.equal(exactSave[4], 'summer');
  assert.equal(exactSave[2].frontmatter.category, 'summer');
  assert.equal(exactSave[2].frontmatter.taxonomy_seasons, 'summer');
  assert.deepEqual(exactSave[2].frontmatter.tags, ['locked']);
  assert.equal(exactSave[2].composite, true);
  assert.deepEqual(exactSave[2].partials, { bio: 'Biographie' });
  assert.ok(!Object.hasOwn(exactSave[2].frontmatter, 'created_by'));
  assert.ok(!Object.hasOwn(exactSave[2].frontmatter, 'translation_group'));
}

async function testApiClient() {
  window.AUTH = {
    apiBase: 'http://test/api/v1',
    getHeaders: () => ({ 'Content-Type': 'application/json', 'X-Pen-Site-Id': 'default' }),
  };
  window.VAULT = null;
  const requests = [];
  global.fetch = async (url, options) => {
    requests.push([url, options]);
    return {
      ok: true,
      status: 200,
      async json() {
        return {
          frontmatter: { name: 'Guide', category: 'summer' },
          body: 'Bonjour',
          language: 'fr',
          translation_group: 'tg_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
          translations: [{ language: 'en', status: 'published' }],
        };
      },
    };
  };

  const APIClient = require(path.join(__dirname, '../src/admin/js/api.js'));
  const client = new APIClient();
  const page = await client.getPage('guide', 'summer', 'fr');
  assert.equal(page.language, 'fr');
  assert.equal(page.translations[0].language, 'en');
  await client.updatePage('guide', {
    frontmatter: { name: 'Guide', category: 'summer' },
    content: 'Révision',
  }, 'fr', 'summer');
  await client.createTranslationSibling('summer', 'guide', 'fr');
  await client.reviewTranslation('guide', 'fr', 'reject');
  await client.getUiStrings('fr');

  assert.equal(
    requests[0][0],
    'http://test/api/v1/content/collections/summer/entries/guide?language=fr'
  );
  assert.ok(requests.some(([url]) => (
    url === 'http://test/api/v1/translations/guide/fr/review'
  )));
  assert.ok(requests.some(([url]) => (
    url === 'http://test/api/v1/translations/strings?language=fr'
  )));
}

Promise.resolve()
  .then(testController)
  .then(testApiClient)
  .then(() => {
    console.log('Admin translations JS: passed');
  })
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
