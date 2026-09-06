"""アドオンのソースツリーを正規化して ``manifest.json`` にする（決定論）。

収集対象・ハッシュ・行数だけを記録する。意味解釈は一切しない。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_PATTERNS = ("*.java",)
_SKIP_DIRS = {".git", "target", "build", "out", ".idea", "node_modules", "__pycache__"}


@dataclass(frozen=True, slots=True)
class SourceFile:
    path: str
    """マニフェスト root からの相対パス（posix 区切り）。"""
    sha256: str
    lines: int


@dataclass(frozen=True, slots=True)
class Manifest:
    root: str
    files: tuple[SourceFile, ...]
    digest: str
    """全ファイルの (path, sha256) を連結してとった sha256。``sha256:`` 前置。"""

    def to_dict(self) -> dict[str, object]:
        return {
            "root": self.root,
            "digest": self.digest,
            "files": [{"path": f.path, "sha256": f.sha256, "lines": f.lines} for f in self.files],
        }


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_manifest(root: Path, *, patterns: tuple[str, ...] = _DEFAULT_PATTERNS) -> Manifest:
    root = root.resolve()
    if not root.is_dir():
        raise NotADirectoryError(root)

    matches: list[Path] = []
    for pat in patterns:
        matches.extend(root.rglob(pat))

    files: list[SourceFile] = []
    for path in sorted(set(matches), key=lambda p: p.relative_to(root).as_posix()):
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if not path.is_file():
            continue
        data = path.read_bytes()
        files.append(
            SourceFile(
                path=path.relative_to(root).as_posix(),
                sha256=_sha256_bytes(data),
                lines=data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0),
            )
        )

    joined = "\n".join(f"{f.path}\0{f.sha256}" for f in files).encode("utf-8")
    return Manifest(root=str(root), files=tuple(files), digest=f"sha256:{_sha256_bytes(joined)}")


def write_manifest(manifest: Manifest, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path
