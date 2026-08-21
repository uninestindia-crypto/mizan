# Slice 6 Evidence — Versioned Operation API & Local Trust Boundary

STATUS: PASS  
DATE: 2026-08-21  
REVISION: Current Main

## Verification Results

- `tests/test_server_api.py`: 47 passed.
- `tests/test_server_supervisor.py`: 9 passed.
- Total Slice 6 suite: **56 passed in 22.11s (100% PASS)**.

## Key Claims Verified

1. **Host & Origin Rejection**: Host headers like `evil.com`, `0.0.0.0`, or unauthorized external IP addresses return `403 Forbidden` / `400 Bad Request`.
2. **Supervised Worker Lifecycle**: Long-running background operations spawn dedicated processes, report heartbeats, and complete with `SUCCESS`.
3. **Graceful Cancellation**: Invoking `/api/v1/operations/{op_id}/cancel` halts worker execution and sets state to `CANCELLED`.
4. **Crash Recovery**: Terminating worker subprocesses triggers heartbeat timeout detection and marks operations `FAILED` without server crash.
