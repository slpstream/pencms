from enum import Enum
from typing import Dict, Literal, Optional, Union
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator

class MenuSlot(str, Enum):
    primary = "primary"
    secondary = "secondary"
    footer = "footer"

class ContentTarget(BaseModel):
    """Link to a page or post by slug."""
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"type": "content", "content_slug": "about", "content_type": "page"},
                {"type": "content", "content_slug": "my-article", "content_type": "post"},
            ]
        }
    )
    type: Literal["content"] = "content"
    content_slug: str            # slug, not UUID — content is file-based
    content_type: Literal["page", "post"]

class CustomTarget(BaseModel):
    """External or arbitrary URL."""
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"type": "custom", "url": "https://github.com/example"},
            ]
        }
    )
    type: Literal["custom"] = "custom"
    url: str

class LabelTarget(BaseModel):
    """Non-clickable label / section header (no URL)."""
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"type": "label"},
            ]
        }
    )
    type: Literal["label"] = "label"

class TaxonomyTarget(BaseModel):
    """Taxonomy term archive. content_slug is `{vocab_key}/{term}`; url is usually `/category/{term-slug}/`."""
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "type": "taxonomy",
                    "content_slug": "primary/Winter",
                    "url": "/category/winter/",
                },
            ]
        }
    )
    type: Literal["taxonomy"] = "taxonomy"
    content_slug: str
    url: Optional[str] = None

class SystemTarget(BaseModel):
    """Built-in system page. content_slug is one of: home, blog, search, rss."""
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"type": "system", "content_slug": "home", "url": "/"},
                {"type": "system", "content_slug": "blog", "url": "/category/"},
                {"type": "system", "content_slug": "search", "url": "/search/"},
                {"type": "system", "content_slug": "rss", "url": "/feed.xml"},
            ]
        }
    )
    type: Literal["system"] = "system"
    content_slug: str
    url: Optional[str] = None

# Discriminated union on the `type` field
MenuItemTarget = Union[ContentTarget, CustomTarget, LabelTarget, TaxonomyTarget, SystemTarget]

_MENU_ITEM_CREATE_EXAMPLES = [
    {
        "menu": "primary",
        "label": "About",
        "target": {"type": "content", "content_slug": "about", "content_type": "page"},
        "parent_id": None,
    },
    {
        "menu": "primary",
        "label": "My Article",
        "target": {"type": "content", "content_slug": "my-article", "content_type": "post"},
    },
    {
        "menu": "primary",
        "label": "Winter",
        "target": {
            "type": "taxonomy",
            "content_slug": "primary/Winter",
            "url": "/category/winter/",
        },
    },
    {
        "menu": "primary",
        "label": "Archives",
        "target": {"type": "system", "content_slug": "blog", "url": "/category/"},
    },
    {
        "menu": "footer",
        "label": "GitHub",
        "target": {"type": "custom", "url": "https://github.com/example"},
        "open_in_new_tab": True,
    },
    {
        "menu": "footer",
        "label": "Legal",
        "target": {"type": "label"},
    },
]


class LocalizedMenuLabelsMixin(BaseModel):
    """Sparse reader-facing labels keyed by normalized BCP-47 language."""

    labels: Optional[Dict[str, str]] = None

    @field_validator("labels")
    @classmethod
    def normalize_labels(
        cls, value: Optional[Dict[str, str]]
    ) -> Optional[Dict[str, str]]:
        if value is None:
            return None

        from services.i18n_service import normalize_language_tag

        normalized: Dict[str, str] = {}
        for raw_language, raw_label in value.items():
            language = normalize_language_tag(
                raw_language, field="menu labels key"
            )
            if language in normalized:
                raise ValueError(
                    f"Duplicate menu label language '{language}' after normalization"
                )
            label = raw_label.strip()
            if not label:
                raise ValueError(
                    f"Menu label for language '{language}' must be non-empty"
                )
            normalized[language] = label
        return normalized or None


class MenuItem(LocalizedMenuLabelsMixin):
    id: str = Field(default_factory=lambda: str(uuid4()))
    menu: MenuSlot
    label: str
    target: MenuItemTarget = Field(..., discriminator="type")
    parent_id: Optional[str] = None     # null = top-level
    order: int = 0                      # sibling order within same parent_id
    open_in_new_tab: bool = False

class MenuItemCreate(LocalizedMenuLabelsMixin):
    """Input model for creating a menu item (id auto-generated).

    Six UI link types map to five API target shapes:
    Page/Post → content; Category/term → taxonomy; System → system;
    Custom Link → custom; Label → label.
    """
    model_config = ConfigDict(json_schema_extra={"examples": _MENU_ITEM_CREATE_EXAMPLES})
    menu: MenuSlot
    label: str
    target: MenuItemTarget = Field(..., discriminator="type")
    parent_id: Optional[str] = None
    order: Optional[int] = None         # if omitted, append to end
    open_in_new_tab: bool = False

class MenuItemUpdate(LocalizedMenuLabelsMixin):
    """Input model for updating a menu item (partial update)."""
    label: Optional[str] = None
    target: Optional[MenuItemTarget] = Field(None, discriminator="type")
    parent_id: Optional[str] = None
    order: Optional[int] = None
    open_in_new_tab: Optional[bool] = None

class ReorderItem(BaseModel):
    id: str
    parent_id: Optional[str] = None
    order: int

class MenuItemReplace(LocalizedMenuLabelsMixin):
    """Input model for wholesale replacement of a menu slot."""
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "label": "About",
                    "target": {
                        "type": "content",
                        "content_slug": "about",
                        "content_type": "page",
                    },
                    "parent_id": None,
                },
                {
                    "id": "parent-uuid",
                    "label": "Legal",
                    "target": {"type": "label"},
                },
                {
                    "label": "Privacy",
                    "target": {
                        "type": "content",
                        "content_slug": "privacy",
                        "content_type": "page",
                    },
                    "parent_id": "parent-uuid",
                },
            ]
        }
    )
    id: Optional[str] = None             # optional; generate UUID if not provided
    label: str
    target: MenuItemTarget = Field(..., discriminator="type")
    parent_id: Optional[str] = None     # matches the custom or auto-generated id of parent in this list
    order: Optional[int] = None         # if omitted, preserve original list order index
    open_in_new_tab: bool = False
