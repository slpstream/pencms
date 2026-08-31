#!/usr/bin/env python3
"""Generate Open Graph images for published pages, scoped to one site or all.

Usage:
  python3 og-image-maker.py [--site=<id>] [--output=<dir>]
  python3 og-image-maker.py --all-sites [--output=<dir>]  (Pro)

Default (neither --site nor --all-sites): site "default" only.
--all-sites writes each site under {output}/{site_id}/images/og/.
Core refuses --all-sites with a Pro pointer (edition from GET /api/config).
Single-site writes under {output}/images/og/.
--domain is accepted and ignored (build.sh pass-through).

Visual settings resolve: site Social overrides → theme social_preview → engine defaults.
Draw path lives in backend ``services.og_image`` (shared with admin Generate preview).
"""

import argparse
import configparser
import json
import os
import sys
import tempfile
import urllib.request

import yaml
from PIL import Image

# Ensure we always run relative to frontend-php/ (chdir happens in run()).
FRONTEND_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

WORKSPACE_ROOT = os.path.abspath(os.path.join(FRONTEND_ROOT, ".."))
CONFIG_PATH = os.path.join(WORKSPACE_ROOT, "backend-python", "config.ini")
SITES_YAML_PATH = os.path.join(WORKSPACE_ROOT, "backend-python", "data", "sites.yaml")
DEFAULT_SITE_ID = "default"

# Allow importing backend social_preview / og_image when available.
_BACKEND_APP = os.path.join(WORKSPACE_ROOT, "backend-python", "app")
if _BACKEND_APP not in sys.path:
    sys.path.insert(0, _BACKEND_APP)

config = configparser.ConfigParser()
config.read(CONFIG_PATH)

API_PORT = config.getint("Server", "api_port", fallback=8000)
API_BASE = f"http://localhost:{API_PORT}/api"

INSTALL_THEME = config.get("theme", "active", fallback="starter")
THEME_DIR = config.get("theme", "directory", fallback="apps/blog/themes")

# Engine safety defaults (mirror services.social_preview.ENGINE_DEFAULTS)
ENGINE_DEFAULTS = {
    "og_accent_color": "#C12929",
    "og_vignette_color": "#FF8000",
    "og_text_color": "#FFFFFF",
    "og_bar_color": "#000000",
    "og_font": "CourierPrime-Bold",
    "og_fonts": {"CourierPrime-Bold": "fonts/CourierPrime-Bold.ttf"},
    "og_headline_style": "redacted",
    "og_text_case": "upper",
    "og_grade_preset": "noir",
    "og_accent_bar": True,
    "og_watermark_enabled": True,
    "og_watermark": None,
    "og_watermark_source": None,
    "og_watermark_layout": "full_canvas",
    "og_watermark_corner": "br",
    "og_watermark_scale": "md",
    "og_default_hero": None,
    "og_fallback_title": "ARCHIVAL RECORD",
}


def theme_path_for(theme_name: str) -> str:
    if THEME_DIR.startswith("../"):
        return os.path.abspath(
            os.path.join(WORKSPACE_ROOT, "backend-python", THEME_DIR, theme_name)
        )
    return os.path.abspath(os.path.join(WORKSPACE_ROOT, THEME_DIR, theme_name))


def load_registry_sites() -> dict:
    """Return {site_id: record_dict} from sites.yaml (empty if missing)."""
    if not os.path.isfile(SITES_YAML_PATH):
        return {}
    with open(SITES_YAML_PATH, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    sites = data.get("sites") or []
    out = {}
    for site in sites:
        if not isinstance(site, dict):
            continue
        sid = str(site.get("id") or "").strip().lower()
        if sid:
            out[sid] = site
    return out


def resolve_theme_name(site_id: str, registry: dict) -> str:
    record = registry.get(site_id) or {}
    theme = record.get("theme")
    if theme:
        return str(theme).strip()
    return INSTALL_THEME


def resolve_social_config(site_id: str, registry: dict) -> dict:
    """Merge site overrides + theme social_preview + engine defaults."""
    record = registry.get(site_id) or {}
    theme_name = resolve_theme_name(site_id, registry)
    try:
        from services.social_preview import resolve_social_preview

        return resolve_social_preview(record, theme_name=theme_name)
    except Exception:
        theme_path = theme_path_for(theme_name)
        theme_block = {}
        tj = os.path.join(theme_path, "theme.json")
        if os.path.isfile(tj):
            try:
                with open(tj, encoding="utf-8") as fh:
                    data = json.load(fh)
                block = data.get("social_preview")
                if isinstance(block, dict):
                    theme_block = block
            except Exception:
                pass
        merged = dict(ENGINE_DEFAULTS)
        for k, v in theme_block.items():
            if v is None or (isinstance(v, str) and not v.strip()):
                continue
            merged[k] = v
        for k in (
            "og_accent_color",
            "og_vignette_color",
            "og_text_color",
            "og_bar_color",
            "og_font",
            "og_headline_style",
            "og_text_case",
            "og_grade_preset",
            "og_watermark",
            "og_watermark_source",
            "og_watermark_layout",
            "og_watermark_corner",
            "og_watermark_scale",
            "og_default_hero",
            "og_fallback_title",
        ):
            if record.get(k):
                merged[k] = record[k]
        if "og_accent_bar" in record and record["og_accent_bar"] is not None:
            merged["og_accent_bar"] = bool(record["og_accent_bar"])
        if "og_watermark_enabled" in record and record["og_watermark_enabled"] is not None:
            merged["og_watermark_enabled"] = bool(record["og_watermark_enabled"])
        return merged


def api_get(url: str, site_id: str, timeout: float = 15):
    """GET url with X-Pen-Site-Id header; return response bytes."""
    req = urllib.request.Request(url, headers={"X-Pen-Site-Id": site_id})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def site_asset_url(site_id: str, logical: str) -> str:
    """Canonical site-scoped raw asset URL (never legacy flat images/…)."""
    clean = logical.lstrip("/")
    if clean.startswith("assets/"):
        clean = clean[7:]
    return f"{API_BASE}/assets/raw/sites/{site_id}/assets/{clean}"


def open_image_from_url(url: str, site_id: str, timeout: float = 15) -> Image.Image:
    data = api_get(url, site_id, timeout=timeout)
    with tempfile.NamedTemporaryFile(delete=True) as tmp:
        tmp.write(data)
        tmp.flush()
        img = Image.open(tmp.name)
        img.load()
        return img


def process_dossier(
    slug,
    title,
    hero_img_url,
    *,
    site_id: str,
    output_dir: str,
    active_theme_path: str,
    cfg: dict,
):
    from services.og_image import render_og_image

    print(f"📸 Generating OG for: {slug}...")

    try:
        hero_source = None
        try:
            hero_source = open_image_from_url(hero_img_url, site_id, timeout=15)
        except Exception as img_err:
            print(
                f"   ⚠️ Hero image failed to load ({img_err}). Using default hero fallback."
            )

        jpeg = render_og_image(
            title,
            cfg,
            site_id=site_id,
            theme_path=active_theme_path,
            hero_source=hero_source,
        )
        os.makedirs(output_dir, exist_ok=True)
        save_path = os.path.join(output_dir, f"{slug}.jpg")
        with open(save_path, "wb") as fh:
            fh.write(jpeg)

    except Exception as e:
        print(f"   ❌ Error processing {slug}: {e}")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate site-scoped Open Graph images for published pages."
    )
    parser.add_argument("--site", default=None, help="Build OG images for one site id")
    parser.add_argument(
        "--all-sites",
        action="store_true",
        help="Build OG images for every site in the registry (PenCMS Pro)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output root (default: dist under frontend-php/)",
    )
    parser.add_argument(
        "--domain",
        default=None,
        help="Ignored; accepted for build.sh pass-through compatibility",
    )
    return parser.parse_args(argv)


def resolve_site_ids(args, registry: dict) -> tuple:
    """Return (site_ids, all_sites_mode). Exits on invalid flags."""
    has_site = args.site is not None
    has_all = bool(args.all_sites)

    if has_site and has_all:
        print(
            "Error: pass either --site=<id> or --all-sites, not both.",
            file=sys.stderr,
        )
        sys.exit(1)

    if has_all:
        edition = "core"
        try:
            raw = api_get(f"{API_BASE}/config", DEFAULT_SITE_ID, timeout=5)
            cfg = json.loads(raw.decode())
            if isinstance(cfg, dict) and cfg.get("edition") == "pro":
                edition = "pro"
        except Exception:
            edition = "core"
        if edition != "pro":
            print(
                "Error: --all-sites requires PenCMS Pro "
                "(overlay; GET /api/config edition=pro).",
                file=sys.stderr,
            )
            sys.exit(1)
        site_ids = list(registry.keys())
        if not site_ids:
            print("Error: no live sites found in registry.", file=sys.stderr)
            sys.exit(1)
        return site_ids, True

    if has_site:
        requested = str(args.site).strip().lower()
        if not requested:
            print("Error: --site= requires a non-empty site id.", file=sys.stderr)
            sys.exit(1)
        if requested not in registry:
            print(
                f"Error: unknown site '{requested}' (not in registry).",
                file=sys.stderr,
            )
            sys.exit(1)
        return [requested], False

    print(
        "Note: building site 'default' only. "
        "Use --site=<id> for other sites (--all-sites is Pro).",
        file=sys.stderr,
    )
    return [DEFAULT_SITE_ID], False


def run_for_site(site_id: str, output_dir: str, registry: dict):
    theme_name = resolve_theme_name(site_id, registry)
    active_theme_path = theme_path_for(theme_name)
    cfg = resolve_social_config(site_id, registry)
    fallback_title = cfg.get("og_fallback_title") or "ARCHIVAL RECORD"

    print(
        f"🖼️  OG Image Maker site={site_id} theme={theme_name} "
        f"style={cfg.get('og_headline_style')} grade={cfg.get('og_grade_preset')} "
        f"(API: {API_BASE})"
    )
    print(f"   → output: {output_dir}")

    try:
        raw = api_get(
            f"{API_BASE}/pages?status=published&live_only=true",
            site_id,
            timeout=15,
        )
        pages = json.loads(raw.decode())
    except Exception as e:
        print(f"❌ Could not connect to API for site '{site_id}': {e}")
        return

    if not isinstance(pages, list):
        print(f"❌ Unexpected pages response for site '{site_id}'")
        return

    for page in pages:
        fm = page.get("frontmatter", {}) or {}
        slug = page.get("id")
        title = fm.get("hero_title") or fm.get("title", fallback_title)
        hero_image = fm.get("hero_image") or "images/defaulthero.jpg"

        hero_image = str(hero_image).lstrip("/")
        if hero_image.startswith("assets/"):
            hero_image = hero_image[7:]

        if hero_image in ("images/defaulthero.jpg", "images/defaulthero.jpeg"):
            cfg_hero = cfg.get("og_default_hero")
            if cfg_hero and str(cfg_hero).startswith("images/"):
                hero_image = str(cfg_hero).lstrip("/")
                if hero_image.startswith("assets/"):
                    hero_image = hero_image[7:]

        hero_url = site_asset_url(site_id, hero_image)
        process_dossier(
            slug,
            title,
            hero_url,
            site_id=site_id,
            output_dir=output_dir,
            active_theme_path=active_theme_path,
            cfg=cfg,
        )

    print(f"✨ OG images for '{site_id}' written to {output_dir}")


def run(argv=None):
    os.chdir(FRONTEND_ROOT)
    args = parse_args(argv)
    registry = load_registry_sites()
    site_ids, all_sites_mode = resolve_site_ids(args, registry)

    if args.output:
        output_root = args.output.rstrip("/")
    else:
        output_root = "dist"

    for site_id in site_ids:
        if all_sites_mode:
            out_dir = os.path.join(output_root, site_id, "images", "og")
        else:
            out_dir = os.path.join(output_root, "images", "og")
        run_for_site(site_id, out_dir, registry)

    print("\n✨ All OG image generation complete.")


if __name__ == "__main__":
    run()
