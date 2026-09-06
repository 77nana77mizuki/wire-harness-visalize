"""``datapattern`` コマンドライン。

第1弾では ``validate`` / ``schema`` のみ実働。``ingest``/``scan``/``render``/``report``/``run``
は骨組み（ロードマップ [[docs/03-architecture.md]] §H）。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from datapattern import __version__
from datapattern.model import SchemaValidationError, load_model, load_schema

_NOT_IMPLEMENTED_PHASE = {
    "ingest": "第3弾",
    "scan": "第3弾",
    "render": "第5弾",
    "report": "第2弾",
    "run": "第4弾",
}


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        model = load_model(args.path)
    except SchemaValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read {args.path}: {exc}", file=sys.stderr)
        return 2
    print(
        f"OK: {args.path} は DataPatternModel v{model.schema_version} として妥当です "
        f"(addon={model.addon.name!r}, patterns={len(model.patterns)})"
    )
    return 0


def _cmd_schema(args: argparse.Namespace) -> int:
    schema = load_schema()
    if args.path_only:
        import datapattern.schema as schema_pkg

        print(Path(schema_pkg.__file__).parent / "datapattern.schema.json")
    else:
        json.dump(schema, sys.stdout, ensure_ascii=False, indent=2, sort_keys=False)
        sys.stdout.write("\n")
    return 0


def _cmd_stub(args: argparse.Namespace) -> int:
    phase = _NOT_IMPLEMENTED_PHASE.get(args.command, "未定")
    print(
        f"`datapattern {args.command}` は未実装です（{phase}で実装予定）。"
        f" 進捗は docs/03-architecture.md §H を参照。",
        file=sys.stderr,
    )
    return 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="datapattern",
        description=(
            "Capital Logic アドオンのテスト用データパターンを洗い出し、"
            "図つき HTML レポートを生成する。"
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    p_validate = sub.add_parser("validate", help="datapatterns.json を JSON Schema で検証する")
    p_validate.add_argument("path", type=Path, help="検証する datapatterns.json")
    p_validate.set_defaults(func=_cmd_validate)

    p_schema = sub.add_parser("schema", help="同梱の JSON Schema を出力する")
    p_schema.add_argument(
        "--path-only", action="store_true", help="スキーマ本体ではなくファイルパスを出力"
    )
    p_schema.set_defaults(func=_cmd_schema)

    for name in ("ingest", "scan", "render", "report", "run"):
        p = sub.add_parser(name, help=f"[未実装] {name}")
        p.set_defaults(func=_cmd_stub)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
