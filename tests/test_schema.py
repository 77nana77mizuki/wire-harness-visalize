"""JSON Schema そのものの健全性と、代表的な適合 / 非適合ケース。"""

import jsonschema
import pytest

from datapattern.model import SchemaValidationError, load_schema, validate_model_dict


def test_schema_is_valid_metaschema():
    schema = load_schema()
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)


def test_valid_minimal_passes(load_fixture):
    validate_model_dict(load_fixture("valid_minimal.json"))


def test_valid_full_passes(load_fixture):
    validate_model_dict(load_fixture("valid_full.json"))


def test_missing_pattern_type_fails(load_fixture):
    with pytest.raises(SchemaValidationError) as exc:
        validate_model_dict(load_fixture("invalid_missing_type.json"))
    # type ガード付きの条件により、報告されるのは type 欠落のみ（分岐エラーで汚れない）
    assert exc.value.errors == ["patterns/0: 'type' is a required property"]


def test_unknown_top_level_key_fails(load_fixture):
    data = load_fixture("valid_minimal.json")
    data["unexpected"] = 1
    with pytest.raises(SchemaValidationError):
        validate_model_dict(data)


def test_circuit_requires_connectivity(load_fixture):
    data = load_fixture("valid_minimal.json")
    data["patterns"] = [
        {"id": "c1", "type": "circuit", "title": "t", "summary": "s", "rationale": "r"}
    ]
    with pytest.raises(SchemaValidationError) as exc:
        validate_model_dict(data)
    assert any("connectivity" in e for e in exc.value.errors)


def test_option_config_requires_expression_or_matrix(load_fixture):
    data = load_fixture("valid_minimal.json")
    data["patterns"] = [
        {"id": "o1", "type": "option_config", "title": "t", "summary": "s", "rationale": "r"}
    ]
    with pytest.raises(SchemaValidationError):
        validate_model_dict(data)


def test_property_set_requires_expectations(load_fixture):
    data = load_fixture("valid_minimal.json")
    data["patterns"] = [
        {"id": "p1", "type": "property_set", "title": "t", "summary": "s", "rationale": "r"}
    ]
    with pytest.raises(SchemaValidationError):
        validate_model_dict(data)


def test_pattern_id_must_be_kebab(load_fixture):
    data = load_fixture("valid_minimal.json")
    data["patterns"] = [
        {
            "id": "Not_Kebab",
            "type": "option_config",
            "title": "t",
            "summary": "s",
            "rationale": "r",
            "optionExpression": "X",
        }
    ]
    with pytest.raises(SchemaValidationError):
        validate_model_dict(data)


def test_errors_are_deterministically_ordered():
    data = {"schemaVersion": "1.0", "addon": {}, "patterns": [{"id": "x"}]}
    seen: list[list[str]] = []
    for _ in range(3):
        try:
            validate_model_dict(data)
        except SchemaValidationError as exc:
            seen.append(exc.errors)
    assert len(seen) == 3
    assert seen[0] == seen[1] == seen[2]
