# NOTICE: Qlib and PyBroker integration edits parts of paths claimed by the retail-redesign record

STATUS: NOTICE (additive; no other record is edited)  
FILED_BY: Claude Code (Sonnet 5.5), `20261009-1250Z-claude-sonnet-open-source-integration.md`  
FILED_UTC: 2026-10-09  
FOR: `20260928-claude-retail-redesign-build.md` (`HANDOFF_REQUIRED`)  
AUTHORIZATION: founder instruction in chat, 2026-10-09 ("learn and integrate it so we can use it in our platform")  
FILED UNDER: PROTOCOL section 8.4

## Paths edited that your record names

- `src/quant_system/server/v2/router.py`: one route that returns the risk of the hand-entered holdings; one new file
  `server/v2/portfolio_risk.py`; one more route in `broker_routes.py` (my own earlier file).
- `src/quant_system/lab/runner.py` and `lab/stats.py`: the Lab result gains a `ranges` entry; a new file `lab/ranges.py`.
  Existing fields, the verdict and the deflated-Sharpe probability do not change.
- `frontend/src/pages/Portfolio.tsx`, `LabRun.tsx`, `lib/queries.ts`, `lib/types.ts`: a risk card and range lines, appended.

## Section 8.4 preconditions checked

Your record says `HANDOFF_REQUIRED (branch complete and verified; awaiting founder review before any merge)` and names no gate
that must land first. The numbers it pins that this could move are test counts: this work adds tests and removes none. The
Lab's verdict, its trial counting and its stored results are not changed; `ranges` is an addition to the result.

## What this does not change

The Lab's verdict thresholds, the deflated-Sharpe probability, any stored run, the hand-entered Portfolio figures, and
anything a paper book trades.
