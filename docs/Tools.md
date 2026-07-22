# Agent Tools & Policies

## Tool framework (`tools/`)

An `AgentTool` couples a JSON-schema declaration with an async implementation and
the full lifecycle the spec requires:

| Method | Purpose |
| --- | --- |
| `schema()` | Name + description + input schema (for discovery/LLM). |
| `describe()` | One-line human description. |
| `validate(args)` | Check required arguments; raise on error. |
| `execute(args)` | Run the tool, return text. |
| `rollback(args, result)` | Undo a mutating execution (no-op for pure tools). |
| `health()` | Whether the tool is ready. |

`AgentToolRegistry.run(name, args)` validates, executes, and captures a
`ToolOutcome` (output, success, error, duration). Tools bridge to the Phase 04
LLM tool-calling layer via `AgentTool.to_llm_tool()`, so the same tool can be
offered to Claude.

### Built-in tools

Provider-independent and offline-safe: `current_time`, `calculator` (safe
arithmetic via a character allow-list), `uuid_generator`, `json_parser`,
`number_format`. `http_request` (network GET) exists but is **off the default
allow-list** — a policy must permit it. YouTube-specific tools register the same
way in a later phase.

### Tool execution flow

Discover → validate arguments → policy check → execute → capture output → log →
audit (`agent_tool_execution`) → publish `ToolExecuted`. Failures raise inside the
executor and count against the task's retries.

## Policies (`policies/`)

`AgentPolicy` bounds a run; `PolicyEnforcer` enforces it and tracks cumulative
usage:

| Limit | Meaning |
| --- | --- |
| `allowed_tools` / `forbidden_tools` | Tool allow / deny lists. |
| `max_cost_usd` | Spend ceiling (raises `PolicyViolationError`). |
| `max_tokens` | Token ceiling. |
| `max_steps` | Max executed tasks. |
| `max_retries` | Clamps per-task retries. |
| `task_timeout_seconds` | Per-task hard timeout. |
| `require_approval_for_mutations` | Mutating tools need `grant_approval()` first. |

Mutating tools raise `ApprovalRequiredError` until approved — the seam for a
human-in-the-loop gate. The `sandbox/` module adds an independent per-action
timeout + concurrency limit for defense in depth.
