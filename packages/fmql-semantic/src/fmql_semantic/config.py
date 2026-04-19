from __future__ import annotations

import os
from dataclasses import dataclass, replace
from typing import Any, Literal

from fmql_semantic.dotenv import load_dotenv
from fmql_semantic.errors import ConfigError

DEFAULT_FIELDS: tuple[str, ...] = ("title", "summary", "name")

_BUILD_KEYS = frozenset(
    {
        "env",
        "model",
        "api_base",
        "api_key",
        "batch_size",
        "concurrency",
        "max_tokens",
        "fields",
        "force",
    }
)
_QUERY_KEYS = frozenset(
    {
        "env",
        "model",
        "api_base",
        "api_key",
        "reranker_model",
        "reranker_top_n",
        "rerank_required",
        "no_rerank",
        "dense_only",
        "sparse_only",
        "fetch_k",
    }
)

_ENV_MAP: dict[str, str] = {
    "FMQL_EMBEDDING_MODEL": "embedding_model",
    "FMQL_EMBEDDING_API_BASE": "embedding_api_base",
    "FMQL_EMBEDDING_API_KEY": "embedding_api_key",
    "FMQL_EMBEDDING_BATCH_SIZE": "embedding_batch_size",
    "FMQL_EMBEDDING_CONCURRENCY": "embedding_concurrency",
    "FMQL_EMBEDDING_MAX_TOKENS": "embedding_max_tokens",
    "FMQL_RERANKER_MODEL": "reranker_model",
    "FMQL_RERANKER_TOP_N": "reranker_top_n",
}

_OPT_MAP: dict[str, str] = {
    "model": "embedding_model",
    "api_base": "embedding_api_base",
    "api_key": "embedding_api_key",
    "batch_size": "embedding_batch_size",
    "concurrency": "embedding_concurrency",
    "max_tokens": "embedding_max_tokens",
    "fields": "fields",
    "force": "force",
    "reranker_model": "reranker_model",
    "reranker_top_n": "reranker_top_n",
    "rerank_required": "rerank_required",
    "no_rerank": "rerank_disabled",
    "dense_only": "dense_only",
    "sparse_only": "sparse_only",
    "fetch_k": "fetch_k",
}

_INT_FIELDS = frozenset(
    {
        "embedding_batch_size",
        "embedding_concurrency",
        "embedding_max_tokens",
        "reranker_top_n",
        "fetch_k",
    }
)
_BOOL_FIELDS = frozenset(
    {"force", "rerank_required", "rerank_disabled", "dense_only", "sparse_only"}
)


@dataclass(frozen=True)
class Config:
    # shared
    embedding_model: str | None = None
    embedding_api_base: str | None = None
    embedding_api_key: str | None = None
    # build-only
    embedding_batch_size: int = 100
    embedding_concurrency: int = 4
    embedding_max_tokens: int = 8000
    fields: tuple[str, ...] = DEFAULT_FIELDS
    force: bool = False
    # query-only
    reranker_model: str | None = None
    reranker_top_n: int = 50
    rerank_disabled: bool = False
    rerank_required: bool = False
    dense_only: bool = False
    sparse_only: bool = False
    fetch_k: int | None = None


def _coerce(field: str, value: Any) -> Any:
    if field in _INT_FIELDS:
        try:
            return int(value)
        except (TypeError, ValueError) as e:
            raise ConfigError(f"{field}: expected integer, got {value!r}") from e
    if field in _BOOL_FIELDS:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            low = value.strip().lower()
            if low in {"true", "1", "yes", "on"}:
                return True
            if low in {"false", "0", "no", "off"}:
                return False
        if isinstance(value, int):
            return bool(value)
        raise ConfigError(f"{field}: expected boolean, got {value!r}")
    if field == "fields":
        if isinstance(value, str):
            parts = [p.strip() for p in value.split(",") if p.strip()]
            return tuple(parts)
        if isinstance(value, (list, tuple)):
            return tuple(str(v) for v in value)
        raise ConfigError(f"fields: expected comma-separated string or list, got {value!r}")
    return value


def resolve_config(options: dict | None, *, kind: Literal["build", "query"]) -> Config:
    options = dict(options or {})
    allowed = _BUILD_KEYS if kind == "build" else _QUERY_KEYS
    unknown = set(options) - allowed
    if unknown:
        raise ConfigError(
            f"unknown options for {kind}: {sorted(unknown)}. Allowed: {sorted(allowed)}."
        )

    cfg = Config()
    layered: dict[str, Any] = {}

    for env_key, field in _ENV_MAP.items():
        if env_key in os.environ:
            layered[field] = _coerce(field, os.environ[env_key])

    env_path = options.pop("env", None)
    if env_path is not None:
        parsed = load_dotenv(env_path)
        for env_key, field in _ENV_MAP.items():
            if env_key in parsed:
                layered[field] = _coerce(field, parsed[env_key])
        for key, value in parsed.items():
            os.environ.setdefault(key, value)

    for opt_key, value in options.items():
        field = _OPT_MAP[opt_key]
        layered[field] = _coerce(field, value)

    cfg = replace(cfg, **layered)

    if kind == "build" and not cfg.embedding_model:
        raise ConfigError(
            "missing embedding model: set FMQL_EMBEDDING_MODEL, --option env=path/to/.env, "
            "or --option model=<litellm-model>. See https://docs.litellm.ai/docs/embedding/supported_embedding"
        )
    if kind == "query" and not cfg.sparse_only and not cfg.embedding_model:
        raise ConfigError(
            "missing embedding model: set FMQL_EMBEDDING_MODEL, --option env=path/to/.env, "
            "or --option model=<litellm-model>. Pass --option sparse_only=true to skip embeddings."
        )
    if cfg.dense_only and cfg.sparse_only:
        raise ConfigError("dense_only and sparse_only are mutually exclusive")

    return cfg
