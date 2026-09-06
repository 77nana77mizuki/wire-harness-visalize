"""option コードの組合せを決定論的に生成する。

全網羅は爆発するので「境界（全 false / 全 true / 各単独 true）＋ ペアワイズ ＋
排他制約違反」に絞る。``option_config`` パターンの variantMatrix の素材。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Combo:
    label: str
    assignment: dict[str, int]

    def expr(self) -> str:
        """'OPT_A=1,OPT_B=0' 形式（コード名昇順）。"""
        return ",".join(f"{k}={self.assignment[k]}" for k in sorted(self.assignment))


def _violates(assignment: dict[str, int], exclusive: list[tuple[str, ...]]) -> bool:
    return any(sum(assignment.get(c, 0) for c in group) > 1 for group in exclusive)


def _pairwise(codes: list[str]) -> list[dict[str, int]]:
    """二値のペアワイズ被覆を貪欲に生成。"""
    targets: set[tuple[int, int, int, int]] = set()
    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            for vi in (0, 1):
                for vj in (0, 1):
                    targets.add((i, vi, j, vj))

    rows: list[dict[str, int]] = []
    while targets:
        best_row: dict[str, int] | None = None
        best_cover: set[tuple[int, int, int, int]] = set()
        # 決定論的な候補列挙: 各未被覆ターゲットを起点に貪欲拡張
        for seed in sorted(targets):
            i, vi, j, vj = seed
            row = {codes[k]: 0 for k in range(len(codes))}
            row[codes[i]] = vi
            row[codes[j]] = vj
            fixed = {i, j}
            for k in range(len(codes)):
                if k in fixed:
                    continue
                gain0 = sum(
                    1
                    for (a, va, b, vb) in targets
                    if (a == k and va == 0 and b in fixed and row[codes[b]] == vb)
                    or (b == k and vb == 0 and a in fixed and row[codes[a]] == va)
                )
                gain1 = sum(
                    1
                    for (a, va, b, vb) in targets
                    if (a == k and va == 1 and b in fixed and row[codes[b]] == vb)
                    or (b == k and vb == 1 and a in fixed and row[codes[a]] == va)
                )
                row[codes[k]] = 1 if gain1 > gain0 else 0
                fixed.add(k)
            cover = {
                (a, va, b, vb)
                for (a, va, b, vb) in targets
                if row[codes[a]] == va and row[codes[b]] == vb
            }
            if len(cover) > len(best_cover):
                best_cover, best_row = cover, row
        assert best_row is not None
        rows.append(best_row)
        targets -= best_cover
    return rows


def generate_combos(
    codes: list[str],
    *,
    exclusive: list[list[str]] | None = None,
) -> list[Combo]:
    """``codes`` の代表的な組合せを返す（決定論、重複排除）。"""
    codes = sorted(dict.fromkeys(codes))
    groups: list[tuple[str, ...]] = [tuple(g) for g in (exclusive or [])]

    out: list[Combo] = []
    seen: set[tuple[tuple[str, int], ...]] = set()

    def add(label: str, assignment: dict[str, int]) -> None:
        key = tuple(sorted(assignment.items()))
        if key in seen:
            return
        seen.add(key)
        out.append(Combo(label=label, assignment=dict(assignment)))

    all_false = {c: 0 for c in codes}
    add("all-false", all_false)

    all_true = {c: 1 for c in codes}
    if codes and not _violates(all_true, groups):
        add("all-true", all_true)

    for c in codes:
        add(f"single:{c}", {**all_false, c: 1})

    for row in _pairwise(codes):
        if not _violates(row, groups):
            add("pairwise", row)

    for group in groups:
        if len(group) >= 2:
            a, b = sorted(group)[:2]
            add(f"exclusive-violation:{a}+{b}", {**all_false, a: 1, b: 1})

    return out
