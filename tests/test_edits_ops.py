from __future__ import annotations

import io

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from fm.edits import EditOp, _apply_ops_to_map


def _load(text: str) -> CommentedMap:
    yaml = YAML(typ="rt", pure=True)
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    data = yaml.load(text)
    if data is None:
        return CommentedMap()
    assert isinstance(data, CommentedMap)
    return data


def _dump(data: CommentedMap) -> str:
    yaml = YAML(typ="rt", pure=True)
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    buf = io.StringIO()
    yaml.dump(data, buf)
    return buf.getvalue()


def _op(kind, **args) -> EditOp:
    return EditOp(packet_id="x.md", kind=kind, args=args)


# ----- set -----


def test_set_new_key_appends_at_end() -> None:
    fm = _load("a: 1\nb: 2\n")
    err = _apply_ops_to_map(fm, [_op("set", assignments={"c": 3})])
    assert err is None
    assert list(fm) == ["a", "b", "c"]
    assert fm["c"] == 3


def test_set_existing_key_preserves_position() -> None:
    fm = _load("a: 1\nb: 2\nc: 3\n")
    err = _apply_ops_to_map(fm, [_op("set", assignments={"b": 99})])
    assert err is None
    assert list(fm) == ["a", "b", "c"]
    assert fm["b"] == 99


def test_set_multiple_in_one_op() -> None:
    fm = _load("a: 1\n")
    err = _apply_ops_to_map(fm, [_op("set", assignments={"a": 2, "b": 3})])
    assert err is None
    assert fm["a"] == 2
    assert fm["b"] == 3


def test_set_on_empty_map() -> None:
    fm = CommentedMap()
    err = _apply_ops_to_map(fm, [_op("set", assignments={"a": 1})])
    assert err is None
    assert fm["a"] == 1


# ----- remove -----


def test_remove_present_key() -> None:
    fm = _load("a: 1\nb: 2\n")
    err = _apply_ops_to_map(fm, [_op("remove", fields=["a"])])
    assert err is None
    assert list(fm) == ["b"]


def test_remove_absent_key_is_noop() -> None:
    fm = _load("a: 1\n")
    err = _apply_ops_to_map(fm, [_op("remove", fields=["missing"])])
    assert err is None
    assert list(fm) == ["a"]


def test_remove_multiple_fields() -> None:
    fm = _load("a: 1\nb: 2\nc: 3\n")
    err = _apply_ops_to_map(fm, [_op("remove", fields=["a", "c"])])
    assert err is None
    assert list(fm) == ["b"]


# ----- rename -----


def test_rename_preserves_position_in_middle() -> None:
    fm = _load("a: 1\nb: 2\nc: 3\n")
    err = _apply_ops_to_map(fm, [_op("rename", mapping={"b": "bb"})])
    assert err is None
    assert list(fm) == ["a", "bb", "c"]
    assert fm["bb"] == 2


def test_rename_preserves_position_at_top() -> None:
    fm = _load("a: 1\nb: 2\n")
    err = _apply_ops_to_map(fm, [_op("rename", mapping={"a": "aa"})])
    assert err is None
    assert list(fm) == ["aa", "b"]


def test_rename_preserves_position_at_end() -> None:
    fm = _load("a: 1\nb: 2\n")
    err = _apply_ops_to_map(fm, [_op("rename", mapping={"b": "bb"})])
    assert err is None
    assert list(fm) == ["a", "bb"]


def test_rename_identity_is_noop() -> None:
    fm = _load("a: 1\n")
    err = _apply_ops_to_map(fm, [_op("rename", mapping={"a": "a"})])
    assert err is None
    assert list(fm) == ["a"]


def test_rename_absent_is_noop() -> None:
    fm = _load("a: 1\n")
    err = _apply_ops_to_map(fm, [_op("rename", mapping={"missing": "x"})])
    assert err is None
    assert list(fm) == ["a"]


def test_rename_to_existing_errors() -> None:
    fm = _load("a: 1\nb: 2\n")
    err = _apply_ops_to_map(fm, [_op("rename", mapping={"a": "b"})])
    assert err is not None
    assert "already exists" in err
    assert list(fm) == ["a", "b"]
    assert fm["a"] == 1


def test_rename_preserves_inline_comment() -> None:
    fm = _load("a: 1\nb: 2 # keep me\nc: 3\n")
    err = _apply_ops_to_map(fm, [_op("rename", mapping={"b": "bb"})])
    assert err is None
    assert list(fm) == ["a", "bb", "c"]
    dumped = _dump(fm)
    assert "keep me" in dumped


# ----- append -----


def test_append_to_block_list() -> None:
    fm = _load("tags:\n  - a\n  - b\n")
    err = _apply_ops_to_map(fm, [_op("append", assignments={"tags": "c"})])
    assert err is None
    assert list(fm["tags"]) == ["a", "b", "c"]


def test_append_to_flow_list_preserves_flow_style() -> None:
    fm = _load("tags: [a, b]\n")
    err = _apply_ops_to_map(fm, [_op("append", assignments={"tags": "c"})])
    assert err is None
    dumped = _dump(fm)
    assert "[a, b, c]" in dumped


def test_append_creates_list_if_absent() -> None:
    fm = _load("a: 1\n")
    err = _apply_ops_to_map(fm, [_op("append", assignments={"tags": "x"})])
    assert err is None
    assert list(fm["tags"]) == ["x"]


def test_append_to_scalar_errors() -> None:
    fm = _load("tags: urgent\n")
    err = _apply_ops_to_map(fm, [_op("append", assignments={"tags": "x"})])
    assert err is not None
    assert "cannot append" in err
    assert fm["tags"] == "urgent"


def test_append_to_map_errors() -> None:
    fm = _load("meta:\n  a: 1\n")
    err = _apply_ops_to_map(fm, [_op("append", assignments={"meta": "x"})])
    assert err is not None
    assert "cannot append" in err


# ----- toggle -----


def test_toggle_true_to_false() -> None:
    fm = _load("flagged: true\n")
    err = _apply_ops_to_map(fm, [_op("toggle", fields=["flagged"])])
    assert err is None
    assert fm["flagged"] is False


def test_toggle_false_to_true() -> None:
    fm = _load("flagged: false\n")
    err = _apply_ops_to_map(fm, [_op("toggle", fields=["flagged"])])
    assert err is None
    assert fm["flagged"] is True


def test_toggle_absent_errors() -> None:
    fm = _load("a: 1\n")
    err = _apply_ops_to_map(fm, [_op("toggle", fields=["missing"])])
    assert err is not None
    assert "absent" in err


def test_toggle_non_bool_errors() -> None:
    fm = _load("status: active\n")
    err = _apply_ops_to_map(fm, [_op("toggle", fields=["status"])])
    assert err is not None
    assert "non-bool" in err
    assert fm["status"] == "active"


# ----- multi-op within a packet -----


def test_multi_op_stops_on_first_error() -> None:
    fm = _load("a: 1\ntags: urgent\n")
    ops = [
        _op("set", assignments={"a": 99}),
        _op("append", assignments={"tags": "x"}),
    ]
    err = _apply_ops_to_map(fm, ops)
    assert err is not None
    # `a` was already set before the error — caller must discard this map.
    assert fm["a"] == 99
