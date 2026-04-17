from __future__ import annotations

from fmql.errors import FmqlError


class BackendNotFoundError(FmqlError):
    """Requested backend is not installed / not registered via entry points."""


class BackendUnavailableError(FmqlError):
    """Backend is installed but cannot be used (missing deps, missing config)."""


class IndexVersionError(FmqlError):
    """On-disk index format is incompatible with the current backend version."""


class BackendKindError(FmqlError):
    """Backend kind mismatch (e.g. build on scan backend, indexed backend without location)."""
