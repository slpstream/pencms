import configparser
import os
import re
import sys
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

# Ensure that the app directory is in sys.path to resolve services, models imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.storage_provider import (
    BaseStorageProvider,
    LocalStorageProvider,
)

BASE_DIR = Path(__file__).resolve().parent.parent
if "gvfs/sftp:" in str(BASE_DIR):
    parts = str(BASE_DIR).split(",user=")
    if len(parts) > 1:
        subparts = parts[1].split("/", 1)
        if len(subparts) > 1:
            BASE_DIR = Path("/" + subparts[1])

_config = configparser.ConfigParser()
_config.read(BASE_DIR / "config.ini")

# API Server Port
API_PORT = _config.getint("Server", "api_port", fallback=8000)
if API_PORT < 1 or API_PORT > 65535:
    API_PORT = 8000


def get_preview_base_url() -> Optional[str]:
    """PHP public-front origin as reachable FROM the API process.

    Env ``PENCMS_PREVIEW_BASE_URL`` wins over ``[Preview] base_url``.
    Unset/empty is OK — inspect tools return PREVIEW_UNREACHABLE; the
    server still boots. Never infer from the incoming API Host header.
    """
    env = os.environ.get("PENCMS_PREVIEW_BASE_URL", "").strip()
    raw = env or _config.get("Preview", "base_url", fallback="").strip()
    origin = raw.rstrip("/")
    return origin or None


def _is_uri(s: str) -> bool:
    """Return True if s looks like a URI scheme (contains :// and scheme is compliant with RFC 3986)."""
    if "://" in s:
        scheme = s.split("://", 1)[0]
        if not scheme or not scheme[0].isalpha():
            return False
        return all(c.isalnum() or c in "+-." for c in scheme)
    return False


# Read explicit types from config
_content_type = _config.get("Paths", "content_storage_type", fallback=None)
_assets_type = _config.get("Paths", "assets_storage_type", fallback=None)

# Resolve local paths
_content_dir_raw = _config.get("Paths", "content_dir")
_assets_dir_raw = _config.get("Paths", "assets_dir")

from services.storage_registry import SSH_STORAGE_PRO_POINTER, get_storage_type


class UnknownStorageTypeError(RuntimeError):
    """Raised when config.ini asks for a storage type Core does not register."""


class _DeferredStorage:
    """Proxy until ``bind_registered_storage()`` after the overlay hook.

    ``from config import content_storage`` at import time must keep working
    when Pro registers ``ssh`` after this module has already loaded.
    """

    def __init__(self, which: str, uri: str, secret_key: str):
        self._which = which
        self._uri = uri
        self._secret_key = secret_key
        self._inner = None

    def bind(self):
        factory = get_storage_type("ssh")
        if factory is None:
            raise UnknownStorageTypeError(
                f"{self._which} storage_type=ssh. {SSH_STORAGE_PRO_POINTER}"
            )
        inner = factory(self._uri, secret_key=self._secret_key)
        if cache_enabled:
            from services.storage_provider import CachedStorageProvider

            inner = CachedStorageProvider(inner, ttl=cache_ttl)
        self._inner = inner
        return inner

    def _resolve(self):
        if self._inner is None:
            self.bind()
        return self._inner

    def __getattr__(self, name):
        return getattr(self._resolve(), name)


def bind_registered_storage() -> None:
    """Resolve deferred SSH storage after ``init_pro`` (or refuse on Core)."""
    if isinstance(content_storage, _DeferredStorage):
        content_storage.bind()
    if isinstance(assets_storage, _DeferredStorage):
        assets_storage.bind()


# Handle Content Directory
if _content_type == "ssh" or (_content_type is None and _is_uri(_content_dir_raw)):
    if _content_dir_raw.startswith("sftp://"):
        content_storage = _DeferredStorage(
            "content", _content_dir_raw, "CONTENT_SFTP_PASS"
        )
        CONTENT_DIR_PATH = None  # No local path for remote storage
    else:
        raise NotImplementedError(f"Unsupported URI scheme: {_content_dir_raw}")
else:
    # If explicitly local/git, ensure the path isn't a URI (prevents "stuck" SSH on switch)
    if _is_uri(_content_dir_raw):
        _content_dir_raw = "../pencms-data/content"
    CONTENT_DIR_PATH = (BASE_DIR / _content_dir_raw).resolve()
    CONTENT_DIR_PATH.mkdir(exist_ok=True, parents=True)
    content_storage = None  # Will be set by factory below

# Handle Assets Directory
if _assets_type == "ssh" or (_assets_type is None and _is_uri(_assets_dir_raw)):
    if _assets_dir_raw.startswith("sftp://"):
        assets_storage = _DeferredStorage(
            "assets", _assets_dir_raw, "ASSETS_SFTP_PASS"
        )
        ASSETS_DIR_PATH = None  # No local path for remote storage
    else:
        raise NotImplementedError(f"Unsupported URI scheme: {_assets_dir_raw}")
else:
    # If explicitly local/git, ensure the path isn't a URI
    if _is_uri(_assets_dir_raw):
        _assets_dir_raw = "../pencms-data/assets"
    ASSETS_DIR_PATH = (BASE_DIR / _assets_dir_raw).resolve()
    ASSETS_DIR_PATH.mkdir(exist_ok=True, parents=True)
    assets_storage = None  # Will be set by factory below

# Instantiate Storage Providers
from services.storage_provider import GitStorageProvider


def get_storage_provider(
    base_path: Path, storage_type: Optional[str] = None
) -> BaseStorageProvider:
    # 1. Explicit Choice
    if storage_type == "git":
        return GitStorageProvider(str(base_path))
    if storage_type == "local":
        return LocalStorageProvider(str(base_path))

    # 2. Auto-detection Fallback
    if (base_path / ".git").exists():
        return GitStorageProvider(str(base_path))

    return LocalStorageProvider(str(base_path))


# Only use factory for local paths (URI-based providers are already instantiated above)
if content_storage is None and CONTENT_DIR_PATH is not None:
    content_storage = get_storage_provider(CONTENT_DIR_PATH, _content_type)
if assets_storage is None and ASSETS_DIR_PATH is not None:
    assets_storage = get_storage_provider(ASSETS_DIR_PATH, _assets_type)

# Caching Configuration
_cache_enabled_str = _config.get("Paths", "cache_enabled", fallback="true")
cache_enabled = _cache_enabled_str.lower() in ("true", "1", "yes", "on")
_cache_ttl_str = _config.get("Paths", "cache_ttl", fallback="0")
try:
    cache_ttl = int(_cache_ttl_str)
except ValueError:
    cache_ttl = 0

if cache_enabled:
    from services.storage_provider import CachedStorageProvider

    if content_storage is not None and not isinstance(content_storage, _DeferredStorage):
        content_storage = CachedStorageProvider(content_storage, ttl=cache_ttl)
    if assets_storage is not None and not isinstance(assets_storage, _DeferredStorage):
        assets_storage = CachedStorageProvider(assets_storage, ttl=cache_ttl)

# Legacy Compatibility (to be phased out as services are refactored)
CONTENT_DIR = CONTENT_DIR_PATH
ASSETS_DIR = ASSETS_DIR_PATH

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
IMAGE_MAX_DIMENSION = 1600
IMAGE_QUALITY = 82
IMAGE_CONVERT_TO_WEBP = True
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

DOMAINS = ["blog"]
STATUS_VALUES = ["stub", "draft", "unpublished", "published"]

# --- Taxonomy State ---

TAXONOMY = {}
PRIMARY_VOCABULARY = None
REQUIRED_FIELDS = ["name", "status"]
PRIMARY_TERMS = []

# --- Collection schema state (Phase 5: Dynamic Schema Discovery) ---
#
# `COLLECTIONS_SCHEMA` holds the parsed `collections.yaml` payload — the
# authoritative schema surface advertised to the AI assistant. It is
# loaded at startup by `reload_collections_schema()` and served to the
# sidebar via `GET /api/ai/schemas`.
#
# The shape mirrors `reload_taxonomy()`'s pattern: a module-level dict
# populated by a `reload_*()` function, so a future admin UI can call the
# reload endpoint after editing the YAML without restarting the server.
COLLECTIONS_SCHEMA = {}

# Per-request taxonomy override (set by content write paths / admin).
TaxonomySnapshot = Dict[str, Any]
_active_taxonomy_ctx: ContextVar[Optional[TaxonomySnapshot]] = ContextVar(
    "pencms_active_taxonomy", default=None
)
_taxonomy_site_cache: Dict[str, TaxonomySnapshot] = {}
_collections_site_cache: Dict[str, dict] = {}


def _term_to_slug(term: str) -> str:
    """Convert a taxonomy term to a filesystem-safe slug."""
    slug = term.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


TAXONOMY_PATH = BASE_DIR.parent / "core" / "schemas" / "taxonomy.yaml"
COLLECTIONS_SCHEMA_PATH = BASE_DIR.parent / "core" / "schemas" / "collections.yaml"


def _parse_taxonomy_data(tax_data: dict) -> TaxonomySnapshot:
    """Build a taxonomy snapshot dict from raw YAML data."""
    vocabularies = tax_data.get("vocabularies", {}) or {}
    primary_vocabulary = tax_data.get("primary_vocabulary", None)
    required_fields = REQUIRED_FIELDS
    _req = tax_data.get("required_fields")
    if isinstance(_req, list) and len(_req) > 0:
        required_fields = _req
    primary_terms = []
    if primary_vocabulary and primary_vocabulary in vocabularies:
        _vocab = vocabularies[primary_vocabulary]
        primary_terms = [_term_to_slug(t) for t in _vocab.get("terms", [])]
    return {
        "vocabularies": vocabularies,
        "primary_vocabulary": primary_vocabulary,
        "required_fields": list(required_fields),
        "primary_terms": primary_terms,
        "raw": tax_data,
    }


def get_active_taxonomy() -> TaxonomySnapshot:
    """Return request-scoped taxonomy, or install-wide seed globals."""
    snap = _active_taxonomy_ctx.get()
    if snap is not None:
        return snap
    return {
        "vocabularies": TAXONOMY,
        "primary_vocabulary": PRIMARY_VOCABULARY,
        "required_fields": list(REQUIRED_FIELDS),
        "primary_terms": list(PRIMARY_TERMS),
        "raw": {
            "vocabularies": TAXONOMY,
            "primary_vocabulary": PRIMARY_VOCABULARY,
            "required_fields": list(REQUIRED_FIELDS),
        },
    }


def set_active_taxonomy(snapshot: Optional[TaxonomySnapshot]):
    """Set (or clear) the request-scoped taxonomy ContextVar. Returns a reset token."""
    return _active_taxonomy_ctx.set(snapshot)


def reset_active_taxonomy(token) -> None:
    _active_taxonomy_ctx.reset(token)


def invalidate_taxonomy_cache(site_id: Optional[str] = None) -> None:
    if site_id is None:
        _taxonomy_site_cache.clear()
    else:
        _taxonomy_site_cache.pop(site_id, None)


def invalidate_collections_cache(site_id: Optional[str] = None) -> None:
    if site_id is None:
        _collections_site_cache.clear()
    else:
        _collections_site_cache.pop(site_id, None)


def reload_taxonomy():
    """Reloads install-wide seed taxonomy.yaml from disk into memory."""
    global TAXONOMY, PRIMARY_VOCABULARY, REQUIRED_FIELDS, PRIMARY_TERMS

    _taxonomy_path = TAXONOMY_PATH
    if not _taxonomy_path.exists():
        print(f"Warning: taxonomy.yaml not found at {_taxonomy_path}", file=sys.stderr)
        return

    try:
        with open(_taxonomy_path, "r", encoding="utf-8") as f:
            _tax_data = yaml.safe_load(f) or {}

        snap = _parse_taxonomy_data(_tax_data)
        TAXONOMY = snap["vocabularies"]
        PRIMARY_VOCABULARY = snap["primary_vocabulary"]
        REQUIRED_FIELDS = snap["required_fields"]
        PRIMARY_TERMS = snap["primary_terms"]

    except Exception as e:
        print(f"Error: Failed to load taxonomy.yaml: {e}", file=sys.stderr)


def reload_collections_schema():
    """Reload install-wide seed `collections.yaml` from disk into memory.

    Mirrors `reload_taxonomy()`: populates the module-level
    `COLLECTIONS_SCHEMA` dict from the YAML file at
    `COLLECTIONS_SCHEMA_PATH`. Called at startup and (in future) from an
    admin reload endpoint. Silently no-ops if the file is missing so the
    server still boots on a fresh checkout where Phase 5 has not yet
    added the file — every collection-aware caller treats an empty dict
    as "no schema advertised".
    """
    global COLLECTIONS_SCHEMA

    _path = COLLECTIONS_SCHEMA_PATH
    if not _path.exists():
        print(f"Warning: collections.yaml not found at {_path}", file=sys.stderr)
        COLLECTIONS_SCHEMA = {}
        return

    try:
        with open(_path, "r", encoding="utf-8") as f:
            _data = yaml.safe_load(f) or {}
        COLLECTIONS_SCHEMA = _data.get("collections", {})
    except Exception as e:
        print(f"Error: Failed to load collections.yaml: {e}", file=sys.stderr)
        COLLECTIONS_SCHEMA = {}


def load_taxonomy_for_site(site_id: str) -> TaxonomySnapshot:
    """Load per-site taxonomy (write empty slate if missing). Cached by site_id."""
    if site_id in _taxonomy_site_cache:
        return _taxonomy_site_cache[site_id]

    from services.site_service import _empty_taxonomy_dict, site_taxonomy_relpath

    rel = site_taxonomy_relpath(site_id)
    tax_data = None

    # Prefer local content path for sync reads
    if CONTENT_DIR_PATH is not None:
        local = CONTENT_DIR_PATH / rel
        if not local.is_file():
            local.parent.mkdir(parents=True, exist_ok=True)
            empty = _empty_taxonomy_dict()
            with open(local, "w", encoding="utf-8") as f:
                yaml.safe_dump(empty, f, default_flow_style=False, sort_keys=False)
            tax_data = empty
        else:
            with open(local, "r", encoding="utf-8") as f:
                tax_data = yaml.safe_load(f) or {}

    if tax_data is None and TAXONOMY_PATH.is_file():
        with open(TAXONOMY_PATH, "r", encoding="utf-8") as f:
            tax_data = yaml.safe_load(f) or {}

    if tax_data is None:
        tax_data = _empty_taxonomy_dict()

    snap = _parse_taxonomy_data(tax_data)
    _taxonomy_site_cache[site_id] = snap
    return snap


def load_collections_for_site(site_id: str) -> dict:
    """Load per-site collections schema (seed-copy if missing)."""
    if site_id in _collections_site_cache:
        return _collections_site_cache[site_id]

    from services.site_service import site_collections_relpath

    rel = site_collections_relpath(site_id)
    collections = {}

    if CONTENT_DIR_PATH is not None:
        local = CONTENT_DIR_PATH / rel
        if not local.is_file() and COLLECTIONS_SCHEMA_PATH.is_file():
            local.parent.mkdir(parents=True, exist_ok=True)
            import shutil

            shutil.copy2(COLLECTIONS_SCHEMA_PATH, local)
        if local.is_file():
            with open(local, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            collections = data.get("collections", {}) or {}
        else:
            collections = dict(COLLECTIONS_SCHEMA)
    else:
        collections = dict(COLLECTIONS_SCHEMA)

    _collections_site_cache[site_id] = collections
    return collections


# Initial load
reload_taxonomy()
reload_collections_schema()
