/**
 * PenCMS Theme Customize controller (customize.js)
 * Twig + CSS workshop: fork / tree / CodeJar save / reset / delete.
 * AI write-through refreshes via refreshAfterAiWrite / refreshAfterAiTreeChange.
 */

const PEN_CODEJAR_THEME_KEY = 'pen-customize-codejar-theme';

document.addEventListener('alpine:init', () => {
  Alpine.data('customize', () => ({
    // ── Chrome (from scaffold) ───────────────────────────────────────
    isDraggingLeftColumn: false,
    isDraggingRightColumn: false,
    toasts: [],
    toastCounter: 0,

    workspacePrefs: {
      sidebarWidth: 32,
      rightColumnWidth: 25,
      leftColumnCollapsed: false,
      rightColumnCollapsed: false,
      secondaryRailCollapsed: false,
      aiAssistantCollapsed: true,
      templatesCardCollapsed: false,
      partialsCardCollapsed: false,
      stylesheetsCardCollapsed: false,
    },

    // ── Theme workshop state ─────────────────────────────────────────
    loading: true,
    forking: false,
    saving: false,
    validating: false,
    validateResult: null,
    resetting: false,
    resettingFile: false,
    deleting: false,
    resetModalOpen: false,
    resetFileModalOpen: false,
    deleteModalOpen: false,
    newFileModalOpen: false,
    newFileKind: 'templates',
    newFileName: '',
    creatingFile: false,
    loadError: '',

    context: {
      exists: false,
      active: false,
      registry_theme: null,
      parent: null,
      name: null,
    },

    files: [],
    selectedPath: null,
    content: '',
    savedContent: '',
    _ignoreSiteWatch: false,

    // CodeJar (editor pane only)
    codejarTheme: 'dark',
    _codejar: null,
    _codejarEl: null,
    _codejarPushing: false,

    get dirty() {
      return this.selectedPath != null && this.content !== this.savedContent;
    },

    get templateFiles() {
      const items = (this.files || []).filter((f) => {
        const p = typeof f === 'string' ? f : f.path;
        return p.startsWith('templates/');
      });
      const getPath = (f) => (typeof f === 'string' ? f : f.path);
      // Priority buckets (not fixed index positions):
      // Top (0) -> Middle (500, sorted alphabetically) -> Bottom (900+)
      const getRank = (path) => {
        const name = path.split('/').pop();
        if (name === 'index.html.twig') return 0;
        if (name === 'archive.html.twig') return 900;
        if (name === 'search.html.twig') return 1000;
        return 500;
      };
      return items.sort((a, b) => {
        const pathA = getPath(a);
        const pathB = getPath(b);
        const rankDiff = getRank(pathA) - getRank(pathB);
        return rankDiff !== 0 ? rankDiff : pathA.localeCompare(pathB);
      });
    },

    get partialFiles() {
      const items = (this.files || []).filter((f) => {
        const p = typeof f === 'string' ? f : f.path;
        return p.startsWith('partials/');
      });
      const getPath = (f) => (typeof f === 'string' ? f : f.path);
      // Priority buckets: Top (0..2) -> Middle (500, sorted alphabetically) -> Bottom (1000)
      const getRank = (path) => {
        const name = path.split('/').pop();
        if (name === '_head.html.twig') return 0;
        if (name === '_header.html.twig') return 1;
        if (name === '_navbar.html.twig') return 2;
        if (name === '_footer.html.twig') return 1000;
        return 500;
      };
      return items.sort((a, b) => {
        const pathA = getPath(a);
        const pathB = getPath(b);
        const rankDiff = getRank(pathA) - getRank(pathB);
        return rankDiff !== 0 ? rankDiff : pathA.localeCompare(pathB);
      });
    },

    get stylesheetFiles() {
      const items = (this.files || []).filter((f) => {
        const p = typeof f === 'string' ? f : f.path;
        return (
          p.startsWith('assets/css/') ||
          p.startsWith('css/') ||
          p.endsWith('.css')
        );
      });
      const getPath = (f) => (typeof f === 'string' ? f : f.path);
      return items.sort((a, b) => getPath(a).localeCompare(getPath(b)));
    },

    get saveStatus() {
      if (this.saving) return 'saving';
      if (this.dirty) return 'unsaved';
      return 'saved';
    },

    get saveStatusText() {
      if (this.saving) return 'Saving…';
      if (this.dirty) return 'Unsaved';
      return 'Saved';
    },

    get baseLabel() {
      const reg = this.context && this.context.registry_theme;
      if (reg && reg !== 'custom') return reg;
      if (this.context && this.context.parent) return this.context.parent;
      return 'starter';
    },

    get forkCtaLabel() {
      return `Customize ${this.baseLabel}`;
    },

    get themeDisplayName() {
      if (this.context && this.context.name) return this.context.name;
      return 'Custom theme';
    },

    get showInactiveBanner() {
      return !!(this.context && this.context.exists && !this.context.active);
    },

    get showValidateBanner() {
      return !!(this.validateResult && this.context && this.context.exists);
    },

    get newFileModalTitle() {
      if (this.newFileKind === 'partials') return 'New Partial';
      if (this.newFileKind === 'stylesheets') return 'New Stylesheet';
      return 'New Template';
    },

    get newFileNameLabel() {
      if (this.newFileKind === 'partials') return 'Partial name';
      if (this.newFileKind === 'stylesheets') return 'Stylesheet name';
      return 'Template name';
    },

    get newFileNamePlaceholder() {
      if (this.newFileKind === 'partials') return 'e.g. hero nav or _sidebar-CTA';
      if (this.newFileKind === 'stylesheets') return 'e.g. brandColors';
      return 'e.g. Custom Page';
    },

    get newFilePrefixHint() {
      if (this.newFileKind === 'partials') return 'partials/_*.html.twig';
      if (this.newFileKind === 'stylesheets') return 'assets/css/*.css';
      return 'templates/*.html.twig';
    },

    get newFilePathPreview() {
      const built = this.buildNewFilePath(this.newFileKind, this.newFileName, { silent: true });
      return built.ok ? built.path : '';
    },

    formatDisplayName(path) {
      if (!path) return '';
      const p = typeof path === 'string' ? path : path.path || '';
      const filename = p.split('/').pop() || p;
      const stripped = filename.replace(/\.(html\.twig|twig|css)$/i, '');
      return stripped.replace(/^_+/, '');
    },

    // ── Helpers ──────────────────────────────────────────────────────
    apiSitesBase() {
      if (Alpine.store('app') && typeof Alpine.store('app').apiSitesBase === 'function') {
        return Alpine.store('app').apiSitesBase();
      }
      const base = (window.AUTH && window.AUTH.apiBase) || '/api/v1';
      return base.replace(/\/v1\/?$/, '');
    },

    siteId() {
      return (Alpine.store('app') && Alpine.store('app').activeSiteId) || 'default';
    },

    themeUrl(suffix = '') {
      return `${this.apiSitesBase()}/sites/${encodeURIComponent(this.siteId())}/theme${suffix}`;
    },

    apiDetail(data, status) {
      return typeof data.detail === 'string'
        ? data.detail
        : data.detail
          ? JSON.stringify(data.detail)
          : `HTTP ${status}`;
    },

    // ── Init ─────────────────────────────────────────────────────────
    async init() {
      window.addEventListener('pen:toast', (e) => {
        if (e.detail && e.detail.message) {
          this.showToast(e.detail.message, e.detail.type || 'success');
        }
      });

      this.loadCodejarThemePref();

      try {
        const saved = localStorage.getItem('pen_editor_workspace_prefs');
        if (saved) {
          this.workspacePrefs = {
            ...this.workspacePrefs,
            ...JSON.parse(saved),
          };
        }
        this.saveWorkspacePrefs();
      } catch (_e) {
        /* ignore */
      }

      await this.reload();

      this.$watch('selectedPath', (path) => {
        if (!path) this.destroyCodeJar();
      });

      this.$watch(
        () => this.$store.app.activeSiteId,
        async (next, prev) => {
          if (this._ignoreSiteWatch) return;
          if (!next || next === prev) return;
          if (this.dirty) {
            if (!confirm('You have unsaved changes. Switch site and discard them?')) {
              this._ignoreSiteWatch = true;
              this.$store.app.activeSiteId = prev;
              queueMicrotask(() => {
                this._ignoreSiteWatch = false;
              });
              return;
            }
          }
          this.clearEditor();
          await this.reload();
        }
      );
    },

    loadCodejarThemePref() {
      try {
        const saved = localStorage.getItem(PEN_CODEJAR_THEME_KEY);
        this.codejarTheme = saved === 'light' || saved === 'dark' ? saved : 'dark';
      } catch (_e) {
        this.codejarTheme = 'dark';
      }
    },

    setCodejarTheme(theme) {
      if (theme !== 'dark' && theme !== 'light') return;
      this.codejarTheme = theme;
      try {
        localStorage.setItem(PEN_CODEJAR_THEME_KEY, theme);
      } catch (_e) {
        /* ignore */
      }
    },

    codejarLanguageForPath(path) {
      if (!path) return 'twig';
      const lower = String(path).toLowerCase();
      if (lower.endsWith('.css')) return 'css';
      return 'twig';
    },

    highlightCodeJar(editor) {
      const hljs = window.hljs;
      const code = editor.textContent || '';
      if (!hljs) {
        editor.textContent = code;
        return;
      }
      const lang = this.codejarLanguageForPath(this.selectedPath);
      try {
        editor.innerHTML = hljs.highlight(code, {
          language: lang,
          ignoreIllegals: true,
        }).value;
      } catch (_e) {
        editor.textContent = code;
      }
    },

    async waitForCodeJar(timeoutMs = 8000) {
      if (typeof window.CodeJar === 'function') return window.CodeJar;
      return new Promise((resolve, reject) => {
        let settled = false;
        const done = (fn) => {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          window.removeEventListener('pen:codejar-ready', onReady);
          resolve(fn);
        };
        const onReady = () => {
          if (typeof window.CodeJar === 'function') done(window.CodeJar);
        };
        const timer = setTimeout(() => {
          if (typeof window.CodeJar === 'function') {
            done(window.CodeJar);
          } else {
            settled = true;
            window.removeEventListener('pen:codejar-ready', onReady);
            reject(new Error('CodeJar failed to load'));
          }
        }, timeoutMs);
        window.addEventListener('pen:codejar-ready', onReady);
        if (typeof window.CodeJar === 'function') done(window.CodeJar);
      });
    },

    async mountCodeJar(el) {
      if (!el) return;
      this.destroyCodeJar();
      this._codejarEl = el;
      try {
        const CodeJar = await this.waitForCodeJar();
        if (this._codejarEl !== el) return;
        const jar = CodeJar(el, (editor) => this.highlightCodeJar(editor), {
          tab: '  ',
          spellcheck: false,
        });
        this._codejar = jar;
        jar.onUpdate((code) => {
          if (this._codejarPushing) return;
          this.content = code;
        });
        this._codejarPushing = true;
        jar.updateCode(this.content || '');
        this._codejarPushing = false;
        if (this.selectedPath) {
          el.setAttribute('aria-label', `Edit ${this.selectedPath}`);
        }
      } catch (err) {
        console.error(err);
        this.showToast(err.message || 'CodeJar failed to load', 'error');
      }
    },

    destroyCodeJar() {
      if (this._codejar && typeof this._codejar.destroy === 'function') {
        try {
          this._codejar.destroy();
        } catch (_e) {
          /* ignore */
        }
      }
      this._codejar = null;
      this._codejarEl = null;
      this._codejarPushing = false;
    },

    pushContentToCodeJar() {
      if (!this._codejar) return;
      const next = this.content || '';
      if (this._codejar.toString() === next) {
        // Path may have changed language; force re-highlight.
        if (this._codejarEl) this.highlightCodeJar(this._codejarEl);
        return;
      }
      this._codejarPushing = true;
      this._codejar.updateCode(next);
      this._codejarPushing = false;
    },

    clearEditor() {
      this.destroyCodeJar();
      this.selectedPath = null;
      this.content = '';
      this.savedContent = '';
      this.files = [];
    },

    async reload() {
      this.loading = true;
      this.loadError = '';
      try {
        await this.loadContext();
        if (this.context.exists) {
          await this.loadTree({ autoOpen: false });
        } else {
          this.clearEditor();
        }
      } catch (err) {
        this.loadError = err.message || String(err);
        this.showToast(this.loadError, 'error');
      } finally {
        this.loading = false;
      }
    },

    async loadContext() {
      const res = await fetch(this.themeUrl('/context'), {
        headers: window.AUTH.getHeaders(),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(this.apiDetail(data, res.status));
      }
      this.context = {
        exists: !!data.exists,
        active: !!data.active,
        registry_theme: data.registry_theme || null,
        parent: data.parent || null,
        name: data.name || null,
        origin: data.origin || null,
        customized_at: data.customized_at || null,
        allowlist: data.allowlist || null,
      };
    },

    async loadTree({ autoOpen = false } = {}) {
      const res = await fetch(this.themeUrl('/tree'), {
        headers: window.AUTH.getHeaders(),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(this.apiDetail(data, res.status));
      }
      this.files = Array.isArray(data.files) ? data.files : [];

      const filePaths = this.files.map((f) => (typeof f === 'string' ? f : f.path));

      if (this.selectedPath && !filePaths.includes(this.selectedPath)) {
        this.destroyCodeJar();
        this.selectedPath = null;
        this.content = '';
        this.savedContent = '';
      }

      if (autoOpen && !this.selectedPath && this.files.length > 0) {
        const first = this.files[0];
        const firstPath = typeof first === 'string' ? first : first.path;
        await this.openFile(firstPath, { skipDirtyCheck: true });
      }
    },

    // ── Fork ─────────────────────────────────────────────────────────
    async forkCustom() {
      if (this.context.exists || this.forking) return;
      this.forking = true;
      try {
        const parent = this.baseLabel;
        const body = parent && parent !== 'custom' ? { parent } : {};
        const res = await fetch(this.themeUrl('/fork'), {
          method: 'POST',
          headers: window.AUTH.getHeaders(),
          body: JSON.stringify(body),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(this.apiDetail(data, res.status));
        }
        this.showToast(`Custom theme created from ${data.parent || parent}`);
        if (Alpine.store('app') && typeof Alpine.store('app').loadSites === 'function') {
          await Alpine.store('app').loadSites();
        }
        await this.loadContext();
        await this.loadTree({ autoOpen: false });
      } catch (err) {
        this.showToast(err.message || String(err), 'error');
      } finally {
        this.forking = false;
      }
    },

    // ── AI write-through refresh ─────────────────────────────────────
    async refreshAfterAiWrite(path) {
      await this.loadTree({ autoOpen: false });
      if (!path) return;
      if (this.selectedPath === path) this.selectedPath = null;
      await this.openFile(path, { skipDirtyCheck: true });
    },

    async refreshAfterAiTreeChange() {
      await this.loadContext();
      if (this.context.exists) {
        await this.loadTree({ autoOpen: false });
      } else {
        this.clearEditor();
      }
      if (Alpine.store('app') && typeof Alpine.store('app').loadSites === 'function') {
        await Alpine.store('app').loadSites();
      }
    },

    // ── New file (human create) ──────────────────────────────────────
    openNewFileModal(kind) {
      if (!this.context || !this.context.exists) return;
      if (kind !== 'templates' && kind !== 'partials' && kind !== 'stylesheets') return;
      this.newFileKind = kind;
      this.newFileName = '';
      if (kind === 'templates') this.workspacePrefs.templatesCardCollapsed = false;
      if (kind === 'partials') this.workspacePrefs.partialsCardCollapsed = false;
      if (kind === 'stylesheets') this.workspacePrefs.stylesheetsCardCollapsed = false;
      this.saveWorkspacePrefs();
      this.newFileModalOpen = true;
      this.$nextTick(() => {
        const el = document.getElementById('new-theme-file-name-input');
        if (el) el.focus();
      });
    },

    _newFileKindConfig(kind) {
      if (kind === 'partials') {
        return {
          prefix: 'partials/',
          defaultExt: '.html.twig',
          validExts: ['.html.twig', '.twig'],
        };
      }
      if (kind === 'stylesheets') {
        return {
          prefix: 'assets/css/',
          defaultExt: '.css',
          validExts: ['.css'],
        };
      }
      return {
        prefix: 'templates/',
        defaultExt: '.html.twig',
        validExts: ['.html.twig', '.twig'],
      };
    },

    _isWindowsReservedName(name) {
      const base = String(name || '').toUpperCase();
      if (!base) return false;
      if (['CON', 'PRN', 'AUX', 'NUL'].includes(base)) return true;
      if (/^COM[1-9]$/.test(base)) return true;
      if (/^LPT[1-9]$/.test(base)) return true;
      return false;
    },

    /**
     * Sanitize a user-entered relative name into path segments (no prefix/ext).
     * @returns {{ ok: true, segments: string[] } | { ok: false, error: string }}
     */
    sanitizeNewFileName(kind, rawName, { silent = false } = {}) {
      const fail = (error) => {
        if (!silent) this.showToast(error, 'error');
        return { ok: false, error };
      };

      let raw = typeof rawName === 'string' ? rawName.trim() : '';
      if (!raw) return fail('Enter a file name.');

      if (raw.includes('\0') || raw.includes('\\')) {
        return fail('Invalid file name.');
      }
      if (/[\x00-\x1f\x7f]/.test(raw)) {
        return fail('Invalid file name.');
      }
      if (raw.startsWith('/') || /^[A-Za-z]:/.test(raw)) {
        return fail('Use a relative name, not an absolute path.');
      }

      const cfg = this._newFileKindConfig(kind);
      // Strip pasted theme-relative prefixes
      const prefixes = ['templates/', 'partials/', 'assets/css/'];
      for (const p of prefixes) {
        if (raw.toLowerCase().startsWith(p)) {
          raw = raw.slice(p.length);
          break;
        }
      }
      raw = raw.replace(/^\/+/, '');
      if (!raw) return fail('Enter a file name.');

      // Split extension from final segment before sanitizing names
      let rel = raw;
      let detectedExt = '';
      const lower = rel.toLowerCase();
      const allExts = ['.html.twig', '.twig', '.css'];
      for (const ext of allExts) {
        if (lower.endsWith(ext)) {
          detectedExt = ext;
          rel = rel.slice(0, -ext.length);
          break;
        }
      }
      if (detectedExt && !cfg.validExts.includes(detectedExt)) {
        return fail(`Use a ${cfg.validExts.join(' or ')} extension for this file type.`);
      }
      if (!rel || rel.endsWith('/') || rel.includes('//')) {
        return fail('Invalid file name.');
      }

      const parts = rel.split('/');
      const segments = [];
      for (let i = 0; i < parts.length; i++) {
        let seg = parts[i];
        if (seg === '' || seg === '.' || seg === '..') {
          return fail('Invalid file name.');
        }
        // Spaces → hyphens
        seg = seg.replace(/\s+/g, '-');
        // Collapse repeated hyphens from multi-spaces
        seg = seg.replace(/-+/g, '-');
        // Reject illegal characters (camelCase letters kept)
        if (!/^[A-Za-z0-9_-]+$/.test(seg)) {
          return fail(
            'Names may only contain letters, numbers, hyphens, and underscores.'
          );
        }
        if (seg === '-' || seg === '_' || /^-+$/.test(seg)) {
          return fail('Invalid file name.');
        }
        if (this._isWindowsReservedName(seg)) {
          return fail('That name is reserved. Choose a different name.');
        }
        segments.push(seg);
      }

      if (!segments.length) return fail('Enter a file name.');

      // Partials: enforce exactly one leading underscore on basename only
      if (kind === 'partials') {
        const last = segments.length - 1;
        let base = segments[last];
        base = base.replace(/^_+/, '');
        if (!base) return fail('Enter a file name.');
        if (this._isWindowsReservedName(base)) {
          return fail('That name is reserved. Choose a different name.');
        }
        segments[last] = `_${base}`;
      }

      return { ok: true, segments, detectedExt };
    },

    /**
     * @returns {{ ok: true, path: string } | { ok: false, error: string }}
     */
    buildNewFilePath(kind, rawName, { silent = false } = {}) {
      const sanitized = this.sanitizeNewFileName(kind, rawName, { silent });
      if (!sanitized.ok) return sanitized;
      const cfg = this._newFileKindConfig(kind);
      const ext = sanitized.detectedExt || cfg.defaultExt;
      const path = `${cfg.prefix}${sanitized.segments.join('/')}${ext}`;
      return { ok: true, path };
    },

    async confirmCreateFile() {
      if (this.creatingFile) return;
      const built = this.buildNewFilePath(this.newFileKind, this.newFileName);
      if (!built.ok) return;

      const path = built.path;
      const exists = (this.files || []).some((f) => {
        const p = typeof f === 'string' ? f : f.path;
        return p === path;
      });
      if (exists) {
        this.showToast(`A file already exists at ${path}`, 'error');
        return;
      }

      if (this.dirty) {
        if (!confirm('You have unsaved changes. Discard them?')) return;
      }

      this.creatingFile = true;
      try {
        const res = await fetch(this.themeUrl('/file'), {
          method: 'PUT',
          headers: window.AUTH.getHeaders(),
          body: JSON.stringify({ path, content: '' }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(this.apiDetail(data, res.status));
        }
        this.newFileModalOpen = false;
        this.newFileName = '';
        await this.loadTree({ autoOpen: false });
        await this.openFile(path, { skipDirtyCheck: true });
        this.showToast(`Created ${path}`);
      } catch (err) {
        this.showToast(err.message || String(err), 'error');
      } finally {
        this.creatingFile = false;
      }
    },

    // ── File open / save ─────────────────────────────────────────────
    closeFile({ skipDirtyCheck = false } = {}) {
      if (!this.selectedPath) return;
      if (!skipDirtyCheck && this.dirty) {
        if (!confirm('You have unsaved changes. Discard them?')) return;
      }
      this.destroyCodeJar();
      this.selectedPath = null;
      this.content = '';
      this.savedContent = '';
    },

    async openFile(path, { skipDirtyCheck = false } = {}) {
      if (!path) return;
      if (path === this.selectedPath) {
        this.closeFile({ skipDirtyCheck });
        return;
      }
      if (!skipDirtyCheck && this.dirty) {
        if (!confirm('You have unsaved changes. Discard them?')) return;
      }
      try {
        const res = await fetch(
          `${this.themeUrl('/file')}?path=${encodeURIComponent(path)}`,
          { headers: window.AUTH.getHeaders() }
        );
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(this.apiDetail(data, res.status));
        }
        this.selectedPath = data.path || path;
        this.content = typeof data.content === 'string' ? data.content : '';
        this.savedContent = this.content;
        this.pushContentToCodeJar();
        if (this._codejarEl && this.selectedPath) {
          this._codejarEl.setAttribute('aria-label', `Edit ${this.selectedPath}`);
        }
      } catch (err) {
        this.showToast(err.message || String(err), 'error');
      }
    },

    async saveFile() {
      if (!this.selectedPath || !this.dirty || this.saving) return;
      this.saving = true;
      try {
        const res = await fetch(this.themeUrl('/file'), {
          method: 'PUT',
          headers: window.AUTH.getHeaders(),
          body: JSON.stringify({
            path: this.selectedPath,
            content: this.content,
          }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(this.apiDetail(data, res.status));
        }
        this.savedContent = this.content;
        this.showToast(`Saved ${this.selectedPath}`);
      } catch (err) {
        this.showToast(err.message || String(err), 'error');
      } finally {
        this.saving = false;
      }
    },

    resetFile() {
      if (!this.context.exists || !this.selectedPath || this.resettingFile) return;
      this.resetFileModalOpen = true;
    },

    async confirmResetFile() {
      if (!this.context.exists || !this.selectedPath || this.resettingFile) return;
      const path = this.selectedPath;
      this.resettingFile = true;
      try {
        const res = await fetch(this.themeUrl('/reset-file'), {
          method: 'POST',
          headers: window.AUTH.getHeaders(),
          body: JSON.stringify({ path }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(this.apiDetail(data, res.status));
        }
        this.showToast(
          data.hint || `Restored ${path} from ${data.parent || 'parent'}`
        );
        await this.openFile(path, { skipDirtyCheck: true });
      } catch (err) {
        this.showToast(err.message || String(err), 'error');
      } finally {
        this.resettingFile = false;
        this.resetFileModalOpen = false;
      }
    },

    async validateTheme() {
      if (!this.context.exists || this.validating) return;
      this.validating = true;
      try {
        const res = await fetch(this.themeUrl('/validate'), {
          method: 'POST',
          headers: window.AUTH.getHeaders(),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(this.apiDetail(data, res.status));
        }
        this.validateResult = data;
        const errN = data.error_count || 0;
        const warnN = data.warning_count || 0;
        if (data.ok) {
          this.showToast(
            warnN > 0
              ? `Theme OK (${warnN} warning${warnN === 1 ? '' : 's'})`
              : 'Theme OK'
          );
        } else {
          this.showToast(
            `${errN} error${errN === 1 ? '' : 's'}` +
              (warnN ? `, ${warnN} warning${warnN === 1 ? '' : 's'}` : ''),
            'error'
          );
        }
      } catch (err) {
        this.validateResult = null;
        this.showToast(err.message || String(err), 'error');
      } finally {
        this.validating = false;
      }
    },

    // ── Reset / Delete ───────────────────────────────────────────────
    resetTheme() {
      if (!this.context.exists || this.resetting) return;
      this.resetModalOpen = true;
    },

    async confirmResetTheme() {
      if (!this.context.exists || this.resetting) return;
      this.resetting = true;
      try {
        const res = await fetch(this.themeUrl('/reset'), {
          method: 'POST',
          headers: window.AUTH.getHeaders(),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(this.apiDetail(data, res.status));
        }
        this.showToast(`Reset from ${data.parent || this.context.parent || 'parent'}`);
        const keepPath = this.selectedPath;
        this.content = '';
        this.savedContent = '';
        await this.loadContext();
        await this.loadTree({ autoOpen: false });
        const filePaths = (this.files || []).map((f) => (typeof f === 'string' ? f : f.path));
        if (keepPath && filePaths.includes(keepPath)) {
          await this.openFile(keepPath, { skipDirtyCheck: true });
        } else {
          this.closeFile({ skipDirtyCheck: true });
        }
      } catch (err) {
        this.showToast(err.message || String(err), 'error');
      } finally {
        this.resetting = false;
        this.resetModalOpen = false;
      }
    },

    deleteCustom() {
      if (!this.context.exists || this.deleting) return;
      this.deleteModalOpen = true;
    },

    async confirmDeleteCustom() {
      if (!this.context.exists || this.deleting) return;
      this.deleting = true;
      try {
        const res = await fetch(this.themeUrl(''), {
          method: 'DELETE',
          headers: window.AUTH.getHeaders(),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(this.apiDetail(data, res.status));
        }
        const reverted = data.reverted_theme || data.parent;
        this.showToast(
          reverted
            ? `Custom theme deleted. Site theme reverted to ${reverted}.`
            : 'Custom theme deleted.'
        );
        this.validateResult = null;
        this.clearEditor();
        if (Alpine.store('app') && typeof Alpine.store('app').loadSites === 'function') {
          await Alpine.store('app').loadSites();
        }
        await this.loadContext();
      } catch (err) {
        this.showToast(err.message || String(err), 'error');
      } finally {
        this.deleting = false;
        this.deleteModalOpen = false;
      }
    },

    // ── Toasts ───────────────────────────────────────────────────────
    showToast(message, type = 'success') {
      const id = ++this.toastCounter;
      this.toasts.push({ id, message, type });
      setTimeout(() => {
        this.toasts = this.toasts.filter((t) => t.id !== id);
      }, 4000);
    },

    // ── Workspace prefs / resize ─────────────────────────────────────
    saveWorkspacePrefs() {
      try {
        localStorage.setItem(
          'pen_editor_workspace_prefs',
          JSON.stringify(this.workspacePrefs)
        );
        const html = document.documentElement;
        html.classList.toggle(
          'pref-left-collapsed',
          !!this.workspacePrefs.leftColumnCollapsed
        );
        html.classList.toggle(
          'pref-right-collapsed',
          !!this.workspacePrefs.rightColumnCollapsed
        );
        html.classList.toggle(
          'pref-secondary-rail-collapsed',
          !!this.workspacePrefs.secondaryRailCollapsed
        );
      } catch (_e) {
        /* ignore */
      }
    },

    startResizeLeft(e) {
      e.preventDefault();
      this.isDraggingLeftColumn = true;

      const startX = e.clientX;
      const startWidthPct = this.workspacePrefs.sidebarWidth || 32;
      const containerWidth = e.currentTarget.parentElement.clientWidth;

      document.body.style.cursor = 'ew-resize';
      document.body.style.userSelect = 'none';
      document.body.style.webkitUserSelect = 'none';

      const onMouseMove = (moveEvent) => {
        const deltaPct = ((moveEvent.clientX - startX) / containerWidth) * 100;
        let newPct = startWidthPct + deltaPct;
        if (newPct < 10) newPct = 10;
        if (newPct > 40) newPct = 40;
        this.workspacePrefs.sidebarWidth = Math.round(newPct * 10) / 10;
      };

      const onMouseUp = () => {
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        document.body.style.webkitUserSelect = '';
        this.isDraggingLeftColumn = false;
        this.saveWorkspacePrefs();
      };

      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    },

    startResizeRight(e) {
      e.preventDefault();
      this.isDraggingRightColumn = true;

      const startX = e.clientX;
      const startWidthPct = this.workspacePrefs.rightColumnWidth || 25;
      const containerWidth = e.currentTarget.parentElement.clientWidth;

      document.body.style.cursor = 'ew-resize';
      document.body.style.userSelect = 'none';
      document.body.style.webkitUserSelect = 'none';

      const onMouseMove = (moveEvent) => {
        const deltaPct = ((moveEvent.clientX - startX) / containerWidth) * 100;
        let newPct = startWidthPct - deltaPct;
        if (newPct < 10) newPct = 10;
        if (newPct > 40) newPct = 40;
        this.workspacePrefs.rightColumnWidth = Math.round(newPct * 10) / 10;
      };

      const onMouseUp = () => {
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        document.body.style.webkitUserSelect = '';
        this.isDraggingRightColumn = false;
        this.saveWorkspacePrefs();
      };

      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
    },
  }));
});
