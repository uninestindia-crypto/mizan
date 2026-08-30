# Completed work: correct the overstated claims found by the Red Team pass

STATUS: COMPLETED
OWNER: Claude Code
TOOL: Claude Code
STARTED_UTC: 2026-08-30T00:00:00Z
STARTING_REVISION: bb62bc58
WORKTREE_OR_BRANCH: D:\quant_system on main

## Objective

Close the remaining findings from `.launch/reports/RED-TEAM-20260829-LIVE-PAPER-PATH.md` that are
about claims rather than behaviour: P2-1, P2-2, P2-5, P2-8, P3-1, P3-2. Several turned out to need
code as well as words.

## What changed, and what it cost me to write it accurately

| Finding | Repair |
|---|---|
| P3-1 | `apply_cross_sectional_ranks` takes the pre-quantisation floats, so the live path ranks on the same values `build_mizan_feature_store.py:174` ranked on |
| P2-2 | The false "verified bit-identical" claim is gone; `tests/test_mizan_store_fidelity.py` opens the committed store and bounds the claim |
| P2-5 | `CrossSectionCoverage.with_extreme_refusals` populates `skipped_extreme`; the coverage gate now runs **after** refusals |
| P3-2 | The `MAX_STANDARDIZED_DEVIATION` justification is rewritten: it is a percentile choice, both prior justifications were wrong, and both are recorded |
| P2-8 | All 264 CRLF-against-LF evidence files restored; a new test covers payloads, not just markers |
| P2-1 | Recorded, not repaired -- see below |

## A correction to my own repair, found by the test I wrote for it

I fixed the rank sort and wrote a test asserting the kernel would then reproduce the store's
published ranks. **The test failed.** Investigating showed the failure was mine, not the test's:

```
BAJAJHIND    return_5=-0.0365853659
NIFTYBEES    return_5=-0.0365853659
```

Both names carry byte-identical published text, so `float(text)` is the same number for each and no
ranking rule can recover the order the builder derived from raw floats that were never published.
The 244 rows are **permanently unreproducible from the store**.

So the repair is narrower than I first wrote: it makes the *live path* follow the builder's
procedure, and it does nothing for the published rows. Three docstrings that claimed otherwise --
including one I had written minutes earlier -- were corrected. The test now asserts the strongest
true thing: every divergence is a published-text tie, which is what shows the rule itself matches.

## P2-1 recorded rather than repaired

`preprocessing_input_hash` binds 51 bars while the values it certifies depend on the full prefix.
Repairing it means rehashing 1,015,831 published rows, which changes every
`preprocessing_input_hash` in the store and invalidates the evidence identity of published models.
That is a training-path change with campaign-wide consequences, not a docstring fix, and it should
not be done as a side effect of this work. It stays open.

## Commands and outcomes

```
git ls-files --eol data/evidence/ | ... -> 264 i/lf w/crlf  BEFORE
                                       -> 0                 AFTER (8933 i/lf w/lf)
git diff --numstat -- data/evidence    -> 0 lines (content matches blobs)
ruff check . / ruff format .           -> clean, 503 files
mypy src                               -> Success, 141 source files
pytest -q                              -> 1157 passed (was 1153)
```

The new evidence guard was verified able to fail: corrupting one file to CRLF made it fail, and
restoring the file made it pass.

## Still open

5.3 and 5.5 (loop idempotency, crash-mid-loop state advance), P2-1 above, P2-4, P2-7, P2-10, P2-11,
and 10.4. The scheduled task remains **disabled** pending an independent recheck.
