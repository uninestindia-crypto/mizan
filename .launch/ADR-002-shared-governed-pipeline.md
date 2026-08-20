# ADR-002 — One governed domain pipeline for every interface

STATUS: accepted  
DATE: 2026-08-20

## Context

The current API, browser, strategies, backtest, and utilities can calculate or present overlapping concepts independently. The PRD requires desktop/API equality and evidence replay.

## Decision

Create framework-independent domain/application contracts for datasets, risk, training, validation, financial execution, sessions, and evidence. FastAPI maps strict DTOs into commands and maps stored domain results out. The browser polls those resources. Exports package the same stored results. Replay invokes the same pure stages and compares hashes.

Risk versions, financial rules, data manifests, model artifacts, and execution mode are explicit command inputs. No interface gets a private calculation shortcut.

## Rejected alternatives

- **Keep route handlers as orchestration:** fast initially, but process-global state, synchronous work, and route-specific result construction make replay and concurrency unsafe.
- **Let the browser calculate analytics:** duplicates financial truth and makes export/API equivalence unprovable.
- **Separate training service:** unnecessary distribution for one local user; adds network failure, deployment, and version skew.
- **Rewrite the whole application:** discards tested ledger/risk/analytics primitives. The slice plan instead wraps and replaces them through vertical seams.

## Consequences

The application gains more explicit types and adapters, but calculations become testable without HTTP or the filesystem. Existing unversioned routes require a temporary adapter and then removal before release.
