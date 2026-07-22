# Conversation Memory

Memory management keeps a conversation's working context within a model's token
budget. It lives in `app/core/llm/memory.py` and complements the persisted
transcript (see [Conversation.md](./Conversation.md)).

## Short-term: `WindowMemory`

A sliding window that keeps the most recent messages that fit within a token
budget.

```python
memory = WindowMemory(max_tokens=8000)
recent = memory.trim(messages, system=system_prompt)
```

- `trim(messages, system=None)` — walks messages newest-first, keeping each while
  the running token estimate stays within `max_tokens`; always keeps at least the
  most recent message. Returns them in chronological order.
- `compress(messages, system=None)` — when a `Summarizer` is configured, older
  overflow messages are summarized into a single `SYSTEM` "Summary of earlier
  conversation" message prepended to the retained recent messages, rather than
  dropped. Without a summarizer it degrades to `trim`.

Token footprints are estimated with `estimate_messages_tokens()`, which uses the
heuristic tokenizer (`heuristic_token_count`) so trimming needs no network call.

## Pluggable interfaces (Protocols)

Two `runtime_checkable` protocols let later phases plug in richer backends
without changing callers:

- **`Summarizer`** — `async summarize(messages) -> str`. A summarizer backed by
  the LLM itself (via `LLMService`) can compress history; any object matching the
  shape works.
- **`LongTermMemory`** — `async store(...)` / `async recall(conversation_id,
  query, k=5)`. The seam for a durable, retrievable memory (e.g. a vector store).
  The concrete backend arrives with the agent framework in a later phase; the
  interface is defined here so the working-context code is already written
  against it.

## Design

Memory is deliberately provider-neutral and offline-friendly: trimming and token
estimation never call a provider, and summarization is an injected dependency.
This keeps the working-context logic fully testable with the `MockProvider` and
in-memory database. See [LLM.md](./LLM.md) for how memory fits the request flow.
