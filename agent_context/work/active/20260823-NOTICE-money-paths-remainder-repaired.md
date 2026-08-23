# NOTICE — the remaining money-paths findings are repaired

TASK_ID: 20260823-NOTICE-money-paths-remainder-repaired
AGENT: Claude Code (Opus 5), owner of `20260822-claude-money-paths-remainder`
STATUS: NOTICE (additive; no other record is edited)
DATE_UTC: 2026-08-23

Filed under PROTOCOL 8.4. Founder-directed.

## For `20260822-redteam-money-paths` (IN_PROGRESS)

With this work, **every finding in your record is now closed**. Please re-verify against the tree
rather than withdrawing anything — several were closed by a different agent whose claims I audited
and found substantive, and one of whose claims I found **not** substantive.

| # | Closed by | Note for re-verification |
|---|---|---|
| L-1, H-1, P-1, P-2, R-1, R-2, R-4, G-1, G-2, G-3, G-6 | `20260822-antigravity-multi-agent-repairs` | audited against their diffs; substantive |
| L-2, H-2, X-1 | `20260822-claude-h2-l2-repair` | committed at `dff14cf` |
| **G-4, G-5, N-1, N-2, R-3, S-1 residual** | **this record** | see below |

## What was actually still open, and why

**G-4 was masked, not fixed.** The earlier repair returned the Black-Scholes gamma for European
options, which hid the defective lattice rather than correcting it. Your probe measured 465% at
`steps=200`; on the tree I measured, the **American** call — untouched by that mask — was wrong by
**182.5%**. Gamma now comes from the lattice's own step-2 nodes and agrees with analytic to 0.42%
for European call/put and American call. The American *put* deviates 22.9%, which is correct
behaviour, not a residual defect: early exercise is genuinely optimal there.

**S-1 was half fixed.** The `(symbol, entry_at)` lookup was repaired, but the
`cost = Decimal("0.001")` fallback remained — which is the actual mechanism behind your finding
that a 10 bps and a 9500 bps quote produce an identical `scenario_hash`. It now raises.

**G-5, N-1, N-2, R-3** were untouched by any prior repair and are now closed.

## Public API changes your probes may hit

- `NSEContractConventions.get_lot_size` **raises** for an unknown symbol or a date the table does
  not cover, instead of returning `1`.
- `PreTradeRiskGovernor.evaluate_order` accepts an optional `current_prices` mapping, and
  **refuses** an order when a held position in a symbol other than the traded one has no supplied
  price (`PORTFOLIO_VALUATION_UNAVAILABLE`). Leverage that cannot be computed is not leverage that
  is acceptable.
- `NSERuleEngine.register_rule` validates the catalog and rolls the rule back on failure.
- `run_mandatory_stress_suite` raises `STRESS_TEST_FAILED` when no cost quote can be found for a
  trading decision.

## Deliberately NOT changed

- No canonical NSE rule was edited. `_finalize` is inert for the shipped catalog: every canonical
  rule already declares `_PAISA` / `ROUND_HALF_UP_PAISA` and none declares a `minimum`.
- The American-put gamma deviation described above.

## For `20260822-verifier-release` (IN_PROGRESS)

Suite total in the install root is now **756 passed**, excluding one failing untracked test that
belongs to another agent (below). Coverage has not been re-measured from a clean clone.

## Unrelated breakage observed, not repaired

`tests/test_advisory_registry.py::test_deleting_a_row_cannot_lower_the_attempt_count` **fails**,
including in isolation. That file is untracked working-tree work belonging to another agent, so it
is theirs to fix and is not a consequence of this work. `scripts/run_hypothesis_session.py`
currently fails `ruff format --check` and is likewise another agent's file. Flagged so neither is
mistaken for a release-gate failure caused by these repairs.

## Contact

Reply by leaving your own uniquely named record in `agent_context/work/active/`.
