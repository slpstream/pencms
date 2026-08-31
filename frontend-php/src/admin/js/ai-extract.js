/**
 * PenCMS extractive field-fill helper (Session 5 / PR-C).
 *
 * POST /api/ai/extract — preview only; the caller writes the field on Apply.
 * Session 6 / PR-D reuses this for faqs (same route, field="faqs").
 */
(function () {
  const VAULT_LOCKED =
    "Unlock your vault under User Settings → Vault to use AI.";
  const NO_PROVIDER =
    "Configure an AI provider in User Settings → Vault first.";

  function aiApiBase() {
    return ((window.AUTH && window.AUTH.apiBase) || "/api/v1").replace(
      "/v1",
      "",
    );
  }

  function detailMessage(errJson, fallback) {
    const detail = errJson && errJson.detail;
    if (!detail) return fallback;
    if (typeof detail === "object") {
      return detail.message || JSON.stringify(detail);
    }
    return String(detail);
  }

  async function ensureVaultReady() {
    if (window.VAULT && window.VAULT.ready) await window.VAULT.ready;
    if (!window.VAULT || !window.VAULT.unlocked) {
      const err = new Error(VAULT_LOCKED);
      err.code = "vault_locked";
      throw err;
    }
    const ai = window.VAULT.getSecret("AI_PROVIDER_CONFIG");
    if (!ai) {
      const err = new Error(NO_PROVIDER);
      err.code = "no_provider";
      throw err;
    }
    const isLocal = ai.baseUrl && /localhost|127\.0\.0\.1/i.test(ai.baseUrl);
    if (!isLocal && !ai.apiKey) {
      const err = new Error(NO_PROVIDER);
      err.code = "no_provider";
      throw err;
    }
  }

  window.penAiExtract = async function penAiExtract({
    field,
    body,
    currentValue,
    replace,
  }) {
    await ensureVaultReady();
    const headers =
      window.AUTH && typeof window.AUTH.getHeaders === "function"
        ? window.AUTH.getHeaders()
        : { "Content-Type": "application/json" };
    const resp = await fetch(`${aiApiBase()}/ai/extract`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        field,
        body: body == null ? "" : String(body),
        current_value: currentValue == null ? "" : currentValue,
        replace: !!replace,
      }),
    });
    const json = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const err = new Error(
        detailMessage(json, resp.statusText || "Extract failed"),
      );
      err.status = resp.status;
      err.code = (json.detail && json.detail.code) || null;
      throw err;
    }
    return json;
  };
})();
