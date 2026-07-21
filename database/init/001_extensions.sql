-- Baseline PostgreSQL initialization for AI YouTube Factory.
-- Runs once on first container start (empty data volume).
-- Schema is owned by Alembic migrations; this file only enables extensions.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
