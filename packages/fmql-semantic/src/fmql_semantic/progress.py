from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import Iterator, Optional


class _NoopBar:
    def update(self, n: int = 1) -> None:
        pass

    def close(self) -> None:
        pass


@contextmanager
def progress(total: int, *, desc: str = "") -> Iterator[object]:
    """tqdm-backed progress bar on stderr TTYs, no-op otherwise. tqdm is an optional dep."""
    bar: Optional[object] = None
    if total > 0 and sys.stderr.isatty():
        try:
            from tqdm import tqdm  # type: ignore

            bar = tqdm(total=total, desc=desc, unit="pkt", file=sys.stderr, leave=False)
        except ImportError:
            bar = None
    if bar is None:
        bar = _NoopBar()
    try:
        yield bar
    finally:
        bar.close()
