/**
 * PenCMS AI Settings Controller (settings-ai.js)
 */
const AI_PROVIDERS = {
  openai_compat: {
    label: "OpenAI-Compatible",
    defaultBaseUrl: "https://api.openai.com/v1",
    defaultModel: "gpt-5.5",
    requiresKey: true,
  },
  ollama: {
    label: "Ollama (Local)",
    defaultBaseUrl: "http://localhost:11434/v1",
    defaultModel: "qwen3",
    requiresKey: false,
  },
  groq: {
    label: "Groq",
    defaultBaseUrl: "https://api.groq.com/openai/v1",
    defaultModel: "openai/gpt-oss-120b",
    requiresKey: true,
  },
  together: {
    label: "Together AI",
    defaultBaseUrl: "https://api.together.xyz/v1",
    defaultModel: "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    requiresKey: true,
  },
  openrouter: {
    label: "OpenRouter",
    defaultBaseUrl: "https://openrouter.ai/api/v1",
    defaultModel: "openrouter/free",
    requiresKey: true,
  },
  custom: {
    label: "Custom",
    defaultBaseUrl: "",
    defaultModel: "",
    requiresKey: true,
  },
};

const IMAGE_PROVIDERS = {
  openai_compat: {
    label: "OpenAI-Compatible",
    defaultBaseUrl: "https://nano-gpt.com/v1/images/generations",
    defaultModel: "qwen-image",
    requiresKey: true,
  },
  nanogpt: {
    label: "NanoGPT",
    defaultBaseUrl: "https://nano-gpt.com/api/v1/images/generations",
    defaultModel: "nano-banana-2-lite",
    requiresKey: true,
  },
  ollama: {
    label: "Ollama (Local)",
    defaultBaseUrl: "http://localhost:11434/v1",
    defaultModel: "stable-diffusion",
    requiresKey: false,
  },
  custom: {
    label: "Custom",
    defaultBaseUrl: "",
    defaultModel: "",
    requiresKey: true,
  },
};

const KEY_SCOPE_PRESETS = {
  read: ["read"],
  writer: ["read", "write:posts", "write:pages", "write:media", "write:authors", "write:taxonomy"],
  editor: [
    "read",
    "write:posts",
    "write:pages",
    "write:media",
    "write:authors",
    "write:taxonomy",
    "delete:posts",
    "delete:pages",
    "delete:media",
    "publish:content",
    "write:seo",
  ],
  publisher: [
    "read",
    "write:posts",
    "write:pages",
    "write:media",
    "write:authors",
    "write:taxonomy",
    "delete:posts",
    "delete:pages",
    "delete:media",
    "publish:content",
    "write:seo",
    "publish",
  ],
  legacy_write: ["read", "write"],
  legacy_publish: ["read", "write", "publish"],
};

const SITE_SCOPED_AGENT_CAPS = [
  "read",
  "write",
  "write:posts",
  "delete:posts",
  "write:pages",
  "delete:pages",
  "write:media",
  "delete:media",
  "publish:content",
  "write:menus",
  "write:authors",
  "write:seo",
  "write:theme",
  "write:taxonomy",
  "publish",
];

document.addEventListener("alpine:init", () => {
  Alpine.data("aiSettings", () => ({
    AI_PROVIDERS,
    IMAGE_PROVIDERS,
    saving: false,
    savingVault: false,
    savingPromptSettings: false,
    savingUseAi: false,
    use_ai: false,
    activeTab: "permissions",
    toasts: [],
    toastCounter: 0,

    agentKeys: [],
    pendingApprovals: [],
    checkingPendingApprovals: false,
    sites: [],
    newlyGeneratedKey: null,
    newKeyName: "",
    newKeySiteId: "default",
    newKeyPreset: "read",
    newKeyScopes: ["read"],
    KEY_SCOPE_PRESETS,
    SITE_SCOPED_AGENT_CAPS,
    promptSettings: {
      textGenerationPrompt: "",
      imageGenerationPrompt: "",
      qualityChecklist: ""
    },

    // Revoke modal state
    showRevokeModal: false,
    keyToRevoke: null,
    keyNameToRevoke: "",

    // Vault state
    vaultUnlocked: false,
    showVaultPassword: false,
    unlockPassword: "",

    // AI Guardrails state
    guardrails: {
      publishAutonomy: "require_approval",
      metadataScope: "allow_metadata",
    },

    // AI Provider state
    aiConfig: {
      provider: "openai_compat",
      baseUrl: "https://api.openai.com/v1",
      apiKey: "",
      model: "gpt-4o",
    },

    // AI Image state
    aiImageConfig: {
      provider: "nanogpt",
      baseUrl: "https://nano-gpt.com/api/v1/images/generations",
      apiKey: "",
      model: "nano-banana-2-lite",
    },
    useSameApiKey: false,

    // Connection test state
    testingConnection: false,
    connectionSuccess: false,
    connectionMessage: "",

    testingImageConnection: false,
    connectionImageSuccess: false,
    connectionImageMessage: "",
    savingGuardrails: false,

    async init() {
      try {
        await this.loadUseAi();

        // Fetch sites + agent keys + pending bootstrap approvals
        await this.refreshSites();
        await this.refreshAgentKeys();
        await this.refreshPendingApprovals();
        await this.loadSiteAiSettings();

        this.$watch(
          () => this.$store.app.activeSiteId,
          async (next, prev) => {
            if (!next || next === prev) return;
            await this.loadSiteAiSettings();
          }
        );

        // Poll for vault unlock state
        const checkVault = () => {
          if (window.VAULT && window.VAULT.unlocked) {
            this.loadVaultData();
          } else {
            setTimeout(checkVault, 100);
          }
        };
        checkVault();

        // Watchers for key synchronization
        this.$watch("aiConfig.apiKey", (value) => {
          if (this.useSameApiKey) {
            this.aiImageConfig.apiKey = value;
          }
        });
        this.$watch("useSameApiKey", (value) => {
          if (value) {
            this.aiImageConfig.apiKey = this.aiConfig.apiKey;
          }
        });
      } catch (e) {
        console.warn("Could not fetch user/keys data", e);
      }
    },

    async loadUseAi() {
      try {
        const general = await window.api.getGeneralConfig();
        this.use_ai = general.use_ai === true;
        Alpine.store("app").use_ai = this.use_ai;
      } catch (e) {
        console.warn("Failed to load use_ai flag", e);
      }
    },

    async toggleUseAi() {
      if (this.savingUseAi) return;
      const next = !this.use_ai;
      this.savingUseAi = true;
      try {
        await window.api.updateGeneralConfig({ use_ai: next });
        this.use_ai = next;
        Alpine.store("app").use_ai = next;
        this.showToast(
          next ? "AI Integration enabled" : "AI Integration disabled",
        );
      } catch (e) {
        this.showToast(e.message || "Failed to update AI Integration", "error");
      } finally {
        this.savingUseAi = false;
      }
    },

    async loadSiteAiSettings() {
      try {
        const apiBase = window.AUTH.apiBase.replace("/v1", "");
        const settingsRes = await fetch(`${apiBase}/ai/settings`, {
          headers: window.AUTH.getHeaders(),
        });
        if (!settingsRes.ok) return;
        const settingsData = await settingsRes.json();
        this.guardrails.publishAutonomy =
          settingsData.ai_publish_autonomy || "require_approval";
        this.guardrails.metadataScope =
          settingsData.ai_metadata_scope || "allow_metadata";
        this.promptSettings.textGenerationPrompt =
          settingsData.text_generation_prompt || "";
        this.promptSettings.imageGenerationPrompt =
          settingsData.image_generation_prompt || "";
        this.promptSettings.qualityChecklist =
          settingsData.post_quality_checklist || "";
      } catch (e) {
        console.warn("Could not fetch per-site AI settings", e);
      }
    },

    async refreshAgentKeys() {
      try {
        const apiBase = window.AUTH.apiBase.replace("/v1", "");
        const keysRes = await fetch(`${apiBase}/auth/keys`, {
          headers: window.AUTH.getHeaders(),
        });
        if (keysRes.ok) {
          const keysData = await keysRes.json();
          const secrets = window.VAULT?.secrets || {};
          const vaultKeys = secrets.AGENT_KEYS || {};
          this.agentKeys = keysData.keys.map(k => ({
            ...k,
            displayKey: (window.VAULT?.unlocked && vaultKeys[k.name]) ? vaultKeys[k.name] : k.name
          }));
        }
      } catch (e) {
        console.warn("Could not fetch keys data", e);
      }
    },

    async refreshSites() {
      try {
        const apiBase = window.AUTH.apiBase.replace("/v1", "");
        const res = await fetch(`${apiBase}/sites`, {
          headers: window.AUTH.getHeaders(),
        });
        if (res.ok) {
          const data = await res.json();
          this.sites = data.sites || [];
          if (
            this.sites.length > 0 &&
            !this.sites.some((s) => s.id === this.newKeySiteId)
          ) {
            this.newKeySiteId = this.sites[0].id;
          }
        }
      } catch (e) {
        console.warn("Could not fetch sites", e);
      }
    },

    async refreshPendingApprovals({ notifyEmpty = false } = {}) {
      this.checkingPendingApprovals = true;
      try {
        const apiBase = window.AUTH.apiBase.replace("/v1", "");
        const res = await fetch(`${apiBase}/auth/agent/pending`, {
          headers: window.AUTH.getHeaders(),
        });
        if (res.ok) {
          const data = await res.json();
          this.pendingApprovals = data.pending || [];
          if (notifyEmpty && this.pendingApprovals.length === 0) {
            this.showToast("No pending approvals");
          }
        } else if (notifyEmpty) {
          this.showToast("Could not check pending approvals", "error");
        }
      } catch (e) {
        console.warn("Could not fetch pending approvals", e);
        if (notifyEmpty) {
          this.showToast("Could not check pending approvals", "error");
        }
      } finally {
        this.checkingPendingApprovals = false;
      }
    },

    async approveBootstrap(userCode, deny = false) {
      try {
        const apiBase = window.AUTH.apiBase.replace("/v1", "");
        const res = await fetch(`${apiBase}/auth/agent/approve`, {
          method: "POST",
          headers: window.AUTH.getHeaders(),
          body: JSON.stringify({ user_code: userCode, deny: !!deny }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail || "Failed to update approval");
        await this.refreshPendingApprovals();
        this.showToast(deny ? "Bootstrap request denied" : "Bootstrap request approved");
      } catch (e) {
        this.showToast(e.message || "Approval failed", "error");
      }
    },

    showToast(message, type = "success") {
      const id = ++this.toastCounter;
      this.toasts.push({ id, message, type });
      setTimeout(() => {
        this.toasts = this.toasts.filter((t) => t.id !== id);
      }, 4000);
    },

    loadVaultData() {
      const secrets = window.VAULT.secrets || {};
      if (secrets.AI_PROVIDER_CONFIG) {
        let config = secrets.AI_PROVIDER_CONFIG;
        if (typeof config === "string") {
          try {
            config = JSON.parse(config);
          } catch (e) {
            config = {};
          }
        }
        this.aiConfig = {
          provider: config.provider || "openai_compat",
          baseUrl: config.baseUrl || "",
          apiKey: config.apiKey || "",
          model: config.model || "",
        };
      } else {
        // defaults
        this.aiConfig = {
          provider: "openai_compat",
          baseUrl: "https://api.openai.com/v1",
          apiKey: "",
          model: "gpt-4o",
        };
      }
      this.connectionSuccess = false;
      this.connectionMessage = "";
      this.testingConnection = false;

      if (secrets.AI_IMAGE_CONFIG) {
        let imgConfig = secrets.AI_IMAGE_CONFIG;
        if (typeof imgConfig === "string") {
          try {
            imgConfig = JSON.parse(imgConfig);
          } catch (e) {
            imgConfig = {};
          }
        }
        this.aiImageConfig = {
          provider: imgConfig.provider || "openai_compat",
          baseUrl: imgConfig.baseUrl || "",
          apiKey: imgConfig.apiKey || "",
          model: imgConfig.model || "",
        };
        this.useSameApiKey = imgConfig.useSameApiKey || false;
      } else {
        // defaults
        this.aiImageConfig = {
          provider: "nanogpt",
          baseUrl: "https://nano-gpt.com/api/v1/images/generations",
          apiKey: "",
          model: "nano-banana-2-lite",
        };
        this.useSameApiKey = false;
      }
      this.connectionImageSuccess = false;
      this.connectionImageMessage = "";
      this.testingImageConnection = false;

      this.vaultUnlocked = true;
      this.refreshAgentKeys();
    },

    handleProviderChange() {
      this.connectionSuccess = false;
      this.connectionMessage = "";
      const providerInfo = AI_PROVIDERS[this.aiConfig.provider];
      if (providerInfo) {
        this.aiConfig.baseUrl = providerInfo.defaultBaseUrl;
        this.aiConfig.model = providerInfo.defaultModel;
        if (!providerInfo.requiresKey) {
          this.aiConfig.apiKey = "";
        } else {
          this.$nextTick(() => {
            const keyInput = document.getElementById("ai-api-key-input");
            if (keyInput) keyInput.focus();
          });
        }
      }
    },

    handleImageProviderChange() {
      this.connectionImageSuccess = false;
      this.connectionImageMessage = "";
      const providerInfo = IMAGE_PROVIDERS[this.aiImageConfig.provider];
      if (providerInfo) {
        this.aiImageConfig.baseUrl = providerInfo.defaultBaseUrl;
        this.aiImageConfig.model = providerInfo.defaultModel;
        if (!providerInfo.requiresKey) {
          this.aiImageConfig.apiKey = "";
        } else {
          this.$nextTick(() => {
            const keyInput = document.getElementById("ai-image-api-key-input");
            if (keyInput) keyInput.focus();
          });
        }
      }
    },

    async unlockVault(silent = false) {
      try {
        await window.VAULT.unlock(this.unlockPassword);
        this.loadVaultData();
        if (!silent) this.showToast("Vault unlocked successfully");
      } catch (e) {
        if (!silent) this.showToast(e.message, "error");
        this.unlockPassword = "";
      }
    },

    lockVault() {
      window.VAULT.lock();
      this.unlockPassword = "";
      this.vaultUnlocked = false;
      this.aiConfig = {
        provider: "openai_compat",
        baseUrl: "https://api.openai.com/v1",
        apiKey: "",
        model: "gpt-4o",
      };
      this.connectionSuccess = false;
      this.connectionMessage = "";
      this.testingConnection = false;

      this.aiImageConfig = {
        provider: "nanogpt",
        baseUrl: "https://nano-gpt.com/api/v1/images/generations",
        apiKey: "",
        model: "nano-banana-2-lite",
      };
      this.useSameApiKey = false;
      this.connectionImageSuccess = false;
      this.connectionImageMessage = "";
      this.testingImageConnection = false;
      this.refreshAgentKeys();
    },

    async testConnection() {
      if (this.testingConnection) return;
      this.testingConnection = true;
      this.connectionSuccess = false;
      this.connectionMessage = "";
      try {
        const apiBase = window.AUTH.apiBase.replace("/v1", "");

        // Construct transient test headers based on current unsaved fields
        const headers = { ...window.AUTH.getHeaders() };
        headers["X-Pen-AI-Key"] = this.aiConfig.apiKey || "";
        headers["X-Pen-AI-Base-URL"] = this.aiConfig.baseUrl || "";
        headers["X-Pen-AI-Model"] = this.aiConfig.model || "";

        const res = await fetch(`${apiBase}/ai/chat`, {
          method: "POST",
          headers: headers,
          body: JSON.stringify({
            messages: [{ role: "user", content: "Say OK" }],
            max_tokens: 5,
            stream: false,
          }),
        });

        if (res.ok) {
          this.connectionSuccess = true;
          this.connectionMessage = "Connection Successful!";
        } else {
          const data = await res
            .json()
            .catch(() => ({ detail: "Unknown error" }));
          this.connectionSuccess = false;
          this.connectionMessage = `Failed: ${data.detail || res.statusText}`;
        }
      } catch (e) {
        this.connectionSuccess = false;
        this.connectionMessage = `Error: ${e.message}`;
      } finally {
        this.testingConnection = false;
      }
    },

    async testImageConnection() {
      if (this.testingImageConnection) return;
      this.testingImageConnection = true;
      this.connectionImageSuccess = false;
      this.connectionImageMessage = "";
      try {
        const apiBase = window.AUTH.apiBase.replace("/v1", "");

        // Construct transient test headers based on current unsaved fields
        const headers = { ...window.AUTH.getHeaders() };
        const apiKeyToUse = this.useSameApiKey
          ? this.aiConfig.apiKey
          : this.aiImageConfig.apiKey;
        headers["X-Pen-AI-Key"] = apiKeyToUse || "";
        headers["X-Pen-AI-Base-URL"] = this.aiImageConfig.baseUrl || "";
        headers["X-Pen-AI-Model"] = this.aiImageConfig.model || "";

        const res = await fetch(`${apiBase}/ai/images`, {
          method: "POST",
          headers: headers,
          body: JSON.stringify({
            prompt: "test connection",
            width: 256,
            height: 256,
            response_format: "b64_json",
          }),
        });

        if (res.ok) {
          this.connectionImageSuccess = true;
          this.connectionImageMessage =
            "Connection Successful (Image API Tested)!";
        } else {
          const data = await res
            .json()
            .catch(() => ({ detail: "Unknown error" }));
          this.connectionImageSuccess = false;
          this.connectionImageMessage = `Failed: ${data.detail || res.statusText}`;
        }
      } catch (e) {
        this.connectionImageSuccess = false;
        this.connectionImageMessage = `Error: ${e.message}`;
      } finally {
        this.testingImageConnection = false;
      }
    },

    applyKeyPreset() {
      const preset = KEY_SCOPE_PRESETS[this.newKeyPreset];
      if (preset) {
        this.newKeyScopes = [...preset];
      }
    },

    toggleKeyScope(scope) {
      this.newKeyPreset = "custom";
      const set = new Set(this.newKeyScopes || []);
      if (set.has(scope)) {
        set.delete(scope);
      } else {
        set.add(scope);
      }
      this.newKeyScopes = SITE_SCOPED_AGENT_CAPS.filter((cap) => set.has(cap));
    },

    hasKeyScope(scope) {
      return (this.newKeyScopes || []).includes(scope);
    },

    selectedKeyScopes() {
      return SITE_SCOPED_AGENT_CAPS.filter((cap) =>
        (this.newKeyScopes || []).includes(cap),
      );
    },

    // --- Agent Keys ---
    async generateAgentKey() {
      const name = (this.newKeyName || "").trim().toLowerCase();
      const siteId = (this.newKeySiteId || "default").trim() || "default";
      const scopes = this.selectedKeyScopes();
      if (!name) {
        this.showToast(
          "Enter a name for this agent key (e.g. blog-cursor)",
          "error",
        );
        return;
      }
      if (!scopes.length) {
        this.showToast("Select at least one scope", "error");
        return;
      }
      try {
        const apiBase = window.AUTH.apiBase.replace("/v1", "");
        const res = await fetch(`${apiBase}/auth/keys`, {
          method: "POST",
          headers: window.AUTH.getHeaders(),
          body: JSON.stringify({
            name,
            scopes,
            site_id: siteId,
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to generate agent key");

        // Save key to vault under the friendly name
        if (window.VAULT && window.VAULT.unlocked) {
          if (!window.VAULT.secrets.AGENT_KEYS) {
            window.VAULT.secrets.AGENT_KEYS = {};
          }
          window.VAULT.secrets.AGENT_KEYS[data.name] = data.key;
          await window.VAULT.save();
        }

        this.newKeyName = "";
        await this.refreshAgentKeys();
        const boundSite = data.site_id || siteId;
        this.showToast(
          `Agent key “${data.name}” on site “${boundSite}” generated`,
        );
      } catch (e) {
        this.showToast(e.message || "Failed to generate key", "error");
      }
    },

    confirmRevokeKey(index, name) {
      this.keyToRevoke = index;
      this.keyNameToRevoke = name || "Agent Key";
      this.showRevokeModal = true;
    },

    async reassignAgentKeySite(index) {
      const key = this.agentKeys[index];
      if (!key) return;
      const siteId = (key.site_id || "default").trim() || "default";
      try {
        const apiBase = window.AUTH.apiBase.replace("/v1", "");
        const res = await fetch(`${apiBase}/auth/keys/${index}`, {
          method: "PATCH",
          headers: window.AUTH.getHeaders(),
          body: JSON.stringify({ site_id: siteId }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          const detail =
            typeof data.detail === "string"
              ? data.detail
              : data.detail
                ? JSON.stringify(data.detail)
                : "Failed to reassign key site";
          throw new Error(detail);
        }
        await this.refreshAgentKeys();
        this.showToast(
          `Key “${key.name}” bound to “${data.site_id || siteId}” (existing JWTs keep old site until expiry)`,
        );
      } catch (e) {
        this.showToast(e.message || "Failed to reassign key site", "error");
        await this.refreshAgentKeys();
      }
    },

    async revokeAgentKey() {
      if (this.keyToRevoke === null) return;
      const index = this.keyToRevoke;
      const keyName = this.keyNameToRevoke;
      try {
        const apiBase = window.AUTH.apiBase.replace("/v1", "");
        const res = await fetch(`${apiBase}/auth/keys/${index}`, {
          method: "DELETE",
          headers: window.AUTH.getHeaders(),
        });
        if (!res.ok) throw new Error("Failed to revoke key");

        // Clean up from vault
        if (window.VAULT && window.VAULT.unlocked && window.VAULT.secrets.AGENT_KEYS) {
          delete window.VAULT.secrets.AGENT_KEYS[keyName];
          await window.VAULT.save();
        }

        await this.refreshAgentKeys();
        this.showToast("Agent key revoked");
      } catch (e) {
        this.showToast("Failed to revoke key", "error");
      } finally {
        this.showRevokeModal = false;
        this.keyToRevoke = null;
        this.keyNameToRevoke = "";
      }
    },

    async saveVault() {
      if (!this.vaultUnlocked || this.savingVault) return;
      this.savingVault = true;
      try {
        // AI Provider configuration
        window.VAULT.secrets["AI_PROVIDER_CONFIG"] = {
          provider: this.aiConfig.provider,
          label:
            AI_PROVIDERS[this.aiConfig.provider]?.label ||
            this.aiConfig.provider,
          baseUrl: this.aiConfig.baseUrl,
          apiKey: this.aiConfig.apiKey,
          model: this.aiConfig.model,
        };

        // AI Image Generation configuration
        if (this.useSameApiKey) {
          this.aiImageConfig.apiKey = this.aiConfig.apiKey;
        }
        window.VAULT.secrets["AI_IMAGE_CONFIG"] = {
          provider: this.aiImageConfig.provider,
          label:
            IMAGE_PROVIDERS[this.aiImageConfig.provider]?.label ||
            this.aiImageConfig.provider,
          baseUrl: this.aiImageConfig.baseUrl,
          apiKey: this.aiImageConfig.apiKey,
          model: this.aiImageConfig.model,
          useSameApiKey: this.useSameApiKey,
        };

        await window.VAULT.save();

        // Save AI agent permissions / settings to server
        const apiBase = window.AUTH.apiBase.replace("/v1", "");
        const settingsRes = await fetch(`${apiBase}/ai/settings`, {
          method: "PUT",
          headers: window.AUTH.getHeaders(),
          body: JSON.stringify({
            ai_publish_autonomy: this.guardrails.publishAutonomy,
            ai_metadata_scope: this.guardrails.metadataScope,
            text_generation_prompt: this.promptSettings.textGenerationPrompt,
            image_generation_prompt: this.promptSettings.imageGenerationPrompt,
          }),
        });
        if (!settingsRes.ok) {
          throw new Error("Failed to save AI permissions and guardrails to site config");
        }

        this.showToast("Vault encrypted and AI settings saved.");

        setTimeout(() => {
          this.lockVault();
        }, 500);
      } catch (e) {
        this.showToast(e.message, "error");
      } finally {
        this.savingVault = false;
      }
    },

    async saveGuardrails() {
      this.savingGuardrails = true;
      try {
        const apiBase = window.AUTH.apiBase.replace("/v1", "");
        const settingsRes = await fetch(`${apiBase}/ai/settings`, {
          method: "PUT",
          headers: window.AUTH.getHeaders(),
          body: JSON.stringify({
            ai_publish_autonomy: this.guardrails.publishAutonomy,
            ai_metadata_scope: this.guardrails.metadataScope,
            text_generation_prompt: this.promptSettings.textGenerationPrompt,
            image_generation_prompt: this.promptSettings.imageGenerationPrompt,
            post_quality_checklist: this.promptSettings.qualityChecklist,
          }),
        });
        if (!settingsRes.ok) {
          throw new Error("Failed to save AI permissions and guardrails");
        }
        this.showToast("AI permissions and guardrails saved.");
      } catch (e) {
        this.showToast(e.message, "error");
      } finally {
        this.savingGuardrails = false;
      }
    },

    async savePromptSettings() {
      if (this.savingPromptSettings) return;
      this.savingPromptSettings = true;
      try {
        const apiBase = window.AUTH.apiBase.replace("/v1", "");
        const settingsRes = await fetch(`${apiBase}/ai/settings`, {
          method: "PUT",
          headers: window.AUTH.getHeaders(),
          body: JSON.stringify({
            ai_publish_autonomy: this.guardrails.publishAutonomy,
            ai_metadata_scope: this.guardrails.metadataScope,
            text_generation_prompt: this.promptSettings.textGenerationPrompt,
            image_generation_prompt: this.promptSettings.imageGenerationPrompt,
            post_quality_checklist: this.promptSettings.qualityChecklist,
          }),
        });
        if (!settingsRes.ok) {
          throw new Error("Failed to save prompt settings");
        }
        this.showToast("Prompt settings saved successfully.");
      } catch (e) {
        this.showToast(e.message, "error");
      } finally {
        this.savingPromptSettings = false;
      }
    },
  }));
});
