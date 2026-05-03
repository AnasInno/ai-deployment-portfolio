# Verification

Last checked: 2026-05-03.

## Commands

```bash
make test
GATEWAY_DB_PATH=/tmp/ai-deployment-gateway-smoke.db GATEWAY_API_KEY=smoke-key \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8033
GATEWAY_API_KEY=smoke-key python3 scripts/smoke_gateway.py --base-url http://127.0.0.1:8033
```

## Results

- `pytest`: 9 passed.
- Local FastAPI boot: succeeded on `127.0.0.1:8033` using the existing Python 3.9 virtualenv.
- Health endpoint returned SQLite storage plus document/deployment/eval/audit counts.
- Ingest endpoint stored a TeachClaw evidence document.
- Unauthenticated ingest returned `401` when `GATEWAY_API_KEY` was configured.
- Eval endpoint returned `status: pass` with expected terms and expected source ID.
- Deployment registration returned `deployment_id: teachclaw-local`.
- Readiness endpoint returned `status: pass`, no blockers, no warnings.
- Metrics endpoint returned one document, one deployment, one eval run, three audit events, and `last_eval_pass_rate: 1.0`.
- SQLite-backed test storage was reset between tests.
- Optional API-key protection returned `401` without `X-API-Key` and accepted the configured key.
- Audit endpoint returned write events for ingestion, deployment registration, and eval runs.
- Smoke script passed against the local server using `sample/evidence.json`.

## Not Verified

- Docker build was not verified locally because Docker is not installed on this machine.
- Render deployment was not run; `render.yaml` is a blueprint for a future hosted demo.
