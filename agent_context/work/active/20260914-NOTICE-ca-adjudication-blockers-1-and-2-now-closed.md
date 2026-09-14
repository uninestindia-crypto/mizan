# NOTICE: two of the corporate-action adjudication's five blockers are closed; its verdict still reads BLOCKED

STATUS: ACTIVE (notice only — `.launch/reports/` was **not** edited)
FILED_BY: Claude Code (Opus 5), session `quant-system-c2`, 2026-09-14T19:05Z
SUBJECT: `.launch/reports/ADJUDICATION-CORPORATE-ACTIONS-20260911.md`
OWNED_BY: `20260911-2330Z-claude-adjudication-corporate-actions.md` (COMPLETED), whose
`OWNED_PATHS` names that report and its own record only.

## Why this notice exists

The report reads `VERDICT: **BLOCKED**` (line 7) and lists five blocking items (line 593). **Items 1
and 2 are now repaired and independently re-measured.** The report is not edited, for the reason a
peer session stated well today about a different dated adjudication: it was correct when written, and
editing it would fabricate an adjudication that never happened.

The conflict matters more here than it would in `reports/`. `agent_context/README.md` puts
`.launch/` **above** `CURRENT.md` and completed work records in the source-of-truth order. So a
reader following that hierarchy correctly reaches "BLOCKED on DEFECT-1" and stops, without reaching
the evidence that DEFECT-1 is closed. README also says: *"Do not silently choose between conflicting
sources. Record the conflict and resolve it with evidence."* This is that record.

## Status of each blocking item, with who measured it

| # | Item | Status | Measured by |
|---|---|---|---|
| 1 | **DEFECT-1 (P1)** rights issues never parsed, never gap-tested, never recorded unresolved | **CLOSED** | **This session**, independently. All four of the report's own reproductions emit an `UnresolvedRecord`, gaps reproducing to the digit (BHARTIARTL -6.98%, HCC -22.94%, CCAVENUE -9.01%, INTELLECT -8.96%). 255 of 255 rights records across the whole 3,359-symbol cache fail closed. Repaired at `c01cb89c`; a further hole in the repaired rule closed at `e0f0c316` |
| 2 | **DEFECT-2 (P2)** 493 of 5,083 dividend records (9.7%) silently unpriced | **CLOSED** | **This session**, independently re-measured against the committed authorities: **52 of 5,083 (1.0%)** remain unpriced, and those state no amount at all (`Interim Dividend` with no figure), so they are deliberately unpriced rather than misparsed. Repaired at `c01cb89c`, not by this session |
| 3 | **I2 partially disproven** — 5 deliberate defects survived all 1,477 tests | **NOT RE-CHECKED.** Unknown | Nobody, as far as this session can see. This session mutation-tested only its *own* new tests (4 of 4 killed) and makes **no claim** about the other five |
| 4 | **H5 disproven** — RAYMOND 2025-05-14 cited from the previous year's filings | Reported repaired by arbitration in `CORPORATE-ACTION-VALIDATION.md` | **Not verified by this session** |
| 5 | **C3 true but hollow** — the value-continuity check that alone can promote a demerger factor has never run and has no test | **STILL OPEN**, confirmed | **This session.** `grep` over `tests/` for the validator returns nothing. Unchanged since the report was written |

## What this notice does not claim

- **It does not clear the verdict.** Two of five items are closed and a third is confirmed still
  open; items 3 and 4 were not re-checked by anyone visible here. `VERDICT: BLOCKED` remains the
  report's own finding and only a further independent adjudication can change it.
- **It does not certify the repairs.** DEFECT-1's repair at `c01cb89c` was written by an author of
  the original code; the verification and the further repair at `e0f0c316` are this session's, and
  this session wrote everything it is vouching for. That is the same arrangement the 2026-09-11
  adjudication existed to correct.
- Nothing here changes release state, promotes any model, or touches live-money scope. No evidence
  store was written and no multiplicity ordinal spent.

## Evidence

`agent_context/work/active/20260914-1740Z-claude-rights-issue-fail-closed.md` and the
"Rights issues: the fail-closed rule, verified end to end (2026-09-14)" section of
`reports/corporate_action_validation/CORPORATE-ACTION-VALIDATION.md`. Commit `e0f0c316`.

## Next safe action

An agent that authored none of `c01cb89c` or `e0f0c316` should re-adjudicate items 1 and 2 and
re-check item 3's five surviving mutants. Until then, cite this notice alongside the report rather
than either alone.
