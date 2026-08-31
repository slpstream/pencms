# Core and Pro editions

PenCMS Core is a complete MIT CMS. PenCMS Pro is a private overlay package
(`pencms_pro`) that registers extra routers, publish adapters, a storage
type, and admin pages via hooks. Core never contains Pro source. Pro never
forks Core files.

Edition is **overlay presence**, not a `config.ini` flag. If
`pencms_pro.init_pro(app)` ran at boot, `/api/config` and `/api/auth/me`
report `"edition": "pro"`; otherwise `"core"`.

Load a sibling overlay checkout with `PYTHONPATH` pointed at the Pro repo
(the parent of the `pencms_pro` package) and `PENCMS_PRO_ADMIN` pointed at
the overlay admin directory. Core does **not** prepend a sibling path onto
`sys.path` automatically — default tests must stay `edition=core`.

```bash
export PYTHONPATH=/path/to/pencms-pro${PYTHONPATH:+:$PYTHONPATH}
export PENCMS_PRO_ADMIN=/path/to/pencms-pro/frontend-php/src/admin
```

```python
# backend-python/app/main.py — after Core include_router calls
try:
    import pencms_pro
except ImportError:
    pass          # Core boot — no overlay installed
else:
    pencms_pro.init_pro(app)   # overlay bugs fail boot loudly
    set_edition("pro")

mcp = FastApiMCP(...)  # scans tagged routes; Pro must register before this
```

Swallow **only** `ImportError` on the `import`. `init_pro` sits in the
`else` so a half-mounted overlay cannot boot as `edition=core`.

PHP/JS read `edition` from the session (`$store.app.edition`). Do not
probe the disk with `file_exists()` to decide nav. Combined PHP serves
`admin-users.php` / `admin-settings-sites.php` (and their JS) from
`PENCMS_PRO_ADMIN` when Core `src/admin/` does not have those files.

**Phase 6 (2026-08-30):** Physical cut. Pro Python (users
HTTP, sites CRUD, four cloud publish adapters, `SSHStorageProvider`) and
Pro PHP admin pages live in the sibling `pencms-pro` repo. Core `try:
import pencms_pro` is the MIT-tree hook. Combined-checkout pyright
`extraPaths` includes `../../pencms-pro`. Core CI is
`python -m pytest -m "not pro"`. Combined checkout runs the full suite
with `PYTHONPATH` set. Edition grep gates live in
`backend-python/tests/test_edition_gates.py`.

**Theme workshop restored to Core (2026-08-31):** zip/URL install, Theme
Settings export/packaging, MCP inspect/customize, and the Customize AI
rail ship in Core. Pro overlay is users + sites CRUD + cloud publish +
SSH storage only.

See `gitignore/core-pro_split_plan3.md` (local planning) for the locked
feature allocation and phase order. Decision record: the **Core / Pro
editions** section in [`product_thesis.md`](./product_thesis.md).
