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

UPDATED 2026-10-09 07:35 UTC. Proof service backend committed and pushed (`878ccae8f`); I re-ran its gates myself: 1,079
tests passed (`tests/shariah`, Copilot proof, packaging, no-terminal copy), ruff format and lint clean, mypy --platform win32
clean on 131 files, craft checks clean on the new files, detect-secrets 0 hits. Still running: fundamentals backend,
top bar and Update dialog, Portfolio accounts, AI apps card.

Open points from the proof helper that need a decision or a small follow-up (not blockers for committing):
1. A bank or other sector-failed business with no usable figures comes back `NON_COMPLIANT` with data status
   `NOT_SCREENED`. The frontend badge collapses that pair to "Not screened"; the proof panel shows it correctly.
   Decide which the badge should say.
2. When AAOIFI and TASIS disagree the proof says QUESTIONABLE; the older screener tab (`lib/shariah.ts` `overallStatus`)
   takes the worse of the two. `/screen` follows the proof; list rows cannot. Decide one rule and make both agree.
3. Market value needs at least about 34 months of prices ending within a year; otherwise the AAOIFI column says it needs
   price history. The bundled filings are all STALE (newest period Dec 2024), so a refresh from NSE is needed in the app.
4. The SQL status filter on the older list still filters on the sample's status before the filing's status is applied.
5. Another helper ran `ruff format src/quant_system` repo-wide by mistake and reformatted the untracked fundamentals
   files (formatting only). The fundamentals helper has been told to re-read them.
6. `data/shariah/halal_stocks.db-shm` and `-wal` are SQLite side files; they must not be committed (`.gitignore` is a
   shared file, so adding them there is for the coordinator, with the founder's say).

UPDATED 2026-10-09 07:40 UTC. AI apps card committed and pushed (`29d589201`). I checked the exact staged state in an
isolated export (the card's own hunks of `queries.ts` and `types.ts` only, none of the Portfolio worker's): tsc clean,
1,003 vitest tests passed, secret scan 0, craft checks clean. Still running: fundamentals backend, top bar and Update
dialog, Portfolio accounts. Follow-ups the card's helper found, not yet done:
1. `pages/Tools.tsx` still has a "Coding agents" tab showing the same card, and `components/topbar/screenName.ts` says
   "Coding agents". Rename to "AI apps" (the top bar worker owns `topbar/`).
2. The engine's own texts still say "Codex CLI is connected." and "Gemini CLI is installed." (`cli_bridge.py`).
3. `APP_NAMES` in `lib/aiSource.ts` still says "Gemini CLI" in the choice card; the founder's wording rule says drop "CLI".
4. Gemini sign-in still opens a window (`signin_mode="terminal"` in `cli_bridge.py`); only an engine change fixes that.

UPDATED 2026-10-09 08:00 UTC. Fundamentals backend committed and pushed (`b34b236f6`); I re-ran its gates myself: 2,786
tests passed (fundamentals, portfolio, Copilot, Shariah, no-terminal copy), ruff, mypy --platform win32 (84 files), craft
checks and detect-secrets all clean. The full snapshot build (423 companies, 8 quarters, 1.5 s pause, one request at a
time) was started in the background at about 08:00 UTC, writing to the scratchpad, not to `data/`. When it finishes:
check the log, copy to `data/fundamentals/fundamentals_snapshot.json.gz`, add `data/fundamentals` to the three
`.spec` files as `data/shariah` is, run the packaging test, commit. Do NOT start a Shariah filings refresh meanwhile (two
NSE jobs have no shared gate). Still running: top bar and Update dialog, Portfolio accounts screens.
Open points from the fundamentals helper (founder decisions): rule-of-thumb thresholds in `fundamentals/scorecard.py`
RULES (profit in 6 of 8 quarters, growth not below zero, interest cover at least 3, borrowings at most 1x owners' money,
ROE at least 12%); `is_long_term` means strictly more than 12 months, 29 Feb counted as 28 Feb; whether stale companies
should be hidden from the screen by default; whether banks and lenders get their own reader (today: FORMAT_NOT_READ).

UPDATED 2026-10-09 08:25 UTC. Top bar and Update dialog committed and pushed (`a4e492df5`). Checked the exact staged state in
an isolated export: tsc clean, 1,194 vitest tests passed (81 files), craft checks clean, secret scan 0 in the new files
(`Settings.tsx` still reports 8 pre-existing "Secret Keyword" lines that hold setting names, none of them in the lines
added). The helper also ran it in a real browser at six widths in both themes (axe: no serious or critical findings). The
real Windows update path (download, fingerprint, installer launch, relaunch) has NOT been run anywhere. Remaining helper:
Portfolio accounts screens. Fundamentals snapshot build still running.
Open points from the top bar helper:
1. The engine sends no NSE holiday list to the app (`data/authorities/nse-trading-holidays.json` has no route), so the
   market chip says "Market hours", never "Market open". Needs a small backend route.
2. The live-prices status only says ready or not, so the chip cannot say "Delayed".
3. The theme toggle is in the sidebar only; phones have none. Decide whether to add it to the Status list.
4. Inline chips need about 1,870 px of window; below that people see one Status button. Decide if Market and Prices should
   stay inline with a shorter mode-switch label (touches ModeSwitch).

UPDATED 2026-10-09 08:55 UTC. Portfolio accounts screens committed and pushed (`995acbaa4`); I checked the exact staged state
in an isolated export: tsc clean, 1,295 vitest tests passed (90 files), craft checks clean, secret scan 0. All earlier
helpers' work is committed. Two helpers are now running, each with its own record and stop point:
- `20261007-claude-fundamentals-screens.md` (resumed `af8649e`): Portfolio Fundamentals tab, filings section and
  'Get the latest results' on the Stock page, the Stock page 'Add to portfolio' fix (it silently files into the first
  account for people with several accounts), a Fundamentals screen with filters and compare, per-lot holding periods.
- `20261007-claude-wording-holidays-badges.md` (new, `a31ba91`): 'Coding agents' -> 'AI apps', drop 'CLI' from visible
  words, a holiday route for the market chip (plus the holidays file in the three specs), one rule for AAOIFI/TASIS
  disagreement across badge and old tab.
Fundamentals snapshot build still running (scratchpad `fundsnap/`); after it finishes: copy to
`data/fundamentals/fundamentals_snapshot.json.gz`, add `data/fundamentals` to the three specs, run the packaging test, commit.
Open from the Portfolio helper: 'remember the account choice' uses localStorage (survives restarts); labels 'By stock' /
'By lot' to be confirmed.

UPDATED 2026-10-09 12:15 UTC. A session usage limit (reset 12:10 UTC) stopped both new helpers before they wrote their
records or any file (checked: working tree clean apart from the two SQLite side files); I resumed them at 12:11 UTC:
fundamentals screens (`af8649e`) and wording/holidays/badges (`a31ba91`). The fundamentals snapshot build had read 412 of
423 companies when its background window ended; I restarted it with the same resume folder at 12:11 UTC so it only reads
the rest. Everything committed is pushed (latest code commit `995acbaa4`).

UPDATED 2026-10-09 12:45 UTC. Fundamentals snapshot committed and pushed (data/fundamentals/fundamentals_snapshot.json.gz,
412 companies, 2,915 filings, 755 industry groups, 803 KB; the three build specs carry `data/fundamentals`; new
`tests/test_fundamentals_bundle_packaging.py` pins it). 11 of the 423 universe names have no filing in NSE's feed.
FOLLOW-UP (engineering, found by reading the build): 414 of 2,915 quarters (14%) are TIE_OUT_FAILED, and 382 of those fail
one check, 'Owners and minority shares add up to profit for the period'. In the cases I read (e.g. AJANTPHARM consolidated,
Mar and Jun 2023) the filer reported both the owners' share and the minority share as exactly 0.00 while profit for the
period, profit before tax less tax, and EPS x shares all agree. The quarter is then excluded and the company may fall back
to its standalone filing. That is safe (fails closed) but throws away good data. A careful fix: when both shares are
exactly zero, profit for the period is non-zero and EPS x shares corroborates it, treat the split as 'not filled in' and use
profit for the period, labelled as such. It changes extraction output, so it needs its own tests and a snapshot rebuild
(about 70 minutes). Not started; not a founder decision.

