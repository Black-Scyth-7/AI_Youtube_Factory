# Database

PostgreSQL is the system of record. Schema is managed exclusively by **Alembic**
migrations in `apps/backend/app/db/migrations`.

- `init/` — SQL run once on first container start (extensions only; no tables).
- Conventions: UUID primary keys, `created_at` / `updated_at` audit timestamps,
  `deleted_at` soft deletes, deterministic constraint naming (see
  `apps/backend/app/models`).

## Migrations

```bash
cd apps/backend
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```
