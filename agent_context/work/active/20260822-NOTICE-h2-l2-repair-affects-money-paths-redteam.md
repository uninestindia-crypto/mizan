# NOTICE — H-2 and L-2 repaired; affects the money-paths Red Team and the Slice 4 handoff

TASK_ID: 20260822-NOTICE-h2-l2-repair-affects-money-paths-redteam
AGENT: Claude Code (Opus 5), owner of `20260822-claude-h2-l2-repair`
STATUS: NOTICE (additive; no other record is edited)
DATE_UTC: 2026-08-22

Filed under PROTOCOL 8.4. Founder-directed repair.

## What changed

- `src/quant_system/core/ledger.py` — L-2
- `src/quant_system/modeling/holdout.py` — H-2, plus `get_evaluation_start` for X-1
- `src/quant_system/modeling/stress.py` — new `draft_from_stress_report` (X-1)
- `src/quant_system/modeling/promotion_pipeline.py` — new module (X-1)
- `scripts/run_governed_promotion.py` — new operator surface for promotion (X-1 follow-on)
- `tests/test_ledger_accounting.py`, `tests/test_modeling_holdout.py`,
  `tests/test_modeling_promotion.py`, `tests/test_modeling_promotion_pipeline.py`,
  `tests/test_governed_promotion_runner.py` — regressions and call-site updates

## For `20260822-redteam-money-paths` (IN_PROGRESS)

- **H-2 and L-2 are repaired.** Please re-verify against the repaired tree rather than withdrawing
  the findings.
  - H-2: `HoldoutVaultTracker` now **requires** an `EvidenceStore` and rebuilds consumed state from
    it on construction, so a second tracker over the same store sees prior use. Probe p05's defeat
    (construct a fresh tracker) is closed. Consumption is committed durably *before* it is trusted
    in memory.
  - L-2: `get_portfolio_snapshot` raises `LedgerInvariantViolation` when a held position has no
    price, instead of marking it to its own average price.
- **SUPERSEDED 2026-08-23.** This line previously said everything else in your record was
  untouched. That is no longer true: G-4, G-5, N-1, N-2, R-3 and the S-1 residual were repaired
  afterwards under `20260822-claude-money-paths-remainder`. See
  `agent_context/work/active/20260823-NOTICE-money-paths-remainder-repaired.md`, which is
  authoritative for the current state of your record. The remaining findings — L-1, H-1, P-1, P-2,
  R-1, R-2, R-4, G-1, G-2, G-3, G-6 — were addressed by
  `20260822-antigravity-multi-agent-repairs`, a different agent's work, not mine.
- **Public API change**: `HoldoutVaultTracker()` no longer constructs. Any probe of yours that
  builds one needs a store. This is deliberate — an optional store would have left the default
  construction exactly as unsafe as the finding describes.
- **X-1 is also now repaired.** `src/quant_system/modeling/promotion_pipeline.py` is new and calls
  `evaluate_governed_holdout`, `run_mandatory_stress_suite` and `evaluate_promotion`, publishing all
  five Slice 5 evidence kinds. Your grep will now return real call sites. Caveat worth your scrutiny:
  the pipeline is now also driven by `scripts/run_governed_promotion.py`, an operator surface. That
  script's configuration guards are tested; its acquisition stages have **not** been run against the
  real provider, so "runs end to end on real data" is not claimed. No API endpoint or UI calls it.
- Two dead things found while closing X-1, neither repaired: `_HOLDOUT_REPORT_SCHEMA` in
  `holdout.py` names a schema that is never published, and `draft_from_stress_report` did not exist
  at all before this change.

## For `20260821-1048Z-claude-slice4-redteam-repair` (HANDOFF_REQUIRED)

Its claim covers `src/quant_system/modeling/*.py` and `tests/test_modeling_*.py`. Under PROTOCOL
section 5, this session has **explicitly adopted only**:

- `src/quant_system/modeling/holdout.py`
- `tests/test_modeling_holdout.py`
- `tests/test_modeling_promotion.py`

The rest of that claim — every other `modeling/*.py`, all of `evidence/*.py`, and the other test
files — is **not** adopted and remains its own. That record has not been edited.

## For `20260820-codex-slice4-ridge-training` (ACTIVE)

No conflict. That record names its files explicitly and `holdout.py` is not among them. None of its
files was modified. `evidence/store.py`, which it does claim, is **used but not modified** — the
holdout consumption record reuses the existing `BUNDLE` resource type with its own `schema_id`
(`quantos.holdout_consumption`), so no new `EvidenceResourceType` was added and
`evidence/models.py` was not touched.

## For `20260822-verifier-release` (IN_PROGRESS)

Test counts have moved again. Measured in the install root at this session's end:
**735 passed** for the full suite, measured before this commit. Coverage has not been re-measured from a clean clone here.
Note the suite has also grown from other agents' concurrent work, not only from this repair.

## Contact

Reply by leaving your own uniquely named record in `agent_context/work/active/`.
