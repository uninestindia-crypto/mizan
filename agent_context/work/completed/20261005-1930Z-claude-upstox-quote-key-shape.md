# Active work: Upstox V2 quote parser matches the real reply shape

STATUS: COMPLETED  
OWNER: Claude Code (cloud session)  
TOOL: Claude Code  
STARTED_UTC: 2026-10-05T19:30:00Z  
STARTING_REVISION: eaba6da92c018a31160baa9f22d39a9d4fbe43fe  
WORKTREE_OR_BRANCH: `/home/user/mizan` (primary checkout of the cloud container), branch `claude/loving-maxwell-rk25i4`. No worktree created.

## Objective

`UpstoxClient.fetch_market_quote` -> `parse_quote_payload` looks the entry up as
`payload["data"][instrument_key]` (ISIN form `NSE_EQ|INE009A01021`). The founder reports the live V2
`market-quote/quotes` reply is keyed by the SYMBOL form (`NSE_EQ:INFY`) and carries the ISIN form
inside the entry as `instrument_token`, so against the real feed the method always raises
`UpstoxDataError(PROVIDER_SCHEMA_DRIFT)`. Make the parser accept the real shape, bind the entry to the
requested instrument, keep failing closed on malformed bodies, and decide explicitly how an
after-hours one-sided book behaves.

## Owned paths

- `src/quant_system/data/upstox_parsing.py`
- `src/quant_system/data/upstox.py`
- `src/quant_system/data/upstox_failures.py`
- `tests/test_upstox_data.py` (all new quote tests live here, beside the existing quote test; no new test file)

Checked against every record in `work/active/` (130 files, 42 `STATUS: ACTIVE`): none lists any of the
paths above under owned paths. `upstox*.py` and `test_upstox_data.py` appear in other records only as
verification evidence or in NOTICE test-name lists, never as a claim. `data/market_data.py` IS claimed by
`20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md` and is deliberately NOT touched
(see Decision rationale: no new `AcquisitionFailureCode`).

## Non-goals

- `scripts/run_paper_pilot_session.py` (claimed by the Antigravity paper-trade record). It already
  handles both key forms; read only.
- `src/quant_system/core/domain.py` (`Quote` contract) and `src/quant_system/data/market_data.py`
  (failure-code enum). No contract changes.
- No live call to Upstox, no token handled, nothing that places an order. Live-money routing stays out.
- No release is cut here (see Next safe action).

## Plan

1. Claim paths (this file). DONE.
2. Provision a Python >= 3.12 env with `uv sync --frozen --extra dev` (does not edit `pyproject.toml`/`uv.lock`). DONE.
3. Reproduce: write tests first, with a fixture shaped like the real reply; confirm RED on the unfixed parser. DONE.
4. Fix `parse_quote_payload`; add the typed one-sided-quote failure; wire `fetch_market_quote`. DONE.
5. Gates: `ruff`, `ruff format --check`, `mypy`, touched tests, mutation check, secret and dead-code scans. DONE (one mypy caveat below).
6. Commit explicit paths only; push to the designated branch; move this record to `completed/`. DONE.

## Current step

Completed.

## Decision rationale

Evidence: the task states a measurement taken against the live endpoint with a valid analytics token.
**This session did not re-measure it** (no credential is available here, and none was requested). The
repository corroborates the symbol-keyed shape independently: `scripts/run_paper_pilot_session.py`
~line 1036 records a ten-instrument measurement on 2026-09-01 where the ISIN-keyed lookup hit 0 of 10
and the `NSE_EQ:<symbol>` lookup hit 10 of 10. The task text dates its own measurement 2026-10-06;
the container clock reads 2026-10-05. Recorded as stated, not resolved.

Findings that differ from the task text:

- `tests/test_upstox_data.py` has no fixture keyed by instrument key. Its ~line 63 test is a
  no-token test that never reaches the parser. `parse_quote_payload` had **no test at all**, which is
  why nothing failed. New tests therefore live mainly in a new file rather than editing a wrong fixture.
- Nothing in `src/` or `scripts/` calls `fetch_market_quote` today, so no live path was broken by this;
  the defect was latent.

Decisions:

1. **Entry selection.** Try the instrument key, then `<segment>:<symbol>` (segment taken from the
   instrument key's prefix), then a unique scan on `instrument_token`.
2. **Identity binding.** The entry's `instrument_token`, when present, must equal the requested
   instrument key, else `PROVIDER_SCHEMA_DRIFT`. When the entry was found by symbol form or by scan, the
   token is mandatory: a symbol string alone is a label, not the data (symbols are reused after
   corporate events; this repo has been bitten by binding the label before). An entry keyed by the
   instrument key itself may omit the token, because the key is the binding.
3. **One-sided book after hours (`{price: 0.0, quantity: 0}`): fail closed, distinct from drift.**
   `Quote` cannot represent "no bid" (non-optional `Decimal`), so "treat as no bid" would need a change
   to `core/domain.py`. Passing the zero through would silently give `mid = ask / 2` and a 200% spread.
   It is not schema drift either: it is a valid reply that has no tradable market, which happens every
   evening, and filing it as drift would send people to "update the provider contract" for a non-bug.
   It raises `ProviderQuoteUnavailable` and surfaces as `UpstoxDataError` with `DATASET_EMPTY`,
   `retryable=True`. Zero bid, zero ask and zero `last_price` take this path; a NEGATIVE price or a
   crossed book is malformed and stays `PROVIDER_SCHEMA_DRIFT`.
4. Rejected: a new `QUOTE_UNAVAILABLE` code (would edit the claimed `market_data.py` enum, a shared
   contract); making `Quote.bid` optional (touches every consumer of `mid_price`); returning a
   `Quote` with `bid=0` (fabricates a mid).
5. Small adjacent hardening inside the same function, because each is the same defect class and each
   was reachable from the reply: `timestamp` must carry a zone (`.astimezone` on a naive value silently
   uses the machine's local zone); prices and sizes go through the module's existing
   `_parse_decimal` / `_parse_nonnegative_integer` (a `NaN` price previously escaped as an uncaught
   `InvalidOperation` from `Quote.__post_init__`; a crossed book escaped as a raw `ValueError`).

## Incident recorded at checkpoint 3: ambient credentials, four live read-only requests

This container's environment has `UPSTOX_ANALYTICS_TOKEN`, `UPSTOX_ACCESS_TOKEN` and `UPSTOX_API_KEY`
set (names checked with `[ -n ... ]`; **values were never printed or written anywhere**). Two existing
tests in `tests/test_upstox_data.py` -- `test_upstox_historical_request_without_token_raises_typed_error`
and `test_upstox_quote_request_without_token_raises_typed_error` -- build
`UpstoxClient(api_key="", access_token="")`, which falls back to those variables, so here the client is
authenticated and the default transport sends a real request. They ran twice (once in my file, once in a
pristine `HEAD` copy to prove they fail without my edit): **4 real GETs to api.upstox.com with the real
token.** All read-only market-data requests; the transport protocol is GET-only (`upstox_http.py`:
"broker writes cannot be expressed"), so no order path was reachable. Both tests failed on
`PROVIDER_SCHEMA_DRIFT` instead of `PROVIDER_UNAUTHORIZED`. For the quote test that outcome is
*consistent with* the reported defect, but the reply body was not captured, so it is not proof of it.

This is the already-recorded class in `20260901-NOTICE-dashboard-threading-under-antigravity-claim.md`
("credential-absence coverage ... one import away from being vacuous"): that notice lists these same
two tests plus five in files this record does not own. Handling here:

- The two tests in the owned file are made hermetic (`monkeypatch.delenv` of the three variables).
- The other five are NOT touched and are reported. A repo-wide autouse fixture in `conftest.py` is the
  real fix and is a shared-infrastructure change that needs its own owner.
- Every verification command in this record runs with the three variables unset (`env -u`), so no
  further test can reach the network.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git status`, `git worktree list`, `git branch --list` | PASS | clean tree; 1 worktree; branches `claude/loving-maxwell-rk25i4`, `main` |
| `python scripts/release_status.py` | DUE | 30 user-visible commits, 2 security, no `v*` tag yet. Not caused by this change; not cut here |
| `uv sync --frozen --extra dev` | PASS | `.venv` (gitignored); `pyproject.toml` and `uv.lock` unchanged |
| RED: `pytest tests/test_upstox_data.py` on unfixed parser | 2 new real-shape tests FAIL | `PROVIDER_SCHEMA_DRIFT` from `fetch_market_quote`; instrument-key-form test passes (regression guard) |
| Same 2 no-token tests on a pristine `HEAD` copy | FAIL | Proves they fail without my edit: ambient token, see incident section |
| `pytest tests/test_upstox_data.py tests/test_upstox_v3_acquisition.py` (`env -u` the 3 vars) | PASS, 74 | 44 in `test_upstox_data.py` (was 6) |
| Same file with DUMMY ambient `UPSTOX_*` values | PASS, 44 | The file no longer depends on the environment. Real values never used for this |
| Mutation A: token binding disabled | 3 FAIL as expected | both token-disagreement tests and the symbol-keyed no-token test |
| Mutation B: one-sided guard removed | 4 FAIL as expected | zero-bid, zero-ask, both-empty, zero-last-price |
| Mutation D: naive timestamp accepted again | 1 FAIL as expected | `timestamp-without-a-zone` |
| Parser restored after each mutation | PASS | `diff` against the saved copy: identical |
| `ruff check .` | PASS | all checks passed |
| `ruff format --check .` | PASS | 933 files already formatted |
| `mypy src launcher.py scripts --platform win32` | 1 error, not mine | `shell/native_window.py:237` cannot import `webview`: `pywebview` is declared `sys_platform == 'win32'`, so it is absent on this Linux container by design. `shell/` untouched by this diff. My 3 source files alone: `Success: no issues found in 3 source files` |
| 9 test modules importing the Upstox code (`env -u` the 3 vars) | PASS, 226 | includes the five tests the 2026-09-01 notice lists as ambient-token-fragile |
| `detect-secrets scan` on the files to commit | 0 candidates | no baseline file in repo; scanned the commit set directly |
| `vulture --min-confidence 80` on the 3 source files | 0 findings | |
| Token-value leak check (compare without printing) | PASS | none of the 3 values occurs in any committed file |

## Files changed

- `src/quant_system/data/upstox_parsing.py`: `parse_quote_payload` selects the entry by instrument key, then `<segment>:<symbol>`, then a unique `instrument_token` scan (`_select_quote_entry`), and binds it to the request through `instrument_token`. New `ProviderQuoteUnavailable` for a book with no priced side. Prices, sizes and timestamp now go through the module's existing strict helpers.
- `src/quant_system/data/upstox_failures.py`: `quote_unavailable_failure` (`DATASET_EMPTY`, retryable).
- `src/quant_system/data/upstox.py`: `fetch_market_quote` maps `ProviderQuoteUnavailable` to that failure; schema drift unchanged.
- `tests/test_upstox_data.py`: 6 -> 44 tests. Real-shape fixture; both key forms; token binding; one-sided books; 21 malformed bodies. The two no-token tests are made hermetic.
- `agent_context/work/completed/20261005-1930Z-claude-upstox-quote-key-shape.md`: this record.

## Blockers and conflicts

- `scripts/audit-agent-claims.ps1` and `scripts/audit-disk-layout.ps1` are PowerShell and this Linux
  container has no `pwsh`; **they were NOT run**. The claim check was done by hand (see Owned paths);
  no worktree or extra branch was created, so there is nothing for them to find, but that is my
  reasoning, not their output. Run them on the Windows machine before relying on it.
- `requires-python >= 3.12`; the container's system Python is 3.11, so the env is provisioned by `uv`.
- Not fixed, not mine: five other tests (`test_config_env`, `test_data_provenance`,
  `test_server_governed_completion`, `test_server_governed_journeys`,
  `test_upstox_v3_acquisition::test_missing_access_token_...`) assert credential absence and are
  fragile to an ambient token, per `20260901-NOTICE-dashboard-threading-under-antigravity-claim.md`.
  Not re-run with the real token in this session (that would send live requests). Real fix is one
  autouse fixture in `tests/conftest.py`, a shared file needing its own owner.
- The one-sided-book outcome reuses `DATASET_EMPTY`. A dedicated code needs `data/market_data.py`,
  claimed by `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md`.
- Release: `release_status.py` reports DUE, and was already due before this change (30 user-visible
  commits, no `v*` tag). `scripts/release.ps1` is PowerShell and builds the Windows installer, so it
  cannot run in this container. Not cut; the founder or a Windows session should.

## Stop point

All changes committed on `claude/loving-maxwell-rk25i4` and pushed (hash in the commit message of that
branch tip). Working tree clean apart from the git-ignored `.venv`. No PR opened.

## Next safe action

1. On the Windows machine: run `scripts/audit-agent-claims.ps1` and `scripts/audit-disk-layout.ps1`.
2. Optionally confirm the fix against the live feed with one read-only quote request for a single
   instrument (not done here: the reported measurement is the founder's, and this session's only live
   contact was the four accidental requests recorded above).
3. Cut the overdue release with `scripts/release.ps1 -DryRun` first.
