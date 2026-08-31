"""Shared OG Pillow renderer (publish CLI + admin preview)."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image


def test_render_og_image_jpeg_dimensions_and_stable_bytes():
    from services.og_image import HEIGHT, WIDTH, render_og_image
    from services.social_preview import ENGINE_DEFAULTS

    cfg = dict(ENGINE_DEFAULTS)
    cfg.update(
        og_grade_preset="none",
        og_headline_style="plain",
        og_accent_bar=False,
    )
    hero = Image.new("RGB", (64, 64), (40, 80, 120))
    first = render_og_image(
        "Preview Title",
        cfg,
        site_id=None,
        theme_path="/nonexistent-theme",
        hero_source=hero,
    )
    second = render_og_image(
        "Preview Title",
        cfg,
        site_id=None,
        theme_path="/nonexistent-theme",
        hero_source=Image.new("RGB", (64, 64), (40, 80, 120)),
    )
    assert first[:2] == b"\xff\xd8"
    assert first == second
    img = Image.open(io.BytesIO(first))
    assert img.size == (WIDTH, HEIGHT)
    assert img.format == "JPEG"


def test_render_og_preview_cache_hits():
    from services.og_image import clear_preview_cache, render_og_preview
    from services.social_preview import ENGINE_DEFAULTS

    clear_preview_cache()
    cfg = dict(ENGINE_DEFAULTS)
    cfg.update(og_grade_preset="none", og_headline_style="plain")
    a = render_og_preview(
        "Cached",
        cfg,
        site_id="default",
        theme_path="/nonexistent-theme",
        hero_source=None,
    )
    b = render_og_preview(
        "Cached",
        cfg,
        site_id="default",
        theme_path="/nonexistent-theme",
        hero_source=None,
    )
    assert a == b
    assert a[:2] == b"\xff\xd8"


def test_apply_social_draft_empty_clears_saved_override():
    from services.social_preview import apply_social_draft

    site = {
        "id": "blog",
        "theme": "starter",
        "og_headline_style": "redacted",
        "og_accent_color": "#112233",
    }
    draft = apply_social_draft(
        site,
        {"og_headline_style": "", "og_accent_color": "#445566"},
    )
    assert "og_headline_style" not in draft
    assert draft["og_accent_color"] == "#445566"
    assert draft["id"] == "blog"


def test_og_image_maker_cli_imports_shared_renderer():
    import importlib.util

    path = (
        Path(__file__).resolve().parents[2]
        / "frontend-php"
        / "cli-tools"
        / "og-image-maker.py"
    )
    spec = importlib.util.spec_from_file_location("og_image_maker_cli", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    source = path.read_text(encoding="utf-8")
    assert "from services.og_image import render_og_image" in source
    assert hasattr(mod, "process_dossier")


def test_watermark_enabled_false_skips_overlay(tmp_path):
    from services.og_image import render_og_image
    from services.social_preview import ENGINE_DEFAULTS

    theme = tmp_path / "theme"
    (theme / "assets" / "images").mkdir(parents=True)
    Image.new("RGBA", (1200, 630), (255, 0, 0, 200)).save(
        theme / "assets" / "images" / "watermark.png"
    )
    cfg = dict(ENGINE_DEFAULTS)
    cfg.update(
        og_grade_preset="none",
        og_headline_style="plain",
        og_accent_bar=False,
        og_watermark_enabled=True,
        og_watermark="assets/images/watermark.png",
    )
    hero = Image.new("RGB", (64, 64), (10, 20, 30))
    with_wm = render_og_image(
        "Title",
        cfg,
        site_id=None,
        theme_path=theme,
        hero_source=hero,
    )
    cfg["og_watermark_enabled"] = False
    without = render_og_image(
        "Title",
        cfg,
        site_id=None,
        theme_path=theme,
        hero_source=Image.new("RGB", (64, 64), (10, 20, 30)),
    )
    assert with_wm[:2] == b"\xff\xd8"
    assert without[:2] == b"\xff\xd8"
    assert with_wm != without


def test_registry_woff2_font_renders_jpeg():
    from services.og_image import (
        build_og_font_catalog,
        registry_font_file,
        render_og_image,
    )
    from services.social_preview import ENGINE_DEFAULTS

    catalog = build_og_font_catalog(ENGINE_DEFAULTS)
    registry_ids = [e["id"] for e in catalog if e["source"] == "registry"]
    assert "inter-700" in registry_ids
    assert registry_font_file("inter-700") is not None
    assert registry_font_file("Inter") is not None

    cfg = dict(ENGINE_DEFAULTS)
    cfg.update(
        og_grade_preset="none",
        og_headline_style="plain",
        og_accent_bar=False,
        og_watermark_enabled=False,
    )
    hero = Image.new("RGB", (64, 64), (30, 30, 30))
    cfg["og_font"] = "inter-700"
    inter = render_og_image(
        "Registry Font",
        cfg,
        site_id=None,
        theme_path="/nonexistent-theme",
        hero_source=hero,
    )
    cfg["og_font"] = "Inter"
    by_label = render_og_image(
        "Registry Font",
        cfg,
        site_id=None,
        theme_path="/nonexistent-theme",
        hero_source=Image.new("RGB", (64, 64), (30, 30, 30)),
    )
    cfg["og_font"] = "CourierPrime-Bold"
    courier = render_og_image(
        "Registry Font",
        cfg,
        site_id=None,
        theme_path="/nonexistent-theme",
        hero_source=Image.new("RGB", (64, 64), (30, 30, 30)),
    )
    assert inter[:2] == b"\xff\xd8"
    img = Image.open(io.BytesIO(inter))
    assert img.size == (1200, 630)
    assert inter == by_label
    assert inter != courier


def test_registry_font_catalog_labels_include_weight():
    from services.og_image import build_og_font_catalog
    from services.social_preview import ENGINE_DEFAULTS

    catalog = build_og_font_catalog(ENGINE_DEFAULTS)
    inter = next(e for e in catalog if e["id"] == "inter-700")
    assert inter["source"] == "registry"
    assert "Bold" in inter["label"]
    assert inter["id"] == "inter-700"
    regular = next(
        (e for e in catalog if e["source"] == "registry" and e["id"].endswith("-400")),
        None,
    )
    if regular is not None:
        assert "Regular" in regular["label"]
        assert regular["id"].endswith("-400")


def test_variable_font_weight_follows_font_id():
    from PIL import ImageDraw

    from services.og_image import get_font

    manrope = (
        Path(__file__).resolve().parents[2]
        / "frontend-php"
        / "src"
        / "blog"
        / "themes"
        / "keys"
        / "assets"
        / "fonts"
        / "Manrope-Bold.ttf"
    )
    if not manrope.is_file():
        return
    path = str(manrope)

    def ink(font_id: str) -> int:
        font = get_font(72, [path], font_id=font_id)
        img = Image.new("L", (800, 120), 255)
        ImageDraw.Draw(img).text((10, 10), "HELLO WORLD", fill=0, font=font)
        return sum(255 - px for px in img.getdata())

    bold = ink("Manrope-Bold")
    regular = ink("Manrope-Regular")
    assert bold > regular * 1.2


def test_new_headline_styles_and_grades_render():
    from services.og_image import _HEADLINE_SPECS, render_og_image
    from services.social_preview import ENGINE_DEFAULTS, GRADE_PRESETS, HEADLINE_STYLES

    assert set(_HEADLINE_SPECS) == HEADLINE_STYLES
    cfg = dict(ENGINE_DEFAULTS)
    cfg.update(og_accent_bar=False, og_watermark_enabled=False)
    hero = Image.new("RGB", (64, 64), (80, 40, 20))
    for style in ("boxed", "caption", "poster", "outline"):
        cfg["og_headline_style"] = style
        cfg["og_grade_preset"] = "none"
        jpeg = render_og_image(
            "Styled",
            cfg,
            site_id=None,
            theme_path="/nonexistent-theme",
            hero_source=hero,
        )
        assert jpeg[:2] == b"\xff\xd8", style
    for grade in ("sepia", "mono", "night", "vibrant"):
        assert grade in GRADE_PRESETS
        cfg["og_headline_style"] = "plain"
        cfg["og_grade_preset"] = grade
        jpeg = render_og_image(
            "Graded",
            cfg,
            site_id=None,
            theme_path="/nonexistent-theme",
            hero_source=Image.new("RGB", (64, 64), (80, 40, 20)),
        )
        assert jpeg[:2] == b"\xff\xd8", grade


def test_apply_social_draft_watermark_bool():
    from services.social_preview import apply_social_draft

    site = {"id": "blog", "og_watermark_enabled": True}
    draft = apply_social_draft(site, {"og_watermark_enabled": False})
    assert draft["og_watermark_enabled"] is False
    cleared = apply_social_draft(site, {"og_watermark_enabled": None})
    assert "og_watermark_enabled" not in cleared


def test_corner_watermark_differs_from_full_canvas():
    from services.og_image import HEIGHT, WIDTH, render_og_image
    from services.social_preview import ENGINE_DEFAULTS

    wm = Image.new("RGBA", (64, 64), (255, 0, 0, 220))
    cfg = dict(ENGINE_DEFAULTS)
    cfg.update(
        og_grade_preset="none",
        og_headline_style="plain",
        og_accent_bar=False,
        og_watermark_enabled=True,
        og_watermark_layout="corner",
        og_watermark_corner="br",
        og_watermark_scale="md",
    )
    hero = Image.new("RGB", (64, 64), (10, 20, 30))
    corner = render_og_image(
        "Title",
        cfg,
        site_id=None,
        theme_path="/nonexistent-theme",
        hero_source=hero,
        watermark_image=wm,
    )
    cfg["og_watermark_layout"] = "full_canvas"
    full = render_og_image(
        "Title",
        cfg,
        site_id=None,
        theme_path="/nonexistent-theme",
        hero_source=Image.new("RGB", (64, 64), (10, 20, 30)),
        watermark_image=Image.new("RGBA", (64, 64), (255, 0, 0, 220)),
    )
    assert corner[:2] == b"\xff\xd8"
    assert full[:2] == b"\xff\xd8"
    assert Image.open(io.BytesIO(corner)).size == (WIDTH, HEIGHT)
    assert corner != full
    cfg["og_watermark_enabled"] = False
    disabled = render_og_image(
        "Title",
        cfg,
        site_id=None,
        theme_path="/nonexistent-theme",
        hero_source=Image.new("RGB", (64, 64), (10, 20, 30)),
        watermark_image=Image.new("RGBA", (64, 64), (255, 0, 0, 220)),
    )
    assert disabled != corner
