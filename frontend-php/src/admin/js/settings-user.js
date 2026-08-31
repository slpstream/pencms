/**
 * PenCMS User Settings & Vault Controller (settings-user.js)
 */
document.addEventListener("alpine:init", () => {
  Alpine.data("userSettings", () => ({
    saving: false,
    savingVault: false,
    toasts: [],
    toastCounter: 0,

    profile: {
      display_name: "",
      avatar: "",
      website: "",
      bio: "",
    },

    // Vault state (aliased from window.VAULT)
    vaultUnlocked: false,
    showVaultPassword: false,
    unlockPassword: "",
    vaultData: [], // Array of {key, value} for editing

    async init() {
      try {
        const data = await window.AUTH.getMe();
        if (data && data.user) {
          this.profile = data.user;
        }

        // Poll for vault unlock state (since vault.js handles auto-unlock)
        const checkVault = () => {
          if (window.VAULT && window.VAULT.unlocked) {
            this.loadVaultData();
          } else {
            setTimeout(checkVault, 100);
          }
        };
        checkVault();
      } catch (e) {
        console.warn("Could not fetch user data", e);
      }
    },

    showToast(message, type = "success") {
      const id = ++this.toastCounter;
      this.toasts.push({ id, message, type });
      setTimeout(() => {
        this.toasts = this.toasts.filter((t) => t.id !== id);
      }, 4000);
    },

    async saveProfile() {
      if (this.saving) return;
      this.saving = true;
      try {
        // 1. Save Public Profile
        const apiBase = window.AUTH.apiBase.replace("/v1", "");
        const profileRes = await fetch(`${apiBase}/auth/profile`, {
          method: "PUT",
          headers: window.AUTH.getHeaders(),
          body: JSON.stringify(this.profile),
        });
        if (!profileRes.ok) throw new Error("Failed to save profile metadata");

        // 2. Save Vault (if unlocked and modified)
        if (this.vaultUnlocked) {
          await this.saveVault();
        }

        this.showToast("Profile and vault saved successfully");
      } catch (e) {
        console.error(e);
        this.showToast(e.message || "Failed to save profile", "error");
      } finally {
        this.saving = false;
      }
    },

    async uploadAvatar(file) {
      try {
        const response = await window.api.uploadAvatar(file);
        this.profile.avatar = response.url + "?t=" + Date.now();
        this.showToast("Avatar uploaded successfully");
      } catch (err) {
        this.showToast(`Failed to upload avatar: ${err.message}`, "error");
      }
    },

    handleFileSelect(event) {
      const files = event.target.files;
      if (files && files.length > 0) {
        this.uploadAvatar(files[0]);
      }
    },

    handleDrop(event) {
      const files = event.dataTransfer.files;
      if (files && files.length > 0) {
        this.uploadAvatar(files[0]);
      }
    },

    // --- Vault UI Logic ---

    loadVaultData() {
      const secrets = window.VAULT.secrets || {};
      
      // Filter out structured AI configs to avoid string coercion in the free-form editor
      this.vaultData = Object.entries(secrets)
        .filter(([k]) => k !== "AI_PROVIDER_CONFIG" && k !== "AI_IMAGE_CONFIG")
        .map(([k, v]) => ({ key: k, value: v }));
      this.vaultUnlocked = true;
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
      this.vaultData = [];
      this.unlockPassword = "";
      this.vaultUnlocked = false;
    },

    addVaultItem() {
      this.vaultData.push({ key: "", value: "" });
    },

    removeVaultItem(index) {
      this.vaultData.splice(index, 1);
    },

    async saveVault() {
      if (!this.vaultUnlocked || this.savingVault) return;
      this.savingVault = true;
      try {
        // Preserve existing AI config structures so we don't overwrite them
        const existingAi = window.VAULT.secrets["AI_PROVIDER_CONFIG"];
        const existingAiImg = window.VAULT.secrets["AI_IMAGE_CONFIG"];

        // Sync vaultData back to window.VAULT.secrets
        window.VAULT.secrets = {};
        for (const item of this.vaultData) {
          if (item.key.trim()) {
            window.VAULT.secrets[item.key.trim()] = item.value;
          }
        }

        if (existingAi) window.VAULT.secrets["AI_PROVIDER_CONFIG"] = existingAi;
        if (existingAiImg) window.VAULT.secrets["AI_IMAGE_CONFIG"] = existingAiImg;

        await window.VAULT.save();
        this.showToast("Vault encrypted and saved.");

        setTimeout(() => {
          this.lockVault();
        }, 500);
      } catch (e) {
        this.showToast(e.message, "error");
      } finally {
        this.savingVault = false;
      }
    },
  }));
});

