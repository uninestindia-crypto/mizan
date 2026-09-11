# Active work: return the CI gate to green

STATUS: ACTIVE
OWNER: Claude Code
TOOL: Claude Code
STARTED_UTC: 2026-09-10T18:30:00Z
STARTING_REVISION: `eae79270`
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout)
AUTHORIZATION: founder instruction, 2026-09-10 — "go ahead, fix them all", given after this session
reported that the gate's two red steps sit entirely in other agents' claimed paths and asked
explicitly whether to cross those claims.

## Why this record exists

`.github/workflows/ci.yml` runs `Ruff format` as step 2, so its failure skips `Strict mypy`, both
test steps and the craft self-tests. **No commit has been verified by CI since at least 2026-09-09.**
Diagnosis and the full ownership map:
`20260910-NOTICE-ci-gate-red-blocks-all-verification.md`.

Billing is *not* the blocker and `CURRENT.md` is stale on that point — runs execute for 1m13s-1m38s.

## Ownership resolution (PROTOCOL §3, §4, §8.3)

Every path below is claimed by another record. PROTOCOL §8.3 makes explicit founder instruction the
sanctioned route to act on another agent's paths, and that instruction was given for this specific,
named set after the collision was put to the founder in writing.

| Paths | Prior claim | Basis for editing |
|---|---|---|
| `scripts/run_claude_analysis.py`, `run_claude_engineering_edits.py`, `run_gpt56_sol_second_opinion.py`, `run_mizan_dual_opinion.py`, `run_mizan_live_audit.py` | `20260904-antigravity-claude-fable-analysis` ACTIVE | founder instruction |
| `scripts/run_mizan_dual_opinion_bedrock.py` | `20260910-claude-bedrock-dual-model-audit` ACTIVE | founder instruction |
| `src/quant_system/execution/paper_portfolio.py`, `tests/test_paper_portfolio.py`, `tests/test_paper_pilot_carried_session.py`, `tests/test_platform_assistant.py` | `20260821-1048Z-claude-slice4-redteam-repair` HANDOFF_REQUIRED | founder instruction |
| `src/quant_system/research_xs_monthly/**`, `scripts/run_xs_monthly_*`, `scripts/serve_xs_watch_dashboard.py` | `20260903-hermes-xs-monthly-screen-new` ACTIVE | founder instruction |
| `scripts/timesfm_probe.py`, `scripts/npu_feasibility_probe.py` | `20260910-1615Z-claude-mizan-correction-and-short-horizon-program` ACTIVE | founder instruction |
| `reports/claude_opus_audit/*.md` | unclaimed | — |

**This is not an adoption of any of those records.** Their objectives, their other paths and their
status all stay exactly as they are. This record touches only what the two gates name, and a NOTICE
goes to each owner.

Every file was verified **clean in the working tree** immediately before editing, so no agent is
mid-edit in any of them.

## Owned paths

The union of the table above, plus:
- `agent_context/work/active/20260910-claude-ci-gate-green.md` (this file)

## Non-goals

- **No behaviour change of any kind.** `ruff format` is semantically neutral by construction. Mypy
  repairs are annotations and narrowing only — no control flow, no logic, no test expectations.
- No edit to any path the two gates do not name, however tempting while in the file.
- No change to `.github/workflows/ci.yml`. Relaxing a gate to make it pass is not fixing it.
- No adoption or retirement of another agent's record.
- No commit of another agent's unrelated in-flight work.

## Plan

1. `ruff format` the 12 named files. Confirm `ruff format --check .` is clean.
2. Repair the 41 mypy errors, file by file, smallest blast radius first.
3. Re-run the full CI sequence locally: ruff check, ruff format, mypy, pytest forward and reverse.
4. Commit only the named paths; push; confirm the remote run goes green.
5. File the owner NOTICE.

## Baseline before any edit (measured at `eae79270`)

| Gate | State |
|---|---|
| `ruff check .` | All checks passed |
| `ruff format --check .` | **12 files would be reformatted** |
| `mypy src launcher.py scripts` | **41 errors in 13 files** |
| `pytest tests/ -q` | **1455 passed** |

The suite already passes, so any test that breaks during this work is a regression I introduced and
must be reverted, never re-baselined.

## Current step

Step 1.
