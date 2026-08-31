"""Slice 3–5 and 9 static localized detail, list, and output coverage."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest


DOCS_QA_FAQS = [
    {"q": "What is this page?", "a": "A docs explainer with real questions and answers."},
    {"q": "Does empty FAQ emit schema?", "a": "No. Poetry stays silent."},
]


def _page(
    slug: str,
    language: str,
    *,
    composite: bool = False,
    is_fallback: bool = False,
    site_id: str = "default",
    is_page: bool = False,
    deck: str = "",
    noindex: bool = False,
    faqs: list | None = None,
) -> dict:
    translated = language != "en"
    if language == "fr":
        title = "Dossier français"
        body = 'Corps français.\n\n[image src="images/content/photo.jpg" alt="Photo"]'
    elif language == "de":
        title = "Dossier deutsch"
        body = "Deutscher Inhalt."
    elif slug == "default-only":
        title = "Default only"
        body = "Seulement anglais."
    elif slug == "about":
        title = "About"
        body = "About page body."
    elif slug == "docs-qa":
        title = "Docs Q&A"
        body = "A documentation page that answers questions."
    elif slug == "secret-notes":
        title = "Secret notes"
        body = "Unlisted page body."
    elif slug == "hidden-post":
        title = "Hidden post"
        body = "Unlisted post body."
    else:
        title = "Default dossier"
        body = 'English body.\n\n[image src="images/content/photo.jpg" alt="Photo"]'
    body += (
        '\n\n[link slug="translated"]Exact link[/link] '
        '[link slug="default-only"]Fallback link[/link]'
    )
    frontmatter = {
        "name": title,
        "hero_title": title,
        "category": "summer",
        "domain": "blog",
        "status": "published",
        "published": True,
        "language": language,
        "translation_group": "tg_" + ("a" * 32),
        "date": "2026-08-01",
        "composite": composite,
    }
    if is_page:
        frontmatter["page"] = True
    if noindex:
        frontmatter["noindex"] = True
    if deck:
        frontmatter["deck"] = deck
    if faqs:
        frontmatter["faqs"] = faqs
    if composite:
        frontmatter["posts"] = [{"id": "bio", "title": "Biographie"}]
    return {
        "id": slug,
        "frontmatter": frontmatter,
        "content": body,
        "file_path": (
            f"sites/{site_id}/{slug}/{language}/index.md"
            if translated
            else f"sites/{site_id}/{slug}/index.md"
        ),
        "composite": composite,
        "partials": (
            {"bio": "Partiel français exact." if translated else "English exact partial."}
            if composite
            else {}
        ),
        "language": language,
        "translation_group": "tg_" + ("a" * 32),
        "translations": _translation_peers(slug, language, site_id),
        "is_fallback": is_fallback,
    }


def _translation_peers(slug: str, language: str, site_id: str) -> list[dict]:
    if slug == "translated" and site_id == "default":
        peer = "fr" if language == "en" else "en"
        return [{"language": peer, "status": "published", "published": True}]
    if slug == "other-translated" and site_id == "other":
        peer = "de" if language == "en" else "en"
        return [{"language": peer, "status": "published", "published": True}]
    return []


COMMENT_VISIBLE_OLDER = "SLICE3_VISIBLE_OLDER_LEMON_FROSTING"
COMMENT_VISIBLE_NEWER = "SLICE3_VISIBLE_NEWER_CUPCAKE_NOTE"
COMMENT_PENDING = "SLICE3_PENDING_SHOULD_NOT_BAKE"
COMMENT_OTHER_SITE = "SLICE3_OTHER_SITE_MUST_NOT_LEAK"
COMMENT_SLUG_OLDER = "c-20260801t120000z-older"
COMMENT_SLUG_NEWER = "c-20260802t120000z-newer"
COMMENT_SLUG_PENDING = "c-20260820t153000z-pending"
COMMENT_SLUG_OTHER = "c-20260803t120000z-other"

_KNOWN_FAKE_SITES = frozenset({"default", "other", "mono", "geo"})


def _comment_fixture(
    *,
    slug: str,
    body: str,
    visibility: str,
    received_at: str,
    author_name: str = "Reader",
) -> dict:
    return {
        "slug": slug,
        "author_name": author_name,
        "author_kind": "public",
        "body": body,
        "in_reply_to": None,
        "received_at": received_at,
        "visibility": visibility,
    }


# Store newer-first so GET must sort oldest-first, not preserve insertion order.
_COMMENT_FIXTURES: dict[tuple[str, str], list[dict]] = {
    ("default", "translated"): [
        _comment_fixture(
            slug=COMMENT_SLUG_NEWER,
            body=COMMENT_VISIBLE_NEWER,
            visibility="visible",
            received_at="2026-08-02T12:00:00Z",
            author_name="Later Reader",
        ),
        _comment_fixture(
            slug=COMMENT_SLUG_PENDING,
            body=COMMENT_PENDING,
            visibility="pending",
            received_at="2026-08-01T18:00:00Z",
            author_name="Pending Reader",
        ),
        _comment_fixture(
            slug=COMMENT_SLUG_OLDER,
            body=COMMENT_VISIBLE_OLDER,
            visibility="visible",
            received_at="2026-08-01T12:00:00Z",
            author_name="Grandmother",
        ),
    ],
    ("other", "other-translated"): [
        _comment_fixture(
            slug=COMMENT_SLUG_OTHER,
            body=COMMENT_OTHER_SITE,
            visibility="visible",
            received_at="2026-08-03T12:00:00Z",
            author_name="Other Site Reader",
        ),
    ],
}


def _public_comment_payload(row: dict) -> dict:
    return {
        "slug": row["slug"],
        "author_name": row["author_name"],
        "author_kind": row["author_kind"],
        "body": row["body"],
        "in_reply_to": row["in_reply_to"],
        "received_at": row["received_at"],
    }


def _fake_comment_site_id(handler: BaseHTTPRequestHandler) -> str:
    header = handler.headers.get("X-Pen-Site-Id")
    if header is not None and str(header).strip():
        return str(header).strip()
    host = (handler.headers.get("Host") or "").split(":")[0].strip().lower()
    first = host.split(".")[0] if host else ""
    return first if first in _KNOWN_FAKE_SITES else "default"


def _assert_visible_thread(html: str) -> None:
    assert "pen-comments" in html
    assert "Grandmother" in html
    assert COMMENT_VISIBLE_OLDER in html
    assert COMMENT_VISIBLE_NEWER in html
    assert html.index(COMMENT_VISIBLE_OLDER) < html.index(COMMENT_VISIBLE_NEWER)
    assert COMMENT_PENDING not in html
    assert COMMENT_OTHER_SITE not in html
    assert COMMENT_SLUG_PENDING not in html


def _assert_no_comment_bodies(blob: str) -> None:
    assert COMMENT_VISIBLE_OLDER not in blob
    assert COMMENT_VISIBLE_NEWER not in blob
    assert COMMENT_PENDING not in blob
    assert COMMENT_OTHER_SITE not in blob


class _StaticApiHandler(BaseHTTPRequestHandler):
    calls: list[tuple[str, dict[str, list[str]]]] = []
    serve_translation = True

    def log_message(self, format: str, *args) -> None:
        return

    def _send(self, status: int, payload) -> None:
        raw = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        self.calls.append((parsed.path, parse_qs(parsed.query)))
        if parsed.path == "/api/storage/rebuild-cache":
            self._send(200, {"status": "ok"})
            return
        self._send(404, {"detail": "not found"})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        self.calls.append((parsed.path, query))
        if parsed.path == "/api/v1/comments":
            post_slug = (query.get("post_slug") or [""])[0].strip()
            if not post_slug:
                self._send(400, {"detail": "post_slug is required"})
                return
            site_id = _fake_comment_site_id(self)
            rows = [
                _public_comment_payload(row)
                for row in _COMMENT_FIXTURES.get((site_id, post_slug), [])
                if row["visibility"] == "visible"
            ]
            rows.sort(key=lambda row: (row["received_at"], row["slug"]))
            self._send(200, {"post_slug": post_slug, "comments": rows})
            return
        site_id = self.headers.get("X-Pen-Site-Id", "default")
        if parsed.path == "/api/pages/":
            language = query.get("language", [None])[0]
            if language is not None:
                if not self.serve_translation:
                    self._send(200, [])
                    return
                if site_id == "other" and language == "de":
                    rows = [
                        _page(
                            "other-translated",
                            "de",
                            site_id="other",
                        )
                    ]
                elif site_id == "default" and language == "fr":
                    rows = [_page("translated", "fr", composite=True)]
                else:
                    rows = []
                if query.get("fallback") == ["default"]:
                    if site_id == "default" and language == "fr":
                        rows.extend(
                            [
                                _page(
                                    "default-only",
                                    "en",
                                    is_fallback=True,
                                ),
                                _page(
                                    "draft-peer",
                                    "en",
                                    is_fallback=True,
                                ),
                            ]
                        )
                self._send(200, rows)
            else:
                if site_id == "other":
                    rows = [
                        _page(
                            "other-translated",
                            "en",
                            site_id="other",
                        )
                    ]
                elif site_id == "mono":
                    rows = [_page("mono-only", "en", site_id="mono")]
                else:
                    rows = [
                        _page("translated", "en", composite=True),
                        _page("default-only", "en"),
                        _page("draft-peer", "en"),
                        _page("about", "en", is_page=True, deck="About the site"),
                        _page(
                            "docs-qa",
                            "en",
                            is_page=True,
                            faqs=DOCS_QA_FAQS,
                        ),
                        _page("secret-notes", "en", is_page=True, noindex=True),
                        _page("hidden-post", "en", noindex=True),
                    ]
                self._send(200, rows)
            return
        detail_slugs = {
            "translated",
            "default-only",
            "draft-peer",
            "other-translated",
            "mono-only",
            "about",
            "docs-qa",
            "secret-notes",
            "hidden-post",
        }
        slug = parsed.path.removeprefix("/api/pages/")
        if slug in detail_slugs:
            language = query.get("language", ["en"])[0]
            if language != "en" and not (
                (site_id == "default" and slug == "translated" and language == "fr")
                or (
                    site_id == "other"
                    and slug == "other-translated"
                    and language == "de"
                )
            ):
                self._send(404, {"detail": "Page not found"})
                return
            self._send(
                200,
                _page(
                    slug,
                    language,
                    composite=slug == "translated",
                    site_id=site_id,
                    is_page=slug in {"about", "secret-notes", "docs-qa"},
                    deck="About the site" if slug == "about" else "",
                    noindex=slug in {"secret-notes", "hidden-post"},
                    faqs=DOCS_QA_FAQS if slug == "docs-qa" else None,
                ),
            )
            return
        self._send(404, {"detail": "not found"})


def test_static_build_emits_exact_details_and_merged_localized_surfaces(tmp_path: Path):
    repo = Path(__file__).resolve().parents[2]
    php = shutil.which("php")
    if php is None:
        pytest.skip("php CLI is not installed")
    if not (repo / "frontend-php" / "vendor" / "autoload.php").is_file():
        pytest.skip("frontend PHP dependencies are not installed")

    backend = tmp_path / "backend"
    content = tmp_path / "content"
    (backend / "data").mkdir(parents=True)
    image_dir = content / "sites" / "default" / "assets" / "images" / "content"
    image_dir.mkdir(parents=True)
    (image_dir / "photo.jpg").write_bytes(b"fixture-image")
    (content / "sites" / "other").mkdir(parents=True)
    (content / "sites" / "mono").mkdir(parents=True)

    themes = backend / "themes"
    fixture_theme = themes / "fixture"
    templates = fixture_theme / "templates"
    templates.mkdir(parents=True)
    international_partials = themes / "international" / "partials"
    international_partials.mkdir(parents=True)
    shutil.copy(
        repo
        / "frontend-php"
        / "src"
        / "blog"
        / "themes"
        / "international"
        / "partials"
        / "_comment-thread.html.twig",
        international_partials / "_comment-thread.html.twig",
    )
    (fixture_theme / "theme.json").write_text(
        json.dumps(
            {
                "type": "native",
                "name": "Fixture",
                "version": "1.0.0",
                "variables": {},
            }
        )
    )
    (fixture_theme / "strings.json").write_text(
        json.dumps({"layer": "theme", "themeOnly": "theme"})
    )
    strings_dir = content / "sites" / "default" / "strings"
    strings_dir.mkdir(parents=True)
    (strings_dir / "en.json").write_text(
        json.dumps({"layer": "default", "defaultOnly": "default"})
    )
    (strings_dir / "fr.json").write_text(
        json.dumps(
            {
                "layer": "target",
                "targetOnly": "target",
                "search": "Rechercher",
            }
        )
    )
    (content / "sites" / "default" / "menus.yaml").write_text(
        """
primary:
  - id: translated
    label: Translated
    labels: {fr: Article traduit}
    target: {type: content, content_slug: translated, content_type: post}
  - id: fallback
    label: Default only
    labels: {fr: Anglais par défaut}
    target: {type: content, content_slug: default-only, content_type: post}
  - id: taxonomy
    label: Summer
    labels: {fr: Menu été}
    target: {type: taxonomy, content_slug: primary/Summer}
  - id: search
    label: Search
    labels: {fr: Rechercher}
    target: {type: system, content_slug: search}
secondary: []
footer: []
""".lstrip()
    )
    (templates / "index.html.twig").write_text(
        "<html lang=\"en\"><head></head><body>HOME|"
        "{{ site.language|default('legacy') }}|"
        '{% for d in dossiers %}{{ d.title }}={{ contentUrl(d) }};{% endfor %}'
        '{% for item in menu("primary") %}MENU={{ item.label }}={{ item.url }};{% endfor %}'
        "|CANON={{ canonical_url|default('missing') }}"
        '</body></html>'
    )
    (templates / "post.html.twig").write_text(
        '<html lang="en"><head></head><body>'
        "{{ site.language|default('legacy') }}|"
        "{{ site.default_language|default('legacy') }}|{{ strings.layer }}|"
        "{{ strings.themeOnly }}|{{ strings.defaultOnly|default('missing-default') }}|"
        "{{ strings.targetOnly|default('missing') }}|{{ strings.relatedPosts }}|"
        "{% for post in posts %}{{ post.content_html|raw }}{% endfor %}"
        "|CANON={{ canonical_url|default('missing') }}"
        "{{ theme.partial('comment-thread') | raw }}"
        "</body></html>"
    )
    (templates / "page.html.twig").write_text(
        '<html lang="en"><head></head><body>'
        "{{ site.language|default('legacy') }}|"
        "{{ site.default_language|default('legacy') }}|{{ strings.layer }}|"
        "{{ strings.themeOnly }}|{{ strings.defaultOnly|default('missing-default') }}|"
        "{{ strings.targetOnly|default('missing') }}|{{ strings.relatedPosts }}|"
        "{{ page_content|raw }}|CANON={{ canonical_url|default('missing') }}"
        "</body></html>"
    )
    (templates / "archive.html.twig").write_text(
        '<html lang="en"><head></head><body>ARCHIVE|'
        "{{ site.language|default('legacy') }}|"
        '{{ hero_title }}|{% for d in dossiers %}{{ d.title }}={{ contentUrl(d) }};{% endfor %}'
        "|CANON={{ canonical_url|default('missing') }}"
        '</body></html>'
    )
    (templates / "search.html.twig").write_text(
        '<html lang="en"><head></head><body>SEARCH|'
        "{{ site.language|default('legacy') }}|"
        '{{ strings.search }}|{{ search_index_url }}'
        "|CANON={{ canonical_url|default('missing') }}</body></html>"
    )
    config = backend / "config.ini"
    config.write_text(
        "\n".join(
            [
                "[Paths]",
                "content_dir = ../content",
                "[Server]",
                "api_port = 1",
                "[theme]",
                "active = fixture",
                "directory = themes",
                "",
            ]
        )
    )
    (backend / "data" / "sites.yaml").write_text(
        """
sites:
  - id: default
    name: Default
    content_relpath: sites/default
    sitename: Fixture Site
    theme: fixture
    language: en
    languages: [en, fr]
    comments_enabled: true
    feedback_submission_key: bakekey0123456789abcdef01234567
  - id: other
    name: Other
    content_relpath: sites/other
    sitename: Other Fixture
    theme: fixture
    language: en
    languages: [en, de]
    comments_enabled: true
  - id: mono
    name: Mono
    content_relpath: sites/mono
    sitename: Mono Fixture
    theme: fixture
    language: en
    languages: []
  - id: geo
    name: Geo
    content_relpath: sites/geo
    sitename: Geo Fixture
    theme: fixture
    language: en
    languages: []
    indexnow_enabled: true
    indexnow_key: testkey01testkey01testkey01testk
    content_signal_ai_train: true
    seo_redirects:
      - from: /old-slug/
        to: /translated/
""".lstrip()
    )

    _StaticApiHandler.calls = []
    _StaticApiHandler.serve_translation = True
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StaticApiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    output = tmp_path / "dist"
    env = os.environ.copy()
    env["PENCMS_CONFIG_PATH"] = str(config)
    env["PENCMS_INTERNAL_API_URL"] = (
        f"http://127.0.0.1:{server.server_port}/api"
    )
    try:
        result = subprocess.run(
            [
                php,
                str(repo / "frontend-php" / "cli-tools" / "generate-static.php"),
                "--site=default",
                "--domain=example.test",
                f"--output={output}",
            ],
            cwd=repo,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        _StaticApiHandler.serve_translation = False
        empty_output = tmp_path / "dist-empty-locale"
        empty_result = subprocess.run(
            [
                php,
                str(repo / "frontend-php" / "cli-tools" / "generate-static.php"),
                "--site=default",
                "--domain=example.test",
                f"--output={empty_output}",
            ],
            cwd=repo,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        _StaticApiHandler.serve_translation = True
        multisite_output = tmp_path / "dist-multisite"
        last_multisite = None
        for site_id in ("default", "other", "mono", "geo"):
            last_multisite = subprocess.run(
                [
                    php,
                    str(repo / "frontend-php" / "cli-tools" / "generate-static.php"),
                    f"--site={site_id}",
                    "--domain=example.test",
                    f"--output={multisite_output / site_id}",
                ],
                cwd=repo,
                env=env,
                text=True,
                capture_output=True,
                timeout=60,
                check=False,
            )
            if last_multisite.returncode != 0:
                break
        # Combined stdout/stderr of the last (or first failing) per-site bake.
        multisite_result = last_multisite
        (strings_dir / "fr.json").write_text('{"broken":')
        malformed_output = tmp_path / "dist-malformed"
        malformed_result = subprocess.run(
            [
                php,
                str(repo / "frontend-php" / "cli-tools" / "generate-static.php"),
                "--site=default",
                "--domain=example.test",
                f"--output={malformed_output}",
            ],
            cwd=repo,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert empty_result.returncode == 0, empty_result.stdout + "\n" + empty_result.stderr
    assert not (empty_output / "fr").exists()
    assert (output / "translated" / "index.html").is_file()
    assert (output / "default-only" / "index.html").is_file()
    assert (output / "fr" / "translated" / "index.html").is_file()
    assert (output / "fr" / "translated" / "index.md").is_file()
    assert not (output / "fr" / "default-only").exists()
    for slug in ("translated", "about", "docs-qa", "default-only", "hidden-post", "secret-notes"):
        alias = output / f"{slug}.md"
        canonical = output / slug / "index.md"
        assert alias.is_file()
        assert alias.read_bytes() == canonical.read_bytes()
        assert (output / slug / "index.html").is_file()
    assert (output / "fr" / "translated.md").read_bytes() == (
        output / "fr" / "translated" / "index.md"
    ).read_bytes()
    assert not (output / "fr" / "default-only.md").exists()
    assert not (output / "llm.txt").exists()
    assert (output / "fr" / "index.html").is_file()
    assert (output / "fr" / "search" / "index.html").is_file()
    assert (output / "fr" / "search-index.json").is_file()
    assert (output / "fr" / "category" / "index.html").is_file()
    assert (output / "fr" / "category" / "summer" / "index.html").is_file()

    localized_html = (output / "fr" / "translated" / "index.html").read_text()
    localized_markdown = (output / "fr" / "translated" / "index.md").read_text()
    localized_home = (output / "fr" / "index.html").read_text()
    localized_archive = (
        output / "fr" / "category" / "summer" / "index.html"
    ).read_text()
    localized_archive_root = (
        output / "fr" / "category" / "index.html"
    ).read_text()
    localized_search = (output / "fr" / "search" / "index.html").read_text()
    localized_search_docs = json.loads(
        (output / "fr" / "search-index.json").read_text()
    )
    default_search_docs = json.loads((output / "search-index.json").read_text())
    default_html = (output / "translated" / "index.html").read_text()
    home_html = (output / "index.html").read_text()
    about_html = (output / "about" / "index.html").read_text()
    default_only_html = (output / "default-only" / "index.html").read_text()
    docs_qa_html = (output / "docs-qa" / "index.html").read_text()
    assert '"@type":"WebSite"' in home_html
    assert '"@type":"Organization"' in home_html
    assert '"inLanguage":"en"' in home_html
    assert (
        '"urlTemplate":"https://example.test/search/?q={search_term_string}"'
        in home_html
    )
    assert '"@type":"SearchAction"' in home_html
    assert 'rel="alternate" type="text/plain"' in home_html
    assert "llms.txt" in home_html
    assert '"@type":"BlogPosting"' in default_html
    assert '"@type":"BreadcrumbList"' in default_html
    assert '"dateModified":"2026-08-01T00:00:00Z"' in default_html
    assert '"inLanguage":"en"' in default_html
    assert '"@type":"SearchAction"' not in default_html
    assert '"@type":"WebPage"' in about_html
    assert '"inLanguage":"en"' in about_html
    assert '"@type":"BlogPosting"' not in about_html
    assert '"@type":"FAQPage"' not in home_html
    assert '"@type":"FAQPage"' not in default_html
    assert '"@type":"FAQPage"' not in about_html
    assert '"@type":"FAQPage"' not in default_only_html
    assert '"@type":"FAQPage"' not in localized_html
    assert '"@type":"FAQPage"' in docs_qa_html
    assert '"@type":"Question"' in docs_qa_html
    assert "What is this page?" in docs_qa_html
    assert "A docs explainer with real questions and answers." in docs_qa_html
    assert "Does empty FAQ emit schema?" in docs_qa_html
    assert "No. Poetry stays silent." in docs_qa_html
    assert 'class="pen-qa"' in docs_qa_html
    assert '<h2 class="pen-qa-heading">FAQ</h2>' in docs_qa_html
    assert "<dt>What is this page?</dt>" in docs_qa_html
    assert "<dd>A docs explainer with real questions and answers.</dd>" in docs_qa_html
    assert "<dt>Does empty FAQ emit schema?</dt>" in docs_qa_html
    assert "<dd>No. Poetry stays silent.</dd>" in docs_qa_html
    assert 'class="pen-qa"' not in default_html
    assert 'class="pen-qa"' not in about_html
    assert "pen-qa-heading" not in default_html
    assert "pen-qa-heading" not in about_html
    assert '"@type":"WebSite"' not in localized_search
    assert '<html lang="fr">' in localized_html
    assert '"inLanguage":"fr"' in localized_html
    assert '"@type":"SearchAction"' not in localized_html
    assert "fr|en|target|theme|default|target|Related Posts|" in localized_html
    assert "CANON=https://example.test/fr/translated/" in localized_html
    assert (
        '<link rel="canonical" href="https://example.test/fr/translated/">'
        in localized_html
    )
    assert '<html lang="en">' in default_html
    assert "en|en|default|theme|default|missing|Related Posts|" in default_html
    assert "CANON=https://example.test/translated/" in default_html
    assert (
        '<link rel="canonical" href="https://example.test/translated/">'
        in default_html
    )
    _assert_visible_thread(default_html)
    _assert_visible_thread(localized_html)
    _assert_no_comment_bodies((output / "default-only" / "index.html").read_text())
    _assert_no_comment_bodies(home_html)
    _assert_no_comment_bodies(localized_home)
    assert 'hreflang="x-default" href="../translated/index.html"' in default_html
    assert 'hreflang="x-default" href="../../translated/index.html"' in localized_html
    assert 'property="og:locale" content="en_US"' in default_html
    assert 'property="og:locale:alternate" content="fr_FR"' in default_html
    assert 'property="og:locale" content="fr_FR"' in localized_html
    assert 'property="og:locale:alternate" content="en_US"' in localized_html
    assert 'property="article:published_time" content="2026-08-01T00:00:00Z"' in default_html
    assert 'property="article:modified_time" content="2026-08-01T00:00:00Z"' in default_html
    assert "article:published_time" not in about_html
    assert "article:published_time" not in home_html
    assert "orps français." in localized_html
    assert "artiel français exact." in localized_html
    assert 'href="../../fr/translated/index.html"' in localized_html
    assert 'href="../../default-only/index.html"' in localized_html
    assert "Corps français." in localized_markdown
    assert "Partiel français exact." in localized_markdown
    assert "../../images/content/photo.jpg" in localized_html
    assert "../images/content/photo.jpg" in (
        output / "translated" / "index.html"
    ).read_text()
    assert (output / "images" / "content" / "photo.jpg").is_file()
    assert '<html lang="fr">' in localized_home
    assert '"inLanguage":"fr"' in localized_home
    assert (
        '"urlTemplate":"https://example.test/fr/search/?q={search_term_string}"'
        in localized_home
    )
    assert "CANON=https://example.test/fr/" in localized_home
    assert "Dossier français=../fr/translated/index.html" in localized_home
    assert "Default only=../default-only/index.html" in localized_home
    assert "MENU=Article traduit=../fr/translated/index.html" in localized_home
    assert "MENU=Anglais par défaut=../default-only/index.html" in localized_home
    assert "MENU=Summer=../fr/category/summer/index.html" in localized_home
    assert "MENU=Rechercher=../fr/search/index.html" in localized_home
    assert "ARCHIVE|fr|summer" in localized_archive
    assert "CANON=https://example.test/fr/category/summer/" in localized_archive
    assert "CANON=https://example.test/fr/category/" in localized_archive_root
    assert "Dossier français=../../../fr/translated/index.html" in localized_archive
    assert "Default only=../../../default-only/index.html" in localized_archive
    assert "SEARCH|fr|Rechercher|../search-index.json" in localized_search
    assert "CANON=https://example.test/fr/search/" in localized_search
    assert [
        (doc["id"], doc["lang"], doc["url"]) for doc in localized_search_docs
    ] == [
        ("translated", "fr", "../../fr/translated/index.html"),
        ("default-only", "en", "../../default-only/index.html"),
        ("draft-peer", "en", "../../draft-peer/index.html"),
    ]
    assert {doc["lang"] for doc in default_search_docs} == {"en"}
    default_search_ids = {doc["id"] for doc in default_search_docs}
    assert "hidden-post" not in default_search_ids
    assert "secret-notes" not in default_search_ids
    assert "about" in default_search_ids
    assert "translated" in default_search_ids

    sitemap = (output / "sitemap.xml").read_text()
    assert "https://example.test/translated/" in sitemap
    assert "https://example.test/about/" in sitemap
    assert "https://example.test/hidden-post/" not in sitemap
    assert "https://example.test/secret-notes/" not in sitemap
    assert "https://example.test/fr/translated/" in sitemap
    assert "https://example.test/fr/default-only/" not in sitemap
    assert "https://example.test/fr/draft-peer/" not in sitemap
    assert 'xmlns:xhtml="http://www.w3.org/1999/xhtml"' in sitemap
    assert (
        '<xhtml:link rel="alternate" hreflang="en" '
        'href="https://example.test/translated/"/>'
    ) in sitemap
    assert (
        '<xhtml:link rel="alternate" hreflang="fr" '
        'href="https://example.test/fr/translated/"/>'
    ) in sitemap
    assert (
        '<xhtml:link rel="alternate" hreflang="x-default" '
        'href="https://example.test/translated/"/>'
    ) in sitemap
    assert (
        '<xhtml:link rel="alternate" hreflang="en" '
        'href="https://example.test/about/"/>'
    ) not in sitemap
    assert not (output / "fr" / "feed.xml").exists()
    assert not (output / "fr" / "llms.txt").exists()
    assert not (output / "fr" / "llms-full.txt").exists()
    root_feed = (output / "feed.xml").read_text()
    root_llms = (output / "llms.txt").read_text()
    root_full = (output / "llms-full.txt").read_text()
    assert "https://example.test/translated/" in root_feed
    assert "hidden-post" not in root_feed
    assert "secret-notes" not in root_feed
    assert "Hidden post" not in root_feed
    assert "https://example.test/about/index.md" in root_llms
    assert "https://example.test/translated/index.md" in root_llms
    assert "secret-notes" not in root_llms
    assert "hidden-post" not in root_llms
    assert "Secret notes" not in root_llms
    assert "Hidden post" not in root_llms
    assert "/fr/" not in root_feed
    assert "Dossier français" not in root_feed
    assert "## Pages" in root_llms
    assert "## Posts" in root_llms
    assert "https://example.test/about/index.md" in root_llms
    assert "https://example.test/translated/index.md" in root_llms
    assert "About the site" in root_llms
    assert "llms-full.txt" in root_llms
    assert "content.jsonl" in root_llms
    assert "feed.xml" in root_llms
    assert "sitemap.xml" in root_llms
    assert "./fr/" not in root_llms
    assert "Dossier français" not in root_llms
    assert "URL: https://example.test/about/" in root_full
    assert "URL: https://example.test/translated/" in root_full
    assert "About page body." in root_full
    assert "English body." in root_full
    assert "Unlisted post body." not in root_full
    assert "Unlisted page body." not in root_full
    assert "secret-notes" not in root_full
    assert "hidden-post" not in root_full
    jsonl = (output / "content.jsonl").read_text()
    assert "about" in jsonl
    assert "About page body." in jsonl
    assert "secret-notes" not in jsonl
    assert "hidden-post" not in jsonl
    assert "Unlisted post body." not in jsonl
    default_markdown = (output / "translated" / "index.md").read_text()
    _assert_no_comment_bodies(default_markdown)
    _assert_no_comment_bodies(localized_markdown)
    _assert_no_comment_bodies(root_full)
    _assert_no_comment_bodies(root_llms)
    _assert_no_comment_bodies(root_feed)
    _assert_no_comment_bodies(sitemap)
    _assert_no_comment_bodies(jsonl)
    _assert_no_comment_bodies(json.dumps(default_search_docs))
    _assert_no_comment_bodies(json.dumps(localized_search_docs))
    for slug in (
        COMMENT_SLUG_OLDER,
        COMMENT_SLUG_NEWER,
        COMMENT_SLUG_PENDING,
        COMMENT_SLUG_OTHER,
    ):
        assert f"/{slug}/" not in sitemap
        assert slug not in root_feed
        assert slug not in root_llms
        assert slug not in home_html
        assert slug not in localized_home
    hidden_html = (output / "hidden-post" / "index.html").read_text()
    secret_html = (output / "secret-notes" / "index.html").read_text()
    search_html = (output / "search" / "index.html").read_text()
    assert 'name="robots" content="noindex,nofollow"' in hidden_html
    assert 'name="robots" content="noindex,nofollow"' in secret_html
    assert 'name="robots" content="noindex,nofollow"' in search_html
    assert 'name="robots" content="noindex,nofollow"' in localized_search
    assert 'name="robots" content="index,follow,max-image-preview:large"' in about_html
    assert "Dossier français" not in root_full
    assert "Corps français." not in root_full
    htaccess = (output / ".htaccess").read_text()
    caddy = (output / "Caddyfile").read_text()
    nginx = (output / "nginx.conf.example").read_text()
    assert "X-Robots-Tag" in htaccess and "noindex" in htaccess
    assert "X-Robots-Tag" in caddy and "noindex" in caddy
    assert "X-Robots-Tag" in nginx and "noindex" in nginx
    assert "ai-train=yes" not in htaccess
    assert "ai-train=no" in htaccess
    assert "ai-train=yes" not in caddy
    assert "ai-train=no" in caddy
    assert "ai-train=yes" not in nginx
    assert "ai-train=no" in nginx
    assert 'header @html Vary "Accept"' in caddy
    assert "add_header Vary" in nginx and ".html" in nginx

    assert multisite_result.returncode == 0, (
        multisite_result.stdout + "\n" + multisite_result.stderr
    )
    default_map = (multisite_output / "default" / "sitemap.xml").read_text()
    other_map = (multisite_output / "other" / "sitemap.xml").read_text()
    mono_map = (multisite_output / "mono" / "sitemap.xml").read_text()
    assert "/fr/translated/" in default_map
    assert "/de/other-translated/" not in default_map
    assert "/de/other-translated/" in other_map
    assert "/fr/translated/" not in other_map
    assert "/fr/" not in mono_map and "/de/" not in mono_map
    other_feed = (multisite_output / "other" / "feed.xml").read_text()
    other_llms = (multisite_output / "other" / "llms.txt").read_text()
    other_full = (multisite_output / "other" / "llms-full.txt").read_text()
    assert "https://example.test/other-translated/" in other_feed
    assert "/de/" not in other_feed and "Dossier deutsch" not in other_feed
    assert "https://example.test/other-translated/index.md" in other_llms
    assert "llms-full.txt" in other_llms
    assert "./de/" not in other_llms and "Dossier deutsch" not in other_llms
    assert "URL: https://example.test/other-translated/" in other_full
    assert "Dossier deutsch" not in other_full
    assert not (multisite_output / "other" / "de" / "feed.xml").exists()
    assert not (multisite_output / "other" / "de" / "llms.txt").exists()
    assert not (multisite_output / "other" / "de" / "llms-full.txt").exists()
    other_alias = multisite_output / "other" / "other-translated.md"
    assert other_alias.read_bytes() == (
        multisite_output / "other" / "other-translated" / "index.md"
    ).read_bytes()

    geo_dir = multisite_output / "geo"
    geo_key = "testkey01testkey01testkey01testk"
    assert (geo_dir / f"{geo_key}.txt").read_text() == geo_key + "\n"
    assert not (output / f"{geo_key}.txt").exists()
    geo_ht = (geo_dir / ".htaccess").read_text()
    geo_caddy = (geo_dir / "Caddyfile").read_text()
    geo_nginx = (geo_dir / "nginx.conf.example").read_text()
    assert "ai-train=yes" in geo_ht
    assert "ai-train=yes" in geo_caddy
    assert "ai-train=yes" in geo_nginx
    assert "RewriteRule ^old-slug/?$ /translated/ [R=301,L]" in geo_ht
    assert (geo_dir / "_redirects").read_text() == "/old-slug/  /translated/  301\n"
    assert not (output / "_redirects").exists()


    mono_search_docs = json.loads(
        (multisite_output / "mono" / "search-index.json").read_text()
    )
    assert mono_search_docs
    assert all("lang" not in doc for doc in mono_search_docs)
    assert not (multisite_output / "mono" / "fr").exists()
    assert not (multisite_output / "mono" / "de").exists()

    localized_lists = [
        query
        for path, query in _StaticApiHandler.calls
        if path == "/api/pages/" and query.get("language") == ["fr"]
    ]
    assert localized_lists
    assert any(query.get("fallback") == ["none"] for query in localized_lists)
    assert any(query.get("fallback") == ["default"] for query in localized_lists)
    assert all(query.get("live_only") == ["true"] for query in localized_lists)
    localized_details = [
        query
        for path, query in _StaticApiHandler.calls
        if path == "/api/pages/translated" and query.get("language") == ["fr"]
    ]
    assert localized_details
    assert all(query.get("live_only") == ["1"] for query in localized_details)
    assert all(query.get("include_partials") == ["1"] for query in localized_details)
    comment_calls = [
        query
        for path, query in _StaticApiHandler.calls
        if path == "/api/v1/comments"
    ]
    assert comment_calls
    assert any(
        query.get("post_slug") == ["translated"] for query in comment_calls
    )

    assert malformed_result.returncode != 0
    malformed_log = malformed_result.stdout + "\n" + malformed_result.stderr
    assert "strings/fr.json" in malformed_log
    assert "Fix: provide a flat JSON object" in malformed_log
