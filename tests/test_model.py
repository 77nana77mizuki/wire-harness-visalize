"""型付きビュー（dataclass）の構築。"""

import pytest

from datapattern.model import (
    Connectivity,
    DataPatternModel,
    Pattern,
    SchemaValidationError,
    load_model,
)


def test_load_minimal(fixtures_dir):
    model = load_model(fixtures_dir / "valid_minimal.json")
    assert isinstance(model, DataPatternModel)
    assert model.schema_version == "1.0"
    assert model.addon.name == "SampleCheck"
    assert model.addon.plugin_type == "unknown"
    assert model.patterns == ()
    assert model.generated_from is None


def test_load_full(fixtures_dir):
    model = load_model(fixtures_dir / "valid_full.json")
    assert len(model.patterns) == 3
    assert model.addon.plugin_type == "check"
    assert model.addon.source_refs == ("src/main/java/com/example/GroundCircuitDrc.java#L20-L88",)
    assert model.generated_from is not None
    assert model.generated_from.generator == "capital-addon-analysis@0.1.0"


def test_pattern_by_id(fixtures_dir):
    model = load_model(fixtures_dir / "valid_full.json")
    p = model.pattern_by_id("circuit-switched-ground")
    assert isinstance(p, Pattern)
    assert p.type == "circuit"
    assert isinstance(p.connectivity, Connectivity)
    assert {n.id for n in p.connectivity.nodes} == {"D1", "X1", "S1"}
    assert p.connectivity.edges[0].source == "D1.GND"
    assert p.connectivity.edges[0].color == "BK"
    assert model.pattern_by_id("does-not-exist") is None


def test_option_config_pattern_fields(fixtures_dir):
    model = load_model(fixtures_dir / "valid_full.json")
    p = model.pattern_by_id("opt-cfg-all-false")
    assert p.option_expression == "OPT_GND"
    assert len(p.variant_matrix) == 2
    assert p.variant_matrix[0].resolves_to == ()
    assert p.variant_matrix[1].resolves_to == ("X1", "W1")
    assert p.preferred_methods == ("html", "graphviz")


def test_property_set_pattern_fields(fixtures_dir):
    model = load_model(fixtures_dir / "valid_full.json")
    p = model.pattern_by_id("prop-wire-csa-lower-bound")
    assert p.property_expectations[0].value == 0.35
    assert p.property_expectations[1].value == 0.34
    assert p.capital_objects[0].properties["csa"] == 0.35


def test_frozen(fixtures_dir):
    model = load_model(fixtures_dir / "valid_minimal.json")
    with pytest.raises((AttributeError, TypeError)):
        model.schema_version = "9.9"  # type: ignore[misc]


def test_invalid_raises(fixtures_dir):
    with pytest.raises(SchemaValidationError):
        load_model(fixtures_dir / "invalid_missing_type.json")


def test_skip_validation(fixtures_dir):
    # validate=False なら壊れた入力でも dataclass 構築まで進む（type は空文字などにならない）
    with pytest.raises(KeyError):
        load_model(fixtures_dir / "invalid_missing_type.json", validate=False)
