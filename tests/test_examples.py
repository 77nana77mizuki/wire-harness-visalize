"""examples/ の検証用データセットが最後まで通ることの確認。"""

from pathlib import Path

from datapattern.model import load_model
from datapattern.orchestrate import build_report

EXAMPLE = Path(__file__).parents[1] / "examples" / "capital-drawing-patterns.json"


def test_dataset_is_valid():
    model = load_model(EXAMPLE)
    assert len(model.patterns) == 16
    kinds = {p.type for p in model.patterns}
    assert kinds == {"circuit", "option_config", "property_set"}


def test_report_covers_every_pattern(tmp_path):
    model, manifest, report = build_report(EXAMPLE, "html", tmp_path)
    assert manifest.skipped == ()
    assert len(manifest.assets) == len(model.patterns)
    html = report.read_text("utf-8")
    for p in model.patterns:
        assert f'id="{p.id}"' in html
    # 図面パターンの代表がタイトルに出ている
    for kw in ("マルチコア", "アース接地", "分岐", "デイジーチェーン", "シールド", "ハイウェイ"):
        assert kw in html


def test_deterministic(tmp_path):
    a = build_report(EXAMPLE, "html", tmp_path / "a")[2].read_text("utf-8")
    b = build_report(EXAMPLE, "html", tmp_path / "b")[2].read_text("utf-8")
    assert a == b


def test_all_methods_report_has_tabs(tmp_path):
    """--method all: 図タブが出る。外部ツールがあれば circuit は複数方式になる。"""
    import shutil

    model, manifest, report = build_report(EXAMPLE, "all", tmp_path)
    html = report.read_text("utf-8")
    assert 'class="figtabs"' in html
    assert html.count('class="figtabs"') == len(model.patterns)
    assert html.count('<input class="tabradio"') == len(manifest.assets)
    if shutil.which("dot"):
        circuit_ids = [p.id for p in model.patterns if p.type == "circuit"]
        multi = [c for c in circuit_ids if len({a.method for a in manifest.assets_for(c)}) > 1]
        assert multi
