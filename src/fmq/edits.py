from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass, field
from difflib import unified_diff
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterable, Literal, Optional

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from fmq.errors import EditError
from fmq.types import PacketId

if TYPE_CHECKING:
    from fmq.workspace import Workspace

OpKind = Literal["set", "remove", "rename", "append", "toggle"]


@dataclass(frozen=True)
class EditOp:
    packet_id: PacketId
    kind: OpKind
    args: dict[str, Any]


@dataclass
class FileChange:
    packet_id: PacketId
    abspath: Path
    before: str
    after: str
    error: Optional[str] = None


@dataclass
class ApplyReport:
    written: list[PacketId] = field(default_factory=list)
    skipped: list[PacketId] = field(default_factory=list)
    errors: list[tuple[PacketId, str]] = field(default_factory=list)
    aborted: bool = False


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, (list, CommentedSeq)):
        return "list"
    if isinstance(value, (dict, CommentedMap)):
        return "map"
    return type(value).__name__


def _apply_op(fm: CommentedMap, op: EditOp) -> Optional[str]:
    kind = op.kind
    if kind == "set":
        assignments: dict[str, Any] = op.args["assignments"]
        for field_name, value in assignments.items():
            fm[field_name] = value
        return None

    if kind == "remove":
        fields: list[str] = op.args["fields"]
        for field_name in fields:
            if field_name in fm:
                del fm[field_name]
        return None

    if kind == "rename":
        mapping: dict[str, str] = op.args["mapping"]
        for old, new in mapping.items():
            if old == new:
                continue
            if old not in fm:
                continue
            if new in fm:
                return f"rename target already exists: {new}"
            keys = list(fm)
            index = keys.index(old)
            value = fm[old]
            ca_entry = fm.ca.items.pop(old, None)
            fm.insert(index, new, value)
            if ca_entry is not None:
                fm.ca.items[new] = ca_entry
            del fm[old]
        return None

    if kind == "append":
        assignments = op.args["assignments"]
        for field_name, value in assignments.items():
            if field_name not in fm:
                fm[field_name] = [value]
                continue
            current = fm[field_name]
            if isinstance(current, (list, CommentedSeq)):
                current.append(value)
            else:
                return (
                    f"cannot append to non-list field {field_name!r} "
                    f"(type: {_type_name(current)})"
                )
        return None

    if kind == "toggle":
        fields = op.args["fields"]
        for field_name in fields:
            if field_name not in fm:
                return f"cannot toggle absent field: {field_name!r}"
            current = fm[field_name]
            if not isinstance(current, bool):
                return (
                    f"cannot toggle non-bool field {field_name!r} " f"(type: {_type_name(current)})"
                )
            fm[field_name] = not current
        return None

    raise ValueError(f"unknown op kind: {kind}")


def _apply_ops_to_map(fm: CommentedMap, ops: list[EditOp]) -> Optional[str]:
    """Apply ops in order. Returns the first error message, or None on success.

    On error, does NOT continue — caller decides per-file all-or-nothing.
    """
    for op in ops:
        err = _apply_op(fm, op)
        if err is not None:
            return err
    return None


@dataclass
class EditPlan:
    workspace: "Workspace"
    ops: list[EditOp] = field(default_factory=list)
    _compiled: Optional[list[FileChange]] = field(default=None, init=False, repr=False)

    def compile(self) -> list[FileChange]:
        if self._compiled is not None:
            return self._compiled

        from fmq.parser import serialize_packet

        by_pid: dict[PacketId, list[EditOp]] = {}
        order: list[PacketId] = []
        for op in self.ops:
            if op.packet_id not in by_pid:
                by_pid[op.packet_id] = []
                order.append(op.packet_id)
            by_pid[op.packet_id].append(op)

        changes: list[FileChange] = []
        for pid in order:
            packet = self.workspace.packets.get(pid)
            if packet is None:
                raise EditError(f"packet not in workspace: {pid}")
            with open(packet.abspath, "r", encoding="utf-8", newline="") as f:
                before = f.read()
            pkt_ops = by_pid[pid]
            fm_copy = deepcopy(packet.frontmatter)
            err = _apply_ops_to_map(fm_copy, pkt_ops)
            if err is not None:
                changes.append(
                    FileChange(
                        packet_id=pid,
                        abspath=packet.abspath,
                        before=before,
                        after=before,
                        error=err,
                    )
                )
                continue
            after = serialize_packet(packet, frontmatter=fm_copy)
            changes.append(
                FileChange(
                    packet_id=pid,
                    abspath=packet.abspath,
                    before=before,
                    after=after,
                )
            )

        self._compiled = changes
        return changes

    def preview(self) -> str:
        return self.preview_errors() + self.preview_diff()

    def preview_diff(self) -> str:
        parts: list[str] = []
        for c in self.compile():
            if c.error is not None:
                continue
            if c.before == c.after:
                continue
            diff = unified_diff(
                c.before.splitlines(keepends=True),
                c.after.splitlines(keepends=True),
                fromfile=f"a/{c.packet_id}",
                tofile=f"b/{c.packet_id}",
                n=3,
            )
            parts.extend(diff)
        return "".join(parts)

    def preview_errors(self) -> str:
        parts: list[str] = []
        for c in self.compile():
            if c.error is not None:
                parts.append(f"!! {c.packet_id}: {c.error}\n")
        return "".join(parts)

    def dry_run(self) -> str:
        return self.preview()

    def summary(self) -> str:
        changes = self.compile()
        changed = sum(1 for c in changes if c.error is None and c.before != c.after)
        noop = sum(1 for c in changes if c.error is None and c.before == c.after)
        errored = sum(1 for c in changes if c.error is not None)
        return f"{changed} changed, {errored} skipped (error), {noop} no-op"

    def has_changes(self) -> bool:
        return any(c.error is None and c.before != c.after for c in self.compile())

    def apply(
        self,
        *,
        confirm: bool = True,
        confirm_fn: Optional[Callable[[str], bool]] = None,
        preview_out: Optional[Callable[[str], None]] = None,
    ) -> ApplyReport:
        from fmq.parser import parse_file

        changes = self.compile()
        report = ApplyReport()

        if confirm and self.has_changes():
            if preview_out is not None:
                preview_out(self.preview())
            if confirm_fn is None:
                from fmq.cli.stdin import confirm_prompt

                ok = confirm_prompt()
            else:
                ok = confirm_fn("Apply these changes? [y/N] ")
            if not ok:
                report.aborted = True
                return report

        for c in changes:
            if c.error is not None:
                report.errors.append((c.packet_id, c.error))
                continue
            if c.before == c.after:
                report.skipped.append(c.packet_id)
                continue
            tmp = c.abspath.with_suffix(c.abspath.suffix + ".tmp")
            tmp.write_text(c.after, encoding="utf-8", newline="")
            os.replace(tmp, c.abspath)
            self.workspace.packets[c.packet_id] = parse_file(c.abspath, pid=c.packet_id)
            report.written.append(c.packet_id)

        return report


def _coerce_targets(ws: "Workspace", targets: Iterable[PacketId | str]) -> list[PacketId]:
    result: list[PacketId] = []
    for t in targets:
        if t not in ws.packets:
            raise EditError(f"packet not in workspace: {t}")
        result.append(t)
    return result


def plan_set(ws: "Workspace", targets: Iterable[PacketId], **assignments: Any) -> EditPlan:
    if not assignments:
        raise EditError("set requires at least one field=value assignment")
    pids = _coerce_targets(ws, targets)
    ops = [
        EditOp(packet_id=pid, kind="set", args={"assignments": dict(assignments)}) for pid in pids
    ]
    return EditPlan(workspace=ws, ops=ops)


def plan_remove(ws: "Workspace", targets: Iterable[PacketId], *fields: str) -> EditPlan:
    if not fields:
        raise EditError("remove requires at least one field name")
    pids = _coerce_targets(ws, targets)
    ops = [EditOp(packet_id=pid, kind="remove", args={"fields": list(fields)}) for pid in pids]
    return EditPlan(workspace=ws, ops=ops)


def plan_rename(ws: "Workspace", targets: Iterable[PacketId], **mapping: str) -> EditPlan:
    if not mapping:
        raise EditError("rename requires at least one old=new mapping")
    pids = _coerce_targets(ws, targets)
    ops = [EditOp(packet_id=pid, kind="rename", args={"mapping": dict(mapping)}) for pid in pids]
    return EditPlan(workspace=ws, ops=ops)


def plan_append(ws: "Workspace", targets: Iterable[PacketId], **assignments: Any) -> EditPlan:
    if not assignments:
        raise EditError("append requires at least one field=value assignment")
    pids = _coerce_targets(ws, targets)
    ops = [
        EditOp(packet_id=pid, kind="append", args={"assignments": dict(assignments)})
        for pid in pids
    ]
    return EditPlan(workspace=ws, ops=ops)


def plan_toggle(ws: "Workspace", targets: Iterable[PacketId], *fields: str) -> EditPlan:
    if not fields:
        raise EditError("toggle requires at least one field name")
    pids = _coerce_targets(ws, targets)
    ops = [EditOp(packet_id=pid, kind="toggle", args={"fields": list(fields)}) for pid in pids]
    return EditPlan(workspace=ws, ops=ops)
