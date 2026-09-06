"""``report.py`` — 組立とゴールデン比較。

ゴールデン更新: ``UPDATE_GOLDEN=1 uv run pytest tests/test_report.py``
"""

import os
from pathlib import Path

import pytest

from datapattern.model import load_model
from datapattern.render.html_renderer import HtmlRenderer
from datapattern.render.pipeline import render_patterns
from datapattern.report import render_report_html, write_report

GOLDEN = Path(__file__).parent / "fixtures" / "expected" / "report_full.html"


def _build(tmp_path, fixtures_dir) -> str:
    model = load_model(fixtures_dir / "valid_full.json")
    manifest = render_patterns(model, HtmlRenderer(), tmp_path)
    return render_report_html(model, manifest)


def test_report_structure(tmp_path, fixtures_dir):
    html = _build(tmp_path, fixtures_dir)
    assert html.startswith("<!DOCTYPE html>")
    assert html.endswith("\n")
    assert "<h1>GroundCircuitDrc</h1>" in html
    assert "プラグイン種別: <strong>check</strong>" in html
    assert "Capital 2207" in html
    # 一覧テーブルの見出しと各行
    assert "<h2>パターン一覧</h2>" in html
    for pid in ("circuit-switched-ground", "opt-cfg-all-false", "prop-wire-csa-lower-bound"):
        assert f'id="{pid}"' in html  # 詳細 section
        assert f'href="#{pid}"' in html  # 一覧からのリンク
    # 詳細テーブルの行見出し（表形式）
    assert "<th>なぜ必要か</th>" in html
    assert "<th>option 式</th>" in html
    assert "<code>OPT_GND</code>" in html
    assert "OPT_GND=0 で DRC を実行" in html  # testHints
    assert "GroundCircuitDrc.java#L44-L52" in html  # per-pattern sourceRefs
    # 図タブ
    assert 'class="figtabs"' in html
    assert '<button class="tab active"' in html
    # フッターに生成器、タイムスタンプは無い
    assert "capital-addon-analysis@0.1.0" in html
    assert "202" not in html.split("<footer>")[1]


def test_report_is_deterministic(tmp_path, fixtures_dir):
    a = _build(tmp_path / "a", fixtures_dir)
    b = _build(tmp_path / "b", fixtures_dir)
    assert a == b


def test_write_report_file(tmp_path, fixtures_dir):
    model = load_model(fixtures_dir / "valid_full.json")
    manifest = render_patterns(model, HtmlRenderer(), tmp_path / "renders")
    out = write_report(model, manifest, tmp_path / "report.html")
    assert out.read_text("utf-8").startswith("<!DOCTYPE html>")


def test_pattern_not_rendered_by_method(tmp_path, fixtures_dir):
    """レンダラが対応しないパターンはプレースホルダになり、フッターに列挙される。"""

    class OnlyCircuit(HtmlRenderer):
        name = "onlycircuit"
        supported_types = frozenset({"circuit"})

    model = load_model(fixtures_dir / "valid_full.json")
    manifest = render_patterns(model, OnlyCircuit(), tmp_path)
    html = render_report_html(model, manifest)
    assert "利用可能なレンダラで描画できませんでした" in html
    assert "opt-cfg-all-false" in html.split("<footer>")[1]


def test_golden(tmp_path, fixtures_dir):
    html = _build(tmp_path, fixtures_dir)
    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(html, encoding="utf-8")
        pytest.skip("golden updated")
    assert GOLDEN.is_file(), "ゴールデン未生成。UPDATE_GOLDEN=1 で作成してください"
    assert html == GOLDEN.read_text("utf-8")
