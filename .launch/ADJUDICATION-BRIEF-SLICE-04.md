# Slice 04 Adjudication Brief — Red Team recheck and Verifier

STATUS: READY — awaiting the repair revision
DATE: 2026-08-21
OWNER: the Slice 4 certification record

This brief is written **before** the repair revision exists, deliberately. The first Verifier round
reported that no Slice 4 baseline existed in `COMMANDS.md` at the revision it adjudicated, so it
could not have separated a pre-existing failure from a new one had anything failed. Writing the
adjudication criteria in advance removes that gap and stops the briefs from being shaped by whatever
the repair happens to produce.

Substitute `<REPAIR_REV>` throughout with the exact committed SHA supplied by the repair session.

## Preconditions — refuse to commission until all four hold

1. `<REPAIR_REV>` is **committed on `main`**. A clean clone can only reproduce committed state. Four
   of the first Verifier's five `NOT TESTED` verdicts came from state that existed only in the
   install root.
2. The full gate passes at `<REPAIR_REV>` from a fresh detached clone — not from the shared
   checkout, which carries unrelated uncommitted work under `src/quant_system/alpha/` that inflates
   the repository test count.
3. Every one of the Red Team's 4 Blockers, 7 Majors and 7 Minors is either repaired or explicitly
   accepted with a recorded rationale. A silently dropped finding is a failed repair round.
4. The evidence sheet's clean-state table has been re-measured at `<REPAIR_REV>`. The table
   currently describes `b24b4eb`, which is blocked.

## Independence rule

Neither adjudicator may be an agent that wrote any part of the repair, and the Red Team and the
Verifier must be separate agents from each other. Self-adjudication voids the result. This applies
to the certification agent too: it prepared the evidence, so it cannot adjudicate it.

Each adjudicator works in its own detached clone created with `scripts/new-workspace-clone.ps1`, and
is walled out of `D:\quant_system` entirely — other agents work there and a verifier that reads a
mutating tree verifies nothing reproducible.

## Red Team recheck — scope

Run first. If it returns any unresolved Blocker or Major, the Verifier run is discarded.

### Primary: the four Blockers must be re-attacked, not re-read

| # | Original Blocker | What the recheck must establish |
|---|---|---|
| 1 | Training labels maturing inside the validation window accepted | The maturity check binds, and cannot be bypassed by a fold that declares a conforming spec while supplying non-conforming rows |
| 2 | Published model evidence rewritable with false metrics | Metric and prediction hashes are re-derived on read, not copied; a rewritten record with a forged Sharpe fails; `rebuild_index()` reports it |
| 3 | Publish before readback verification bricks the catalog | Staged resources verify before publication; neither over-limit metadata nor a `bool` `schema_version` can leave an unreadable resource |
| 4 | A legal `trial_id` ending `_outcome` deadlocks the store | The reserved suffix is rejected at both start and outcome validation, and no legal id can collide with a derived resource id |

### Also required

- The seven Majors and seven Minors, each confirmed repaired or explicitly accepted.
- **Variant hunting.** Three of the four Blockers in the first round were variants that earlier
  repairs did not reach — correct fixes, scoped too narrowly. Assume the same of this round. For
  each repair, ask what neighbouring type, field, or code path the fix did *not* cover.
- The attack families not probed in round one, which remain open questions rather than passes: real
  crash/SIGKILL/disk-full injection, Slice 3 feature and point-in-time correctness, `net_return`
  versus cost arithmetic, scale beyond 70 rows, Windows PID reuse in lease recovery, cross-filesystem
  `os.replace`, and second-architecture reproducibility.
- **Whether Slice 5's holdout inherits Blocker 1's machinery.** Flagged in round one and unanswered.

Report to `.launch/reports/RED-TEAM-SLICE-04-RECHECK.md`. Every finding reproducible: exact command,
exact output, exact file and line. State at the top whether any unresolved Blocker or Major exists.

## Verifier — scope

Run only after a clean Red Team recheck.

Adjudicate every claim in `.launch/SLICE-04-EVIDENCE.md` as `PROVEN`, `DISPROVEN`, or `NOT TESTED`,
with raw output pasted for each. `PASS` or `BLOCKED`, no middle verdict; any `DISPROVEN` means
`BLOCKED`.

### Carry-forwards from the first Verifier round — both are binding

1. **Re-execute the eleven mutations at `<REPAIR_REV>`.** Round one marked the mutation row
   `NOT TESTED` because re-running a mutation requires editing a source file, which its scope
   forbade, and recorded that this made it weaker than the Slice 3 Verifier, which did re-execute.
   The mutation row in the evidence sheet is currently labelled `INHERITED from 6a17d5e`. Grant the
   scope to edit-and-restore inside its own clone so the row can become measured.
2. **The focused-suite figure changed meaning.** `scripts/run-slice4-gates.ps1` now selects by
   pattern rather than a fixed list (`5200741`), after the fixed list was found to exclude
   `test_multiplicity.py` and all three repair-round regressions. Confirm the pattern-based suite
   actually selects every Slice 4 regression at `<REPAIR_REV>`, and that its count matches the
   evidence sheet.

### Specific claims to reproduce independently

- The pinned replay identities, through a driver the Verifier writes itself against
  `run_persisted_ridge_trial` over `governed_training_journey`, across two independent evidence
  roots. **These hashes are expected to change**: the repairs alter published payloads, so the
  values in the evidence sheet must be re-pinned at `<REPAIR_REV>` and the Verifier is checking that
  the sheet's new values match what it derives, not the old ones.
- Byte-identical published files across two independent roots.
- No holdout opened anywhere in the slice; `RESEARCH_ONLY` the only verdict value, inside the hashed
  payload and re-enforced on read; scores `UNCALIBRATED_SCORE`; the string `probab` absent from
  Slice 4 source and tests.
- Status integrity: the sheet must not claim a certification it does not have.

### Do not repeat round one's install-root problem

Claims about `D:\quant_system` are unverifiable from a clone and must be marked `NOT TESTED` with
the reason stated, never inferred. The evidence sheet has already had one install-root explanation
withdrawn as unsound after the first Verifier disproved it; any remaining install-root sentence
should be dropped rather than defended.

Report to `.launch/reports/VERIFIER-SLICE-04-FINAL.md`.

## On completion

Only when the Red Team recheck reports no unresolved Blocker or Major **and** the Verifier returns
`PASS`:

1. `.launch/SLICE-04-EVIDENCE.md` → `STATUS: PASS`, with both report paths cited.
2. `.launch/SLICES.md` → Slice 4 row `PASS`, citing the repair revision.
3. `.launch/STATE.md` → close G4, record the decisions, set the next action to Slice 5.
4. `.launch/COMMANDS.md` → replace the superseded `b24b4eb` baseline with the `<REPAIR_REV>` gate.
5. Retire both Slice 4 work records to `work/completed/`, and the verification clones.

If either adjudication fails, none of the above happens. The slice stays `BLOCKED`, the findings are
recorded, and the repair round reopens. A partial pass is not a pass.
