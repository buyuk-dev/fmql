from __future__ import annotations

import sys
from importlib.metadata import entry_points
from typing import Union

from fmql.search.errors import BackendNotFoundError
from fmql.search.protocol import IndexedSearch, ScanSearch

ENTRY_POINT_GROUP = "fmql.search_index"

Backend = Union[ScanSearch, IndexedSearch]

_cache: dict[str, type] | None = None


def discover_backends() -> dict[str, type]:
    """Return {name: backend_class} discovered via the fmql.search_index entry-point group.

    A plugin whose import fails logs a one-line warning to stderr and is skipped.
    """
    global _cache
    if _cache is not None:
        return _cache
    backends: dict[str, type] = {}
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        try:
            backends[ep.name] = ep.load()
        except Exception as e:
            print(
                f"fmql: failed to load search backend {ep.name!r} from {ep.value!r}: {e}",
                file=sys.stderr,
            )
    _cache = backends
    return backends


def get_backend(name: str) -> Backend:
    """Instantiate and return the backend registered under `name`."""
    backends = discover_backends()
    if name not in backends:
        available = ", ".join(sorted(backends)) or "(none)"
        raise BackendNotFoundError(f"Unknown backend: {name!r}. Available: {available}.")
    return backends[name]()


def clear_cache() -> None:
    """Clear the discovery cache. Intended for tests."""
    global _cache
    _cache = None


def is_indexed(backend: Backend) -> bool:
    """Return True iff `backend` implements IndexedSearch (has a build step)."""
    return hasattr(backend, "build") and hasattr(backend, "parse_location")


def is_scan(backend: Backend) -> bool:
    """Return True iff `backend` is a ScanSearch (no build step)."""
    return not is_indexed(backend)
