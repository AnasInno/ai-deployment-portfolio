# Anas Abdi - AI Deployment Portfolio

Public-safe portfolio for AI Deployment Engineer, Forward Deployed Engineer, and Applied AI Engineer roles.

Live site: https://anasinno.github.io/ai-deployment-portfolio/

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
