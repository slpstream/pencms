import sys
import os
# Ensure that the app directory is in sys.path to resolve routers, services, and models imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from routers.pages import router as pages_router
from routers.assets import router as assets_router
from routers.taxonomy import router as taxonomy_router
from routers.storage import router as storage_router
from routers.auth import router as auth_router
from routers.v1 import router as v1_router
from routers.ai_proxy import router as ai_router
from routers.menus import router as menus_router
from routers.authors import router as authors_router
from routers.mcp_tools import router as mcp_tools_router
from routers.mcp_menus import router as mcp_menus_router
from routers.mcp_authors import router as mcp_authors_router
from routers.mcp_taxonomy import router as mcp_taxonomy_router
from routers.mcp_site_presentation import router as mcp_site_presentation_router
from routers.mcp_feedback import router as mcp_feedback_router
from routers.mcp_comments import router as mcp_comments_router
from routers.mcp_prompts import router as mcp_prompts_router
from routers.oauth_mcp import router as oauth_mcp_router, require_mcp_bearer
from routers.sites import router as sites_router
from routers.theme_customize import router as theme_customize_router
from routers.theme_style import router as theme_style_router
from routers.theme_package import router as theme_package_router
from routers.theme_install import router as theme_install_router
from routers.mcp_theme_inspect import router as mcp_theme_inspect_router
from routers.mcp_theme_customize import router as mcp_theme_customize_router
from routers.publish import router as publish_router
from routers.translations import router as translations_router
from routers.feedback import router as feedback_router
from routers.comments_admin import router as comments_admin_router
from fastapi_mcp import FastApiMCP
from fastapi_mcp.types import AuthConfig
from services.edition import get_edition, set_edition
from services.llms_service import get_llms_content
from services.mcp_rate_limit import McpRateLimitMiddleware
from services.mcp_session_guard import McpSessionGuardMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    import logging
    from config import content_storage
    from services.cache_service import sync_cache_with_storage
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    logging.getLogger("uvicorn.error").info("PenCMS API started (git-pull loop)")
    # Start cache synchronization in the background
    asyncio.create_task(sync_cache_with_storage(content_storage))
    yield


app = FastAPI(
    title="pencms — Blog CMS API",
    description="FastAPI backend for a Markdown-first blog CMS with configurable taxonomy.",
    version="0.2.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
# Loop-test marker (safe to keep): StatReload watches this file.

_DEFAULT_CORS_ORIGINS = "http://127.0.0.1:8009,http://localhost:8009"


def _cors_allow_origins() -> list[str]:
    """Admin UI origins from CORS_ALLOW_ORIGINS (comma-separated). Non-browser MCP agents omit Origin and are unaffected."""
    raw = os.environ.get("CORS_ALLOW_ORIGINS", _DEFAULT_CORS_ORIGINS)
    return [o.strip() for o in raw.split(",") if o.strip()]


# Inner: session-header hint. Then loop-guard. Outer: CORS so 400/429s still get ACAO.
app.add_middleware(McpSessionGuardMiddleware)
app.add_middleware(McpRateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(pages_router, prefix="/api")
app.include_router(assets_router, prefix="/api")
app.include_router(taxonomy_router, prefix="/api")
app.include_router(storage_router, prefix="/api")
app.include_router(v1_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(menus_router, prefix="/api")
app.include_router(authors_router, prefix="/api")
app.include_router(mcp_tools_router)
app.include_router(mcp_menus_router)
app.include_router(mcp_authors_router)
app.include_router(mcp_taxonomy_router)
app.include_router(mcp_site_presentation_router)
app.include_router(mcp_feedback_router)
app.include_router(mcp_comments_router)
app.include_router(mcp_prompts_router)
app.include_router(oauth_mcp_router)
app.include_router(sites_router, prefix="/api")  # GET + PATCH + og-preview; CRUD from init_pro
app.include_router(theme_customize_router, prefix="/api")
app.include_router(theme_style_router, prefix="/api")
app.include_router(theme_package_router, prefix="/api")
app.include_router(theme_install_router, prefix="/api")
app.include_router(mcp_theme_inspect_router)
app.include_router(mcp_theme_customize_router)
app.include_router(publish_router, prefix="/api")
app.include_router(translations_router, prefix="/api")
app.include_router(feedback_router, prefix="/api")
app.include_router(comments_admin_router, prefix="/api")

# Overlay hook — must run BEFORE FastApiMCP so Pro MCP routes are scanned.
# Only the import is optional. init_pro failures (including ImportError
# from a missing Pro submodule) must fail boot, not silently become Core.
try:
    # Overlay is optional; Core-only checkouts have no pencms_pro on the
    # type-checker path. Combined checkout lists sibling pencms-pro in extraPaths.
    import pencms_pro  # pyright: ignore[reportMissingImports]
except ImportError:
    pass
else:
    pencms_pro.init_pro(app)
    set_edition("pro")

import config as _storage_config

_storage_config.bind_registered_storage()

mcp = FastApiMCP(
    fastapi=app,
    name="PenCMS",
    description="PenCMS content management tools for AI agents",
    include_tags=["mcp"],
    auth_config=AuthConfig(dependencies=[Depends(require_mcp_bearer)]),
)
mcp.mount_http(mount_path="/api/mcp")

@app.get("/llms.txt", response_class=PlainTextResponse)
async def llms_txt():
    """Machine-readable MCP discovery for agents (here.now-inspired)."""
    return PlainTextResponse(get_llms_content())


@app.get("/api")
@app.get("/api/")
async def root():
    return {
        "message": "pencms Blog CMS API",
        "health": "/api/health",
        "docs": "/api/docs"
    }


@app.get("/api/config")
async def get_config(request: Request):
    from config import DOMAINS, STATUS_VALUES, MAX_UPLOAD_SIZE, load_taxonomy_for_site
    from services.site_service import resolve_human_site_id

    try:
        site_id = resolve_human_site_id(request)
    except Exception:
        site_id = "default"
    snap = load_taxonomy_for_site(site_id)
    # Always use API raw URLs so site-embedded paths work for local + SSH.
    asset_base_url = "/api/assets/raw/"

    return {
        "domains": DOMAINS,
        "status_values": STATUS_VALUES,
        "required_fields": snap["required_fields"],
        "max_upload_size": MAX_UPLOAD_SIZE,
        "taxonomy": snap["vocabularies"],
        "primary_vocabulary": snap["primary_vocabulary"],
        "asset_base_url": asset_base_url,
        "site_id": site_id,
        "edition": get_edition(),
    }


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc)},
    )


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    from config import API_PORT
    uvicorn.run("main:app", host="127.0.0.1", port=API_PORT)
