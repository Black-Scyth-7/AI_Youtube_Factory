"""The plugin ecosystem.

A plugin declares a manifest — name, hooks, capabilities — and supplies a
handler per hook. The host validates the manifest before running anything,
grants only the capabilities it is willing to, and contains every invocation
with a timeout and an exception boundary.

Third-party code must not be able to take the host down, hang it, or reach
what it never declared.
"""

from __future__ import annotations

from app.core.plugins.builtin import register_builtin_plugins
from app.core.plugins.manifest import (
    PRIVILEGED_CAPABILITIES,
    Capability,
    HookName,
    PluginManifest,
)
from app.core.plugins.registry import (
    REGISTRY,
    HookContext,
    HookResult,
    PluginRegistry,
    RegisteredPlugin,
    dispatch,
    register_plugin,
)

__all__ = [
    "PRIVILEGED_CAPABILITIES",
    "REGISTRY",
    "Capability",
    "HookContext",
    "HookName",
    "HookResult",
    "PluginManifest",
    "PluginRegistry",
    "RegisteredPlugin",
    "dispatch",
    "register_builtin_plugins",
    "register_plugin",
]
