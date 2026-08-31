import frontmatter
from typing import Any, Mapping, Optional, List
from datetime import datetime, timezone
import re
import logging
import time
import json

from config import content_storage
from models.page import Page, PageFrontmatter, PageResponse
from services.concurrency import attach_page_version
from services.i18n_service import (
    ContentI18nError,
    ContentIdentity,
    LanguageConfig,
    content_identity_from_path,
    is_live_translation,
    manifest_partial_ids,
    new_translation_group,
    normalize_language_config,
    normalize_requested_language,
    validate_translation_group,
)
from services.site_service import (
    DEFAULT_SITE_ID,
    get_site,
    get_site_content_prefix,
    list_sites,
)

logger = logging.getLogger("pencms.files")


# --- Helpers ---

def name_to_id(name: str) -> str:
    """Convert a page name to a filesystem-safe ID."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug


async def unique_post_slug(site_id: str, base: str) -> str:
    """Keep ``base`` when free; otherwise ``{base}-{UTC YYYYMMDD-HHMMSS}``, then ``-2``, ``-3``, …"""
    if await resolve_path(base, site_id=site_id) is None:
        return base
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    candidate = f"{base}-{stamp}"
    n = 2
    while await resolve_path(candidate, site_id=site_id) is not None:
        candidate = f"{base}-{stamp}-{n}"
        n += 1
    return candidate


def sanitize_slug(slug: str) -> str:
    """Normalize a user-provided slug to be filesystem-safe."""
    slug = slug.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug


def is_partial(path: str) -> bool:
    """Partials are files whose name starts with an underscore."""
    # path is a relative string like "person/elena/_bio.md"
    filename = path.split("/")[-1]
    return filename.startswith("_")


def site_id_from_filepath(rel_path: str) -> str:
    """Extract site_id from a storage path under ``sites/{id}/…``."""
    parts = rel_path.replace("\\", "/").strip("/").split("/")
    if len(parts) >= 2 and parts[0] == "sites":
        return parts[1]
    return DEFAULT_SITE_ID


def join_site_path(site_id: str, *parts: str) -> str:
    """Join a site content prefix with relative path parts (no traversal)."""
    prefix = get_site_content_prefix(site_id)
    cleaned = []
    for p in parts:
        if not p:
            continue
        for seg in str(p).replace("\\", "/").split("/"):
            if not seg or seg == ".":
                continue
            if seg == ".." or seg.startswith(".."):
                raise ValueError("Path traversal not allowed")
            cleaned.append(seg)
    if not cleaned:
        return prefix
    return f"{prefix}/{'/'.join(cleaned)}"


def get_site_language_config(site_id: str) -> LanguageConfig:
    site = get_site(site_id)
    if site is None:
        raise ValueError(f"Unknown site_id: {site_id}")
    return normalize_language_config(
        language=site.language,
        languages=site.languages,
        language_labels=site.language_labels,
        translation_automation_paused=site.translation_automation_paused,
    )


def content_identity_for_path(rel_path: str, site_id: str) -> ContentIdentity:
    return content_identity_from_path(
        rel_path,
        site_id=site_id,
        site_prefix=get_site_content_prefix(site_id),
        config=get_site_language_config(site_id),
    )


async def resolve_path(
    page_id: str,
    category: Optional[str] = None,
    site_id: str = DEFAULT_SITE_ID,
    language: Optional[str] = None,
) -> Optional[str]:
    """Resolve a page_id to its canonical relative storage path.

    Returns the relative path string if found, None otherwise.
    """
    config = get_site_language_config(site_id)
    requested = normalize_requested_language(language, config)
    if requested == config.language:
        composite = join_site_path(site_id, page_id, "index.md")
    else:
        composite = join_site_path(site_id, page_id, requested, "index.md")
    if await content_storage.exists(composite):
        return composite

    # Translations are always folder documents. Never fall back to default.
    if requested != config.language:
        return None

    # Legacy standalone files remain default-language only.
    simple = join_site_path(site_id, f"{page_id}.md")
    if await content_storage.exists(simple):
        return simple

    return None


async def build_write_path(
    page_id: str,
    category: str,
    composite: bool = False,
    site_id: str = DEFAULT_SITE_ID,
    language: Optional[str] = None,
) -> str:
    """Construct the relative write path for a page."""
    config = get_site_language_config(site_id)
    requested = normalize_requested_language(language, config)
    if requested == config.language:
        page_dir = join_site_path(site_id, page_id)
    else:
        page_dir = join_site_path(site_id, page_id, requested)
    await content_storage.mkdir(page_dir)
    return f"{page_dir}/index.md"


async def _read_metadata(path: str) -> tuple[dict[str, Any], str]:
    raw = await content_storage.read(path)
    post = frontmatter.loads(raw)
    return dict(post.metadata), post.content or ""


def _teaching_error(path: str, message: str, fix: str) -> ContentI18nError:
    return ContentI18nError(f"{path}: {message} Fix: {fix}")


def _structural_identity(metadata: Mapping[str, Any]) -> dict[str, Any]:
    tags = metadata.get("tags") or []
    if not isinstance(tags, list):
        tags = [tags]
    composite = bool(metadata.get("composite") or metadata.get("posts") or metadata.get("articles"))
    taxonomy_assignments = {
        str(key): value
        for key, value in sorted(metadata.items(), key=lambda item: str(item[0]))
        if str(key).startswith("taxonomy_")
    }
    return {
        "page": bool(metadata.get("page")),
        "category": metadata.get("category") or "",
        "domain": metadata.get("domain") or "blog",
        "tags": sorted(str(tag) for tag in tags),
        "taxonomy": taxonomy_assignments,
        "composite": composite,
        "manifest": manifest_partial_ids(metadata),
    }


async def _validate_sibling_set(
    *,
    site_id: str,
    slug: str,
    default_path: str,
    translation_paths: list[str],
    group_owners: dict[str, tuple[str, str]],
) -> None:
    config = get_site_language_config(site_id)
    default_metadata, _ = await _read_metadata(default_path)
    default_identity = content_identity_for_path(default_path, site_id)

    default_fm_language = default_metadata.get("language")
    if default_fm_language is not None and default_fm_language != config.language:
        raise _teaching_error(
            default_path,
            f"frontmatter language '{default_fm_language}' does not match its default path",
            f"set language: {config.language} or omit it while the document has no siblings.",
        )

    default_group = default_metadata.get("translation_group")
    if default_group is not None:
        default_group = validate_translation_group(default_group, filepath=default_path)

    if translation_paths:
        if default_fm_language != config.language:
            raise _teaching_error(
                default_path,
                "a document with translations must declare its authoritative language",
                f"add language: {config.language}.",
            )
        if not default_group:
            raise _teaching_error(
                default_path,
                "a document with translations is missing translation_group",
                "add one generated tg_<32 hex> value and copy it to every sibling.",
            )

    if default_group:
        owner = group_owners.setdefault(default_group, (slug, default_path))
        if owner[0] != slug:
            raise _teaching_error(
                default_path,
                f"translation_group '{default_group}' is already owned by slug '{owner[0]}'",
                "generate a different group for this document and update all its siblings.",
            )

    source_structure = _structural_identity(default_metadata)
    seen_languages: dict[str, str] = {}
    for path in translation_paths:
        identity = content_identity_for_path(path, site_id)
        if identity.language in seen_languages:
            raise _teaching_error(
                path,
                f"duplicate locale peer for '{identity.language}' (also {seen_languages[identity.language]})",
                "keep exactly one normalized locale folder for each language.",
            )
        seen_languages[identity.language] = path

        metadata, _ = await _read_metadata(path)
        if metadata.get("language") != identity.language:
            raise _teaching_error(
                path,
                f"frontmatter language must exactly match locale folder '{identity.language}'",
                f"set language: {identity.language}.",
            )
        group = metadata.get("translation_group")
        if not group:
            raise _teaching_error(
                path,
                "translation sibling is missing translation_group",
                f"copy translation_group: {default_group or '<group from default peer>'}.",
            )
        group = validate_translation_group(group, filepath=path)
        if group != default_group:
            raise _teaching_error(
                path,
                f"translation_group '{group}' does not match default peer '{default_group}'",
                "copy the exact translation_group from the default-language index.md.",
            )
        if metadata.get("slug") not in (None, "", slug):
            raise _teaching_error(
                path,
                f"frontmatter slug '{metadata.get('slug')}' differs from path slug '{slug}'",
                f"set slug: {slug}.",
            )
        if _structural_identity(metadata) != source_structure:
            raise _teaching_error(
                path,
                "page kind, domain, taxonomy assignments, or composite manifest differs from the default peer",
                "copy page/category/domain/tags and the ordered composite part IDs from the default peer.",
            )

        if is_live_translation(metadata):
            locale_dir = "/".join(path.split("/")[:-1])
            missing = []
            for partial_id in source_structure["manifest"]:
                partial_path = f"{locale_dir}/_{partial_id}.md"
                if not await content_storage.exists(partial_path):
                    missing.append(partial_path)
            if missing:
                raise _teaching_error(
                    path,
                    f"published composite is missing locale-local partials: {', '.join(missing)}",
                    "add every translated partial or keep the sibling in draft/unpublished state.",
                )

    # Touch the parsed default identity so malformed/shadowing paths fail above.
    if default_identity.slug != slug:
        raise _teaching_error(
            default_path,
            f"path identity resolved to '{default_identity.slug}', expected '{slug}'",
            "keep the canonical index directly under its slug directory.",
        )


async def _iter_site_canonical(site_root: str, site_id: str) -> List[str]:
    """List canonical pages under one site root prefix."""
    canonical = []
    config = get_site_language_config(site_id)
    group_owners: dict[str, tuple[str, str]] = {}
    try:
        root_items = await content_storage.list_dir(site_root)
    except Exception:
        return []

    for item in root_items:
        # list_dir may return bare names or relative paths
        name = item.split("/")[-1]
        full = f"{site_root}/{name}" if not item.startswith(site_root) else item
        if await content_storage.is_dir(full):
            index_path = f"{full}/index.md"
            translation_paths: list[str] = []
            if config.active:
                if name in config.languages:
                    raise _teaching_error(
                        index_path,
                        f"slug '{name}' shadows a configured language code",
                        "rename the slug or remove that language from the site config.",
                    )
                try:
                    children = await content_storage.list_dir(full)
                except Exception:
                    children = []
                for child in children:
                    child_name = child.split("/")[-1]
                    if child_name == "comments":
                        continue
                    child_full = f"{full}/{child_name}" if not child.startswith(full) else child
                    if not await content_storage.is_dir(child_full):
                        continue
                    child_index = f"{child_full}/index.md"
                    if not await content_storage.exists(child_index):
                        continue
                    # Parsing performs normalized/configured/default-folder checks.
                    content_identity_for_path(child_index, site_id)
                    translation_paths.append(child_index)

                if translation_paths and not await content_storage.exists(index_path):
                    raise _teaching_error(
                        translation_paths[0],
                        f"translation for slug '{name}' has no default-language peer",
                        f"create {index_path} first.",
                    )
            if await content_storage.exists(index_path):
                canonical.append(index_path)
                if config.active:
                    canonical.extend(translation_paths)
                    await _validate_sibling_set(
                        site_id=site_id,
                        slug=name,
                        default_path=index_path,
                        translation_paths=translation_paths,
                        group_owners=group_owners,
                    )
        else:
            if name.endswith(".md") and not is_partial(name):
                if config.active:
                    identity = content_identity_for_path(full, site_id)
                    metadata, _ = await _read_metadata(full)
                    group = metadata.get("translation_group")
                    if metadata.get("language") not in (None, config.language):
                        raise _teaching_error(
                            full,
                            "legacy standalone files can only represent the default language",
                            f"set language: {config.language} or convert it to a folder document.",
                        )
                    if group:
                        validate_translation_group(group, filepath=full)
                        owner = group_owners.setdefault(group, (identity.slug, full))
                        if owner[0] != identity.slug:
                            raise _teaching_error(
                                full,
                                f"translation_group '{group}' is already owned by slug '{owner[0]}'",
                                "generate a different group for this document.",
                            )
                canonical.append(full)
    return canonical


async def iter_canonical_files(site_id: Optional[str] = None) -> List[str]:
    """Return canonical page paths for one site, or all sites if site_id is None."""
    if site_id is not None:
        return await _iter_site_canonical(get_site_content_prefix(site_id), site_id)

    canonical: List[str] = []
    try:
        sites = list_sites()
    except Exception:
        sites = []
    if not sites:
        # Pre-registry fallback: try default prefix
        return await _iter_site_canonical(f"sites/{DEFAULT_SITE_ID}", DEFAULT_SITE_ID)
    for site in sites:
        canonical.extend(await _iter_site_canonical(site.content_relpath, site.id))
    return canonical


async def list_sibling_records(
    page_id: str,
    *,
    site_id: str = DEFAULT_SITE_ID,
) -> list[dict[str, Any]]:
    """Read exact sibling metadata from Markdown, in configured language order."""
    config = get_site_language_config(site_id)
    default_path = join_site_path(site_id, page_id, "index.md")
    if not await content_storage.exists(default_path):
        legacy = join_site_path(site_id, f"{page_id}.md")
        if await content_storage.exists(legacy):
            metadata, _ = await _read_metadata(legacy)
            return [{
                "language": config.language,
                "filepath": legacy,
                "frontmatter": metadata,
            }]
        return []

    translation_paths = []
    if config.active:
        try:
            children = await content_storage.list_dir(
                join_site_path(site_id, page_id)
            )
        except Exception:
            children = []
        for child in children:
            child_name = child.split("/")[-1]
            path = join_site_path(site_id, page_id, child_name, "index.md")
            child_path = join_site_path(site_id, page_id, child_name)
            if (
                await content_storage.is_dir(child_path)
                and await content_storage.exists(path)
            ):
                # Parse every nested index so unknown/default/unnormalized
                # locale folders cannot hide from exact reads.
                content_identity_for_path(path, site_id)
                translation_paths.append(path)
        await _validate_sibling_set(
            site_id=site_id,
            slug=page_id,
            default_path=default_path,
            translation_paths=translation_paths,
            group_owners={},
        )

    records = []
    default_metadata, _ = await _read_metadata(default_path)
    records.append({
        "language": config.language,
        "filepath": default_path,
        "frontmatter": default_metadata,
    })
    for path in translation_paths:
        identity = content_identity_for_path(path, site_id)
        metadata, _ = await _read_metadata(path)
        records.append({
            "language": identity.language,
            "filepath": path,
            "frontmatter": metadata,
        })
    order = {language: index for index, language in enumerate(config.languages)}
    records.sort(key=lambda record: order.get(record["language"], len(order)))
    return records


async def translation_peer_summaries(
    page_id: str,
    *,
    current_language: str,
    site_id: str = DEFAULT_SITE_ID,
    live_only: bool = False,
) -> list[dict[str, Any]]:
    peers = []
    for record in await list_sibling_records(page_id, site_id=site_id):
        if record["language"] == current_language:
            continue
        metadata = record["frontmatter"]
        if live_only and not is_live_translation(metadata):
            continue
        peers.append({
            "language": record["language"],
            "status": metadata.get("status", "published"),
            "published": bool(metadata.get("published", True)),
            "needs_review": bool(metadata.get("needs_review", False)),
            "review_decision": metadata.get("review_decision"),
        })
    return peers


def path_to_id(rel_path: str) -> str:
    """Derive the page_id from a canonical relative path."""
    parts = rel_path.replace("\\", "/").strip("/").split("/")
    # Strip sites/{site_id}/ prefix when present
    if len(parts) >= 3 and parts[0] == "sites":
        parts = parts[2:]
    filename = parts[-1]
    if filename == "index.md":
        # Pattern B: <slug>/<lang>/index.md still has document identity <slug>.
        return parts[0] if parts else filename.replace(".md", "")
    return filename.replace(".md", "")

def frontmatter_to_dict(fm: PageFrontmatter) -> dict:
    """Convert the Pydantic model to a clean dict for writing."""
    raw = fm.model_dump(exclude_none=True)
    raw = {k: v for k, v in raw.items() if v != []}
    if not raw.get("pinned"):
        raw.pop("pinned", None)

    if "from_entity" in raw:
        raw["from"] = raw.pop("from_entity")
    if "to_entity" in raw:
        raw["to"] = raw.pop("to_entity")

    for key in ("temporal", "spatial"):
        if key in raw and hasattr(raw[key], "model_dump"):
            raw[key] = raw[key].model_dump(exclude_none=True)

    if "relations" in raw:
        raw["relations"] = [
            r.model_dump(exclude_none=True) if hasattr(r, "model_dump") else r
            for r in raw["relations"]
        ]

    return raw


def dict_to_frontmatter(data: dict) -> dict:
    """Rename from/to back to from_entity/to_entity."""
    if "from" in data:
        data["from_entity"] = data.pop("from")
    if "to" in data:
        data["to_entity"] = data.pop("to")
    return data


def _enrich_page_data(rel_path: str, fm_dict: dict, content: Optional[str] = None):
    """Enrich page frontmatter with inferred metadata and aliases."""
    fm_dict["is_legacy"] = False

    if "status" not in fm_dict:
        fm_dict["status"] = "published"
    if "published" not in fm_dict:
        fm_dict["published"] = True
    if "domain" not in fm_dict:
        fm_dict["domain"] = "blog"

    if "title" not in fm_dict and "name" not in fm_dict and content:
        h1_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if h1_match:
            fm_dict["title"] = h1_match.group(1).strip()
            fm_dict["name"] = fm_dict["title"]
            fm_dict["is_legacy"] = True

    if "name" not in fm_dict and "title" in fm_dict:
        fm_dict["name"] = fm_dict["title"]
        fm_dict["is_legacy"] = True

    if "category" not in fm_dict and "type" in fm_dict:
        fm_dict["category"] = fm_dict["type"]
        fm_dict["is_legacy"] = True

    if "category" not in fm_dict:
        fm_dict["is_legacy"] = True
        if fm_dict.get("page") in (True, "true"):
            fm_dict["category"] = ""
        else:
            fm_dict["category"] = "general"
    
    if "articles" in fm_dict and "posts" not in fm_dict:
        fm_dict["posts"] = fm_dict["articles"]
        fm_dict["is_legacy"] = True

    if "composite" not in fm_dict and "posts" in fm_dict:
        fm_dict["composite"] = True
        fm_dict["is_legacy"] = True


# --- Composite entity helpers ---

async def read_partials(index_path: str, manifest: Optional[list] = None) -> dict[str, str]:
    """Read partial files (_*.md) in the same directory as an index.md."""
    partials = {}
    entity_dir = "/".join(index_path.split("/")[:-1])

    if manifest:
        for item in manifest:
            if not isinstance(item, dict): continue
            partial_id = item.get("id")
            if not partial_id: continue
            
            partial_path = f"{entity_dir}/_{partial_id}.md"
            if await content_storage.exists(partial_path):
                partials[partial_id] = await content_storage.read(partial_path)
    else:
        # Legacy fallback
        files = await content_storage.list_dir(entity_dir)
        for filename in files:
            if filename.startswith("_") and filename.endswith(".md"):
                partial_id = filename.lstrip("_").replace(".md", "")
                partials[partial_id] = await content_storage.read(f"{entity_dir}/{filename}")

    return partials


async def write_partial(index_path: str, partial_id: str, content: str) -> str:
    """Write a partial file into a composite entity's directory."""
    entity_dir = "/".join(index_path.split("/")[:-1])
    partial_path = f"{entity_dir}/_{partial_id}.md"
    await content_storage.write(partial_path, content)
    return partial_path


async def _snapshot_markdown_directory(index_path: str) -> dict[str, str]:
    """Capture Markdown files for best-effort multi-file rollback."""
    entity_dir = "/".join(index_path.split("/")[:-1])
    if not await content_storage.exists(entity_dir):
        return {}
    snapshot: dict[str, str] = {}
    for item in await content_storage.list_dir(entity_dir):
        name = item.split("/")[-1]
        path = f"{entity_dir}/{name}" if not item.startswith(entity_dir) else item
        if name.endswith(".md") and not await content_storage.is_dir(path):
            snapshot[name] = await content_storage.read(path)
    return snapshot


async def _restore_markdown_directory(index_path: str, snapshot: dict[str, str]) -> None:
    entity_dir = "/".join(index_path.split("/")[:-1])
    await content_storage.mkdir(entity_dir)
    try:
        current = await content_storage.list_dir(entity_dir)
    except Exception:
        current = []
    for item in current:
        name = item.split("/")[-1]
        path = f"{entity_dir}/{name}" if not item.startswith(entity_dir) else item
        if name.endswith(".md") and name not in snapshot and not await content_storage.is_dir(path):
            await content_storage.delete(path)
    for name, value in snapshot.items():
        await content_storage.write(f"{entity_dir}/{name}", value)


# --- Core service functions ---

async def write_page(
    page: Page,
    page_id: Optional[str] = None,
    composite: bool = False,
    partials: Optional[dict[str, str]] = None,
    site_id: str = DEFAULT_SITE_ID,
    language: Optional[str] = None,
) -> PageResponse:
    """Write a page to storage."""
    if partials:
        cleaned_partials = {}
        for k, v in partials.items():
            clean_k = k
            if clean_k.startswith("_"):
                clean_k = clean_k[1:]
            if clean_k.endswith(".md"):
                clean_k = clean_k[:-3]
            cleaned_partials[clean_k] = v
        partials = cleaned_partials

    if not page_id:
        page_id = name_to_id(page.frontmatter.name)
    config = get_site_language_config(site_id)
    requested_language = normalize_requested_language(language, config)
    if config.active and page_id in config.languages:
        raise _teaching_error(
            join_site_path(site_id, page_id, "index.md"),
            f"slug '{page_id}' shadows a configured language code",
            "rename the slug or remove that language from the site config.",
        )
    category = page.frontmatter.category
    
    if requested_language != config.language:
        legacy_file = ""
    elif category:
        legacy_file = join_site_path(site_id, category, f"{page_id}.md")
    else:
        legacy_file = join_site_path(site_id, f"{page_id}.md")
    file_path = await build_write_path(
        page_id,
        category,
        composite=composite,
        site_id=site_id,
        language=requested_language,
    )

    fm_dict = frontmatter_to_dict(page.frontmatter)
    source_path = join_site_path(site_id, page_id, "index.md")
    source_original: Optional[str] = None
    source_rewrite: Optional[str] = None
    source_cache_metadata: Optional[dict[str, Any]] = None
    source_cache_body = ""

    if config.active:
        if requested_language != config.language:
            if not await content_storage.exists(source_path):
                raise _teaching_error(
                    file_path,
                    f"translation for slug '{page_id}' has no default-language peer",
                    f"create {source_path} first.",
                )
            source_original = await content_storage.read(source_path)
            source_post = frontmatter.loads(source_original)
            source_metadata = dict(source_post.metadata)
            group = source_metadata.get("translation_group")
            if group:
                group = validate_translation_group(group, filepath=source_path)
            else:
                group = new_translation_group()
                source_metadata["translation_group"] = group
            source_metadata["language"] = config.language

            existing_target_metadata: dict[str, Any] = {}
            if await content_storage.exists(file_path):
                existing_target_metadata, _ = await _read_metadata(file_path)
                existing_group = existing_target_metadata.get("translation_group")
                if existing_group and existing_group != group:
                    raise _teaching_error(
                        file_path,
                        f"existing translation_group '{existing_group}' does not match '{group}'",
                        "keep the group from the default-language peer.",
                    )

            fm_dict["language"] = requested_language
            fm_dict["translation_group"] = group
            if fm_dict.get("slug") not in (None, "", page_id):
                raise _teaching_error(
                    file_path,
                    f"frontmatter slug '{fm_dict.get('slug')}' differs from path slug '{page_id}'",
                    f"set slug: {page_id}.",
                )
            if _structural_identity(fm_dict) != _structural_identity(source_metadata):
                raise _teaching_error(
                    file_path,
                    "page kind, domain, taxonomy assignments, or composite manifest differs from the default peer",
                    "copy page/category/domain/tags and the ordered composite part IDs from the default peer.",
                )
            source_rewrite = frontmatter.dumps(
                frontmatter.Post(source_post.content or "", **source_metadata)
            )
            source_cache_metadata = source_metadata
            source_cache_body = source_post.content or ""
        else:
            existing_source_metadata: dict[str, Any] = {}
            if await content_storage.exists(source_path):
                existing_source_metadata, _ = await _read_metadata(source_path)
            existing_group = existing_source_metadata.get("translation_group")
            if existing_group:
                fm_dict["translation_group"] = validate_translation_group(
                    existing_group, filepath=source_path
                )
                fm_dict["language"] = config.language
            elif fm_dict.get("translation_group"):
                fm_dict["translation_group"] = validate_translation_group(
                    fm_dict["translation_group"], filepath=file_path
                )
                fm_dict["language"] = config.language

    # Timestamps
    legacy_exists = bool(legacy_file) and await content_storage.exists(legacy_file)
    if not await content_storage.exists(file_path) and not legacy_exists:
        fm_dict["created_at"] = datetime.utcnow().strftime("%Y-%m-%d")
    fm_dict["updated_at"] = datetime.utcnow().strftime("%Y-%m-%d")

    if composite:
        fm_dict["composite"] = True
        posts = fm_dict.get("posts", [])
        index_entry = next((a for a in posts if isinstance(a, dict) and a.get("id") == "index"), None)
        fragment_posts = [a for a in posts if isinstance(a, dict) and a.get("id") != "index"]
        fragment_existing_ids = {a.get("id") for a in fragment_posts}

        if partials:
            for raw_id in list(partials.keys()):
                partial_id = sanitize_slug(raw_id)
                if partial_id not in fragment_existing_ids:
                    fragment_posts.append({
                        "id": partial_id,
                        "content": f"_{partial_id}.md",
                        "title": partial_id.replace('-', ' ').capitalize()
                    })

            sanitized_payload_ids = {sanitize_slug(k) for k in partials.keys()}
            fragment_posts = [a for a in fragment_posts if a.get("id") in sanitized_payload_ids]

        posts = ([index_entry] if index_entry else []) + fragment_posts
        fm_dict["posts"] = posts

    target_snapshot = await _snapshot_markdown_directory(file_path)
    await content_storage.begin_transaction()
    try:
        if source_rewrite is not None:
            await content_storage.write(source_path, source_rewrite)
        post = frontmatter.Post(page.content or "", **fm_dict)
        await content_storage.write(file_path, frontmatter.dumps(post))

        # Clean up legacy .md file
        if legacy_file and await content_storage.exists(legacy_file) and not await content_storage.is_dir(legacy_file):
            await content_storage.delete(legacy_file)

        if composite and partials:
            for raw_id, partial_content in partials.items():
                partial_id = sanitize_slug(raw_id)
                await write_partial(file_path, partial_id, partial_content)

        # Clean up orphan partial files on disk
        entity_dir = "/".join(file_path.split("/")[:-1])
        if await content_storage.exists(entity_dir) and await content_storage.is_dir(entity_dir):
            disk_files = await content_storage.list_dir(entity_dir)
            keep_partials = {f"_{sanitize_slug(k)}.md" for k in (partials or {}).keys()} if composite else set()
            for filename in disk_files:
                name = filename.split("/")[-1]
                if name.startswith("_") and name.endswith(".md"):
                    if name not in keep_partials:
                        await content_storage.delete(f"{entity_dir}/{name}")

        if config.active:
            records = await list_sibling_records(page_id, site_id=site_id)
            if requested_language != config.language and not any(
                record["language"] == requested_language for record in records
            ):
                raise _teaching_error(
                    file_path,
                    "written sibling was not discoverable",
                    "verify its locale folder and frontmatter language.",
                )

        await content_storage.end_transaction(f"Updated page: {page_id}")
        
        # Write through to SQLite cache
        try:
            from services.cache_service import save_entry_to_cache
            if source_cache_metadata is not None:
                source_stat = await content_storage.stat(source_path)
                save_entry_to_cache(
                    collection=source_cache_metadata.get("category") or "general",
                    slug=page_id,
                    filepath=source_path,
                    title=(
                        source_cache_metadata.get("title")
                        or source_cache_metadata.get("name")
                        or page_id.replace("-", " ").capitalize()
                    ),
                    published=source_cache_metadata.get("published", True),
                    status=source_cache_metadata.get("status", "published"),
                    domain=source_cache_metadata.get("domain", "blog"),
                    needs_review=source_cache_metadata.get("needs_review", False),
                    mtime=source_stat.get("mtime", time.time()),
                    frontmatter_dict=source_cache_metadata,
                    body=source_cache_body,
                    site_id=site_id,
                    language=config.language,
                    translation_group=source_cache_metadata.get("translation_group"),
                )
            # Get current file stat for mtime
            file_stat = await content_storage.stat(file_path)
            mtime = file_stat.get("mtime", time.time())
            save_entry_to_cache(
                collection=category or "general",
                slug=page_id,
                filepath=file_path,
                title=fm_dict.get("title") or fm_dict.get("name") or page_id.replace("-", " ").capitalize(),
                published=fm_dict.get("published", True),
                status=fm_dict.get("status", "published"),
                domain=fm_dict.get("domain", "blog"),
                needs_review=fm_dict.get("needs_review", False),
                mtime=mtime,
                frontmatter_dict=fm_dict,
                body=page.content or "",
                site_id=site_id,
                language=requested_language,
                translation_group=fm_dict.get("translation_group"),
            )
        except Exception as cache_err:
            logger.error(f"Failed to update SQLite cache in write_page: {cache_err}")
    except Exception as e:
        # Storage providers do not all offer multi-file rollback. Restore the
        # source and target Markdown snapshots before leaving transaction mode.
        try:
            if source_original is not None:
                await content_storage.write(source_path, source_original)
            await _restore_markdown_directory(file_path, target_snapshot)
        except Exception as rollback_err:
            logger.error("Failed to restore i18n write snapshot: %s", rollback_err)
        await content_storage.cancel_transaction()
        raise e

    return await attach_page_version(
        PageResponse(
            id=page_id,
            frontmatter=fm_dict,
            content=page.content or "",
            file_path=file_path,
            composite=composite,
            partials=partials or {},
            language=requested_language if config.active else None,
            translation_group=fm_dict.get("translation_group") if config.active else None,
            translations=(
                await translation_peer_summaries(
                    page_id,
                    current_language=requested_language,
                    site_id=site_id,
                )
                if config.active
                else None
            ),
        )
    )


async def read_page(
    page_id: str,
    category: Optional[str] = None,
    include_partials: bool = False,
    site_id: str = DEFAULT_SITE_ID,
    language: Optional[str] = None,
    translations_live_only: bool = False,
    public_only: bool = False,
) -> Optional[PageResponse]:
    """Read a single page from storage by ID."""
    config = get_site_language_config(site_id)
    requested_language = normalize_requested_language(language, config)
    rel_path = await resolve_path(
        page_id,
        category,
        site_id=site_id,
        language=requested_language,
    )

    if not rel_path:
        return None

    try:
        raw = await content_storage.read(rel_path)
        post = frontmatter.loads(raw)
        fm_dict = dict_to_frontmatter(dict(post.metadata))
    except Exception as exc:
        if public_only:
            logger.warning(
                "Withholding unreadable public detail %s/%s (%s): %s",
                requested_language,
                page_id,
                site_id,
                exc,
            )
            return None
        raise

    if public_only:
        if not is_live_translation(fm_dict):
            return None
        if config.active and requested_language != config.language:
            default_path = await resolve_path(
                page_id,
                category,
                site_id=site_id,
                language=config.language,
            )
            if not default_path:
                return None
            try:
                default_metadata, _ = await _read_metadata(default_path)
                if not is_live_translation(default_metadata):
                    return None
                # Validate the exact sibling against its authoritative peer.
                # This also enforces locale-local composite completeness.
                await _validate_sibling_set(
                    site_id=site_id,
                    slug=page_id,
                    default_path=default_path,
                    translation_paths=[rel_path],
                    group_owners={},
                )
            except Exception as exc:
                logger.warning(
                    "Withholding invalid localized detail %s/%s (%s): %s",
                    requested_language,
                    page_id,
                    site_id,
                    exc,
                )
                return None
    
    _enrich_page_data(rel_path, fm_dict, post.content)

    composite_flag = fm_dict.get("composite", False)
    partials_dict = {}
    if include_partials and composite_flag:
        manifest = fm_dict.get("posts")
        partials_dict = await read_partials(rel_path, manifest)

    return await attach_page_version(
        PageResponse(
            id=page_id,
            frontmatter=fm_dict,
            content=post.content,
            file_path=rel_path,
            composite=composite_flag,
            partials=partials_dict,
            language=requested_language if config.active else None,
            translation_group=fm_dict.get("translation_group") if config.active else None,
            translations=(
                await translation_peer_summaries(
                    page_id,
                    current_language=requested_language,
                    site_id=site_id,
                    live_only=translations_live_only,
                )
                if config.active
                else None
            ),
        )
    )


async def delete_page(
    page_id: str,
    category: Optional[str] = None,
    site_id: str = DEFAULT_SITE_ID,
    language: Optional[str] = None,
    delete_group: bool = False,
) -> bool:
    """Delete a page from storage."""
    config = get_site_language_config(site_id)
    requested_language = normalize_requested_language(language, config)
    rel_path = await resolve_path(
        page_id,
        category,
        site_id=site_id,
        language=requested_language,
    )

    if not rel_path:
        return False

    collection = category or "general"
    cache_targets = [(requested_language, collection)]

    if config.active and requested_language == config.language:
        siblings = await list_sibling_records(page_id, site_id=site_id)
        translated = [r["language"] for r in siblings if r["language"] != config.language]
        if translated and not delete_group:
            raise _teaching_error(
                rel_path,
                f"default-language document still has siblings: {', '.join(translated)}",
                "delete the non-default siblings first or explicitly request whole-group deletion.",
            )
        if translated:
            cache_targets = [
                (
                    str(record["language"]),
                    str(record["frontmatter"].get("category") or collection),
                )
                for record in siblings
            ]

    if rel_path.endswith("index.md"):
        # Pattern B translations remove only their locale directory.
        entity_dir = "/".join(rel_path.split("/")[:-1])
        await content_storage.delete_dir(entity_dir)
    else:
        await content_storage.delete(rel_path)

    # Delete from SQLite cache
    try:
        from services.cache_service import delete_entry_from_cache
        for cache_language, cache_collection in cache_targets:
            delete_entry_from_cache(
                cache_collection,
                page_id,
                site_id=site_id,
                language=cache_language,
            )
    except Exception as cache_err:
        logger.error(f"Failed to delete SQLite cache entry: {cache_err}")

    return True


async def list_pages(
    category: Optional[str] = None,
    status: Optional[str] = None,
    domain: Optional[str] = None,
    needs_review: Optional[bool] = None,
    published: Optional[bool] = None,
    site_id: Optional[str] = DEFAULT_SITE_ID,
    live_only: bool = False,
    due_within_hours: Optional[int] = None,
    language: Optional[str] = None,
    fallback: str = "none",
    translations_live_only: bool = False,
) -> List[PageResponse]:
    """List all canonical pages with optional filters leveraging the SQLite cache.

    When ``live_only`` is True, only entries that are publicly listable are
    returned: ``status == published`` and (``publish_at`` is null or in the past).

    When ``due_within_hours`` is set, only published entries whose ``publish_at``
    fell within the last N hours (and is not in the future) are returned —
    used by the static rebuild-due CLI.
    """
    from models.page import utc_now_iso
    from datetime import datetime, timedelta, timezone

    now_iso = utc_now_iso()
    language_config = (
        get_site_language_config(site_id) if site_id is not None else None
    )
    requested_language = (
        normalize_requested_language(language, language_config)
        if language_config is not None
        else None
    )
    query_language = (
        requested_language
        if language_config is not None and language_config.active
        else None
    )
    if (
        language_config is not None
        and fallback == "default"
        and requested_language != language_config.language
    ):
        query_language = language_config.language
    due_since_iso = None
    if due_within_hours is not None and due_within_hours > 0:
        due_since = datetime.now(timezone.utc) - timedelta(hours=due_within_hours)
        due_since_iso = due_since.strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        from services.cache_service import get_db_connection
        pages = []
        
        # Base query
        query = (
            "SELECT slug, collection, filepath, title, published, status, domain, "
            "needs_review, publish_at, modified_at, frontmatter, body, site_id, "
            "language, translation_group FROM entries"
        )
        conditions = []
        params = []

        if site_id is not None:
            conditions.append("site_id = ?")
            params.append(site_id)
        if query_language is not None:
            conditions.append("language = ?")
            params.append(query_language)
        if category:
            conditions.append("collection = ?")
            params.append(category)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if domain:
            conditions.append("domain = ?")
            params.append(domain)
        if needs_review is not None:
            conditions.append("needs_review = ?")
            params.append(1 if needs_review else 0)
        if published is not None:
            conditions.append("published = ?")
            params.append(1 if published else 0)
        if live_only:
            conditions.append("status = ?")
            params.append("published")
            conditions.append("(publish_at IS NULL OR publish_at = '' OR publish_at <= ?)")
            params.append(now_iso)
        if due_since_iso is not None:
            conditions.append("status = ?")
            params.append("published")
            conditions.append("publish_at IS NOT NULL AND publish_at != ''")
            conditions.append("publish_at <= ?")
            params.append(now_iso)
            conditions.append("publish_at >= ?")
            params.append(due_since_iso)
            
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        query += " ORDER BY modified_at DESC"
        
        with get_db_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            
            selected_rows = []
            for r in rows:
                selected = r
                is_fallback = False
                if (
                    language_config is not None
                    and fallback == "default"
                    and requested_language != language_config.language
                ):
                    default_live = (
                        r["status"] == "published"
                        and (not r["publish_at"] or r["publish_at"] <= now_iso)
                    )
                    target = None
                    if default_live:
                        target = conn.execute(
                            """
                            SELECT slug, collection, filepath, title, published, status,
                                   domain, needs_review, publish_at, modified_at,
                                   frontmatter, body, site_id, language, translation_group
                            FROM entries
                            WHERE site_id = ? AND collection = ? AND slug = ?
                              AND language = ? AND translation_group = ?
                              AND status = 'published'
                              AND (needs_review IS NULL OR needs_review = 0)
                              AND (publish_at IS NULL OR publish_at = '' OR publish_at <= ?)
                            """,
                            (
                                site_id,
                                r["collection"],
                                r["slug"],
                                requested_language,
                                r["translation_group"],
                                now_iso,
                            ),
                        ).fetchone()
                    if target is not None:
                        selected = target
                    else:
                        is_fallback = True
                selected_rows.append((selected, is_fallback))

            for r, is_fallback in selected_rows:
                fm_dict = json.loads(r["frontmatter"])
                if "articles" in fm_dict and "posts" not in fm_dict:
                    fm_dict["posts"] = fm_dict["articles"]
                    fm_dict["is_legacy"] = True
                active = bool(language_config and language_config.active)
                if (
                    live_only
                    and active
                    and fallback == "none"
                    and requested_language != language_config.language
                ):
                    public_page = await read_page(
                        r["slug"],
                        category=r["collection"],
                        site_id=site_id,
                        language=requested_language,
                        public_only=True,
                    )
                    if public_page is None:
                        continue
                peers = None
                if active:
                    peer_query = (
                        "SELECT language, status, published, needs_review FROM entries "
                        "WHERE site_id = ? AND collection = ? AND slug = ? AND language != ?"
                    )
                    peer_params: list[Any] = [
                        r["site_id"],
                        r["collection"],
                        r["slug"],
                        r["language"],
                    ]
                    if translations_live_only:
                        peer_query += (
                            " AND status = 'published'"
                            " AND (needs_review IS NULL OR needs_review = 0)"
                            " AND (publish_at IS NULL OR publish_at = '' OR publish_at <= ?)"
                        )
                        peer_params.append(now_iso)
                    peer_query += " ORDER BY language"
                    peer_rows = conn.execute(peer_query, peer_params).fetchall()
                    peers = [
                        {
                            "language": peer["language"],
                            "status": peer["status"],
                            "published": bool(peer["published"]),
                            "needs_review": bool(peer["needs_review"]),
                        }
                        for peer in peer_rows
                    ]
                pages.append(PageResponse(
                    id=r["slug"],
                    frontmatter=fm_dict,
                    content=r["body"],
                    file_path=r["filepath"],
                    composite=bool(fm_dict.get("composite", False)),
                    language=r["language"] if active else None,
                    translation_group=r["translation_group"] if active else None,
                    translations=peers,
                    is_fallback=is_fallback if active else None,
                ))
        return pages
    except Exception as e:
        logger.error(f"SQLite cache query failed, falling back to slow file listing: {e}")

    # Fallback to slow implementation
    pages = []
    for rel_path in await iter_canonical_files(site_id=site_id):
        identity = (
            content_identity_for_path(rel_path, site_id)
            if site_id is not None
            else None
        )
        if identity is not None and query_language is not None and identity.language != query_language:
            continue
        raw = await content_storage.read(rel_path)
        post = frontmatter.loads(raw)
        fm = dict_to_frontmatter(dict(post.metadata))
        
        _enrich_page_data(rel_path, fm, post.content)

        # Apply filters
        if category and fm.get("category") != category:
            continue
        if status and fm.get("status") != status:
            continue
        if domain and fm.get("domain") != domain:
            continue
        if needs_review is not None and fm.get("needs_review") != needs_review:
            continue
        if published is not None and fm.get("published") != published:
            continue
        if live_only:
            if fm.get("status", "published") != "published":
                continue
            pa = fm.get("publish_at")
            if pa and pa > now_iso:
                continue
        if due_since_iso is not None:
            if fm.get("status") != "published":
                continue
            pa = fm.get("publish_at")
            if not pa or pa > now_iso or pa < due_since_iso:
                continue

        page_id = path_to_id(rel_path)
        if (
            live_only
            and language_config is not None
            and language_config.active
            and fallback == "none"
            and requested_language != language_config.language
        ):
            public_page = await read_page(
                page_id,
                category=category,
                site_id=site_id,
                language=requested_language,
                public_only=True,
            )
            if public_page is None:
                continue
        if (
            language_config is not None
            and fallback == "default"
            and requested_language != language_config.language
            and is_live_translation(fm)
        ):
            target = await read_page(
                page_id,
                include_partials=False,
                site_id=site_id,
                language=requested_language,
                translations_live_only=translations_live_only,
            )
            if target and is_live_translation(target.frontmatter):
                target.is_fallback = False
                pages.append(target)
                continue
        pages.append(PageResponse(
            id=page_id,
            frontmatter=fm,
            content=post.content,
            file_path=rel_path,
            composite=fm.get("composite", False),
            language=identity.language if identity and language_config and language_config.active else None,
            translation_group=fm.get("translation_group") if language_config and language_config.active else None,
            translations=(
                await translation_peer_summaries(
                    page_id,
                    current_language=identity.language,
                    site_id=site_id,
                    live_only=translations_live_only,
                )
                if identity and language_config and language_config.active
                else None
            ),
            is_fallback=(
                fallback == "default" and requested_language != language_config.language
                if language_config and language_config.active
                else None
            ),
        ))

    return pages
