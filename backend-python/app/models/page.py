from datetime import datetime, timezone
from typing import Any, Optional

import config
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


def normalize_publish_at(value: Any) -> Optional[str]:
    """Normalize publish_at to a UTC ISO-8601 string, or None if empty.

    Accepts full ISO-8601 datetimes (with Z or offset) and bare YYYY-MM-DD
    dates (treated as UTC midnight). Returns a string ending in Z for storage.
    """
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("publish_at must be an ISO-8601 datetime string")
    raw = value.strip()
    if not raw:
        return None
    # Bare date → UTC midnight
    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        try:
            datetime.strptime(raw, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"publish_at date is invalid: {raw}") from e
        return f"{raw}T00:00:00Z"
    # Normalize trailing Z / offset via fromisoformat
    candidate = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
    try:
        dt = datetime.fromisoformat(candidate)
    except ValueError as e:
        raise ValueError(
            "publish_at must be ISO-8601 (e.g. 2026-07-20T15:00:00Z or 2026-07-20)"
        ) from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_now_iso() -> str:
    """Current UTC time as ISO-8601 with Z suffix (sortable)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# --- Core page model ---


class FaqItem(BaseModel):
    """One Q&A pair stored on post/page frontmatter (`faqs: [{q, a}]`)."""

    q: str
    a: str


class PageFrontmatter(BaseModel):
    model_config = ConfigDict(extra="allow", coerce_numbers_to_str=True)

    # Primary classification — maps to the directory name and taxonomy
    category: str

    @model_validator(mode="before")
    @classmethod
    def alias_and_fallback(cls, data: Any) -> Any:
        """Backward compatibility: if 'type' exists but 'category' does not,
        copy type → category. Also aliases 'title' → 'name'.
        Implements fallback chain for name, hero_title, and slug."""
        if isinstance(data, dict):
            # type → category migration
            if "category" not in data and "type" in data:
                data["category"] = data["type"]
            # If it is a page, category can be empty/null
            if data.get("page") in (True, "true"):
                if not data.get("category"):
                    data["category"] = ""
            # title → name migration
            if "name" not in data and "title" in data:
                data["name"] = data["title"]

            # Fallback chain fields
            slug_val = data.get("slug")
            name_val = data.get("name")
            hero_title_val = data.get("hero_title")

            # Rule 1: No name
            if not name_val:
                if hero_title_val:
                    name_val = hero_title_val
                elif slug_val:
                    name_val = slug_val.replace("-", " ").replace("_", " ").strip().title()

            # Rule 2: No hero_title
            if not hero_title_val:
                if name_val:
                    hero_title_val = name_val
                elif slug_val:
                    hero_title_val = slug_val.replace("-", " ").replace("_", " ").strip().title()

            # Rule 3: No slug
            if not slug_val:
                from services.file_service import name_to_id
                if name_val:
                    slug_val = name_to_id(name_val)
                elif hero_title_val:
                    slug_val = name_to_id(hero_title_val)

            # Write back derived values
            if name_val:
                data["name"] = name_val
                if "title" in data:
                    data["title"] = name_val
            if hero_title_val:
                data["hero_title"] = hero_title_val
            if slug_val:
                data["slug"] = slug_val

        return data

    # Universal required
    name: str

    # Universal optional
    slug: Optional[str] = None
    language: Optional[str] = None
    translation_group: Optional[str] = None

    # Universal optional
    domain: Optional[str] = "blog"  # blog (only domain)
    status: Optional[str] = "stub"
    published: Optional[bool] = False
    page: Optional[bool] = False
    date: Optional[str] = None  # YYYY-MM-DD display / sort dateline
    publish_at: Optional[str] = None  # ISO-8601 UTC go-live datetime
    author: Optional[str] = None  # Author or byline
    main_image: Optional[str] = None  # primary image for cards
    tags: Optional[list[str]] = []
    notes: Optional[str] = None

    # Agent provenance
    created_by: Optional[str] = "human"  # human | agent
    created_by_id: Optional[str] = None
    updated_by: Optional[str] = None  # human | agent
    updated_by_id: Optional[str] = None
    run_id: Optional[str] = None
    confidence: Optional[float] = None
    needs_review: Optional[bool] = False
    source: Optional[str] = None  # e.g. "Chapter 3 extraction"
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_decision: Optional[str] = None  # pending | approved | rejected
    review_note: Optional[str] = None

    # Presentation fields
    deck: Optional[str] = None
    summary: Optional[str] = None
    faqs: list[FaqItem] = Field(default_factory=list)
    trumpet: Optional[str] = None
    hero_image: Optional[str] = None
    hero_title: Optional[str] = None
    pinned: Optional[bool] = False
    noindex: Optional[bool] = False

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v):
        if v and v not in config.DOMAINS:
            raise ValueError(f"domain must be one of {config.DOMAINS}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v and v not in config.STATUS_VALUES:
            raise ValueError(f"status must be one of {config.STATUS_VALUES}")
        return v

    @field_validator("publish_at", mode="before")
    @classmethod
    def validate_publish_at(cls, v):
        return normalize_publish_at(v)

    @model_validator(mode="after")
    def validate_category_and_required_fields(self):
        # Default display date from publish_at calendar day when date is empty
        if self.publish_at and not self.date:
            self.date = self.publish_at[:10]

        tax = config.get_active_taxonomy()
        primary_terms = tax.get("primary_terms") or []
        primary_vocabulary = tax.get("primary_vocabulary")
        required_fields = tax.get("required_fields") or config.REQUIRED_FIELDS

        # 1. Validate category if page is not True
        if not self.page:
            v = self.category
            slug = config._term_to_slug(v)
            if primary_terms and slug not in primary_terms:
                vocab_name = primary_vocabulary or "(primary_vocabulary not set)"
                raise ValueError(
                    f"category '{v}' (slug: '{slug}') is not a valid term in the "
                    f"primary_vocabulary '{vocab_name}'. Valid terms: {primary_terms}. "
                    f"Note: the frontmatter field `category` is validated against the "
                    f"site's primary_vocabulary, NOT against any vocabulary literally "
                    f"named 'category' in taxonomy.yaml."
                )

        # 2. Validate required fields for non-stubs
        if self.status in ("stub", "draft"):
            return self

        if self.page:
            missing = []
            for field in ["name", "hero_title"]:
                if not getattr(self, field, None):
                    missing.append(field)
            if missing:
                raise ValueError(
                    f"Pages with status '{self.status}' require these fields: {missing}"
                )
            return self

        missing = []
        for field in required_fields:
            if not getattr(self, field, None):
                missing.append(field)
        if missing:
            raise ValueError(
                f"Posts with status '{self.status}' require these fields: {missing}"
            )
        return self


# --- Full page model (frontmatter + prose) ---


class Page(BaseModel):
    model_config = ConfigDict(extra="allow", coerce_numbers_to_str=True)
    frontmatter: PageFrontmatter
    content: Optional[str] = ""  # Markdown prose body
    composite: Optional[bool] = None  # None preserves existing structure on update
    partials: Optional[dict[str, str]] = None  # None preserves existing partials
    slug: Optional[str] = None  # Client-provided slug (used on create only)
    expected_version: Optional[str] = None  # Opaque token from a prior read
    force: bool = False  # Explicit overwrite; omitted expected_version is not force

    @model_validator(mode="before")
    @classmethod
    def sync_slug_before(cls, data: Any) -> Any:
        if isinstance(data, dict):
            fm = data.get("frontmatter")
            if fm is None:
                fm = {}
                data["frontmatter"] = fm
            elif not isinstance(fm, dict):
                return data

            slug_val = data.get("slug") or fm.get("slug")
            if slug_val and "slug" not in fm:
                fm["slug"] = slug_val
        return data

    @model_validator(mode="after")
    def sync_slug_after(self):
        if not self.slug and self.frontmatter and self.frontmatter.slug:
            self.slug = self.frontmatter.slug
        return self


# --- Response model ---


class TranslationPeer(BaseModel):
    language: str
    status: Optional[str] = None
    published: bool = False
    needs_review: bool = False
    review_decision: Optional[str] = None


class PageResponse(BaseModel):
    id: str  # filename without extension
    frontmatter: dict[str, Any]
    content: str
    file_path: str
    composite: bool = False
    partials: Optional[dict[str, str]] = {}
    language: Optional[str] = None
    translation_group: Optional[str] = None
    translations: Optional[list[TranslationPeer]] = None
    is_fallback: Optional[bool] = None
    provenance: Optional[dict[str, Any]] = None
    version: Optional[str] = None  # Opaque mtime token; not written to YAML
    version_warning: Optional[str] = None  # Soft-warn only when strict is off


def format_validation_error(e: ValidationError) -> str:
    """Format Pydantic ValidationError into a user-friendly error message."""
    messages = []
    for err in e.errors():
        loc = err.get("loc", ())
        # Filter out generic 'frontmatter' or 'body' from loc to get the actual field name
        field_path = [str(l) for l in loc if l not in ("frontmatter", "body")]
        field_prefix = f"{'.'.join(field_path)}: " if field_path else ""

        msg = err.get("msg", "")
        # Remove standard Pydantic prefixes if present
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, "):]

        # Check for specific posts status validation message and format nicely
        import re
        match = re.search(r"Posts with status '([^']+)' require these fields: \[(.+)\]", msg)
        if match:
            status_val = match.group(1)
            fields_str = match.group(2)
            fields = re.findall(r"['\"]([^'\"]+)['\"]", fields_str)
            fields_formatted = ", ".join([f.capitalize() for f in fields])
            msg = f"{status_val.capitalize()} posts require {fields_formatted}"
            field_prefix = ""

        messages.append(f"{field_prefix}{msg}")
    return "; ".join(messages)
