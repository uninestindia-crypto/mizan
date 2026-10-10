# Work record: plain wording, market holidays on the top bar, one rule for AAOIFI and TASIS disagreement

STATUS: COMPLETED (all four tasks done and gated; the coordinator stages and commits)  
OWNER: Claude Code (helper, spawned by the coordinator of `20261007-claude-shariah-mode-and-filing-proof.md`)  
TOOL: Claude Code  
STARTED_UTC: 2026-10-09T12:11:31Z  
STARTING_REVISION: `de5347b1de281bedb16d817c6f9479a55194df02`  
WORKTREE_OR_BRANCH: `/home/user/mizan`, branch `wip/halal-transparency` (pushed to `claude/wonderful-wozniak-6ek6zl`). No other worktree, no new branch.

GOAL_LINE: G6 (retail benefit: plain words, honest market state) and G2 (the same stock reads the same in both Mizan screens).

## Objective

Four small follow-ups found by earlier helpers, each verified against HEAD before changing:

1. The "Coding agents" tab and screen name read "AI apps".
2. The developer word "CLI" is removed from everything a person sees (AI choice card names, the engine's own sentences).
3. The top bar's market chip can say "Market open", "Market closed" or "Market closed, holiday" because the engine now
   serves the NSE trading holiday list; it keeps saying "Market hours" when the list does not cover this year.
4. The older screener tab follows the proof contract's one rule when AAOIFI and TASIS disagree (the engine's overall
   status wins when the row carries one), so a badge and the tab never disagree.

## Owned paths

Edited (existing):

- `frontend/src/pages/Tools.tsx` and its test, `frontend/src/components/topbar/screenName.ts` and its test
- `frontend/src/lib/aiSource.ts` and its test; any frontend file that matches on the old app names (found by search, listed below when touched)
- `src/quant_system/server/v2/cli_bridge.py`, `src/quant_system/copilot/cli_chat.py` (the `CLI_LABELS` text only), `src/quant_system/server/v2/updates.py` (two release-note lines), `src/quant_system/copilot/messages.py` (checked: no change needed), and the tests that pin those sentences (`tests/test_cli_bridge.py`, `tests/test_copilot_cli_chat.py`, plus the frontend tests named below)
- `frontend/src/lib/copilotHistory.ts` and its test, `frontend/src/pages/Settings.tsx` (two release-note lines only, precise Edit), `frontend/src/components/aiapps/appFixtures.tsx` (test fixture names), `frontend/src/components/AgentCliBridge*.test.tsx`, `frontend/src/components/settings/AiSource.test.tsx`, `frontend/src/components/copilot/SecondOpinionGroups.test.tsx`, `frontend/src/components/copilot/history/Answers.test.tsx`
- `src/quant_system/server/v2/router.py` (one import and one include line only)
- `frontend/src/components/topbar/` chip wiring only: `statusItems.ts` and `useStatusItems.ts` (pass the holiday list through), `marketHours.ts` (accept a date-to-name map, word the holiday label), `topbarKit.tsx` (an optional holiday answer for the test engine), and their tests `marketHours.test.ts`, `statusItems.test.ts`, `TopBar.test.tsx`
- `installer/quantos.spec`, `installer/quantos-studio.spec`, `quant_system.spec` (one data line each, precise edits)
- `tests/test_shariah_bundle_packaging.py` (extend) or a small new test beside it
- `frontend/src/lib/shariah.ts` (`overallStatus` only) and its test

New:

- `src/quant_system/server/v2/market_holidays.py` (read-only route) and `tests/test_market_holidays_route.py`
- `frontend/src/components/topbar/useHolidays.ts` and its test

## Not touched (another helper's, or not mine)

`frontend/src/pages/Stock.tsx`, `pages/Fundamentals.tsx`, `components/fundamentals/`, `components/portfolio/`,
`lib/fundamentals*.ts`, the one fundamentals sidebar entry in `Layout.tsx`, `lib/queries.ts`, `lib/types.ts`,
`data/**`, `.gitignore`. How a bank with no figures is badged is a founder decision and stays as it is.

## Non-goals

No commit or staging (the coordinator commits after re-running the gates). No repo-wide formatter. No change to any
Shariah threshold. No change to how the engine decides a verdict; only which already-computed status the older tab shows.
Gemini sign-in still opening a window (`signin_mode="terminal"`) is an engine change outside this brief.

## Plan

1. Task 1: rename "Coding agents" to "AI apps". DONE (verified at HEAD: `Tools.tsx:17`, `screenName.ts:22`; tests added)
2. Task 2: drop "CLI" from visible words. DONE (engine names, install label, error sentences, copilot label, release notes; fixtures and tests updated)
3. Task 3: holidays route, hook, chip, spec lines, packaging test. DONE (route `GET /api/v2/market/holidays`, three spec lines, packaging tests, hook `useHolidays.ts`, chip wiring, tests; mutation-checked: removing the covers-this-year rule fails 5 tests)
4. Task 4: one rule for AAOIFI and TASIS disagreement. DONE in two layers: (1) frontend rule + tests, (2) the engine sends `overall_status` on list rows and the audit, because the rule alone is not enough (see Decision rationale)
5. Gates (Python, frontend, craft checks, secret scan) and the final report. DONE (results below)

## Current step

Task 3 next (holidays). Task 2 (done) was: dropping the word CLI from visible text. Sites found at HEAD (verified by search, not taken from the brief): frontend `lib/aiSource.ts` APP_NAMES, `lib/copilotHistory.ts` ANSWERED_BY, release-note lines in `pages/Settings.tsx` (2) and `server/v2/updates.py` (2); engine `server/v2/cli_bridge.py` (3 names, one install step label, 2 error sentences, 1 window title), `copilot/cli_chat.py` CLI_LABELS (gemini). `copilot/messages.py` has no CLI wording. Not visible anywhere (left alone): `server/v2/aitools.py` names (no screen renders /ai-tools), `alpha/cli_manager.py`, `alpha/ai_advisor.py` default rationale (no screen renders it), docstrings and comments.

## Decision rationale

Each task description came from other helpers' reports, so each is checked against HEAD first and the finding is
written under "Commands and outcomes". Other records that mention the spec files and `router.py`
(`20261007-claude-shariah-proof-service-backend.md`, `20261007-claude-shariah-mode-screens-worker.md`) are finished and
committed; the coordinator explicitly assigned these paths to this record.

### Task 4: what the proof's rule is, and why the frontend rule alone is not enough (measured, not assumed)

The contract's rule, from `shariah/services/proof_builder.py::_verdict`: business fails -> NOT_COMPLIANT; every standard
that could be worked out says NOT_COMPLIANT -> NOT_COMPLIANT; business not confirmed, or a standard could not be worked
out -> QUESTIONABLE; COMPLIANT only when every standard passes; anything else (including one passes, one fails) -> QUESTIONABLE.
The older tab's `overallStatus` took the worse of the two (any NON_COMPLIANT -> NON_COMPLIANT).

What the rows send: `/stocks` rows (`CompanySummary`) carry `aaoifi_status`, `tasis_status`, `data_status`, `verdict_source`,
`as_of` and NO overall; `/stocks/{t}/audit` carries the same plus two evaluations and NO overall; only `/stocks/{t}/screen`
carries `overall_status`, and it already follows the proof. In the older three-value form a standard the engine could not
work out (`NOT_COMPUTED`, e.g. AAOIFI with under 34 months of prices) is shown as QUESTIONABLE (`verdict_overlay.standard_status`),
so the two statuses cannot always reproduce the proof.

Measured (read-only script in my scratchpad, bundled snapshot, no market data loaded, 350 stocks with a filing proof):
the OLD rule matched the proof's verdict on 350 of 350; a pure "contract rule on the two statuses" differs on 69 of 350
(all: AAOIFI not worked out, TASIS fails, proof says NON_COMPLIANT, two-status rule says QUESTIONABLE). So replacing the old
rule with the contract rule alone would have made 20% of these stocks disagree with their badges in the other direction.
Decision: (1) frontend `overallStatus(aaoifi, tasis, engine?)`: the engine's own verdict stands when the row carries a
known one; otherwise the contract rule on the two statuses (exact for the sample rows, which never have an unworked
standard); (2) the engine adds an optional `overall_status` to list/detail rows and to the audit when a filing proof exists
(= the proof's verdict, the same word `/status` gives the badge). A bank with no figures is untouched: both of its
standards are NON_COMPLIANT in every form, so it reads Not compliant before and after; the badge's "Not screened"
collapse is not touched.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git status --short --branch` | CLEAN at start apart from two SQLite side files | `data/shariah/halal_stocks.db-shm` and `-wal` belong to the running app; must not be committed |
| pytest: `tests/test_cli_bridge.py test_copilot_cli_chat.py test_updates.py test_market_holidays_route.py test_no_terminal_copy.py test_shariah_bundle_packaging.py tests/shariah` | PASS | 1,145 passed, 2 skipped (Windows-only terminal windows, pre-existing) |
| pytest: `tests -k 'cli_bridge or copilot or v2_api or packaging or no_terminal or update or holiday or health or paper'` | 1 FAIL, 1,724 passed, 5 skipped | the failure is `tests/test_v2_api.py::test_every_page_the_web_app_defines_is_served_on_reload`: `/fundamentals` is in the fundamentals helper's uncommitted `App.tsx` but not in `server/v2/spa.py`. Not mine, not touched |
| `ruff format --check` and `ruff check` on the 16 Python files I changed | PASS | |
| `mypy --platform win32` on the 9 changed src files | PASS | |
| `npx tsc --noEmit -p .` and `npx vitest run` (whole frontend suite) | PASS | 99 files, 1,492 tests |
| `node scripts/check-code.mjs` / `check-tests.mjs` vs the same files at HEAD | NO NEW findings | old findings are the project baseline; `router.py` and `types.ts` were already over the god-file limit (only the line count in the message moved) |
| `detect-secrets scan` on every changed/new file | 0 new | 8 hits in `Settings.tsx` lines 456-519 pre-exist (environment-variable names such as `LIGHTNING_API_KEY`, not values); my diff to that file is lines 1257 and 1279 only |
| mutation checks | caught | removing the covers-this-year rule fails 5 frontend tests; removing `overall_status` from `filing_fields` fails 4 engine tests; both restored |
| `scripts/audit-agent-claims.ps1`, `audit-disk-layout.ps1` | NOT RUN | PowerShell, not available in this Linux container |
| browser check | NOT RUN | no real-browser check of the chip or the screener; covered by component tests only |

## Files changed

- `frontend/src/pages/Tools.tsx` (EDITED, 1 line): tab label "Coding agents" -> "AI apps"
- `frontend/src/components/topbar/screenName.ts` (EDITED, 1 line): same for the top bar name
- `frontend/src/components/topbar/screenName.test.ts` (EDITED, 1 row): pins `/tools/agents` -> "AI apps"
- `frontend/src/pages/Tools.tabs.test.tsx` (NEW): pins the tab names and that no "Coding agents" shows
- `src/quant_system/server/v2/cli_bridge.py` (EDITED): spec names "Antigravity CLI"/"Codex CLI"/"Gemini CLI" -> "Antigravity"/"Codex"/"Gemini" (so the engine's "X is installed." and "X is connected." sentences and the card's data-app-name follow); install step label "Installing Gemini CLI" -> "Installing Gemini"; two "Unknown agent CLI" errors -> "Unknown AI app"; terminal window title "Agent CLI - ..." -> "QuantOS - ...". Ids, commands, docstrings and comments unchanged.
- `src/quant_system/copilot/cli_chat.py` (EDITED, 1 line): CLI_LABELS gemini "Gemini CLI (your Google sign-in)" -> "Gemini (your Google sign-in)"
- `src/quant_system/server/v2/updates.py` (EDITED, 2 lines): release notes of 2.1.0 and 2.0.1 no longer say CLI
- `frontend/src/pages/Settings.tsx` (EDITED, 2 lines): the same two release-note lines in the fallback list
- `frontend/src/lib/aiSource.ts` (EDITED, 1 line): APP_NAMES gemini "Gemini CLI" -> "Gemini"
- `frontend/src/lib/copilotHistory.ts` (EDITED, 1 line): "Answered by Gemini CLI" -> "Gemini"
- Tests and fixtures (EDITED): `frontend/src/lib/aiSource.test.ts` (+appName test), `lib/copilotHistory.test.ts`, `components/settings/AiSource.test.tsx` (+Gemini jump test, CLI added to the plain-words check), `components/copilot/SecondOpinionGroups.test.tsx`, `components/copilot/history/Answers.test.tsx`, `components/AgentCliBridge.test.tsx`, `components/AgentCliBridge.jobs.test.tsx`, `components/aiapps/appFixtures.tsx` (fixture names follow the engine), `tests/test_cli_bridge.py` (+2 tests), `tests/test_copilot_cli_chat.py` (+1), `tests/test_updates.py` (+1), `tests/test_no_terminal_copy.py` (the word CLI joins the developer words the guard bans in Copilot text; +1 catch row)
- `src/quant_system/server/v2/market_holidays.py` (NEW): `GET /api/v2/market/holidays` -> `{years:[2026], holidays:[{date,name}], source, fetched_at}`; reads `data/authorities/nse-trading-holidays.json` from the app root, the built app's folders, then the checkout; the copy reaching the latest year wins; any unreadable or inconsistent file gives an empty list with no years (the screen then keeps saying "Market hours"); trailing footnote mark on a name removed ("Diwali Laxmi Pujan*")
- `src/quant_system/server/v2/router.py` (EDITED, 2 lines): one import, one `include_router` line
- `installer/quantos.spec`, `installer/quantos-studio.spec`, `quant_system.spec` (EDITED, 1 line each): `nse-trading-holidays.json` -> `data/authorities`
- `tests/test_market_holidays_route.py` (NEW, 21 tests), `tests/test_shariah_bundle_packaging.py` (EDITED: +4 cases: 3 specs, 1 tracked/readable)
- `frontend/src/components/topbar/useHolidays.ts` (NEW) and `useHolidays.test.tsx` (NEW, 18 tests): asks `/api/v2/market/holidays` (6 h cache, no retry), trusts the list only when well formed and when it covers the year in India; otherwise undefined
- `frontend/src/components/topbar/marketHours.ts` (EDITED): `HolidayDates` type (set of dates, or map date->name); the holiday phase now reads "Market closed, holiday" and its tooltip names the holiday ("Today is a market holiday: Dussehra."); header comment corrected
- `frontend/src/components/topbar/statusItems.ts` (EDITED): optional `holidays` input passed to `marketStatus`; `useStatusItems.ts` (EDITED): calls `useHolidays(now)`
- `frontend/src/components/topbar/topbarKit.tsx` (EDITED): `HOLIDAYS_2026` and an optional `holidays` answer for the fake engine (served only when a test passes it, so the older tests still run the "no list" path)
- Tests: `marketHours.test.ts` (+5 cases, holiday label), `statusItems.test.ts` (+5), `TopBar.test.tsx` (+4)
- `frontend/src/lib/shariah.ts` (EDITED): `overallStatus(aaoifi, tasis, engine?)` now follows the proof's rule (Not compliant only when both fail, Compliant only when both pass, otherwise Questionable) and lets a known engine verdict stand; `ShariahStockRow.overall_status`; `toCompliance` passes it
- `frontend/src/lib/types.ts` (EDITED, +2 lines): optional `overall_status` on `ShariahAudit`
- `frontend/src/components/shariah/verdictModel.ts`, `StockResultCard.tsx` (EDITED, 1 line each): pass `audit.overall_status`
- Tests: `frontend/src/lib/shariah.test.ts` (rewritten to the contract rule, +engine-verdict cases; 23 tests), `components/shariah/ScreenerTab.test.tsx` (+2), `StockResultCard.test.tsx` (+2), `verdictModel.test.ts` (+2)
- `src/quant_system/shariah/schemas/company.py` (+7), `schemas/screening.py` (+7), `services/verdict_overlay.py` (+17: `overall_status_of`, one more field in `filing_fields`), `api/v1/endpoints/screening.py` (+2: audit carries it): additive optional `overall_status` = the proof's verdict, only when the row rests on a filing; sample rows send null
- `tests/shariah/test_verdict_overlay.py` (EDITED, +75 lines, +6 tests; mutation-checked: dropping the field fails 4)

## Blockers and conflicts

`frontend/src/components/topbar/screenName.ts` and `screenName.test.ts` also contain the fundamentals helper's change (the "/fundamentals" screen name), made while I worked; both edits are intact and neither of us touched the other's lines. Another helper is building the fundamentals screens (Stock.tsx, Fundamentals.tsx, components/fundamentals/,
components/portfolio/, lib/fundamentals*.ts, one sidebar entry in Layout.tsx); I stay out of those.

## Stop point

All four tasks finished at ~12:45Z and gated. Nothing staged or committed by me. No scratch build was made. My scratch
files are only under the session scratchpad (a measurement script and HEAD copies). `.mypy_cache`, `.pytest_cache`,
`.ruff_cache` in the repo root pre-date this work (5 to 7 Oct) and are git-ignored.

## Open points for the coordinator

1. `/stocks/{ticker}/screen` for a sample-only stock (no filing) still takes the worse of the two standards, while the
   badge's proof says Questionable on a split. Nothing in the app calls that route and eight tier tests pin its
   sample behaviour, so I left it; changing it is a small follow-up if wanted.
2. Basket constituents (Baskets tab) show the sample's two statuses, not the filing's, so a basket stock can still read
   differently from its badge when a filing exists. The new rule makes the sample reading agree with the proof's rule.
3. User-visible change in the older tab: a stock where one standard passes and the other fails now reads "Questionable"
   (as its badge always did) instead of "Non-Compliant". A stock both standards fail, and a bank, still read
   "Non-Compliant". How a bank with no figures is badged is untouched (founder decision).
4. `tests/test_v2_api.py::test_every_page_the_web_app_defines_is_served_on_reload` needs `/fundamentals` added to
   `src/quant_system/server/v2/spa.py` (the fundamentals helper's or the coordinator's change).
5. Three copies of the "where is a bundled data file" root list now exist (`shariah/services/proof_paths.py`,
   `fundamentals/runtime.py`, `server/v2/market_holidays.py`); a shared helper would remove the duplication.
6. `server/v2/aitools.py` (`/api/v2/ai-tools`) still names the apps "Codex CLI"/"Gemini CLI"; no screen shows it, so I
   left it. The Gemini sign-in window (`signin_mode="terminal"`) is an engine change outside this brief.

## Next safe action

Coordinator: re-run the gates, stage the exact paths listed in the report, commit, then move this record to
`agent_context/work/completed/`.
