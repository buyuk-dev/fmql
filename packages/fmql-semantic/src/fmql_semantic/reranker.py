from __future__ import annotations

import asyncio
import logging
from typing import Sequence

from fmql.search.errors import BackendUnavailableError
from fmql_semantic.config import Config

logger = logging.getLogger("fmql_semantic.reranker")


def rerank(
    query: str,
    documents: Sequence[str],
    *,
    cfg: Config,
) -> list[tuple[int, float]] | None:
    """Rerank `documents` against `query`. Returns [(index, score)] sorted by score desc,
    or None if reranking was skipped (soft-fail)."""
    if not cfg.reranker_model or cfg.rerank_disabled or not documents:
        return None
    try:
        return asyncio.run(_rerank_async(query, documents, cfg=cfg))
    except BackendUnavailableError:
        if cfg.rerank_required:
            raise
        logger.warning(
            "rerank call failed; falling back to RRF ordering. "
            "Pass --option rerank_required=true to make this a hard error."
        )
        return None


async def _rerank_async(
    query: str,
    documents: Sequence[str],
    *,
    cfg: Config,
) -> list[tuple[int, float]]:
    import litellm  # type: ignore

    kwargs: dict = {
        "model": cfg.reranker_model,
        "query": query,
        "documents": list(documents),
        "top_n": min(cfg.reranker_top_n, len(documents)),
    }
    if cfg.embedding_api_base:
        kwargs["api_base"] = cfg.embedding_api_base
    if cfg.embedding_api_key:
        kwargs["api_key"] = cfg.embedding_api_key
    try:
        resp = await litellm.arerank(**kwargs)
    except Exception as e:
        raise BackendUnavailableError(f"rerank call failed ({type(e).__name__}): {e}") from e

    results = _extract_results(resp)
    return sorted(
        [(int(r["index"]), float(r.get("relevance_score", r.get("score", 0.0)))) for r in results],
        key=lambda p: p[1],
        reverse=True,
    )


def _extract_results(resp: object) -> list[dict]:
    if isinstance(resp, dict) and "results" in resp:
        return list(resp["results"])
    results = getattr(resp, "results", None)
    if results is not None:
        return [dict(r) if not isinstance(r, dict) else r for r in results]
    raise BackendUnavailableError(f"unexpected rerank response shape: {type(resp).__name__}")
