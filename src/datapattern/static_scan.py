"""Java アドオンソースから「事実」を機械抽出する（決定論）。

正規表現ベースの軽量スキャン。コンパイルは伴わない。より高精度が必要になったら
tree-sitter-java へ差し替える（``docs/03-architecture.md`` §H / ``docs/01`` §C）。
意味解釈（どのパターンをテストすべきか）は LLM 側（capital-addon-analysis skill）。
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from datapattern.ingest import Manifest
from datapattern.model import load_named_schema, validate_against

_SCANNER = "datapattern.static_scan@0.1.0 (regex)"

_RE_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_RE_LINE_COMMENT = re.compile(r"//[^\n]*")
_RE_IMPORT = re.compile(r"^\s*import\s+(static\s+)?([\w.]+)\s*;", re.MULTILINE)
_RE_TYPE_DECL = re.compile(
    r"\b(?:class|interface|enum)\s+(\w+)"
    r"(?:\s+extends\s+([\w.]+(?:<[^>]*>)?))?"
    r"(?:\s+implements\s+([\w.,\s<>]+?))?\s*\{"
)
_RE_IX = re.compile(r"\bIX[A-Z]\w*\b")
_RE_PROP = re.compile(
    r"\.(?:get|set)(?:Property|Attribute|Attr|Value|Param)\s*\(\s*\"([^\"]{1,80})\""
)
_RE_CONST_KEY = re.compile(r"\"([A-Z][A-Z0-9_]{2,40})\"")
# camelCase（getOptionExpression 等）も拾うため \b は課さない。
_RE_OPTION = re.compile(
    r"(?:option|variant|module).{0,48}?"
    r"(?:express|expr|code|evaluate|resolve|effectiv|configuration|150%)",
    re.IGNORECASE,
)
_RE_VERDICT = re.compile(
    r"\b(?:addError|addWarning|addViolation|reportError|reportViolation|"
    r"Status\.(?:FAIL|PASS)|Verdict\.|new\s+\w*Violation)\b"
)
_RE_FOREACH = re.compile(r"for\s*\(\s*[\w.<>]+\s+\w+\s*:\s*([\w.]+(?:\(\))?)\s*\)")
_RE_GETTERS = re.compile(r"\.get([A-Z]\w+?)s\s*\(\s*\)")

_CAPITAL_HINT = re.compile(r"(?:capital|mentor|\bIX[A-Z])", re.IGNORECASE)

_PLUGIN_TYPE_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("check", re.compile(r"check|rule|drc|constraint|validat", re.IGNORECASE)),
    ("report", re.compile(r"report|publish|export|document", re.IGNORECASE)),
    ("action", re.compile(r"action|command|operation|task", re.IGNORECASE)),
    ("ui", re.compile(r"panel|dialog|\bview\b|widget|\bui\b|menu", re.IGNORECASE)),
)


@dataclass
class _Acc:
    plugin_evidence: list[str] = field(default_factory=list)
    plugin_votes: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    capital_imports: set[str] = field(default_factory=set)
    ix_types: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    property_keys: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    option_calls: list[dict[str, str]] = field(default_factory=list)
    verdicts: list[dict[str, str]] = field(default_factory=list)
    collections: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))


def _strip_comments(text: str) -> str:
    """コメントを空白（改行は保持）に置換して行番号を保つ。"""

    def _blank(m: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    return _RE_LINE_COMMENT.sub(_blank, _RE_BLOCK_COMMENT.sub(_blank, text))


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _scan_file(rel_path: str, source: str, acc: _Acc) -> None:
    text = _strip_comments(source)

    for m in _RE_IMPORT.finditer(text):
        fqn = m.group(2)
        if _CAPITAL_HINT.search(fqn):
            acc.capital_imports.add(fqn)

    for m in _RE_TYPE_DECL.finditer(text):
        name, extends, implements = m.group(1), m.group(2), m.group(3)
        supers = [s.strip() for s in re.split(r"[,\s]+", implements or "") if s.strip()]
        if extends:
            supers.append(extends.strip())
        ref = f"{rel_path}#L{_line_of(text, m.start())}"
        for sup in supers:
            for ptype, rule in _PLUGIN_TYPE_RULES:
                if rule.search(sup):
                    acc.plugin_votes[ptype] += 1
                    acc.plugin_evidence.append(f"{name} : {sup} → {ptype} ({ref})")
                    break

    for m in _RE_IX.finditer(text):
        acc.ix_types[m.group(0)].append(f"{rel_path}#L{_line_of(text, m.start())}")

    for m in _RE_PROP.finditer(text):
        acc.property_keys[m.group(1)].append(f"{rel_path}#L{_line_of(text, m.start())}")

    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if _RE_OPTION.search(line):
            acc.option_calls.append({"ref": f"{rel_path}#L{lineno}", "text": stripped[:200]})
        if _RE_VERDICT.search(line):
            acc.verdicts.append({"ref": f"{rel_path}#L{lineno}", "text": stripped[:200]})
        # 定数キーは option/attr らしい行に限定して拾う（ノイズ低減）
        if re.search(r"attr|property|key|param", line, re.IGNORECASE):
            for m in _RE_CONST_KEY.finditer(line):
                acc.property_keys[m.group(1)].append(f"{rel_path}#L{lineno}")

    for m in _RE_FOREACH.finditer(text):
        acc.collections[m.group(1).rstrip("()")].append(f"{rel_path}#L{_line_of(text, m.start())}")
    for m in _RE_GETTERS.finditer(text):
        acc.collections[m.group(1).lower()].append(f"{rel_path}#L{_line_of(text, m.start())}")


def _sorted_named(d: dict[str, list[str]]) -> list[dict[str, object]]:
    return [{"name": k, "refs": sorted(set(d[k]))} for k in sorted(d)]


def scan(manifest: Manifest, *, validate: bool = True) -> dict[str, object]:
    """マニフェストのファイルを走査して evidence 辞書を返す（``evidence.schema.json`` 準拠）。"""
    root = Path(manifest.root)
    acc = _Acc()
    for entry in sorted(manifest.files, key=lambda f: f.path):
        source = (root / entry.path).read_text("utf-8", errors="replace")
        _scan_file(entry.path, source, acc)

    if acc.plugin_votes:
        best = max(sorted(acc.plugin_votes), key=lambda k: acc.plugin_votes[k])
        plugin_guess = best
    else:
        plugin_guess = "unknown"

    evidence: dict[str, object] = {
        "schemaVersion": "1.0",
        "manifestDigest": manifest.digest,
        "scanner": _SCANNER,
        "pluginTypeGuess": plugin_guess,
        "pluginTypeEvidence": sorted(set(acc.plugin_evidence)),
        "findings": {
            "capitalImports": sorted(acc.capital_imports),
            "ixTypes": _sorted_named(acc.ix_types),
            "propertyKeys": _sorted_named(acc.property_keys),
            "optionApiCalls": sorted(acc.option_calls, key=lambda d: (d["ref"], d["text"])),
            "verdictBranches": sorted(acc.verdicts, key=lambda d: (d["ref"], d["text"])),
            "collectionsIterated": _sorted_named(acc.collections),
        },
    }
    if validate:
        validate_against(evidence, load_named_schema("evidence.schema.json"))
    return evidence


def write_evidence(evidence: dict[str, object], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
