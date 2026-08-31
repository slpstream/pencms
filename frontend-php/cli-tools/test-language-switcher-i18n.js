'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');

const switcher = require(path.join(
  __dirname,
  '../public/assets/vendor/pencms/language-switcher.js'
));

assert.equal(switcher.normalizeCode(' PT_BR '), 'pt-br');
assert.equal(
  switcher.resolveLanguageLabel('fr', 'Français personnalisé', {
    DisplayNames: class {
      of() {
        return 'ignored';
      }
    },
  }),
  'Français personnalisé',
  'configured override wins'
);
assert.equal(
  switcher.resolveLanguageLabel('fr', '', {
    DisplayNames: class {
      constructor(locales, options) {
        assert.deepEqual(locales, ['fr']);
        assert.deepEqual(options, { type: 'language' });
      }

      of(code) {
        assert.equal(code, 'fr');
        return 'français';
      }
    },
  }),
  'français',
  'Intl.DisplayNames supplies the endonym'
);
assert.equal(
  switcher.resolveLanguageLabel('de', '', {}),
  'de',
  'missing Intl uses the safe code fallback'
);
assert.equal(
  switcher.resolveLanguageLabel('es', '', {
    DisplayNames: class {
      constructor() {
        throw new RangeError('unsupported');
      }
    },
  }),
  'es',
  'throwing Intl uses the safe code fallback'
);

class FakeLabel {
  constructor(text) {
    this.textContent = text;
  }
}

class FakeElement {
  constructor(attributes = {}, label = null) {
    this.attributes = { ...attributes };
    this.label = label;
  }

  getAttribute(name) {
    return this.attributes[name] ?? null;
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  removeAttribute(name) {
    delete this.attributes[name];
  }

  querySelector(selector) {
    return selector === '[data-pen-language-label]' ? this.label : null;
  }
}

const englishLabel = new FakeLabel('en');
const frenchLabel = new FakeLabel('Français personnalisé');
const english = new FakeElement({
  'data-pen-language-code': 'en',
  'data-pen-language-override': '',
  href: '/stale-en',
  'aria-current': 'page',
}, englishLabel);
const french = new FakeElement({
  'data-pen-language-code': 'fr',
  'data-pen-language-override': 'Français personnalisé',
  href: '/stale-fr',
}, frenchLabel);
const nav = {
  querySelectorAll(selector) {
    assert.equal(selector, '[data-pen-language-code]');
    return [english, french];
  },
};
const headAlternates = [
  new FakeElement({ hreflang: 'en', href: '/about/' }),
  new FakeElement({ hreflang: 'fr', href: '/fr/about/' }),
];

switcher.enhanceSwitcher(nav, headAlternates, 'fr', {
  DisplayNames: class {
    of(code) {
      return code === 'en' ? 'English' : 'français';
    }
  },
});

assert.equal(english.getAttribute('href'), '/about/');
assert.equal(french.getAttribute('href'), '/fr/about/');
assert.equal(english.getAttribute('aria-current'), null);
assert.equal(french.getAttribute('aria-current'), 'page');
assert.equal(englishLabel.textContent, 'English');
assert.equal(frenchLabel.textContent, 'Français personnalisé');

console.log('Language switcher JS: passed');
