"""パイプライン結線（``datapattern run`` と `capital-datapattern-report` skill が使う）。

決定論パート（ingest → scan → render → report）をひとつなぎにする。
その間の「evidence → datapatterns.json」だけは LLM（`capital-addon-analysis` skill）が担う。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from datapattern.ingest import Manifest, build_manifest, write_manifest
from datapattern.model import DataPatternModel, load_model
from datapattern.render.base import Renderer
from datapattern.render.pipeline import RenderManifest, render_patterns
from datapattern.report import write_report
from datapattern.static_scan import scan, write_evidence


@dataclass(frozen=True, slots=True)
class PreparedWorkspace:
    manifest: Manifest
    manifest_path: Path
    evidence: dict[str, object]
    evidence_path: Path
    evidence_hash: str
    """``sha256:...``（evidence.json のバイト列に対して）。"""
    template_path: Path


def _sha256(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def patterns_template(evidence: dict[str, object]) -> dict[str, object]:
    """analyst（LLM）が埋めるための、検証を通る空テンプレート。"""
    return {
        "schemaVersion": "1.0",
        "addon": {
            "name": "TODO-addon-name",
            "pluginType": evidence.get("pluginTypeGuess", "unknown"),
        },
        "generatedFrom": {
            "evidenceHash": _sha256(
                json.dumps(evidence, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ),
            "generator": "capital-addon-analysis (TODO)",
        },
        "patterns": [],
    }


def prepare_workspace(src: Path, out: Path) -> PreparedWorkspace:
    """ingest + scan を実行し、``manifest.json`` / ``evidence.json`` /
    ``datapatterns.template.json`` を ``out/workspace/`` に書く。"""
    manifest = build_manifest(src)
    ws = out / "workspace"
    manifest_path = write_manifest(manifest, ws / "manifest.json")
    evidence = scan(manifest)
    evidence_path = write_evidence(evidence, ws / "evidence.json")
    evidence_hash = _sha256(evidence_path.read_bytes())

    template = patterns_template(evidence)
    template_path = ws / "datapatterns.template.json"
    template_path.write_text(
        json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return PreparedWorkspace(
        manifest=manifest,
        manifest_path=manifest_path,
        evidence=evidence,
        evidence_path=evidence_path,
        evidence_hash=evidence_hash,
        template_path=template_path,
    )


def build_report(
    patterns_path: Path,
    renderer: Renderer,
    out: Path,
) -> tuple[DataPatternModel, RenderManifest, Path]:
    """``datapatterns.json`` を検証し、render → report まで通す。"""
    model = load_model(patterns_path)
    manifest = render_patterns(model, renderer, out / "renders")
    report_path = write_report(model, manifest, out / "report.html")
    return model, manifest, report_path
