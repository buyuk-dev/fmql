from __future__ import annotations

from pathlib import Path
from typing import Optional

from fmql.errors import FmqlError
from fmql.parser import parse_file
from fmql.resolvers import resolver_by_name
from fmql.types import Resolver

WORKSPACE_FILE = "WORKSPACE.md"
FMQL_KEY = "fmql"
DIAGNOSE_KEY = "diagnose"


def load_workspace_config(root: Path) -> dict:
    """Return the ``fmql:`` block from ``<root>/WORKSPACE.md``.

    Returns ``{}`` if the file is absent, has no frontmatter, or has no ``fmql`` key.
    """
    path = root / WORKSPACE_FILE
    if not path.is_file():
        return {}
    packet = parse_file(path, pid=WORKSPACE_FILE)
    cfg = packet.as_plain().get(FMQL_KEY)
    return dict(cfg) if isinstance(cfg, dict) else {}


def build_resolvers_from_config(
    cfg: dict,
) -> tuple[dict[str, Resolver], Optional[Resolver]]:
    """Translate a config dict into a per-field resolver map and optional default."""
    raw_resolvers = cfg.get("resolvers") or {}
    if not isinstance(raw_resolvers, dict):
        raw_resolvers = {}
    resolvers: dict[str, Resolver] = {
        str(field): resolver_by_name(str(name)) for field, name in raw_resolvers.items()
    }
    default: Optional[Resolver] = None
    if "default_resolver" in cfg:
        default = resolver_by_name(str(cfg["default_resolver"]))
    return resolvers, default


def read_diagnose_flag(cfg: dict) -> bool:
    if DIAGNOSE_KEY not in cfg:
        return False
    value = cfg[DIAGNOSE_KEY]
    if not isinstance(value, bool):
        raise FmqlError(
            f"WORKSPACE.md: fmql.{DIAGNOSE_KEY} must be a boolean, got {type(value).__name__}"
        )
    return value
