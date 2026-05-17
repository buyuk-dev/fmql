# examples

Sample vaults you can run fmql against to see the query surface in action.
Each subdirectory is a self-contained vault — point fmql at it with `-w`.

## vault_1 — wikilinks sampler

A tiny vault that exercises every wikilink shape fmql understands. Six notes
arranged as a fictional startup's knowledge base: an `Index`, two people under
`team/`, two projects under `projects/`, and one decision under `decisions/`.

What it demonstrates:

- **Body wikilinks** — `[[Note]]` in note bodies become `mentions` edges.
- **Alias form** — `[[Note|alias]]` resolves to `Note`, alias is display-only.
- **Path-form** — `[[team/Alice]]` resolves to a specific workspace path.
- **Frontmatter scalar `[[]]`** — `owner: '[[team/Alice]]'` becomes an `owner` edge.
- **Frontmatter list `[[]]`** — `contributors: ['[[Bob]]']` becomes a `contributors` edge.
- **Mixed list** — a `[[]]` entry alongside a bare string in the same property.
- **Dangling target** — `[[Ghost]]` in `Index.md` for the `--diagnose` warning path.

Run from the repo root:

```bash
# Every body-link mention
fmql query "MATCH (a)-[:mentions]->(b) RETURN a, b" -w examples/vault_1

# Project owners (frontmatter scalar [[]])
fmql query "MATCH (a)-[:owner]->(b) RETURN a, b" -w examples/vault_1

# Project contributors (frontmatter list [[]])
fmql query "MATCH (a)-[:contributors]->(b) RETURN a, b" -w examples/vault_1

# Decisions that relate to a project (mixed-list demo)
fmql query "MATCH (a)-[:relates_to]->(b) RETURN a, b" -w examples/vault_1

# Walk one hop out from Index along mentions
fmql query "MATCH (n) WHERE n._id = 'Index.md' RETURN n" \
  --follow mentions --depth 1 -w examples/vault_1

# Surface the dangling [[Ghost]] link
fmql query "MATCH (a)-[:mentions]->(b) RETURN a" --diagnose -w examples/vault_1
```

## Visualize the graph

Export the whole vault as a Cytoscape JSON graph:

```bash
fmql subgraph "MATCH (n) RETURN n" \
  --follow mentions --follow owner --follow contributors --follow relates_to \
  --depth '*' --ids-only --format cytoscape -w examples/vault_1 \
  > /tmp/vault_1.cyjs
```

Then open `examples/viewer.html` in any browser and drop the `.cyjs` file
onto the page. The viewer uses cytoscape.js (loaded from CDN), color-codes
edges by field name, and lets you switch layouts.
