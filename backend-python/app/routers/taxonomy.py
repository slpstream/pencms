from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict
import config
from routers.auth import get_current_user, UserPublic
from services.site_service import resolve_human_site_id
from services.taxonomy_service import TaxonomyError, persist_taxonomy_document

router = APIRouter(prefix="/taxonomy", tags=["taxonomy"])


@router.get("/")
async def get_taxonomy_data(
    current_user: UserPublic = Depends(get_current_user),
    site_id: str = Depends(resolve_human_site_id),
) -> Dict[str, Any]:
    """Returns the raw taxonomy.yaml data and parsed state for the active site."""
    snap = config.load_taxonomy_for_site(site_id)
    return {
        "raw": snap.get("raw") or {
            "vocabularies": snap["vocabularies"],
            "primary_vocabulary": snap["primary_vocabulary"],
            "required_fields": snap["required_fields"],
        },
        "parsed": {
            "vocabularies": snap["vocabularies"],
            "primary_vocabulary": snap["primary_vocabulary"],
            "required_fields": snap["required_fields"],
            "primary_terms": snap["primary_terms"],
        },
        "site_id": site_id,
    }


@router.put("/")
async def update_taxonomy_data(
    data: Dict[str, Any],
    current_user: UserPublic = Depends(get_current_user),
    site_id: str = Depends(resolve_human_site_id),
):
    """Updates the active site's taxonomy.yaml and invalidates cache."""
    if "vocabularies" not in data:
        raise HTTPException(status_code=400, detail="Missing 'vocabularies' key")

    try:
        await persist_taxonomy_document(site_id, data)
        return {"message": "Taxonomy updated and reloaded successfully", "site_id": site_id}
    except TaxonomyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update taxonomy: {str(e)}")
