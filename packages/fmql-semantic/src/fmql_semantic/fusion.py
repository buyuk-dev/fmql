from __future__ import annotations

from typing import Sequence

K_RRF = 60


def reciprocal_rank_fusion(
    *ranked_lists: Sequence[tuple[str, float]],
    k_rrf: int = K_RRF,
) -> list[tuple[str, float]]:
    """Combine ranked `[(id, score)]` lists via reciprocal rank fusion.

    Score contribution from list L: 1 / (k_rrf + rank_L(id)), where rank_L is 1-based.
    IDs absent from a list contribute 0 from it.
    Returns [(id, rrf_score)] sorted by rrf_score descending.
    """
    totals: dict[str, float] = {}
    for lst in ranked_lists:
        for rank, (pid, _score) in enumerate(lst, start=1):
            totals[pid] = totals.get(pid, 0.0) + 1.0 / (k_rrf + rank)
    return sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
