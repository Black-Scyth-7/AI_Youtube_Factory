# AI YouTube Factory — Worker

**Celery** worker for background, scheduled, and (future) AI-pipeline jobs.

- **Broker:** RabbitMQ
- **Result backend:** Redis
- **Reliability:** late acks, reject-on-worker-lost, bounded retries, and a
  declared dead-letter queue for exhausted tasks.

## Run

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -e ".[dev]"

celery -A worker.celery_app:celery_app worker --loglevel=INFO
celery -A worker.celery_app:celery_app beat --loglevel=INFO   # scheduler
```

## Test

```bash
pytest
```

No business jobs are implemented in Phase 01 — only the app, a `ping` health
task, and DLQ scaffolding.
