# Anas Abdi - AI Deployment Portfolio

[![Gateway CI](https://github.com/AnasInno/ai-deployment-portfolio/actions/workflows/gateway-ci.yml/badge.svg)](https://github.com/AnasInno/ai-deployment-portfolio/actions/workflows/gateway-ci.yml)
[![Public Link Check](https://github.com/AnasInno/ai-deployment-portfolio/actions/workflows/public-link-check.yml/badge.svg)](https://github.com/AnasInno/ai-deployment-portfolio/actions/workflows/public-link-check.yml)

Public-safe portfolio for AI Deployment Engineer, Forward Deployed Engineer, and Applied AI Engineer roles.

Live site: https://anasinno.github.io/ai-deployment-portfolio/

Hosted Gateway API docs: https://ai-gateway.shortlistops.co.uk/docs

Gateway health: https://ai-gateway.shortlistops.co.uk/health

Gateway readiness: https://ai-gateway.shortlistops.co.uk/deployments/teachclaw-local/readiness

## What This Contains

- Static recruiter portfolio at `index.html`
- Public-safe case studies under `case-studies/`
- CV PDF under `assets/`
- TeachClaw/OpenClaw architecture diagram under `assets/`
- Public-safe FastAPI AI Deployment Gateway under `gateway/`

## Gateway

The Gateway is a small FastAPI service showing deployment-readiness patterns:

- evidence ingestion
- source-grounded retrieval
- eval runs
- SQLite persistence
- API-key write protection
- audit events
- readiness gates
- metrics
- Docker
- CI
- smoke script

Run locally:

```bash
cd gateway
make install
make test
make run
```

## Public-Safety Boundary

This repo intentionally excludes private job-application trackers, phone number, secrets, internal TeachClaw source code, private IPs, and user/customer data.

See `PUBLIC_BOUNDARY.md` for the explicit public/private boundary. `public-safety.yml` enforces the most important leakage checks in CI.

## Verification

- GitHub Actions runs Gateway tests and a smoke check on every Gateway change.
- `public-link-check.yml` checks the live portfolio and public Gateway endpoints on push and daily schedule.
- The hosted Gateway is served through Cloudflare Tunnel from a local LaunchAgent-backed FastAPI process; the source remains Docker/Render-ready for a future independent cloud deployment.
