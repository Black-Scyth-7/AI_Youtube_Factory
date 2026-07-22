# Agent Knowledge

Knowledge is **separate from memory**: memory is the volatile working state of a
run; knowledge is the relatively stable body of facts, policies, documentation,
templates, and preferences an agent consults. See [Memory.md](./Memory.md) for the
distinction.

## Runtime (`knowledge/`)

- **`KnowledgeEntry`** — `title`, `content`, a `KnowledgeKind`
  (`policy` / `documentation` / `template` / `fact` / `preference` / `rule`), and
  tags.
- **`KnowledgeBase`** — an in-memory, keyword-searchable store. `search(query,
  limit)` returns the most relevant entry contents; `policies()` returns policy
  and rule entries (the reasoner injects these into the system prompt).
- **`KnowledgeContext`** — renders selected facts + policies into a prompt-ready
  block.

RAG / vector retrieval plugs in behind the same `search()` surface in a later
phase without changing callers.

## Persistence & service

`KnowledgeDocument` rows (table `knowledge_document`) are organization-scoped.
`KnowledgeService`:

- `create(...)` / `list_for_org(...)` / `delete(...)` — CRUD (soft delete).
- `build_base(organization_id)` — assembles a runtime `KnowledgeBase` from stored
  documents, injected into every agent run by `AgentService.run()`.

## API & UI

- `GET /knowledge?organization_id=` — list documents.
- `POST /knowledge` — create (requires `agent.manage`).
- `DELETE /knowledge/{id}` — remove.

The frontend **Knowledge base** page (`/dashboard/agents/knowledge`) provides
create/list/delete over these endpoints.
