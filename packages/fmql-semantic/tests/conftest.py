from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from fmql_semantic.storage.connection import probe_extension_support  # noqa: E402

if not probe_extension_support():
    import pytest as _pytest  # noqa

    _pytest.skip(
        "Python build lacks sqlite3 loadable extensions or sqlite-vec is not importable. "
        "Install via uv/pyenv/python.org.",
        allow_module_level=True,
    )

from fakes.provider import fake_aembedding, fake_arerank  # noqa: E402


@pytest.fixture(autouse=True)
def patch_litellm(monkeypatch):
    import litellm  # type: ignore

    monkeypatch.setattr(litellm, "aembedding", fake_aembedding, raising=False)
    monkeypatch.setattr(litellm, "arerank", fake_arerank, raising=False)
    yield


@pytest.fixture
def tmp_location(tmp_path: Path) -> str:
    return str(tmp_path / "index.db")


@pytest.fixture
def ws_root(tmp_path: Path) -> Path:
    d = tmp_path / "ws"
    d.mkdir()
    return d


@pytest.fixture
def embed_model_env(monkeypatch):
    monkeypatch.setenv("FMQL_EMBEDDING_MODEL", "fake/embed")
