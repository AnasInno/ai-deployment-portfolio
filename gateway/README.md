# Mini Project: AI Deployment Gateway

Small public-safe FastAPI service for proving AI deployment fundamentals without exposing TeachClaw code.

## Goal

Demonstrate the stack hiring teams keep asking for:

- Python API
- document ingestion with tags
- lightweight retrieval with source IDs
- eval endpoint with pass/block status
- deployment registration
- readiness gates
- metrics endpoint
- health checks
- SQLite persistence
- optional API-key auth for write endpoints
- audit events for deployment/eval activity
- repeatable smoke script
- Render blueprint for hosted demo setup
- Docker
- CI
- deployment-ready structure

This is deliberately small. The point is to show clean deployment discipline, not build a fake enterprise platform. It mirrors the practical loop hiring teams keep asking for: register a deployment, ingest evidence, run evals, keep an audit trail, then decide whether the release is ready.

## Endpoints

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/health` | GET | Service health plus document/deployment/eval counts |
| `/ingest` | POST | Add documents to SQLite-backed store |
| `/ask` | POST | Retrieve relevant snippets and return a grounded answer stub |
| `/eval/run` | POST | Run source/term evals against the retrieval layer |
| `/deployments/register` | POST | Register deployment owner, environment, rollback plan, and eval threshold |
| `/deployments/{deployment_id}/readiness` | GET | Return pass/block/needs-judgement launch status |
| `/metrics` | GET | Return lightweight operational metrics |
| `/audit/events` | GET | Inspect recent write-side audit events |

## Run Locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

By default the service stores SQLite state at `data/gateway.db`. Set `GATEWAY_API_KEY`
to require `X-API-Key` on `/ingest`, `/eval/run`, and `/deployments/register`.

## Docker

```bash
docker build -t ai-deployment-service .
docker run --rm -p 8000:8000 ai-deployment-service
```

## Example

```bash
curl -X POST http://localhost:8000/ingest \
  -H 'Content-Type: application/json' \
  -d '{"documents":[{"id":"teachclaw","text":"TeachClaw routes teacher requests into worksheets, PPTs, marking and feedback.","tags":["teacher-workflow","artifacts"]}]}'

curl -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"What does TeachClaw route?"}'
```

Readiness-gated deployment:

```bash
curl -X POST http://localhost:8000/deployments/register \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "TeachClaw",
    "environment": "local",
    "owner": "Anas Abdi",
    "rollback_plan": "Revert to last validated route bundle and rerun gateway smoke tests.",
    "risk_notes": ["Artifact contracts can drift across runtime layers."],
    "required_eval_pass_rate": 1.0
  }'

curl -X POST http://localhost:8000/eval/run \
  -H 'Content-Type: application/json' \
  -d '{"cases":[{"question":"What does TeachClaw route?","expected_terms":["worksheets","marking"],"expected_source_ids":["teachclaw"]}]}'

curl http://localhost:8000/deployments/teachclaw-local/readiness

curl http://localhost:8000/audit/events
```

## Smoke Check

With the API running:

```bash
GATEWAY_API_KEY=smoke-key python3 scripts/smoke_gateway.py --base-url http://127.0.0.1:8000
```

The smoke script uses `sample/evidence.json` to prove the full path: health, rejected unauthenticated write, ingestion, retrieval, deployment registration, eval, readiness, metrics, and audit events.

## Hosted Demo Blueprint

The repo includes `../render.yaml` for a lightweight Render web service using this Dockerfile, `/health` as the health check, a persistent `/data` disk, and a manually supplied `GATEWAY_API_KEY`.

## Interview Talking Point

This mirrors the deployment shape of larger AI systems:

- separate health and metrics surfaces
- explicit schemas
- deterministic retrieval with source IDs
- eval endpoint with launch status
- readiness gate before deployment
- rollback plan captured with the deployment profile
- persistent SQLite state for docs, deployments, eval runs, and audit events
- optional API-key protection for write endpoints
- structured JSON audit logs
- sample payload and smoke script for reviewer-friendly proof
- containerized runtime
- CI test lane

The next step would be replacing the local token-overlap retriever with embeddings/vector search, adding rate limits, and deploying it behind a hosted HTTPS endpoint with immutable eval reports.

## Verification

See `VERIFICATION.md` for the latest local test and smoke-check record.
