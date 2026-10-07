# Work record: Shariah mode everywhere, and real filing proof on every stock

STATUS: ACTIVE  
OWNER: Claude Code (cloud session)  
TOOL: Claude Code  
STARTED_UTC: 2026-10-07T05:05Z  
STARTING_REVISION: 8b4a9706e1bdbcd0ad502dd2b943cd8414c98aff (origin/main, v2.5.0 version commit)  
WORKTREE_OR_BRANCH: `/home/user/mizan` (cloud clone). Local branch `wip/halal-transparency` while the Stage 0 workers finish, then
restarted from `main` on the designated branch `claude/wonderful-wozniak-6ek6zl`. No other worktree.

GOAL_LINE: G2 (one app, two real modes), G6 (retail benefit), tripwire 4 (no screen presented as a fatwa or an edge).

## Objective

Founder, 2026-10-07: "many users complained on shariah compliance: when they selected shariah compliance then everything
should be based on shariah compliance, and on clicking on a stock it should tell with real data and proof why it's
shariah compliant and why not." Design and rules: `agent_context/decisions/20261007-shariah-mode-and-filing-proof.md`.

## Owned paths

- `src/quant_system/shariah/filings/**` (new), `tests/shariah/test_filings_*.py` (new), `tests/fixtures/shariah_filings/**` (new),
  `scripts/build_shariah_filings_snapshot.py` (new), `data/shariah/filings_snapshot.json.gz` (new, generated)
- `src/quant_system/shariah/services/proof_service.py`, `.../api/v1/endpoints/proof.py`, `.../api/v1/endpoints/filings.py` (new, after
  the Stage 0 backend worker finishes) and the one-line router includes
- `frontend/src/lib/mode.ts`, `frontend/src/lib/shariahStatus.ts`, `frontend/src/lib/proof.ts` (new),
  `frontend/src/components/mode/**` (new), `frontend/src/components/proof/**` (new)
- mount-point edits only, each re-read before editing: `frontend/src/components/Layout.tsx`, `frontend/src/pages/Home.tsx`,
  `frontend/src/pages/Stock.tsx`, `frontend/src/pages/Models.tsx`, `frontend/src/components/OrderTicket.tsx`,
  `frontend/src/components/PaperPositions.tsx`, search and watchlist components
- `src/quant_system/copilot/**` (mode awareness only)
- `docs/HALAL_METHODOLOGY.md` (after the Stage 0 backend worker finishes)

Not owned and not touched while the Stage 0 workers run: `src/quant_system/shariah/{services/screener_service.py,schemas/**,
api/v1/endpoints/{screening,stocks,baskets,purification}.py}`, `frontend/src/pages/Shariah.tsx`,
`frontend/src/components/shariah/**`, `frontend/src/lib/{shariah.ts,types.ts}` (claimed in
`20261007-claude-halal-transparency-and-model-picks.md`).

## Non-goals

No order placement. No change to what a running paper book trades. No new model trial. No claim that a screen is a
fatwa, certified or reviewed by a scholar. No scraping that needs a login, no use of a paid vendor, no credentials.
Thresholds unchanged. Stage 2 (daily recompute) and 3 (intraday) are not part of this.

## Plan

1. Contract and record. DONE (this file and the decision record)
2. Filings engine: NSE client, XBRL reader, tie-out, store, tests with a recorded real filing as fixture. WORKER
3. Mode: setting-driven mode, badges, filters, hidden-count control, proof panel mount, Copilot awareness. WORKER (screens), me (Copilot)
4. After Stage 0 workers finish: proof service and endpoints, screener integration with the two-bound rule, in-app fetch jobs. 
5. Snapshot of real figures for the research universe, built here (network is open), committed with its build date.
6. Gates, real-browser check, PR.

## Blockers and conflicts

The Stage 0 workers finished and were verified and committed (`48aa24b6d`, `e23ab6da8`); the screener, schemas and Shariah
screen files are free again.
Release v2.5.0 is PUBLISHED (2026-10-07 09:35 UTC, tag on `aaf41e472`). GitHub gave no runners for about four hours after
04:53 UTC (account side, cause unconfirmed), then the first release run failed on a Windows-only bug of mine: the Copilot
folder held `Markdown.tsx` beside `markdown.ts`, which are one name on Windows. It was fixed on `main` by renaming to
`MarkdownView.tsx`. `tests/test_repo_hygiene.py` now fails on any such pair; run against the tree that shipped the bug it
reports both pairs. Workers were stopped by a session limit and resumed at 09:45 UTC.

## Stop point

Contract written; Copilot Shariah-mode awareness committed (`d6d138032`); business-activity test and proof builder written
test-first and passing (52 tests, uncommitted: `services/{activity_check,proof_*}.py`, `tests/shariah/{proof_fixtures,
test_proof_*}.py`); filings-engine worker and mode-screens worker resumed. Still to do on my side: the proof service and
endpoints (`GET /stocks/{symbol}/proof`, `GET /status`, filing jobs, coverage), the price-history market value, the
snapshot build, then gates, a real-browser check of the whole flow, and the PR.

## Next safe action

When both workers report: re-run their gates myself, commit their paths, write `proof_service.py` over the filings store and
the market index, then the endpoints.
