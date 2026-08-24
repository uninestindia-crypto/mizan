# Work record: governed feature-window final independent recheck at 8f29564

STATUS: HALTED_ON_FINDING

OWNER: Codex / Dalton independent Red Team

STARTED_UTC: 2026-08-24T11:31:00Z

TESTED_REVISION: `8f29564680c3563e8694ad486429c068242738ab`

WORKSPACE:
`D:\quant_system_workspaces\verification_clones\redteam-governed-feature-window-final-recheck-dalton-8f29564-20260824-112501`

SCRATCH:
`D:\quant_system_workspaces\scratch\qa-governed-feature-window-final-recheck-8f29564-20260824-codex-dalton`

## Objective and outcome

Independently rerun the prior evaluator mismatch and, if it held, execute the 30 previously unrun
targets. The evaluator now returned typed `TRAINING_INPUT_MISMATCH` before any model/evaluation
identity. The next public-boundary attack found a Blocker: `compute_feature_values` accepted the same
21 valid bars in reverse chronology and silently returned six different values. Product testing
stopped immediately under the user's instruction; no repair was made.

## Owned artifacts

- `.launch/reports/RED-TEAM-GOVERNED-FEATURE-WINDOW-RECHECK-FINAL.md`
- This retired work record
- The exact clone and external scratch paths above

No prior record, report, clone, scratch tree, product source, or existing test was edited, adopted,
retired, removed, or reused.

## Commands and outcomes

- Canonical clone script: exit `0`; exact detached target created.
- `uv sync --frozen --extra dev --link-mode copy`: exit `0`; 47 packages, CPython 3.13.15.
- Fresh evaluator mismatch probe: exit `0`; `TRAINING_INPUT_MISMATCH`; no identities.
- Fresh reversed-kernel probe: exit `3`; six different feature values returned without typed error.
- Agent-claim audit: exit `0`; every visible workspace/branch claim resolved.
- Disk-layout audit: exit `0`; no stray QuantOS directory reported.
- Ledger: 31 items; 2 verified, 1 failed, 28 blocked; 5.33% verified coverage.
- Clone remained detached and clean. No command was running or stuck at retirement.

## Files changed

- Final Red Team report
- This retired work record

## Stop point and next safe action

Revision `8f29564` is blocked at the exported feature kernel's ordering boundary. A separate
implementation agent may add strict order handling and a failing-first regression. A fresh
independent recheck must rerun the evaluator and ordering reproductions, then execute all 28 items
listed as `NOT TESTED` in the report.
