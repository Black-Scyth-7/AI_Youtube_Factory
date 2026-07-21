"""Tests for the enhanced BaseRepository and optimistic locking."""

from __future__ import annotations

import uuid

import pytest
from app.core.api.pagination import FilterSpec, PageParams, SortParam
from app.db.session import session_scope
from app.models.workspace import Workspace
from app.repositories.content import WorkspaceRepository
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm.exc import StaleDataError

pytestmark = pytest.mark.asyncio


async def _seed(session: AsyncSession, org_id: uuid.UUID, count: int) -> None:
    repo = WorkspaceRepository(session)
    for i in range(count):
        await repo.add(
            Workspace(organization_id=org_id, name=f"WS {i:02d}", slug=f"ws-{i:02d}")
        )


async def test_pagination_and_total(session: AsyncSession) -> None:
    org = uuid.uuid4()
    await _seed(session, org, 25)
    repo = WorkspaceRepository(session)
    page = await repo.paginate(
        PageParams(page=1, size=10),
        filters=[FilterSpec("organization_id", "eq", org)],
        sort=[SortParam("slug")],
    )
    assert page.total == 25
    assert len(page.items) == 10
    assert page.pages == 3
    assert page.items[0].slug == "ws-00"


async def test_filter_like_and_sort_desc(session: AsyncSession) -> None:
    org = uuid.uuid4()
    await _seed(session, org, 5)
    repo = WorkspaceRepository(session)
    page = await repo.paginate(
        PageParams(page=1, size=50),
        filters=[
            FilterSpec("organization_id", "eq", org),
            FilterSpec("slug", "like", "ws-0"),
        ],
        sort=[SortParam("slug", descending=True)],
    )
    assert [w.slug for w in page.items] == [f"ws-0{i}" for i in reversed(range(5))]


async def test_soft_delete_excluded_and_restore(session: AsyncSession) -> None:
    org = uuid.uuid4()
    repo = WorkspaceRepository(session)
    ws = await repo.add(Workspace(organization_id=org, name="X", slug="x"))
    await repo.soft_delete(ws)
    assert await repo.count(filters=[FilterSpec("organization_id", "eq", org)]) == 0
    assert (
        await repo.count(
            filters=[FilterSpec("organization_id", "eq", org)], include_deleted=True
        )
        == 1
    )
    await repo.restore(ws)
    assert await repo.count(filters=[FilterSpec("organization_id", "eq", org)]) == 1


async def test_optimistic_locking_raises_on_stale(
    db_sessionmaker: async_sessionmaker,
) -> None:
    org = uuid.uuid4()
    async with session_scope(db_sessionmaker) as s:
        ws = await WorkspaceRepository(s).add(
            Workspace(organization_id=org, name="Lock", slug="lock")
        )
        ws_id = ws.id

    # Two independent sessions load the same row.
    s1 = db_sessionmaker()
    s2 = db_sessionmaker()
    try:
        w1 = await s1.get(Workspace, ws_id)
        w2 = await s2.get(Workspace, ws_id)
        assert w1 is not None and w2 is not None

        w1.name = "First"
        await s1.commit()  # version 1 -> 2

        w2.name = "Second"  # still at version 1
        with pytest.raises(StaleDataError):
            await s2.commit()
    finally:
        await s1.close()
        await s2.close()


async def test_version_increments(session: AsyncSession) -> None:
    org = uuid.uuid4()
    repo = WorkspaceRepository(session)
    ws = await repo.add(Workspace(organization_id=org, name="V", slug="v"))
    assert ws.version == 1
    ws.name = "V2"
    await session.flush()
    assert ws.version == 2
