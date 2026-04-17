from __future__ import annotations

import asyncio
from typing import Sequence

from fmql.search.errors import BackendUnavailableError
from fmql_semantic.config import Config


async def _embed_batch(
    texts: Sequence[str],
    *,
    model: str,
    api_base: str | None,
    api_key: str | None,
) -> list[list[float]]:
    import litellm  # type: ignore

    kwargs: dict = {"model": model, "input": list(texts)}
    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key
    try:
        resp = await litellm.aembedding(**kwargs)
    except Exception as e:
        raise BackendUnavailableError(f"embedding call failed ({type(e).__name__}): {e}") from e
    data = getattr(resp, "data", None) or resp["data"]
    return [list(item["embedding"]) for item in data]


def embed_sync(text: str, cfg: Config) -> list[float]:
    """Synchronously embed a single string via the configured model (used for query-time probe)."""
    if not cfg.embedding_model:
        raise BackendUnavailableError("embed_sync called without a configured model")
    vecs = asyncio.run(
        _embed_batch(
            [text],
            model=cfg.embedding_model,
            api_base=cfg.embedding_api_base,
            api_key=cfg.embedding_api_key,
        )
    )
    return vecs[0]


async def embed_many(
    texts: Sequence[str],
    *,
    cfg: Config,
) -> list[list[float]]:
    """Batch + bounded-concurrency embedding. Partial failures cancel pending work."""
    if not cfg.embedding_model:
        raise BackendUnavailableError("embed_many called without a configured model")
    if not texts:
        return []

    batch_size = max(1, cfg.embedding_batch_size)
    concurrency = max(1, cfg.embedding_concurrency)

    chunks: list[list[str]] = [
        list(texts[i : i + batch_size]) for i in range(0, len(texts), batch_size)
    ]
    sem = asyncio.Semaphore(concurrency)

    async def _run(chunk: list[str]) -> list[list[float]]:
        async with sem:
            return await _embed_batch(
                chunk,
                model=cfg.embedding_model,
                api_base=cfg.embedding_api_base,
                api_key=cfg.embedding_api_key,
            )

    results = await asyncio.gather(*[_run(c) for c in chunks])
    flat: list[list[float]] = []
    for r in results:
        flat.extend(r)
    return flat
