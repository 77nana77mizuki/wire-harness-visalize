"""``datapattern`` コマンドライン。

実働: ``ingest`` / ``scan`` / ``combos`` / ``validate`` / ``schema`` / ``render`` / ``report``。
骨組み: ``run``（ロードマップ ``docs/03-architecture.md`` §H）。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from datapattern import __version__
from datapattern.model import SchemaValidationError, load_model, load_schema
from datapattern.render.base import Renderer

_NOT_IMPLEMENTED_PHASE = {
    "run": "第4弾",
}


class CliError(Exception):
    """コマンド実行時のエラー。``main`` が終了コードに変換する。"""

    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


# 第5弾でレジストリに置き換える。今は html のみ。
_RENDERERS: dict[str, type[Renderer]] = {}


def _renderer(name: str) -> Renderer:
    if not _RENDERERS:
        from datapattern.render.html_renderer import HtmlRenderer

        _RENDERERS["html"] = HtmlRenderer
    try:
        return _RENDERERS[name]()
    except KeyError:
        raise CliError(
            f"未知のレンダラ: {name!r}（利用可能: {', '.join(sorted(_RENDERERS))}）", code=2
        ) from None


def _load(path: Path):
    try:
        return load_model(path)
    except SchemaValidationError as exc:
        raise CliError(str(exc), code=1) from None
    except (OSError, json.JSONDecodeError) as exc:
        raise CliError(f"cannot read {path}: {exc}", code=2) from None


def _cmd_validate(args: argparse.Namespace) -> int:
    model = _load(args.path)
    print(
        f"OK: {args.path} は DataPatternModel v{model.schema_version} として妥当です "
        f"(addon={model.addon.name!r}, patterns={len(model.patterns)})"
    )
    return 0


def _cmd_schema(args: argparse.Namespace) -> int:
    if args.path_only:
        import datapattern.schema as schema_pkg

        print(Path(schema_pkg.__file__).parent / "datapattern.schema.json")
    else:
        json.dump(load_schema(), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    from datapattern.render.pipeline import render_patterns

    model = _load(args.path)
    manifest = render_patterns(model, _renderer(args.method), args.out / "renders")
    print(
        f"render: {len(manifest.assets)} 件を {manifest.method_dir}/ に出力"
        f"（skip {len(manifest.skipped)} 件）"
    )
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    from datapattern.render.pipeline import render_patterns
    from datapattern.report import write_report

    model = _load(args.path)
    manifest = render_patterns(model, _renderer(args.method), args.out / "renders")
    out_html = write_report(model, manifest, args.out / "report.html")
    print(f"report: {out_html}（patterns={len(model.patterns)}, 図={len(manifest.assets)}）")
    return 0


def _cmd_ingest(args: argparse.Namespace) -> int:
    from datapattern.ingest import build_manifest, write_manifest

    try:
        manifest = build_manifest(args.src)
    except (OSError, NotADirectoryError) as exc:
        raise CliError(f"cannot read source dir {args.src}: {exc}", code=2) from None
    out = write_manifest(manifest, args.out / "workspace" / "manifest.json")
    print(f"ingest: {len(manifest.files)} files → {out}  ({manifest.digest})")
    return 0


def _cmd_scan(args: argparse.Namespace) -> int:
    from datapattern.ingest import build_manifest, write_manifest
    from datapattern.static_scan import scan, write_evidence

    try:
        manifest = build_manifest(args.src)
    except (OSError, NotADirectoryError) as exc:
        raise CliError(f"cannot read source dir {args.src}: {exc}", code=2) from None
    write_manifest(manifest, args.out / "workspace" / "manifest.json")
    evidence = scan(manifest)
    out = write_evidence(evidence, args.out / "workspace" / "evidence.json")
    f = evidence["findings"]
    print(
        f"scan: pluginType={evidence['pluginTypeGuess']}, "
        f"IX型={len(f['ixTypes'])}, プロパティキー={len(f['propertyKeys'])}, "
        f"option箇所={len(f['optionApiCalls'])} → {out}"
    )
    return 0


def _cmd_combos(args: argparse.Namespace) -> int:
    from datapattern.combos import generate_combos

    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    exclusive = [[x.strip() for x in g.split(":") if x.strip()] for g in (args.exclusive or [])]
    combos = generate_combos(codes, exclusive=exclusive)
    json.dump(
        [{"label": c.label, "assignment": c.assignment, "expr": c.expr()} for c in combos],
        sys.stdout,
        ensure_ascii=False,
        indent=2,
    )
    sys.stdout.write("\n")
    return 0


def _cmd_stub(args: argparse.Namespace) -> int:
    phase = _NOT_IMPLEMENTED_PHASE.get(args.command, "未定")
    print(
        f"`datapattern {args.command}` は未実装です（{phase}で実装予定）。"
        " 進捗は docs/03-architecture.md §H を参照。",
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

    p_render = sub.add_parser("render", help="各パターンを図アセットに変換する")
    p_render.add_argument("path", type=Path, help="datapatterns.json")
    p_render.add_argument("--out", type=Path, default=Path("out"), help="出力先（既定: out/）")
    p_render.add_argument("--method", default="html", help="レンダラ名（既定: html）")
    p_render.set_defaults(func=_cmd_render)

    p_report = sub.add_parser("report", help="report.html を生成する（render も実行）")
    p_report.add_argument("path", type=Path, help="datapatterns.json")
    p_report.add_argument("--out", type=Path, default=Path("out"), help="出力先（既定: out/）")
    p_report.add_argument("--method", default="html", help="レンダラ名（既定: html）")
    p_report.set_defaults(func=_cmd_report)

    p_ingest = sub.add_parser("ingest", help="ソースツリーを manifest.json に正規化する")
    p_ingest.add_argument("src", type=Path, help="アドオンのソースディレクトリ")
    p_ingest.add_argument("--out", type=Path, default=Path("out"), help="出力先（既定: out/）")
    p_ingest.set_defaults(func=_cmd_ingest)

    p_scan = sub.add_parser("scan", help="Java ソースから evidence.json を抽出する（ingest 込み）")
    p_scan.add_argument("src", type=Path, help="アドオンのソースディレクトリ")
    p_scan.add_argument("--out", type=Path, default=Path("out"), help="出力先（既定: out/）")
    p_scan.set_defaults(func=_cmd_scan)

    p_combos = sub.add_parser("combos", help="option コード組合せ（境界＋ペアワイズ）を生成する")
    p_combos.add_argument("--codes", required=True, help="カンマ区切りの option コード")
    p_combos.add_argument(
        "--exclusive",
        action="append",
        metavar="A:B[:C]",
        help="相互排他グループ（複数指定可）",
    )
    p_combos.set_defaults(func=_cmd_combos)

    for name in ("run",):
        p = sub.add_parser(name, help=f"[未実装] {name}")
        p.set_defaults(func=_cmd_stub)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except CliError as exc:
        print(str(exc), file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    raise SystemExit(main())
