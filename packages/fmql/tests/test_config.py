from __future__ import annotations

from pathlib import Path

import pytest

from fmql.config import (
    build_resolvers_from_config,
    load_workspace_config,
    read_diagnose_flag,
)
from fmql.errors import FmqlError
from fmql.resolvers import (
    IdResolver,
    RelativePathResolver,
    SlugResolver,
    UuidResolver,
)
from fmql.workspace import Workspace


def _write_workspace_md(root: Path, body: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "WORKSPACE.md").write_text(body, encoding="utf-8")


def test_load_returns_empty_when_workspace_md_missing(tmp_path):
    assert load_workspace_config(tmp_path) == {}


def test_load_returns_empty_when_no_fmql_key(tmp_path):
    _write_workspace_md(tmp_path, "---\ntitle: My Workspace\n---\n# hello\n")
    assert load_workspace_config(tmp_path) == {}


def test_load_returns_fmql_block(tmp_path):
    _write_workspace_md(
        tmp_path,
        "---\nfmql:\n  resolvers:\n    depends_on: id\n---\n",
    )
    cfg = load_workspace_config(tmp_path)
    assert cfg == {"resolvers": {"depends_on": "id"}}


def test_build_resolvers_empty():
    assert build_resolvers_from_config({}) == ({}, None)


def test_build_resolvers_per_field():
    cfg = {"resolvers": {"depends_on": "id", "supersedes": "slug"}}
    resolvers, default = build_resolvers_from_config(cfg)
    assert isinstance(resolvers["depends_on"], IdResolver)
    assert isinstance(resolvers["supersedes"], SlugResolver)
    assert default is None


def test_build_resolvers_default_only():
    resolvers, default = build_resolvers_from_config({"default_resolver": "uuid"})
    assert resolvers == {}
    assert isinstance(default, UuidResolver)


def test_build_resolvers_unknown_name_raises():
    with pytest.raises(FmqlError):
        build_resolvers_from_config({"resolvers": {"x": "bogus"}})


def test_workspace_picks_up_per_field_from_workspace_md(tmp_path):
    _write_workspace_md(
        tmp_path,
        "---\nfmql:\n  resolvers:\n    depends_on: id\n---\n",
    )
    ws = Workspace(tmp_path)
    assert isinstance(ws.resolvers["depends_on"], IdResolver)
    assert isinstance(ws.default_resolver, RelativePathResolver)


def test_workspace_picks_up_default_from_workspace_md(tmp_path):
    _write_workspace_md(
        tmp_path,
        "---\nfmql:\n  default_resolver: uuid\n---\n",
    )
    ws = Workspace(tmp_path)
    assert isinstance(ws.default_resolver, UuidResolver)


def test_workspace_kwarg_overrides_config(tmp_path):
    _write_workspace_md(
        tmp_path,
        "---\nfmql:\n  resolvers:\n    depends_on: id\n---\n",
    )
    ws = Workspace(tmp_path, resolvers={"depends_on": SlugResolver()})
    assert isinstance(ws.resolvers["depends_on"], SlugResolver)


def test_workspace_kwarg_default_overrides_config(tmp_path):
    _write_workspace_md(
        tmp_path,
        "---\nfmql:\n  default_resolver: uuid\n---\n",
    )
    ws = Workspace(tmp_path, default_resolver=SlugResolver())
    assert isinstance(ws.default_resolver, SlugResolver)


def test_workspace_unknown_resolver_in_config_raises(tmp_path):
    _write_workspace_md(
        tmp_path,
        "---\nfmql:\n  resolvers:\n    depends_on: bogus\n---\n",
    )
    with pytest.raises(FmqlError):
        Workspace(tmp_path)


def test_workspace_md_without_frontmatter_is_ignored(tmp_path):
    _write_workspace_md(tmp_path, "# just a heading\n")
    ws = Workspace(tmp_path)
    assert ws.resolvers == {}
    assert isinstance(ws.default_resolver, RelativePathResolver)


def test_read_diagnose_flag_default_false():
    assert read_diagnose_flag({}) is False


def test_read_diagnose_flag_true():
    assert read_diagnose_flag({"diagnose": True}) is True


def test_read_diagnose_flag_false():
    assert read_diagnose_flag({"diagnose": False}) is False


def test_read_diagnose_flag_non_bool_raises():
    with pytest.raises(FmqlError):
        read_diagnose_flag({"diagnose": "yes"})
    with pytest.raises(FmqlError):
        read_diagnose_flag({"diagnose": 1})


def test_workspace_diagnose_default_absent_is_false(tmp_path):
    ws = Workspace(tmp_path)
    assert ws.diagnose_default is False


def test_workspace_diagnose_default_via_workspace_md(tmp_path):
    _write_workspace_md(tmp_path, "---\nfmql:\n  diagnose: true\n---\n")
    ws = Workspace(tmp_path)
    assert ws.diagnose_default is True


def test_workspace_diagnose_invalid_value_raises(tmp_path):
    _write_workspace_md(tmp_path, '---\nfmql:\n  diagnose: "yes"\n---\n')
    with pytest.raises(FmqlError):
        Workspace(tmp_path)
