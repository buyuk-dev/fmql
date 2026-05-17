"""Wikilink parsing and resolution for Obsidian-shaped vaults.

Two surface shapes:

- Body wikilinks: ``[[Note]]`` and ``[[Note|alias]]`` substrings in a packet body.
- Frontmatter values: a scalar that is wholly ``[[X]]`` (possibly inside a list).

Both share the same target syntax (alias after ``|`` ignored for resolution;
``#heading`` and ``^block-id`` fragments stripped — resolution is to the file).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any, Optional

from fmql.types import PacketId

if TYPE_CHECKING:
    from fmql.workspace import Workspace

_INNER = r"([^\]|]+)(?:\|[^\]]*)?"
BODY_WIKILINK_RE = re.compile(rf"(?<!!)\[\[{_INNER}\]\]")
WHOLE_VALUE_WIKILINK_RE = re.compile(rf"^\s*\[\[{_INNER}\]\]\s*$")

MENTIONS_FIELD = "mentions"


@dataclass(frozen=True)
class WikilinkTarget:
    raw: str
    target: str


@dataclass(frozen=True)
class WikilinkResolution:
    target: Optional[PacketId]
    candidates: tuple[PacketId, ...]


def _normalize_target(raw: str) -> str:
    target = raw.split("#", 1)[0].split("^", 1)[0]
    return target.strip()


def _from_match(raw_inner: str) -> WikilinkTarget:
    return WikilinkTarget(raw=raw_inner, target=_normalize_target(raw_inner))


def parse_body_wikilinks(body: str) -> list[WikilinkTarget]:
    """Extract every ``[[X]]`` / ``[[X|alias]]`` from a body string.

    Skips ``![[X]]`` embeds (Obsidian's render-the-content-here syntax — not a
    graph edge for v1). Empty-target matches are dropped.
    """
    out: list[WikilinkTarget] = []
    for m in BODY_WIKILINK_RE.finditer(body):
        link = _from_match(m.group(1))
        if link.target:
            out.append(link)
    return out


def match_whole_value_wikilink(value: Any) -> Optional[WikilinkTarget]:
    """Return a ``WikilinkTarget`` iff ``value`` is a string wholly wrapped in ``[[]]``."""
    if not isinstance(value, str):
        return None
    m = WHOLE_VALUE_WIKILINK_RE.match(value)
    if m is None:
        return None
    link = _from_match(m.group(1))
    return link if link.target else None


def resolve_wikilink(link: WikilinkTarget, workspace: "Workspace") -> WikilinkResolution:
    """Resolve a wikilink to a packet id.

    Path-form (contains ``/``): workspace-relative path lookup; ``.md`` is
    appended if absent. Basename-form: lookup via ``workspace.index_by_stem()``,
    with alphabetical-by-path tiebreak when more than one packet shares the
    basename. Returns a resolution carrying both the chosen target and the full
    candidate list (used by diagnostics).
    """
    target = link.target
    if not target:
        return WikilinkResolution(target=None, candidates=())

    if "/" in target:
        normalized = PurePosixPath(target).as_posix()
        candidates: list[PacketId] = []
        for candidate in (normalized, normalized + ".md"):
            if candidate in workspace.packets and candidate not in candidates:
                candidates.append(candidate)
        if not candidates:
            return WikilinkResolution(target=None, candidates=())
        return WikilinkResolution(target=candidates[0], candidates=tuple(candidates))

    stems = workspace.index_by_stem().get(target, [])
    if not stems:
        return WikilinkResolution(target=None, candidates=())
    ordered = tuple(sorted(stems))
    return WikilinkResolution(target=ordered[0], candidates=ordered)
