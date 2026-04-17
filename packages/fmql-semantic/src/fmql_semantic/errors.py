from __future__ import annotations

from fmql.errors import FmqlError


class ConfigError(FmqlError):
    """Invalid or missing backend configuration (bad option key, missing model, missing dotenv)."""
