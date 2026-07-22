# Conversations

A conversation is a persisted, ordered sequence of messages plus a system prompt.
The framework separates the **runtime** representation (used while a turn is
processed) from **persistence** (the durable transcript).

## Runtime object

`app/core/llm/conversation.py` — a lightweight, provider-neutral dataclass:

```python
convo = Conversation(system="You are helpful.")
convo.add_user("Hello")
convo.add_assistant("Hi there!")
request = convo.to_request(model="claude-opus-4-8", max_tokens=1024)
```

- `add()` / `add_user()` / `add_assistant()` accumulate `Message` objects.
- `to_request(model, max_tokens, **kwargs)` builds a `ChatRequest`, moving the
  system prompt into the request's `system` field and excluding any `SYSTEM`
  messages from the message list (the Anthropic API takes `system` separately).

## Persistence

`app/services/llm/conversation_service.py` over the `Conversation`,
`ConversationMessage`, and `ConversationSummary` models:

- `create(organization_id, actor_id, model=, system=, title=)` — starts a
  conversation. The model defaults to `LLM_DEFAULT_MODEL`.
- `append(conversation_id, role, content, tokens=, tool_calls=)` — appends a
  message. `next_sequence()` assigns a gap-free ordering index per conversation.
- `load_runtime(conversation_id)` — rebuilds the in-memory `Conversation` from
  stored messages so a new turn can continue an existing thread.
- `get_or_404(...)` — fetches a conversation, treating soft-deleted rows as
  missing.

> The `Conversation.conversation_metadata` attribute maps to the SQL column
> `metadata` (SQLAlchemy reserves the attribute name `metadata`), so arbitrary
> per-conversation metadata is stored without a name clash.

## Continuing a thread through the API

```
POST /api/v1/llm/conversations            -> { id, model, ... }
POST /api/v1/llm/chat  { conversation_id } -> accounted turn, linked to the thread
GET  /api/v1/llm/conversations/{id}/messages -> ordered transcript
```

The frontend **Conversation viewer** (`/dashboard/llm/conversations`) loads a
transcript by id and renders each message with its role, sequence, and token
count.

## Context management

Trimming older turns to a token budget and summarizing overflow is handled by the
memory layer — see [Memory.md](./Memory.md).
