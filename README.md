# BabelBeam

BabelBeam is a classroom interpretation product for parish teaching. The catechist speaks English. Students are meant to hear Spanish audio, read Spanish captions, and ask teacher-approved questions. This repository is the Phase 0 foundation: a local app, API, and worker skeleton. It does not run live translation or billing.

## What is simulated

`PROVIDER_MODE=mock` is the default. The site shows a simulated-mode banner. The worker returns labeled mock text and does not call OpenAI, LiveKit, or Stripe. Production startup refuses mock mode, example secrets, recording, minor sessions, and live billing.

## Windows

GNU make is optional. From the repository root:

```text
powershell -File scripts/bb.ps1 setup
copy .env.example .env
powershell -File scripts/bb.ps1 dev
```

`dev` starts Postgres, Redis, and Mailpit with Docker, then the API on port 8000, the worker, and the web app on port 5173. Mailpit's inbox is http://localhost:8025.

Other commands use the same script: `migrate`, `seed`, `lint`, `typecheck`, `test`, `test-e2e`, `provider-check`, `billing-test`, and `build`.

If Python, Node, or Docker is missing, the command stops and names the missing tool. Install Python 3.12, Node 22 or newer, and Docker Desktop.

## Unix

```text
make setup
cp .env.example .env
make dev
```

## Checks

`provider-check` and `billing-test` exit 2 on purpose. They explain the missing credentials and do not call paid services. `make test` is the deterministic suite.

## Layout

- `apps/web`: React, TypeScript, Vite
- `services/backend`: FastAPI
- `services/worker`: mock provider adapters
- `packages/runtime`: shared settings and state names
- `docs`: specification, brochures, and build status
