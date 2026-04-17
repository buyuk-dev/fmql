from __future__ import annotations

from fmql_semantic.fusion import K_RRF, reciprocal_rank_fusion


def test_rrf_known_output():
    dense = [("a", 0.9), ("b", 0.8), ("c", 0.7)]
    sparse = [("c", 3.0), ("b", 2.0), ("d", 1.0)]
    out = reciprocal_rank_fusion(dense, sparse)
    # Scores (k_rrf=60):
    # a: 1/61                ≈ 0.01639
    # b: 1/62 + 1/62         ≈ 0.03226
    # c: 1/63 + 1/61         ≈ 0.03226
    # d: 1/63                ≈ 0.01587
    ids = [pid for pid, _ in out]
    assert ids[:2] == ["b", "c"] or ids[:2] == ["c", "b"]
    assert set(ids) == {"a", "b", "c", "d"}
    score_map = dict(out)
    assert score_map["b"] == 1 / (K_RRF + 2) + 1 / (K_RRF + 2)
    assert score_map["a"] == 1 / (K_RRF + 1)


def test_rrf_empty_lists():
    assert reciprocal_rank_fusion([], []) == []


def test_rrf_single_list():
    out = reciprocal_rank_fusion([("a", 1.0), ("b", 0.5)])
    assert [pid for pid, _ in out] == ["a", "b"]


def test_rrf_custom_k():
    out = reciprocal_rank_fusion([("a", 1.0)], k_rrf=10)
    assert out[0][1] == 1 / 11
