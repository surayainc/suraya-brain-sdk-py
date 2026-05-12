# suraya-brain-sdk

Python client for the Suraya brain. MIT-licensed. Sister to the TypeScript `@surayaorg/brain-sdk` package.

> **Sandbox note.** This package lives in the suraya meta repo at `apps/brain-sdk-py/` until its dedicated repo at `surayainc/suraya-brain-sdk-py` exists (OQ-12 follow-up). On creation, the package moves and PyPI publish points at the new repo.

## Install

```bash
pip install suraya-brain-sdk
```

## Quick start

```python
from suraya_brain_sdk import BrainClient, ObservationInput
import os

brain = BrainClient(
    base_url="https://brain.suraya.ai",
    project_slug="my-project",
    hmac_secret=os.environ["SURAYA_BRAIN_WEBHOOK_SECRET_MY_PROJECT"],
)

results = brain.retrieve(q="supabase pooler create index concurrently", top_k=10)
for r in results.results:
    print(r.representative_summary, round(r.similarity, 3))

brain.emit_observation(ObservationInput(
    type="decision",
    representative_summary="Picked Postgres over MongoDB for the new analytics service",
    criticality="medium",
    actor_handle="kareem",
))
```

## API

Same wire contract as `@surayaorg/brain-sdk` (TypeScript):

- `retrieve(q, top_k=10, scope=None)` — semantic search over `memory_nodes`
- `emit_observation(observation)` — ship a typed observation
- `health()` — endpoint reachability + version probe

## Auth

Pass exactly one of:

- `hmac_secret=<service token>` — long-lived per-project HMAC
- `bootstrap_token=<F6 bootstrap>` — ephemeral device-bound auth from the credential bridge

## Errors

All failures raise `BrainError` with a discriminated `kind`:

```python
from suraya_brain_sdk import BrainError

try:
    brain.retrieve("…")
except BrainError as e:
    if e.kind == "rate_limited":
        time.sleep(e.retry_after_seconds or 5)
    elif e.kind == "invalid_signature":
        raise
```

## Status (2026-05-23)

- ✅ Scaffolded
- ✅ Sync `retrieve()` + `emit_observation()` + `health()`
- ❌ Async client (`AsyncBrainClient`) — queued
- ❌ PyPI publish — gated on operator action (OQ-16 — register `suraya-brain-sdk` namespace + token)
