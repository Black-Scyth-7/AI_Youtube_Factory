"""Plugin registry and dispatch.

Plugins are registered with a manifest and an implementation, and are invoked
by hook. Three rules govern execution, and each exists because the alternative
breaks the host:

* **A plugin cannot take the host down.** Every invocation is wrapped: an
  exception is recorded and the chain continues. Third-party code failing must
  not fail a render.
* **A plugin cannot hang the host.** Every invocation has a timeout from its
  manifest. Without one, a plugin that awaits forever stalls the pipeline
  stage it attached to.
* **A plugin gets only the capabilities it declared**, and privileged ones only
  if an operator allow-listed them. What it never declares, it cannot reach.

Ordering is by priority then name, so a given set of plugins always runs in the
same order rather than in whatever order they happened to be imported.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.config import settings
from app.core.plugins.manifest import (
    PRIVILEGED_CAPABILITIES,
    Capability,
    HookName,
    PluginManifest,
)
from app.exceptions.base import ValidationError
from app.logging import get_logger
from app.observability import instruments
from app.observability.tracing import start_span

logger = get_logger(__name__)

#: A hook implementation: given the payload, return a patch or None.
HookHandler = Callable[["HookContext"], Awaitable[dict[str, Any] | None]]


@dataclass(slots=True)
class HookContext:
    """What a plugin is given when a hook fires.

    A plain payload dict rather than ORM objects: handing a plugin a live
    entity would let it write to the database through a relationship, entirely
    outside the capability model.
    """

    hook: HookName
    payload: dict[str, Any]
    organization_id: str | None = None
    #: Capabilities actually granted, which may be fewer than requested.
    granted: frozenset[Capability] = field(default_factory=frozenset)

    def can(self, capability: Capability) -> bool:
        return capability in self.granted


@dataclass(frozen=True, slots=True)
class RegisteredPlugin:
    """A manifest and its handlers."""

    manifest: PluginManifest
    handlers: dict[HookName, HookHandler]
    granted: frozenset[Capability]

    @property
    def name(self) -> str:
        return self.manifest.name


@dataclass(frozen=True, slots=True)
class HookResult:
    """What one plugin did with one hook."""

    plugin: str
    ok: bool
    duration_ms: float
    patch: dict[str, Any] | None = None
    error: str | None = None
    timed_out: bool = False


class PluginRegistry:
    """Holds registered plugins and dispatches hooks to them."""

    def __init__(self) -> None:
        self._plugins: dict[str, RegisteredPlugin] = {}

    # -- Registration ---------------------------------------------------
    def register(
        self, manifest: PluginManifest, handlers: dict[HookName, HookHandler]
    ) -> RegisteredPlugin:
        """Register a plugin.

        Raises:
            ValidationError: If the name is taken, a declared hook has no
                handler, or a handler is supplied for a hook the manifest
                never declared. A handler nobody declared would run without
                appearing in an audit of what a plugin does.
        """
        if manifest.name in self._plugins:
            raise ValidationError(
                f"A plugin named '{manifest.name}' is already registered.",
                details={"name": manifest.name},
            )

        declared = set(manifest.hooks)
        supplied = set(handlers)
        if missing := sorted(declared - supplied):
            raise ValidationError(
                f"Plugin '{manifest.name}' declares hooks with no handler: "
                f"{', '.join(missing)}"
            )
        if undeclared := sorted(supplied - declared):
            raise ValidationError(
                f"Plugin '{manifest.name}' supplies handlers for undeclared "
                f"hooks: {', '.join(undeclared)}"
            )

        granted = self._grant(manifest)
        plugin = RegisteredPlugin(
            manifest=manifest, handlers=dict(handlers), granted=granted
        )
        self._plugins[manifest.name] = plugin

        refused = sorted(set(manifest.capabilities) - granted)
        logger.info(
            "plugin.registered",
            extra={
                "plugin": manifest.name,
                "version": manifest.version,
                "hooks": [h.value for h in manifest.hooks],
                "granted": sorted(c.value for c in granted),
                "refused": [c.value for c in refused],
            },
        )
        return plugin

    @staticmethod
    def _grant(manifest: PluginManifest) -> frozenset[Capability]:
        """Decide which requested capabilities the host actually allows.

        Unprivileged ones are granted as asked. Privileged ones are granted
        only when an operator named the plugin in ``PLUGIN_PRIVILEGED_ALLOWLIST``
        — the default is that a plugin cannot reach the network or spend money
        on inference simply by asking to.
        """
        requested = set(manifest.capabilities)
        granted = requested - PRIVILEGED_CAPABILITIES
        allowlist = {
            name.strip()
            for name in settings.plugin_privileged_allowlist.split(",")
            if name.strip()
        }
        if manifest.name in allowlist:
            granted |= requested & PRIVILEGED_CAPABILITIES
        return frozenset(granted)

    def unregister(self, name: str) -> None:
        self._plugins.pop(name, None)

    def clear(self) -> None:
        """Drop every plugin. Tests only."""
        self._plugins.clear()

    def get(self, name: str) -> RegisteredPlugin | None:
        return self._plugins.get(name)

    def all(self) -> list[RegisteredPlugin]:
        """Every plugin, in dispatch order."""
        return sorted(
            self._plugins.values(),
            key=lambda p: (p.manifest.priority, p.manifest.name),
        )

    def for_hook(self, hook: HookName) -> list[RegisteredPlugin]:
        """Plugins attached to ``hook``, in dispatch order."""
        return [p for p in self.all() if hook in p.handlers]

    # -- Dispatch -------------------------------------------------------
    async def dispatch(
        self,
        hook: HookName,
        payload: dict[str, Any],
        *,
        organization_id: str | None = None,
    ) -> tuple[dict[str, Any], list[HookResult]]:
        """Run every plugin attached to ``hook``.

        Returns the payload with each plugin's patch applied in order, and one
        result per plugin. Plugins run sequentially rather than concurrently:
        each sees the previous one's output, which is what makes a chain of
        transformations meaningful.

        Never raises on plugin failure. A plugin that throws is recorded and
        skipped, and the ones after it still run.
        """
        plugins = self.for_hook(hook)
        if not plugins:
            return payload, []

        current = dict(payload)
        results: list[HookResult] = []

        with start_span(
            f"plugins.{hook.value}", attributes={"plugin.count": len(plugins)}
        ):
            for plugin in plugins:
                result = await self._invoke(plugin, hook, current, organization_id)
                results.append(result)
                if result.patch:
                    current.update(result.patch)

        return current, results

    async def _invoke(
        self,
        plugin: RegisteredPlugin,
        hook: HookName,
        payload: dict[str, Any],
        organization_id: str | None,
    ) -> HookResult:
        """Run one plugin's handler, contained."""
        handler = plugin.handlers[hook]
        context = HookContext(
            hook=hook,
            # A copy: a plugin mutating the payload in place would edit what
            # every later plugin sees, bypassing the patch mechanism entirely.
            payload=dict(payload),
            organization_id=organization_id,
            granted=plugin.granted,
        )
        started = time.perf_counter()

        try:
            patch = await asyncio.wait_for(
                handler(context), timeout=plugin.manifest.timeout_seconds
            )
        except TimeoutError:
            duration = (time.perf_counter() - started) * 1000
            instruments.plugin_invocations_total.inc(
                1.0, plugin=plugin.name, hook=hook.value, outcome="timeout"
            )
            logger.warning(
                "plugin.timeout",
                extra={
                    "plugin": plugin.name,
                    "hook": hook.value,
                    "timeout_seconds": plugin.manifest.timeout_seconds,
                },
            )
            return HookResult(
                plugin=plugin.name,
                ok=False,
                duration_ms=round(duration, 3),
                error="timed out",
                timed_out=True,
            )
        except Exception as exc:
            duration = (time.perf_counter() - started) * 1000
            instruments.plugin_invocations_total.inc(
                1.0, plugin=plugin.name, hook=hook.value, outcome="error"
            )
            logger.exception(
                "plugin.failed",
                extra={
                    "plugin": plugin.name,
                    "hook": hook.value,
                    "error": f"{type(exc).__name__}: {exc}",
                },
            )
            return HookResult(
                plugin=plugin.name,
                ok=False,
                duration_ms=round(duration, 3),
                error=f"{type(exc).__name__}: {exc}",
            )

        duration = (time.perf_counter() - started) * 1000
        instruments.plugin_invocations_total.inc(
            1.0, plugin=plugin.name, hook=hook.value, outcome="succeeded"
        )
        instruments.plugin_duration_seconds.observe(
            duration / 1000, plugin=plugin.name, hook=hook.value
        )

        if patch is not None and not isinstance(patch, dict):
            logger.warning(
                "plugin.invalid_patch",
                extra={"plugin": plugin.name, "returned": type(patch).__name__},
            )
            return HookResult(
                plugin=plugin.name,
                ok=False,
                duration_ms=round(duration, 3),
                error=f"handler returned {type(patch).__name__}, expected dict or None",
            )

        return HookResult(
            plugin=plugin.name, ok=True, duration_ms=round(duration, 3), patch=patch
        )


#: The registry the application dispatches through.
REGISTRY = PluginRegistry()


def register_plugin(
    manifest: PluginManifest, handlers: dict[HookName, HookHandler]
) -> RegisteredPlugin:
    """Register a plugin on the default registry."""
    return REGISTRY.register(manifest, handlers)


async def dispatch(
    hook: HookName, payload: dict[str, Any], *, organization_id: str | None = None
) -> tuple[dict[str, Any], list[HookResult]]:
    """Dispatch a hook on the default registry."""
    return await REGISTRY.dispatch(hook, payload, organization_id=organization_id)
