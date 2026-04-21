from __future__ import annotations

from fmql.subgraph_formats import SubgraphFormat, format_subgraph


def _sample() -> dict:
    return {
        "nodes": [
            {"id": "a.md", "frontmatter": {"title": "A"}},
            {"id": "b.md", "frontmatter": {"title": "B", "blocked_by": "a"}},
        ],
        "edges": [
            {"source": "b.md", "target": "a.md", "field": "blocked_by"},
        ],
    }


def test_raw_is_identity():
    payload = _sample()
    assert format_subgraph(payload, SubgraphFormat.raw) is payload


def test_cytoscape_wraps_nodes_in_data():
    payload = _sample()
    out = format_subgraph(payload, SubgraphFormat.cytoscape)
    assert out == {
        "elements": {
            "nodes": [
                {"data": {"id": "a.md", "frontmatter": {"title": "A"}}},
                {"data": {"id": "b.md", "frontmatter": {"title": "B", "blocked_by": "a"}}},
            ],
            "edges": [
                {
                    "data": {
                        "id": "b.md__blocked_by__a.md",
                        "source": "b.md",
                        "target": "a.md",
                        "field": "blocked_by",
                    }
                }
            ],
        }
    }


def test_cytoscape_with_ids_only_nodes():
    payload = {
        "nodes": [{"id": "a.md"}, {"id": "b.md"}],
        "edges": [{"source": "b.md", "target": "a.md", "field": "blocked_by"}],
    }
    out = format_subgraph(payload, SubgraphFormat.cytoscape)
    assert out["elements"]["nodes"] == [
        {"data": {"id": "a.md"}},
        {"data": {"id": "b.md"}},
    ]


def test_cytoscape_synthesizes_edge_ids():
    payload = {
        "nodes": [{"id": "x"}, {"id": "y"}],
        "edges": [
            {"source": "x", "target": "y", "field": "ref"},
            {"source": "x", "target": "y", "field": "other"},
        ],
    }
    out = format_subgraph(payload, SubgraphFormat.cytoscape)
    ids = [e["data"]["id"] for e in out["elements"]["edges"]]
    assert ids == ["x__ref__y", "x__other__y"]


def test_empty_payload_roundtrips_in_both_formats():
    empty = {"nodes": [], "edges": []}
    assert format_subgraph(empty, SubgraphFormat.raw) == empty
    assert format_subgraph(empty, SubgraphFormat.cytoscape) == {
        "elements": {"nodes": [], "edges": []}
    }


def test_cytoscape_does_not_mutate_input():
    payload = _sample()
    before_nodes = [dict(n) for n in payload["nodes"]]
    before_edges = [dict(e) for e in payload["edges"]]
    format_subgraph(payload, SubgraphFormat.cytoscape)
    assert payload["nodes"] == before_nodes
    assert payload["edges"] == before_edges
