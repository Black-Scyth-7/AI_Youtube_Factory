"""Tests for the public, API-key-authenticated API.

The properties that matter here are authentication (a key that is revoked,
expired, or malformed gets nothing), scoping (a key cannot exceed what it was
granted), and — above all — tenancy: one organization must never see another's
data, however the request is shaped.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.models.api_key import ApiKey
from app.models.video import Video
from app.models.workspace import Project, Workspace
from app.security.api_scopes import ALL_SCOPES, DEFAULT_SCOPES
from app.security.tokens import generate_api_key
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio

BASE = "/api/public/v1"


async def _org_with_video(
    session: AsyncSession, *, title: str = "A video"
) -> tuple[uuid.UUID, Project, Video]:
    """An organization with a workspace, a project, and one video."""
    org_id = uuid.uuid4()
    workspace = Workspace(
        organization_id=org_id, name="W", slug=f"w-{uuid.uuid4().hex[:8]}"
    )
    session.add(workspace)
    await session.flush()

    project = Project(
        workspace_id=workspace.id, name="P", slug=f"p-{uuid.uuid4().hex[:8]}"
    )
    session.add(project)
    await session.flush()

    video = Video(project_id=project.id, title=title)
    session.add(video)
    await session.flush()
    return org_id, project, video


async def _key(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID | None,
    scopes: list[str] | None = None,
    revoked: bool = False,
    expires_at: datetime | None = None,
) -> str:
    """Create an API key directly and return the raw value."""
    from app.security.tokens import hash_token

    raw, prefix, _ = generate_api_key()
    secret = raw.split(".", 1)[1]
    key = ApiKey(
        user_id=uuid.uuid4(),
        organization_id=organization_id,
        name="test key",
        prefix=prefix,
        secret_hash=hash_token(secret),
        scopes=list(scopes if scopes is not None else DEFAULT_SCOPES),
        revoked_at=datetime.now(UTC) if revoked else None,
        expires_at=expires_at,
    )
    session.add(key)
    await session.flush()
    return raw


def _auth(raw: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw}"}


# -- Authentication -----------------------------------------------------------


async def test_a_request_without_a_key_is_rejected(api: AsyncClient) -> None:
    response = await api.get(f"{BASE}/me")
    assert response.status_code == 401


async def test_a_malformed_key_is_rejected(api: AsyncClient) -> None:
    response = await api.get(f"{BASE}/me", headers=_auth("not-a-key"))
    assert response.status_code == 401


async def test_an_unknown_key_is_rejected(api: AsyncClient) -> None:
    raw, _, _ = generate_api_key()
    assert (await api.get(f"{BASE}/me", headers=_auth(raw))).status_code == 401


async def test_a_valid_key_identifies_itself(
    api: AsyncClient, session: AsyncSession
) -> None:
    org_id = uuid.uuid4()
    raw = await _key(session, organization_id=org_id)

    response = await api.get(f"{BASE}/me", headers=_auth(raw))
    assert response.status_code == 200
    body = response.json()
    assert body["organization_id"] == str(org_id)
    assert set(body["scopes"]) == set(DEFAULT_SCOPES)


async def test_the_x_api_key_header_also_works(
    api: AsyncClient, session: AsyncSession
) -> None:
    """Both conventions are in wide use; rejecting one buys nothing."""
    raw = await _key(session, organization_id=uuid.uuid4())
    response = await api.get(f"{BASE}/me", headers={"X-API-Key": raw})
    assert response.status_code == 200


async def test_a_revoked_key_is_rejected(api: AsyncClient, session: AsyncSession) -> None:
    raw = await _key(session, organization_id=uuid.uuid4(), revoked=True)
    assert (await api.get(f"{BASE}/me", headers=_auth(raw))).status_code == 401


async def test_an_expired_key_is_rejected(
    api: AsyncClient, session: AsyncSession
) -> None:
    raw = await _key(
        session,
        organization_id=uuid.uuid4(),
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    assert (await api.get(f"{BASE}/me", headers=_auth(raw))).status_code == 401


async def test_a_key_expiring_in_the_future_still_works(
    api: AsyncClient, session: AsyncSession
) -> None:
    raw = await _key(
        session,
        organization_id=uuid.uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    assert (await api.get(f"{BASE}/me", headers=_auth(raw))).status_code == 200


# -- Scopes -------------------------------------------------------------------


async def test_a_missing_scope_is_forbidden(
    api: AsyncClient, session: AsyncSession
) -> None:
    raw = await _key(session, organization_id=uuid.uuid4(), scopes=["project:read"])
    response = await api.get(f"{BASE}/videos", headers=_auth(raw))
    assert response.status_code == 403
    assert "video:read" in response.text


async def test_write_does_not_imply_read(api: AsyncClient, session: AsyncSession) -> None:
    """Implication rules are convenient until a webhook key granted write can
    also enumerate the catalogue."""
    raw = await _key(session, organization_id=uuid.uuid4(), scopes=["video:write"])
    assert (await api.get(f"{BASE}/videos", headers=_auth(raw))).status_code == 403


async def test_read_does_not_imply_write(api: AsyncClient, session: AsyncSession) -> None:
    org_id, project, _ = await _org_with_video(session)
    raw = await _key(session, organization_id=org_id, scopes=["video:read"])

    response = await api.post(
        f"{BASE}/videos",
        headers=_auth(raw),
        json={"project_id": str(project.id), "title": "New"},
    )
    assert response.status_code == 403


async def test_a_scope_removed_from_the_catalogue_is_not_honoured(
    api: AsyncClient, session: AsyncSession
) -> None:
    """A key issued with a scope that no longer exists must not act as a
    wildcard."""
    raw = await _key(
        session, organization_id=uuid.uuid4(), scopes=["video:read", "retired:scope"]
    )
    body = (await api.get(f"{BASE}/me", headers=_auth(raw))).json()
    assert body["scopes"] == ["video:read"]
    assert "retired:scope" not in ALL_SCOPES


async def test_a_key_without_an_organization_cannot_read_org_data(
    api: AsyncClient, session: AsyncSession
) -> None:
    """Defaulting to "all organizations" would turn a narrow key into a
    tenant-wide read."""
    raw = await _key(session, organization_id=None)
    response = await api.get(f"{BASE}/videos", headers=_auth(raw))
    assert response.status_code == 403
    assert "not bound to an organization" in response.text


# -- Tenancy ------------------------------------------------------------------


async def test_a_key_sees_only_its_own_organizations_videos(
    api: AsyncClient, session: AsyncSession
) -> None:
    mine_org, _, mine = await _org_with_video(session, title="Mine")
    _, _, theirs = await _org_with_video(session, title="Theirs")
    raw = await _key(session, organization_id=mine_org)

    body = (await api.get(f"{BASE}/videos", headers=_auth(raw))).json()
    titles = [v["title"] for v in body["data"]]
    assert titles == ["Mine"]
    assert str(theirs.id) not in str(body)
    assert body["meta"]["total"] == 1
    assert mine.title == "Mine"


async def test_reading_another_organizations_video_by_id_is_a_404(
    api: AsyncClient, session: AsyncSession
) -> None:
    """404 rather than 403: confirming an id exists is itself a disclosure."""
    mine_org, _, _ = await _org_with_video(session)
    _, _, theirs = await _org_with_video(session)
    raw = await _key(session, organization_id=mine_org)

    response = await api.get(f"{BASE}/videos/{theirs.id}", headers=_auth(raw))
    assert response.status_code == 404


async def test_filtering_by_another_organizations_project_returns_nothing(
    api: AsyncClient, session: AsyncSession
) -> None:
    """A project id from the request must narrow the query, never widen it."""
    mine_org, _, _ = await _org_with_video(session, title="Mine")
    _, their_project, _ = await _org_with_video(session, title="Theirs")
    raw = await _key(session, organization_id=mine_org)

    body = (
        await api.get(
            f"{BASE}/videos",
            headers=_auth(raw),
            params={"project_id": str(their_project.id)},
        )
    ).json()
    assert body["data"] == []
    assert body["meta"]["total"] == 0


async def test_creating_a_video_in_another_organizations_project_is_refused(
    api: AsyncClient, session: AsyncSession
) -> None:
    mine_org, _, _ = await _org_with_video(session)
    _, their_project, _ = await _org_with_video(session)
    raw = await _key(
        session, organization_id=mine_org, scopes=["video:write", "video:read"]
    )

    response = await api.post(
        f"{BASE}/videos",
        headers=_auth(raw),
        json={"project_id": str(their_project.id), "title": "Injected"},
    )
    assert response.status_code == 404


async def test_pipeline_runs_of_another_organizations_video_are_a_404(
    api: AsyncClient, session: AsyncSession
) -> None:
    mine_org, _, _ = await _org_with_video(session)
    _, _, theirs = await _org_with_video(session)
    raw = await _key(
        session, organization_id=mine_org, scopes=["pipeline:read", "video:read"]
    )

    response = await api.get(
        f"{BASE}/videos/{theirs.id}/pipeline-runs", headers=_auth(raw)
    )
    assert response.status_code == 404


# -- Shape --------------------------------------------------------------------


async def test_a_video_can_be_created_and_read_back(
    api: AsyncClient, session: AsyncSession
) -> None:
    org_id, project, _ = await _org_with_video(session)
    raw = await _key(
        session, organization_id=org_id, scopes=["video:write", "video:read"]
    )

    created = await api.post(
        f"{BASE}/videos",
        headers=_auth(raw),
        json={"project_id": str(project.id), "title": "Created via API"},
    )
    assert created.status_code == 201
    video_id = created.json()["id"]

    fetched = await api.get(f"{BASE}/videos/{video_id}", headers=_auth(raw))
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Created via API"


async def test_lists_are_objects_not_bare_arrays(
    api: AsyncClient, session: AsyncSession
) -> None:
    """A top-level array cannot grow a field, so pagination could never be
    added without breaking every client."""
    org_id, _, _ = await _org_with_video(session)
    raw = await _key(session, organization_id=org_id)

    body = (await api.get(f"{BASE}/videos", headers=_auth(raw))).json()
    assert isinstance(body, dict)
    assert set(body) == {"data", "meta"}
    assert set(body["meta"]) == {"total", "page", "size", "has_next"}


async def test_pagination_reports_more_pages(
    api: AsyncClient, session: AsyncSession
) -> None:
    org_id, project, _ = await _org_with_video(session)
    for i in range(4):
        session.add(Video(project_id=project.id, title=f"Extra {i}"))
    await session.flush()
    raw = await _key(session, organization_id=org_id)

    body = (
        await api.get(f"{BASE}/videos", headers=_auth(raw), params={"size": 2})
    ).json()
    assert len(body["data"]) == 2
    assert body["meta"]["total"] == 5
    assert body["meta"]["has_next"] is True


async def test_the_public_api_is_separate_from_the_internal_one(
    api: AsyncClient,
) -> None:
    """The internal API changes with the product; this one is a contract."""
    schema = (await api.get("/openapi.json")).json()
    public = [p for p in schema["paths"] if p.startswith("/api/public/v1")]
    assert public, "the public API should be documented"
    assert not any(p.startswith("/api/public/v1") and "/agents" in p for p in public)
