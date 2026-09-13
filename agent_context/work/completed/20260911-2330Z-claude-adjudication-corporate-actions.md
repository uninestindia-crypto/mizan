# Independent adjudication — the corporate-action correction

STATUS: COMPLETED
AGENT: Claude Opus 5 (third independent session, authored none of the code in scope)
STARTING_REVISION: `9aa3bd8e`
WORKTREE_OR_BRANCH: install root `D:\quant_system`, branch `main`, **read-only**
OWNED_PATHS: `.launch/reports/ADJUDICATION-CORPORATE-ACTIONS-20260911.md` and this record only

## Objective

Execute `.launch/ADJUDICATION-BRIEF-CORPORATE-ACTIONS.md`: adjudicate claims A1-I2 of the
2026-09-10/11 corporate-action correction, from source, tests, committed authorities and the market
cache — never from a work record, a `reports/` file, or `CURRENT.md`.

## Non-goals

Repairing anything found. Writing any evidence store. Spending any multiplicity ordinal. Touching
any file outside the two above.

## Outcome

**BLOCKED.** Full report and raw output: `.launch/reports/ADJUDICATION-CORPORATE-ACTIONS-20260911.md`.

PROVEN: A1, A2, A3, B1, B2, B3, B4 (corpus-scoped), C1, C2, C3, D1, D2, D3, D4, E1, E2, E3, E4
(feature values), F1, F2, F3, F4, G3, G4, H1, H2, H3, H4, I1.
DISPROVEN: C4, H5. PARTIALLY DISPROVEN: I2. NOT TESTED: G1, G2 (counterfactuals about code no
longer in the tree).

Three defects, each with a reproduction in the report:

- **DEFECT-1 (P1)** rights issues are never parsed, never gap-tested and never recorded unresolved,
  so `spans_unresolved` returns `False` and a fabricated return is published — reproduced on
  BHARTIARTL, HCC (-22.94% in one session), CCAVENUE and INTELLECT.
- **DEFECT-2 (P2)** `_DIVIDEND_RE` rejects the `/-` suffix the split regex accepts, so 493 of 5,083
  dividend records (9.7%) in the research universe are silently unpriced in the `TOTAL_RETURN` basis.
- **DEFECT-3 (P3)** `demerger-resulting-companies.json` names RAYMOND 2025-05-14 from the 2024
  Raymond Lifestyle filings; the 2025 action is the Raymond Realty demerger.

Mutation testing: 32 deliberate defects, 27 killed, **5 survive all 1,477 tests** (factor-set hash
ignoring unresolved actions; the per-bar execution instrument identity check; refused-quote
accounting; the adjustment-reference source binding; a dividend relabelled `PARSED_AND_GAP_CONFIRMED`).

## Commands and outcomes

All re-measurements, with raw output, are in the report. Mutation testing ran in an isolated copy of
`src/` and `tests/` in this session's scratchpad, never in the install root, because the automated
`sync: evidence checkpoint` committer does directory-wide `git add`.

## Verification of read-only compliance

`git diff --stat` over `src/quant_system/data/`, `src/quant_system/modeling/`, `tests/`,
`scripts/validate_demerger_factors.py`, `scripts/ingest_all_market_data.py`,
`scripts/screen_mizan_out_of_sample.py`, `scripts/fetch_demerger_announcements.py` and
`reports/mizan_ab_screen/` is **empty**. No evidence store written. No ordinal spent.
`scripts/validate_demerger_factors.py` was re-run with `--out`, `--discovery-out` and
`--index-cache` redirected to scratch so no committed authority was overwritten.

## Next safe action

Owner of the corporate-action code decides on DEFECT-1 and DEFECT-2. Nothing here is repaired, and
nothing in this record or the report may be cited as a passing gate.
