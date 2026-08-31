#!/usr/bin/env node
/**
 * One-shot theme screenshot capture for PenCMS admin theme cards.
 *
 * Writes frontend-php/src/blog/themes/{slug}/screenshot.webp (16:10 viewport).
 * Requires: Node 18+, Playwright Chromium, Python3 + Pillow (PNG→WebP).
 *
 * Usage:
 *   npx --yes playwright install chromium
 *   PENCMS_BASE_URL=http://127.0.0.1:8009 node frontend-php/cli-tools/capture-theme-screenshots.mjs
 *
 * Flags:
 *   --only starter,launch   Capture a subset
 *   --force                 Overwrite existing screenshot.webp
 *   --site default          Site id for ?site= (default: default)
 *   --path /blog/           Public homepage path (default: /blog/)
 *   --out path/to/shot.webp Write WebP to an arbitrary path (implies single capture)
 *   --live-site             Skip config.ini / sites.yaml mutation; capture ?site= only
 *   --dry-run               List themes only
 */

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "../..");
const THEMES_ROOT = path.join(REPO_ROOT, "frontend-php/src/blog/themes");
const DEFAULT_CONFIG = path.join(REPO_ROOT, "backend-python/config.ini");
const DEFAULT_SITES = path.join(REPO_ROOT, "backend-python/data/sites.yaml");

const VIEWPORT = { width: 1280, height: 800 };
const WEBP_QUALITY = 80;
const THEME_SETTLE_MS = {
  pulp: 16000,
};

function parseArgs(argv) {
  const out = {
    only: null,
    force: false,
    site: "default",
    path: "/blog/",
    dryRun: false,
    wait: 0,
    outFile: null,
    liveSite: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--force") out.force = true;
    else if (a === "--dry-run") out.dryRun = true;
    else if (a === "--live-site") out.liveSite = true;
    else if (a === "--wait") out.wait = parseInt(argv[++i], 10) || 0;
    else if (a.startsWith("--wait=")) out.wait = parseInt(a.slice("--wait=".length), 10) || 0;
    else if (a === "--only") {
      out.only = new Set(
        String(argv[++i] || "")
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean)
      );
    } else if (a.startsWith("--only=")) {
      out.only = new Set(
        a
          .slice("--only=".length)
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean)
      );
    } else if (a === "--site") out.site = String(argv[++i] || "default");
    else if (a.startsWith("--site=")) out.site = a.slice("--site=".length);
    else if (a === "--path") out.path = String(argv[++i] || "/blog/");
    else if (a.startsWith("--path=")) out.path = a.slice("--path=".length);
    else if (a === "--out") out.outFile = String(argv[++i] || "");
    else if (a.startsWith("--out=")) out.outFile = a.slice("--out=".length);
  }
  if (!out.path.startsWith("/")) out.path = "/" + out.path;
  return out;
}

function listThemes() {
  return fs
    .readdirSync(THEMES_ROOT, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name)
    .filter((name) => !name.startsWith("_") && name !== "custom")
    .filter((name) => fs.existsSync(path.join(THEMES_ROOT, name, "theme.json")))
    .sort();
}

function readActiveTheme(configPath) {
  const text = fs.readFileSync(configPath, "utf8");
  const m = text.match(/^\s*active\s*=\s*(.+)\s*$/m);
  return m ? m[1].trim() : "starter";
}

function setActiveTheme(configPath, slug) {
  const text = fs.readFileSync(configPath, "utf8");
  if (!/^\s*active\s*=/m.test(text)) {
    throw new Error(`No [theme] active= line in ${configPath}`);
  }
  const next = text.replace(/^\s*active\s*=\s*.*$/m, `active = ${slug}`);
  fs.writeFileSync(configPath, next, "utf8");
}

/**
 * Clear sites.yaml theme for captureSite so install [theme] active wins.
 * Returns { restoredYaml, previousTheme } for finally restore.
 */
function clearSiteTheme(sitesPath, captureSite) {
  if (!fs.existsSync(sitesPath)) {
    throw new Error(`sites.yaml not found: ${sitesPath}`);
  }
  const original = fs.readFileSync(sitesPath, "utf8");
  const lines = original.split("\n");
  let inTarget = false;
  let previousTheme = null;
  let themeLineIndex = -1;
  let themeIndent = "";

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const idMatch = line.match(/^(\s*)-\s*id:\s*(.+)\s*$/);
    if (idMatch) {
      inTarget = idMatch[2].trim() === captureSite;
      continue;
    }
    if (!inTarget) continue;
    // Next top-level list item ends the site block
    if (/^\s*-\s*id:\s*/.test(line)) break;
    const themeMatch = line.match(/^(\s*)theme:\s*(.*)\s*$/);
    if (themeMatch) {
      themeIndent = themeMatch[1];
      previousTheme = themeMatch[2].trim();
      themeLineIndex = i;
      break;
    }
  }

  if (themeLineIndex === -1) {
    console.log(
      `Preflight: site "${captureSite}" already has no theme: (install [theme] active will apply).`
    );
    return { restoredYaml: original, previousTheme: null, cleared: false };
  }

  // Remove the theme line so SiteRegistry falls back to install active
  const nextLines = lines.slice();
  nextLines.splice(themeLineIndex, 1);
  fs.writeFileSync(sitesPath, nextLines.join("\n"), "utf8");
  console.log(
    `Preflight: cleared site "${captureSite}" theme: ${previousTheme} (was ${themeIndent}theme: ${previousTheme})`
  );
  return {
    restoredYaml: original,
    previousTheme,
    cleared: true,
  };
}

function pngToWebp(pngPath, webpPath, quality) {
  const py = `
from PIL import Image
im = Image.open(${JSON.stringify(pngPath)})
im.save(${JSON.stringify(webpPath)}, "WEBP", quality=${quality}, method=6)
print("ok")
`;
  const r = spawnSync("python3", ["-c", py], { encoding: "utf8" });
  if (r.status !== 0) {
    throw new Error(
      `PNG→WebP failed: ${r.stderr || r.stdout || "unknown error"}`
    );
  }
}

async function loadPlaywright() {
  try {
    return await import("playwright");
  } catch {
    // Resolve from npx cache / sibling install
    const require = createRequire(import.meta.url);
    try {
      return require("playwright");
    } catch {
      console.error(
        "Playwright not found. Install once:\n  npm install -D playwright\n  npx playwright install chromium"
      );
      process.exit(1);
    }
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const baseUrl = (process.env.PENCMS_BASE_URL || "").replace(/\/$/, "");
  const configPath = process.env.PENCMS_CONFIG || DEFAULT_CONFIG;
  const sitesPath = process.env.PENCMS_SITES || DEFAULT_SITES;

  if (args.outFile) {
    if (!baseUrl) {
      console.error(
        "Set PENCMS_BASE_URL (e.g. http://127.0.0.1:8009). Aborting."
      );
      process.exit(1);
    }
    const outPath = path.resolve(args.outFile);
    const { chromium } = await loadPlaywright();
    let browser;
    try {
      browser = await chromium.launch({ headless: true });
      const context = await browser.newContext({
        viewport: VIEWPORT,
        deviceScaleFactor: 1,
      });
      const page = await context.newPage();
      const homePath = args.path.endsWith("/") ? args.path : `${args.path}/`;
      const url = `${baseUrl}${homePath}?site=${encodeURIComponent(args.site)}&_shot=${Date.now()}`;
      const resp = await page.goto(url, {
        waitUntil: "networkidle",
        timeout: 45000,
      });
      const status = resp ? resp.status() : 0;
      if (status >= 400) {
        throw new Error(`HTTP ${status}`);
      }
      const settleMs = args.wait || 400;
      await new Promise((r) => setTimeout(r, settleMs));
      const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "pencms-theme-shots-"));
      const pngPath = path.join(tmpDir, "live.png");
      await page.screenshot({ path: pngPath, fullPage: false, type: "png" });
      fs.mkdirSync(path.dirname(outPath), { recursive: true });
      pngToWebp(pngPath, outPath, WEBP_QUALITY);
      const bytes = fs.statSync(outPath).size;
      console.log(`ok    live-site → ${outPath} (${bytes} bytes)`);
      fs.rmSync(tmpDir, { recursive: true, force: true });
    } finally {
      if (browser) await browser.close();
    }
    return;
  }

  let themes = listThemes();
  if (args.only) {
    const missing = [...args.only].filter((s) => !themes.includes(s));
    if (missing.length) {
      console.error(`Unknown --only themes: ${missing.join(", ")}`);
      process.exit(1);
    }
    themes = themes.filter((t) => args.only.has(t));
  }

  console.log(`Themes to capture: ${themes.length}`);
  if (args.dryRun) {
    for (const t of themes) console.log(`  - ${t}`);
    return;
  }

  if (!baseUrl) {
    console.error(
      "Set PENCMS_BASE_URL (e.g. http://127.0.0.1:8009). Aborting."
    );
    process.exit(1);
  }
  if (!fs.existsSync(configPath)) {
    console.error(`config.ini not found: ${configPath}`);
    process.exit(1);
  }

  const originalTheme = readActiveTheme(configPath);
  let siteClear = { restoredYaml: null, previousTheme: null, cleared: false };
  if (!args.liveSite) {
    siteClear = clearSiteTheme(sitesPath, args.site);
  } else {
    console.log(
      `Preflight: --live-site — skipping config.ini and sites.yaml mutation.`
    );
  }
  const { chromium } = await loadPlaywright();

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "pencms-theme-shots-"));
  const ok = [];
  const skipped = [];
  const failed = [];

  let browser;
  try {
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
      viewport: VIEWPORT,
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();

    for (const slug of themes) {
      const outPath = path.join(THEMES_ROOT, slug, "screenshot.webp");
      if (fs.existsSync(outPath) && !args.force) {
        console.log(`skip  ${slug} (exists; use --force)`);
        skipped.push(slug);
        continue;
      }

      try {
        if (!args.liveSite) {
          setActiveTheme(configPath, slug);
        }
        const homePath = args.path.endsWith("/") ? args.path : `${args.path}/`;
        const url = `${baseUrl}${homePath}?site=${encodeURIComponent(args.site)}&_shot=${Date.now()}`;
        const resp = await page.goto(url, {
          waitUntil: "networkidle",
          timeout: 45000,
        });
        const status = resp ? resp.status() : 0;
        if (status >= 400) {
          throw new Error(`HTTP ${status}`);
        }
        // Settle fonts / late CSS / theme animations (e.g. pulp woodcut/press animation takes 15s)
        const settleMs = args.wait || THEME_SETTLE_MS[slug] || 400;
        if (settleMs > 400) {
          console.log(`settle ${slug} (waiting ${settleMs}ms for animations)...`);
        }
        await new Promise((r) => setTimeout(r, settleMs));

        // Sanity: CSS should reference the theme we just activated
        const html = await page.content();
        if (!html.includes(`/themes/${slug}/`) && !html.includes(`skin-${slug}`)) {
          console.warn(
            `warn  ${slug}: page HTML may not reference this theme (site.theme override?)`
          );
        }

        const pngPath = path.join(tmpDir, `${slug}.png`);
        await page.screenshot({
          path: pngPath,
          fullPage: false,
          type: "png",
        });
        pngToWebp(pngPath, outPath, WEBP_QUALITY);
        const bytes = fs.statSync(outPath).size;
        console.log(`ok    ${slug} → screenshot.webp (${bytes} bytes)`);
        ok.push(slug);
      } catch (err) {
        console.error(`FAIL  ${slug}: ${err.message || err}`);
        failed.push({ slug, error: String(err.message || err) });
      }
    }
  } finally {
    if (browser) await browser.close();
    if (!args.liveSite) {
      setActiveTheme(configPath, originalTheme);
      console.log(`Restored config.ini theme.active = ${originalTheme}`);
      if (siteClear.cleared) {
        fs.writeFileSync(sitesPath, siteClear.restoredYaml, "utf8");
        console.log(
          `Restored sites.yaml theme for "${args.site}" (${siteClear.previousTheme})`
        );
      }
    }
    try {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    } catch {
      /* ignore */
    }
  }

  console.log("\nSummary");
  console.log(`  ok:      ${ok.length}`);
  console.log(`  skipped: ${skipped.length}`);
  console.log(`  failed:  ${failed.length}`);
  if (failed.length) {
    for (const f of failed) console.log(`    - ${f.slug}: ${f.error}`);
    process.exit(1);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
