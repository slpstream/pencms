"""Shared Pillow renderer for Open Graph images (publish CLI + admin preview).

Disk-first for fonts, fallback heroes, and watermarks. The publish CLI still
fetches per-page heroes over HTTP and passes the loaded image in as
``hero_source``. Preview never HTTP-loops back into the API.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import re
import tempfile
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

WIDTH, HEIGHT = 1200, 630
JPEG_QUALITY = 90
PREVIEW_DATA_URL_MAX_DECODED = 4 * 1024 * 1024

_PREVIEW_CACHE_MAX = 8
_preview_cache: OrderedDict[str, bytes] = OrderedDict()

HeroSource = Union[None, str, Path, Image.Image]

_DATA_URL_RE = re.compile(
    r"^data:image/(png|jpeg|jpg|webp|gif);base64,(.+)$",
    re.IGNORECASE | re.DOTALL,
)


def repo_root() -> Path:
    """Install root (parent of ``backend-python/``). Stable when tests rebind BASE_DIR."""
    return Path(__file__).resolve().parents[3]


def frontend_root() -> Path:
    return repo_root() / "frontend-php"


def cold_war_og_kit_path() -> Path:
    from services.social_preview import themes_root

    return themes_root() / "_asset-kits" / "cold-war-og"


def theme_path_for_site(site: Any) -> Path:
    """Theme directory for a site record or mapping."""
    from services.social_preview import effective_theme_name, theme_json_path, themes_root

    theme = effective_theme_name(site)
    site_id = None
    if isinstance(site, Mapping):
        raw = site.get("id")
        if isinstance(raw, str) and raw.strip():
            site_id = raw.strip()
    else:
        raw = getattr(site, "id", None)
        if isinstance(raw, str) and raw.strip():
            site_id = raw.strip()
    try:
        return theme_json_path(theme, site_id=site_id).parent
    except (ValueError, FileNotFoundError, OSError):
        return themes_root() / str(theme or "starter")


def hex_to_rgb(value, fallback=(0, 0, 0)):
    text = (value or "").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(c * 2 for c in text)
    if len(text) != 6:
        return fallback
    try:
        return tuple(int(text[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return fallback


def apply_text_case(text: str, mode: str) -> str:
    mode = (mode or "upper").lower()
    if mode == "as_is":
        return text
    if mode == "title":
        return text.title()
    return text.upper()


_FONTS_REGISTRY: Optional[dict] = None
_WEIGHT_PREF = ("700", "800", "900", "600", "500", "400")
_WEIGHT_LABELS = {
    "100": "Thin",
    "200": "ExtraLight",
    "300": "Light",
    "400": "Regular",
    "500": "Medium",
    "600": "SemiBold",
    "700": "Bold",
    "800": "ExtraBold",
    "900": "Black",
}
_woff_ttf_cache: Dict[str, str] = {}


def fonts_registry_dir() -> Path:
    return frontend_root() / "public" / "assets" / "fonts"


def load_fonts_registry() -> dict:
    global _FONTS_REGISTRY
    if _FONTS_REGISTRY is not None:
        return _FONTS_REGISTRY
    path = fonts_registry_dir() / "fonts.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        _FONTS_REGISTRY = data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        _FONTS_REGISTRY = {}
    return _FONTS_REGISTRY


def _pick_registry_face(files: Mapping[str, Any]) -> Optional[Tuple[str, str]]:
    if not isinstance(files, dict):
        return None
    for weight in _WEIGHT_PREF:
        name = files.get(weight)
        if isinstance(name, str) and name.strip():
            return weight, name.strip()
    for key, name in files.items():
        if not isinstance(name, str) or not name.strip():
            continue
        if str(key).endswith("i"):
            continue
        return str(key), name.strip()
    for key, name in files.items():
        if isinstance(name, str) and name.strip():
            return str(key), name.strip()
    return None


def registry_font_file(font_id: str) -> Optional[Path]:
    """Resolve a registry catalog id (``inter-700``) to a vendored font file."""
    text = (font_id or "").strip()
    if not text:
        return None
    registry = load_fonts_registry()
    font_dir = fonts_registry_dir()
    best_key = ""
    for family_key in registry:
        prefix = f"{family_key}-"
        if text.startswith(prefix) and len(family_key) > len(best_key):
            best_key = family_key
    if best_key:
        weight = text[len(best_key) + 1 :]
        entry = registry.get(best_key)
        files = entry.get("files") if isinstance(entry, dict) else None
        if isinstance(files, dict):
            name = files.get(weight)
            if isinstance(name, str) and name.strip():
                path = font_dir / name.strip()
                if path.is_file():
                    return path
    entry = registry.get(text)
    if isinstance(entry, dict):
        picked = _pick_registry_face(entry.get("files") or {})
        if picked:
            path = font_dir / picked[1]
            if path.is_file():
                return path
    needle = text.lower()
    for family_key, entry in registry.items():
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label") or "").strip().lower()
        family = str(entry.get("family") or "").strip().lower()
        if needle not in {family_key.lower(), label, family}:
            continue
        picked = _pick_registry_face(entry.get("files") or {})
        if not picked:
            continue
        path = font_dir / picked[1]
        if path.is_file():
            return path
    return None


def _registry_font_label(family: str, weight: str) -> str:
    """Family plus CSS weight word, e.g. Inter + 700 → Inter Bold."""
    family_s = str(family).strip() or "Font"
    raw = str(weight).strip()
    if raw.endswith("i") and raw[:-1].isdigit():
        raw = raw[:-1]
    word = _WEIGHT_LABELS.get(raw, raw)
    if family_s.lower().endswith(word.lower()):
        return family_s
    return f"{family_s} {word}"


def build_og_font_catalog(cfg: Mapping[str, Any]) -> List[Dict[str, str]]:
    """Theme og_fonts + registry faces (bold preferred) + engine fallback id."""
    out: List[Dict[str, str]] = []
    seen = set()
    og_fonts = cfg.get("og_fonts") if isinstance(cfg.get("og_fonts"), dict) else {}
    for fid in og_fonts:
        fid_s = str(fid).strip()
        if not fid_s or fid_s in seen:
            continue
        seen.add(fid_s)
        out.append({"id": fid_s, "label": fid_s, "source": "theme"})
    registry_entries: List[Dict[str, str]] = []
    font_dir = fonts_registry_dir()
    for family_key, entry in load_fonts_registry().items():
        if not isinstance(entry, dict):
            continue
        picked = _pick_registry_face(entry.get("files") or {})
        if not picked:
            continue
        weight, filename = picked
        fid = f"{family_key}-{weight}"
        if fid in seen:
            continue
        if not (font_dir / filename).is_file():
            continue
        label = entry.get("label") or entry.get("family") or family_key
        registry_entries.append(
            {
                "id": fid,
                "label": _registry_font_label(str(label), weight),
                "source": "registry",
            }
        )
        seen.add(fid)
    registry_entries.sort(key=lambda item: item["label"].lower())
    out.extend(registry_entries)
    if "CourierPrime-Bold" not in seen:
        out.append(
            {
                "id": "CourierPrime-Bold",
                "label": "Courier Prime Bold",
                "source": "engine",
            }
        )
    return out


def font_paths_for(active_theme_path: Union[str, Path], cfg: dict) -> list:
    """Build font candidate list from theme og_fonts, registry, and engine cascade."""
    theme_path = Path(active_theme_path)
    front = frontend_root()
    paths: List[str] = []
    font_id = (cfg.get("og_font") or "CourierPrime-Bold").strip()
    og_fonts = cfg.get("og_fonts") or {}
    rel = og_fonts.get(font_id) if isinstance(og_fonts, dict) else None
    if rel:
        rel = str(rel).lstrip("/")
        paths.append(str(theme_path / rel))
        paths.append(str(front / rel))
        if rel.startswith("assets/"):
            paths.append(str(theme_path / rel))
    registry_file = registry_font_file(font_id)
    if registry_file is not None:
        paths.append(str(registry_file))
    kit = cold_war_og_kit_path()
    paths.extend(
        [
            str(theme_path / "assets" / "fonts" / f"{font_id}.ttf"),
            str(theme_path / "assets" / "fonts" / "CourierPrime-Bold.ttf"),
            str(front / "fonts" / "CourierPrime-Bold.ttf"),
            str(kit / "fonts" / "CourierPrime-Bold.ttf"),
            "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
            "Courier",
        ]
    )
    seen = set()
    out = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _woff_to_ttf_path(woff_path: str) -> Optional[str]:
    cached = _woff_ttf_cache.get(woff_path)
    if cached and Path(cached).is_file():
        return cached
    src = Path(woff_path)
    try:
        st = src.stat()
        key = hashlib.sha256(
            f"{src.resolve()}:{st.st_mtime_ns}:{st.st_size}".encode()
        ).hexdigest()[:20]
    except OSError:
        return None
    dest_dir = Path(tempfile.gettempdir()) / "pencms-og-fonts"
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    dest = dest_dir / f"{key}.ttf"
    if dest.is_file():
        _woff_ttf_cache[woff_path] = str(dest)
        return str(dest)
    try:
        from fontTools.ttLib import TTFont

        font = TTFont(str(src))
        font.flavor = None
        font.save(str(dest))
        _woff_ttf_cache[woff_path] = str(dest)
        return str(dest)
    except Exception:
        try:
            dest.unlink(missing_ok=True)
        except OSError:
            pass
        return None


def _ensure_truetype_candidates(path: str) -> List[str]:
    """Return font files Pillow should try, converted TTF first then original."""
    p = Path(path)
    if not p.is_file():
        return []
    suffix = p.suffix.lower()
    if suffix in (".ttf", ".otf"):
        return [str(p)]
    if suffix in (".woff2", ".woff"):
        converted = _woff_to_ttf_path(str(p))
        out = []
        if converted:
            out.append(converted)
        out.append(str(p))
        return out
    return []


_STYLE_NAMES = {
    "100": "Thin",
    "thin": "Thin",
    "200": "ExtraLight",
    "extralight": "ExtraLight",
    "300": "Light",
    "light": "Light",
    "400": "Regular",
    "regular": "Regular",
    "normal": "Regular",
    "500": "Medium",
    "medium": "Medium",
    "600": "SemiBold",
    "semibold": "SemiBold",
    "700": "Bold",
    "bold": "Bold",
    "800": "ExtraBold",
    "extrabold": "ExtraBold",
    "900": "Black",
    "black": "Black",
}
_STYLE_WGHT = {
    "100": 100,
    "thin": 100,
    "200": 200,
    "extralight": 200,
    "300": 300,
    "light": 300,
    "400": 400,
    "regular": 400,
    "normal": 400,
    "500": 500,
    "medium": 500,
    "600": 600,
    "semibold": 600,
    "700": 700,
    "bold": 700,
    "800": 800,
    "extrabold": 800,
    "900": 900,
    "black": 900,
}


def _style_token(font_id: str, path: str) -> str:
    for source in (font_id or "", Path(path).stem):
        text = str(source).strip()
        if not text or "-" not in text:
            continue
        token = text.rsplit("-", 1)[-1].strip().lower()
        if token in _STYLE_NAMES or token in _STYLE_WGHT:
            return token
    return ""


def _apply_requested_weight(font, font_id: str, path: str):
    """Pin variable-font wght from the selected id (Bold/Regular/700/…)."""
    token = _style_token(font_id, path)
    if not token:
        return font
    try:
        names = font.get_variation_names()
    except Exception:
        return font
    if not names:
        return font
    want = _STYLE_NAMES.get(token)
    if want:
        for raw in names:
            decoded = (
                raw.decode("ascii", "ignore") if isinstance(raw, (bytes, bytearray)) else str(raw)
            )
            if decoded.lower() == want.lower():
                try:
                    font.set_variation_by_name(raw)
                    return font
                except Exception:
                    break
    wght = _STYLE_WGHT.get(token)
    if wght is None:
        return font
    try:
        axes = font.get_variation_axes()
        values = []
        for axis in axes:
            name = axis.get("name")
            tag = (
                name.decode("ascii", "ignore")
                if isinstance(name, (bytes, bytearray))
                else str(name or "")
            )
            if tag.lower() in ("weight", "wght"):
                lo = float(axis.get("minimum", wght))
                hi = float(axis.get("maximum", wght))
                values.append(max(lo, min(hi, float(wght))))
            else:
                values.append(float(axis.get("default", 0)))
        if values:
            font.set_variation_by_axes(values)
    except Exception:
        pass
    return font


def get_font(size, paths, font_id: str = ""):
    for path in paths:
        try:
            if path == "Courier":
                return ImageFont.truetype(path, size)
            for candidate in _ensure_truetype_candidates(path):
                try:
                    font = ImageFont.truetype(candidate, size)
                    return _apply_requested_weight(font, font_id, candidate)
                except Exception:
                    continue
        except Exception:
            continue
    return ImageFont.load_default()


def _radial_vignette(color, intensity, reach=0.7):
    gradient = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    pixels = gradient.load()
    max_dist = math.sqrt((WIDTH * reach) ** 2 + (HEIGHT * reach) ** 2)
    r, g, b = color
    for x in range(WIDTH):
        for y in range(HEIGHT):
            distance = math.sqrt(x**2 + (HEIGHT - y) ** 2)
            if distance < max_dist:
                opacity = 1.0 - (distance / max_dist)
                pixels[x, y] = (r, g, b, int(255 * opacity * intensity))
    return gradient


def _solid_tint(color, alpha):
    r, g, b = color
    return Image.new("RGBA", (WIDTH, HEIGHT), (r, g, b, int(alpha)))


def apply_color_grade(image, cfg: dict):
    """Apply a named grade preset. Unknown ids fall back to noir."""
    from services.social_preview import GRADE_PRESETS

    preset = (cfg.get("og_grade_preset") or "noir").lower()
    if preset not in GRADE_PRESETS:
        preset = "noir"
    if preset == "none":
        return image.convert("RGBA")

    base = image.convert("RGBA")
    vignette = hex_to_rgb(cfg.get("og_vignette_color"), (255, 128, 0))

    if preset == "clean":
        base = ImageEnhance.Color(base).enhance(0.85)
        base = ImageEnhance.Contrast(base).enhance(1.05)
        return Image.alpha_composite(base, _radial_vignette(vignette, 0.25))

    if preset == "vibrant":
        base = ImageEnhance.Color(base).enhance(1.35)
        base = ImageEnhance.Contrast(base).enhance(1.12)
        base = ImageEnhance.Sharpness(base).enhance(1.1)
        return base

    if preset == "warm":
        base = ImageEnhance.Color(base).enhance(1.1)
        return Image.alpha_composite(base, _solid_tint(vignette, 55))

    if preset == "cool":
        base = ImageEnhance.Color(base).enhance(0.85)
        blue_layer = Image.new("RGBA", base.size, "blue")
        return Image.blend(base, blue_layer, 0.12)

    if preset == "fade":
        base = ImageEnhance.Contrast(base).enhance(0.75)
        base = ImageEnhance.Brightness(base).enhance(1.15)
        base = ImageEnhance.Color(base).enhance(0.7)
        return base

    if preset == "high_contrast":
        base = ImageEnhance.Contrast(base).enhance(1.5)
        base = ImageEnhance.Color(base).enhance(0.7)
        base = ImageEnhance.Sharpness(base).enhance(1.3)
        return base

    if preset == "sepia":
        gray = ImageOps.grayscale(base)
        return ImageOps.colorize(gray, black="#1a1008", white="#edd9b0").convert(
            "RGBA"
        )

    if preset == "mono":
        return ImageOps.grayscale(base).convert("RGBA")

    if preset == "dusk":
        base = ImageEnhance.Color(base).enhance(0.75)
        base = ImageEnhance.Brightness(base).enhance(0.85)
        base = Image.alpha_composite(base, _solid_tint((48, 16, 64), 70))
        return Image.alpha_composite(base, _radial_vignette((20, 0, 40), 0.5))

    if preset == "night":
        base = ImageEnhance.Brightness(base).enhance(0.55)
        base = ImageEnhance.Contrast(base).enhance(1.15)
        return Image.alpha_composite(base, _solid_tint((0, 0, 20), 90))

    if preset == "paper":
        base = ImageEnhance.Color(base).enhance(0.8)
        base = ImageEnhance.Contrast(base).enhance(0.85)
        base = ImageEnhance.Brightness(base).enhance(1.08)
        return Image.alpha_composite(base, _solid_tint((232, 220, 196), 45))

    # noir (default)
    base = ImageEnhance.Color(base).enhance(0.4)
    base = ImageEnhance.Contrast(base).enhance(1.2)
    base = ImageEnhance.Sharpness(base).enhance(1.2)
    blue_layer = Image.new("RGBA", base.size, "blue")
    base = Image.blend(base, blue_layer, 0.1)
    return Image.alpha_composite(base, _radial_vignette(vignette, 0.6))


def _wrap_lines(draw, text, font, max_text_width):
    words = text.split()
    lines = []
    current_line = []
    for word in words:
        test_line = " ".join(current_line + [word])
        w, _ = draw.textbbox((0, 0), test_line, font=font)[2:]
        if w < max_text_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
    return lines


_HEADLINE_SPECS = {
    "redacted": {"align": "right", "valign": "center", "treatment": "redacted"},
    "shadow": {"align": "right", "valign": "center", "treatment": "shadow"},
    "plain": {"align": "right", "valign": "center", "treatment": "plain"},
    "left": {"align": "left", "valign": "center", "treatment": "plain"},
    "left_redacted": {"align": "left", "valign": "center", "treatment": "redacted"},
    "center": {"align": "center", "valign": "center", "treatment": "plain"},
    "center_redacted": {
        "align": "center",
        "valign": "center",
        "treatment": "redacted",
    },
    "outline": {"align": "right", "valign": "center", "treatment": "outline"},
    "banner": {"align": "left", "valign": "center", "treatment": "banner"},
    "boxed": {"align": "left", "valign": "center", "treatment": "boxed"},
    "underline": {"align": "left", "valign": "center", "treatment": "underline"},
    "caption": {
        "align": "left",
        "valign": "bottom",
        "treatment": "plain",
        "size": "small",
    },
    "poster": {
        "align": "left",
        "valign": "top",
        "treatment": "shadow",
        "size": "large",
    },
}


def _line_x(align: str, width_px: int, margin: int = 40) -> int:
    if align == "left":
        return margin
    if align == "center":
        return (WIDTH - width_px) // 2
    return WIDTH - margin - width_px


def draw_headline(draw, text, paths, cfg: dict):
    """Draw headline using a named style preset. Unknown ids fall back to redacted."""
    style = (cfg.get("og_headline_style") or "redacted").lower()
    spec = _HEADLINE_SPECS.get(style) or _HEADLINE_SPECS["redacted"]
    text = apply_text_case(text, cfg.get("og_text_case") or "upper")
    text_color = hex_to_rgb(cfg.get("og_text_color"), (255, 255, 255))
    bar_color = hex_to_rgb(cfg.get("og_bar_color"), (0, 0, 0))
    accent = hex_to_rgb(cfg.get("og_accent_color"), (193, 41, 41))
    align = spec["align"]
    treatment = spec["treatment"]
    size_mode = spec.get("size")

    if size_mode == "small":
        font_size = 42 if len(text) > 60 else 52
    elif size_mode == "large":
        font_size = 72 if len(text) > 60 else 96
    elif len(text) > 60:
        font_size = 65
    else:
        font_size = 90
    font = get_font(font_size, paths, font_id=str(cfg.get("og_font") or ""))

    max_text_width = 1000 if align != "right" else 800
    margin = 40
    line_spacing = 28 if size_mode == "small" else 40
    bar_padding_x = 15
    bar_padding_y = 15

    lines = _wrap_lines(draw, text, font, max_text_width)
    if not lines:
        return
    caps_h = draw.textbbox((0, 0), "ABC", font=font, anchor="lt")[3]
    total_text_height = (len(lines) * caps_h) + ((len(lines) - 1) * line_spacing)

    valign = spec["valign"]
    if valign == "top":
        y = 48
    elif valign == "bottom":
        y = HEIGHT - total_text_height - 56
    else:
        y = (HEIGHT - total_text_height) // 2

    metrics = []
    for line in lines:
        w, _ = draw.textbbox((0, 0), line, font=font, anchor="lt")[2:]
        metrics.append((_line_x(align, w, margin), w, line))

    if treatment == "banner":
        draw.rectangle(
            [0, y - bar_padding_y, WIDTH, y + total_text_height + bar_padding_y],
            fill=bar_color,
        )
    elif treatment == "boxed":
        min_x = min(x for x, _, _ in metrics) - bar_padding_x
        max_x = max(x + w for x, w, _ in metrics) + bar_padding_x
        draw.rectangle(
            [min_x, y - bar_padding_y, max_x, y + total_text_height + bar_padding_y],
            fill=bar_color,
        )

    for x_start, w, line in metrics:
        if treatment == "redacted":
            if align == "right":
                bar_bbox = [
                    x_start - bar_padding_x,
                    y - bar_padding_y,
                    WIDTH - margin + bar_padding_x,
                    y + caps_h + bar_padding_y,
                ]
            else:
                bar_bbox = [
                    x_start - bar_padding_x,
                    y - bar_padding_y,
                    x_start + w + bar_padding_x,
                    y + caps_h + bar_padding_y,
                ]
            draw.rectangle(bar_bbox, fill=bar_color)
            draw.text((x_start, y), line, fill=text_color, font=font, anchor="lt")
        elif treatment == "shadow":
            shadow = (0, 0, 0)
            for dx, dy in ((3, 3), (2, 2), (1, 1)):
                draw.text(
                    (x_start + dx, y + dy),
                    line,
                    fill=shadow,
                    font=font,
                    anchor="lt",
                )
            draw.text((x_start, y), line, fill=text_color, font=font, anchor="lt")
        elif treatment == "outline":
            draw.text(
                (x_start, y),
                line,
                fill=text_color,
                font=font,
                anchor="lt",
                stroke_width=3,
                stroke_fill=bar_color,
            )
        elif treatment == "underline":
            draw.text((x_start, y), line, fill=text_color, font=font, anchor="lt")
            underline_y = y + caps_h + 4
            draw.line(
                [(x_start, underline_y), (x_start + w, underline_y)],
                fill=accent,
                width=4,
            )
        else:
            draw.text((x_start, y), line, fill=text_color, font=font, anchor="lt")

        y += caps_h + line_spacing


def draw_accent_bar(draw, cfg: dict):
    """Draws the slanted accent bar at the bottom when enabled."""
    if not cfg.get("og_accent_bar", True):
        return
    accent = hex_to_rgb(cfg.get("og_accent_color"), (193, 41, 41))
    offset = int(WIDTH * 0.018)
    points = [
        (0, HEIGHT - 20 - offset),
        (WIDTH, HEIGHT - 20),
        (WIDTH, HEIGHT),
        (0, HEIGHT),
    ]
    draw.polygon(points, fill=accent)


def resolve_local_asset(path_value, active_theme_path: Union[str, Path]):
    """Resolve a theme-relative or absolute asset path on disk."""
    if not path_value:
        return None
    rel = str(path_value).lstrip("/")
    theme_path = Path(active_theme_path)
    kit = cold_war_og_kit_path()
    candidates = [
        theme_path / rel,
        frontend_root() / rel,
        Path(rel) if Path(rel).is_absolute() else None,
        kit / rel,
    ]
    if rel.startswith("assets/"):
        candidates.append(kit / rel[len("assets/") :])
    for c in candidates:
        if c is not None and c.is_file():
            return str(c)
    return None


def _site_asset_disk_path(site_id: Optional[str], logical: str) -> Optional[Path]:
    if not site_id or not logical:
        return None
    from config import CONTENT_DIR_PATH
    from services.site_service import join_site_assets_path

    if not CONTENT_DIR_PATH:
        return None
    clean = str(logical).lstrip("/")
    if clean.startswith("assets/"):
        clean = clean[7:]
    path = Path(CONTENT_DIR_PATH) / join_site_assets_path(site_id, clean)
    if path.is_file():
        return path
    return None


_RASTER_LOGO_EXTS = ("png", "webp", "jpg", "jpeg", "gif")
_WM_SCALE = {"sm": 0.12, "md": 0.18, "lg": 0.24}
_WM_MARGIN = 0.04


def site_raster_logo_path(site_id: Optional[str]) -> Optional[Path]:
    """Site logo PNG/WebP/JPEG/GIF if present. SVG is skipped (Pillow cannot composite it)."""
    for ext in _RASTER_LOGO_EXTS:
        path = _site_asset_disk_path(site_id, f"images/logo.{ext}")
        if path is not None:
            return path
    return None


def _load_rgba(path: Union[str, Path]) -> Optional[Image.Image]:
    try:
        with Image.open(path) as img:
            return img.convert("RGBA")
    except Exception:
        return None


def _effective_watermark_layout(cfg: dict) -> str:
    source = str(cfg.get("og_watermark_source") or "").strip().lower()
    if source == "logo":
        return "corner"
    layout = str(cfg.get("og_watermark_layout") or "full_canvas").strip().lower()
    if layout == "corner":
        return "corner"
    return "full_canvas"


def _corner_watermark(wm: Image.Image, cfg: dict) -> Image.Image:
    wm = wm.convert("RGBA")
    scale_id = str(cfg.get("og_watermark_scale") or "md").strip().lower()
    frac = _WM_SCALE.get(scale_id, _WM_SCALE["md"])
    max_w = max(1, int(WIDTH * frac))
    max_h = max(1, int(HEIGHT * frac))
    fitted = ImageOps.contain(wm, (max_w, max_h))
    margin = int(WIDTH * _WM_MARGIN)
    corner = str(cfg.get("og_watermark_corner") or "br").strip().lower()
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    if corner == "tl":
        xy = (margin, margin)
    elif corner == "tr":
        xy = (WIDTH - fitted.width - margin, margin)
    elif corner == "bl":
        xy = (margin, HEIGHT - fitted.height - margin)
    else:
        xy = (WIDTH - fitted.width - margin, HEIGHT - fitted.height - margin)
    canvas.paste(fitted, xy, fitted)
    return canvas


def _composite_watermark(img: Image.Image, wm: Image.Image, cfg: dict) -> None:
    if _effective_watermark_layout(cfg) == "corner":
        overlay = _corner_watermark(wm, cfg)
    else:
        overlay = _fit_watermark(wm)
    img.alpha_composite(overlay)


def _load_configured_watermark(
    site_id: Optional[str],
    active_theme_path: Union[str, Path],
    cfg: dict,
    *,
    theme_fallback: bool,
) -> Optional[Image.Image]:
    watermark = cfg.get("og_watermark")
    if watermark:
        watermark_text = str(watermark)
        if watermark_text.startswith("assets/"):
            local = resolve_local_asset(watermark_text, active_theme_path)
            if local:
                loaded = _load_rgba(local)
                if loaded is not None:
                    return loaded
        if watermark_text.startswith("images/") or watermark_text.startswith(
            "assets/"
        ):
            disk = _site_asset_disk_path(site_id, watermark_text)
            if disk:
                loaded = _load_rgba(disk)
                if loaded is not None:
                    return loaded
        local = resolve_local_asset(watermark, active_theme_path)
        if local:
            loaded = _load_rgba(local)
            if loaded is not None:
                return loaded
    if not theme_fallback:
        return None
    for candidate in (
        Path(active_theme_path) / "assets" / "images" / "watermark.png",
        cold_war_og_kit_path() / "images" / "watermark.png",
    ):
        if candidate.is_file():
            loaded = _load_rgba(candidate)
            if loaded is not None:
                return loaded
    return None


def _fit_canvas(img: Image.Image) -> Image.Image:
    return ImageOps.fit(img.convert("RGB"), (WIDTH, HEIGHT), centering=(0.5, 0.5))


def decode_preview_data_url(data_url: str) -> Image.Image:
    """Decode an in-memory ``data:image/...;base64,...`` for OG preview only."""
    text = (data_url or "").strip()
    match = _DATA_URL_RE.match(text)
    if not match:
        raise ValueError("Invalid image data URL")
    payload = re.sub(r"\s+", "", match.group(2))
    try:
        raw = base64.b64decode(payload, validate=True)
    except Exception as exc:
        raise ValueError("Invalid image data URL") from exc
    if len(raw) > PREVIEW_DATA_URL_MAX_DECODED:
        raise ValueError("Image data URL exceeds 4 MiB")
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception as exc:
        raise ValueError("Invalid image data URL") from exc
    return img


def _fit_watermark(wm: Image.Image) -> Image.Image:
    wm = wm.convert("RGBA")
    if wm.size == (WIDTH, HEIGHT):
        return wm
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    fitted = ImageOps.contain(wm, (WIDTH, HEIGHT))
    x = (WIDTH - fitted.width) // 2
    y = (HEIGHT - fitted.height) // 2
    canvas.paste(fitted, (x, y), fitted)
    return canvas


def _blank_canvas(cfg: dict) -> Image.Image:
    color = hex_to_rgb(cfg.get("og_bar_color"), (0, 0, 0))
    return Image.new("RGB", (WIDTH, HEIGHT), color)


def _open_fitted(path: Union[str, Path]) -> Optional[Image.Image]:
    try:
        with Image.open(path) as img:
            loaded = img.copy()
        return _fit_canvas(loaded)
    except Exception:
        return None


def load_fallback_hero(
    site_id: Optional[str],
    active_theme_path: Union[str, Path],
    cfg: dict,
) -> Image.Image:
    """Load generator fallback hero: site override → theme → OG kit → solid canvas."""
    hero_cfg = cfg.get("og_default_hero")
    if hero_cfg:
        text = str(hero_cfg)
        if text.startswith("images/") or text.startswith("assets/"):
            disk = _site_asset_disk_path(site_id, text)
            if disk:
                fitted = _open_fitted(disk)
                if fitted is not None:
                    return fitted
        local = resolve_local_asset(hero_cfg, active_theme_path)
        if local:
            fitted = _open_fitted(local)
            if fitted is not None:
                return fitted

    theme_path = Path(active_theme_path)
    for candidate in (
        theme_path / "assets" / "images" / "defaulthero.jpg",
        cold_war_og_kit_path() / "images" / "defaulthero.jpg",
    ):
        if candidate.is_file():
            fitted = _open_fitted(candidate)
            if fitted is not None:
                return fitted

    return _blank_canvas(cfg)


def apply_watermark(
    img: Image.Image,
    site_id: Optional[str],
    active_theme_path: Union[str, Path],
    cfg: dict,
    watermark_image: Optional[Image.Image] = None,
):
    if not cfg.get("og_watermark_enabled", True):
        return
    try:
        source = str(cfg.get("og_watermark_source") or "").strip().lower()
        wm: Optional[Image.Image] = None
        if source == "logo":
            logo = site_raster_logo_path(site_id)
            if logo is None:
                return
            wm = _load_rgba(logo)
        elif watermark_image is not None:
            wm = watermark_image.convert("RGBA")
        elif source == "custom":
            wm = _load_configured_watermark(
                site_id, active_theme_path, cfg, theme_fallback=False
            )
        else:
            wm = _load_configured_watermark(
                site_id, active_theme_path, cfg, theme_fallback=True
            )
        if wm is None:
            return
        _composite_watermark(img, wm, cfg)
    except Exception:
        pass


def _hero_from_source(
    hero_source: HeroSource,
    *,
    site_id: Optional[str],
    active_theme_path: Union[str, Path],
    cfg: dict,
) -> Image.Image:
    if isinstance(hero_source, Image.Image):
        return _fit_canvas(hero_source)

    if hero_source:
        text = str(hero_source)
        path = Path(text)
        if path.is_file():
            fitted = _open_fitted(path)
            if fitted is not None:
                return fitted
        if text.startswith("images/") or text.startswith("assets/") or "/" in text:
            disk = _site_asset_disk_path(site_id, text)
            if disk:
                fitted = _open_fitted(disk)
                if fitted is not None:
                    return fitted
            local = resolve_local_asset(text, active_theme_path)
            if local:
                fitted = _open_fitted(local)
                if fitted is not None:
                    return fitted

    return load_fallback_hero(site_id, active_theme_path, cfg)


def render_og_image(
    title: str,
    cfg: dict,
    *,
    site_id: Optional[str],
    theme_path: Union[str, Path],
    hero_source: HeroSource = None,
    watermark_image: Optional[Image.Image] = None,
) -> bytes:
    """Render one 1200×630 JPEG using the publish look. Does not write files."""
    img = _hero_from_source(
        hero_source,
        site_id=site_id,
        active_theme_path=theme_path,
        cfg=cfg,
    )
    img = apply_color_grade(img, cfg)
    draw = ImageDraw.Draw(img)
    draw_accent_bar(draw, cfg)
    paths = font_paths_for(theme_path, cfg)
    draw_headline(draw, title or "", paths, cfg)
    apply_watermark(
        img, site_id, theme_path, cfg, watermark_image=watermark_image
    )

    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=JPEG_QUALITY)
    return buf.getvalue()


def _preview_cache_key(
    title: str,
    cfg: Mapping[str, Any],
    *,
    site_id: Optional[str],
    theme_path: Union[str, Path],
    hero_source: HeroSource,
    watermark_image: Optional[Image.Image] = None,
) -> Optional[str]:
    if isinstance(hero_source, Image.Image) or watermark_image is not None:
        return None
    source = str(cfg.get("og_watermark_source") or "").strip().lower()
    logo_fp = ""
    if source == "logo":
        logo = site_raster_logo_path(site_id)
        if logo is not None:
            try:
                st = logo.stat()
                logo_fp = f"{logo}:{st.st_mtime_ns}:{st.st_size}"
            except OSError:
                logo_fp = str(logo)
    payload = {
        "title": title,
        "cfg": dict(cfg),
        "site_id": site_id or "",
        "theme_path": str(theme_path),
        "hero": "" if hero_source is None else str(hero_source),
        "logo": logo_fp,
    }
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def render_og_preview(
    title: str,
    cfg: dict,
    *,
    site_id: Optional[str],
    theme_path: Union[str, Path],
    hero_source: HeroSource = None,
    watermark_image: Optional[Image.Image] = None,
) -> bytes:
    """Like ``render_og_image`` with a small in-process cache for repeat clicks."""
    key = _preview_cache_key(
        title,
        cfg,
        site_id=site_id,
        theme_path=theme_path,
        hero_source=hero_source,
        watermark_image=watermark_image,
    )
    if key and key in _preview_cache:
        _preview_cache.move_to_end(key)
        return _preview_cache[key]
    jpeg = render_og_image(
        title,
        cfg,
        site_id=site_id,
        theme_path=theme_path,
        hero_source=hero_source,
        watermark_image=watermark_image,
    )
    if key:
        _preview_cache[key] = jpeg
        _preview_cache.move_to_end(key)
        while len(_preview_cache) > _PREVIEW_CACHE_MAX:
            _preview_cache.popitem(last=False)
    return jpeg


def clear_preview_cache() -> None:
    _preview_cache.clear()
