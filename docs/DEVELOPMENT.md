# AegisChain Development Guide

## Prerequisites

- Node.js and npm compatible with the installed SAP CAP dependencies.
- Git.
- For local CAP development, install the project dependencies from the repository root. The intended local database is SQLite; no production SAP credentials are needed for a local mock-data demo.
- SAP HANA Cloud, SAP AI Launchpad / Generative AI Hub, and SAP Build Process Automation access are not required by the current scaffold. They will be needed only for integrations that are implemented and configured against provisioned services.

## Local setup and run

From the repository root:

```sh
npm install
npm start
```

The current `start` script runs `cds-serve`. During development, with the CAP development kit (`cds` CLI) available in `PATH`, CAP's watch mode can be started with:

```sh
cds watch
```

The local SQLite model and seed data are under `db/`. The CAP service layer is under `srv/`. Use the documented local SQLite workflow for development; no production SAP credentials are needed for the mock-data demonstration.

## Optional standalone Python evaluator service

The Python evaluator can run as an HTTP prototype without CAP or BTP credentials. From the repository root, install the pinned dependencies and start it in a separate terminal:

```powershell
& 'C:\Users\jeeva\AppData\Local\Python\bin\python.exe' -m pip install -r requirements.txt
& 'C:\Users\jeeva\AppData\Local\Python\bin\python.exe' -m ml.http_service
```

It listens on `http://localhost:8082` by default. Check `/healthz` and `/readyz`; the evaluation endpoint is `POST /internal/v1/evaluate`. Generate one random secret of at least 32 bytes and inject the same value as `AEGISCHAIN_EVALUATOR_TOKEN` in the Python terminal and `AEGISCHAIN_ML_TOKEN` in the CAP terminal. Do not save the secret in repository files. Health and readiness endpoints are public for probes; evaluation requires bearer authentication. Keep the service on a private network.

To point CAP at it, set `AEGISCHAIN_ML_MODE=remote`, `AEGISCHAIN_ML_URL=http://localhost:8082/internal/v1/evaluate`, `AEGISCHAIN_ML_TOKEN` to that same secret, and optionally `AEGISCHAIN_ML_TIMEOUT_MS=15000` before starting CAP. Local subprocess mode remains the default. Remote mode does not fall back to local execution when misconfigured or unavailable. This is a shared-secret prototype; OAuth/XSUAA requires a selected BTP service plan, scopes, and bindings that are not configured in this repository.

## Local live-demo ports

For the ML-enabled live demo on Windows PowerShell, start CAP and Fiori in separate terminals. The live UI5 proxy configurations target CAP on port 4404; Fiori's default port is 8080, so pass 8081 when using the verified demo URL:

```powershell
# Terminal 1, repository root
$env:PORT = '4404'
$env:AEGISCHAIN_PYTHON = 'C:\Users\jeeva\AppData\Local\Python\bin\python.exe'
npm start
```

```powershell
# Terminal 2
Set-Location app/controltower
npm start -- --port 8081
```

Open `http://localhost:8081/index.html?mode=live`; CAP is at `http://localhost:4404/odata/v4/aegis`. The existing service on port 4004 is a legacy instance with stale metadata and is not targeted by the Fiori startup configurations. Leave it running if it may hold demo data. For mock mode, open `http://localhost:8081/index.html?mode=mock` without starting CAP.

## Test and quality checks

Run the current automated checks with:

```sh
npm test
```

The suite validates CAP model loading/compilation and exercises the OData service over HTTP against an isolated CAP process using its default in-memory SQLite database and seed data. The tests cover seeded reads, signal creation and impact links, signal validation, recommendation creation, approval/rejection, repeated decisions, and direct recommendation update rejection. CAP's local mocked authentication is used; production authentication, authorization roles, AI/BPA integrations, and external action execution are not covered. There is no lint script yet.

The repository includes an ESLint configuration extending SAP CAP's recommended rules. When linting is configured, use the project script rather than assuming a global ESLint installation.

## Configuration and secrets

- Keep credentials, tokens, private endpoint configuration, and local secret files out of Git.
- Use environment-specific configuration or the appropriate SAP destination/credential mechanism for external services.
- Do not commit generated local databases or production data. The existing `.gitignore` excludes SQLite database files.
- Label mock data and mock AI/approval behavior in the demo.

## Git workflow for phased delivery

1. Start from the agreed project branch and inspect `git status --short --branch` before editing.
2. Implement one agreed phase at a time. Preserve unrelated working-tree changes; do not use reset, clean, or force-push to resolve conflicts.
3. Review `git diff` and run the relevant tests/quality checks available for that phase.
4. Stage only the files belonging to the completed phase and create a descriptive commit, for example `docs: establish AegisChain product foundation`.
5. Before pulling or pushing, inspect local and remote histories. If histories are unrelated or diverged, coordinate a merge plan and preserve both sides; never force-push or rewrite shared history without an explicit decision.

## Current repository state

At the time this guide was written, `main` has one local commit and `origin/main` has a different one-commit history with no common ancestor. The remote commit contains `README.md`, while the local generated scaffold contains `readme.md`. Do not perform a routine pull or push until the owner has chosen how to reconcile those histories. Preserve both commits and resolve the README case conflict deliberately as part of a merge review.

## Backend workflow assumptions

- Disruption type and severity values remain open vocabularies because the MVP documents no allowed list. The service stores supplied values without inferring a taxonomy.
- A disruption signal must identify at least one existing affected shipment or inventory item. CAP/database referential integrity validates the links.
- Recommendations are caller-provided advisory records; no recommendation generation logic is included. New records always start pending.
- A decision is allowed once, from pending to approved or rejected. The request user's CAP identity is recorded; authentication and enterprise approver roles are not configured in this demo phase.
- Approval records a decision only. It never executes or writes a recovery action to S/4HANA.
