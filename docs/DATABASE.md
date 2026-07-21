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
0001_identity      → identity & access-management schema
0002_core_infra    → content, workflow, and infrastructure tables
```

```bash
cd apps/backend
alembic upgrade head
alembic revision --autogenerate -m "message"   # incremental changes
```

## Repository layer

`BaseRepository[Model]` provides CRUD, `paginate` (filter + sort + soft-delete
aware), `count`, `soft_delete`/`restore`, `bulk_add`, and `find_by`/`exists`.
Repositories contain **no business logic** — that lives in services. Filtering
uses `FilterSpec(field, op, value)` (`eq/ne/gt/ge/lt/le/like/ilike/in`) and
sorting uses `SortParam(field, descending)`.
