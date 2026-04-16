from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Callable

import pytest
from ruamel.yaml import YAML

from fmq.workspace import Workspace

_YAML = YAML(typ="rt", pure=True)
_YAML.default_flow_style = False


def _dump_yaml(data: dict[str, Any]) -> str:
    buf = io.StringIO()
    _YAML.dump(data, buf)
    return buf.getvalue()


def _write_packet(path: Path, frontmatter: dict[str, Any] | None, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    parts: list[str] = []
    if frontmatter is not None:
        parts.append("---\n")
        parts.append(_dump_yaml(frontmatter))
        parts.append("---\n")
    parts.append(body)
    path.write_text("".join(parts), encoding="utf-8")


@pytest.fixture
def make_workspace(tmp_path: Path) -> Callable[[dict[str, Any]], Workspace]:
    def _factory(spec: dict[str, Any]) -> Workspace:
        root = tmp_path / "ws"
        root.mkdir(exist_ok=True)
        for rel, entry in spec.items():
            p = root / rel
            if isinstance(entry, dict) and set(entry.keys()) <= {"frontmatter", "body"}:
                _write_packet(p, entry.get("frontmatter"), entry.get("body", ""))
            else:
                _write_packet(p, entry)
        return Workspace(root)

    return _factory


@pytest.fixture
def project_pm_ws(make_workspace) -> Workspace:
    from datetime import date

    spec: dict[str, Any] = {
        "tasks/task-1.md": {
            "frontmatter": {
                "uuid": "task-1",
                "type": "task",
                "status": "active",
                "priority": 3,
                "in_sprint": "sprint-3",
                "due_date": date(2026, 4, 10),
                "tags": ["backend"],
            },
            "body": "task 1 body\n",
        },
        "tasks/task-2.md": {
            "frontmatter": {
                "uuid": "task-2",
                "type": "task",
                "status": "done",
                "priority": 1,
                "in_sprint": "sprint-3",
                "due_date": date(2026, 4, 20),
                "tags": ["frontend"],
            },
            "body": "task 2 body\n",
        },
        "tasks/task-3.md": {
            "frontmatter": {
                "uuid": "task-3",
                "type": "task",
                "status": "active",
                "priority": 5,
                "in_sprint": "sprint-4",
                "due_date": date(2026, 5, 1),
                "blocked_by": "task-1",
                "tags": ["backend", "urgent"],
            },
            "body": "task 3 body\n",
        },
        "epics/epic-1.md": {
            "frontmatter": {
                "uuid": "epic-1",
                "type": "epic",
                "status": "active",
                "priority": "high",
            },
            "body": "epic 1 body\n",
        },
        "notes/readme.md": {
            "frontmatter": None,
            "body": "plain markdown with no frontmatter\n",
        },
    }
    return make_workspace(spec)
