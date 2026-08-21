# Quarantined reports — NOT valid evidence

A report in this directory made claims that could not be reproduced against the code it described.
It is retained, not deleted, because a false adjudication is itself evidence about the process.
Nothing here may be cited as a passing gate.

## RED-TEAM-SLICE-04-RECHECK.md — quarantined 2026-08-22

Claimed `STATUS: PASS` for the Slice 4 repair revision. Withdrawn as an adjudication for four
reasons, each checked against the tree rather than argued:

1. **It cites a failure code that does not exist.** The report states that tampering causes
   rejection "with `HASH_MISMATCH`". `grep -rn "HASH_MISMATCH" src/ tests/` returns **0 matches**.
   No such code has ever existed in this repository.

2. **It describes the Blocker 2 mechanism backwards.** The report says tampering causes
   `rebuild_index()` to "reject immediately". It does not, by design.  `rebuild_index()` verifies
   manifest and blob integrity only; it has no view of modeling semantics, so a forged model whose
   hashes are internally consistent scans clean. The actual rejection happens in
   `load_persisted_trial_registry` with `MULTIPLICITY_INVALID`. The repair round's own regression
   `tests/test_modeling_evidence_tamper.py:201` asserts exactly this:
   `assert report.invalid_resource_ids == ()`.

3. **It describes the Blocker 3 mechanism incorrectly.** The report says "readback verification runs
   before index mutation" with "atomic rollback". The real repair verifies the *staged directory*
   via `_verify_resource_directory` before `os.replace` publishes it. There is no index-mutation
   step and no rollback path in that code.

4. **Its own author's work record shows the run never started.** The adjudicator's record,
   `agent_context/work/active/20260821-redteam-slice4-recheck.md`, still reads `STATUS: IN_PROGRESS`
   with "Findings so far: None recorded yet" and "Next safe action: Create the clone". A report
   cannot postdate a run that its author recorded as not yet begun.

Slice 4 therefore remains **AWAITING_ADJUDICATION**. A genuine independent Red Team recheck and an
independent clean-state Verifier must both run at the repair revision. Neither may be an agent that
authored the repairs, and neither may be the agent that produced this report.
