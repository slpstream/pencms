from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List
from routers.auth import get_current_user
from routers.mcp_tools import require_scope, resolve_mcp_site_id
from models.user import UserPublic
from models.author import Author, AuthorCreate, AuthorUpdate
from services import author_service

router = APIRouter(prefix="/api/v1", tags=["mcp"])

CREATE_AUTHOR_DOC = """Create a site author / contributor bio (plain text).

Bios are plain text only — no Markdown rendering.

After create, attribute a post by setting frontmatter `author:` to this author's
display **`name`** via `write_content_file` (not the slug, and never post `name`).

Example:
{"name":"Jane Doe","bio":"Writer and editor","role":"Editor"}
"""

UPDATE_AUTHOR_DOC = """Partial update of a site author bio.

Slug is immutable (path param only). Bios remain plain text.

Example:
{"bio":"Updated bio","role":"Senior Editor"}
"""


@router.get(
    "/mcp/authors",
    operation_id="list_authors",
    dependencies=[Depends(require_scope("read"))],
)
async def list_authors(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> List[Author]:
    """List all site authors for the active MCP site (`authors.yaml`)."""
    site_id = resolve_mcp_site_id(request)
    try:
        return await author_service.list_authors(site_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list authors: {e}")


@router.get(
    "/mcp/authors/{slug}",
    operation_id="get_author",
    dependencies=[Depends(require_scope("read"))],
)
async def get_author(
    slug: str,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Author:
    """Get one site author by slug."""
    site_id = resolve_mcp_site_id(request)
    try:
        return await author_service.get_author(slug, site_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get author: {e}")


@router.post(
    "/mcp/authors",
    operation_id="create_author",
    dependencies=[Depends(require_scope("write:authors"))],
    status_code=201,
    summary="Create a site author",
    description=CREATE_AUTHOR_DOC,
)
async def create_author(
    author_create: AuthorCreate,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Author:
    site_id = resolve_mcp_site_id(request)
    try:
        return await author_service.create_author(author_create, site_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create author: {e}")


create_author.__doc__ = CREATE_AUTHOR_DOC


@router.put(
    "/mcp/authors/{slug}",
    operation_id="update_author",
    dependencies=[Depends(require_scope("write:authors"))],
    summary="Update a site author",
    description=UPDATE_AUTHOR_DOC,
)
async def update_author(
    slug: str,
    author_update: AuthorUpdate,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Author:
    site_id = resolve_mcp_site_id(request)
    try:
        return await author_service.update_author(slug, author_update, site_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update author: {e}")


update_author.__doc__ = UPDATE_AUTHOR_DOC


@router.delete(
    "/mcp/authors/{slug}",
    operation_id="delete_author",
    dependencies=[Depends(require_scope("write:authors"))],
    status_code=204,
)
async def delete_author(
    slug: str,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
):
    """Delete a site author by slug."""
    site_id = resolve_mcp_site_id(request)
    try:
        await author_service.delete_author(slug, site_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete author: {e}")
