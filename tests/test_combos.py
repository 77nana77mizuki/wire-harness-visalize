"""combos.py — option 組合せ生成。"""

from datapattern.combos import generate_combos


def test_boundaries_present():
    combos = generate_combos(["OPT_A", "OPT_B", "OPT_C"])
    labels = [c.label for c in combos]
    assert "all-false" in labels
    assert "all-true" in labels
    assert labels.count("single:OPT_A") == 1
    assert "single:OPT_C" in labels


def test_all_false_is_first():
    combos = generate_combos(["Z", "A"])
    assert combos[0].label == "all-false"
    assert combos[0].assignment == {"A": 0, "Z": 0}


def test_pairwise_covers_all_pairs():
    codes = ["A", "B", "C", "D"]
    combos = generate_combos(codes)
    rows = [c.assignment for c in combos]
    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            for vi in (0, 1):
                for vj in (0, 1):
                    assert any(r[codes[i]] == vi and r[codes[j]] == vj for r in rows), (
                        f"missing pair {codes[i]}={vi},{codes[j]}={vj}"
                    )


def test_exclusive_violation_and_no_valid_all_true():
    combos = generate_combos(["A", "B", "C"], exclusive=[["A", "B"]])
    labels = [c.label for c in combos]
    assert "exclusive-violation:A+B" in labels
    # 排他を破る行は violation ラベルのものだけ
    for c in combos:
        if c.label != "exclusive-violation:A+B":
            assert c.assignment["A"] + c.assignment["B"] <= 1


def test_deterministic():
    a = [(c.label, c.expr()) for c in generate_combos(["X", "Y", "Z"], exclusive=[["X", "Z"]])]
    b = [(c.label, c.expr()) for c in generate_combos(["Z", "Y", "X"], exclusive=[["Z", "X"]])]
    assert a == b


def test_expr_format():
    (c,) = [c for c in generate_combos(["B", "A"]) if c.label == "single:A"]
    assert c.expr() == "A=1,B=0"


def test_empty():
    assert generate_combos([]) == generate_combos([])
    assert [c.label for c in generate_combos([])] == ["all-false"]
