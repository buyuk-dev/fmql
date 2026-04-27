from __future__ import annotations

import pytest

from fmql.errors import FmqlError
from fmql.resolvers import (
    IdResolver,
    RelativePathResolver,
    SlugResolver,
    UuidResolver,
    resolver_by_name,
)


def test_relative_path_resolver_hit(paths_refs_ws):
    r = RelativePathResolver()
    tgt = r.resolve("b.md", origin="tasks/a.md", workspace=paths_refs_ws)
    assert tgt == "tasks/b.md"


def test_relative_path_resolver_parent_hop(paths_refs_ws):
    r = RelativePathResolver()
    tgt = r.resolve("../shared/c.md", origin="tasks/b.md", workspace=paths_refs_ws)
    assert tgt == "shared/c.md"


def test_relative_path_resolver_miss(paths_refs_ws):
    r = RelativePathResolver()
    assert r.resolve("no-such.md", origin="tasks/a.md", workspace=paths_refs_ws) is None


def test_relative_path_resolver_non_string(paths_refs_ws):
    r = RelativePathResolver()
    assert r.resolve(42, origin="tasks/a.md", workspace=paths_refs_ws) is None
    assert r.resolve(None, origin="tasks/a.md", workspace=paths_refs_ws) is None
    assert r.resolve(["b.md"], origin="tasks/a.md", workspace=paths_refs_ws) is None


def test_relative_path_resolver_outside_workspace(paths_refs_ws):
    r = RelativePathResolver()
    assert r.resolve("../../etc/passwd", origin="tasks/a.md", workspace=paths_refs_ws) is None


def test_uuid_resolver_hit(project_pm_ws):
    r = UuidResolver()
    tgt = r.resolve("task-1", origin="tasks/task-3.md", workspace=project_pm_ws)
    assert tgt == "tasks/task-1.md"


def test_uuid_resolver_miss(project_pm_ws):
    r = UuidResolver()
    assert r.resolve("nope", origin="tasks/task-3.md", workspace=project_pm_ws) is None


def test_uuid_resolver_non_string(project_pm_ws):
    r = UuidResolver()
    assert r.resolve(123, origin="tasks/task-3.md", workspace=project_pm_ws) is None


def test_uuid_resolver_index_cached(project_pm_ws):
    r = UuidResolver()
    calls = {"n": 0}
    original = project_pm_ws.index_by_field

    def counting_index(field: str):
        calls["n"] += 1
        return original(field)

    project_pm_ws.index_by_field = counting_index  # type: ignore[method-assign]
    r.resolve("task-1", origin="tasks/task-3.md", workspace=project_pm_ws)
    r.resolve("task-2", origin="tasks/task-3.md", workspace=project_pm_ws)
    r.resolve("task-3", origin="tasks/task-3.md", workspace=project_pm_ws)
    assert calls["n"] == 3  # index_by_field called per resolve — internal cache inside it


def test_index_by_field_is_cached(project_pm_ws):
    idx1 = project_pm_ws.index_by_field("uuid")
    idx2 = project_pm_ws.index_by_field("uuid")
    assert idx1 is idx2


def test_slug_resolver_slug_field(make_workspace):
    ws = make_workspace(
        {
            "a.md": {"frontmatter": {"slug": "alpha"}},
            "b.md": {"frontmatter": {"slug": "beta"}},
        }
    )
    r = SlugResolver()
    assert r.resolve("alpha", origin="a.md", workspace=ws) == "a.md"
    assert r.resolve("beta", origin="a.md", workspace=ws) == "b.md"


def test_slug_resolver_stem_fallback(make_workspace):
    ws = make_workspace(
        {
            "notes/alpha.md": {"frontmatter": {"title": "Alpha"}},
            "notes/beta.md": {"frontmatter": {"title": "Beta"}},
        }
    )
    r = SlugResolver()
    # No slug field at all — fall back to file stem.
    assert r.resolve("alpha", origin="notes/beta.md", workspace=ws) == "notes/alpha.md"


def test_slug_resolver_miss(make_workspace):
    ws = make_workspace({"a.md": {"frontmatter": {"slug": "alpha"}}})
    r = SlugResolver()
    assert r.resolve("zeta", origin="a.md", workspace=ws) is None


def test_resolver_by_name_known():
    assert isinstance(resolver_by_name("path"), RelativePathResolver)
    assert isinstance(resolver_by_name("uuid"), UuidResolver)
    assert isinstance(resolver_by_name("slug"), SlugResolver)
    assert isinstance(resolver_by_name("id"), IdResolver)


def test_resolver_by_name_unknown():
    with pytest.raises(FmqlError):
        resolver_by_name("bogus")


def test_id_resolver_int_value(make_workspace):
    ws = make_workspace(
        {
            "a.md": {"frontmatter": {"id": 1}, "body": ""},
            "b.md": {"frontmatter": {"id": 17}, "body": ""},
        }
    )
    r = IdResolver()
    assert r.resolve(1, origin="b.md", workspace=ws) == "a.md"
    assert r.resolve(17, origin="a.md", workspace=ws) == "b.md"


def test_id_resolver_str_matches_int_id(make_workspace):
    ws = make_workspace({"a.md": {"frontmatter": {"id": 17}, "body": ""}})
    r = IdResolver()
    assert r.resolve("17", origin="a.md", workspace=ws) == "a.md"


def test_id_resolver_int_matches_str_id(make_workspace):
    ws = make_workspace({"a.md": {"frontmatter": {"id": "17"}, "body": ""}})
    r = IdResolver()
    assert r.resolve(17, origin="a.md", workspace=ws) == "a.md"


def test_id_resolver_string_with_leading_zero_only_matches_quoted(make_workspace):
    ws = make_workspace(
        {
            "a.md": {"frontmatter": {"id": "017"}, "body": ""},
            "b.md": {"frontmatter": {"id": 17}, "body": ""},
        }
    )
    r = IdResolver()
    assert r.resolve("017", origin="b.md", workspace=ws) == "a.md"
    assert r.resolve(17, origin="a.md", workspace=ws) == "b.md"


def test_id_resolver_rejects_collections_and_bool(make_workspace):
    ws = make_workspace({"a.md": {"frontmatter": {"id": 1}, "body": ""}})
    r = IdResolver()
    assert r.resolve(None, origin="a.md", workspace=ws) is None
    assert r.resolve(True, origin="a.md", workspace=ws) is None
    assert r.resolve([1], origin="a.md", workspace=ws) is None
    assert r.resolve({"id": 1}, origin="a.md", workspace=ws) is None


def test_id_resolver_custom_field(make_workspace):
    ws = make_workspace({"a.md": {"frontmatter": {"ticket_id": 42}, "body": ""}})
    r = IdResolver(field="ticket_id")
    assert r.resolve(42, origin="a.md", workspace=ws) == "a.md"
