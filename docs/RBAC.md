# RBAC — Roles, Permissions & Organizations

## Model

- **Organization** — a tenant. Created by a user, who becomes its `Owner`.
- **OrganizationMember** — a user's membership + assigned **role** in an org.
- **Team** — a group within an org; team members carry a role.
- **Role** — a named set of permissions, scoped to an org. Five system roles are
  provisioned automatically per org; custom roles are supported.
- **Permission** — a granular capability slug (global catalog).

## System roles

| Role    | Summary                                                                 |
| ------- | ----------------------------------------------------------------------- |
| Owner   | All permissions, including `organization.delete` and `billing.manage`.  |
| Admin   | All except org deletion and billing.                                    |
| Manager | Teams, projects, channels, video lifecycle, prompts, agents, analytics. |
| Editor  | Create/publish video, edit prompts, run agents, read analytics.         |
| Viewer  | Read analytics only.                                                    |

## Permission catalog

`organization.manage`, `organization.delete`, `member.manage`, `team.manage`,
`role.manage`, `billing.manage`, `project.create`, `project.delete`,
`channel.manage`, `video.create`, `video.delete`, `video.publish`,
`prompt.edit`, `agent.run`, `analytics.read`, `api_key.manage`, `audit.read`.

The catalog lives in `app/security/permissions.py` — the single source of truth.
Default role→permission mappings are seeded from `DEFAULT_ROLE_PERMISSIONS`.

## Enforcing authorization

Routes never hardcode authorization. They declare a required permission via the
reusable dependency:

```python
@router.post("/{organization_id}/teams")
async def create_team(
    organization_id: uuid.UUID,
    ...,
    _: User = Depends(require_permission("team.manage")),
):
    ...
```

`require_permission(slug)` resolves the caller's role in the path
`organization_id`, checks the slug against the role's permissions, and raises
`403` on failure. Superusers bypass the check. Permission resolution is
implemented in `RBACService.get_permissions_for_user`.

## Provisioning

`OrganizationService.create` seeds the permission catalog (idempotent), creates
the five system roles for the org with their permission sets, and adds the
creator as `Owner`. Invitations assign a role by slug on acceptance.
