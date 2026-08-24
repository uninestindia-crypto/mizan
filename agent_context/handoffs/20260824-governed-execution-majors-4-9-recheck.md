# Handoff: independently recheck governed execution Majors 4-9

STATUS: READY_FOR_ADOPTION
FROM: Claude Code — repair author
TO: Independent Red Team
DATE_UTC: 2026-08-24T10:15:54Z
ACTIVE_RECORD: `agent_context/work/completed/20260823-claude-redteam-repair-b1-b3.md`

## Objective and acceptance criteria

Independently try to break commit `deccec1` on the governed execution path. Reproduce the original
Majors 4-9, test bypasses of each repair through the public surfaces, and report raw output without
adopting the repair author's severity or closure claims.

## Repaired by the author

- Model execution is bound to the one symbol found in verified published decision records.
- Malformed bar-history values raise `GovernedExecutionError`; empty history remains no-signal.
- Unresolvable maturity halts as `MATURITY_UNRESOLVABLE` and preserves the session audit.
- Pre-open and post-close fills resolve to the session actually held through.
- Duplicate exchange dates are refused at the execution adapter boundary.
- Shadow audit reports include open-entry count and symbols.

## Files and ownership

- Commit under review: `deccec1` on `main`, pushed to `origin/main`.
- Repair record: `agent_context/work/completed/20260823-claude-redteam-repair-b1-b3.md`.
- Original Red Team record: `agent_context/work/active/20260823-redteam-governed-execution-path.md`.
- No uncommitted repair files remain. Unstaged analytics/modeling DSR work belongs to another agent.

## Verification observed by the repair author

| Command | Result | Notes |
|---|---|---|
| Five owned pytest suites, forward and reverse concurrently | exit 0 twice | 68 tests each run |
| `uv run pytest -q` | exit 0 | 855 tests; count includes another agent's unstaged DSR tests |
| Ruff, Ruff format, strict mypy, code-craft, test-craft | exit 0 | Exact repair paths |
| `uv run python scripts/run_governed_shadow_session.py` | exit 3 | Derived `GRASIM` from verified decisions, then refused `RESEARCH_ONLY`; no session ran |
| Claim and disk-layout audits | exit 0 | Run before handoff |

## Known failures and risks

- Blocker 2 remains open: feature values can depend on the amount of history supplied. No canonical
  execution window was selected, and this repair must not be cited as closing that issue.
- The repair was written and tested by the same author whose code was broken. None of its findings
  are independently adjudicated.
- `compute_feature_values` still accepts duplicate dates when called as a kernel. The claimed guard
  is at the execution adapter boundary; test whether any real governed execution route bypasses it.
- All persisted models remain `RESEARCH_ONLY`; the real runner reached the gate but did not run a
  market session.

## Exact stop point

`git push origin main` published `deccec1`. The final real-evidence command derived symbol `GRASIM`
from 40 verified model resources and returned the documented promotion-refusal exit code 3.

## Next safe action

Create a separately owned Red Team workspace/record, inspect the original probes under
`tmp/redteam-governed-exec/`, and rerun or strengthen them against `deccec1`. Start with public
`run_session()` and `scripts/run_governed_shadow_session.py` paths before directly calling helpers.

## Do not do

- Do not promote a `RESEARCH_ONLY` model to make the session run.
- Do not use synthetic data as evidence for the real-data path.
- Do not edit or stage the other agent's unstaged DSR boundary files.
- Do not report the repair as independently adjudicated until a separate agent has produced and
  recorded its own evidence.
