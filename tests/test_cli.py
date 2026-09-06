"""CLI 骨組み。"""

import json

import pytest

from datapattern.cli import main


def test_validate_ok(capsys, fixtures_dir):
    rc = main(["validate", str(fixtures_dir / "valid_full.json")])
    assert rc == 0
    assert "妥当です" in capsys.readouterr().out


def test_validate_invalid(capsys, fixtures_dir):
    rc = main(["validate", str(fixtures_dir / "invalid_missing_type.json")])
    assert rc == 1
    assert "invalid" in capsys.readouterr().err


def test_validate_missing_file(capsys, tmp_path):
    rc = main(["validate", str(tmp_path / "nope.json")])
    assert rc == 2


def test_schema_dump(capsys):
    rc = main(["schema"])
    assert rc == 0
    out = capsys.readouterr().out
    assert json.loads(out)["title"] == "DataPatternModel"


def test_schema_path_only(capsys):
    rc = main(["schema", "--path-only"])
    assert rc == 0
    assert capsys.readouterr().out.strip().endswith("datapattern.schema.json")


def test_ingest_cmd(capsys, tmp_path, fixtures_dir):
    rc = main(["ingest", str(fixtures_dir / "sample_addon"), "--out", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "workspace" / "manifest.json").is_file()
    assert "files" in capsys.readouterr().out


def test_scan_cmd(capsys, tmp_path, fixtures_dir):
    rc = main(["scan", str(fixtures_dir / "sample_addon"), "--out", str(tmp_path)])
    assert rc == 0
    ev = json.loads((tmp_path / "workspace" / "evidence.json").read_text("utf-8"))
    assert ev["pluginTypeGuess"] in {"check", "action"}


def test_combos_cmd(capsys):
    rc = main(["combos", "--codes", "OPT_A,OPT_B", "--exclusive", "OPT_A:OPT_B"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert any(c["label"] == "exclusive-violation:OPT_A+OPT_B" for c in out)


def test_report_end_to_end(capsys, tmp_path, fixtures_dir):
    rc = main(["report", str(fixtures_dir / "valid_full.json"), "--out", str(tmp_path)])
    assert rc == 0
    report = tmp_path / "report.html"
    assert report.is_file()
    text = report.read_text("utf-8")
    assert "<!DOCTYPE html>" in text
    assert "GroundCircuitDrc" in text
    assert (tmp_path / "renders" / "html" / "index.json").is_file()
    assert (tmp_path / "renders" / "html" / "opt-cfg-all-false.html").is_file()


def test_render_only(tmp_path, fixtures_dir):
    rc = main(["render", str(fixtures_dir / "valid_full.json"), "--out", str(tmp_path)])
    assert rc == 0
    index = json.loads((tmp_path / "renders" / "html" / "index.json").read_text("utf-8"))
    assert set(index["entries"]) == {
        "circuit-switched-ground",
        "opt-cfg-all-false",
        "prop-wire-csa-lower-bound",
    }


def test_unknown_renderer(capsys, fixtures_dir, tmp_path):
    args = ["report", str(fixtures_dir / "valid_full.json"), "--out", str(tmp_path)]
    rc = main([*args, "--method", "nope"])
    assert rc == 2
    assert "未知のレンダラ" in capsys.readouterr().err


def test_no_command_errors():
    with pytest.raises(SystemExit):
        main([])
