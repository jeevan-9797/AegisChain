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

The repository is currently a generated CAP scaffold. It has no domain model or service yet, so a successful server start does not mean AegisChain workflows are implemented. Once the SQLite model is added, developers should use the local SQLite configuration and documented seed data for the demonstration.

## Test and quality checks

There is currently no test script, test suite, or lint script in `package.json`. Do not treat the absence of a test command as a passing test result. As application phases add features, add focused automated tests and scripts for domain behavior, services, and acceptance criteria. Record the exact commands and outcomes in the phase's completion notes.

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
