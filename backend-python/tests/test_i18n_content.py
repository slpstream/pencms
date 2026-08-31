"""Slice 2 file encoding, cache identity, and read-contract coverage."""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path

import frontmatter
import pytest
import yaml

from models.page import Page, PageFrontmatter


GROUP = "tg_" + ("a" * 32)


@pytest.fixture
def clean_i18n_site(authed_client, temp_data_root: Path):
    """Reset default-site files, registry, and disposable cache per test."""
    from services.cache_service import get_db_connection, init_db
    from services.site_service import ensure_sites_initialized

    sites_yaml = temp_data_root / "data" / "sites.yaml"
    if sites_yaml.exists():
        sites_yaml.unlink()
    sites_root = temp_data_root / "content" / "sites"
    if sites_root.exists():
        shutil.rmtree(sites_root)
    ensure_sites_initialized()
    init_db()
    with get_db_connection() as conn:
        conn.execute("DELETE FROM entries")
        conn.execute("INSERT INTO entries_fts(entries_fts) VALUES('rebuild')")
        conn.commit()
    return temp_data_root / "content" / "sites" / "default"


def _activate(client) -> None:
    response = client.patch(
        "/api/sites/default",
        json={"language": "en", "languages": ["en", "fr"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["i18n_active"] is True


def _document(
    *,
    name: str,
    language: str,
    body: str,
    group: str = GROUP,
    status: str = "published",
    published: bool = True,
    composite: bool = False,
    publish_at: str | None = None,
    page: bool = False,
    extra: dict | None = None,
) -> str:
    metadata = {
        "name": name,
        "category": "summer",
        "status": status,
        "published": published,
        "language": language,
        "translation_group": group,
        "page": page,
    }
    if publish_at is not None:
        metadata["publish_at"] = publish_at
    if extra:
        metadata.update(extra)
    if composite:
        metadata["composite"] = True
        metadata["posts"] = [{"id": "bio", "content": "_bio.md"}]
    return frontmatter.dumps(frontmatter.Post(body, **metadata))


def test_pattern_b_discovery_exact_read_and_locale_partials(
    authed_client, clean_i18n_site
):
    from services.file_service import iter_canonical_files, path_to_id, read_page

    _activate(authed_client)
    default_dir = clean_i18n_site / "about"
    french_dir = default_dir / "fr"
    french_dir.mkdir(parents=True)
    (default_dir / "index.md").write_text(
        _document(name="About", language="en", body="English", composite=True)
    )
    (default_dir / "_bio.md").write_text("English bio")
    (french_dir / "index.md").write_text(
        _document(name="About", language="fr", body="Français", composite=True)
    )
    (french_dir / "_bio.md").write_text("Biographie")

    canonical = asyncio.run(iter_canonical_files("default"))
    assert "sites/default/about/index.md" in canonical
    assert "sites/default/about/fr/index.md" in canonical
    assert path_to_id("sites/default/about/fr/index.md") == "about"

    page = asyncio.run(
        read_page(
            "about",
            site_id="default",
            language="fr",
            include_partials=True,
        )
    )
    assert page is not None
    assert page.language == "fr"
    assert page.content.strip() == "Français"
    assert page.partials == {"bio": "Biographie"}
    assert [peer.language for peer in page.translations or []] == ["en"]


def test_site_ui_string_files_are_not_discovered_as_content(
    authed_client, clean_i18n_site
):
    from services.file_service import iter_canonical_files

    _activate(authed_client)
    strings_dir = clean_i18n_site / "strings"
    strings_dir.mkdir()
    (strings_dir / "en.json").write_text('{"relatedPosts": "Related Posts"}')
    (strings_dir / "fr.json").write_text('{"relatedPosts": "Articles associés"}')

    canonical = asyncio.run(iter_canonical_files("default"))
    assert all("/strings/" not in path for path in canonical)

    response = authed_client.get("/api/pages/")
    assert response.status_code == 200, response.text
    assert response.json() == []


@pytest.mark.parametrize(
    ("relative_path", "message"),
    [
        ("about/en/index.md", "default language"),
        ("about/de/index.md", "not configured"),
    ],
)
def test_discovery_rejects_invalid_locale_folders_with_teaching_error(
    authed_client, clean_i18n_site, relative_path, message
):
    from services.file_service import iter_canonical_files
    from services.i18n_service import ContentI18nError

    _activate(authed_client)
    default_dir = clean_i18n_site / "about"
    default_dir.mkdir(parents=True)
    (default_dir / "index.md").write_text(
        _document(name="About", language="en", body="English")
    )
    bad = clean_i18n_site / relative_path
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text(_document(name="About", language=bad.parent.name, body="Bad"))

    with pytest.raises(ContentI18nError) as exc:
        asyncio.run(iter_canonical_files("default"))
    assert relative_path in str(exc.value)
    assert message in str(exc.value)
    assert "Fix:" in str(exc.value) or "must stay" in str(exc.value)


def test_first_internal_sibling_write_assigns_group_to_both_markdown_files(
    authed_client, clean_i18n_site
):
    from services.cache_service import get_entry
    from services.file_service import read_page, write_page

    _activate(authed_client)
    source = Page(
        frontmatter=PageFrontmatter(
            name="Guide",
            category="summer",
            status="draft",
            published=False,
        ),
        content="English draft",
    )
    asyncio.run(write_page(source, page_id="guide", site_id="default"))

    target = Page(
        frontmatter=PageFrontmatter(
            name="Guide",
            category="summer",
            status="draft",
            published=False,
        ),
        content="Brouillon français",
    )
    result = asyncio.run(
        write_page(
            target,
            page_id="guide",
            site_id="default",
            language="fr",
        )
    )
    assert result.translation_group
    assert result.translation_group.startswith("tg_")

    source_post = frontmatter.load(clean_i18n_site / "guide" / "index.md")
    target_post = frontmatter.load(clean_i18n_site / "guide" / "fr" / "index.md")
    assert source_post["language"] == "en"
    assert target_post["language"] == "fr"
    assert source_post["translation_group"] == target_post["translation_group"]
    assert get_entry(
        "summer", "guide", site_id="default", language="en"
    )["translation_group"] == result.translation_group
    assert get_entry(
        "summer", "guide", site_id="default", language="fr"
    )["translation_group"] == result.translation_group

    exact = asyncio.run(
        read_page("guide", site_id="default", language="fr")
    )
    assert exact is not None
    assert exact.content.strip() == "Brouillon français"


def test_discovery_rejects_orphan_and_mismatched_group(
    authed_client, clean_i18n_site
):
    from services.file_service import iter_canonical_files
    from services.i18n_service import ContentI18nError

    _activate(authed_client)
    french = clean_i18n_site / "orphan" / "fr"
    french.mkdir(parents=True)
    (french / "index.md").write_text(
        _document(name="Orphan", language="fr", body="Orphelin")
    )
    with pytest.raises(ContentI18nError, match="no default-language peer"):
        asyncio.run(iter_canonical_files("default"))

    shutil.rmtree(clean_i18n_site / "orphan")
    default = clean_i18n_site / "mismatch"
    (default / "fr").mkdir(parents=True)
    (default / "index.md").write_text(
        _document(name="Mismatch", language="en", body="English")
    )
    (default / "fr" / "index.md").write_text(
        _document(
            name="Mismatch",
            language="fr",
            body="Français",
            group="tg_" + ("b" * 32),
        )
    )
    with pytest.raises(ContentI18nError, match="does not match default peer"):
        asyncio.run(iter_canonical_files("default"))


def test_published_composite_requires_every_locale_partial(
    authed_client, clean_i18n_site
):
    from services.file_service import iter_canonical_files
    from services.i18n_service import ContentI18nError

    _activate(authed_client)
    default = clean_i18n_site / "composite"
    french = default / "fr"
    french.mkdir(parents=True)
    (default / "index.md").write_text(
        _document(
            name="Composite",
            language="en",
            body="English",
            composite=True,
        )
    )
    (default / "_bio.md").write_text("English bio")
    (french / "index.md").write_text(
        _document(
            name="Composite",
            language="fr",
            body="Français",
            composite=True,
        )
    )

    with pytest.raises(ContentI18nError) as exc:
        asyncio.run(iter_canonical_files("default"))
    assert "published composite is missing locale-local partials" in str(exc.value)
    assert "composite/fr/_bio.md" in str(exc.value)
    assert "keep the sibling in draft" in str(exc.value)


def test_cache_and_fts_keep_language_and_site_identity(
    authed_client, clean_i18n_site
):
    from config import content_storage
    from services.cache_service import (
        delete_entry_from_cache,
        get_db_connection,
        get_entry,
        search_entries,
        sync_cache_with_storage,
    )
    from services.site_service import create_site

    _activate(authed_client)
    root = clean_i18n_site / "shared"
    (root / "fr").mkdir(parents=True)
    (root / "index.md").write_text(
        _document(name="Shared", language="en", body="English needle")
    )
    (root / "fr" / "index.md").write_text(
        _document(name="Shared", language="fr", body="Aiguille française")
    )
    create_site("other", "Other", language="en", languages=["en", "fr"])
    other_root = clean_i18n_site.parent / "other" / "shared"
    (other_root / "fr").mkdir(parents=True)
    (other_root / "index.md").write_text(
        _document(name="Shared", language="en", body="Other-site needle")
    )
    (other_root / "fr" / "index.md").write_text(
        _document(name="Shared", language="fr", body="Aiguille autre site")
    )

    asyncio.run(sync_cache_with_storage(content_storage))
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT site_id, slug, language, translation_group FROM entries "
            "WHERE site_id = 'default' AND slug = 'shared' ORDER BY language"
        ).fetchall()
    assert [(r["site_id"], r["slug"], r["language"]) for r in rows] == [
        ("default", "shared", "en"),
        ("default", "shared", "fr"),
    ]
    assert all(r["translation_group"] == GROUP for r in rows)
    assert get_entry("summer", "shared", site_id="default", language="en")["body"].strip() == "English needle"
    assert get_entry("summer", "shared", site_id="default", language="fr")["body"].strip() == "Aiguille française"
    assert search_entries("Aiguille", site_id="default", language="en") == []
    french = search_entries("Aiguille", site_id="default", language="fr")
    assert french[0]["language"] == "fr"
    assert french[0]["translation_group"] == GROUP
    assert all(result["site_id"] == "default" for result in french)
    assert search_entries("autre site", site_id="default", language="fr") == []

    delete_entry_from_cache(
        "summer", "shared", site_id="default", language="fr"
    )
    assert get_entry("summer", "shared", site_id="default", language="fr") is None
    assert get_entry("summer", "shared", site_id="default", language="en") is not None
    assert get_entry("summer", "shared", site_id="other", language="fr") is not None


def test_v1_exact_and_merged_reads_report_actual_language_and_fallback(
    authed_client, clean_i18n_site
):
    from config import content_storage
    from services.cache_service import sync_cache_with_storage

    _activate(authed_client)
    translated = clean_i18n_site / "translated"
    (translated / "fr").mkdir(parents=True)
    (translated / "index.md").write_text(
        _document(name="Translated", language="en", body="English")
    )
    (translated / "fr" / "index.md").write_text(
        _document(name="Translated", language="fr", body="Français")
    )
    default_only = clean_i18n_site / "default-only"
    default_only.mkdir()
    (default_only / "index.md").write_text(
        frontmatter.dumps(
            frontmatter.Post(
                "Only English",
                name="Default only",
                category="summer",
                status="published",
                published=True,
            )
        )
    )
    asyncio.run(sync_cache_with_storage(content_storage))

    exact = authed_client.get(
        "/api/v1/content/collections/summer/entries",
        params={"language": "fr", "fallback": "none"},
    )
    assert exact.status_code == 200, exact.text
    assert [item["slug"] for item in exact.json()["items"]] == ["translated"]
    assert exact.json()["items"][0]["is_fallback"] is False

    merged = authed_client.get(
        "/api/v1/content/collections/summer/entries",
        params={"language": "fr", "fallback": "default"},
    )
    assert merged.status_code == 200, merged.text
    by_slug = {item["slug"]: item for item in merged.json()["items"]}
    assert by_slug["translated"]["language"] == "fr"
    assert by_slug["translated"]["is_fallback"] is False
    assert by_slug["default-only"]["language"] == "en"
    assert by_slug["default-only"]["is_fallback"] is True

    detail = authed_client.get(
        "/api/v1/content/collections/summer/entries/translated",
        params={"language": "fr"},
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["language"] == "fr"
    assert detail.json()["body"].strip() == "Français"
    assert detail.json()["translations"][0]["language"] == "en"

    missing = authed_client.get(
        "/api/v1/content/collections/summer/entries/default-only",
        params={"language": "fr"},
    )
    assert missing.status_code == 404


def test_public_merged_list_retains_default_order_and_live_fallback_contract(
    authed_client, clean_i18n_site, monkeypatch
):
    from config import content_storage
    from services import cache_service
    from services.cache_service import sync_cache_with_storage
    from services.file_service import list_pages

    _activate(authed_client)
    timestamps = {
        "first": 1_700_000_300,
        "second": 1_700_000_200,
        "third": 1_700_000_100,
        "withheld": 1_700_000_400,
    }
    groups = {
        "first": "tg_" + ("1" * 32),
        "second": "tg_" + ("2" * 32),
        "third": "tg_" + ("3" * 32),
        "withheld": "tg_" + ("4" * 32),
    }
    for slug in ["first", "second", "third"]:
        root = clean_i18n_site / slug
        root.mkdir()
        (root / "index.md").write_text(
            _document(
                name=slug.title(),
                language="en",
                body=f"English {slug}",
                group=groups[slug],
            )
        )
        os.utime(root / "index.md", (timestamps[slug], timestamps[slug]))

    first_target = clean_i18n_site / "first" / "fr"
    first_target.mkdir()
    (first_target / "index.md").write_text(
        _document(
            name="Premier",
            language="fr",
            body="Français first",
            group=groups["first"],
        )
    )
    os.utime(first_target / "index.md", (1_700_000_900, 1_700_000_900))

    second_target = clean_i18n_site / "second" / "fr"
    second_target.mkdir()
    (second_target / "index.md").write_text(
        _document(
            name="Deuxième",
            language="fr",
            body="Brouillon",
            group=groups["second"],
            status="draft",
            published=False,
        )
    )

    withheld = clean_i18n_site / "withheld"
    (withheld / "fr").mkdir(parents=True)
    (withheld / "index.md").write_text(
        _document(
            name="Withheld",
            language="en",
            body="Draft default",
            group=groups["withheld"],
            status="draft",
            published=False,
        )
    )
    (withheld / "fr" / "index.md").write_text(
        _document(
            name="Masqué",
            language="fr",
            body="Published target",
            group=groups["withheld"],
        )
    )
    os.utime(withheld / "index.md", (timestamps["withheld"], timestamps["withheld"]))

    asyncio.run(sync_cache_with_storage(content_storage))

    response = authed_client.get(
        "/api/pages/",
        params={
            "language": "fr",
            "fallback": "default",
            "live_only": True,
        },
    )
    assert response.status_code == 200, response.text
    rows = response.json()
    assert [row["id"] for row in rows] == ["first", "second", "third"]
    assert [
        (row["language"], row["is_fallback"]) for row in rows
    ] == [
        ("fr", False),
        ("en", True),
        ("en", True),
    ]
    assert rows[0]["frontmatter"]["name"] == "Premier"
    assert rows[1]["frontmatter"]["name"] == "Second"

    def unavailable_cache():
        raise RuntimeError("forced cache miss")

    monkeypatch.setattr(cache_service, "get_db_connection", unavailable_cache)
    slow_rows = asyncio.run(
        list_pages(
            site_id="default",
            language="fr",
            fallback="default",
            live_only=True,
        )
    )
    slow_by_slug = {row.id: row for row in slow_rows}
    assert slow_by_slug["first"].language == "fr"
    assert slow_by_slug["first"].is_fallback is False
    assert slow_by_slug["second"].language == "en"
    assert slow_by_slug["second"].is_fallback is True


def test_translation_sibling_cannot_translate_taxonomy_assignments(
    authed_client, clean_i18n_site
):
    from services.file_service import ContentI18nError, iter_canonical_files

    _activate(authed_client)
    root = clean_i18n_site / "taxonomy-locked"
    (root / "fr").mkdir(parents=True)
    (root / "index.md").write_text(
        _document(
            name="Canonical",
            language="en",
            body="English",
            extra={"taxonomy_topics": "Science / Space"},
        )
    )
    (root / "fr" / "index.md").write_text(
        _document(
            name="Traduit",
            language="fr",
            body="Français",
            extra={"taxonomy_topics": "Sciences / Espace"},
        )
    )

    with pytest.raises(ContentI18nError) as exc:
        asyncio.run(iter_canonical_files("default"))
    assert "taxonomy assignments" in str(exc.value)
    assert "taxonomy-locked/fr/index.md" in str(exc.value)


def test_activation_rejects_language_shadowing_slug(
    authed_client, clean_i18n_site
):
    slug = clean_i18n_site / "fr"
    slug.mkdir()
    (slug / "index.md").write_text("---\nname: French\ncategory: summer\n---\nBody\n")
    response = authed_client.patch(
        "/api/sites/default",
        json={"language": "en", "languages": ["en", "fr"]},
    )
    assert response.status_code == 400
    assert "shadows a configured language code" in response.json()["detail"]
    assert "sites/default/fr/index.md" in response.json()["detail"]


def test_inactive_content_shape_stays_legacy_and_rejects_locale_request(
    authed_client, clean_i18n_site
):
    from config import content_storage
    from services.cache_service import sync_cache_with_storage

    page = clean_i18n_site / "legacy" / "index.md"
    page.parent.mkdir()
    page.write_text(
        "---\nname: Legacy\ncategory: summer\nstatus: published\npublished: true\n---\nBody\n"
    )
    asyncio.run(sync_cache_with_storage(content_storage))

    response = authed_client.get(
        "/api/v1/content/collections/summer/entries"
    )
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert "language" not in item
    assert "translations" not in item
    assert "is_fallback" not in item

    rejected = authed_client.get(
        "/api/v1/content/collections/summer/entries",
        params={"language": "fr"},
    )
    assert rejected.status_code == 400
    assert "i18n is inactive" in rejected.json()["detail"]


def test_public_localized_detail_requires_exact_valid_live_siblings(
    authed_client, clean_i18n_site
):
    _activate(authed_client)

    def write_pair(
        slug: str,
        *,
        default_status: str = "published",
        default_published: bool = True,
        default_publish_at: str | None = None,
        target_status: str = "published",
        target_published: bool = True,
        target_publish_at: str | None = None,
        target_group: str = GROUP,
        composite: bool = False,
        include_target_partial: bool = True,
    ) -> None:
        root = clean_i18n_site / slug
        target = root / "fr"
        target.mkdir(parents=True)
        (root / "index.md").write_text(
            _document(
                name=slug,
                language="en",
                body=f"English {slug}",
                status=default_status,
                published=default_published,
                publish_at=default_publish_at,
                composite=composite,
            )
        )
        (target / "index.md").write_text(
            _document(
                name=slug,
                language="fr",
                body=f"Français {slug}",
                group=target_group,
                status=target_status,
                published=target_published,
                publish_at=target_publish_at,
                composite=composite,
            )
        )
        if composite:
            (root / "_bio.md").write_text("English bio")
            if include_target_partial:
                (target / "_bio.md").write_text("Biographie exacte")

    write_pair("live")
    write_pair("target-draft", target_status="draft", target_published=False)
    write_pair("target-unpublished", target_status="unpublished", target_published=False)
    write_pair("target-future", target_publish_at="2999-01-01T00:00:00Z")
    write_pair("default-draft", default_status="draft", default_published=False)
    write_pair("default-future", default_publish_at="2999-01-01T00:00:00Z")
    write_pair("invalid-group", target_group="tg_" + ("b" * 32))
    write_pair("incomplete", composite=True, include_target_partial=False)
    missing = clean_i18n_site / "missing"
    missing.mkdir()
    (missing / "index.md").write_text(
        _document(name="missing", language="en", body="English only")
    )

    live = authed_client.get(
        "/api/pages/live",
        params={"language": "fr", "live_only": True, "include_partials": True},
    )
    assert live.status_code == 200, live.text
    assert live.json()["content"].strip() == "Français live"
    assert live.json()["language"] == "fr"

    for slug in [
        "target-draft",
        "target-unpublished",
        "target-future",
        "default-draft",
        "default-future",
        "invalid-group",
        "incomplete",
        "missing",
    ]:
        response = authed_client.get(
            f"/api/pages/{slug}",
            params={"language": "fr", "live_only": True, "include_partials": True},
        )
        assert response.status_code == 404, (slug, response.text)

    # The opt-in public filter does not alter existing default/query reads.
    legacy_detail = authed_client.get("/api/pages/default-draft")
    assert legacy_detail.status_code == 200, legacy_detail.text
    assert legacy_detail.json()["content"].strip() == "English default-draft"


def test_exact_live_language_list_withholds_nonpublic_peers_and_isolates_sites(
    authed_client, clean_i18n_site
):
    from config import content_storage
    from services.cache_service import sync_cache_with_storage
    from services.site_service import create_site

    _activate(authed_client)

    def write_pair(
        site_root: Path,
        slug: str,
        *,
        default_status: str = "published",
        default_published: bool = True,
        target_status: str = "published",
        target_published: bool = True,
        target_publish_at: str | None = None,
        body: str = "Français",
    ) -> None:
        group = "tg_" + slug.encode().hex()[:32].ljust(32, "0")
        root = site_root / slug
        target = root / "fr"
        target.mkdir(parents=True)
        (root / "index.md").write_text(
            _document(
                name=slug,
                language="en",
                body="English",
                status=default_status,
                published=default_published,
                group=group,
            )
        )
        (target / "index.md").write_text(
            _document(
                name=slug,
                language="fr",
                body=body,
                status=target_status,
                published=target_published,
                publish_at=target_publish_at,
                group=group,
            )
        )

    write_pair(clean_i18n_site, "public", body="Français public")
    write_pair(
        clean_i18n_site,
        "default-draft",
        default_status="draft",
        default_published=False,
    )
    write_pair(
        clean_i18n_site,
        "target-draft",
        target_status="draft",
        target_published=False,
    )
    write_pair(
        clean_i18n_site,
        "target-unpublished",
        target_status="unpublished",
        target_published=False,
    )
    write_pair(
        clean_i18n_site,
        "target-future",
        target_publish_at="2999-01-01T00:00:00Z",
    )

    create_site("other", "Other", language="en", languages=["en", "fr"])
    other_root = clean_i18n_site.parent / "other"
    write_pair(other_root, "public", body="Français autre site")
    asyncio.run(sync_cache_with_storage(content_storage))

    default_site = authed_client.get(
        "/api/pages/",
        params={
            "language": "fr",
            "fallback": "none",
            "live_only": True,
            "status": "published",
        },
    )
    assert default_site.status_code == 200, default_site.text
    assert [item["id"] for item in default_site.json()] == ["public"]
    assert default_site.json()[0]["content"].strip() == "Français public"

    default_merged = authed_client.get(
        "/api/pages/",
        params={"language": "fr", "fallback": "default", "live_only": True},
    )
    assert default_merged.status_code == 200, default_merged.text
    default_rows = {item["id"]: item for item in default_merged.json()}
    assert set(default_rows) == {
        "public",
        "target-draft",
        "target-unpublished",
        "target-future",
    }
    assert default_rows["public"]["is_fallback"] is False
    assert default_rows["public"]["language"] == "fr"
    for slug in ["target-draft", "target-unpublished", "target-future"]:
        assert default_rows[slug]["is_fallback"] is True
        assert default_rows[slug]["language"] == "en"

    other_site = authed_client.get(
        "/api/pages/",
        params={"language": "fr", "fallback": "none", "live_only": True},
        headers={"X-Pen-Site-Id": "other"},
    )
    assert other_site.status_code == 200, other_site.text
    assert [item["id"] for item in other_site.json()] == ["public"]
    assert other_site.json()[0]["content"].strip() == "Français autre site"

    other_merged = authed_client.get(
        "/api/pages/",
        params={"language": "fr", "fallback": "default", "live_only": True},
        headers={"X-Pen-Site-Id": "other"},
    )
    assert other_merged.status_code == 200, other_merged.text
    assert [item["id"] for item in other_merged.json()] == ["public"]
    assert other_merged.json()[0]["content"].strip() == "Français autre site"


def test_openapi_exposes_additive_read_contracts():
    spec_path = Path(__file__).resolve().parents[2] / "core" / "openapi.yaml"
    spec = yaml.safe_load(spec_path.read_text())
    list_parameters = spec["paths"]["/content/collections/{collection}/entries"]["get"]["parameters"]
    assert {"$ref": "#/components/parameters/ContentLanguage"} in list_parameters
    assert {"$ref": "#/components/parameters/ContentFallback"} in list_parameters
    detail = spec["components"]["schemas"]["EntryDetail"]["properties"]
    summary = spec["components"]["schemas"]["EntrySummary"]["properties"]
    assert {"language", "translation_group", "translations"} <= set(detail)
    assert {"language", "translation_group", "translations", "is_fallback"} <= set(summary)
