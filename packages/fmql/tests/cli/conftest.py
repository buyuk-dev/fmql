from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest


@pytest.fixture
def write_blocked_ws() -> Callable[[Path], None]:
    """Return a writer for the canonical 3-packet blocked-by chain used across CLI tests.

    Layout: a (uuid=a) ← b (uuid=b, blocked_by=a) ← c (uuid=c, blocked_by=b).
    """

    def _write(root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / "a.md").write_text("---\nuuid: a\n---\nA\n", encoding="utf-8")
        (root / "b.md").write_text("---\nuuid: b\nblocked_by: a\n---\nB\n", encoding="utf-8")
        (root / "c.md").write_text("---\nuuid: c\nblocked_by: b\n---\nC\n", encoding="utf-8")

    return _write
