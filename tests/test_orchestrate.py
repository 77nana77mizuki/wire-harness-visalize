"""orchestrate.py と `datapattern run`。"""

import json

from datapattern.cli import main
from datapattern.model import load_named_schema, validate_against, validate_model_dict
from datapattern.orchestrate import build_report, patterns_template, prepare_workspace
from datapattern.render.html_renderer import HtmlRenderer


def test_prepare_workspace(tmp_path, fixtures_dir):
    ws = prepare_workspace(fixtures_dir / "sample_addon", tmp_path)
    assert ws.manifest_path.is_file()
    assert ws.evidence_path.is_file()
    assert ws.template_path.is_file()
    assert ws.evidence_hash.startswith("sha256:")
    validate_against(
        json.loads(ws.evidence_path.read_text("utf-8")),
        load_named_schema("evidence.schema.json"),
    )


def test_template_is_schema_valid(tmp_path, fixtures_dir):
    ws = prepare_workspace(fixtures_dir / "sample_addon", tmp_path)
    template = json.loads(ws.template_path.read_text("utf-8"))
    validate_model_dict(template)
    assert template["addon"]["pluginType"] in {"check", "action", "report", "ui", "unknown"}
    assert template["patterns"] == []


def test_patterns_template_pure():
    t = patterns_template({"pluginTypeGuess": "report"})
    validate_model_dict(t)
    assert t["addon"]["pluginType"] == "report"


def test_build_report(tmp_path, fixtures_dir):
    model, manifest, report_path = build_report(
        fixtures_dir / "valid_full.json", HtmlRenderer(), tmp_path
    )
    assert report_path.read_text("utf-8").startswith("<!DOCTYPE html>")
    assert len(manifest.assets) == len(model.patterns)


def test_run_prepare_only(capsys, tmp_path, fixtures_dir):
    rc = main(["run", "--addon", str(fixtures_dir / "sample_addon"), "--out", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "workspace" / "datapatterns.template.json").is_file()
    assert "次:" in capsys.readouterr().out


def test_run_patterns_only(capsys, tmp_path, fixtures_dir):
    rc = main(["run", "--patterns", str(fixtures_dir / "valid_full.json"), "--out", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "report.html").is_file()


def test_run_full(capsys, tmp_path, fixtures_dir):
    rc = main(
        [
            "run",
            "--addon",
            str(fixtures_dir / "sample_addon"),
            "--patterns",
            str(fixtures_dir / "valid_full.json"),
            "--out",
            str(tmp_path),
        ]
    )
    assert rc == 0
    assert (tmp_path / "workspace" / "evidence.json").is_file()
    assert (tmp_path / "report.html").is_file()


def test_run_needs_an_argument(capsys, tmp_path):
    rc = main(["run", "--out", str(tmp_path)])
    assert rc == 2


def test_run_is_deterministic(tmp_path, fixtures_dir):
    a = tmp_path / "a"
    b = tmp_path / "b"
    for d in (a, b):
        main(["run", "--addon", str(fixtures_dir / "sample_addon"), "--out", str(d)])
    for name in ("manifest.json", "evidence.json", "datapatterns.template.json"):
        assert (a / "workspace" / name).read_text() == (b / "workspace" / name).read_text()
