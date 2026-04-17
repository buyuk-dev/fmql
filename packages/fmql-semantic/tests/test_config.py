from __future__ import annotations

from pathlib import Path

import pytest

from fmql_semantic.config import DEFAULT_FIELDS, Config, resolve_config
from fmql_semantic.errors import ConfigError


def test_defaults_for_build_require_model():
    with pytest.raises(ConfigError, match="embedding model"):
        resolve_config({}, kind="build")


def test_env_provides_model(monkeypatch):
    monkeypatch.setenv("FMQL_EMBEDDING_MODEL", "env/model")
    cfg = resolve_config({}, kind="build")
    assert cfg.embedding_model == "env/model"
    assert cfg.fields == DEFAULT_FIELDS
    assert isinstance(cfg, Config)


def test_option_overrides_env(monkeypatch):
    monkeypatch.setenv("FMQL_EMBEDDING_MODEL", "env/model")
    cfg = resolve_config({"model": "opt/model"}, kind="build")
    assert cfg.embedding_model == "opt/model"


def test_dotenv_layered_between_env_and_options(monkeypatch, tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("FMQL_EMBEDDING_MODEL=dotenv/model\nFMQL_EMBEDDING_API_KEY=dotenv-key\n")
    monkeypatch.setenv("FMQL_EMBEDDING_MODEL", "proc/model")
    cfg = resolve_config({"env": str(env_file), "model": "opt/model"}, kind="build")
    assert cfg.embedding_model == "opt/model"
    assert cfg.embedding_api_key == "dotenv-key"


def test_missing_dotenv_errors():
    with pytest.raises(ConfigError, match="dotenv file not found"):
        resolve_config({"env": "/nonexistent/file.env"}, kind="build")


def test_unknown_option_for_build():
    with pytest.raises(ConfigError, match="unknown options for build"):
        resolve_config({"model": "m", "reranker_model": "r"}, kind="build")


def test_unknown_option_for_query():
    with pytest.raises(ConfigError, match="unknown options for query"):
        resolve_config({"model": "m", "batch_size": 10}, kind="query")


def test_fields_coerced_from_csv():
    cfg = resolve_config({"model": "m", "fields": "title,slug,name"}, kind="build")
    assert cfg.fields == ("title", "slug", "name")


def test_fields_from_list():
    cfg = resolve_config({"model": "m", "fields": ["a", "b"]}, kind="build")
    assert cfg.fields == ("a", "b")


def test_int_coercion():
    cfg = resolve_config({"model": "m", "batch_size": "50"}, kind="build")
    assert cfg.embedding_batch_size == 50


def test_bool_coercion():
    cfg = resolve_config({"model": "m", "force": "true"}, kind="build")
    assert cfg.force is True
    cfg = resolve_config({"model": "m", "force": False}, kind="build")
    assert cfg.force is False


def test_query_dense_only_requires_model():
    with pytest.raises(ConfigError, match="embedding model"):
        resolve_config({"dense_only": True}, kind="query")


def test_query_sparse_only_needs_no_model():
    cfg = resolve_config({"sparse_only": True}, kind="query")
    assert cfg.sparse_only is True
    assert cfg.embedding_model is None


def test_dense_and_sparse_mutually_exclusive():
    with pytest.raises(ConfigError, match="mutually exclusive"):
        resolve_config({"model": "m", "dense_only": True, "sparse_only": True}, kind="query")
