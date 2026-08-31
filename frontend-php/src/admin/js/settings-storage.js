/**
 * PenCMS Storage Settings Logic (Stateless / Zero-Knowledge)
 */
document.addEventListener("alpine:init", () => {
  Alpine.data("storageSettings", () => ({
    loading: true,
    saving: false,
    activeTab: "content",

    availableProviders: ["local", "git"],
    contentProvider: "local",
    contentBasePath: "",
    contentPath: "",
    assetsProvider: "local",
    assetsBasePath: "",
    assetsPath: "",

    // Decomposed SSH fields
    contentSSH: { host: "", port: 22, username: "", path: "/" },
    assetsSSH: { host: "", port: 22, username: "", path: "/" },

    // Auth method
    contentAuthMethod: "key",
    assetsAuthMethod: "key",
    contentPassword: "",
    assetsPassword: "",
    contentHasPassword: false,
    assetsHasPassword: false,

    // Password visibility
    showContentPassword: false,
    showAssetsPassword: false,

    // SSH test state
    contentSSHStatus: null,
    contentSSHResult: "",
    assetsSSHStatus: null,
    assetsSSHResult: "",

    // SSH key state
    sshKeyExists: false,
    sshKeyPath: "",
    sshPublicKey: "",
    generatingKey: false,
    copiedKey: false,

    // Restart state
    restartRequired: false,
    restarting: false,

    // Modal state
    showVaultModal: false,
    vaultPassword: "",
    vaultError: "",
    showMessageModal: false,
    modalMessage: "",
    modalIsError: false,

    // Vault status
    vaultLocked: true,

    activeSite() {
      const store = Alpine.store("app");
      const id = store?.activeSiteId || "default";
      const site = (store?.sites || []).find((s) => s.id === id);
      const contentRelpath =
        (site && site.content_relpath) || `sites/${id}`;
      return { id, contentRelpath };
    },

    joinStoragePath(base, ...parts) {
      const root = String(base || "").replace(/\/+$/, "");
      const segments = parts
        .flat()
        .map((p) => String(p).replace(/^\/+|\/+$/g, ""))
        .filter(Boolean);
      if (!root) return segments.join("/");
      return segments.length ? `${root}/${segments.join("/")}` : root;
    },

    /** Strip multisite suffixes so config.ini keeps the install content root. */
    normalizeContentRoot(path) {
      const normalized = String(path || "").replace(/\/+$/, "");
      const withoutAssets = normalized.replace(/\/sites\/[^/]+\/assets$/, "");
      const withoutSite = withoutAssets.replace(/\/sites\/[^/]+$/, "");
      return withoutSite || normalized;
    },

    syncDisplayedPaths() {
      const { contentRelpath } = this.activeSite();
      if (!this.isSSH("content")) {
        this.contentPath = this.joinStoragePath(
          this.contentBasePath,
          contentRelpath
        );
      }
      if (!this.isSSH("assets")) {
        this.assetsPath = this.joinStoragePath(
          this.contentBasePath,
          contentRelpath,
          "assets"
        );
      }
    },

    async init() {
      try {
        const config = await window.api.getStorageConfig();

        this.availableProviders = config.available_providers || ["local", "git"];
        this.contentProvider = config.content.effective_provider;
        this.assetsProvider = config.assets.effective_provider;
        this.contentBasePath = this.normalizeContentRoot(config.content.path);
        this.assetsBasePath = config.assets.path;
        this.syncDisplayedPaths();

        this.contentAuthMethod = config.content.auth_method || "key";
        this.assetsAuthMethod = config.assets.auth_method || "key";

        if (config.content.ssh) this.contentSSH = { ...config.content.ssh };
        if (config.assets.ssh) this.assetsSSH = { ...config.assets.ssh };

        this.sshKeyExists = config.ssh_key_exists;
        this.sshKeyPath = config.ssh_key_path;

        this.$watch(
          () => Alpine.store("app").activeSiteId,
          () => this.syncDisplayedPaths()
        );

        // Sync with Vault
        const checkVault = () => {
          if (window.VAULT && window.VAULT.unlocked) {
            this.vaultLocked = false;
            const cp = window.VAULT.getSecret("CONTENT_SFTP_PASS");
            const ap = window.VAULT.getSecret("ASSETS_SFTP_PASS");
            if (cp) {
              this.contentHasPassword = true;
              if (!this.contentPassword) this.contentPassword = cp;
            }
            if (ap) {
              this.assetsHasPassword = true;
              if (!this.assetsPassword) this.assetsPassword = ap;
            }
          } else {
            setTimeout(checkVault, 200);
          }
        };
        checkVault();

        this.loading = false;
      } catch (err) {
        console.error("Failed to load storage config:", err);
      }
    },

    providerLabel(type) {
      return (
        {
          local: "Local Filesystem",
          git: "Git (Version-Controlled)",
          ssh: "Remote SSH",
        }[type] || type
      );
    },

    providerDescription(type) {
      return (
        {
          local:
            "Files stored on the local filesystem. Best for single-server setups.",
          git: "Local filesystem with automatic Git version history.",
          ssh: "Files stored on a remote server via SSH/SFTP. Credentials are kept in your Zero-Knowledge Vault.",
        }[type] || ""
      );
    },

    isSSH(target) {
      if (!this.availableProviders.includes("ssh")) return false;
      return (
        (target === "content" ? this.contentProvider : this.assetsProvider) ===
        "ssh"
      );
    },

    async testSSH(target) {
      const ssh = target === "content" ? this.contentSSH : this.assetsSSH;
      const statusKey =
        target === "content" ? "contentSSHStatus" : "assetsSSHStatus";
      const resultKey =
        target === "content" ? "contentSSHResult" : "assetsSSHResult";
      const pw =
        target === "content" ? this.contentPassword : this.assetsPassword;

      this[statusKey] = "testing";
      try {
        const payload = {
          host: ssh.host,
          port: parseInt(ssh.port) || 22,
          username: ssh.username,
          path: ssh.path || "/",
          auth_method:
            target === "content"
              ? this.contentAuthMethod
              : this.assetsAuthMethod,
          password: pw,
        };
        const result = await window.api.testSSH(payload);
        this[statusKey] = result.success ? "success" : "error";
        this[resultKey] = result.success
          ? `Connected (${result.latency_ms}ms)`
          : result.error;
      } catch (err) {
        this[statusKey] = "error";
        this[resultKey] = err.message;
      }
    },

    async save() {
      if (this.vaultLocked) {
        this.vaultPassword = "";
        this.vaultError = "";
        this.showVaultModal = true;
        return;
      }
      await this.proceedWithSave();
    },

    async unlockVaultAndSave() {
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
        await this.proceedWithSave();
      } catch (e) {
        this.vaultError = "Incorrect Master Password.";
      }
    },

    cancelVaultUnlock() {
      this.showVaultModal = false;
      this.vaultPassword = "";
      this.vaultError = "";
    },

    async proceedWithSave() {
      this.saving = true;
      try {
        // 1. Update Vault if passwords changed
        if (this.contentPassword)
          window.VAULT.setSecret("CONTENT_SFTP_PASS", this.contentPassword);
        if (this.assetsPassword)
          window.VAULT.setSecret("ASSETS_SFTP_PASS", this.assetsPassword);
        await window.VAULT.save();

        // 2. Update System Config (Stateless)
        const payload = {
          content_storage_type: this.contentProvider,
          assets_storage_type: this.assetsProvider,
          content_auth_method: this.contentAuthMethod,
          assets_auth_method: this.assetsAuthMethod,
        };

        if (this.contentProvider === "ssh") {
          payload.content_ssh = {
            ...this.contentSSH,
            port: parseInt(this.contentSSH.port) || 22,
          };
        } else {
          payload.content_dir = this.normalizeContentRoot(this.contentBasePath);
        }

        if (this.assetsProvider === "ssh") {
          payload.assets_ssh = {
            ...this.assetsSSH,
            port: parseInt(this.assetsSSH.port) || 22,
          };
        } else {
          payload.assets_dir = this.assetsBasePath;
        }

        const result = await window.api.updateStorageConfig(payload);
        this.restartRequired = result.restart_required;
        this.contentHasPassword = !!window.VAULT.getSecret("CONTENT_SFTP_PASS");
        this.assetsHasPassword = !!window.VAULT.getSecret("ASSETS_SFTP_PASS");

        this.modalMessage =
          "Storage settings saved. A service restart is required to apply changes.";
        this.modalIsError = false;
        this.showMessageModal = true;
      } catch (err) {
        this.modalMessage = "Failed to save: " + err.message;
        this.modalIsError = true;
        this.showMessageModal = true;
      } finally {
        this.saving = false;
      }
    },

    dismissMessageModal() {
      this.showMessageModal = false;
      this.modalMessage = "";
    },

    async restart() {
      this.restarting = true;
      try {
        await window.api.restartService();
        setTimeout(() => this.pollHealth(), 2000);
      } catch {
        setTimeout(() => this.pollHealth(), 2000);
      }
    },

    async pollHealth() {
      const poll = async () => {
        try {
          await window.api.healthCheck();
          window.location.reload();
        } catch {
          setTimeout(poll, 1000);
        }
      };
      poll();
    },

    async generateKey() {
      this.generatingKey = true;
      try {
        const result = await window.api.generateSSHKey();
        this.sshKeyExists = true;
        this.sshKeyPath = result.key_path;
        this.sshPublicKey = (result.public_key || "").trim();
      } catch (err) {
        this.modalMessage = err.message;
        this.modalIsError = true;
        this.showMessageModal = true;
      } finally {
        this.generatingKey = false;
      }
    },

    async loadPublicKey() {
      if (this.sshKeyExists && !this.sshPublicKey) {
        const result = await window.api.getSSHKey();
        this.sshPublicKey = (result.public_key || "").trim();
      }
    },

    copyPublicKey() {
      navigator.clipboard.writeText(this.sshPublicKey);
      this.copiedKey = true;
      setTimeout(() => (this.copiedKey = false), 2000);
    },

    setProvider(target, type) {
      if (target === "content") {
        this.contentProvider = type;
        if (type !== "ssh" && this.contentPath.includes("://")) {
          this.contentBasePath = "../pencms-data/content";
          this.syncDisplayedPaths();
        }
      } else {
        this.assetsProvider = type;
        if (type !== "ssh" && this.assetsPath.includes("://")) {
          this.assetsBasePath = "../pencms-data/assets";
          this.syncDisplayedPaths();
        }
      }
    },
  }));
});
