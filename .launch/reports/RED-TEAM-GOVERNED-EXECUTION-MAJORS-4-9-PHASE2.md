# Governed execution Majors 4-9 — Phase 2 closure

## Verdict

**READY within the governed-execution Majors 4-9 scope.** Phase 2 closes the two P1 defects and one
P2 defect independently reproduced in Phase 1. At exact product repair commit
`96080e75442c63ab2ca3201f651b827293d9ca55`, the structured ledger records 23/23 items passed,
144/144 weighted coverage verified, 7/7 run milestones complete, and zero failed or blocked items.
The release validator passes.

This verdict does not authorize live-money routing, model promotion, or execution of legacy model
evidence under the new feature schema.

## Repairs

| Finding | Repair | Public outcome |
|---|---|---|
| RT-GE-01, wrong instrument hidden under expected key | Every point-in-time bar must carry the same symbol as its bound map key | Direct scoring raises `GovernedExecutionError`; a public session returns `GOVERNED_INPUT_INVALID`, zero proposals, and zero broker writes |
| RT-GE-02, partial maturity settlement | Every same-symbol maturity is resolved before the first Decimal cash, position, outcome, or open-entry mutation | Any unresolvable entry halts the whole batch as a no-op; valid multi-entry batches still settle fully |
| RT-GE-03, governed provider exception escapes | `run_session()` catches only `GovernedExecutionError` around quote processing and maps it to a stable halt code | Malformed and duplicate provider output return a terminal audit instead of losing the session record |

The catch is deliberately narrow. Non-governed programming failures are not relabelled as an input
integrity event.

## Failing-first and mutation evidence

Before product edits, the new six-case regression file produced 5 failures and 1 pass:

- internal bar-symbol mismatch was accepted;
- the wrong-instrument public session completed;
- malformed and duplicate provider output escaped `run_session()`;
- the mixed maturity batch published a partial outcome.

After repair, all 6 pass. Three plausible mutants were then applied one at a time and killed:

1. inverting the bar-symbol guard caused the direct identity regression to fail;
2. replacing the governed catch with `ValueError` caused both public provider regressions to fail;
3. continuing after `MaturityPolicyError` caused the atomic maturity regression to fail.

Every mutant was restored before the final commit.

## Final verification

| Gate | Result |
|---|---|
| New Phase 2 regressions | 6 passed |
| Governed strategy/shadow adjacent suites | 76 passed |
| Independent Phase 1 matrix plus original probes | 27 passed |
| Full repository suite after final product commit | 867 passed, 1 dependency deprecation warning, 43.05 seconds |
| Ruff lint | All repository inputs passed |
| Strict Mypy | 121 source files passed |
| Ruff format, Phase 2-owned paths | 3 files already formatted |
| Code Craft / Test Craft, Phase 2-owned paths | Clean |
| Real-evidence runner | Bound the real GRASIM artifact, refused legacy/schema-less `RESEARCH_ONLY` evidence with exit 3; no session or order |
| Agent-claims and disk-layout audits | Required at final handoff after branch reconciliation |

The repository-wide Ruff format baseline has one inherited, out-of-scope file that would be
reformatted: `src/quant_system/modeling/trials.py`. The repository-wide craft scan also retains
legacy findings. Neither baseline failure is introduced by the three Phase 2-owned files, which are
individually clean.

## Canonical feature-window item

The Phase 1 blocker was a missing canonical history-window policy. Parent commit `81f4f1b` supplies
feature schema v2: the shared kernel consumes exactly the trailing 21 available bars, hashes only
those consumed bars, and refuses schema-v1 or schema-less model evidence at execution. The final
suite proves full-history and canonical-tail feature/score invariance and legacy relabelling refusal.

That item is passed for this audit inventory. A broader independent feature-window Red Team remains
a separate certification task and is not silently inherited by this closure.

## Model status

The training machinery and prior real-data campaign ran, but the current model is not deployable:

- 51 real governed attempts exist in the legacy campaign; 40 models were published and 11 attempts
  ended in typed failure.
- 0/40 published models are promotable; every verdict is `RESEARCH_ONLY`.
- Best campaign DSR after final multiplicity deflation is `0.397794`, below the `0.95` gate.
- All 40 published models predate feature schema v2 and are now intentionally non-executable.

A fresh real-data campaign under schema v2 is required. No legacy artifact was relabelled, promoted,
or used to start a shadow session during Phase 2.

## Evidence location

Structured coverage state, JUnit files, mutation/static notes, evidence records, and the final
dashboard are stored under:

`D:\quant_system_workspaces\scratch\qa-governed-execution-m4-m9-deccec1-20260824-102218`

Final dashboard: 100.00% audit completion, 100.00% verified coverage, 100.00% milestone completion.
