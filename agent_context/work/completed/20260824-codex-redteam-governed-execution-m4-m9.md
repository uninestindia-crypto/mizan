# Independent Red Team: governed execution Majors 4-9 recheck

STATUS: COMPLETE
OWNER: Codex (independent adjudicator and founder-approved Phase 2 repair owner)
TOOL: Codex
STARTED_UTC: 2026-08-24T10:21:06Z
COMPLETED_UTC: 2026-08-24T11:02:14Z
STARTING_REVISION: `ac47d7c5f41d8eb54fc6454cfbb4bcd778ef597c`
PHASE1_TARGET: `deccec176c3791c010238f54452dacd00e212b14`
PHASE2_BASE: `81f4f1be41b54421e0d2f845c086dd791fb88889`
PHASE2_REPAIR: `96080e75442c63ab2ca3201f651b827293d9ca55`
WORKTREE_OR_BRANCH: `D:\quant_system_workspaces\worktrees\feature-governed-execution-phase2-81f4f1b-20260824-104547` on `codex/governed-execution-phase2`
ARTIFACT_DIRECTORY: `D:\quant_system_workspaces\scratch\qa-governed-execution-m4-m9-deccec1-20260824-102218`

## Objective

Independently recheck the governed-execution Majors 4-9 repairs, reproduce adjacent defects through
public interfaces, obtain founder approval before mutation, repair confirmed defects, and publish a
proof-backed Phase 2 verdict without live-money, broker-write, or promotion actions.

## Scope and owned paths

- `src/quant_system/execution/governed_strategy.py`
- `src/quant_system/execution/realtime_shadow.py`
- `tests/test_governed_execution_phase2.py`
- `.launch/reports/RED-TEAM-GOVERNED-EXECUTION-MAJORS-4-9-RECHECK.md`
- `.launch/reports/RED-TEAM-GOVERNED-EXECUTION-MAJORS-4-9-PHASE2.md`
- this completed record and the external QA artifact directory

## Non-goals

- No live-money routing, broker writes, or fabricated model promotion.
- No change to model features, labels, fitting, thresholds, holdouts, or campaign evidence.
- No claim that the broader independent feature-window Red Team is complete.
- No cleanup of another agent's changes, records, branches, or worktrees.

## Plan and current step

1. Complete Phase 1 discovery, attacks, full regression, and immutable report.
2. Obtain and record explicit Phase 2 approval.
3. Start from the committed canonical-window repair and write failing-first regressions.
4. Repair the three confirmed findings and kill plausible mutants.
5. Run independent, adjacent, static, real-evidence, and full regression gates.
6. Close the structured ledger, publish reports, reconcile, commit, and push.

All implementation, verification, reconciliation, audit, merge, and push steps are complete.

## Decision rationale

- Instrument identity is checked on every bar because a map key cannot prove the identity of the
  record it contains.
- Maturity eligibility is preflighted for the full same-symbol batch because financial state cannot
  be partially committed beneath a terminal failure audit.
- The public session catches only `GovernedExecutionError`, preserving a durable typed audit while
  allowing unrelated programming defects to remain visible.
- Legacy model evidence is refused after feature schema v2; no evidence is relabelled.

## Commands and outcomes

| Command/evidence | Outcome |
|---|---|
| Failing-first Phase 2 suite | 5 failed, 1 passed |
| Repaired Phase 2 suite | 6 passed |
| Three manual mutation probes | 3/3 killed |
| Adjacent governed/shadow suites | 76 passed |
| Independent matrix plus original probes | 27 passed |
| Final full suite at `96080e7` | 867 passed, 1 warning |
| Ruff lint | passed repository-wide |
| Strict Mypy | 121 source files passed |
| Owned-path Ruff format and craft checks | passed |
| Real evidence runner | exit 3, safe refusal, no session/order/promotion |
| Structured QA ledger | 23/23 passed, 144/144 weight, 7/7 milestones, release validation passed |
| Main reconciliation | fast-forwarded through the product and certification commits |
| Agent-claims / disk-layout audits | passed after retiring only this run's worktree and local branch |
| Remote delivery | feature branch and `main` pushed to `origin`; main includes the Phase 1 report |

## Files changed

- Added an internal-bar identity guard to governed execution.
- Added `GOVERNED_INPUT_INVALID` and narrow public-session exception containment.
- Made maturity-policy resolution a preflight before Decimal settlement mutation.
- Added six permanent regressions.
- Added Phase 1 and Phase 2 reports, this completion record, and external evidence artifacts.

## Blockers and conflicts

No blocker remains in the Majors 4-9 Phase 2 inventory. Separate work remains active for real
journey API/UI wiring and the broader feature-window independent Red Team; neither is included in
this closure.

## Stop point and next safe action

Phase 2 is merged and pushed. The derived repair worktree was removed after Git retirement; all
commits and evidence remain recoverable from Git and the recorded scratch directory. Continue the
real journey API task or the independent feature-window certification. A fresh schema-v2 real-data
training campaign is required before any governed model may reach shadow execution.
