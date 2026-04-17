"""fmql search-backend plugin API.

Third-party packages register backends via the `fmql.search_index` entry-point group
and implement the `ScanSearch` or `IndexedSearch` Protocol from this package.
"""

from fmql.search.errors import (
    BackendKindError,
    BackendNotFoundError,
    BackendUnavailableError,
    IndexVersionError,
)
from fmql.search.protocol import IndexedSearch, ScanSearch
from fmql.search.registry import (
    clear_cache,
    discover_backends,
    get_backend,
    is_indexed,
    is_scan,
)
from fmql.search.types import BackendInfo, IndexStats, SearchHit

__all__ = [
    "BackendInfo",
    "BackendKindError",
    "BackendNotFoundError",
    "BackendUnavailableError",
    "IndexStats",
    "IndexVersionError",
    "IndexedSearch",
    "ScanSearch",
    "SearchHit",
    "clear_cache",
    "discover_backends",
    "get_backend",
    "is_indexed",
    "is_scan",
]
