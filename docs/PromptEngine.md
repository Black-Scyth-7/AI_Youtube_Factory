# Prompt Engine

The prompt engine renders versioned, variable-driven templates with a **sandboxed
Jinja2** environment. The pure rendering/validation core is
`app/core/llm/prompts.py`; database-backed storage, versioning, and rollback live
in `app/services/llm/prompt_service.py` over the `PromptTemplate` /
`PromptVersion` models.

## Core types

- **`PromptVariable`** — a declared variable: `name`, `required` (default
  `True`), `default`, and an optional `description`.
- **`PromptSpec`** — a renderable definition: `name`, `template`, `variables`,
  `version`, plus `category` / `description` / `examples` metadata.
- **`PromptEngine`** — validates a context and renders a spec.

## Rendering

```python
from app.core.llm.prompts import PromptEngine, PromptSpec, PromptVariable

engine = PromptEngine()
spec = PromptSpec(
    name="greet",
    template="Hello {{ name }}, you are {{ role }}.",
    variables=[PromptVariable("name"), PromptVariable("role", default="user")],
)
engine.render(spec, {"name": "Ada"})  # -> "Hello Ada, you are user."
```

`validate_context()` applies declared defaults and raises `PromptRenderError`
(with the list of `missing` names) when a required variable is absent.
`render()` validates first, then renders. `render_string()` renders an ad-hoc
template string.

## Safety

- **Sandboxed** — `SandboxedEnvironment` blocks arbitrary attribute/method
  access on passed-in objects, so untrusted variable values cannot escape into
  code execution.
- **Strict undefined** — `StrictUndefined` turns an unknown `{{ var }}` into a
  render error instead of silently emitting an empty string.
- **No autoescape** — prompts are plain text, not HTML; escaping is off by
  design. Variables are still sanitized/validated before rendering.

Both `trim_blocks` and `lstrip_blocks` are enabled for clean whitespace around
control blocks.

## Versioning (service layer)

`PromptService` stores each template and its immutable versions:

- `create_template(...)` — creates a `PromptTemplate` and its first
  `PromptVersion`.
- `add_version(...)` — appends a new immutable version; the next version number
  is computed from the DB (`list_for_template`), stored in `version_number`.
- `render(template_id, context, version=None)` — loads the active/target version
  and renders it via the engine.
- `rollback(template_id, to_version)` — creates a **new** version whose body
  copies an older one (history is never mutated), returning the new version.

> **Why `version_number`, not `version`?** The Phase 03 `EntityMixin` owns a
> `version` column for optimistic locking (`version_id_col`). A business field
> named `version` collides with it and gets forced to `1` on every insert, so
> the prompt version number is stored as `version_number`.

## Auditability

Versions are immutable and rollbacks are additive, so the full history of a
prompt is preserved and every change is attributable via the mixin's
`created_by` / `updated_by`. See [LLM.md](./LLM.md) for the security model.
