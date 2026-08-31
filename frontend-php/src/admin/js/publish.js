/**
 * PenCMS Publish page — Settings form + Publish empty/connected states + deploy run.
 * SFTP password: ZK vault ``PUBLISH_SFTP_PASS:{siteId}``.
 * GitHub Pages PAT: ZK vault ``PUBLISH_GITHUB_TOKEN:{siteId}``.
 * Other adapters: vault key + HTTP alias come from GET /publish/providers.
 * SFTP key auth: install Ed25519 via /api/storage/ssh-key (no vault publish secret).
 */
document.addEventListener("alpine:init", () => {
  Alpine.data("publishPage", () => ({
    activeTab: "publish",
    loading: true,
    saving: false,
    testing: false,

    // Target from GET /api/publish/target
    configured: false,
    provider: "sftp",
    _prevProvider: "sftp",
    providerOptions: [{ id: "sftp", label: "SFTP", enabled: true }],
    host: "",
    port: 22,
    username: "",
    remote_path: "",
    public_url: "",
    webhook_url: "",
    webhook_secret: "",
    has_webhook_secret: false,
    _clearWebhookSecret: false,
    showWebhooks: false,
    schemaValues: {},
    github_owner: "",
    github_repo: "",
    github_pages_branch: "gh-pages",
    github_pages_cname: "",
    auth_method: "password",
    last_published_at: null,
    last_status: null,

    // Vault secret draft (never sent in PUT body)
    password: "",
    hasPassword: false,

    // Install SSH key (shared with Storage; no second keystore)
    sshKeyExists: false,
    sshPublicKey: "",
    sshKeyLoading: false,
    generatingKey: false,
    copiedKey: false,
    sshKeyError: "",

    // Status feedback
    saveStatus: null, // success | error
    saveMessage: "",
    testStatus: null, // testing | success | error
    testMessage: "",

    // Publish run / poll
    publishing: false,
    forceFullUpload: false,
    publishStatus: null, // null | running | success | error
    publishPhase: null, // building | uploading | done
    publishTaskId: null,
    publishLog: [],
    publishError: "",
    publishHint: "",
    publishMessage: "",
    _pollTimer: null,
    _pollSiteId: null,
    _pollFailures: 0,

    // Export zip download (S16)
    exporting: false,
    exportStatus: null, // null | success | error
    exportMessage: "",
    exportError: "",

    // Export streaming pipeline (inlined from admin-export)
    exportBuilding: false,
    exportBuildStarted: false,
    exportBuildDomain: "",
    exportBuildScope: "active", // active | all
    exportBuildStatus: null, // null | active | complete | failed | error
    exportBuildExitCode: null,

    // Vault unlock modal
    showVaultModal: false,
    vaultPassword: "",
    vaultError: "",
    vaultLocked: true,
    _pendingAction: null, // 'save' | 'test' | 'publish' | 'enroll'

    // Deploy Grant (agentic)
    grantEnrolled: false,
    grantHasCiphertext: false,
    grantBusy: false,
    grantMessage: "",
    grantMessageOk: false,

    get siteId() {
      return (this.$store.app && this.$store.app.activeSiteId) || "default";
    },

    get canHostPublish() {
      return !!(this.$store.app && this.$store.app.hasCap("publish"));
    },

    /** Registry domain for the active Content site (host only), or empty. */
    get activeSiteDomain() {
      const sites = (this.$store.app && this.$store.app.sites) || [];
      const active = sites.find((s) => s.id === this.siteId);
      const raw = active && active.domain ? String(active.domain).trim() : "";
      if (!raw) return "";
      return raw.replace(/^https?:\/\//i, "").split("/")[0] || "";
    },

    get isGithubPages() {
      return this.provider === "github_pages";
    },

    get isSftp() {
      return this.provider === "sftp";
    },

    get activeProviderOption() {
      return this.providerOptions.find((p) => p.id === this.provider) || null;
    },

    get schemaFields() {
      const schema =
        this.activeProviderOption && this.activeProviderOption.ui_schema;
      return (schema && schema.fields) || [];
    },

    get secretSchema() {
      const schema =
        this.activeProviderOption && this.activeProviderOption.ui_schema;
      return (schema && schema.secret) || {};
    },

    /** Provider label for UI copy (matches /providers registry). */
    get providerDisplayLabel() {
      const fromOpts = this.activeProviderOption;
      if (fromOpts && fromOpts.label) return fromOpts.label;
      if (this.provider === "sftp") return "SFTP";
      if (this.provider === "github_pages") return "GitHub Pages";
      return "this host";
    },

    get deployGrantHeading() {
      return `Allow agents to publish to ${this.providerDisplayLabel}`;
    },

    get isTokenHost() {
      const caps =
        (this.activeProviderOption && this.activeProviderOption.capabilities) ||
        {};
      const methods = caps.auth_methods || [];
      return methods.indexOf("token") !== -1 && methods.indexOf("password") === -1;
    },

    /** Short label for the vault secret (UI copy). */
    get tokenSecretLabel() {
      return this.secretSchema.label || (this.isSftp ? "SFTP password" : "API token");
    },

    get secretHelp() {
      return this.secretSchema.help || "";
    },

    get secretPlaceholder() {
      return this.secretSchema.placeholder || "Enter secret";
    },

    get secretCreateUrl() {
      return this.secretSchema.create_url || "";
    },

    get secretCreateLabel() {
      return this.secretSchema.create_label || "Create token";
    },

    get secretCreateHint() {
      return this.secretSchema.create_hint || "";
    },

    get secretCreateHost() {
      const url = this.secretCreateUrl || "";
      return url.replace(/^https?:\/\//i, "");
    },

    get publicUrlHelp() {
      const schema =
        this.activeProviderOption && this.activeProviderOption.ui_schema;
      if (schema && schema.public_url_help) return schema.public_url_help;
      if (this.isGithubPages) {
        return "Usually filled after the first successful GitHub Pages publish.";
      }
      return "Optional. Use the URL visitors should open after you publish to this host.";
    },

    get publicUrlPlaceholder() {
      if (this.isGithubPages) {
        return "https://owner.github.io/repo/ (filled after publish)";
      }
      if (this.isSftp) return "https://example.com";
      return "https://… (filled after publish)";
    },

    get publicUrlHint() {
      if (this.isSftp) return "Optional live site URL shown on the Publish tab.";
      if (this.isGithubPages) {
        return "Leave blank until the first GitHub Pages publish fills it, unless you already use a custom domain.";
      }
      return "Leave blank until the first deploy fills it, unless you already use a custom domain.";
    },

    get displayLastPublished() {
      if (this.last_published_at) return this.last_published_at;
      return "never";
    },

    get displayLiveUrl() {
      return this.public_url || "";
    },

    get displayLastStatus() {
      if (!this.last_status) return "";
      return this.last_status;
    },

    get publishPhaseLabel() {
      if (this.publishStatus === "success") return "Complete";
      if (this.publishStatus === "error") return "Failed";
      if (this.publishPhase === "building") return "Building…";
      if (this.publishPhase === "uploading") return "Uploading…";
      if (this.publishing) return "Starting…";
      return "";
    },

    /** True when a vault secret is required (SFTP password or platform API token). */
    get usesPasswordAuth() {
      if (this.isTokenHost) return true;
      return this.auth_method !== "key";
    },

    vaultKey() {
      const opt = this.activeProviderOption;
      const template = opt && opt.vault_key;
      if (template) return String(template).replace("{site}", this.siteId);
      if (this.isGithubPages) return "PUBLISH_GITHUB_TOKEN:" + this.siteId;
      return "PUBLISH_SFTP_PASS:" + this.siteId;
    },

    _clearProviderFields() {
      const next = {};
      this.schemaFields.forEach((field) => {
        next[field.name] = "";
      });
      this.schemaValues = next;
      this.github_owner = "";
      this.github_repo = "";
      this.github_pages_branch = "gh-pages";
      this.github_pages_cname = "";
    },

    async init() {
      this.$watch(
        () => this.$store.app.activeSiteId,
        async (next, prev) => {
          if (!next || next === prev) return;
          await this.loadTarget();
          this.syncExportBuildDomain();
        }
      );
      this.$watch("activeTab", (tab) => {
        if (tab === "settings" && this.auth_method === "key" && this.isSftp) {
          this.loadSSHKey();
        }
      });
      this.$watch("auth_method", (method) => {
        if (method === "key" && this.isSftp) this.loadSSHKey();
      });
      this.$watch("exportBuildScope", () => this.syncExportBuildDomain());
      this.$watch(
        () => this.activeSiteDomain,
        () => {
          if (this.exportBuildScope === "active") this.syncExportBuildDomain();
        }
      );

      this._watchVault();
      await this.loadProviders();
      await this.loadTarget();
      this.syncExportBuildDomain();
    },

    /**
     * Prefill Target Domain from the active site registry when scope is
     * "Active Content site"; clear it for "All sites".
     */
    syncExportBuildDomain() {
      if (this.exportBuilding) return;
      if (this.exportBuildScope === "active") {
        this.exportBuildDomain = this.activeSiteDomain || "";
      } else {
        this.exportBuildDomain = "";
      }
    },

    async loadProviders() {
      try {
        const data = await window.api.getPublishProviders();
        const list = (data && data.providers) || [];
        if (list.length) {
          this.providerOptions = list;
        }
        const bindings = [];
        this.providerOptions.forEach((p) => {
          if (p && p.http_alias && p.vault_key) {
            bindings.push({ alias: p.http_alias, keyTemplate: p.vault_key });
          }
        });
        if (window.AUTH) {
          window.AUTH.vaultHeaderBindings = bindings;
        }
      } catch (err) {
        console.error("Failed to load publish providers:", err);
        this.providerOptions = [{ id: "sftp", label: "SFTP", enabled: true }];
      }
      if (!this.provider) this.provider = "sftp";
    },

    onProviderChange() {
      const selected = this.providerOptions.find((p) => p.id === this.provider);
      if (selected && !selected.enabled) {
        this.provider = this._prevProvider || "sftp";
        return;
      }
      const prev = this._prevProvider || "sftp";
      const next = this.provider || "sftp";
      if (next !== prev) {
        // Host-specific: a prior public_url must not look like it belongs
        // to the newly selected provider.
        this.public_url = "";
        this._clearProviderFields();
        if (this.isTokenHost) {
          this.auth_method = "token";
        } else if (this.auth_method === "token") {
          this.auth_method = "password";
        }
        this.password = "";
        this._syncPasswordFromVault();
        this.testStatus = null;
        this.testMessage = "";
        this.saveStatus = null;
        this.saveMessage = "";
      }
      this._prevProvider = next;
    },

    _watchVault() {
      const check = () => {
        if (window.VAULT && window.VAULT.unlocked) {
          this.vaultLocked = false;
          this._syncPasswordFromVault();
        } else {
          this.vaultLocked = true;
          setTimeout(check, 200);
        }
      };
      check();
    },

    _syncPasswordFromVault() {
      if (!window.VAULT || !window.VAULT.unlocked) {
        this.hasPassword = false;
        return;
      }
      const existing = window.VAULT.getSecret(this.vaultKey());
      this.hasPassword = !!existing;
      if (existing && !this.password) {
        this.password = existing;
      }
    },

    setAuthMethod(method) {
      if (this.isTokenHost) {
        this.auth_method = "token";
        return;
      }
      this.auth_method = method === "key" ? "key" : "password";
      this.testStatus = null;
      this.testMessage = "";
      if (this.auth_method === "key") {
        this.loadSSHKey();
      }
    },

    async loadSSHKey() {
      this.sshKeyLoading = true;
      this.sshKeyError = "";
      try {
        const result = await window.api.getSSHKey();
        this.sshKeyExists = !!(result && result.exists);
        this.sshPublicKey = (result && result.public_key
          ? result.public_key
          : ""
        ).trim();
      } catch (err) {
        this.sshKeyExists = false;
        this.sshPublicKey = "";
        this.sshKeyError = err.message || "Failed to load SSH key";
      } finally {
        this.sshKeyLoading = false;
      }
    },

    async generateSSHKey() {
      if (this.generatingKey || !this.canHostPublish) return;
      this.generatingKey = true;
      this.sshKeyError = "";
      try {
        const result = await window.api.generateSSHKey();
        this.sshKeyExists = true;
        this.sshPublicKey = (result && result.public_key
          ? result.public_key
          : ""
        ).trim();
      } catch (err) {
        this.sshKeyError = err.message || "Failed to generate SSH key";
      } finally {
        this.generatingKey = false;
      }
    },

    copyPublicKey() {
      if (!this.sshPublicKey) return;
      navigator.clipboard.writeText(this.sshPublicKey);
      this.copiedKey = true;
      setTimeout(() => {
        this.copiedKey = false;
      }, 2000);
    },

    applyTarget(data) {
      this.configured = !!(data && data.configured);
      this.provider = (data && data.provider) || "sftp";
      this._prevProvider = this.provider;
      this.host = (data && data.host) || "";
      this.port = data && data.port != null ? data.port : 22;
      this.username = (data && data.username) || "";
      this.remote_path = (data && data.remote_path) || "";
      this.public_url = (data && data.public_url) || "";
      this.webhook_url = (data && data.webhook_url) || "";
      this.has_webhook_secret = !!(data && data.has_webhook_secret);
      this.webhook_secret = "";
      this._clearWebhookSecret = false;
      const next = {};
      this.schemaFields.forEach((field) => {
        next[field.name] = (data && data[field.name]) || "";
      });
      this.schemaValues = next;
      this.github_owner = (data && data.github_owner) || "";
      this.github_repo = (data && data.github_repo) || "";
      this.github_pages_branch =
        (data && data.github_pages_branch) || "gh-pages";
      this.github_pages_cname = (data && data.github_pages_cname) || "";
      const am = data && data.auth_method;
      if (this.isTokenHost || this.isGithubPages) {
        this.auth_method = "token";
      } else if (am === "key") {
        this.auth_method = "key";
      } else {
        this.auth_method = "password";
      }
      this.last_published_at =
        data && data.last_published_at != null ? data.last_published_at : null;
      this.last_status =
        data && data.last_status != null ? data.last_status : null;
      if (data && data.configured && data.agent_publish === "enrolled") {
        this.grantEnrolled = true;
      } else {
        this.grantEnrolled = false;
      }
    },

    resetFormForEmpty() {
      this.configured = false;
      this.provider = "sftp";
      this._prevProvider = "sftp";
      this.host = "";
      this.port = 22;
      this.username = "";
      this.remote_path = "";
      this.public_url = "";
      this.webhook_url = "";
      this.webhook_secret = "";
      this.has_webhook_secret = false;
      this._clearWebhookSecret = false;
      this.showWebhooks = false;
      this.schemaValues = {};
      this.github_owner = "";
      this.github_repo = "";
      this.github_pages_branch = "gh-pages";
      this.github_pages_cname = "";
      this.auth_method = "password";
      this.last_published_at = null;
      this.last_status = null;
      this.password = "";
      this.hasPassword = false;
      this.grantEnrolled = false;
      this.grantHasCiphertext = false;
      this.grantMessage = "";
    },

    async loadGrantStatus() {
      if (!this.configured) {
        this.grantEnrolled = false;
        this.grantHasCiphertext = false;
        return;
      }
      try {
        const g = await window.api.getPublishGrant(this.siteId);
        this.grantEnrolled = !!(g && g.enrolled);
        this.grantHasCiphertext = !!(g && g.has_ciphertext);
      } catch (err) {
        console.error("Failed to load publish grant:", err);
      }
    },

    async enrollGrant() {
      if (this.grantBusy || this.grantEnrolled || !this.canHostPublish) return;
      this.grantMessage = "";
      this.grantMessageOk = false;
      if (this.usesPasswordAuth) {
        const draft = (this.password || "").trim();
        const inVault =
          window.VAULT &&
          window.VAULT.unlocked &&
          window.VAULT.getSecret(this.vaultKey());
        if (!draft && !inVault) {
          if (this.vaultLocked) {
            this._pendingAction = "enroll";
            this.vaultPassword = "";
            this.vaultError = "";
            this.showVaultModal = true;
            return;
          }
          this.grantMessage =
            "Enter the " +
            this.tokenSecretLabel +
            " (or unlock vault with a saved secret) before enrolling.";
          this.grantMessageOk = false;
          return;
        }
        if (this.vaultLocked && draft) {
          // Draft password alone is enough — no vault unlock required for enroll body.
        } else if (!draft && this.vaultLocked) {
          this._pendingAction = "enroll";
          this.vaultPassword = "";
          this.vaultError = "";
          this.showVaultModal = true;
          return;
        }
      }
      await this.proceedWithEnroll();
    },

    async proceedWithEnroll() {
      if (this.grantBusy) return;
      this.grantBusy = true;
      this.grantMessage = "";
      try {
        let password = null;
        if (this.usesPasswordAuth) {
          password = (this.password || "").trim() || null;
          if (!password && window.VAULT && window.VAULT.unlocked) {
            // Header X-Vault-Publish-Pass is sent by AUTH.getHeaders(); body optional.
            password = null;
          }
          if (
            !password &&
            !(
              window.VAULT &&
              window.VAULT.unlocked &&
              window.VAULT.getSecret(this.vaultKey())
            )
          ) {
            throw new Error(
              "SFTP password required to enroll (enter it or unlock vault)."
            );
          }
        }
        const result = await window.api.enrollPublishGrant(
          this.siteId,
          password || undefined
        );
        this.grantEnrolled = !!(result && result.enrolled);
        this.grantHasCiphertext = !!(result && result.has_ciphertext);
        this.grantMessage = this.grantEnrolled
          ? "Deploy Grant enrolled. Agents with publish scope can deploy."
          : "Enroll did not complete.";
        this.grantMessageOk = this.grantEnrolled;
        if (this.password) this.password = "";
      } catch (err) {
        this.grantMessage = err.message || "Failed to enroll Deploy Grant";
        this.grantMessageOk = false;
      } finally {
        this.grantBusy = false;
      }
    },

    async revokeGrant() {
      if (this.grantBusy || !this.grantEnrolled || !this.canHostPublish) return;
      if (
        !confirm(
          "Revoke the Deploy Grant for this site? Agents will no longer be able to publish to this host (agent keys are unchanged)."
        )
      ) {
        return;
      }
      this.grantBusy = true;
      this.grantMessage = "";
      try {
        const result = await window.api.revokePublishGrant(this.siteId);
        this.grantEnrolled = !!(result && result.enrolled);
        this.grantHasCiphertext = !!(result && result.has_ciphertext);
        this.grantMessage = "Deploy Grant revoked.";
        this.grantMessageOk = true;
      } catch (err) {
        this.grantMessage = err.message || "Failed to revoke Deploy Grant";
        this.grantMessageOk = false;
      } finally {
        this.grantBusy = false;
      }
    },

    _resetPublishUi() {
      this._stopPoll();
      this.publishing = false;
      this.publishStatus = null;
      this.publishPhase = null;
      this.publishTaskId = null;
      this.publishLog = [];
      this.publishError = "";
      this.publishHint = "";
      this.publishMessage = "";
      this._pollSiteId = null;
      this._pollFailures = 0;
    },

    _stopPoll() {
      if (this._pollTimer != null) {
        clearTimeout(this._pollTimer);
        this._pollTimer = null;
      }
    },

    _scrollPublishLog() {
      this.$nextTick(() => {
        const el = this.$refs.publishLogPre;
        if (el) el.scrollTop = el.scrollHeight;
      });
    },

    _applyStatusPayload(data) {
      if (!data) return;
      if (data.status && data.status !== "idle") {
        this.publishStatus = data.status;
      }
      this.publishPhase = data.phase != null ? data.phase : this.publishPhase;
      if (Array.isArray(data.log)) {
        this.publishLog = data.log.slice();
        this._scrollPublishLog();
      }
      if (data.error) {
        this._setPublishFailure(data.error);
      }
      if (data.last_published_at != null) {
        this.last_published_at = data.last_published_at;
      }
      if (data.last_status != null) {
        this.last_status = data.last_status;
      }
    },

    _isBusyError(message) {
      const msg = (message || "").toLowerCase();
      return msg.includes("already running") || msg.includes("publish already");
    },

    _formatPublishHint(message) {
      const msg = (message || "").toLowerCase();
      if (!msg) {
        return "Check Settings, run Test Connection, or use Export for a local build.";
      }
      if (
        msg.includes("password") ||
        msg.includes("vault") ||
        msg.includes("api key") ||
        msg.includes("permission denied") ||
        msg.includes("authentication") ||
        msg.includes("unauthorized")
      ) {
        if (this.isTokenHost) {
          const hint = this.activeProviderOption &&
            this.activeProviderOption.ui_schema &&
            this.activeProviderOption.ui_schema.auth_hint;
          return (
            hint ||
            "Unlock the vault, confirm the API token in Settings, then Test Connection."
          );
        }
        if (this.isGithubPages) {
          return "Unlock the vault, confirm the GitHub PAT in Settings, then Test Connection.";
        }
        if (this.auth_method === "key") {
          return "Confirm the install public key is in the host’s authorized_keys, then Test Connection in Settings.";
        }
        return "Unlock the vault, confirm the SFTP password in Settings, then Test Connection.";
      }
      if (
        msg.includes("timed out") ||
        msg.includes("timeout") ||
        msg.includes("connection refused") ||
        msg.includes("no route") ||
        msg.includes("could not resolve") ||
        msg.includes("name or service not known")
      ) {
        return "Check host, port, and network reachability in Settings, then Test Connection.";
      }
      if (msg.includes("build.sh") || msg.includes("exited with code")) {
        return "The static build failed. Fix build errors (see log), or use Export to debug locally.";
      }
      if (msg.includes("lost connection") || msg.includes("poll")) {
        return "Refresh the page to reattach if a run is still in progress.";
      }
      if (msg.includes("already running")) {
        return "A publish is already in progress for this site — watching that run.";
      }
      if (this.auth_method === "key") {
        return "Try Test Connection in Settings, or confirm authorized_keys. Export remains available.";
      }
      return "Try Test Connection in Settings. Export remains available for a local build.";
    },

    _setPublishFailure(message) {
      this.publishError = message || "Publish failed";
      this.publishHint = this._formatPublishHint(message);
    },

    _attachToRunning(data) {
      if (!data || data.status !== "running" || !data.task_id) return false;
      this.publishing = true;
      this.publishStatus = "running";
      this.publishTaskId = data.task_id;
      this.publishError = "";
      this.publishHint = "";
      this.publishMessage = "";
      this._pollFailures = 0;
      this._pollSiteId = this.siteId;
      this._applyStatusPayload(data);
      return true;
    },

    async _tryAttachRunning() {
      try {
        const data = await window.api.getPublishStatus(this.siteId);
        return this._attachToRunning(data);
      } catch (err) {
        console.error("Failed to check publish status on load:", err);
        return false;
      }
    },

    async loadTarget() {
      this._stopPoll();
      this.loading = true;
      this.saveStatus = null;
      this.saveMessage = "";
      this.testStatus = null;
      this.testMessage = "";
      this.password = "";
      let shouldPoll = false;
      try {
        const data = await window.api.getPublishTarget(this.siteId);
        this.applyTarget(data);
        this._syncPasswordFromVault();
        await this.loadGrantStatus();
        if (this.auth_method === "key") {
          await this.loadSSHKey();
        }
        shouldPoll = await this._tryAttachRunning();
        if (!shouldPoll) {
          this._resetPublishUi();
        }
      } catch (err) {
        console.error("Failed to load publish target:", err);
        this.resetFormForEmpty();
        this._resetPublishUi();
        this.saveStatus = "error";
        this.saveMessage = err.message || "Failed to load publish target";
        shouldPoll = false;
      } finally {
        this.loading = false;
      }
      // Resume poll after clearing the loading state so the hero stays interactive.
      if (shouldPoll) {
        await this._pollUntilDone();
      }
    },

    async save() {
      if (this.saving || !this.canHostPublish) return;
      this.saveStatus = null;
      this.saveMessage = "";
      if (this.usesPasswordAuth && this.password && this.vaultLocked) {
        this._pendingAction = "save";
        this.vaultPassword = "";
        this.vaultError = "";
        this.showVaultModal = true;
        return;
      }
      await this.proceedWithSave();
    },

    async proceedWithSave() {
      if (this.saving) return;
      this.saving = true;
      this.saveStatus = null;
      this.saveMessage = "";
      try {
        if (this.usesPasswordAuth && this.password) {
          if (!window.VAULT || !window.VAULT.unlocked) {
            throw new Error(
              "Unlock the vault to save the " + this.tokenSecretLabel + "."
            );
          }
          window.VAULT.setSecret(this.vaultKey(), this.password);
          await window.VAULT.save();
        }

        let payload;
        if (this.isGithubPages) {
          payload = {
            site: this.siteId,
            provider: "github_pages",
            auth_method: "token",
            github_owner: (this.github_owner || "").trim() || null,
            github_repo: (this.github_repo || "").trim() || null,
            github_pages_branch:
              (this.github_pages_branch || "").trim() || "gh-pages",
            github_pages_cname: (this.github_pages_cname || "").trim() || null,
            public_url: (this.public_url || "").trim() || null,
          };
        } else if (this.isSftp) {
          payload = {
            site: this.siteId,
            provider: this.provider || "sftp",
            host: (this.host || "").trim(),
            port: parseInt(this.port, 10) || 22,
            username: (this.username || "").trim(),
            remote_path: (this.remote_path || "").trim(),
            public_url: (this.public_url || "").trim() || null,
            auth_method: this.auth_method === "key" ? "key" : "password",
          };
        } else {
          payload = {
            site: this.siteId,
            provider: this.provider,
            auth_method: this.isTokenHost ? "token" : this.auth_method,
            public_url: (this.public_url || "").trim() || null,
          };
          this.schemaFields.forEach((field) => {
            const raw = (this.schemaValues[field.name] || "").trim();
            payload[field.name] = raw || null;
          });
        }
        payload.webhook_url = (this.webhook_url || "").trim() || null;
        if (this._clearWebhookSecret) {
          payload.webhook_secret = "";
        } else if ((this.webhook_secret || "").trim()) {
          payload.webhook_secret = (this.webhook_secret || "").trim();
        }

        const result = await window.api.updatePublishTarget(payload);
        this.applyTarget(result);
        this._syncPasswordFromVault();
        if (this.password) {
          this.password = "";
        }
        this.webhook_secret = "";
        this._clearWebhookSecret = false;
        this.saveStatus = "success";
        this.saveMessage = "Publish target saved.";
      } catch (err) {
        this.saveStatus = "error";
        this.saveMessage = err.message || "Failed to save publish target";
      } finally {
        this.saving = false;
      }
    },

    async testConnection() {
      if (this.testing || !this.canHostPublish) return;
      this.testStatus = null;
      this.testMessage = "";
      if (this.usesPasswordAuth && this.vaultLocked) {
        this._pendingAction = "test";
        this.vaultPassword = "";
        this.vaultError = "";
        this.showVaultModal = true;
        return;
      }
      await this.proceedWithTest();
    },

    async proceedWithTest() {
      if (this.testing) return;
      this.testing = true;
      this.testStatus = "testing";
      this.testMessage = "";
      this.saveStatus = null;
      this.saveMessage = "";
      try {
        if (this.usesPasswordAuth) {
          if (!window.VAULT || !window.VAULT.unlocked) {
            throw new Error("Unlock the vault to test the connection.");
          }
          // Ensure header picks up a freshly typed password before the request.
          if (this.password) {
            window.VAULT.setSecret(this.vaultKey(), this.password);
          }
          const existing = window.VAULT.getSecret(this.vaultKey());
          if (!existing) {
            throw new Error(
              "No " +
                this.tokenSecretLabel +
                " in vault. Enter one and Save, or type one before testing."
            );
          }
        }

        const result = await window.api.testPublish(this.siteId);
        if (result && result.success) {
          this.testStatus = "success";
          this.testMessage =
            result.latency_ms != null
              ? `Connected (${result.latency_ms}ms)`
              : "Connected";
          if (this.usesPasswordAuth) {
            this.hasPassword = true;
          }
        } else {
          this.testStatus = "error";
          this.testMessage =
            (result && result.error) || "Connection failed";
        }
      } catch (err) {
        this.testStatus = "error";
        this.testMessage = err.message || "Connection failed";
      } finally {
        this.testing = false;
      }
    },

    async startPublish() {
      if (!this.canHostPublish || !this.configured || this.publishing) return;
      this.publishError = "";
      this.publishHint = "";
      this.publishMessage = "";
      if (this.usesPasswordAuth && this.vaultLocked) {
        this._pendingAction = "publish";
        this.vaultPassword = "";
        this.vaultError = "";
        this.showVaultModal = true;
        return;
      }
      await this.proceedWithPublish();
    },

    async proceedWithPublish() {
      if (!this.configured || this.publishing) return;

      this.publishError = "";
      this.publishHint = "";
      this.publishMessage = "";
      this.publishLog = [];
      this.publishPhase = null;
      this.publishStatus = null;
      this.publishTaskId = null;

      if (this.usesPasswordAuth) {
        try {
          if (!window.VAULT || !window.VAULT.unlocked) {
            throw new Error("Unlock the vault to publish.");
          }
          if (this.password) {
            window.VAULT.setSecret(this.vaultKey(), this.password);
          }
          const existing = window.VAULT.getSecret(this.vaultKey());
          if (!existing) {
            throw new Error(
              "No " +
                this.tokenSecretLabel +
                " in vault. Enter one in Settings and Save, then try again."
            );
          }
        } catch (err) {
          this.publishStatus = "error";
          this._setPublishFailure(err.message || "Cannot start publish");
          return;
        }
      }

      this.publishing = true;
      this.publishStatus = "running";
      this._pollSiteId = this.siteId;
      this._pollFailures = 0;

      try {
        const started = await window.api.runPublish(this.siteId, {
          force_full: !!this.forceFullUpload,
        });
        this.publishTaskId = started && started.task_id ? started.task_id : null;
        if (!this.publishTaskId) {
          throw new Error("Publish started but no task_id was returned.");
        }
        await this._pollUntilDone();
      } catch (err) {
        const msg = err.message || "Publish failed to start";
        if (this._isBusyError(msg)) {
          try {
            const data = await window.api.getPublishStatus(this.siteId);
            if (this._attachToRunning(data)) {
              await this._pollUntilDone();
              return;
            }
          } catch (attachErr) {
            console.error("Failed to attach to running publish:", attachErr);
          }
        }
        this.publishStatus = "error";
        this._setPublishFailure(msg);
        this.publishing = false;
        this._stopPoll();
      }
    },

    _pollDelayMs() {
      // 800 → 1500 → 3000 → 5000 (cap)
      const steps = [800, 1500, 3000, 5000];
      const idx = Math.min(this._pollFailures, steps.length - 1);
      return steps[idx];
    },

    async _pollUntilDone() {
      const siteId = this._pollSiteId;
      const MAX_POLL_FAILURES = 5;

      const tick = async () => {
        if (this._pollSiteId !== siteId || this.siteId !== siteId) {
          return;
        }
        const taskId = this.publishTaskId;
        try {
          const data = await window.api.getPublishStatus(siteId, taskId);
          if (this._pollSiteId !== siteId) return;
          this._pollFailures = 0;
          this._applyStatusPayload(data);

          const status = data && data.status;
          if (status === "success" || status === "error") {
            this.publishing = false;
            this._stopPoll();
            if (status === "success") {
              this.publishMessage = "Published successfully.";
              this.publishError = "";
              this.publishHint = "";
            } else if (data && data.error) {
              this._setPublishFailure(data.error);
            }
            try {
              const fresh = await window.api.getPublishTarget(siteId);
              if (this.siteId === siteId) this.applyTarget(fresh);
            } catch (e) {
              console.error("Failed to refresh publish target after run:", e);
            }
            return;
          }

          this._pollTimer = setTimeout(tick, 800);
        } catch (err) {
          if (this._pollSiteId !== siteId) return;
          this._pollFailures += 1;
          if (this._pollFailures >= MAX_POLL_FAILURES) {
            this.publishStatus = "error";
            this._setPublishFailure(
              "Lost connection while checking publish status. Refresh the page — if a run is still going, you’ll reattach."
            );
            this.publishing = false;
            this._stopPoll();
            return;
          }
          this._pollTimer = setTimeout(tick, this._pollDelayMs());
        }
      };

      await tick();
    },

    async unlockVaultAndContinue() {
      this.vaultError = "";
      if (!this.vaultPassword) {
        this.vaultError = "Please enter your Master Password.";
        return;
      }
      try {
        await window.VAULT.unlock(this.vaultPassword);
        this.vaultLocked = false;
        this.showVaultModal = false;
        this.vaultPassword = "";
        const action = this._pendingAction;
        this._pendingAction = null;
        this._syncPasswordFromVault();
        if (action === "save") await this.proceedWithSave();
        else if (action === "test") await this.proceedWithTest();
        else if (action === "publish") await this.proceedWithPublish();
        else if (action === "enroll") await this.proceedWithEnroll();
      } catch (e) {
        this.vaultError = "Incorrect Master Password.";
      }
    },

    cancelVaultUnlock() {
      this.showVaultModal = false;
      this.vaultPassword = "";
      this.vaultError = "";
      this._pendingAction = null;
    },

    async downloadExportZip() {
      if (!this.canHostPublish || this.exporting || this.exportBuilding || this.publishing) return;
      this.exportStatus = null;
      this.exportMessage = "";
      this.exportError = "";
      this.exporting = true;
      try {
        // Content-storage vault headers (if unlocked) are sent via AUTH.getHeaders.
        const result = await window.api.downloadPublishExportZip(this.siteId);
        this.exportStatus = "success";
        this.exportMessage = result && result.filename
          ? `Download started: ${result.filename}`
          : "Download started.";
      } catch (err) {
        console.error("Export zip failed:", err);
        this.exportStatus = "error";
        this.exportError = (err && err.message) || "Export failed";
      } finally {
        this.exporting = false;
      }
    },

    async startExportBuild() {
      if (!this.canHostPublish || this.exportBuilding || this.exporting || this.publishing) return;

      this.exportBuilding = true;
      this.exportBuildStarted = true;
      this.exportBuildStatus = "active";
      this.exportBuildExitCode = null;

      await this.$nextTick();
      const output = this.$refs.exportBuildLogPre;
      if (output) {
        output.innerHTML = "";
        output.appendChild(document.createTextNode("Starting build process...\n"));
      }

      try {
        const secrets = window.VaultClient
          ? await window.VaultClient.getSecrets()
          : {};
        const headers = {};
        if (secrets && secrets.CONTENT_SFTP_PASS) {
          headers["X-Vault-Content-Pass"] = secrets.CONTENT_SFTP_PASS;
        }
        if (secrets && secrets.ASSETS_SFTP_PASS) {
          headers["X-Vault-Assets-Pass"] = secrets.ASSETS_SFTP_PASS;
        }

        const params = new URLSearchParams({
          ajax_build: "1",
          domain: this.exportBuildDomain || "",
        });
        if (this.exportBuildScope === "all" && this.$store.app.edition === "pro") {
          params.set("all_sites", "1");
        } else {
          params.set("site", this.siteId);
        }

        const response = await fetch("?" + params.toString(), { headers });
        if (!response.body) throw new Error("ReadableStream not supported");

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let done = false;

        while (!done) {
          const { value, done: readerDone } = await reader.read();
          done = readerDone;
          if (!value || !output) continue;

          let chunk = decoder.decode(value, { stream: true });
          chunk = chunk.replace(/ {4096}/g, "");

          if (chunk.includes("[PROCESS_EXIT:")) {
            const match = chunk.match(/\[PROCESS_EXIT:(\d+)\]/);
            if (match) {
              const code = match[1];
              this.exportBuildExitCode = code;
              this.exportBuildStatus = code === "0" ? "complete" : "failed";
              chunk = chunk.replace(/\[PROCESS_EXIT:\d+\]\n?/g, "");
            }
          }

          const lines = chunk.split("\n");
          for (let i = 0; i < lines.length; i++) {
            if (lines[i].startsWith("ERR: ")) {
              const span = document.createElement("span");
              span.className = "text-danger font-bold";
              span.appendChild(
                document.createTextNode(lines[i].substring(5) + "\n"),
              );
              output.appendChild(span);
            } else if (lines[i] !== "") {
              output.appendChild(document.createTextNode(lines[i] + "\n"));
            }
          }
          output.scrollTop = output.scrollHeight;
        }

        if (this.exportBuildStatus === "active") {
          this.exportBuildStatus = "complete";
        }
      } catch (e) {
        if (output) {
          output.appendChild(
            document.createTextNode("\nERR: Fetch Error: " + e.message + "\n"),
          );
          output.scrollTop = output.scrollHeight;
        }
        this.exportBuildStatus = "error";
      }

      this.exportBuilding = false;
    },
  }));
});
