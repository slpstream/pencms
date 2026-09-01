"""Unit tests for ReDoS-safe markdown/shortcode parsers in mcp_tools."""

from routers.mcp_tools import (
    _extract_image_shortcode_srcs,
    _has_empty_media_refs,
    _iter_image_shortcode_attrs,
    _markdown_heading,
    _parse_expand_embed_refs,
    match_heading,
)


def test_parse_expand_slug_and_bare_shortcode():
    refs = _parse_expand_embed_refs('[expand slug="x"] and [expand]')
    assert refs == [
        {"mode": "expand", "slug": "x", "heading": None},
        {"mode": "expand", "slug": "", "heading": None},
    ]


def test_parse_embed_heading_and_hash_in_slug():
    refs = _parse_expand_embed_refs(
        '[embed slug="post" heading="Intro"] [expand slug="other#Section"]'
    )
    assert refs[0] == {"mode": "embed", "slug": "post", "heading": "Intro"}
    assert refs[1] == {"mode": "expand", "slug": "other", "heading": "Section"}


def test_extract_quoted_image_srcs_skips_empty():
    body = (
        '[image src="images/content/a.png" alt="a"] '
        "[image src='images/content/b.png'] "
        '[image src="" align="center"]'
    )
    assert _extract_image_shortcode_srcs(body) == [
        "images/content/a.png",
        "images/content/b.png",
    ]


def test_has_empty_media_quoted_src():
    assert _has_empty_media_refs('[image src="" align="center"]')
    assert _has_empty_media_refs("[image src='  ']")
    assert not _has_empty_media_refs('[image src="images/content/ok.png"]')


def test_has_empty_media_unquoted_src_and_markdown():
    assert _has_empty_media_refs("[image src=]")
    assert _has_empty_media_refs("[image foo src= ]")
    assert _has_empty_media_refs("![]()")
    assert _has_empty_media_refs("![alt]( )")
    assert not _has_empty_media_refs("![alt](images/content/ok.png)")
    assert not _has_empty_media_refs("[image src=unquoted.png]")


def test_image_shortcode_case_unclosed_and_nested_close():
    assert _extract_image_shortcode_srcs('[IMAGE src="x.png"]') == ["x.png"]
    assert _iter_image_shortcode_attrs(
        '[image no close [image src="y.png"]'
    ) == [' no close [image src="y.png"']
    assert _extract_image_shortcode_srcs("[image never closed") == []
    assert not _has_empty_media_refs("[image never closed")


def test_expand_case_unclosed_and_nested_close():
    refs = _parse_expand_embed_refs('[EXPAND slug="X"] [EMBED slug="Y"]')
    assert refs == [
        {"mode": "expand", "slug": "X", "heading": None},
        {"mode": "embed", "slug": "Y", "heading": None},
    ]
    nested = _parse_expand_embed_refs('[expand no close [expand slug="z"]')
    assert nested == [{"mode": "expand", "slug": "z", "heading": None}]
    assert _parse_expand_embed_refs("[expand never closed") == []
    assert _parse_expand_embed_refs("[embed never closed") == []


def test_markdown_heading_and_match_heading():
    assert _markdown_heading("# Title") == (1, "Title")
    assert _markdown_heading("## Nested") == (2, "Nested")
    assert _markdown_heading("####### Too deep") is None
    assert _markdown_heading("#NoSpace") is None

    assert match_heading("# Title", "Title")
    assert match_heading("## Title", "# Title")
    assert match_heading("# Title", "# Title")
    assert match_heading("## Nested", "nested")
    assert not match_heading("# Title", "Other")
