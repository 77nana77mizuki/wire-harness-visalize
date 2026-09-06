"""static_scan.py — Java ソースからの事実抽出。"""

from datapattern.ingest import build_manifest
from datapattern.model import load_named_schema, validate_against
from datapattern.static_scan import scan


def _evidence(fixtures_dir):
    return scan(build_manifest(fixtures_dir / "sample_addon"))


def test_conforms_to_schema(fixtures_dir):
    ev = _evidence(fixtures_dir)
    validate_against(ev, load_named_schema("evidence.schema.json"))


def test_plugin_type_guess(fixtures_dir):
    ev = _evidence(fixtures_dir)
    # check（DRC）と action の両方の証拠がある。票の多い方 = 決定論的に安定
    assert ev["pluginTypeGuess"] in {"check", "action"}
    assert any("IXDrcCheck" in e for e in ev["pluginTypeEvidence"])
    assert any("IXAction" in e for e in ev["pluginTypeEvidence"])


def test_capital_imports(fixtures_dir):
    ev = _evidence(fixtures_dir)
    imports = ev["findings"]["capitalImports"]
    assert "com.mentor.capital.logic.IXConnector" in imports
    assert imports == sorted(imports)


def test_ix_types(fixtures_dir):
    ev = _evidence(fixtures_dir)
    names = {t["name"] for t in ev["findings"]["ixTypes"]}
    assert {"IXConnector", "IXWire", "IXSplice", "IXOptionExpression"} <= names
    conn = next(t for t in ev["findings"]["ixTypes"] if t["name"] == "IXConnector")
    assert all(r.startswith("src/com/example/") for r in conn["refs"])


def test_property_keys(fixtures_dir):
    ev = _evidence(fixtures_dir)
    keys = {k["name"] for k in ev["findings"]["propertyKeys"]}
    assert "PART_NUMBER" in keys
    assert "SPLICE_LABEL" in keys
    assert "CONDUCTOR_CSA" in keys


def test_option_and_verdict(fixtures_dir):
    ev = _evidence(fixtures_dir)
    assert any("OptionExpression" in c["text"] for c in ev["findings"]["optionApiCalls"])
    assert any("addViolation" in v["text"] for v in ev["findings"]["verdictBranches"])


def test_collections_iterated(fixtures_dir):
    ev = _evidence(fixtures_dir)
    names = {c["name"] for c in ev["findings"]["collectionsIterated"]}
    assert "connector" in names or "connectors" in names


def test_deterministic(fixtures_dir):
    import json

    a = json.dumps(_evidence(fixtures_dir), sort_keys=True)
    b = json.dumps(_evidence(fixtures_dir), sort_keys=True)
    assert a == b


def test_comments_are_ignored(fixtures_dir, tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "X.java").write_text(
        "// import com.mentor.capital.Fake;\n/* IXGhost should not count */\nclass X { }\n",
        encoding="utf-8",
    )
    ev = scan(build_manifest(tmp_path))
    assert ev["findings"]["capitalImports"] == []
    assert all(t["name"] != "IXGhost" for t in ev["findings"]["ixTypes"])
