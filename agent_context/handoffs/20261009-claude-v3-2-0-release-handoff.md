# Handoff: v3.2.0 release and what is left

STATUS: READY_FOR_ADOPTION  
FROM: Claude Code (cloud session, coordinator of the Shariah proof, fundamentals and screens work)  
TO: the founder, working locally (or any agent the founder starts)  
DATE_UTC: 2026-10-09  
ACTIVE_RECORD: none. Every record of this work is in `agent_context/work/completed/20261007-claude-*.md`; the coordinator's is
`20261007-claude-shariah-mode-and-filing-proof.md` and has the full history, with every number and decision.

GOAL_LINE: G2 (one app, two modes), G3 (factory-new laptop), G6 (benefit to retail users)

## Objective and acceptance criteria

The founder asked for the work to be merged to `main` and released so it can be tested, and for everything to be finished
so the cloud session can be deleted and work can continue locally. Done means: pull request merged, release published with
its installer and fingerprint file, every record closed, every open decision and every remaining task written down here.

## Completed (all on `main` and in the release)

- Shariah results come from each company's own filing where the app holds one (proof service and endpoints), with the filing
  behind every figure and an "out of date" label. One rule when the two standards disagree, on the badge, the stock card and
  the screener tab (the contract's rule: questionable).
- Fundamentals from filings: engine, bundled snapshot of 412 companies (`data/fundamentals/fundamentals_snapshot.json.gz`),
  Fundamentals screen (filters you choose, compare up to four), the Stock page section, the Portfolio tab, holding periods as
  facts, a Copilot tool, and "Get the latest results" inside the app.
- Portfolio with several accounts; "Add to portfolio" asks which account.
- Top bar, "Update and restart" dialog in Settings > About, plain-words AI apps card, "AI apps" naming, no "CLI" in visible
  words, an NSE holiday route for the market chip.
- The release workflow (`.github/workflows/release.yml`) now publishes `SHA256SUMS-<tag>.txt`, which the in-app updater
  needs. Without that file the button refuses to install (by design).
- CI fixes found on the way: changelog tests no longer pin a version; the PyBroker test skips when `alpaca-py` (research
  extra) is absent instead of stopping collection of the whole suite; one handoff note's Python sample is formatted.

## In progress

Nothing. There is no uncommitted work and no running helper.

## Open decisions for the founder (nobody should settle these by guessing)

1. Bank, lender or any business that fails the sector rule, with no usable figures: the proof says Not compliant with data
   status Not screened; the badge shows "Not screened". Which should a person see?
2. Fundamentals rules of thumb (`src/quant_system/fundamentals/scorecard.py`, `RULES`): profit in at least 6 of the last 8
   quarters, growth not below zero, interest cover at least 3, borrowings at most 1x owners' money, ROE at least 12%.
   Confirm or change. They are shown as "inside / outside the rule of thumb", never as good or bad.
3. "Held more than 12 months" means strictly after the same date a year later (29 Feb counts as 28 Feb). Right line?
4. Hide companies whose newest filing is over 18 months old from the Fundamentals screen by default? Today they are shown,
   counted and labelled.
5. Should banks and lenders (50 of the 412 companies) get their own reader? Today: "format not read".
6. Small UI choices: remember the chosen account in `localStorage` (survives restarts) or per session; the labels "By stock"
   and "By lot"; scorecard words versus the literal OK / WATCH; theme toggle on phones (none today); inline top-bar chips
   need about a 1,870 px window, below that one Status button.
7. The product is now called "Mizan Quant OS" in the installer and release names, but many visible strings still say
   "QuantOS". Rename everywhere, or keep both?
8. From earlier in the program, still open: the repository is public in reality while `AGENTS.md` says private;
   `community.py` has invented data under "verified" labels; zakat and purification constants are assumed; the installer is not
   code-signed (Windows may ask to confirm); the bundled Shariah filings are out of date (newest period Dec 2024).

## Remaining work, in the order I would do it

1. **Fundamentals: stop throwing away good quarters.** In the bundled build, 414 of 2,915 quarters (14%) failed a check, and
   382 of those failed only "owners and minority shares add up to profit for the period". In the cases read (for example
   AJANTPHARM consolidated, Mar and Jun 2023) the filer reported both shares as exactly 0.00 while profit for the period,
   profit before tax less tax, and EPS x shares all agree. Proposed rule: when both shares are exactly zero, profit for the
   period is non-zero and EPS x shares corroborates it, treat the split as "not filled in" and use profit for the period,
   labelled as such. Needs tests (use `tests/fixtures/fundamentals/`) and a snapshot rebuild:
   `uv run python scripts/build_fundamentals_snapshot.py` (about 70 to 90 minutes, polite one request at a time, resumable with
   `--resume-dir`). Do not run it at the same time as a Shariah filings refresh (the two NSE jobs share no gate).
2. **Read real filings and newer data.** NSE's feed seen from the cloud ends around January 2025, so both bundled snapshots
   are out of date and labelled so. Rebuild them from your own machine (Shariah: `scripts/` filings builder named in the
   coordinator record; fundamentals: the script above) and commit the new `.gz` files. People can also press "Get the latest
   results" / refresh inside the app.
3. **NSE holiday list for 2027** (`data/authorities/nse-trading-holidays.json` covers 2026 only). Before 1 January 2027 the
   market chip says "Market hours" instead of "Market open". The health check warns 90 days ahead.
4. **Test on real Windows** what could not be run in the cloud: install `MizanQuantOS_v3.2.0_Setup.exe` on a clean laptop,
   check WebView2 handling (bundled setup plus main's download page both exist in the installer script), press Update and
   restart once a later release exists (v3.2.0 to the next), run `scripts/audit-agent-claims.ps1` and
   `scripts/audit-disk-layout.ps1`.
5. Small engineering debts: Gemini sign-in still opens a window (`signin_mode="terminal"` in
   `server/v2/cli_bridge.py`); `/api/v2/ai-tools` still says "Codex CLI" / "Gemini CLI"; `/stocks/{ticker}/screen` for
   sample-only stocks and the baskets still show the sample's statuses; the "where is a bundled data file" root list exists in
   three places (`shariah/services/proof_paths.py`, `fundamentals/runtime.py`, `server/v2/market_holidays.py`); the Portfolio
   "no filing data" list looks reasons up one stock at a time (add a reason field to `portfolio_fundamentals`);
   `ruff check .` run locally reports errors in the vendored folders `Learn from open source codebase/` and `skills/` while CI
   passes, so check how CI excludes them and make the config explicit.
6. Research stays closed (see `agent_context/CURRENT.md` "Next safe actions"): no model trial without its own declaration.

## Files and ownership

- All of the above is committed and merged. The working tree of the cloud session was clean when this note was written.
- `agent_context/CURRENT.md` is stale (last full snapshot 2026-09-14 plus the Kronos section). It is claimed by two older records
  and was not edited; the coordinator should refresh it from `.launch/STATE.md` and this note.

## Verification

| Command | Result | Notes |
|---|---|---|
| `cd frontend && npx tsc --noEmit -p . && npx vitest run` | PASS | 1,498 tests, 100 files, on the merged tree |
| `uv run --frozen pytest tests` (Linux, merged tree) | PASS after two test fixes | 5,473 passed, 18 skipped (Windows-only or no Tk) |
| CI "Static gates" on the pull request | PASS | ruff lint, ruff format, strict mypy: first green run on this line of work |
| CI "Craft checkers and audits" | PASS | includes the PowerShell claim and disk-layout audits |
| CI "Tests" (both orders, Windows) | see the release section of the coordinator record | |
| Real Windows install and update | NOT RUN | cannot run in the cloud |
| Real NSE read, newest filings | NOT RUN | the cloud-visible feed ends around Jan 2025 |

## Known failures and risks

- Every bundled filing is out of date and labelled so; no result computed from them should be quoted as current.
- The one-click update has never run on a real Windows machine. If it misbehaves, the release page link beside it always works.
- Two NSE jobs (Shariah refresh and Fundamentals read) can run at once; keep to one at a time by hand.

## Exact stop point

All helpers finished and everything is committed. When this note was first pushed, pull request 11 was open with the Windows
test jobs still running; the merge to main, the release workflow run and the removal of the hourly "Keep QuantOS agents
moving" routine were the only steps left. A later commit on `main` replaces this paragraph with the result. If it still
reads like this, look at the pull request and at the Releases page to see how far the closing steps got.

## Next safe action

On the local machine: `git fetch origin && git switch main && git pull --ff-only`, `uv sync --frozen --extra dev`,
`cd frontend && npm ci`, then work item 1 above (it is self-contained and testable).

## Do not do

- Do not edit a version number by hand; use `python scripts/bump_version.py <X.Y.Z>` and add a real entry at the top of
  `CHANGELOG.md`, `OFFLINE_CHANGELOG` in `server/v2/updates.py` and the fallback list in `frontend/src/pages/Settings.tsx`
  (the script only relabels the top entry, it does not add one).
- Do not run `scripts/release.ps1` and the GitHub release workflow for the same version; both create `SHA256SUMS-<tag>.txt`.
- Do not push to `main` between starting the release workflow and its end: the release tag is cut from main's newest commit.
- Do not commit `data/shariah/*.db-shm` / `*.db-wal` (now ignored) or anything under `tmp/`.
