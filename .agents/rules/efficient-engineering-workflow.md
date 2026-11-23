---
trigger: always_on
---

# DSS-PIK Efficient Engineering Workflow (Permanent Rule)

Apply these engineering standards across all DSS-PIK development sessions alongside `.agents/rules/dss-pik-architecture.md`:

## 1. Selective Inspection
- Inspect only files, modules, and dependencies directly relevant to the task.
- Reuse valid prior verification results and documentation; do not re-audit the entire codebase or re-run passing checks when affected code/dependencies have not changed.

## 2. Risk-Based Testing
- **Level 1 — Quick Check** (labels, text, logos, CSS, docs, simple config): verify only the changed artifact and required build.
- **Level 2 — Targeted Test** (API, DB queries, auth, middleware, data upload/processing, frontend-backend integration): run only tests covering the modified module and immediate integration.
- **Level 3 — Full Regression** (architecture changes, DB schema migrations, auth/security changes, core operational flows, new releases, production deployment): run the full regression and security suite.

## 3. Execution Optimization
- Reuse Docker BuildKit cache and existing `.venv` / `node_modules`; rebuild/restart only changed services (`--no-deps`).
- Batch independent read-only inspections and edits in parallel.
- Do not create standalone markdown reports for minor changes; update documentation only when operationally relevant.

## 4. Non-Negotiable Quality & Process
- Never skip security validation, ignore errors, use dummy data as production proof, modify databases without backups, or claim success without actual test evidence.
- Workflow: identify goal -> scope impacted files -> pick test level -> execute directly -> verify -> update docs only if needed.
- Execute safe, reversible technical steps directly; pause and request approval only for destructive operations, data loss risks, production changes, or credential/authorization actions.
