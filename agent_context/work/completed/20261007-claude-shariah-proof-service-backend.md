# Work record: Shariah proof service (backend), sub-task of the Shariah mode and filing proof work

STATUS: COMPLETED (released in v3.2.0; remaining work is in agent_context/handoffs/20261009-claude-v3-2-0-release-handoff.md)  
OWNER: Claude Code worker (backend proof service), spawned by the coordinator session  
TOOL: Claude Code  
STARTED_UTC: 2026-10-07  
STARTING_REVISION: 07b6c6c8c on `wip/halal-transparency` (shared checkout, no other worktree)  
PARENT_RECORD: `agent_context/work/active/20261007-claude-shariah-mode-and-filing-proof.md`  
CONTRACT: `agent_context/decisions/20261007-shariah-mode-and-filing-proof.md`  
GOAL_LINE: G2 (one app, two real modes), G6 (retail benefit); tripwire 4 (no screen presented as a fatwa).

## Objective

Serve the proof contract over HTTP: `GET /stocks/{symbol}/proof`, `GET /status`, `POST /filings/fetch|refresh`,
`GET|DELETE /filings/jobs/{id}`, `GET /filings/coverage`, and make the screener endpoints and the Copilot's halal tool
prefer the filing-based proof.

## Owned paths (new unless marked)

- `src/quant_system/shariah/services/{proof_service,proof_market,proof_inputs,proof_short,proof_sector_only,filing_jobs,proof_samples}.py`
- `src/quant_system/shariah/api/v1/endpoints/{proof,filings}.py`; `src/quant_system/shariah/api/v1/router.py` (includes only)
- `src/quant_system/server/v2/shariah_wiring.py`
- `src/quant_system/shariah/api/v1/endpoints/{screening,stocks}.py` (additive fields only)
- `src/quant_system/copilot/{tools_screening,sources,rules}.py` and `src/quant_system/server/v2/copilot_wiring.py`
  (halal tool uses the proof; `rules.py` only so the halal text stops calling filing figures "a hand-entered sample")
- `src/quant_system/shariah/services/proof_types.py` (one type annotation widened: `filed_on` may be missing)
- `installer/*.spec` / `quant_system.spec` data lists and their packaging tests (pin `data/shariah` carrying the snapshot)
- `tests/shariah/test_proof_service.py`, `test_proof_routes.py`, `test_filings_jobs.py` and helpers beside them,
  `tests/test_copilot_*` additions for the proof-backed tool

## Not touched

`frontend/**`, `data/**`, `scripts/build_shariah_filings_snapshot.py`, `src/quant_system/shariah/filings/**`,
`server/v2/router.py`, `copilot/{cli_chat,ai_choice,conversations}.py`, `server/v2/{copilot_ai,copilot_routes,state}.py`.

## Non-goals

No network call from any test. No snapshot written. No change to thresholds. No git add or commit (the coordinator commits).

## Stop point (updated after each finished sub-step; newest first)

### After sub-step 8: ALL PLANNED WORK DONE; final gates being re-run; nothing staged or committed

Done since the last stop point: packaging (`quant_system.spec`, `installer/quantos.spec`, `installer/quantos-studio.spec`
now list `data/authorities/nse-all-listed-equities.csv`; `quant_system.spec` also lists `data/shariah`; the other two already
shipped `data/shariah` whole) with `tests/test_shariah_bundle_packaging.py` (11); proof cache now keyed on the price-data
build (`_AppBars.version()`), so prices loaded after a proof was cached are used; full suite
(`pytest tests --ignore=tests/fundamentals`): 5,089 passed, 17 skipped (all pre-existing, Windows-only or Tk).
New tests: 188 (tests/shariah +153: market 16, service 57, jobs 26, routes 33, paths 7, overlay 14; copilot proof 24;
packaging 11). `tests/shariah` is 1,010 tests (857 before).
Files ready to commit are listed in the final report to the coordinator. Not committed by me.

### After sub-step 7: Copilot done (step 3); filtered pytest set passes (2,143, 2 skipped, pre-existing skips)

Added `copilot/{screening_proof,halal_text}.py`, `ProofBackedShariahSource` in `copilot/sources.py`, `_proof`/`_shariah` in
`server/v2/copilot_wiring.py`, small hooks in `copilot/rules.py` (`render_halal`, `verdict_word`) and
`copilot/tools_screening.py` (`shariah_check` uses a decisive proof, else the sample as before; an unreadable sample is
still reported). New `tests/test_copilot_screening_proof.py` (24). Screening endpoint: `overall_status` for "both" follows
the proof verdict (questionable when the two standards disagree).
MISTAKE TO REPORT: I ran `ruff format src/quant_system` once (a repo-wide format) at ~20:02; it rewrote another worker's
untracked `src/quant_system/fundamentals/*.py` (formatting only). Never run it again; format files by explicit path.
Their `tests/fundamentals/test_fund_store.py` fails to collect (missing module, their work in progress): I pass
`--ignore=tests/fundamentals` in my gate run.
NEXT: step 4 packaging specs + test; step 5 gates (ruff, mypy win32, vulture, check-code, check-tests, detect-secrets); report.

### After sub-step 6: screener overlay done (step 2 of the plan), whole tests/shariah passes (1,006 tests)

Added: `services/verdict_overlay.py`; `verdict_source`/`as_of` on `CompanySummary`, `SearchSuggestion`, `CompanyDetail`,
`TransparencyFields` (AAOIFI debt/cash/receivables ratios on `CompanyDetail` may now be null when no prices);
`endpoints/stocks.py` (`_summary` helper, search/list/detail prefer the filing), `endpoints/screening.py` (screen and audit
prefer the filing; helpers `filing_proof_of`, `evaluate_preferring_filing`, `transparency_of`, `audit_source`).
`tests/shariah/conftest.py` gained an autouse fixture that installs a proof runtime holding no filings, so the old
sample-based tests do not read the real bundled snapshot. New `tests/shariah/test_verdict_overlay.py` (14).
Gates so far: ruff check/format and `mypy --platform win32 src/quant_system/shariah` clean; `pytest tests/shariah` 1,006 pass.
NEXT: Copilot (tools_screening, sources, copilot_wiring, rules.render_halal), packaging specs + test, then all gates + report.

### After sub-step 5: route and path tests written and passing (135 tests across my 5 files)

`test_proof_routes.py` (30, includes the real app and the real bundled snapshot now placed at
`data/shariah/filings_snapshot.json.gz`), `test_proof_paths.py` (7), plus the three earlier files: 135 pass.
Real-snapshot facts: 350 READ_OK / 53 bank-format; every filing in it is STALE against today's date (newest period
2024-12-31); 200 statuses take 0.21 s with no prices, 0.002 s cached. The real app needs the `X-CSRF-Token` header on POST.
Test helper `no_network` blocks any non-local connect or DNS lookup. NEXT: step 2 (screener overlay), step 3 (Copilot),
step 4 (packaging), step 5 (gates), report.

### After sub-step 4: service, market-value and job tests written and passing

`tests/shariah/test_proof_market.py` (16), `test_proof_service.py` (56), `test_filings_jobs.py` (26) all pass; helper
`proof_service_fixtures.py` (no tests). Command: `env -u UPSTOX_ANALYTICS_TOKEN -u UPSTOX_ACCESS_TOKEN uv run --frozen
pytest <files> --basetemp=/tmp/claude-0/bt_proof -p no:cacheprovider -q`. NEXT: `test_proof_routes.py` (TestClient), then
the screener overlay, Copilot, packaging, gates (see the list below).

### After sub-step 3: routes and wiring written, smoke-tested by hand (no unit tests yet)

DONE and importable, ruff check/format clean on `src/quant_system/shariah/services/`:
`proof_market`, `proof_samples`, `proof_inputs`, `proof_unscreened`, `proof_short`, `proof_paths`, `proof_service`,
`filing_words`, `filing_jobs`, `proof_runtime` (services); `server/v2/shariah_wiring.py`; `endpoints/proof.py`
(`/stocks/{symbol}/proof`, `/status`) and `endpoints/filings.py` (`/filings/fetch|refresh|coverage|jobs/{id}`), both
included in `api/v1/router.py`. `proof_types.py`: `FilingIn.filed_on` widened to `str | None`.
Hand smoke test (scratchpad `smoke2.py`) with a fake store and no network: proof 200, bad symbol 422 plain error,
status row, coverage, fetch 202, second fetch 429, cancel, unknown job 404.
Lesson: `quant_system.server.security` must be imported lazily inside `fail()` (the server package imports this router).

NEXT, in order:
1. Tests (test-first for the rest): `tests/shariah/test_proof_service.py`, `test_proof_routes.py`, `test_filings_jobs.py`
   (fakes only, no network, no sleeps), market-value maths, statuses == proof verdicts, STALE by clock, NOT_SCREENED.
2. Screener overlay (additive): new `services/verdict_overlay.py`, schema fields `verdict_source`/`as_of`, edits to
   `endpoints/{stocks,screening}.py`; run old `tests/shariah` with a temp app root holding a copy of the snapshot.
3. Copilot: `tools_screening.py`, `sources.py`, `copilot_wiring.py`, `rules.py` (`render_halal` says "hand-entered sample").
4. Packaging: add `data/authorities/nse-all-listed-equities.csv` (and `data/shariah` for `quant_system.spec`) to the specs
   and pin in a packaging test. Note: `data/shariah` is already shipped whole by `installer/quantos*.spec`, the release
   staging step and the Inno script, so the snapshot rides along with `halal_stocks.db`.
5. Gates: pytest (my tests + tests/shariah + `-k "copilot or shariah or packaging or installer or no_terminal"`), ruff,
   mypy `--platform win32`, vulture, check-code, check-tests, detect-secrets. Then the final report.

Gates passed so far: ruff check and format on the services folder only. No pytest run yet.
Decisions to report: sector-only verdict (a bank) is NON_COMPLIANT with data_status NOT_SCREENED (contract-literal; the
frontend `parseStatus` collapses it to "Not screened"); market value needs ~34 months of prices ending within a year.
