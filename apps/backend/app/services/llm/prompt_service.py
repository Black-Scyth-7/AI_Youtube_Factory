"""Prompt management service.

Creates and versions prompt templates in the database and renders them through
the prompt engine. New versions are immutable; ``latest_version`` on the template
tracks the head. Rendering resolves declared variables and validates context.
"""

from __future__ import annotations

import contextlib
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm.exceptions import PromptRenderError
from app.core.llm.prompts import (
    PromptSpec,
    PromptVariable,
    get_prompt_engine,
)
from app.exceptions.base import ConflictError, NotFoundError
from app.models.enums import AuditAction
from app.models.llm import PromptStatus, PromptTemplate, PromptVersion
from app.repositories.llm import PromptTemplateRepository, PromptVersionRepository
from app.services.audit import AuditService


class PromptService:
    """Manages prompt templates and versions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.templates = PromptTemplateRepository(session)
        self.versions = PromptVersionRepository(session)
        self.engine = get_prompt_engine()
        self.audit = AuditService(session)

    async def create_template(
        self,
        *,
        organization_id: uuid.UUID,
        name: str,
        template: str,
        actor_id: uuid.UUID,
        category: str | None = None,
        description: str | None = None,
        variables: list[dict[str, Any]] | None = None,
        tags: list[str] | None = None,
    ) -> tuple[PromptTemplate, PromptVersion]:
        """Create a template with its first version."""
        if await self.templates.get_by_name(organization_id, name):
            raise ConflictError(f"A prompt named '{name}' already exists.")
        record = await self.templates.add(
            PromptTemplate(
                organization_id=organization_id,
                name=name,
                category=category,
                description=description,
                tags=tags or [],
                status=PromptStatus.ACTIVE.value,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )
        version = await self.add_version(
            template_id=record.id,
            template=template,
            actor_id=actor_id,
            variables=variables,
        )
        await self.audit.record(
            AuditAction.API_KEY_CREATED,  # generic create action; prompt-specific later
            actor_id=actor_id,
            organization_id=organization_id,
            target_type="prompt",
            target_id=str(record.id),
        )
        return record, version

    async def add_version(
        self,
        *,
        template_id: uuid.UUID,
        template: str,
        actor_id: uuid.UUID,
        variables: list[dict[str, Any]] | None = None,
        examples: list[dict[str, Any]] | None = None,
    ) -> PromptVersion:
        """Add a new immutable version and advance the template head."""
        record = await self.templates.get(template_id)
        if record is None or record.deleted_at is not None:
            raise NotFoundError("Prompt template not found.")
        # Validate the template compiles before persisting. A render error with
        # empty context is fine (undefined vars); we only guard against template
        # syntax errors, which raise on compile.
        with contextlib.suppress(PromptRenderError):
            self.engine.render_string(template, {})
        # Derive the next version from the DB (authoritative across sessions).
        existing = await self.versions.list_for_template(template_id)
        next_version = (existing[0].version_number + 1) if existing else 1
        version = await self.versions.add(
            PromptVersion(
                template_id=template_id,
                version_number=next_version,
                template=template,
                variables=variables or [],
                examples=examples or [],
                created_by=actor_id,
                updated_by=actor_id,
            )
        )
        record.latest_version = next_version
        record.updated_by = actor_id
        await self.session.flush()
        return version

    async def render(
        self,
        *,
        template_id: uuid.UUID,
        context: dict[str, Any],
        version: int | None = None,
    ) -> str:
        """Render a prompt version with ``context``."""
        record = await self.templates.get(template_id)
        if record is None:
            raise NotFoundError("Prompt template not found.")
        target_version = version or record.latest_version
        version_row = await self.versions.get_version(template_id, target_version)
        if version_row is None:
            raise NotFoundError(f"Prompt version {target_version} not found.")
        spec = PromptSpec(
            name=record.name,
            template=version_row.template,
            version=version_row.version_number,
            variables=[
                PromptVariable(
                    name=v["name"],
                    required=v.get("required", True),
                    default=v.get("default"),
                )
                for v in version_row.variables
            ],
        )
        return self.engine.render(spec, context)

    async def rollback(
        self, *, template_id: uuid.UUID, to_version: int, actor_id: uuid.UUID
    ) -> PromptVersion:
        """Create a new version cloned from an earlier one (rollback)."""
        source = await self.versions.get_version(template_id, to_version)
        if source is None:
            raise NotFoundError(f"Prompt version {to_version} not found.")
        return await self.add_version(
            template_id=template_id,
            template=source.template,
            actor_id=actor_id,
            variables=source.variables,
            examples=source.examples,
        )
