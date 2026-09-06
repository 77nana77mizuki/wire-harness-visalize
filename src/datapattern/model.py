"""``DataPatternModel`` — 解析・描画・レポート組立をつなぐ唯一の契約。

JSON Schema (``schema/datapattern.schema.json``) が検証の正。ここではその上に
型付きの読み取りビュー（frozen dataclass）を提供する。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema

PropertyScalar = str | int | float | bool | None

_SCHEMA_RESOURCE = "datapattern.schema.json"


class SchemaValidationError(ValueError):
    """``DataPatternModel`` が JSON Schema に適合しないとき送出される。

    ``errors`` に人間可読なメッセージを全件（決定論的な順序で）保持する。
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        joined = "\n".join(f"  - {e}" for e in errors)
        super().__init__(f"DataPatternModel is invalid ({len(errors)} error(s)):\n{joined}")


def load_schema() -> dict[str, Any]:
    """同梱の JSON Schema を辞書として返す。"""
    text = resources.files("datapattern.schema").joinpath(_SCHEMA_RESOURCE).read_text("utf-8")
    return json.loads(text)


def _format_error(err: jsonschema.ValidationError) -> str:
    location = "/".join(str(p) for p in err.absolute_path) or "<root>"
    return f"{location}: {err.message}"


def validate_model_dict(data: Any) -> None:
    """``data`` を JSON Schema で検証する。適合しなければ :class:`SchemaValidationError`。"""
    validator_cls = jsonschema.validators.validator_for(load_schema())
    validator = validator_cls(load_schema())
    errors = sorted(validator.iter_errors(data), key=lambda e: (list(e.absolute_path), e.message))
    if errors:
        raise SchemaValidationError([_format_error(e) for e in errors])


# --------------------------------------------------------------------------- #
# 型付きビュー
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Addon:
    name: str
    plugin_type: str = "unknown"
    capital_version: str | None = None
    source_refs: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Addon:
        return cls(
            name=d["name"],
            plugin_type=d.get("pluginType", "unknown"),
            capital_version=d.get("capitalVersion"),
            source_refs=tuple(d.get("sourceRefs", ())),
        )


@dataclass(frozen=True, slots=True)
class GeneratedFrom:
    evidence_hash: str | None = None
    generator: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GeneratedFrom:
        return cls(evidence_hash=d.get("evidenceHash"), generator=d.get("generator"))


@dataclass(frozen=True, slots=True)
class CapitalObject:
    kind: str
    ref: str | None = None
    properties: dict[str, PropertyScalar] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CapitalObject:
        return cls(kind=d["kind"], ref=d.get("ref"), properties=dict(d.get("properties", {})))


@dataclass(frozen=True, slots=True)
class VariantRow:
    expr: str
    resolves_to: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> VariantRow:
        return cls(expr=d["expr"], resolves_to=tuple(d.get("resolvesTo", ())))


@dataclass(frozen=True, slots=True)
class Node:
    id: str
    kind: str
    pincount: int | None = None
    pinlabels: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Node:
        return cls(
            id=d["id"],
            kind=d["kind"],
            pincount=d.get("pincount"),
            pinlabels=tuple(d.get("pinlabels", ())),
        )


@dataclass(frozen=True, slots=True)
class Edge:
    source: str
    target: str
    via: str | None = None
    gauge: str | None = None
    color: str | None = None
    shield: bool = False

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Edge:
        return cls(
            source=d["from"],
            target=d["to"],
            via=d.get("via"),
            gauge=d.get("gauge"),
            color=d.get("color"),
            shield=bool(d.get("shield", False)),
        )


@dataclass(frozen=True, slots=True)
class Connectivity:
    nodes: tuple[Node, ...] = ()
    edges: tuple[Edge, ...] = ()

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Connectivity:
        return cls(
            nodes=tuple(Node.from_dict(n) for n in d.get("nodes", ())),
            edges=tuple(Edge.from_dict(e) for e in d.get("edges", ())),
        )


@dataclass(frozen=True, slots=True)
class PropertyExpectation:
    object: str
    property: str
    why: str
    value: PropertyScalar = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PropertyExpectation:
        return cls(
            object=d["object"],
            property=d["property"],
            why=d["why"],
            value=d.get("value"),
        )


@dataclass(frozen=True, slots=True)
class Pattern:
    id: str
    type: str
    title: str
    summary: str
    rationale: str
    capital_objects: tuple[CapitalObject, ...] = ()
    option_expression: str | None = None
    variant_matrix: tuple[VariantRow, ...] = ()
    connectivity: Connectivity | None = None
    property_expectations: tuple[PropertyExpectation, ...] = ()
    test_hints: tuple[str, ...] = ()
    preferred_methods: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Pattern:
        conn = d.get("connectivity")
        return cls(
            id=d["id"],
            type=d["type"],
            title=d["title"],
            summary=d["summary"],
            rationale=d["rationale"],
            capital_objects=tuple(CapitalObject.from_dict(o) for o in d.get("capitalObjects", ())),
            option_expression=d.get("optionExpression"),
            variant_matrix=tuple(VariantRow.from_dict(v) for v in d.get("variantMatrix", ())),
            connectivity=Connectivity.from_dict(conn) if conn is not None else None,
            property_expectations=tuple(
                PropertyExpectation.from_dict(p) for p in d.get("propertyExpectations", ())
            ),
            test_hints=tuple(d.get("testHints", ())),
            preferred_methods=tuple(d.get("renderHints", {}).get("preferredMethods", ())),
        )


@dataclass(frozen=True, slots=True)
class DataPatternModel:
    schema_version: str
    addon: Addon
    patterns: tuple[Pattern, ...]
    generated_from: GeneratedFrom | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, validate: bool = True) -> DataPatternModel:
        if validate:
            validate_model_dict(data)
        gen = data.get("generatedFrom")
        return cls(
            schema_version=data["schemaVersion"],
            addon=Addon.from_dict(data["addon"]),
            patterns=tuple(Pattern.from_dict(p) for p in data.get("patterns", ())),
            generated_from=GeneratedFrom.from_dict(gen) if gen is not None else None,
        )

    def pattern_by_id(self, pattern_id: str) -> Pattern | None:
        return next((p for p in self.patterns if p.id == pattern_id), None)


def load_model(path: str | Path, *, validate: bool = True) -> DataPatternModel:
    """``path`` の JSON を読み込み、検証して :class:`DataPatternModel` を返す。"""
    raw = json.loads(Path(path).read_text("utf-8"))
    return DataPatternModel.from_dict(raw, validate=validate)
