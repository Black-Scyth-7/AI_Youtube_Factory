"""Plugin routes.

Read-only. Installing a plugin means loading third-party code into the server
process, which is a deployment action rather than an API call — exposing it
here would turn any account takeover into remote code execution.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.plugins import REGISTRY, Capability, HookName
from app.dependencies.auth import require_permission
from app.models.user import User

router = APIRouter(prefix="/plugins", tags=["plugins"])


class PluginResponse(BaseModel):
    """An installed plugin and what the host actually allows it to do."""

    name: str
    version: str
    display_name: str
    description: str
    author: str
    hooks: list[str]
    priority: int
    timeout_seconds: float
    requested_capabilities: list[str] = Field(default_factory=list)
    #: What was granted. Fewer than requested when a privileged capability was
    #: asked for and the plugin is not allow-listed.
    granted_capabilities: list[str] = Field(default_factory=list)
    refused_capabilities: list[str] = Field(default_factory=list)


class HookResponse(BaseModel):
    """A hook and the plugins attached to it, in dispatch order."""

    hook: str
    plugins: list[str]


@router.get("", response_model=list[PluginResponse], summary="List installed plugins")
async def list_plugins(
    _: User = Depends(require_permission("analytics.read")),
) -> list[PluginResponse]:
    """Every installed plugin, in dispatch order."""
    out: list[PluginResponse] = []
    for plugin in REGISTRY.all():
        manifest = plugin.manifest
        requested = {c.value for c in manifest.capabilities}
        granted = {c.value for c in plugin.granted}
        out.append(
            PluginResponse(
                name=manifest.name,
                version=manifest.version,
                display_name=manifest.display_name,
                description=manifest.description,
                author=manifest.author,
                hooks=[h.value for h in manifest.hooks],
                priority=manifest.priority,
                timeout_seconds=manifest.timeout_seconds,
                requested_capabilities=sorted(requested),
                granted_capabilities=sorted(granted),
                refused_capabilities=sorted(requested - granted),
            )
        )
    return out


@router.get("/hooks", response_model=list[HookResponse], summary="List hooks")
async def list_hooks(
    _: User = Depends(require_permission("analytics.read")),
) -> list[HookResponse]:
    """Every hook the host offers, and what is attached to each.

    Includes hooks with nothing attached: "no plugin runs here" is the useful
    answer when a plugin appears not to be firing.
    """
    return [
        HookResponse(hook=hook.value, plugins=[p.name for p in REGISTRY.for_hook(hook)])
        for hook in HookName
    ]


@router.get(
    "/capabilities",
    response_model=dict[str, str],
    summary="Describe the capability model",
)
async def list_capabilities(
    _: User = Depends(require_permission("analytics.read")),
) -> dict[str, str]:
    """What each capability permits."""
    return {
        Capability.READ_CONTEXT.value: "Read the object the hook fired for",
        Capability.WRITE_CONTEXT.value: "Return modifications to that object",
        Capability.STORAGE.value: "Read and write the plugin's own storage",
        Capability.LLM.value: "Call the LLM framework (privileged)",
        Capability.NETWORK.value: "Make outbound HTTP requests (privileged)",
    }
