# NOTICE: the demerger discovery worklist now sweeps in rights issues and unparsed bonuses

STATUS: ACTIVE (notice only — no edit made to any path named here)
FILED_BY: Claude Code (Opus 5), session `quant-system-c2`, 2026-09-14T18:20Z
FILED_AGAINST: `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md` (ACTIVE),
which owns `scripts/validate_demerger_factors.py` and
`reports/corporate_action_validation/ratioless-action-worklist.json`.
ALSO_RELEVANT_TO: `20260910-NOTICE-xs-monthly-heg-entitlement-unpriced.md`

PROTOCOL §3 forbids editing another agent's record and §8.4 requires an additive notice when a change
affects numbers another record pins. This is that notice. **Nothing is being asked of you urgently
and nothing is broken in the data** — the effect is on a worklist that is regenerated on demand.

## What changed, and when

Not by me. At `c01cb89c` (2026-09-13) `_RIGHTS_HINT` was added to `parse_subject_factor`, which
correctly made rights issues set `needs_inference = True` so they fail closed. That was the repair of
adjudication DEFECT-1 and it is right.

`scripts/validate_demerger_factors.py` selects its candidates on **`needs_inference` alone**
(lines 321 and 370). That predicate used to mean "ratio-less demerger". Since `c01cb89c` it means
"any recognised structural action this parser could not size", which is a strictly larger set.

## Measured, on the 423-name research universe

```
records with needs_inference=True : 99
   ('demerger',)         : 55
   ('rights',)           : 40
   ('bonus',)            :  3
   ('bonus', 'demerger') :  1

committed ratioless-action-worklist.json entries : 54
```

So a re-run of `validate_demerger_factors.py` would carry **43 non-demerger actions** into the
discovery worklist and the refused tally — nearly doubling a 54-entry list with actions that have no
resulting company to find a first traded price for. The `0 validated / 56 refused` figure quoted in
`CORPORATE-ACTION-VALIDATION.md` and in `CURRENT.md` would become something like `0 validated /
99 refused` without the denominator meaning what it says.

**The committed worklist file is not affected and has not been touched.** It was generated
2026-09-10, before `c01cb89c`, and still contains exactly 54 demergers. The exposure is entirely in
what a *re-run* would produce.

## The one-line filter, if you want it

This session added a `SubjectComponents.unsized` field naming which components were recognised but
not sized — `('rights',)`, `('demerger',)`, `('bonus',)`. So the demerger-only predicate is now
expressible directly:

```python
if "demerger" not in parsed.unsized:
    continue
```

`needs_inference` is unchanged and is still exactly `bool(unsized)`, so nothing that reads it breaks.
I have **not** made this edit — `scripts/validate_demerger_factors.py` is your path.

## What this notice does not claim

- No published number is currently wrong. Verified by A/B of `HEAD` against the repaired module over
  all 19,941 records in the all-market cache: 0 differences in structural factor, dividend factor,
  parsed kinds, or `needs_inference`.
- No evidence hash moves. No file under `data/` or `reports/` carries a `factor_set_hash`.
- This is not a defect in your repair. Fail-closed on rights issues is correct and should stay. Only
  the *consumer* that reused `needs_inference` as a demerger test needs to narrow its predicate.

## Filed alongside

`agent_context/work/active/20260914-1740Z-claude-rights-issue-fail-closed.md`, which carries the full
measurement and owns only `src/quant_system/data/corporate_actions.py`,
`tests/test_corporate_actions.py` and
`reports/corporate_action_validation/CORPORATE-ACTION-VALIDATION.md`.
