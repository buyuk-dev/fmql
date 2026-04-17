from __future__ import annotations

from pathlib import Path

from fmql.workspace import Workspace
from fmql_semantic.textprep import (
    build_document,
    build_rows,
    content_hash,
    pick_frontmatter_field,
)


def _ws(tmp_path: Path, files: dict[str, str]) -> Workspace:
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return Workspace(tmp_path)


def test_pick_first_present_field(tmp_path: Path):
    ws = _ws(
        tmp_path,
        {
            "a.md": "---\ntitle: Hello\nsummary: ignore\n---\nBody.\n",
            "b.md": "---\nsummary: Fallback\n---\nBody.\n",
            "c.md": "---\nname: Last resort\n---\nBody.\n",
            "d.md": "---\n---\nBody.\n",
        },
    )
    field, value = pick_frontmatter_field(ws.packets["a.md"], ("title", "summary", "name"))
    assert (field, value) == ("title", "Hello")
    field, value = pick_frontmatter_field(ws.packets["b.md"], ("title", "summary", "name"))
    assert (field, value) == ("summary", "Fallback")
    field, value = pick_frontmatter_field(ws.packets["c.md"], ("title", "summary", "name"))
    assert (field, value) == ("name", "Last resort")
    field, value = pick_frontmatter_field(ws.packets["d.md"], ("title", "summary", "name"))
    assert (field, value) == (None, None)


def test_build_document_concatenates(tmp_path: Path):
    ws = _ws(tmp_path, {"a.md": "---\ntitle: Hello\n---\nBody text.\n"})
    doc, truncated = build_document(ws.packets["a.md"], ("title",), max_tokens=100)
    assert "Hello" in doc and "Body text." in doc
    assert truncated is False


def test_truncation_flag(tmp_path: Path):
    long_body = "x" * 10_000
    ws = _ws(tmp_path, {"a.md": f"---\ntitle: T\n---\n{long_body}\n"})
    doc, truncated = build_document(ws.packets["a.md"], ("title",), max_tokens=100)
    assert truncated is True
    assert len(doc) <= 100 * 4


def test_hash_stable_across_calls(tmp_path: Path):
    ws = _ws(tmp_path, {"a.md": "---\ntitle: Hello\n---\nBody.\n"})
    h1 = content_hash(ws.packets["a.md"], ("title",), max_tokens=100)
    h2 = content_hash(ws.packets["a.md"], ("title",), max_tokens=100)
    assert h1 == h2


def test_hash_changes_on_body_edit(tmp_path: Path):
    ws1 = _ws(tmp_path, {"a.md": "---\ntitle: Hello\n---\nBody v1.\n"})
    h1 = content_hash(ws1.packets["a.md"], ("title",), max_tokens=100)
    ws2 = _ws(tmp_path, {"a.md": "---\ntitle: Hello\n---\nBody v2.\n"})
    h2 = content_hash(ws2.packets["a.md"], ("title",), max_tokens=100)
    assert h1 != h2


def test_build_rows_warns_once(tmp_path: Path, recwarn):
    long = "x" * 10_000
    ws = _ws(
        tmp_path,
        {
            "a.md": f"---\ntitle: A\n---\n{long}\n",
            "b.md": f"---\ntitle: B\n---\n{long}\n",
        },
    )
    rows = list(build_rows(ws.packets.values(), ("title",), max_tokens=100))
    assert len(rows) == 2
    truncation_warnings = [w for w in recwarn.list if "truncated" in str(w.message)]
    assert len(truncation_warnings) == 1
