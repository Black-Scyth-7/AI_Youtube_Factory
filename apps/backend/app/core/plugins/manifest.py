"""Plugin manifests.

A plugin declares what it is and what it wants before any of its code runs. The
manifest is validated first, so a plugin asking for a capability it should not
have is rejected at load time rather than discovered at call time.

Nothing here executes plugin code. Keeping declaration and execution apart is
what makes it possible to list, audit, and refuse a plugin without running it.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: Plugin names are used in logs, metric labels, and registry keys, so they are
#: constrained rather than free text.
_NAME_RE: Final = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
_VERSION_RE: Final = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


class Capability(StrEnum):
    """What a plugin is permitted to touch.

    Requested in the manifest and granted by the host. A plugin that never
    declares ``NETWORK`` is not given a way to make a request, so the common
    case — a formatter, a scorer, a naming convention — cannot exfiltrate
    anything even if its code is hostile.
    """

    #: Read the video, run, and project it was invoked for.
    READ_CONTEXT = "read_context"
    #: Return modifications to the object it was invoked for.
    WRITE_CONTEXT = "write_context"
    #: Read and write the plugin's own namespaced storage.
    STORAGE = "storage"
    #: Call the LLM framework, metered against the organization's quota.
    LLM = "llm"
    #: Make outbound HTTP requests.
    NETWORK = "network"


#: Capabilities that let a plugin reach outside the process. Granting one is a
#: decision an operator should make deliberately, so they are refused unless
#: explicitly allow-listed in configuration.
PRIVILEGED_CAPABILITIES: Final[frozenset[Capability]] = frozenset(
    {Capability.NETWORK, Capability.LLM}
)


class HookName(StrEnum):
    """The points a plugin may attach to.

    A closed set. Arbitrary hook names would mean a typo silently never runs,
    which is the worst failure mode for something that is supposed to modify
    behaviour.
    """

    VIDEO_CREATED = "video.created"
    SCRIPT_GENERATED = "script.generated"
    BEFORE_RENDER = "render.before"
    AFTER_RENDER = "render.after"
    BEFORE_PUBLISH = "publish.before"
    AFTER_PUBLISH = "publish.after"
    ANALYTICS_COLLECTED = "analytics.collected"


class PluginManifest(BaseModel):
    """What a plugin declares about itself."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(description="Unique slug, lowercase.")
    version: str = Field(description="Semantic version.")
    display_name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=1000)
    author: str = Field(default="", max_length=128)
    #: Hooks this plugin attaches to, in the order it wants to run.
    hooks: list[HookName] = Field(min_length=1)
    capabilities: list[Capability] = Field(default_factory=list)
    #: Lower runs first. Ties break on name, so ordering is deterministic
    #: rather than dependent on load order.
    priority: int = Field(default=100, ge=0, le=1000)
    #: Seconds a single hook invocation may take before it is cancelled.
    timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    config_schema: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if not _NAME_RE.match(value):
            raise ValueError(
                f"Invalid plugin name {value!r}: lowercase letters, digits, "
                "hyphen and underscore only, 2-64 characters."
            )
        return value

    @field_validator("version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        if not _VERSION_RE.match(value):
            raise ValueError(f"Invalid version {value!r}: expected MAJOR.MINOR.PATCH.")
        return value

    @field_validator("hooks", "capabilities")
    @classmethod
    def _reject_duplicates(cls, value: list[Any]) -> list[Any]:
        if len(set(value)) != len(value):
            raise ValueError("Duplicate entries are not allowed.")
        return value

    def wants(self, capability: Capability) -> bool:
        return capability in self.capabilities

    @property
    def privileged(self) -> frozenset[Capability]:
        """The privileged capabilities this plugin asks for."""
        return frozenset(self.capabilities) & PRIVILEGED_CAPABILITIES
