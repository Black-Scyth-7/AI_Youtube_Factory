# Plugins

Third-party code that attaches to points in the pipeline and modifies what
passes through.

The whole design answers one question: **what stops a plugin from breaking the
host?**

- It cannot crash it — every invocation has an exception boundary, and a plugin
  that throws is recorded and skipped while the rest of the chain runs.
- It cannot hang it — every invocation has a timeout from its own manifest.
- It cannot reach what it never declared — capabilities are requested in the
  manifest and granted by the host, and privileged ones are refused by default.

## Manifest

A plugin declares itself before any of its code runs, so one asking for
something it should not have is rejected at load time rather than at call time.

```python
from app.core.plugins import Capability, HookName, PluginManifest, register_plugin

MANIFEST = PluginManifest(
    name="my-plugin",            # lowercase slug; also a metric label
    version="1.0.0",             # semantic version
    display_name="My plugin",
    description="What it does.",
    hooks=[HookName.BEFORE_PUBLISH],
    capabilities=[Capability.READ_CONTEXT, Capability.WRITE_CONTEXT],
    priority=50,                 # lower runs first
    timeout_seconds=5.0,
)


async def handler(context):
    title = context.payload.get("title", "")
    stripped = title.strip()
    return {"title": stripped} if stripped != title else None


register_plugin(MANIFEST, {HookName.BEFORE_PUBLISH: handler})
```

The manifest is frozen and rejects unknown fields — a misspelled key would
otherwise be silently ignored, and a plugin must not be able to widen its own
declaration after loading.

Registration fails if a declared hook has no handler, or a handler is supplied
for a hook the manifest never declared. A handler nobody declared would run
without appearing in an audit of what the plugin does.

## Hooks

`video.created` · `script.generated` · `render.before` · `render.after` ·
`publish.before` · `publish.after` · `analytics.collected`

A closed set. Arbitrary names would mean a typo silently never runs, which is
the worst failure mode for something meant to change behaviour.

## Capabilities

| Capability      | Grants                                | Privileged |
| --------------- | ------------------------------------- | ---------- |
| `read_context`  | Read the object the hook fired for    | no         |
| `write_context` | Return modifications to it            | no         |
| `storage`       | The plugin's own namespaced storage   | no         |
| `llm`           | Call the LLM framework                | **yes**    |
| `network`       | Outbound HTTP                         | **yes**    |

Privileged capabilities are refused unless an operator names the plugin in
`PLUGIN_PRIVILEGED_ALLOWLIST`. A plugin cannot reach the network or spend money
on inference merely by asking to — which is what keeps a formatter or a scorer
unable to exfiltrate anything even if its code is hostile.

Refused capabilities are shown in the console rather than hidden: a plugin that
asked for the network and did not get it explains why it is not doing what its
README claims.

## Dispatch

Plugins run **sequentially**, ordered by priority then name, and each sees the
previous one's output — which is what makes a chain of transformations
meaningful. Ordering by name breaks ties, so a given set always runs in the same
order rather than in whatever order they happened to be imported.

A handler receives a **copy** of the payload and returns a patch, or `None` for
"no change". Mutating the payload in place does not propagate: changes travel
through the patch mechanism, where they are recorded, rather than invisibly.

Handlers are given a plain dict, never an ORM object. Handing a plugin a live
entity would let it write to the database through a relationship, entirely
outside the capability model.

`dispatch` never raises. A failing plugin produces a result with `ok=False`, and
the chain continues.

## Built-ins

| Plugin              | Hook             | Does                                                     |
| ------------------- | ---------------- | -------------------------------------------------------- |
| `title-case`        | `video.created`  | Headline capitalisation, preserving acronyms             |
| `hashtag-extract`   | `publish.before` | Collects hashtags from the description into tags         |
| `description-guard` | `publish.before` | Truncates to YouTube's 5000-character limit on a word boundary |

`hashtag-extract` has a lower priority than `description-guard`, so tags are
read from the full text rather than from whatever survived truncation.

## Console

`/dashboard/plugins` lists what is installed, what each was granted and refused,
and which plugins are attached to each hook — including hooks with nothing
attached, because "no plugin runs here" is the useful answer when a plugin
appears not to be firing.

Installation is **not** exposed over the API. Loading a plugin means loading
third-party code into the server process; a button for it would turn any account
takeover into remote code execution.
