"""Unit tests for publish path→hash manifests (S9)."""

from __future__ import annotations

import json

import pytest


@pytest.fixture
def manifests_root(temp_data_root, monkeypatch):
    """Point BASE_DIR at temp so manifests land under temp data/."""
    import config

    monkeypatch.setattr(config, "BASE_DIR", temp_data_root)
    yield temp_data_root


def test_hash_dist_tree_and_diff(tmp_path):
    from services.publish_manifests import diff_manifests, hash_dist_tree

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("a", encoding="utf-8")
    sub = dist / "css"
    sub.mkdir()
    (sub / "app.css").write_text("body{}", encoding="utf-8")

    first = hash_dist_tree(dist)
    assert set(first) == {"index.html", "css/app.css"}
    assert len(first["index.html"]) == 64

    diff0 = diff_manifests(None, first)
    assert diff0["added"] == ["css/app.css", "index.html"]
    assert diff0["changed"] == []
    assert diff0["removed"] == []
    assert diff0["unchanged"] == []

    (dist / "index.html").write_text("b", encoding="utf-8")
    (dist / "gone.txt").write_text("x", encoding="utf-8")
    # Remove css file from tree by not including it in second hash simulation:
    # actually delete it
    (sub / "app.css").unlink()
    second = hash_dist_tree(dist)
    d = diff_manifests(first, second)
    assert d["added"] == ["gone.txt"]
    assert d["changed"] == ["index.html"]
    assert d["removed"] == ["css/app.css"]
    assert d["unchanged"] == []


def test_save_load_manifest(manifests_root):
    from services.publish_manifests import load_manifest, manifest_path, save_manifest

    files = {"index.html": "a" * 64, "css/x.css": "b" * 64}
    path = save_manifest("default", files)
    assert path == manifest_path("default")
    assert path.is_file()

    loaded = load_manifest("default")
    assert loaded == files

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["version"] == 1
    assert raw["updated_at"]
    assert raw["files"] == files


def test_load_missing_returns_none(manifests_root):
    from services.publish_manifests import clear_manifest, load_manifest

    clear_manifest("orphan-site")
    assert load_manifest("orphan-site") is None


def test_normalize_rejects_unsafe(manifests_root):
    from services.publish_manifests import save_manifest

    with pytest.raises(ValueError, match="unsafe|absolute"):
        save_manifest("default", {"../etc/passwd": "a" * 64})


def test_unchanged_second_diff(tmp_path):
    from services.publish_manifests import diff_manifests, hash_dist_tree

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "a.html").write_text("same", encoding="utf-8")
    h = hash_dist_tree(dist)
    d = diff_manifests(h, hash_dist_tree(dist))
    assert d["added"] == []
    assert d["changed"] == []
    assert d["removed"] == []
    assert d["unchanged"] == ["a.html"]
