# Completed work: fixes from a stranger walkthrough of the first-run app

STATUS: COMPLETED  
OWNER: Claude Code session (founder: "push it and do the rest ... so that we can move once for all")  
TOOL: Claude Code  
DATE: 2026-10-04  
STARTING_REVISION: 256a6f65a (main)  
WORKTREE_OR_BRANCH: the install root, branch `main` (shared checkout, no worktree)

## Objective

Have a fresh-eyes agent (`customer-zero`, no knowledge of the code) use the app from an empty state, then fix what a real
stranger would trip on. Its friction log was 3 blockers, 12 major and 16 minor findings (kept in the session scratchpad,
`friction_log.md`; summarised here).

## Owned paths

`frontend/src/**` (pages Welcome, Settings, Home, Lab, LabNew, LabRun, Stock, Paper, Tools; components Layout, common,
AgentCliBridge; `lib/api.ts`, new `lib/rules.ts` and `lib/rules.test.ts`), `src/quant_system/lab/{runner,stats}.py`,
`src/quant_system/market/{downloader,index_builder}.py`, `tests/test_lab.py`, `tests/test_market_downloader.py`,
`tests/test_market_index.py`. No active record claims these paths.

## A real defect found and fixed (not a wording issue)

The Strategy Lab's "whole list" comparison is simulated with Rs 100 crore of notional money and its equity is scaled down to the
user's capital, but its charges and slippage were not. A Rs 50,000 test showed "Charges paid Rs 11,91,059" next to a Rs 4.15 lakh
result. The list column now reports Rs 59.55 for the same run. Regression test fails on the old code (verified) and passes now.

## Blockers fixed

- Paper trading: the empty state no longer sends people to "connect the workspace's data folder". It says what a paper book is, that
  QuantOS cannot start one from this app yet, and links to the Strategy Lab. The welcome promise "practise with virtual money first"
  was replaced with what the app does deliver. **Creating a paper book inside the app is not built; that is the largest product gap.**
- A double-click on Run test saved two permanent tests (and each saved test raises the bar for every later verdict). A synchronous
  in-flight guard now allows one; measured 5 -> 6 runs after a real double-click.
- `/stock/<unknown>` blanked the whole window (React error 300: an early return before two hooks). The error return now sits below all hooks.

## Majors and minors fixed

NIFTY tile now says it shows the NIFTY BeES ETF price, not the index level; welcome page no longer promises 3,000+ stocks; verdicts
say "percentage points" and "more than luck" and "not a forecast", plus a hindsight warning for hand-picked stocks; money rules show
their limits up front and report every problem at once (shared `lib/rules.ts`, also used to humanise engine validation errors);
Lab capital minimum stated; "Test again" keeps the previous settings; start-date clamp explained; left-out stocks are explained in words
("8 days where the high, low and close do not fit together") not codes; download progress shown in the sidebar, empty states and
Settings (and the contradicting "searching" banner removed); empty-data states point to the download; both search boxes pick the best
fresh match on Enter (stale results are never offered); "Pages" no longer appears under "No matches"; accounts, broker and AI-key
sections say they are optional and what they do or do not do; coding agents explained and the tab renamed; Tools no longer shows a grey
box for quantity 0 and warns when a stop-loss above entry makes a short; the stock-page note "only the recent refresh exists" is no longer
shown for a ten-year download; plural "1 test", DP-charge hint, disabled-button hints.

## Not changed (reported)

Creating paper books in the app; old company names in search (Zomato for ETERNAL, Vodafone Idea left out by the data checks because the
provider's history has one impossible volume); NIFTY index level (the data has only the ETF); the classic console link still opens
developer vocabulary (now labelled advanced); the wizard restarts at step 1 on reload; broker presets; the NIFTY 500 download is not
all listed stocks.

## Verification

`ruff`, `mypy` (251 files, excluding another agent's uncommitted `scripts/generate_moonshot_pdf.py`, which has 5 lint and 26 type errors
of its own), `vitest` 18 passed, pytest on the touched areas 176 passed. Browser checks against a stranger-state app: unknown stock page,
double-click Run test, the re-run momentum test (list charges Rs 59.55, new verdict text).
