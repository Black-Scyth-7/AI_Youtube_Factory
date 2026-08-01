# LLM Providers

Every LLM call resolves to a **provider** — the only layer that touches a vendor
SDK. This is what makes the golden rule enforceable: _no AI feature calls
Anthropic directly._

## Contract: `BaseLLMProvider`

`app/core/llm/base.py` defines the ABC every provider implements:

| Method                                                | Purpose                       |
| ----------------------------------------------------- | ----------------------------- |
| `async chat(request) -> ChatResponse`                 | One non-streaming completion. |
| `async stream(request) -> AsyncIterator[StreamEvent]` | Uniform streaming events.     |
| `async count_tokens(request) -> int`                  | Token count for a request.    |
| `async health_check() -> bool`                        | Liveness/credential probe.    |

Concrete helpers (`complete`, `embed`, `estimate_cost`, `supports_*`) are
provided on the base. Each provider exposes a `slug` used for registration and
accounting.

## Registry

`app/core/llm/registry.py` maps slugs to constructors and caches instances:

```python
_REGISTRY = {
    "anthropic": AnthropicProvider,
    "claude":    AnthropicProvider,  # alias
    "mock":      MockProvider,
}
```

- `get_provider(slug)` — returns a cached instance (constructs on first use);
  raises `ProviderNotAvailableError` (listing available slugs) for an unknown
  one.
- `register_provider(slug, factory)` — registers/overrides a provider and evicts
  any cached instance.
- `available_providers()` — sorted slugs (drives `GET /llm/health`).
- `reset_providers()` — clears the instance cache (test isolation).

The active provider defaults to `LLM_DEFAULT_PROVIDER`; a request may override it
per call (`provider=` on `/llm/chat`).

## Anthropic provider

`app/core/llm/providers/anthropic.py` — the **only** place the Anthropic SDK is
imported. Key behaviors, driven by the model catalog (`models.py`):

- **Model from config, never hardcoded.** The request's model (or
  `LLM_DEFAULT_MODEL`) is passed straight through.
- **Adaptive thinking** is sent only for models flagged `adaptive_thinking_only`;
  `budget_tokens` is never sent to models that reject it.
- **Sampling params** (`temperature`/`top_p`/`top_k`) are sent only when a
  model's `accepts_sampling_params` is true — the default models return a 400
  otherwise.
- **System prompt** is split out of the message list into the API's `system`
  field.
- The client is constructed lazily so the process starts (and tests run) without
  an `ANTHROPIC_API_KEY`.

## Mock provider

`app/core/llm/providers/mock.py` — a deterministic, network-free provider used in
tests and as a safe default when no key is configured (`LLM_DEFAULT_PROVIDER=mock`).

- Echoes `"Echo: {last user message}"` for a normal chat.
- Emits a minimal valid JSON object when a `response_schema` is set (exercises
  structured output + recovery).
- Emits a tool call when a tool is present and the user says "use tool"
  (exercises the tool loop).
- Streams the echoed content token-by-token as `StreamEvent`s.

This lets the entire framework — services, retry, cache, cost, streaming,
tools — run offline with no vendor dependency.

## Adding a provider

1. Implement `BaseLLMProvider` (set a unique `slug`).
2. Confine all SDK usage to that module.
3. Add its models to the catalog in `models.py` (pricing, limits, capability and
   sampling flags).
4. Register it: `register_provider("myslug", MyProvider)`.

No caller changes are needed — the manager, services, and API resolve providers
purely through the registry. See [LLM.md](./LLM.md) for the full request flow.
