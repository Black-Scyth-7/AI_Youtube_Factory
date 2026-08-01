# Database

PostgreSQL + SQLAlchemy 2 (async, asyncpg) + Alembic. The portable `GUID` type
maps to native `UUID` on PostgreSQL and `CHAR(36)` elsewhere (tests run on
SQLite).

## Conventions

Every domain entity (Phase 03 `EntityMixin`) carries:

- `id` — UUID primary key
- `created_at` / `updated_at` — audit timestamps
- `deleted_at` — soft delete
- `created_by` / `updated_by` — actor references
- `version` — integer **optimistic-lock** column (`version_id_col`); concurrent
  ORM updates raise `StaleDataError`

Identity entities (Phase 02 `AuditMixin`) carry the first three. Constraint names
are deterministic (see `models/base.py`) so Alembic autogenerate is stable.

## Schema (32 tables)

- **Identity (Phase 02):** user, profile, organization, organization_member,
  team, team_member, role, permission, role_permission, session, refresh_token,
  email_verification_token, password_reset_token, oauth_account, api_key,
  invitation, audit_log.
- **Content (Phase 03):** workspace → project → channel → video → video_version;
  folder, media_file, tag, video_tag.
- **Workflow:** workflow, workflow_node, workflow_edge, workflow_execution.
- **Infrastructure:** feature_flag, activity_log.

## Migrations

```
0001_identity      → identity & access management            17 tables
0002_core_infra    → content, workflow, and infrastructure   15 tables
0003_llm           → prompts, conversations, accounting       11 tables
0004_agent         → agents, goals, plans, knowledge          15 tables
0005_catalog       → billing, notifications, jobs             12 tables
0006_workflow      → workflow triggers and node executions     2 tables
0007_pipeline      → research, runs, publications, analytics   5 tables
```

```bash
cd apps/backend
alembic upgrade head
alembic revision --autogenerate -m "message"   # incremental changes
alembic downgrade -1                           # undo the last revision
```

### Migrations use explicit DDL

Every migration spells out its `op.create_table` / `op.add_column` calls, and
describes the schema **as of that revision**. Nothing in a migration may read
`Base.metadata`.

This is load-bearing rather than stylistic. These migrations previously called
`Base.metadata.create_all()`, which had two consequences:

- A revision produced whatever the models happened to look like when it ran, so
  the history described no particular schema. `0001` alone created all 77
  tables, including ones belonging to phases years of commits later, and every
  subsequent revision was a silent no-op.
- `create_all` only creates *missing* tables and cannot alter an existing one.
  A column added to a model therefore reached a fresh database — because the
  database was built from the models — and silently never reached a deployed
  one. The failure surfaced at runtime as a missing column, long after the
  deployment reported success.

`tests/integration/test_migrations.py` enforces this: it applies every revision
to a scratch SQLite database, compares the result against the ORM metadata, and
fails on a model change with no matching migration. It also refuses any
migration that mentions `Base.metadata`.

Set `MIGRATION_TEST_DATABASE_URL` to a **throwaway** PostgreSQL database to
additionally check types, server defaults, and indexes, which SQLite reflection
cannot see:

```bash
MIGRATION_TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/scratch   pytest tests/integration/test_migrations.py
```

That test drops and recreates the `public` schema, so never point it at a
database whose contents matter.

### Adding a migration

```bash
alembic revision --autogenerate -m "add publication.retry_count"
```

Read what autogenerate produced before committing it — it does not detect
renames (it emits a drop plus an add, which loses the data) and it cannot know
whether an added non-null column needs a backfill.

## Repository layer

`BaseRepository[Model]` provides CRUD, `paginate` (filter + sort + soft-delete
aware), `count`, `soft_delete`/`restore`, `bulk_add`, and `find_by`/`exists`.
Repositories contain **no business logic** — that lives in services. Filtering
uses `FilterSpec(field, op, value)` (`eq/ne/gt/ge/lt/le/like/ilike/in`) and
sorting uses `SortParam(field, descending)`.
