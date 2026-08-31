/**
 * Shared MCP HTTP executor for admin AI sidebars.
 * Used by ai-sidebar.js (editor) and ai-sidebar-navigation.js (nav).
 */
(function (global) {
  "use strict";

  /**
   * MCP HTTP failure with structured fields for tool-result shaping.
   * `.message` stays a readable string for legacy catch sites.
   */
  class McpToolError extends Error {
    /**
     * @param {string} message
     * @param {{ status?: number, detail?: unknown }} [opts]
     */
    constructor(message, opts = {}) {
      super(message);
      this.name = "McpToolError";
      this.status = opts.status != null ? opts.status : null;
      this.detail = opts.detail !== undefined ? opts.detail : null;
    }
  }

  /**
   * @param {Array<[string, {method: string, path: string}]>} entries
   * @returns {Record<string, {method: string, path: string}>}
   */
  function buildToolMap(entries) {
    const map = {};
    for (const [name, def] of entries) {
      map[name] = def;
    }
    return map;
  }

  /**
   * @param {...Record<string, {method: string, path: string}>} maps
   * @returns {Record<string, {method: string, path: string}>}
   */
  function mergeToolMaps(...maps) {
    return Object.assign({}, ...maps);
  }

  /**
   * Execute an MCP tool via the PenCMS HTTP gateway.
   *
   * @param {object} opts
   * @param {string} opts.functionName
   * @param {object} opts.args
   * @param {Record<string, {method: string, path: string}>} opts.toolMap
   * @param {string} [opts.apiBase]
   * @param {Record<string, string>} [opts.headers]
   * @param {string[]} [opts.unwrapBodyKeys]  If present on args, send that nested value as body
   * @param {(fn: string, args: object) => object|void} [opts.prepareArgs]
   * @param {(fn: string, headers: object) => object|void} [opts.enrichHeaders]
   * @param {(fn: string, data: object, ctx: {apiBase: string, headers: object}) => Promise<object>|object} [opts.afterResponse]
   */
  async function executeMcpTool({
    functionName,
    args,
    toolMap,
    apiBase,
    headers,
    unwrapBodyKeys = [],
    prepareArgs,
    enrichHeaders,
    afterResponse,
  }) {
    if (!toolMap || !toolMap[functionName]) {
      throw new McpToolError(`Unknown MCP tool: ${functionName}`, {
        status: null,
        detail: `Unknown MCP tool: ${functionName}`,
      });
    }

    const { method, path } = toolMap[functionName];
    let requestArgs = args && typeof args === "object" ? { ...args } : {};

    if (typeof prepareArgs === "function") {
      const prepared = prepareArgs(functionName, requestArgs);
      if (prepared && typeof prepared === "object") {
        requestArgs = prepared;
      }
    }

    let finalPath = path;
    const pathParams = [];
    const matches = path.match(/\{([^}]+)\}/g) || [];
    for (const match of matches) {
      const paramName = match.slice(1, -1);
      pathParams.push(paramName);
      const val = requestArgs[paramName];
      if (val === undefined || val === null) {
        throw new McpToolError(`Missing required path parameter: ${paramName}`, {
          status: 400,
          detail: `Missing required path parameter: ${paramName}`,
        });
      }
      finalPath = finalPath.replace(match, encodeURIComponent(val));
    }

    const base =
      apiBase != null
        ? apiBase
        : global.AUTH && global.AUTH.apiBase
          ? global.AUTH.apiBase
          : "";

    let requestHeaders =
      headers != null
        ? { ...headers }
        : global.AUTH && typeof global.AUTH.getHeaders === "function"
          ? { ...global.AUTH.getHeaders() }
          : {};

    if (typeof enrichHeaders === "function") {
      const enriched = enrichHeaders(functionName, requestHeaders);
      if (enriched && typeof enriched === "object") {
        requestHeaders = enriched;
      }
    }

    const queryParams = new URLSearchParams();
    let requestBody = null;
    const upperMethod = String(method).toUpperCase();

    if (upperMethod === "GET" || upperMethod === "HEAD") {
      for (const [key, val] of Object.entries(requestArgs)) {
        if (!pathParams.includes(key) && val !== undefined && val !== null) {
          queryParams.append(key, val);
        }
      }
    } else {
      let bodyValue = null;
      for (const key of unwrapBodyKeys) {
        if (
          Object.prototype.hasOwnProperty.call(requestArgs, key) &&
          requestArgs[key] !== undefined &&
          requestArgs[key] !== null
        ) {
          bodyValue = requestArgs[key];
          break;
        }
      }
      if (bodyValue === null) {
        const bodyObj = {};
        for (const [key, val] of Object.entries(requestArgs)) {
          if (!pathParams.includes(key) && val !== undefined && val !== null) {
            bodyObj[key] = val;
          }
        }
        bodyValue = bodyObj;
      }
      requestBody = JSON.stringify(bodyValue);
    }

    const queryString = queryParams.toString();
    const url = `${base}${finalPath}${queryString ? "?" + queryString : ""}`;

    const resp = await fetch(url, {
      method: upperMethod,
      headers: requestHeaders,
      ...(requestBody && { body: requestBody }),
    });

    if (!resp.ok) {
      let errMsg = resp.statusText;
      let detail = null;
      const contentType = resp.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        const err = await resp.json().catch(() => ({}));
        if (err && err.detail !== undefined) {
          detail = err.detail;
          errMsg =
            typeof err.detail === "object"
              ? JSON.stringify(err.detail)
              : String(err.detail);
        }
      } else {
        const text = await resp.text().catch(() => "");
        if (text) {
          errMsg = text;
          detail = text;
        }
      }
      throw new McpToolError(errMsg, { status: resp.status, detail });
    }

    if (resp.status === 204) {
      return { success: true };
    }

    let data = await resp.json();

    if (typeof afterResponse === "function") {
      const next = await afterResponse(functionName, data, {
        apiBase: base,
        headers: requestHeaders,
      });
      if (next !== undefined) {
        data = next;
      }
    }

    return data;
  }

  global.PenMcpClient = {
    McpToolError,
    executeMcpTool,
    buildToolMap,
    mergeToolMaps,
  };
})(typeof window !== "undefined" ? window : globalThis);
