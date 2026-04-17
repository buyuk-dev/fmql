from __future__ import annotations

from typing import Any

from fakes.hashing import cosine, deterministic_vector

DIM = 8


class FailingEmbedder:
    def __init__(self, exception: Exception) -> None:
        self.exception = exception
        self.calls = 0

    async def __call__(self, *, model: str, input: list[str], **kwargs: Any) -> dict:
        self.calls += 1
        raise self.exception


class FailingReranker:
    def __init__(self, exception: Exception) -> None:
        self.exception = exception
        self.calls = 0

    async def __call__(
        self, *, model: str, query: str, documents: list[str], **kwargs: Any
    ) -> dict:
        self.calls += 1
        raise self.exception


async def fake_aembedding(*, model: str, input: list[str], **kwargs: Any) -> dict:
    vecs = [deterministic_vector(t, DIM) for t in input]
    return {
        "object": "list",
        "model": model,
        "data": [{"object": "embedding", "index": i, "embedding": v} for i, v in enumerate(vecs)],
        "usage": {"prompt_tokens": 0, "total_tokens": 0},
    }


async def fake_arerank(
    *,
    model: str,
    query: str,
    documents: list[str],
    top_n: int | None = None,
    **kwargs: Any,
) -> dict:
    qvec = deterministic_vector(query, DIM)
    scored = [(i, cosine(qvec, deterministic_vector(doc, DIM))) for i, doc in enumerate(documents)]
    scored.sort(key=lambda p: p[1], reverse=True)
    if top_n is not None:
        scored = scored[:top_n]
    return {"results": [{"index": i, "relevance_score": s} for i, s in scored]}
