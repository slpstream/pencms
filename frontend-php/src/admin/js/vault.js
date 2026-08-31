/**
 * PenCMS Zero-Knowledge Vault Client
 * Handles client-side encryption/decryption of the user's secret vault.
 * Uses KEK (Key Encryption Key) + DEK (Data Encryption Key) architecture.
 */
class VaultClient {
    constructor() {
        this.unlocked = false;
        this.secrets = {};
        this.masterPassword = null;
        this.encryptedBlob = null;
        // Promise that resolves once init() completes (success or failure).
        // Other code (e.g. APIClient) can `await window.VAULT.ready` to
        // ensure the vault has had a chance to auto-unlock before reading headers.
        this._readyResolve = null;
        this.ready = new Promise(resolve => { this._readyResolve = resolve; });
        this._initStarted = false;
    }

    /**
     * Initialize the vault by fetching the blob from the server.
     * Idempotent: AUTH IIFE starts this before alpine; DOMContentLoaded is a no-op.
     */
    async init() {
        if (this._initStarted) return this.ready;
        this._initStarted = true;
        this.checkSecureContext();
        let meOk = false;
        try {
            if (window.AUTH && typeof window.AUTH.getMe === 'function') {
                const data = await window.AUTH.getMe();
                meOk = true;
                this.encryptedBlob = data.vault || null;
            } else {
                const apiBase = window.AUTH.apiBase.replace('/v1', '');
                const res = await fetch(`${apiBase}/auth/me`, {
                    headers: window.AUTH.getHeaders()
                });
                if (res.ok) {
                    const data = await res.json();
                    meOk = true;
                    this.encryptedBlob = data.vault || null;
                }
            }
            // Only unlock (including empty-vault bootstrap) after a successful /auth/me.
            // A failed fetch must not leave the vault "unlocked" with an empty blob.
            if (meOk) {
                const savedPw = sessionStorage.getItem('pen_master_password');
                if (savedPw) {
                    await this.unlock(savedPw);
                }
            }
        } catch (e) {
            console.warn('Vault init failed:', e);
        } finally {
            // Signal readiness regardless of success/failure
            this._readyResolve();
        }
        return this.ready;
    }

    /**
     * Verify if the browser context supports secure cryptographic APIs.
     */
    checkSecureContext() {
        if (!window.isSecureContext || !window.crypto || !window.crypto.subtle) {
            console.error("VaultClient: Insecure context detected! Browser cryptography APIs are unavailable.");
            try {
                if (localStorage.getItem('pen_insecure_dismissed') === 'true') {
                    return; // User dismissed it permanently
                }
            } catch (e) {
                // Ignore localStorage access errors
            }
            this.showInsecureContextBanner();
        }
    }

    /**
     * Inject a warning banner at the top of the document body.
     */
    showInsecureContextBanner() {
        // Prevent duplicate banners
        if (document.getElementById('pen-insecure-context-banner')) return;

        const banner = document.createElement('div');
        banner.id = 'pen-insecure-context-banner';
        banner.className = 'bg-orange-50 border-b border-orange-200 px-4 py-3 text-orange-950 shadow-sm relative z-50';
        banner.innerHTML = `
            <div class="max-w-7xl mx-auto flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div class="flex items-start gap-3">
                    <span class="flex-shrink-0 text-lg mt-0.5" aria-hidden="true">⚠️</span>
                    <div>
                        <p class="font-brand font-bold tracking-tight text-xs uppercase text-orange-900">Insecure Context Detected</p>
                        <p class="text-xs text-orange-800 mt-0.5 leading-relaxed">
                            The Zero-Knowledge Vault is disabled because this page is loaded in an insecure context (HTTP on a remote domain/IP). 
                            To enable credential encryption and clipboard features, please host this site over <strong>HTTPS</strong> or access it via <strong>localhost</strong> or a <strong>.onion</strong> domain.
                        </p>
                    </div>
                </div>
                <button onclick="window.VAULT.dismissInsecureContextBanner()" class="text-orange-600 hover:text-orange-900 transition-colors text-xs font-semibold uppercase tracking-wider self-start sm:self-center shrink-0">
                    Dismiss
                </button>
            </div>
        `;
        // Inject at the very top of the body
        document.body.insertBefore(banner, document.body.firstChild);
    }

    /**
     * Dismiss the banner and remember the preference permanently.
     */
    dismissInsecureContextBanner() {
        const banner = document.getElementById('pen-insecure-context-banner');
        if (banner) {
            banner.remove();
        }
        try {
            localStorage.setItem('pen_insecure_dismissed', 'true');
        } catch (e) {
            console.warn("Failed to set persistent preference:", e);
        }
    }

    async unlock(password) {
        if (!this.encryptedBlob) {
            // New vault bootstrap
            this.secrets = {};
            this.masterPassword = password;
            this.unlocked = true;
            sessionStorage.setItem('pen_master_password', password);
            return true;
        }

        try {
            const decrypted = await this.decryptVaultData(this.encryptedBlob, password);
            this.secrets = decrypted;
            this.masterPassword = password;
            this.unlocked = true;
            sessionStorage.setItem('pen_master_password', password);
            return true;
        } catch (e) {
            console.error('Vault unlock failed:', e);
            throw new Error('Incorrect vault password');
        }
    }

    lock() {
        this.unlocked = false;
        this.secrets = {};
        this.masterPassword = null;
        sessionStorage.removeItem('pen_master_password');
    }

    getSecret(key) {
        return this.unlocked ? this.secrets[key] : null;
    }

    setSecret(key, value) {
        if (!this.unlocked) throw new Error('Vault is locked');
        this.secrets[key] = value;
    }

    async save() {
        if (!this.unlocked || !this.masterPassword) throw new Error('Vault is locked');
        
        const blob = await this.encryptVaultData(this.secrets, this.masterPassword);
        const apiBase = window.AUTH.apiBase.replace('/v1', '');
        const res = await fetch(`${apiBase}/auth/vault`, {
            method: 'PUT',
            headers: window.AUTH.getHeaders(),
            body: JSON.stringify({ vault: blob })
        });
        
        if (!res.ok) throw new Error('Failed to save vault to server');
        this.encryptedBlob = blob;
        return true;
    }

    // --- Cryptography Helpers (KEK/DEK + AES-GCM) ---

    async deriveKEK(password, salt) {
        const enc = new TextEncoder();
        const keyMaterial = await window.crypto.subtle.importKey(
            "raw", enc.encode(password), "PBKDF2", false, ["deriveBits", "deriveKey"]
        );
        return window.crypto.subtle.deriveKey(
            { name: "PBKDF2", salt: salt, iterations: 100000, hash: "SHA-256" },
            keyMaterial,
            { name: "AES-GCM", length: 256 },
            false, ["encrypt", "decrypt"]
        );
    }

    async encryptVaultData(plainTextObj, password) {
        const enc = new TextEncoder();
        
        // 1. Generate new DEK
        const dek = await window.crypto.subtle.generateKey(
            { name: "AES-GCM", length: 256 },
            true, 
            ["encrypt", "decrypt"]
        );
        
        // 2. Encrypt Vault with DEK
        const vaultIv = window.crypto.getRandomValues(new Uint8Array(12));
        const plainTextBytes = enc.encode(JSON.stringify(plainTextObj));
        const vaultCipherText = await window.crypto.subtle.encrypt(
            { name: "AES-GCM", iv: vaultIv },
            dek,
            plainTextBytes
        );
        
        // 3. Derive KEK from Password
        const kekSalt = window.crypto.getRandomValues(new Uint8Array(16));
        const kek = await this.deriveKEK(password, kekSalt);
        
        // 4. Export DEK and Encrypt it with KEK
        const dekRaw = await window.crypto.subtle.exportKey("raw", dek);
        const dekIv = window.crypto.getRandomValues(new Uint8Array(12));
        const dekCipherText = await window.crypto.subtle.encrypt(
            { name: "AES-GCM", iv: dekIv },
            kek,
            dekRaw
        );
        
        return JSON.stringify({
            kekSalt: btoa(String.fromCharCode(...kekSalt)),
            dekIv: btoa(String.fromCharCode(...dekIv)),
            encryptedDek: btoa(String.fromCharCode(...new Uint8Array(dekCipherText))),
            vaultIv: btoa(String.fromCharCode(...vaultIv)),
            encryptedVault: btoa(String.fromCharCode(...new Uint8Array(vaultCipherText)))
        });
    }

    async decryptVaultData(encryptedJsonStr, password) {
        const encData = JSON.parse(encryptedJsonStr);
        const kekSalt = Uint8Array.from(atob(encData.kekSalt), c => c.charCodeAt(0));
        const dekIv = Uint8Array.from(atob(encData.dekIv), c => c.charCodeAt(0));
        const encryptedDek = Uint8Array.from(atob(encData.encryptedDek), c => c.charCodeAt(0));
        const vaultIv = Uint8Array.from(atob(encData.vaultIv), c => c.charCodeAt(0));
        const encryptedVault = Uint8Array.from(atob(encData.encryptedVault), c => c.charCodeAt(0));
        
        const kek = await this.deriveKEK(password, kekSalt);
        const dekRaw = await window.crypto.subtle.decrypt({ name: "AES-GCM", iv: dekIv }, kek, encryptedDek);
        
        const dek = await window.crypto.subtle.importKey("raw", dekRaw, { name: "AES-GCM" }, false, ["decrypt"]);
        const plainTextBytes = await window.crypto.subtle.decrypt({ name: "AES-GCM", iv: vaultIv }, dek, encryptedVault);
        
        return JSON.parse(new TextDecoder().decode(plainTextBytes));
    }
}

window.VAULT = new VaultClient();
document.addEventListener('DOMContentLoaded', () => window.VAULT.init());
