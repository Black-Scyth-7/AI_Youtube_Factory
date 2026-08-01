"""Tests for the plugin manifest, registry, and dispatch.

The guarantees under test are the ones that make running third-party code
survivable: a plugin cannot take the host down, cannot hang it, and cannot
reach a capability it never declared.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from app.core.plugins import (
    Capability,
    HookContext,
    HookName,
    PluginManifest,
    PluginRegistry,
    register_builtin_plugins,
)
from app.core.plugins.builtin import headline_case
from app.core.plugins.registry import REGISTRY
from app.exceptions.base import ValidationError
from pydantic import ValidationError as PydanticValidationError


def _manifest(**overrides: Any) -> PluginManifest:
    base: dict[str, Any] = {
        "name": "test-plugin",
        "version": "1.0.0",
        "display_name": "Test",
        "hooks": [HookName.VIDEO_CREATED],
        "capabilities": [Capability.READ_CONTEXT],
    }
    base.update(overrides)
    return PluginManifest(**base)


async def _noop(context: HookContext) -> dict[str, Any] | None:
    return None


@pytest.fixture()
def registry() -> PluginRegistry:
    return PluginRegistry()


# -- Manifest validation ------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["", "A", "Uppercase", "has space", "has.dot", "x" * 65, "1leading"]
)
def test_invalid_names_are_rejected(name: str) -> None:
    """Names appear in metric labels and registry keys, so they are bounded."""
    with pytest.raises(PydanticValidationError):
        _manifest(name=name)


@pytest.mark.parametrize("version", ["1.0", "v1.0.0", "", "1.0.0.0", "latest"])
def test_invalid_versions_are_rejected(version: str) -> None:
    with pytest.raises(PydanticValidationError):
        _manifest(version=version)


def test_a_plugin_must_declare_at_least_one_hook() -> None:
    """A plugin attached to nothing can never run; accepting it hides a typo."""
    with pytest.raises(PydanticValidationError):
        _manifest(hooks=[])


def test_unknown_fields_are_rejected() -> None:
    """A misspelled manifest key would otherwise be silently ignored."""
    with pytest.raises(PydanticValidationError):
        _manifest(capabilitys=["read_context"])


def test_duplicate_hooks_are_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        _manifest(hooks=[HookName.VIDEO_CREATED, HookName.VIDEO_CREATED])


def test_a_manifest_is_immutable() -> None:
    """A plugin must not be able to widen its own declaration after loading."""
    manifest = _manifest()
    with pytest.raises(PydanticValidationError):
        manifest.name = "something-else"  # type: ignore[misc]


# -- Registration -------------------------------------------------------------


def test_a_plugin_registers_and_is_listed(registry: PluginRegistry) -> None:
    registry.register(_manifest(), {HookName.VIDEO_CREATED: _noop})
    assert [p.name for p in registry.all()] == ["test-plugin"]
    assert registry.get("test-plugin") is not None


def test_registering_the_same_name_twice_is_refused(registry: PluginRegistry) -> None:
    registry.register(_manifest(), {HookName.VIDEO_CREATED: _noop})
    with pytest.raises(ValidationError, match="already registered"):
        registry.register(_manifest(), {HookName.VIDEO_CREATED: _noop})


def test_a_declared_hook_without_a_handler_is_refused(
    registry: PluginRegistry,
) -> None:
    with pytest.raises(ValidationError, match="no handler"):
        registry.register(
            _manifest(hooks=[HookName.VIDEO_CREATED, HookName.BEFORE_RENDER]),
            {HookName.VIDEO_CREATED: _noop},
        )


def test_a_handler_for_an_undeclared_hook_is_refused(
    registry: PluginRegistry,
) -> None:
    """A handler nobody declared would run without appearing in an audit of
    what the plugin does."""
    with pytest.raises(ValidationError, match="undeclared"):
        registry.register(
            _manifest(hooks=[HookName.VIDEO_CREATED]),
            {HookName.VIDEO_CREATED: _noop, HookName.BEFORE_RENDER: _noop},
        )


# -- Capabilities -------------------------------------------------------------


def test_unprivileged_capabilities_are_granted(registry: PluginRegistry) -> None:
    plugin = registry.register(
        _manifest(capabilities=[Capability.READ_CONTEXT, Capability.STORAGE]),
        {HookName.VIDEO_CREATED: _noop},
    )
    assert plugin.granted == {Capability.READ_CONTEXT, Capability.STORAGE}


def test_privileged_capabilities_are_refused_by_default(
    registry: PluginRegistry,
) -> None:
    """A plugin must not reach the network or spend money on inference merely
    by asking to."""
    plugin = registry.register(
        _manifest(
            capabilities=[Capability.READ_CONTEXT, Capability.NETWORK, Capability.LLM]
        ),
        {HookName.VIDEO_CREATED: _noop},
    )
    assert plugin.granted == {Capability.READ_CONTEXT}
    assert Capability.NETWORK not in plugin.granted


def test_an_allowlisted_plugin_gets_its_privileged_capabilities(
    registry: PluginRegistry, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    monkeypatch.setattr(
        settings, "plugin_privileged_allowlist", "other-plugin, test-plugin"
    )
    plugin = registry.register(
        _manifest(capabilities=[Capability.READ_CONTEXT, Capability.NETWORK]),
        {HookName.VIDEO_CREATED: _noop},
    )
    assert Capability.NETWORK in plugin.granted


@pytest.mark.asyncio
async def test_the_handler_sees_only_granted_capabilities(
    registry: PluginRegistry,
) -> None:
    seen: dict[str, bool] = {}

    async def handler(context: HookContext) -> dict[str, Any] | None:
        seen["network"] = context.can(Capability.NETWORK)
        seen["read"] = context.can(Capability.READ_CONTEXT)
        return None

    registry.register(
        _manifest(capabilities=[Capability.READ_CONTEXT, Capability.NETWORK]),
        {HookName.VIDEO_CREATED: handler},
    )
    await registry.dispatch(HookName.VIDEO_CREATED, {})
    assert seen == {"network": False, "read": True}


# -- Dispatch -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_patch_is_applied_to_the_payload(registry: PluginRegistry) -> None:
    async def handler(context: HookContext) -> dict[str, Any]:
        return {"title": context.payload["title"].upper()}

    registry.register(_manifest(), {HookName.VIDEO_CREATED: handler})
    payload, results = await registry.dispatch(HookName.VIDEO_CREATED, {"title": "hello"})

    assert payload["title"] == "HELLO"
    assert results[0].ok is True
    assert results[0].patch == {"title": "HELLO"}


@pytest.mark.asyncio
async def test_dispatch_with_no_plugins_returns_the_payload(
    registry: PluginRegistry,
) -> None:
    payload, results = await registry.dispatch(HookName.VIDEO_CREATED, {"a": 1})
    assert payload == {"a": 1}
    assert results == []


@pytest.mark.asyncio
async def test_plugins_run_in_priority_then_name_order(
    registry: PluginRegistry,
) -> None:
    """Deterministic ordering: a chain that depends on import order is a
    heisenbug waiting to happen."""
    order: list[str] = []

    def make(name: str):  # type: ignore[no-untyped-def]
        async def handler(context: HookContext) -> None:
            order.append(name)
            return None

        return handler

    registry.register(
        _manifest(name="c-late", priority=50), {HookName.VIDEO_CREATED: make("c-late")}
    )
    registry.register(
        _manifest(name="b-early", priority=10),
        {HookName.VIDEO_CREATED: make("b-early")},
    )
    registry.register(
        _manifest(name="a-early", priority=10),
        {HookName.VIDEO_CREATED: make("a-early")},
    )

    await registry.dispatch(HookName.VIDEO_CREATED, {})
    assert order == ["a-early", "b-early", "c-late"]


@pytest.mark.asyncio
async def test_each_plugin_sees_the_previous_ones_output(
    registry: PluginRegistry,
) -> None:
    async def first(context: HookContext) -> dict[str, Any]:
        return {"value": context.payload.get("value", 0) + 1}

    async def second(context: HookContext) -> dict[str, Any]:
        return {"value": context.payload["value"] * 10}

    registry.register(
        _manifest(name="first", priority=1), {HookName.VIDEO_CREATED: first}
    )
    registry.register(
        _manifest(name="second", priority=2), {HookName.VIDEO_CREATED: second}
    )

    payload, _ = await registry.dispatch(HookName.VIDEO_CREATED, {"value": 0})
    assert payload["value"] == 10


# -- Containment --------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_failing_plugin_does_not_stop_the_chain(
    registry: PluginRegistry,
) -> None:
    """Third-party code failing must not fail a render."""

    async def explode(context: HookContext) -> None:
        raise RuntimeError("boom")

    async def survivor(context: HookContext) -> dict[str, Any]:
        return {"survived": True}

    registry.register(
        _manifest(name="exploder", priority=1), {HookName.VIDEO_CREATED: explode}
    )
    registry.register(
        _manifest(name="survivor", priority=2), {HookName.VIDEO_CREATED: survivor}
    )

    payload, results = await registry.dispatch(HookName.VIDEO_CREATED, {})

    assert payload["survived"] is True
    assert results[0].ok is False
    assert "RuntimeError: boom" in (results[0].error or "")
    assert results[1].ok is True


@pytest.mark.asyncio
async def test_a_hanging_plugin_is_timed_out(registry: PluginRegistry) -> None:
    """Without a timeout, a plugin that awaits forever stalls the stage."""

    async def hang(context: HookContext) -> None:
        await asyncio.sleep(30)

    async def after(context: HookContext) -> dict[str, Any]:
        return {"ran": True}

    registry.register(
        _manifest(name="hanger", priority=1, timeout_seconds=0.05),
        {HookName.VIDEO_CREATED: hang},
    )
    registry.register(
        _manifest(name="after", priority=2), {HookName.VIDEO_CREATED: after}
    )

    payload, results = await registry.dispatch(HookName.VIDEO_CREATED, {})

    assert results[0].timed_out is True
    assert results[0].ok is False
    assert payload["ran"] is True


@pytest.mark.asyncio
async def test_mutating_the_payload_in_place_does_not_leak(
    registry: PluginRegistry,
) -> None:
    """Each plugin gets a copy, so changes travel through the patch mechanism
    where they are recorded, rather than invisibly."""

    async def sneaky(context: HookContext) -> None:
        context.payload["injected"] = "yes"
        return None

    registry.register(_manifest(name="sneaky"), {HookName.VIDEO_CREATED: sneaky})
    payload, _ = await registry.dispatch(HookName.VIDEO_CREATED, {"a": 1})
    assert "injected" not in payload


@pytest.mark.asyncio
async def test_a_non_dict_return_is_rejected(registry: PluginRegistry) -> None:
    async def wrong(context: HookContext) -> Any:
        return ["not", "a", "dict"]

    registry.register(_manifest(), {HookName.VIDEO_CREATED: wrong})
    payload, results = await registry.dispatch(HookName.VIDEO_CREATED, {"a": 1})

    assert results[0].ok is False
    assert "expected dict" in (results[0].error or "")
    assert payload == {"a": 1}


# -- Built-in plugins ---------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("the rise of video", "The Rise of Video"),
        ("a tale of two cities", "A Tale of Two Cities"),
        ("how AI works", "How AI Works"),
        ("ending with the", "Ending With The"),
        ("single", "Single"),
    ],
)
def test_headline_case(raw: str, expected: str) -> None:
    assert headline_case(raw) == expected


@pytest.mark.asyncio
async def test_the_builtin_publish_chain_runs_in_order() -> None:
    """Hashtags are extracted before truncation, so tags come from the full
    text rather than from whatever survived."""
    REGISTRY.clear()
    register_builtin_plugins()

    description = "Great video #Python #FastAPI " + ("x" * 6000)
    payload, results = await REGISTRY.dispatch(
        HookName.BEFORE_PUBLISH, {"description": description}
    )

    assert [r.plugin for r in results] == ["hashtag-extract", "description-guard"]
    assert all(r.ok for r in results)
    assert payload["tags"] == ["python", "fastapi"]
    assert len(payload["description"]) <= 5001
    REGISTRY.clear()


@pytest.mark.asyncio
async def test_builtin_registration_is_idempotent() -> None:
    REGISTRY.clear()
    register_builtin_plugins()
    register_builtin_plugins()
    assert len(REGISTRY.all()) == 3
    REGISTRY.clear()
