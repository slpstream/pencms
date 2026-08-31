"""MCP tools for site taxonomy (vocabularies + terms).

Publishing Rules (``required_fields`` / collections.yaml) stay human Structure-only.
``replace_taxonomy`` and upserts preserve on-disk ``required_fields``. Vocab key
``category`` is reserved. Human Structure UI remains admin-only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from models.user import UserPublic
from routers.auth import get_current_user
from routers.mcp_tools import require_scope, resolve_mcp_site_id
from services import taxonomy_service
from services.taxonomy_service import TaxonomyError

router = APIRouter(prefix="/api/v1", tags=["mcp"])


class ReplaceTaxonomyBody(BaseModel):
    primary_vocabulary: str = Field(
        ...,
        description="Key of the primary vocabulary. Must exist in vocabularies.",
    )
    vocabularies: Dict[str, Any] = Field(
        ...,
        description=(
            "Map of vocab key → {label, type: 'flat', controlled, required, terms}. "
            "Key 'category' is reserved. On-disk required_fields are preserved."
        ),
    )


class UpsertVocabularyBody(BaseModel):
    label: Optional[str] = Field(None, description="Display label. Defaults from the key.")
    controlled: Optional[bool] = Field(None, description="Whether terms are a closed list.")
    terms: Optional[List[str]] = Field(None, description="Replace the term list when set.")


class TermBody(BaseModel):
    term: str = Field(..., description="Term string as stored (not slugified).")


class PrimaryVocabularyBody(BaseModel):
    key: str = Field(..., description="Existing vocabulary key to make primary.")


def _map_taxonomy_error(exc: Exception) -> HTTPException:
    if isinstance(exc, TaxonomyError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=500, detail=f"Taxonomy operation failed: {exc}")


GET_TAXONOMY_DOC = """Read this site's vocabularies, primary_vocabulary, and terms.

Not a substitute for Publishing Rules (required_fields). Call this (or get_site_config)
before create_post so category/terms match a controlled vocabulary.
"""

REPLACE_TAXONOMY_DOC = """Bootstrap or replace this site's vocabularies wholesale.

Preserves on-disk required_fields (Publishing Rules stay human Structure-only).
Vocab key 'category' is reserved. Cannot drop the current primary without switching
first (include it, or set primary_vocabulary to a remaining key).

Example:
{"primary_vocabulary":"topics","vocabularies":{"topics":{"label":"Topics","type":"flat","controlled":true,"required":false,"terms":["News","Notes"]}}}
"""

UPSERT_VOCABULARY_DOC = """Create or update one vocabulary (label, controlled, terms).

If this is the first vocabulary and no primary is set, it becomes primary.
Key 'category' is reserved.
"""

DELETE_VOCABULARY_DOC = """Delete one vocabulary. Cannot delete the current primary — switch first."""

ADD_TERM_DOC = """Append a term to a vocabulary. Duplicate terms are rejected."""

REMOVE_TERM_DOC = """Remove a term from a vocabulary (exact string match)."""

SET_PRIMARY_DOC = """Set the primary vocabulary. The key must already exist."""


@router.get(
    "/mcp/taxonomy",
    operation_id="get_taxonomy",
    dependencies=[Depends(require_scope("read"))],
    summary="Read site vocabularies and terms",
    description=GET_TAXONOMY_DOC,
)
async def get_taxonomy(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    site_id = resolve_mcp_site_id(request)
    return taxonomy_service.public_taxonomy_view(site_id)


get_taxonomy.__doc__ = GET_TAXONOMY_DOC


@router.put(
    "/mcp/taxonomy",
    operation_id="replace_taxonomy",
    dependencies=[Depends(require_scope("write:taxonomy"))],
    summary="Replace site vocabularies (bootstrap)",
    description=REPLACE_TAXONOMY_DOC,
)
async def replace_taxonomy(
    body: ReplaceTaxonomyBody,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    site_id = resolve_mcp_site_id(request)
    try:
        return await taxonomy_service.replace_taxonomy(
            site_id,
            primary_vocabulary=body.primary_vocabulary,
            vocabularies=body.vocabularies,
        )
    except Exception as e:
        raise _map_taxonomy_error(e) from e


replace_taxonomy.__doc__ = REPLACE_TAXONOMY_DOC


@router.put(
    "/mcp/taxonomy/vocabularies/{key}",
    operation_id="upsert_vocabulary",
    dependencies=[Depends(require_scope("write:taxonomy"))],
    summary="Create or update one vocabulary",
    description=UPSERT_VOCABULARY_DOC,
)
async def upsert_vocabulary(
    key: str,
    body: UpsertVocabularyBody,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    site_id = resolve_mcp_site_id(request)
    try:
        return await taxonomy_service.upsert_vocabulary(
            site_id,
            key,
            label=body.label,
            controlled=body.controlled,
            terms=body.terms,
        )
    except Exception as e:
        raise _map_taxonomy_error(e) from e


upsert_vocabulary.__doc__ = UPSERT_VOCABULARY_DOC


@router.delete(
    "/mcp/taxonomy/vocabularies/{key}",
    operation_id="delete_vocabulary",
    dependencies=[Depends(require_scope("write:taxonomy"))],
    summary="Delete one vocabulary",
    description=DELETE_VOCABULARY_DOC,
)
async def delete_vocabulary(
    key: str,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    site_id = resolve_mcp_site_id(request)
    try:
        return await taxonomy_service.delete_vocabulary(site_id, key)
    except Exception as e:
        raise _map_taxonomy_error(e) from e


delete_vocabulary.__doc__ = DELETE_VOCABULARY_DOC


@router.post(
    "/mcp/taxonomy/vocabularies/{key}/terms",
    operation_id="add_taxonomy_term",
    dependencies=[Depends(require_scope("write:taxonomy"))],
    summary="Add a term to a vocabulary",
    description=ADD_TERM_DOC,
)
async def add_taxonomy_term(
    key: str,
    body: TermBody,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    site_id = resolve_mcp_site_id(request)
    try:
        return await taxonomy_service.add_taxonomy_term(site_id, key, body.term)
    except Exception as e:
        raise _map_taxonomy_error(e) from e


add_taxonomy_term.__doc__ = ADD_TERM_DOC


@router.delete(
    "/mcp/taxonomy/vocabularies/{key}/terms",
    operation_id="remove_taxonomy_term",
    dependencies=[Depends(require_scope("write:taxonomy"))],
    summary="Remove a term from a vocabulary",
    description=REMOVE_TERM_DOC,
)
async def remove_taxonomy_term(
    key: str,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
    term: str = Query(..., description="Exact term string to remove."),
) -> Dict[str, Any]:
    site_id = resolve_mcp_site_id(request)
    try:
        return await taxonomy_service.remove_taxonomy_term(site_id, key, term)
    except Exception as e:
        raise _map_taxonomy_error(e) from e


remove_taxonomy_term.__doc__ = REMOVE_TERM_DOC


@router.post(
    "/mcp/taxonomy/primary",
    operation_id="set_primary_vocabulary",
    dependencies=[Depends(require_scope("write:taxonomy"))],
    summary="Set the primary vocabulary",
    description=SET_PRIMARY_DOC,
)
async def set_primary_vocabulary(
    body: PrimaryVocabularyBody,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    site_id = resolve_mcp_site_id(request)
    try:
        return await taxonomy_service.set_primary_vocabulary(site_id, body.key)
    except Exception as e:
        raise _map_taxonomy_error(e) from e


set_primary_vocabulary.__doc__ = SET_PRIMARY_DOC
