# Halal transparency: what the engine and the Shariah screens agree on

DATE: 2026-10-07
GOAL_LINE: G2 (the Shariah mode works from the same install), G5/tripwire 4 (never present an unproven result as an edge)
OWNER_RECORD: `agent_context/work/active/20261007-claude-halal-transparency-and-model-picks.md`
SOURCE: `reports/halal_docs_review/REVIEW.md` sections 2, 3 and 4 (Stage 0: honesty)

The deterministic screener decides; everything else explains. Nothing an AI says may change a verdict. These changes
are **additive** to the existing responses, so older screens and the Flutter client keep working. Where a number was an
assumed constant, it becomes `null` and the response says why in words.

## Screening (`GET /api/v2/shariah/stocks/{ticker}/screen` and the audit response)

New fields on `ScreeningResponse` and `ShariahAuditResponse`:

| Field | Value |
|---|---|
| `data_status` | `"UNVERIFIED_SAMPLE"` today (also `"VERIFIED_FILING"`, `"STALE"` when real filings arrive). Never anything stronger than what a check backs. |
| `data_notice` | the existing sample-data notice, in plain words |
| `methodology_version` | `"shariah-screen-v1"` (one constant, changed only with the rules) |
| `screened_at` | ISO-8601 UTC time of this evaluation |
| `sector_rule` | `{"compliant": bool, "rule": str or null, "matched_keyword": str or null, "reason": str or null}`: which rule fired and the word it matched on |
| `not_covered` | list of plain sentences about what this result does not cover: no scholar has reviewed it, the figures are a hand-entered sample, not every income line is reviewed, it is a screening aid and not a fatwa |

## Baskets (`BasketSummary`, `BasketDetail`, `TearSheetMetrics`)

- `expected_cagr`, `expected_sharpe`, `cagr`, `sharpe_ratio`, `annualized_volatility`, `max_drawdown`, `beta` become
  `null` (typed `float | None`). They were typed constants, not results of any test, and are removed until computed from
  real data. `dividend_yield` and `weighted_purification_ratio` stay only if they are computed from the screening rows;
  otherwise `null`.
- New `performance: {"status": "NOT_COMPUTED", "message": "QuantOS has not back-tested this basket, so no return or risk figure is shown."}`.
- The invented rebalance history is removed: `rebalance_history` is `[]` and a new `history_status` is `"NONE_RECORDED"`
  with `history_message: "No rebalances have been recorded yet."`.
- Constituent `current_price` and `market_cap` keep their values only where they come from a real source; where they are
  typed samples they are `null` and the constituent carries `price_status: "SAMPLE"` or `"NOT_AVAILABLE"` (plain words on
  the screen: "Sample price" / "No price"). Order-sheet export stays disabled while prices are samples, as today.

## Purification ledger

Each receipt gains `hash_version` (integer). Version 1 (existing rows) hashes `previous hash | id | amount`, as today.
Version 2 (new rows) hashes `previous hash | id | ticker | gross dividend | purification ratio | payable | timestamp`, so
none of the figures the methodology lists can be changed without breaking the chain. Verification reads each row's own
version, so a ledger that already exists still verifies. No existing row is rewritten.

## Words on screens

- "Order-sheet export" replaces "1-Click Execution". It must say "QuantOS does not place orders."
- "Pre-audited" and "Shipped & Live" do not appear anywhere a person reads. The honest label is "Working prototype on a
  39-company illustrative sample. Not live, not audited."
- Every verdict shows its `data_status` next to the verdict, not only in a banner.
