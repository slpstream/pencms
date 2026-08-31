"""Read/write site taxonomy.yaml (vocabularies + terms).

Publishing Rules (``required_fields``) stay human Structure-only. MCP replace
and upsert preserve on-disk ``required_fields``. Vocab key ``category`` is
reserved (conflicts with the primary classification field).
"""

from __future__ import annotations

import copy
import re
import shutil
from typing import Any, Dict, List, Optional

import yaml

import config
from services.site_service import site_taxonomy_relpath

RESERVED_VOCAB_KEY = "category"
VOCAB_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class TaxonomyError(ValueError):
    """Operator-facing taxonomy validation error."""


def slugify_vocab_key(raw: str) -> str:
    slug = (raw or "").strip().lower().replace(" ", "_")
    slug = re.sub(r"[^a-z0-9_]", "", slug)
    return slug


def empty_vocabulary(label: str, *, controlled: bool = True) -> Dict[str, Any]:
    return {
        "label": label,
        "type": "flat",
        "controlled": bool(controlled),
        "required": False,
        "terms": [],
    }


def load_taxonomy_document(site_id: str) -> Dict[str, Any]:
    """Return the persistable taxonomy.yaml mapping for a site."""
    snap = config.load_taxonomy_for_site(site_id)
    raw = snap.get("raw") or {}
    vocabs = raw.get("vocabularies")
    if not isinstance(vocabs, dict):
        vocabs = dict(snap.get("vocabularies") or {})
    primary = raw.get("primary_vocabulary")
    if primary is None:
        primary = snap.get("primary_vocabulary") or ""
    required = raw.get("required_fields")
    if not isinstance(required, list) or not required:
        required = list(snap.get("required_fields") or [])
    return {
        "vocabularies": copy.deepcopy(vocabs),
        "primary_vocabulary": primary or "",
        "required_fields": list(required),
    }


def public_taxonomy_view(site_id: str) -> Dict[str, Any]:
    """Agent-facing view: vocabs + primary, not Publishing Rules."""
    snap = config.load_taxonomy_for_site(site_id)
    doc = load_taxonomy_document(site_id)
    return {
        "vocabularies": doc["vocabularies"],
        "primary_vocabulary": doc["primary_vocabulary"] or "",
        "primary_terms": list(snap.get("primary_terms") or []),
        "site_id": site_id,
    }


def _normalize_vocab(payload: Any, *, key: str, existing: Optional[dict] = None) -> Dict[str, Any]:
    base = empty_vocabulary(key.replace("_", " ").title())
    if isinstance(existing, dict):
        base.update({k: copy.deepcopy(v) for k, v in existing.items() if k in base or k == "terms"})
        if "terms" not in base or not isinstance(base.get("terms"), list):
            base["terms"] = []
    if not isinstance(payload, dict):
        payload = {}
    label = payload.get("label")
    if label is not None:
        label_s = str(label).strip()
        if not label_s:
            raise TaxonomyError(f"Vocabulary '{key}' needs a non-empty label.")
        base["label"] = label_s
    if "controlled" in payload and payload.get("controlled") is not None:
        base["controlled"] = bool(payload.get("controlled"))
    if "required" in payload and payload.get("required") is not None:
        base["required"] = bool(payload.get("required"))
    if "type" in payload and payload.get("type"):
        base["type"] = str(payload.get("type"))
    if "terms" in payload and payload.get("terms") is not None:
        terms = payload.get("terms")
        if not isinstance(terms, list):
            raise TaxonomyError(f"Vocabulary '{key}' terms must be a list of strings.")
        cleaned: List[str] = []
        seen = set()
        for term in terms:
            text = str(term).strip()
            if not text:
                continue
            if text in seen:
                continue
            seen.add(text)
            cleaned.append(text)
        base["terms"] = cleaned
    elif "terms" not in base or not isinstance(base.get("terms"), list):
        base["terms"] = []
    return base


def _assert_vocab_key(key: str) -> str:
    slug = slugify_vocab_key(key)
    if not slug or not VOCAB_KEY_RE.match(slug):
        raise TaxonomyError(
            "Vocabulary key must start with a letter and use lowercase letters, digits, and underscores."
        )
    if slug == RESERVED_VOCAB_KEY:
        raise TaxonomyError(
            "The vocabulary name 'category' is reserved to prevent conflicts with the primary classification field."
        )
    return slug


def _validate_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    vocabs_in = doc.get("vocabularies")
    if not isinstance(vocabs_in, dict):
        raise TaxonomyError("Missing 'vocabularies' key")
    if RESERVED_VOCAB_KEY in vocabs_in:
        raise TaxonomyError(
            "The vocabulary name 'category' is reserved to prevent conflicts with the primary classification field."
        )
    normalized: Dict[str, Any] = {}
    for raw_key, payload in vocabs_in.items():
        key = _assert_vocab_key(str(raw_key))
        if key in normalized:
            raise TaxonomyError(f"Duplicate vocabulary key '{key}'.")
        normalized[key] = _normalize_vocab(payload, key=key)
    primary = doc.get("primary_vocabulary") or ""
    primary = str(primary).strip()
    if primary:
        primary = _assert_vocab_key(primary)
        if primary not in normalized:
            raise TaxonomyError(
                f"primary_vocabulary '{primary}' is not in vocabularies."
            )
    elif normalized:
        primary = next(iter(normalized))
    required = doc.get("required_fields")
    if not isinstance(required, list) or not required:
        required = ["name", "status"]
    return {
        "vocabularies": normalized,
        "primary_vocabulary": primary,
        "required_fields": list(required),
    }


async def persist_taxonomy_document(site_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Write a full taxonomy.yaml document and invalidate the site cache."""
    validated = _validate_document(data)
    rel = site_taxonomy_relpath(site_id)
    text = yaml.dump(
        validated, default_flow_style=False, allow_unicode=True, sort_keys=False
    )
    content_path = config.CONTENT_DIR_PATH
    if content_path is not None:
        target = content_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        backup_path = target.with_suffix(".yaml.bak")
        if target.exists():
            shutil.copy2(target, backup_path)
        try:
            target.write_text(text, encoding="utf-8")
        except Exception:
            if backup_path.exists():
                shutil.copy2(backup_path, target)
            raise
    else:
        storage = config.content_storage
        parent = "/".join(rel.split("/")[:-1])
        if parent:
            await storage.mkdir(parent)
        await storage.write(rel, text)
    config.invalidate_taxonomy_cache(site_id)
    return public_taxonomy_view(site_id)


async def replace_taxonomy(
    site_id: str,
    *,
    primary_vocabulary: str,
    vocabularies: Dict[str, Any],
) -> Dict[str, Any]:
    existing = load_taxonomy_document(site_id)
    incoming_keys = {slugify_vocab_key(str(k)) for k in (vocabularies or {})}
    current_primary = existing.get("primary_vocabulary") or ""
    new_primary = (primary_vocabulary or "").strip()
    if (
        current_primary
        and current_primary not in incoming_keys
        and slugify_vocab_key(new_primary) != current_primary
        and slugify_vocab_key(new_primary) not in incoming_keys
    ):
        raise TaxonomyError(
            "Cannot drop the primary vocabulary without switching first. "
            "Set primary_vocabulary to a remaining key (or include the current primary)."
        )
    payload = {
        "vocabularies": vocabularies or {},
        "primary_vocabulary": new_primary,
        "required_fields": existing.get("required_fields") or ["name", "status"],
    }
    return await persist_taxonomy_document(site_id, payload)


async def upsert_vocabulary(
    site_id: str,
    key: str,
    *,
    label: Optional[str] = None,
    controlled: Optional[bool] = None,
    terms: Optional[List[str]] = None,
) -> Dict[str, Any]:
    slug = _assert_vocab_key(key)
    doc = load_taxonomy_document(site_id)
    vocabs = doc["vocabularies"]
    patch: Dict[str, Any] = {}
    if label is not None:
        patch["label"] = label
    if controlled is not None:
        patch["controlled"] = controlled
    if terms is not None:
        patch["terms"] = terms
    vocabs[slug] = _normalize_vocab(patch, key=slug, existing=vocabs.get(slug))
    if not doc.get("primary_vocabulary") and len(vocabs) == 1:
        doc["primary_vocabulary"] = slug
    doc["vocabularies"] = vocabs
    return await persist_taxonomy_document(site_id, doc)


async def delete_vocabulary(site_id: str, key: str) -> Dict[str, Any]:
    slug = _assert_vocab_key(key)
    doc = load_taxonomy_document(site_id)
    vocabs = doc["vocabularies"]
    if slug not in vocabs:
        raise KeyError(f"Vocabulary '{slug}' not found")
    if slug == (doc.get("primary_vocabulary") or ""):
        raise TaxonomyError(
            "Cannot remove the primary vocabulary. Switch the primary vocabulary first."
        )
    del vocabs[slug]
    doc["vocabularies"] = vocabs
    return await persist_taxonomy_document(site_id, doc)


async def add_taxonomy_term(site_id: str, key: str, term: str) -> Dict[str, Any]:
    slug = _assert_vocab_key(key)
    text = (term or "").strip()
    if not text:
        raise TaxonomyError("Term cannot be empty.")
    doc = load_taxonomy_document(site_id)
    vocabs = doc["vocabularies"]
    if slug not in vocabs:
        raise KeyError(f"Vocabulary '{slug}' not found")
    vocab = _normalize_vocab({}, key=slug, existing=vocabs[slug])
    if text in vocab["terms"]:
        raise TaxonomyError(f"Term '{text}' already exists in '{slug}'.")
    vocab["terms"].append(text)
    vocabs[slug] = vocab
    doc["vocabularies"] = vocabs
    return await persist_taxonomy_document(site_id, doc)


async def remove_taxonomy_term(site_id: str, key: str, term: str) -> Dict[str, Any]:
    slug = _assert_vocab_key(key)
    text = (term or "").strip()
    if not text:
        raise TaxonomyError("Term cannot be empty.")
    doc = load_taxonomy_document(site_id)
    vocabs = doc["vocabularies"]
    if slug not in vocabs:
        raise KeyError(f"Vocabulary '{slug}' not found")
    vocab = _normalize_vocab({}, key=slug, existing=vocabs[slug])
    if text not in vocab["terms"]:
        raise KeyError(f"Term '{text}' not found in '{slug}'")
    vocab["terms"] = [t for t in vocab["terms"] if t != text]
    vocabs[slug] = vocab
    doc["vocabularies"] = vocabs
    return await persist_taxonomy_document(site_id, doc)


async def set_primary_vocabulary(site_id: str, key: str) -> Dict[str, Any]:
    slug = _assert_vocab_key(key)
    doc = load_taxonomy_document(site_id)
    if slug not in doc["vocabularies"]:
        raise KeyError(f"Vocabulary '{slug}' not found")
    doc["primary_vocabulary"] = slug
    return await persist_taxonomy_document(site_id, doc)
