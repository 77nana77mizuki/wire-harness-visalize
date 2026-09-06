"""ingest.py — マニフェスト生成の決定論。"""

import json

import pytest

from datapattern.ingest import build_manifest, write_manifest

SAMPLE = "sample_addon"


def test_manifest_lists_java_files(fixtures_dir):
    m = build_manifest(fixtures_dir / SAMPLE)
    paths = [f.path for f in m.files]
    assert paths == sorted(paths)
    assert "src/com/example/GroundCircuitDrc.java" in paths
    assert "src/com/example/SpliceLabelAction.java" in paths
    assert all(p.endswith(".java") for p in paths)


def test_digest_is_stable(fixtures_dir):
    a = build_manifest(fixtures_dir / SAMPLE)
    b = build_manifest(fixtures_dir / SAMPLE)
    assert a.digest == b.digest
    assert a.digest.startswith("sha256:")


def test_line_counts(fixtures_dir):
    m = build_manifest(fixtures_dir / SAMPLE)
    by_path = {f.path: f for f in m.files}
    assert by_path["src/com/example/SpliceLabelAction.java"].lines > 5


def test_write_manifest(tmp_path, fixtures_dir):
    m = build_manifest(fixtures_dir / SAMPLE)
    out = write_manifest(m, tmp_path / "workspace" / "manifest.json")
    data = json.loads(out.read_text("utf-8"))
    assert data["digest"] == m.digest
    assert len(data["files"]) == len(m.files)


def test_missing_dir(tmp_path):
    with pytest.raises(NotADirectoryError):
        build_manifest(tmp_path / "nope")
