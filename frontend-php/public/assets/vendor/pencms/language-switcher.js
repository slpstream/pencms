(function (root, factory) {
  'use strict';

  const api = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  }
  if (root) {
    root.PenLanguageSwitcher = api;
  }

  if (!root || !root.document) {
    return;
  }
  const start = () => api.enhanceDocument(root.document, root.Intl);
  if (root.document.readyState === 'loading') {
    root.document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    start();
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function normalizeCode(value) {
    return String(value || '').trim().replaceAll('_', '-').toLowerCase();
  }

  function resolveLanguageLabel(code, override, intlObject) {
    const normalized = normalizeCode(code);
    const configured = String(override || '').trim();
    if (configured) {
      return configured;
    }
    if (!normalized) {
      return '';
    }
    try {
      if (intlObject && typeof intlObject.DisplayNames === 'function') {
        const names = new intlObject.DisplayNames([normalized], { type: 'language' });
        const label = names.of(normalized);
        if (typeof label === 'string' && label.trim()) {
          return label.trim();
        }
      }
    } catch (_) {
      // Unsupported/invalid locale: retain the safe code fallback.
    }
    return normalized;
  }

  function alternateMap(alternateLinks) {
    const alternates = new Map();
    Array.from(alternateLinks || []).forEach((link) => {
      const code = normalizeCode(link.getAttribute('hreflang'));
      const href = String(link.getAttribute('href') || '').trim();
      if (code && href) {
        alternates.set(code, href);
      }
    });
    return alternates;
  }

  function enhanceSwitcher(nav, alternateLinks, currentLanguage, intlObject) {
    if (!nav || typeof nav.querySelectorAll !== 'function') {
      return;
    }
    const alternates = alternateMap(alternateLinks);
    if (alternates.size < 2) {
      return;
    }
    const current = normalizeCode(currentLanguage);
    Array.from(nav.querySelectorAll('[data-pen-language-code]')).forEach((link) => {
      const code = normalizeCode(link.getAttribute('data-pen-language-code'));
      if (!alternates.has(code)) {
        return;
      }
      link.setAttribute('href', alternates.get(code));
      if (code === current) {
        link.setAttribute('aria-current', 'page');
      } else {
        link.removeAttribute('aria-current');
      }
      const labelNode = link.querySelector('[data-pen-language-label]');
      if (labelNode) {
        labelNode.textContent = resolveLanguageLabel(
          code,
          link.getAttribute('data-pen-language-override'),
          intlObject
        );
      }
    });
  }

  function enhanceDocument(documentObject, intlObject) {
    if (!documentObject || typeof documentObject.querySelectorAll !== 'function') {
      return;
    }
    const alternates = documentObject.querySelectorAll(
      'head link[rel~="alternate"][hreflang]'
    );
    const currentLanguage = documentObject.documentElement
      ? documentObject.documentElement.getAttribute('lang')
      : '';
    Array.from(
      documentObject.querySelectorAll('[data-pen-language-switcher]')
    ).forEach((nav) => {
      enhanceSwitcher(nav, alternates, currentLanguage, intlObject);
    });
  }

  return {
    normalizeCode,
    resolveLanguageLabel,
    enhanceSwitcher,
    enhanceDocument,
  };
}));
