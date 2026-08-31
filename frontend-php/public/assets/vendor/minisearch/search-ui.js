/**
 * PenCMS search UI — loads search-index.json (or embedded JSON) into MiniSearch.
 * Expects MiniSearch on window. Config via #pencms-search[data-*] attributes.
 */
(function () {
  'use strict';

  var MIN_QUERY = 2;
  var DEBOUNCE_MS = 150;

  function $(sel, root) {
    return (root || document).querySelector(sel);
  }

  function getConfig(root) {
    return {
      indexUrl: root.getAttribute('data-search-index-url') || '',
      isStatic: root.getAttribute('data-static') === '1' || root.getAttribute('data-static') === 'true',
      basePath: root.getAttribute('data-base-path') || '',
      webRoot: root.getAttribute('data-web-root') || '',
      loadingText: root.getAttribute('data-loading-text') || 'Loading search index…',
      noResultsText: root.getAttribute('data-no-results-text') || 'No results found.',
      hintText: root.getAttribute('data-hint-text') || 'Type at least %d characters to search.',
      unavailableText: root.getAttribute('data-unavailable-text') || 'Search is temporarily unavailable.',
      pageText: root.getAttribute('data-page-text') || 'Page',
      postText: root.getAttribute('data-post-text') || 'Post'
    };
  }

  function resultHref(doc, cfg) {
    if (doc.url) {
      return String(doc.url);
    }
    var slug = doc.id || '';
    if (cfg.isStatic) {
      return cfg.basePath + slug + '/index.html';
    }
    var script = doc.type === 'page' ? 'page.php' : 'post.php';
    return cfg.webRoot + script + '?slug=' + encodeURIComponent(slug);
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function readQueryFromUrl() {
    try {
      var params = new URLSearchParams(window.location.search);
      return params.get('q') || '';
    } catch (e) {
      return '';
    }
  }

  function writeQueryToUrl(q) {
    try {
      var url = new URL(window.location.href);
      if (q) {
        url.searchParams.set('q', q);
      } else {
        url.searchParams.delete('q');
      }
      window.history.replaceState(null, '', url.pathname + url.search + url.hash);
    } catch (e) {
      /* ignore */
    }
  }

  function loadDocuments(cfg) {
    var embedded = $('#search-index-data');
    if (embedded && embedded.textContent.trim()) {
      try {
        return Promise.resolve(JSON.parse(embedded.textContent));
      } catch (e) {
        console.warn('PenCMS search: failed to parse embedded index', e);
      }
    }
    if (!cfg.indexUrl) {
      return Promise.reject(new Error('No search index URL'));
    }
    return fetch(cfg.indexUrl)
      .then(function (res) {
        if (!res.ok) throw new Error('Failed to load search index (' + res.status + ')');
        return res.json();
      });
  }

  function buildIndex(docs) {
    var ms = new MiniSearch({
      fields: ['title', 'tags', 'categories', 'excerpt', 'body'],
      storeFields: ['title', 'url', 'type', 'excerpt', 'tags', 'categories', 'pinned'],
      searchOptions: {
        boost: { title: 5, tags: 3, categories: 3, excerpt: 2, body: 1 },
        prefix: true,
        fuzzy: 0.2
      },
      extractField: function (doc, fieldName) {
        var val = doc[fieldName];
        if (Array.isArray(val)) return val.join(' ');
        return val == null ? '' : String(val);
      }
    });
    ms.addAll(docs);
    return ms;
  }

  function renderStatus(el, message, className) {
    el.innerHTML = '<p class="search-status' + (className ? ' ' + className : '') + '">' + escapeHtml(message) + '</p>';
  }

  function renderResults(el, results, cfg) {
    if (!results.length) {
      renderStatus(el, cfg.noResultsText, 'search-status-empty');
      return;
    }
    var html = '<ul class="search-results-list" role="list">';
    for (var i = 0; i < results.length; i++) {
      var doc = results[i];
      var href = resultHref(doc, cfg);
      var typeLabel = doc.type === 'page' ? cfg.pageText : cfg.postText;
      var pinMark = doc.pinned
        ? '<span class="search-result-pin" aria-label="Pinned" title="Pinned">Pinned · </span>'
        : '';
      var excerpt = doc.excerpt ? '<p class="search-result-excerpt">' + escapeHtml(doc.excerpt) + '</p>' : '';
      html +=
        '<li class="search-result-item' + (doc.pinned ? ' search-result-item--pinned' : '') + '">' +
        '<span class="search-result-type" data-type="' + escapeHtml(doc.type || 'post') + '">' + pinMark + escapeHtml(typeLabel) + '</span>' +
        '<h2 class="search-result-title"><a href="' + escapeHtml(href) + '">' + escapeHtml(doc.title || doc.id) + '</a></h2>' +
        excerpt +
        '</li>';
    }
    html += '</ul>';
    el.innerHTML = html;
  }

  function init() {
    var root = $('#pencms-search');
    if (!root) return;
    if (typeof MiniSearch === 'undefined') {
      console.error('PenCMS search: MiniSearch is not loaded');
      return;
    }

    var cfg = getConfig(root);
    var input = $('#search-input', root);
    var resultsEl = $('#search-results', root);
    if (!input || !resultsEl) return;

    var mini = null;
    var debounceTimer = null;

    function runSearch(q) {
      q = (q || '').trim();
      writeQueryToUrl(q);

      if (!mini) {
        renderStatus(resultsEl, cfg.loadingText);
        return;
      }
      if (q.length < MIN_QUERY) {
        renderStatus(resultsEl, cfg.hintText.replace('%d', String(MIN_QUERY)), 'search-status-hint');
        return;
      }
      var hits = mini.search(q);
      hits.sort(function (a, b) {
        var ap = a.pinned ? 1 : 0;
        var bp = b.pinned ? 1 : 0;
        if (ap !== bp) return bp - ap;
        return 0;
      });
      renderResults(resultsEl, hits, cfg);
    }

    renderStatus(resultsEl, cfg.loadingText);

    loadDocuments(cfg)
      .then(function (docs) {
        if (!Array.isArray(docs)) docs = [];
        mini = buildIndex(docs);
        var initial = readQueryFromUrl();
        if (initial) {
          input.value = initial;
          runSearch(initial);
        } else {
          renderStatus(resultsEl, cfg.hintText.replace('%d', String(MIN_QUERY)), 'search-status-hint');
        }
      })
      .catch(function (err) {
        console.error(err);
        renderStatus(resultsEl, cfg.unavailableText, 'search-status-error');
      });

    input.addEventListener('input', function () {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function () {
        runSearch(input.value);
      }, DEBOUNCE_MS);
    });

    input.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        input.value = '';
        runSearch('');
        input.blur();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
