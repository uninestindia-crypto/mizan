[VERIFICATION — QuantOS real-journey server/API/UI at 474795f]

ENVIRONMENT   Windows/PowerShell; Dewey's fresh canonical detached clone at
`D:\quant_system_workspaces\verification_clones\verify-real-journey-api-final-474795f-20260824-130801`.
Before install: no `.venv`, coverage, mypy/pytest/ruff caches, `tmp`, `htmlcov`, `build`, `dist`, or
`__pycache__`; frozen install created 47 packages with uv 0.12.5 / CPython 3.13.15. Independent
read-only corroboration found no database/migration contract. Evidence root:
`D:\quant_system_workspaces\scratch\qa-real-journey-api-474795f-20260824-codex-dewey\logs`.

COMMANDS

$ `Get-Content -Raw ...\logs\01-identity.txt` and independent `git rev-parse/status/diff`
```text
474795f3ad6287bdec3b7deaa677a54b537f28c7
1f6ca227bfdcd9dded692d7334f817da965d5f9e
SYMBOLIC_REF_EXIT=1
## HEAD (no branch)
DIFF_CHECK_EXIT=0
WORKTREE_DIFF_EXIT=0
CACHED_DIFF_EXIT=0
```

$ `Get-Content -Raw ...\logs\03-clean-install.txt`
```text
CLEAN_STATE_BEFORE_INSTALL
ABSENT  .venv
ABSENT  .coverage
ABSENT  .mypy_cache
ABSENT  .pytest_cache
ABSENT  .ruff_cache
ABSENT  tmp
ABSENT  htmlcov
ABSENT  build
ABSENT  dist
PYCACHE_DIR_COUNT=0
Installed 47 packages in 1.77s
UV_SYNC_EXIT=0
Python 3.13.15
PYTHON_VERSION_EXIT=0
v24.19.0
NODE_VERSION_EXIT=0
```

$ `Get-Content -Raw ...\logs\04-focused-127.txt`
```text
collected 127 items
======================= 127 passed, 1 warning in 40.02s =======================
```

$ `Get-Content -Raw ...\logs\05-full-normal.txt`
```text
collected 903 items
tests\test_costs_and_friction.py ..                                      [ 23%]
```
This first capture ends there with no verdict and is not counted as a pass.

$ `Get-Content -Raw ...\logs\05-full-normal-rerun.txt`
```text
collected 903 items
======================= 903 passed, 1 warning in 53.85s =======================
```

$ `Get-Content -Raw ...\logs\06-full-reverse.txt`
```text
REVERSE_FILE_COUNT=71
collected 903 items
======================= 903 passed, 1 warning in 55.04s =======================
```

$ `Get-Content -Raw ...\logs\07-ruff-check.txt` through `14-git-integrity.txt`
```text
All checks passed!
EXIT_CODE=0
355 files already formatted
EXIT_CODE=0
Success: no issues found in 125 source files
EXIT_CODE=0
NODE EXIT_CODE=0
OPENAPI_CONTRACT=PASS
OPENAPI EXIT_CODE=0
secure-by-default: clean — 11 file(s) scanned.
SECURITY EXIT_CODE=0
"results": {}
SECRETS EXIT_CODE=0
474795f3ad6287bdec3b7deaa677a54b537f28c7
1f6ca227bfdcd9dded692d7334f817da965d5f9e
## HEAD (no branch)
WORKTREE_DIFF_EXIT=0
CACHED_DIFF_EXIT=0
WHITESPACE_EXIT=0
```

$ `Get-Content -Raw ...\logs\15-historical-regressions.txt`
```text
collected 20 items
tests/test_server_governed_completion.py::test_dataset_catalog_rejects_hash_valid_but_domain_invalid_metadata PASSED
tests/test_server_governed_completion.py::test_dataset_idempotency_replays_the_same_operation_after_supervisor_restart PASSED
tests/test_server_governed_completion.py::test_security_middleware_never_reflects_an_unbounded_or_unsafe_request_id PASSED
tests/test_server_supervisor.py::test_cancellation_preserves_a_worker_success_that_won_during_grace PASSED
tests/test_ui_journeys.py::test_chart_controller_uses_native_canvas PASSED
tests/test_ui_journeys.py::test_control_target_size[.btn-secondary] PASSED
tests/test_ui_journeys.py::test_chart_canvas_is_responsive_and_contained PASSED
======================== 20 passed, 1 warning in 4.33s ========================
EXIT_CODE=0
```

$ `Get-Content -Raw ...\logs\16-governed-boundaries.txt`
```text
collected 29 items
tests/test_server_governed_journeys.py::test_data_sync_worker_publishes_the_provider_acquisition PASSED
tests/test_server_governed_journeys.py::test_data_sync_worker_rechecks_cancellation_before_publication PASSED
tests/test_server_governed_journeys.py::test_dataset_acquisition_binds_an_idempotency_key_to_one_request PASSED
tests/test_server_governed_journeys.py::test_legacy_training_route_never_returns_invented_positive_metrics PASSED
tests/test_server_governed_journeys.py::test_paper_order_never_fills_without_a_real_campaign PASSED
tests/test_ui_journeys.py::test_zero_live_broker_orders_contract_across_all_journeys PASSED
======================== 29 passed, 1 warning in 5.94s ========================
EXIT_CODE=0
```

$ `Get-Content -Raw ...\logs\17-claim-audit-pre-retirement.txt` and `18-disk-layout-audit.txt`
```text
RESULT: PASS - every workspace has a visible claim and every claim resolves.
EXIT_CODE=0
RESULT: PASS - no stray QuantOS directories.
EXIT_CODE=0
```

$ `Get-Content -Raw ...\logs\19-zero-broker-write-search.txt`
```text
COMMAND=rg -n -i broker write/order routing signatures in changed server paths
RG_EXIT=1 (1 means zero matches)
```

$ `Get-Content -Raw ...\logs\20-browser-evidence.json` and independent JSON audit
```text
REVISION=474795f3ad6287bdec3b7deaa677a54b537f28c7
BACKTEST_ENDPOINT=POST /api/backtest/run
BACKTEST_TRADES=6
BACKTEST_FILL_ROWS=6
STATE_COUNT=4
desktop-dark-post-backtest|theme=dark|viewport=1280x720|canvas=CANVAS|contained=True|overflowX=False|min=44x44|undersized=0|externalScripts=0
desktop-light-post-backtest|theme=light|viewport=1280x720|fills=6|canvas=CANVAS|contained=True|overflowX=False|min=44x44|undersized=0|externalScripts=0
mobile-light-post-backtest|theme=light|viewport=390x844|fills=6|canvas=CANVAS|contained=True|overflowX=False|min=44x44|undersized=0|externalScripts=0
mobile-dark-post-backtest|theme=dark|viewport=390x844|fills=6|canvas=CANVAS|contained=True|overflowX=False|min=44x44|undersized=0|externalScripts=0
CONSOLE_SECURITY_LOG_COUNT=0
RESOURCE_EXTERNAL_SCRIPT_COUNT=0
RESOURCE_EXTERNAL_STYLE_COUNT=0
RESOURCE_PAGE_OVERFLOW_X=False
```

EVIDENCE SHA-256

| Artifact | SHA-256 |
|---|---|
| `01-identity.txt` | `08eb6360f4c69c517d619d7eb1a7a8e9d42a1777742c49cf5a32e67baaa61fd6` |
| `02-command-discovery.txt` | `23e209f993e90379ef1cf2c376dcdc6b03f004a98b5f883a383b0b682df2965f` |
| `03-clean-install.txt` | `f7efca809c890585c43605630abbba4850475e5ec3489f2f8e3ab6ff17266391` |
| `04-focused-127.txt` | `6aa1c5c9bfb3b564632ab265152e61cee38ad5c63f4dac7e4a3c34407646f9f2` |
| `05-full-normal.txt` | `7ef60f3676f8eb869367fb7e3c65b036fcef328a85a0ca7cb6898153c6d1c2c3` |
| `05-full-normal-rerun.txt` | `29c273a2e016a5959ba1cd4bf69c16f36a04bd2a3fa32a40e7ab72f8bf982dde` |
| `06-full-reverse.txt` | `c96fe0462fac5f48dff027864df1166967e79f51cb567e10930b72c2b523b00a` |
| `07-ruff-check.txt` | `c3617f0e77c832a5e2cdc97a3aca146bdc88c869e1bbc487ed2917a3a817acdd` |
| `08-ruff-format.txt` | `881bb0b0627bcfd9a736e5895d33ed6fc4e82f4df888ccbfd613bd078bc3b289` |
| `09-mypy-src.txt` | `3c91935d9689ace5e646a876e825b02ccf340bc12e81c78920e04bfdf7da162e` |
| `10-node-check.txt` | `0c5a3ea0329ad8d282b0ac107483ec19ed14f6b31463bc4f1f8a519fe6b1009b` |
| `11-openapi-contract.txt` | `538880c57888a487c0f04d3df3f66887a908b1820a49a10dfc186558c00f2948` |
| `12-changed-security.txt` | `320af9733a8d15341b2b61fb01d31627a0f297b9afaf7cf6f689af11cd78c795` |
| `13-changed-secrets.txt` | `9be048b647f2a312cb732d76698ffe280dc966f0c2551599e28e699c7644848d` |
| `14-git-integrity.txt` | `c9ea980cf7e2422c8f774239568c6ce89abf45b2b1d441a849831e2921b57272` |
| `15-historical-regressions.txt` | `ff640c132a95b392ae35f9b3538ee26b88a0c7fe924fccdb835e56897af3dfc0` |
| `16-governed-boundaries.txt` | `32f17e6ea4a18d8844b8b99770b6c0021e892d8f905d96452b61d3d0df935834` |
| `17-claim-audit-pre-retirement.txt` | `5545cdd13a098efcd835b34c2763fa724db5a4aa136e13e72c0233d4a85b0560` |
| `18-disk-layout-audit.txt` | `b23cef65cdd82e3d4d0d49e4a431992e10aa433cc65a5bf2ee0feba7bd4d8d76` |
| `19-zero-broker-write-search.txt` | `74ee249d4b875f38b881e938ee600299c937850f4d2b904c770ce3a2eb71e6b1` |
| `20-browser-evidence.json` | `20cdd97ab2dc8ff8f0cb97a457f6c88b9113fe0ad9ca61c75aa3f55290c0c061` |
| handoff | `6f4762c875f9c8927081542507eda9a079a33efc492447b48637384329b1b4a4` |

ADJUDICATION

| # | Claim | Verdict | Evidence |
|---|-------|---------|----------|
| 1 | Exact HEAD/tree, detached state, and clean tracked worktree/index | PROVEN | Logs 01, 03, 14 plus independent corroboration |
| 2 | Focused server/API/UI suite: 127 passed | PROVEN | Log 04 |
| 3 | Full suite normal order: 903 passed | PROVEN | Complete rerun log 05; the incomplete first capture is not counted |
| 4 | Full suite reverse order: 903 passed across 71 files | PROVEN | Log 06 |
| 5 | Ruff lint and repository format gate pass | PROVEN | Logs 07-08 |
| 6 | Strict Mypy over 125 source files and Node syntax pass | PROVEN | Logs 09-10 |
| 7 | OpenAPI contract passes with 43 paths and required dataset/training schemas | PROVEN | Log 11 |
| 8 | Changed executable paths pass security and secret scans | PROVEN | Logs 12-13 |
| 9 | Git identity, whitespace, worktree, and index integrity pass | PROVEN | Log 14 |
| 10 | Twenty historical blocker regressions pass | PROVEN | Log 15 |
| 11 | Twenty-nine governed boundary tests pass | PROVEN | Log 16 |
| 12 | Agent-claim and disk-layout audits pass | PROVEN | Logs 17-18 and final reruns |
| 13 | Server/UI scope has zero broker-write behavior | PROVEN | Logs 16 and 19 |
| 14 | Real backtest completed with six trades and six fill rows | PROVEN | Log 20 |
| 15 | Chart is self-hosted native canvas on desktop/mobile light+dark | PROVEN | Log 20 and screenshot hashes |
| 16 | Controls are at least 44px, no X overflow, no external assets, clean console/security logs | PROVEN | Log 20 |

BASELINE COMPARISON   No exact-revision baseline is recorded in `.launch/COMMANDS.md`; its top-level
baseline is the stale 74-test state. Every current figure claimed in the handoff's evidence section
is reproduced: 127 focused, 903 normal/reverse, 355 formatted, Mypy 125, static/security/Git gates,
historical regressions, governed boundaries, audits, zero broker writes, and browser behavior.

NOT RUN               Long tests and browser were not rerun by this final adjudicator, per user
instruction; Dewey's raw outputs were independently read and hashed. Live Upstox/provider access,
private credentials, model training/promotion, live money, and broker writes were outside scope.
No database reset/migration was applicable because no database/migration contract exists. Log 21
was outside the requested 01-20 evidence set and was not used.

VERDICT: PASS
