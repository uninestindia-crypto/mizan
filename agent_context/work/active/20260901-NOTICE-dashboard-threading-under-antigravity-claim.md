# NOTICE: the live dashboard was made threaded, under an active Antigravity claim

STATUS: NOTICE (additive; no other record is edited)
DATE_UTC: 2026-09-01T10:45:00Z
FILED_BY: Claude Code, `20260901-1030Z-claude-seven-item-sweep.md`
ADDRESSED TO: owner of `20260826-antigravity-paper-trade-live-market-testing.md` (STATUS: ACTIVE),
  which owns `scripts/serve_live_dashboard.py`
SEVERITY: P2 Major, repaired

## Why I edited a path you own

Founder instruction, 2026-09-01, to work seven named open items in order. A repair to this file was
already sitting **uncommitted** in the shared checkout when I started -- someone had written it and
not committed it. Leaving it uncommitted is the worse option: a `git checkout` or a clean clone
silently restores the hang.

This follows the practice already established by three notices against the same record
(`20260830` engine, `20260830` session, `20260831` dashboard).

## The defect

`socketserver.TCPServer` serves exactly one request at a time. A browser holding a connection open
-- a keep-alive, a tab left on the page, a request that never completes -- blocks every request
behind it. The process stays alive and the port stays listening while nothing is answered.

Observed on 2026-09-01: process alive, `Get-NetTCPConnection` listening, page dead.

**This page carries the Start and Halt controls.** A hang here is not a cosmetic problem; it is the
founder unable to halt a running session from the interface built for it.

## What changed

- `ThreadedDashboardServer` (`ThreadingTCPServer`, `daemon_threads = True`) replaces the plain
  `TCPServer`.
- `build_dashboard_server()` extracted from `serve_dashboard()`, returning the bound server before
  it serves. `serve_forever` blocks, so nothing could otherwise observe the blocking behaviour.
  This is the same extraction-for-testability pattern as `f4d9c379`.
- The loopback bind is unchanged and now has a test holding it there.

## Tests, and the mutants that validate them

`tests/test_live_dashboard_server.py`, new file, 3 tests. Both mutants killed by the correct test:

| Mutant | Result |
|---|---|
| M1 the historical original, `socketserver.TCPServer` | **killed** by `..._answers_while_another_client_holds_a_connection_open` |
| M2 bound to `0.0.0.0` | **killed** by `..._binds_loopback_only` |

## Residual, stated rather than hidden

A dropped connection prints `Exception occurred during processing of request from ...` to stderr
from the handler thread. `ThreadingTCPServer` catches it and the server continues -- the test proves
the next request is answered -- but the traceback is noise in an operator's log, and I have not
quietened it. It is cosmetic and it is not fixed.

No file owned by your record other than `scripts/serve_live_dashboard.py` was touched.

## Second defect, found by the first repair's own test (P2, credential hygiene)

Adding a test that imports this module turned **7 unrelated tests red**:

```
tests/test_config_env.py::test_configured_env_file_reaches_the_upstox_client
tests/test_data_provenance.py::test_env_var_names_match_the_client_that_reads_them
tests/test_server_governed_completion.py::test_dataset_idempotency_replays_the_same_operation_after_supervisor_restart
tests/test_server_governed_journeys.py::test_dataset_acquisition_reports_missing_provider_credentials_without_publishing
tests/test_upstox_data.py::test_upstox_historical_request_without_token_raises_typed_error
tests/test_upstox_data.py::test_upstox_quote_request_without_token_raises_typed_error
tests/test_upstox_v3_acquisition.py::test_missing_access_token_returns_unauthorized_without_transport_call
```

Every one asserts behaviour **without** a token. `scripts/serve_live_dashboard.py:31-40` read `.env`
into `os.environ` at **module scope**, so `import scripts.serve_live_dashboard` wrote the founder's
real Upstox access token into the environment as a side effect of the import statement. By the time
those tests ran, there was a token.

Two things follow, and the second is the one that outlives this repair:

- The whole suite's credential-absence coverage was one `import` away from being vacuous. Nothing
  imported this script before today, so nothing had noticed.
- **A credential belongs in the environment of the process launched to use it**, not in the
  environment of anything that imports the module that reads it.

Repaired: the read is now `load_env_file()`, called from `main()`. Real behaviour is unchanged --
`main` loads before `serve_dashboard`, and the token is read at request time from `os.getenv`.

Three further tests, three further mutants, all killed:

| Mutant | Result |
|---|---|
| M3 the historical original, `.env` loaded at import time | **killed** |
| M4 the loader overwrites a caller-supplied value | **killed** |
| M5 the loader is a no-op | **killed** |

No token value is printed by any test; only its absence is asserted.
