# Slice 6 Contract — Versioned Operation API & Local Trust Boundary

STATUS: FROZEN FOR IMPLEMENTATION  
DATE: 2026-08-21

## Inputs & Invariants

- **Loopback Trust Boundary**: FastAPI `/api/v1` server bound exclusively to `127.0.0.1` and `localhost`. Host header verification strictly rejects non-local hostnames, IP spoofing, and DNS rebinding attacks.
- **CORS & Anti-CSRF Protection**: Origin verification and anti-CSRF token checking on all state-mutating HTTP methods.
- **Worker Process Supervision**: Background worker supervisor spawns isolated subprocesses for long-running quantitative workloads (training, data sync, backtests), tracks heartbeats via inter-process pipes, handles cancellation tokens gracefully, and exposes idempotent polling via `/api/v1/operations/{op_id}`.
- **Crash Recovery**: Interrupted, crashed, or killed background worker processes are detected within heartbeat timeout windows, transitioning operation status to `FAILED` with failure logs preserved.
