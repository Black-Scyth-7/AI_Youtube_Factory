# Video pipeline

The product itself: an idea becomes a researched, scripted, narrated, rendered,
published video — and then the system learns from how it performed.

```
research → script → voiceover → render → publish → analytics → learning
```

## Providers

The pipeline needs four things it cannot do itself. Each is a Protocol in
`app/core/pipeline/interfaces.py` with a deterministic mock, exactly as the LLM
framework does:

| Capability  | Contract            | Produces                        |
| ----------- | ------------------- | ------------------------------- |
| `speech`    | `SpeechProvider`    | narration audio in storage      |
| `render`    | `RenderProvider`    | a video file in storage         |
| `publish`   | `PublishProvider`   | an external id and a public URL |
| `analytics` | `AnalyticsProvider` | one day of metrics              |

Providers resolve through a registry by configuration:

```bash
PIPELINE_SPEECH_PROVIDER=mock
PIPELINE_RENDER_PROVIDER=mock
PIPELINE_PUBLISH_PROVIDER=mock
PIPELINE_ANALYTICS_PROVIDER=mock
```

`mock` is always registered, so **the entire pipeline runs offline** and CI needs
no TTS key, renderer, or YouTube account. Mocks are deterministic — the same
script always yields the same duration, the same video key always yields the same
published id — and they write **real bytes through the storage layer**, so the
storage path is exercised rather than stubbed.

Registering a real provider is the whole point of the registry:

```python
register_provider(ProviderKind.PUBLISH, "youtube", YouTubeProvider)
```

Nothing in the pipeline changes.

## Stages are separate methods

Each stage is its own method rather than one long function, so a run resumes at
the stage that failed. Rendering is the expensive step; repeating it because
_publishing_ failed would waste it.

`PipelineRun.artifacts` accumulates what each stage produced, keyed by stage
name, which is how later stages find earlier output — `render` reads the
voiceover's storage key from `artifacts["voiceover"]`.

For tests and simple cases, `run_to_completion()` walks every stage in one call.

## Publishing

One `Publication` per video per platform, enforced by a unique constraint, so a
re-publish updates the existing row instead of accumulating duplicates. A
provider failure is recorded on the publication — status `failed` plus the error
— and then re-raised, so the caller knows and the row explains why.

Rendering records a `video_render` usage event, so a plan's render quota is
enforced against real work.

## Analytics and learning

`collect_analytics` upserts on `(publication_id, measured_on)`: re-fetching a day
updates that row rather than appending a duplicate. Different days are separate
rows, so the series is preserved.

`learn` turns the latest snapshot into `PerformanceLesson` rows. The rules are
deliberately simple and explainable — an agent can consult them and a human can
see why each was recorded:

- Click-through below target → the title or thumbnail is the likely limit.
- Watch time against duration → an average retention observation.

`click_through_rate` returns `0.0` for zero impressions, because no data is not
the same as a zero rate; the property makes that explicit rather than dividing by
zero.

## Schema

Migration `0007_pipeline` adds five tables:

```
research_note  pipeline_run  publication  analytics_record  performance_lesson
```

Verified against PostgreSQL 17: `upgrade head` creates all five, `downgrade
0006_workflow` removes them.

## What is still mocked

Every external call. The mocks make the pipeline _complete and testable_, not
_real_. Shipping needs genuine providers for TTS, rendering, and the YouTube Data
API, plus OAuth for channel access — each of which slots in behind the Protocol
it already has.
