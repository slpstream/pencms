"""Site-scoped author / contributor bios (plain text; no CMS user linkage)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Author(BaseModel):
    """One contributor bio for a Content site (stored in authors.yaml)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "slug": "jane-doe",
                    "name": "Jane Doe",
                    "bio": "Short bio as plain text",
                    "website": "https://example.com",
                    "avatar": "images/authors/jane-doe.webp",
                    "email": "",
                    "role": "Editor",
                    "sort_order": 0,
                }
            ]
        }
    )

    slug: str
    name: str
    bio: str = ""
    website: str = ""
    avatar: Optional[str] = None
    email: str = ""
    role: str = ""
    sort_order: int = 0


class AuthorCreate(BaseModel):
    """Create one author. Slug optional — derived from name when omitted."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Jane Doe",
                    "bio": "Short bio as plain text",
                    "website": "https://example.com",
                    "role": "Editor",
                }
            ]
        }
    )

    name: str
    slug: Optional[str] = None
    bio: str = ""
    website: str = ""
    avatar: Optional[str] = None
    email: str = ""
    role: str = ""
    sort_order: Optional[int] = None


class AuthorUpdate(BaseModel):
    """Partial update. Slug is immutable (path param only)."""

    name: Optional[str] = None
    bio: Optional[str] = None
    website: Optional[str] = None
    avatar: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    sort_order: Optional[int] = None


class AuthorsListResponse(BaseModel):
    site_id: str
    authors: List[Author] = Field(default_factory=list)
