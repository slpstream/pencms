"""Unit tests for ReDoS-safe markdown/MDX/wikilink parsers in mcp_tools."""

from routers.mcp_tools import (
    _extract_image_shortcode_srcs,
    _extract_mdx_image_srcs,
    _has_empty_media_refs,
    _iter_image_shortcode_attrs,
    _iter_mdx_image_attrs,
    _markdown_heading,
    _parse_expand_embed_refs,
    match_heading,
)


def test_parse_expand_slug_and_label():
    refs = _parse_expand_embed_refs('[[>x|Read more]] and [[>y]]')
    assert refs == [
        {"mode": "expand", "slug": "x", "heading": None, "source": None},
        {"mode": "expand", "slug": "y", "heading": None, "source": None},
    ]


def test_parse_embed_heading_and_source():
    refs = _parse_expand_embed_refs(
        '[[!post#Intro|T]] [[>other^summary|L]] [[slug|Label]]'
    )
    assert refs[0] == {"mode": "embed", "slug": "post", "heading": "Intro", "source": None}
    assert refs[1] == {"mode": "expand", "slug": "other", "heading": None, "source": "summary"}
    assert refs[2] == {"mode": "link", "slug": "slug", "heading": None, "source": None}


def test_parse_wikilink_unclosed_and_single_line():
    assert _parse_expand_embed_refs("[[>never closed") == []
    assert _parse_expand_embed_refs("[[>no close\n[[>z]]") == [
        {"mode": "expand", "slug": "z", "heading": None, "source": None}
    ]
    # Legacy single-bracket shortcodes are plain text, not wikilinks.
    assert _parse_expand_embed_refs('[expand slug="x"]') == []


def test_extract_quoted_image_srcs_skips_empty():
    body = (
        '<Image src="images/content/a.png" alt="a" /> '
        "<Image src='images/content/b.png'> "
        '<Image src="" align="center" />'
    )
    assert _extract_mdx_image_srcs(body) == [
        "images/content/a.png",
        "images/content/b.png",
    ]
    # Deprecated aliases keep working.
    assert _extract_image_shortcode_srcs(body) == [
        "images/content/a.png",
        "images/content/b.png",
    ]


def test_has_empty_media_quoted_src():
    assert _has_empty_media_refs('<Image src="" align="center" />')
    assert _has_empty_media_refs("<Image src='  '> ")
    assert not _has_empty_media_refs('<Image src="images/content/ok.png" />')


def test_has_empty_media_unquoted_src_and_markdown():
    assert _has_empty_media_refs("<Image src=/>")
    assert _has_empty_media_refs("<Image foo src= >")
    assert _has_empty_media_refs("![]()")
    assert _has_empty_media_refs("![alt]( )")
    assert not _has_empty_media_refs("![alt](images/content/ok.png)")
    assert not _has_empty_media_refs("<Image src=unquoted.png>")


def test_image_tag_case_unclosed_and_nested_close():
    assert _extract_mdx_image_srcs('<IMAGE src="x.png">') == ["x.png"]
    assert _iter_mdx_image_attrs(
        '<Image no close <Image src="y.png">'
    ) == [' no close <Image src="y.png"']
    assert _iter_image_shortcode_attrs('<Image src="y.png">') == [' src="y.png"']
    assert _extract_mdx_image_srcs("<Image never closed") == []
    assert not _has_empty_media_refs("<Image never closed")


def test_markdown_heading_and_match_heading():
    assert _markdown_heading("# Title") == (1, "Title")
    assert _markdown_heading("## Nested") == (2, "Nested")
    assert _markdown_heading("####### Too deep") is None
