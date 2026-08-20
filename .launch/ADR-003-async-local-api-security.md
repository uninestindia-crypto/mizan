# ADR-003 — Async resource API with loopback session defense

STATUS: accepted  
DATE: 2026-08-20

## Context

Training, validation, provider acquisition, Monte Carlo work, exports, and replay can exceed browser timeouts. The current server is unauthenticated, allows wildcard CORS, mutates global state, and blocks on work.

## Decision

Expose `/api/v1` resources. Long work returns `202` and an operation `Location`; clients poll a side-effect-free operation resource and can create an idempotent cancellation sub-resource. Require idempotency keys on unsafe writes and optimistic concurrency on active references. Run governed work in one supervised Windows-spawned child process with five-second heartbeats, cooperative cancellation, and staging-only write access; the server event loop never performs the CPU-heavy work.

Bind only to loopback, enforce exact-origin CORS/Host checks, and require an ephemeral same-origin session header on unsafe requests. Add one error body, request IDs, strict bounded inputs, security headers, and a one-operation compute lease.

## Rejected alternatives

- **Synchronous HTTP until completion:** fragile under slow provider/model work and cannot meet progress/cancellation criteria.
- **WebSockets first:** adds reconnection, ordering, and packaging complexity. Polling at bounded intervals satisfies the local release; events remain ordered in evidence.
- **Wildcard CORS because the server is local:** permits browser-based drive-by requests against a loopback service.
- **Full account authentication:** does not defend against an attacker controlling the same Windows account and is unnecessary for a local single-user release. Remote or multi-user exposure requires a new design.

## Consequences

The UI needs operation polling and token bootstrapping. Automated contract tests must cover idempotency, CORS, Host checks, cancellation, rate limits, errors, and stale ETags. Local hostile-process protection remains explicitly out of scope.
