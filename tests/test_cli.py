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


@pytest.mark.parametrize("cmd", ["ingest", "scan", "render", "report", "run"])
def test_stub_commands(capsys, cmd):
    rc = main([cmd])
    assert rc == 3
    assert "未実装" in capsys.readouterr().err


def test_no_command_errors():
    with pytest.raises(SystemExit):
        main([])
