from __future__ import annotations

from enum import Enum
from typing import Any, Callable

Payload = dict[str, Any]


class SubgraphFormat(str, Enum):
    raw = "raw"
    cytoscape = "cytoscape"


def _raw(payload: Payload) -> Payload:
    return payload


def _cytoscape(payload: Payload) -> Payload:
    nodes = [{"data": n} for n in payload["nodes"]]
    edges = [
        {"data": {**e, "id": f"{e['source']}__{e['field']}__{e['target']}"}}
        for e in payload["edges"]
    ]
    return {"elements": {"nodes": nodes, "edges": edges}}


FORMATTERS: dict[SubgraphFormat, Callable[[Payload], Payload]] = {
    SubgraphFormat.raw: _raw,
    SubgraphFormat.cytoscape: _cytoscape,
}


def format_subgraph(payload: Payload, fmt: SubgraphFormat) -> Payload:
    return FORMATTERS[fmt](payload)
