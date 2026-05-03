# Deployment Notes

This mini-project is intentionally small, but it has the bones expected in a production AI deployment service.

## Local

```bash
make install
cp .env.example .env
make test
make smoke
make run
```

Useful environment variables:

| Variable | Purpose |
| --- | --- |
| `GATEWAY_DB_PATH` | SQLite path. Defaults to `data/gateway.db`. |
| `GATEWAY_API_KEY` | Optional write-key. When set, write endpoints require `X-API-Key`. |
| `LOG_LEVEL` | Python logging level for structured audit logs. |

## Docker

```bash
make docker-build
make docker-run
```

Docker Compose mounts a named volume at `/data` and sets `GATEWAY_DB_PATH=/data/gateway.db`.
Set `GATEWAY_API_KEY` in the shell before `docker compose up` if you want write protection.

Health check:

```bash
curl http://localhost:8000/health
```

Readiness check:

```bash
curl http://localhost:8000/deployments/teachclaw-local/readiness
```

Metrics:

```bash
curl http://localhost:8000/metrics
```

Audit events:

```bash
curl http://localhost:8000/audit/events
```

## Smoke Script

Run this after starting the API. If `GATEWAY_API_KEY` is set for the service, pass the same value to the script.

```bash
GATEWAY_API_KEY=smoke-key python3 scripts/smoke_gateway.py --base-url http://127.0.0.1:8000
```

The smoke script runs the reviewer-facing path from `sample/evidence.json`:

1. Health check.
2. Rejected unauthenticated write when an API key is configured.
3. Evidence ingestion.
4. Source-grounded retrieval.
5. Deployment registration.
6. Eval run.
7. Readiness check.
8. Metrics and audit-event inspection.

## Render Blueprint

The root `render.yaml` defines a Docker web service with:

- `dockerContext: ./gateway`
- `dockerfilePath: ./gateway/Dockerfile`
- `healthCheckPath: /health`
- persistent disk mounted at `/data`
- `GATEWAY_DB_PATH=/data/gateway.db`
- manually supplied `GATEWAY_API_KEY`

This is a deployment blueprint, not a live deployment record. A real hosted demo still needs a Render account connection and secret value.

## CI

GitHub Actions workflow:

```text
.github/workflows/mini-project-ci.yml
```

It installs dependencies and runs `pytest` from `mini-project/`.

## Hosted Deployment Options

Good lightweight options:

- Render web service from Dockerfile
- Fly.io app from Dockerfile
- Railway service from Dockerfile
- Small VPS with Docker Compose and reverse proxy

## Production Hardening Checklist

- Replace SQLite with Postgres or object storage plus vector index for shared production deployments.
- Add OAuth or signed service tokens for multi-user environments.
- Add request IDs and tracing across retrieval/eval calls.
- Add latency, retrieval quality, and error-rate metrics.
- Add proper embedding model or managed vector store.
- Add rate limits and max document size.
- Add separate staging/prod configs.
- Add deployment approvals with explicit human sign-off for risky launches.
- Store rollback artifacts and eval reports with immutable timestamps.
