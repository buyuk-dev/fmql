from __future__ import annotations

from fmql.cypher import compile_cypher
from fmql.resolvers import RelativePathResolver, UuidResolver
from fmql.traversal import follow


def test_follow_mentions_from_body(obsidian_vault_ws):
    # Index.md body has [[Strategy]], [[Playbook|alias]], [[business/notes/Roadmap]],
    # [[Strategy#vision]] (heading-fragment → same target), ![[Diagram.png]] (skipped),
    # [[Ghost]] (dangling). Strategy is ambiguous (top-level wins alphabetically).
    result = follow(obsidian_vault_ws, ["Index.md"], field="mentions", depth=1)
    assert result == ["Playbook.md", "Strategy.md", "business/notes/Roadmap.md"]


def test_follow_mentions_reverse(obsidian_vault_ws):
    # Who mentions Playbook? Index.md (body) and ScalarRef.md ([[]] in frontmatter)
    # — both contribute to the `mentions` reverse adjacency for the body source,
    # but ScalarRef.md uses the 'primary' field, not 'mentions', so reverse on
    # 'mentions' should be just Index.md.
    result = follow(
        obsidian_vault_ws,
        ["Playbook.md"],
        field="mentions",
        depth=1,
        direction="reverse",
    )
    assert result == ["Index.md"]


def test_frontmatter_scalar_wikilink_typed_by_property(obsidian_vault_ws):
    result = follow(obsidian_vault_ws, ["ScalarRef.md"], field="primary", depth=1)
    assert result == ["Playbook.md"]


def test_frontmatter_list_wikilink_typed_by_property(obsidian_vault_ws):
    # related: ["[[Playbook]]", "Strategy.md"] — wikilink + resolver-path.
    result = follow(
        obsidian_vault_ws,
        ["ListRef.md"],
        field="related",
        depth=1,
        resolver=RelativePathResolver(),
    )
    assert result == ["Playbook.md", "Strategy.md"]


def test_mixed_list_resolver_does_not_run_for_wikilink_item(obsidian_vault_ws):
    # Pinning the "[[]] wins, resolver doesn't run for that item" rule:
    # if we use a uuid resolver that would NOT match "[[Playbook]]" as a string,
    # the wikilink still resolves to Playbook.md (resolver bypassed).
    result = follow(
        obsidian_vault_ws,
        ["ListRef.md"],
        field="related",
        depth=1,
        resolver=UuidResolver(),
    )
    # UuidResolver doesn't match "Strategy.md" (no packet has uuid="Strategy.md"),
    # so only the wikilink item produces an edge.
    assert result == ["Playbook.md"]


def test_dangling_wikilink_yields_no_edge(obsidian_vault_ws):
    # Index has [[Ghost]] which doesn't match any packet; mentions traversal
    # should silently omit it (no failure, no None target).
    result = follow(obsidian_vault_ws, ["Index.md"], field="mentions", depth=1)
    assert "Ghost" not in str(result)
    assert "Ghost.md" not in result


def test_follow_mentions_depth_star(obsidian_vault_ws):
    # Strategy.md, Playbook.md, Roadmap.md are leaves (no body wikilinks).
    # depth='*' from Index should reach exactly the three.
    result = follow(obsidian_vault_ws, ["Index.md"], field="mentions", depth="*")
    assert result == ["Playbook.md", "Strategy.md", "business/notes/Roadmap.md"]


def test_existing_behavior_unchanged_no_wikilinks(project_pm_ws):
    # project_pm_ws has zero wikilink syntax. Behavior must match pre-refactor.
    r = UuidResolver()
    assert follow(project_pm_ws, ["tasks/task-3.md"], field="blocked_by", depth=1, resolver=r) == [
        "tasks/task-1.md"
    ]
    # Reverse path also unchanged.
    assert follow(
        project_pm_ws,
        ["tasks/task-1.md"],
        field="blocked_by",
        depth=1,
        direction="reverse",
        resolver=r,
    ) == ["tasks/task-3.md", "tasks/task-4.md"]


def test_cypher_match_mentions(obsidian_vault_ws):
    result = compile_cypher(
        'MATCH (a)-[:mentions]->(b) WHERE a._id = "Index.md" RETURN b',
        obsidian_vault_ws,
    )
    targets = sorted(row[0] for row in result.rows)
    assert targets == ["Playbook.md", "Strategy.md", "business/notes/Roadmap.md"]


def test_cypher_match_property_name(obsidian_vault_ws):
    result = compile_cypher(
        "MATCH (a)-[:primary]->(b) RETURN a, b",
        obsidian_vault_ws,
    )
    rows = sorted((row[0], row[1]) for row in result.rows)
    assert rows == [("ScalarRef.md", "Playbook.md")]


def test_cypher_match_related_mixed_list(obsidian_vault_ws):
    result = compile_cypher(
        'MATCH (a)-[:related]->(b) WHERE a._id = "ListRef.md" RETURN b',
        obsidian_vault_ws,
    )
    targets = sorted(row[0] for row in result.rows)
    assert targets == ["Playbook.md", "Strategy.md"]
