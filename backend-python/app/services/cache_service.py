import sqlite3
import json
import logging
import time
import asyncio
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
import frontmatter

from services.site_service import DEFAULT_SITE_ID, get_site

logger = logging.getLogger("pencms.cache")


def _site_default_language(site_id: str) -> str:
    site = get_site(site_id)
    return site.language if site is not None else "en"


def _db_path() -> Path:
    from config import BASE_DIR

    return Path(BASE_DIR) / "data" / ".cms_cache.db"


def get_db_connection() -> sqlite3.Connection:
    """Get a connection to the SQLite database with WAL mode enabled."""
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=15.0)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrency
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize the SQLite database schema."""
    with get_db_connection() as conn:
        # The cache is disposable: rebuild whenever identity-bearing columns/PK drift.
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='entries'"
        ).fetchone()
        if row:
            sql = row[0] or ""
            cols = {
                r[1]
                for r in conn.execute("PRAGMA table_info(entries)").fetchall()
            }
            needs_rebuild = (
                "filepath TEXT NOT NULL UNIQUE" in sql
                or "site_id" not in cols
                or "language" not in cols
                or "translation_group" not in cols
                or "PRIMARY KEY (collection, slug)" in sql
                or "PRIMARY KEY (site_id, collection, slug)" in sql
            )
            if needs_rebuild:
                logger.info("Recreating entries table for language-aware PK migration...")
                conn.execute("DROP TABLE IF EXISTS entries_fts")
                conn.execute("DROP TABLE IF EXISTS entries")
                conn.commit()

        conn.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                site_id TEXT NOT NULL,
                slug TEXT NOT NULL,
                collection TEXT NOT NULL,
                language TEXT NOT NULL,
                translation_group TEXT,
                filepath TEXT NOT NULL,
                title TEXT,
                published INTEGER DEFAULT 1,
                status TEXT,
                domain TEXT,
                needs_review INTEGER DEFAULT 0,
                publish_at TEXT,
                modified_at REAL NOT NULL,
                frontmatter TEXT NOT NULL,
                body TEXT NOT NULL,
                PRIMARY KEY (site_id, collection, slug, language)
            )
        """)
        # Migrate older caches that lack publish_at
        cols = {
            r[1]
            for r in conn.execute("PRAGMA table_info(entries)").fetchall()
        }
        if "publish_at" not in cols:
            conn.execute("ALTER TABLE entries ADD COLUMN publish_at TEXT")
        # Indexes for fast querying
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entries_collection ON entries(collection)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entries_status ON entries(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entries_published ON entries(published)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entries_filepath ON entries(filepath)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entries_site_id ON entries(site_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entries_site_language ON entries(site_id, language)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entries_site_group ON entries(site_id, translation_group)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entries_publish_at ON entries(publish_at)")
        
        # Create FTS5 virtual table for full-text search
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
                slug,
                collection,
                language UNINDEXED,
                translation_group UNINDEXED,
                title,
                body,
                frontmatter,
                content='entries',
                content_rowid='rowid'
            )
        """)
        conn.commit()
    logger.info("SQLite cache database initialized.")

# Run initialization
init_db()

# --- Sync Logic ---

async def sync_cache_with_storage(storage_provider):
    """Scan storage_provider and bring the local SQLite cache up to date.
    
    Performs delta sync to avoid reading unchanged files.
    """
    logger.info("Starting SQLite cache synchronization with storage provider...")
    
    # 1. Get canonical files list from storage
    # We import iter_canonical_files here to avoid circular imports
    from services.file_service import (
        content_identity_for_path,
        iter_canonical_files,
        path_to_id,
        site_id_from_filepath,
    )
    from services.i18n_service import ContentI18nError
    
    try:
        canonical_paths = await iter_canonical_files()
    except ContentI18nError:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve canonical files from storage: {e}")
        return
        
    storage_set = set(canonical_paths)
    
    # 2. Get currently cached entries and determine deletions
    cached_entries = {}
    to_delete = []
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT filepath, modified_at, slug, collection, site_id, language FROM entries"
        ).fetchall()
        for r in rows:
            if r["filepath"] not in storage_set:
                to_delete.append((
                    r["filepath"],
                    r["site_id"],
                    r["collection"],
                    r["slug"],
                    r["language"],
                ))
            else:
                cached_entries[r["filepath"]] = {
                    "modified_at": r["modified_at"],
                    "slug": r["slug"],
                    "collection": r["collection"],
                    "site_id": r["site_id"],
                    "language": r["language"],
                }
            
    # Process deletions
    if to_delete:
        # A background sync can overlap a write. Recheck storage before
        # applying the stale canonical snapshot so a newly-created file is
        # never deleted from cache by the earlier scan.
        confirmed_deletions = []
        for filepath, site_id, collection, slug, language in to_delete:
            if not await storage_provider.exists(filepath):
                confirmed_deletions.append((site_id, collection, slug, language))
        if confirmed_deletions:
            logger.info(
                "Removing %s deleted entries from cache.",
                len(confirmed_deletions),
            )
            with get_db_connection() as conn:
                conn.executemany(
                    "DELETE FROM entries WHERE site_id = ? AND collection = ? AND slug = ? AND language = ?",
                    confirmed_deletions,
                )
                conn.commit()

    # Determine additions or updates
    to_update_or_add = []
    for filepath in canonical_paths:
        # Check stat
        try:
            file_stat = await storage_provider.stat(filepath)
            mtime = file_stat.get("mtime", 0.0)
        except Exception as e:
            logger.warning(f"Could not stat file {filepath}: {e}")
            mtime = 0.0
            
        if filepath not in cached_entries or abs(cached_entries[filepath]["modified_at"] - mtime) > 1.0:
            to_update_or_add.append((filepath, mtime))

    if to_update_or_add:
        logger.info(f"Syncing {len(to_update_or_add)} new or modified files to cache...")
        
        # Read and insert each file
        for filepath, mtime in to_update_or_add:
            try:
                # 1. Read from storage
                raw_content = await storage_provider.read(filepath)
                post = frontmatter.loads(raw_content)
                
                # 2. Parse frontmatter
                fm_dict = dict(post.metadata)
                if "articles" in fm_dict and "posts" not in fm_dict:
                    fm_dict["posts"] = fm_dict["articles"]
                    fm_dict["is_legacy"] = True
                body = post.content or ""
                
                # Determine collection (category) and slug (id)
                # Collection is derived from frontmatter category, slug is path_to_id
                slug = path_to_id(filepath)
                collection = fm_dict.get("category") or "general"
                site_id = site_id_from_filepath(filepath)
                identity = content_identity_for_path(filepath, site_id)
                language = identity.language
                translation_group = fm_dict.get("translation_group")
                
                # Enrich metadata
                title = fm_dict.get("title") or fm_dict.get("name") or slug.replace("-", " ").capitalize()
                published = 1 if fm_dict.get("published", True) else 0
                status = fm_dict.get("status", "published")
                domain = fm_dict.get("domain", "blog")
                needs_review = 1 if fm_dict.get("needs_review", False) else 0
                from models.page import normalize_publish_at
                try:
                    publish_at = normalize_publish_at(fm_dict.get("publish_at"))
                except ValueError:
                    publish_at = None
                
                # Save to db
                with get_db_connection() as conn:
                    conn.execute(
                        "DELETE FROM entries WHERE filepath = ? AND (collection != ? OR site_id != ? OR language != ?)",
                        (filepath, collection, site_id, language),
                    )
                    conn.execute("""
                        INSERT INTO entries (site_id, slug, collection, language, translation_group, filepath, title, published, status, domain, needs_review, publish_at, modified_at, frontmatter, body)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(site_id, collection, slug, language) DO UPDATE SET
                            translation_group = excluded.translation_group,
                            filepath = excluded.filepath,
                            title = excluded.title,
                            published = excluded.published,
                            status = excluded.status,
                            domain = excluded.domain,
                            needs_review = excluded.needs_review,
                            publish_at = excluded.publish_at,
                            modified_at = excluded.modified_at,
                            frontmatter = excluded.frontmatter,
                            body = excluded.body
                        WHERE excluded.modified_at >= entries.modified_at
                    """, (
                        site_id, slug, collection, language, translation_group, filepath, title, published, status, domain, needs_review, publish_at, mtime,
                        json.dumps(fm_dict), body
                    ))
                    conn.commit()
            except Exception as e:
                logger.error(f"Error syncing cache for {filepath}: {e}")
                
        # Rebuild FTS index to sync the virtual table with the updated content
        try:
            with get_db_connection() as conn:
                conn.execute("INSERT INTO entries_fts(entries_fts) VALUES('rebuild')")
                conn.commit()
        except Exception as fts_err:
            logger.error(f"Failed to rebuild FTS index on sync: {fts_err}")
            
    logger.info("SQLite cache synchronization completed successfully.")

# --- Database Operations ---

def get_entry(
    collection: str,
    slug: str,
    site_id: str = DEFAULT_SITE_ID,
    language: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve an entry details from the SQLite cache."""
    resolved_language = language or _site_default_language(site_id)
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM entries WHERE site_id = ? AND collection = ? AND slug = ? AND language = ?",
            (site_id, collection, slug, resolved_language)
        ).fetchone()
        if not row:
            return None
        return dict(row)

def save_entry_to_cache(
    collection: str,
    slug: str,
    filepath: str,
    title: str,
    published: bool,
    status: str,
    domain: str,
    needs_review: bool,
    mtime: float,
    frontmatter_dict: dict,
    body: str,
    site_id: str = DEFAULT_SITE_ID,
    language: Optional[str] = None,
    translation_group: Optional[str] = None,
):
    """Directly insert or update an entry in the SQLite cache (write-through)."""
    resolved_language = language or _site_default_language(site_id)
    if translation_group is None:
        translation_group = frontmatter_dict.get("translation_group")
    from models.page import normalize_publish_at
    try:
        publish_at = normalize_publish_at(frontmatter_dict.get("publish_at"))
    except ValueError:
        publish_at = None
    with get_db_connection() as conn:
        conn.execute(
            "DELETE FROM entries WHERE filepath = ? AND (collection != ? OR site_id != ? OR language != ?)",
            (filepath, collection, site_id, resolved_language),
        )
        conn.execute("""
            INSERT INTO entries (site_id, slug, collection, language, translation_group, filepath, title, published, status, domain, needs_review, publish_at, modified_at, frontmatter, body)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(site_id, collection, slug, language) DO UPDATE SET
                translation_group = excluded.translation_group,
                filepath = excluded.filepath,
                title = excluded.title,
                published = excluded.published,
                status = excluded.status,
                domain = excluded.domain,
                needs_review = excluded.needs_review,
                publish_at = excluded.publish_at,
                modified_at = excluded.modified_at,
                frontmatter = excluded.frontmatter,
                body = excluded.body
            WHERE excluded.modified_at >= entries.modified_at
        """, (
            site_id, slug, collection, resolved_language, translation_group, filepath, title, 1 if published else 0, status, domain, 1 if needs_review else 0, publish_at, mtime,
            json.dumps(frontmatter_dict), body
        ))
        conn.commit()
        try:
            conn.execute("INSERT INTO entries_fts(entries_fts) VALUES('rebuild')")
            conn.commit()
        except Exception as fts_err:
            logger.warning("FTS rebuild after cache write failed: %s", fts_err)

def delete_entry_from_cache(
    collection: str,
    slug: str,
    site_id: str = DEFAULT_SITE_ID,
    language: Optional[str] = None,
):
    """Remove an entry from the SQLite cache."""
    resolved_language = language or _site_default_language(site_id)
    with get_db_connection() as conn:
        conn.execute(
            "DELETE FROM entries WHERE site_id = ? AND collection = ? AND slug = ? AND language = ?",
            (site_id, collection, slug, resolved_language),
        )
        conn.execute("INSERT INTO entries_fts(entries_fts) VALUES('rebuild')")
        conn.commit()


def _rebuild_fts(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("INSERT INTO entries_fts(entries_fts) VALUES('rebuild')")
        conn.commit()
    except Exception as fts_err:
        logger.warning("FTS rebuild failed: %s", fts_err)


def delete_entries_for_site(site_id: str) -> int:
    """Purge all cache rows for a site_id and rebuild FTS. Returns rows deleted."""
    with get_db_connection() as conn:
        cur = conn.execute("DELETE FROM entries WHERE site_id = ?", (site_id,))
        deleted = cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else 0
        conn.commit()
        _rebuild_fts(conn)
        return deleted


def reassign_entries_site_id(old_id: str, new_id: str) -> int:
    """Rewrite entries from old_id → new_id (PK-safe) and update filepaths.

    Returns number of rows reassigned. Raises ValueError on slug/collection
    collision at the destination site.
    """
    if old_id == new_id:
        return 0
    old_prefix = f"sites/{old_id}/"
    new_prefix = f"sites/{new_id}/"
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM entries WHERE site_id = ?", (old_id,)
        ).fetchall()
        if not rows:
            return 0

        for row in rows:
            conflict = conn.execute(
                "SELECT 1 FROM entries WHERE site_id = ? AND collection = ? AND slug = ? AND language = ?",
                (new_id, row["collection"], row["slug"], row["language"]),
            ).fetchone()
            if conflict:
                raise ValueError(
                    f"FTS collision: {new_id}/{row['collection']}/{row['slug']}/{row['language']} already exists"
                )

        moved = 0
        for row in rows:
            fp = row["filepath"] or ""
            if fp.startswith(old_prefix):
                new_fp = new_prefix + fp[len(old_prefix) :]
            elif fp == f"sites/{old_id}":
                new_fp = f"sites/{new_id}"
            else:
                new_fp = fp
            conn.execute(
                "DELETE FROM entries WHERE site_id = ? AND collection = ? AND slug = ? AND language = ?",
                (old_id, row["collection"], row["slug"], row["language"]),
            )
            conn.execute(
                """
                INSERT INTO entries (
                    site_id, slug, collection, language, translation_group, filepath, title, published, status,
                    domain, needs_review, publish_at, modified_at, frontmatter, body
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id,
                    row["slug"],
                    row["collection"],
                    row["language"],
                    row["translation_group"],
                    new_fp,
                    row["title"],
                    row["published"],
                    row["status"],
                    row["domain"],
                    row["needs_review"],
                    row["publish_at"] if "publish_at" in row.keys() else None,
                    row["modified_at"],
                    row["frontmatter"],
                    row["body"],
                ),
            )
            moved += 1
        conn.commit()
        _rebuild_fts(conn)
        return moved


def delete_entries_by_site_and_slugs(site_id: str, slugs: List[str]) -> int:
    """Delete cache rows for specific slugs under a site. Returns rows deleted."""
    if not slugs:
        return 0
    with get_db_connection() as conn:
        deleted = 0
        for slug in slugs:
            cur = conn.execute(
                "DELETE FROM entries WHERE site_id = ? AND slug = ?",
                (site_id, slug),
            )
            if cur.rowcount and cur.rowcount > 0:
                deleted += cur.rowcount
        conn.commit()
        _rebuild_fts(conn)
        return deleted


def query_entries(
    collection: str,
    page: int = 1,
    limit: int = 20,
    status: Optional[str] = None,
    published: Optional[bool] = None,
    site_id: str = DEFAULT_SITE_ID,
    language: Optional[str] = None,
    fallback: str = "none",
) -> Tuple[List[Dict[str, Any]], int]:
    """Retrieve entries paginated and filtered from SQLite cache."""
    offset = (page - 1) * limit
    site = get_site(site_id)
    default_language = site.language if site is not None else "en"
    active = bool(
        site is not None
        and len(site.languages) >= 2
        and default_language in site.languages
    )
    requested_language = language or default_language
    base_language = (
        default_language
        if active and fallback == "default" and requested_language != default_language
        else (requested_language if active else None)
    )

    query = (
        "SELECT slug, title, published, filepath, modified_at, status, domain, "
        "needs_review, publish_at, frontmatter, site_id, language, translation_group "
        "FROM entries WHERE site_id = ? AND collection = ?"
    )
    params: List[Any] = [site_id, collection]
    if base_language is not None:
        query += " AND language = ?"
        params.append(base_language)
    
    if status is not None:
        query += " AND status = ?"
        params.append(status)
        
    if published is not None:
        query += " AND published = ?"
        params.append(1 if published else 0)
        
    # Order by last modified desc
    query += " ORDER BY modified_at DESC"
    
    # Get total count first
    count_query = f"SELECT COUNT(*) FROM ({query})"
    
    # Paginate
    query += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    with get_db_connection() as conn:
        total = conn.execute(count_query, params[:-2]).fetchone()[0]
        rows = conn.execute(query, params).fetchall()

        if active and fallback == "default" and requested_language != default_language:
            merged_rows = []
            now_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            for default_row in rows:
                default_live = (
                    default_row["status"] == "published"
                    and (
                        not default_row["publish_at"]
                        or default_row["publish_at"] <= now_iso
                    )
                )
                target = None
                if default_live:
                    target = conn.execute(
                        """
                        SELECT slug, title, published, filepath, modified_at, status,
                               domain, needs_review, publish_at, frontmatter, site_id,
                               language, translation_group
                        FROM entries
                        WHERE site_id = ? AND collection = ? AND slug = ? AND language = ?
                          AND translation_group = ?
                          AND status = 'published'
                          AND (needs_review IS NULL OR needs_review = 0)
                          AND (publish_at IS NULL OR publish_at = '' OR publish_at <= ?)
                        """,
                        (
                            site_id,
                            collection,
                            default_row["slug"],
                            requested_language,
                            default_row["translation_group"],
                            now_iso,
                        ),
                    ).fetchone()
                merged_rows.append((target or default_row, target is None))
        else:
            merged_rows = [(row, False) for row in rows]
        
        items = []
        for r, is_fallback in merged_rows:
            # Format modified_at to ISO string
            mtime_epoch = r["modified_at"]
            iso_time = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(mtime_epoch))
            try:
                fm = json.loads(r["frontmatter"]) if r["frontmatter"] else {}
            except Exception:
                fm = {}
            item = {
                "slug": r["slug"],
                "title": r["title"],
                "published": bool(r["published"]),
                "modified_at": iso_time,
                "status": r["status"],
                "domain": r["domain"],
                "frontmatter": fm,
                "site_id": r["site_id"],
            }
            if active:
                peer_rows = conn.execute(
                    """
                    SELECT language, status, published, needs_review
                    FROM entries
                    WHERE site_id = ? AND collection = ? AND slug = ? AND language != ?
                    ORDER BY language
                    """,
                    (site_id, collection, r["slug"], r["language"]),
                ).fetchall()
                item.update({
                    "language": r["language"],
                    "translation_group": r["translation_group"],
                    "translations": [
                        {
                            "language": peer["language"],
                            "status": peer["status"],
                            "published": bool(peer["published"]),
                            "needs_review": bool(peer["needs_review"]),
                        }
                        for peer in peer_rows
                    ],
                    "is_fallback": is_fallback,
                })
            items.append(item)
            
        return items, total

def get_collections_list(site_id: Optional[str] = DEFAULT_SITE_ID) -> List[Dict[str, Any]]:
    """Retrieve distinct collections inside the cache."""
    with get_db_connection() as conn:
        conn.execute("DELETE FROM entries WHERE collection = '' OR collection IS NULL")
        conn.commit()
        if site_id is not None:
            rows = conn.execute(
                "SELECT DISTINCT collection FROM entries WHERE site_id = ?",
                (site_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT DISTINCT collection FROM entries").fetchall()
        collections = []
        for r in rows:
            col_name = r["collection"]
            if not col_name:
                continue
            collections.append({
                "name": col_name,
                "path": f"/{col_name}",
                "schema": {}
            })
        return collections

def search_entries(
    query: str,
    limit: int = 20,
    site_id: str = DEFAULT_SITE_ID,
    language: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Full-text search across cached entries using FTS5 (scoped to site_id).
    
    Returns matches ranked by relevance. Each result includes slug,
    collection, title, and a snippet of the matching body text.
    """
    if not query.strip():
        return []
    # FTS5 query syntax: wrap the user input in quotes to treat it as
    # a phrase query. Advanced users can use FTS5 query syntax directly
    # by leaving the quotes off, but v1 defaults to phrase mode for safety.
    escaped_query = query.replace('"', '""')
    fts_query = f'"{escaped_query}"'
    params: list[Any] = [fts_query, site_id]
    language_clause = ""
    if language is not None:
        language_clause = " AND e.language = ?"
        params.append(language)
    params.append(limit)
    with get_db_connection() as conn:
        rows = conn.execute(f"""
            SELECT e.slug, e.collection, e.title, e.site_id, e.language,
                   e.translation_group,
                   snippet(entries_fts, 5, '<mark>', '</mark>', '…', 32) as excerpt,
                   bm25(entries_fts) as rank
            FROM entries_fts
            JOIN entries e ON e.rowid = entries_fts.rowid
            WHERE entries_fts MATCH ? AND e.site_id = ?{language_clause}
            ORDER BY rank
            LIMIT ?
        """, params).fetchall()
        return [dict(r) for r in rows]
