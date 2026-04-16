from __future__ import annotations

from pathlib import Path

import pytest

from fmq.workspace import Workspace


def test_scans_all_md(make_workspace):
    ws = make_workspace({
        "a.md": {"frontmatter": {"x": 1}},
        "sub/b.md": {"frontmatter": {"y": 2}},
    })
    assert set(ws.packets.keys()) == {"a.md", "sub/b.md"}


def test_packet_id_is_posix_relative(make_workspace):
    ws = make_workspace({
        "nested/dir/deep.md": {"frontmatter": {"x": 1}},
    })
    assert "nested/dir/deep.md" in ws.packets


def test_skips_non_matching_glob(tmp_path: Path):
    (tmp_path / "a.md").write_text("---\nx: 1\n---\nbody\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("not markdown\n", encoding="utf-8")
    ws = Workspace(tmp_path)
    assert list(ws.packets.keys()) == ["a.md"]


def test_bad_yaml_skipped_with_warning(tmp_path: Path):
    (tmp_path / "good.md").write_text("---\nx: 1\n---\n", encoding="utf-8")
    (tmp_path / "bad.md").write_text("---\nx: :\n---\n", encoding="utf-8")
    with pytest.warns(UserWarning):
        ws = Workspace(tmp_path)
    assert "good.md" in ws.packets
    assert "bad.md" not in ws.packets


def test_no_frontmatter_file_still_indexed(make_workspace):
    ws = make_workspace({
        "plain.md": {"frontmatter": None, "body": "hi\n"},
    })
    assert "plain.md" in ws.packets
    assert ws.packets["plain.md"].has_frontmatter is False


def test_rescan(make_workspace, tmp_path: Path):
    ws = make_workspace({"a.md": {"frontmatter": {"x": 1}}})
    new = ws.root / "b.md"
    new.write_text("---\ny: 2\n---\n", encoding="utf-8")
    assert "b.md" not in ws.packets
    ws.rescan()
    assert "b.md" in ws.packets


def test_missing_root_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        Workspace(tmp_path / "does-not-exist")
