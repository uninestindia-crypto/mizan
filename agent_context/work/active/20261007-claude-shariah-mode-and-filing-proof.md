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

UPDATED 2026-10-07 19:55 UTC. Committed and pushed to `claude/wonderful-wozniak-6ek6zl`: Copilot Shariah-mode awareness;
the proof builder; the filings engine; the bundled real-filings snapshot (413 companies, newest period Dec 2024, so every
verdict from it is labelled out of date until the app fetches newer filings: NSE's feed as seen from this cloud machine
ends in Jan 2025); the AI-source backend (`cli_chat`, `ai_choice`, `copilot_ai`, settings fields, `20261007-ai-source-cli-default.md`);
the one-click updater backend (`updater.py`, `update_routes.py`, installer relaunch); the Shariah mode screens and proof panel.
Six helpers were stopped by a usage limit at 19:40 UTC and resumed at 19:53 UTC, each with a work record of its own:
proof service and endpoints (`afb3ed9`), fundamentals backend (`af9f045`), chat-history screen (`a95ee07`), "Which AI answers"
settings screen (`a032d6e`), top bar and Update button (`a73b644`), Portfolio accounts screens (`af8649e`).
Their files are uncommitted and are committed by me only after I re-run their gates. Hourly routine
"Keep QuantOS agents moving" resumes any helper that a limit stops.

## Next safe action

For each helper report: re-run its gates, commit only its own paths, push. Then: full fundamentals snapshot build
(`scripts/build_fundamentals_snapshot.py`, polite, about an hour), Fundamentals tab on the Portfolio screens,
`scripts/release_status.py`, and ask the founder before the pull request, merge and release.

UPDATED 2026-10-09 07:20 UTC. The weekly usage limit reset; the chat-history and AI-source screens are committed
(`297301b69`, `c9a0f9341`). Five helpers were resumed by me at 07:15 UTC, each continuing from the stop point in its own
record: proof service backend (`afb3ed9`), fundamentals backend (`af9f045`), top bar and Update dialog (`a73b644`),
Portfolio accounts screens (`af8649e`), AI apps card in plain words (`acafd55`). Their files are still uncommitted and are
committed by me only after I re-run their gates. Pull request, merge and release still wait for the founder.
