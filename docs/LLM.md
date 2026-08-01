# Claude LLM Framework

The LLM framework is the shared AI infrastructure every future capability
(agents, the video pipeline, workflow AI nodes) is built on. It lives under
`apps/backend/app/core/llm/` and is exposed through a service layer and the
`/api/v1/llm/*` endpoints.

> **Golden rule:** no AI feature calls Anthropic directly. Every request goes
> through the provider abstraction. All future AI modules must use this
> framework exclusively — there are no direct Anthropic API calls outside
> `app/core/llm/providers/anthropic.py`.

## Layout

```
app/core/llm/
  messages.py     Role, Message, Usage, ChatRequest, ChatResponse, ToolCall/Result
  models.py       Model catalog: pricing, context/output limits, capabilities
  base.py         BaseLLMProvider ABC (chat/stream/count_tokens/health_check)
  registry.py     Provider registry + get_provider() resolution/caching
  providers/
    anthropic.py  AnthropicProvider — the only place the Anthropic SDK is used
    mock.py       MockProvider — deterministic, network-free (tests + default)
  manager.py      LLMManager — cache + retry + circuit-breaker + rate limit
  retry.py        RetryPolicy, CircuitBreaker, with_retry()
  cache.py        LLMCache (Redis-backed response + token-count caching)
  streaming.py    StreamEvent / StreamEventType (uniform SSE event shape)
  tools.py        Tool, ToolRegistry (validated tool execution)
  schemas.py      Structured-output parsing + malformed-JSON recovery
  tokenizer.py    Token counting (provider count_tokens + heuristic fallback)
  prompts.py      PromptEngine (Jinja) — see PromptEngine.md
  conversation.py Runtime conversation object — see Conversation.md / Memory.md
  metrics.py      Request timing + accounting hooks
  exceptions.py   Typed LLM errors
```

## Request flow

```
Service layer (LLMService / PromptService / ConversationService)
        │
        ▼
   LLMManager.chat()/stream()
        │  ┌─ response cache (Redis) ── hit ──▶ return
        │  ├─ rate limit (RPM + concurrency)
        │  ├─ retry + circuit breaker
        ▼  ▼
   Provider (Anthropic | Mock)  ──▶ ChatResponse
        │
        ▼
   record_request() ──▶ token accounting + cost rollups (DB)
```

## Configuration

All behavior is driven by settings (env vars, prefix-less uppercase) — see
`.env.example` and `app/config/settings.py`:

| Setting                     | Default           | Purpose                                |
| --------------------------- | ----------------- | -------------------------------------- |
| `LLM_DEFAULT_PROVIDER`      | `anthropic`       | Provider slug; `mock` for offline.     |
| `LLM_DEFAULT_MODEL`         | `claude-opus-4-8` | Resolved from config, never hardcoded. |
| `LLM_MAX_TOKENS`            | `4096`            | Default output cap.                    |
| `LLM_THINKING`              | `adaptive`        | Adaptive thinking (`off` to disable).  |
| `LLM_TIMEOUT_SECONDS`       | `120`             | Per-request timeout.                   |
| `LLM_MAX_RETRIES`           | `3`               | Retry attempts (exponential backoff).  |
| `LLM_CACHE_ENABLED`         | `true`            | Response + token-count caching.        |
| `LLM_CACHE_TTL_SECONDS`     | `3600`            | Cache TTL.                             |
| `LLM_RATE_LIMIT_RPM`        | `60`              | Requests/min per rate-limit key.       |
| `LLM_RATE_LIMIT_CONCURRENT` | `10`              | Max concurrent in-flight requests.     |
| `LLM_FALLBACK_MODEL`        | —                 | Optional fallback model on failure.    |

### A note on sampling parameters

The default models (Opus 4.8/4.7, Sonnet 5, Fable 5) **reject** `temperature`,
`top_p`, and `top_k` with a 400. The model catalog (`models.py`) marks each
model's `accepts_sampling_params` and `adaptive_thinking_only`; the Anthropic
provider only sends sampling params / thinking config a model actually accepts.
Never hardcode these — the catalog is the source of truth.

## Model catalog

`app/core/llm/models.py` holds `ModelInfo` for each known model (context window,
max output, input/output price per MTok, tool/streaming support). Unknown model
IDs resolve to a safe default via `dataclasses.replace(_DEFAULT, id=model)` so a
newer model string still works. `estimate_cost(model, input, output)` computes
USD cost from token counts; the API surfaces this per request and in rollups.

## API endpoints (`/api/v1/llm`)

| Method & path                       | Purpose                                        |
| ----------------------------------- | ---------------------------------------------- |
| `POST /chat`                        | Single accounted completion (cached, retried). |
| `POST /stream`                      | Server-Sent Events stream of the completion.   |
| `GET  /models`                      | Model catalog.                                 |
| `GET  /health`                      | Per-provider health checks.                    |
| `GET  /tools`                       | Registered tool schemas.                       |
| `POST /prompts`                     | Create a versioned prompt template.            |
| `POST /prompts/{id}/versions`       | Add an immutable version.                      |
| `POST /prompts/{id}/render`         | Render with a variable context.                |
| `POST /prompts/{id}/rollback`       | Roll back to a prior version (as a new one).   |
| `POST /conversations`               | Create a persisted conversation.               |
| `GET  /conversations/{id}/messages` | Load the transcript.                           |
| `GET  /usage`                       | Token-usage rollup for an org + date range.    |
| `GET  /costs`                       | Cost rollup for an org + date range.           |

Org-scoped operations enforce RBAC (`prompt.edit`, `agent.run`,
`analytics.read`).

## Security

- **API keys are never exposed.** Provider secrets are encrypted at rest with
  Fernet (`app/security/crypto.py`, keyed from `SECRET_KEY`).
- Prompt variables are sanitized before rendering; Jinja runs without arbitrary
  attribute access.
- Tool execution is validated against the registered JSON schema before a
  handler runs.
- Prompt changes are versioned and auditable (immutable versions + rollback).

## Testing

There is no Anthropic key or Docker requirement to run the suite. Tests exercise
the full framework — services, retry, cache, cost, streaming, tools, structured
output — against an in-memory SQLite database (via the portable `GUID` type) and
the deterministic `MockProvider`. Set `LLM_DEFAULT_PROVIDER=mock` (the test
conftest does this automatically). The live Anthropic path is written to the SDK
contract but is not exercised offline.

Run: `ruff check`, `black --check`, `mypy app`, `pytest` (all green).
