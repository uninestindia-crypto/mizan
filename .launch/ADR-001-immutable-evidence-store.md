# ADR-001 — Immutable content-addressed filesystem evidence

STATUS: accepted  
DATE: 2026-08-20

## Context

QuantOS must reproduce datasets, trials, models, financial results, promotions, and paper/shadow sessions on one Windows workstation. The PRD excludes a database for this release and requires rollback without rewriting evidence.

## Decision

Use canonical JSON/JSONL content addressed by SHA-256, immutable manifest directories, atomic same-volume publication, append-only lifecycle events, and small atomic active-reference files under `%LOCALAPPDATA%\QuantOS\evidence\v1`.

Persist model coefficients and preprocessing arrays as typed canonical data, never executable/native object serialization. Treat a manifest as published only after all referenced blobs pass hash verification.

## Rejected alternatives

- **SQLite now:** good transactional semantics, but adds schema migrations, backup/recovery behavior, an alternate canonical export contract, and database-specific corruption/locking work before a single-user release needs queries at that scale.
- **Pickle/joblib model files:** convenient, but unsafe for untrusted input, coupled to Python implementation details, and poor evidence for cross-version review.
- **Mutable JSON files by logical name:** simple, but cannot prove what a completed result consumed and makes rollback an overwrite.
- **Cloud/object storage:** outside local-only scope and introduces identity, tenancy, network, cost, and data-residency obligations.

## Consequences

Reads and replay are simple and inspectable; deduplication and rollback are natural. The application must implement canonicalization, atomic publication, lease recovery, retention, and bounded collection indexing carefully. If later scale proves file indexing inadequate, a database may be introduced as a rebuildable index over immutable evidence; the evidence contract remains the source of truth.
