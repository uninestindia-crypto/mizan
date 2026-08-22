# Red Team adjudication — money and model-governance paths

TASK_ID: 20260822-redteam-money-paths
AGENT: Claude Code (Opus 5) — INDEPENDENT Red Team adjudicator
ROLE: Adjudicator. Did not author any code under test.
STATUS: IN_PROGRESS
STARTED_UTC: 2026-08-21T20:43Z
STARTING_REVISION: 5067fa9e61d569bf31c5e37d83d4a8b318c7d808 (main)

## Objective

Break the money paths and model-governance paths. Adjudicate:
- Slice 4 repair revision (re-attack repairs listed in
  `agent_context/work/active/20260821-1048Z-claude-slice4-redteam-repair.md`)
- Slice 5: `src/quant_system/modeling/{holdout,promotion,stress,lifecycle}.py`
- Slice 7: `src/quant_system/analytics/{greeks,nse_rules}.py`,
  `src/quant_system/portfolio/**`, `risk/**`, `core/{domain,ledger}.py`

## Non-goals

- Slices 6, 8, 9, 10 — a concurrent Red Team agent owns those. Stay out.
- No fixes. No source modification anywhere.

## Owned paths (install root)

- `agent_context/work/active/20260822-redteam-money-paths.md` (this file)
- `.launch/reports/RED-TEAM-MONEY-PATHS.md` (final report, single write at end)

Nothing else in the install root will be written.

## Workspace

WORKTREE_OR_BRANCH: clone via `scripts/new-workspace-clone.ps1 -Purpose redteam -Label moneypaths`
CLONE_PATH: `D:\quant_system_workspaceserification_clones
edteam-moneypaths-5067fa9-20260821-204318` (detached at 5067fa9)

## Plan

1. Create this record (done).
2. Read protocol/state/slices/evidence docs.
3. Create clone, `uv sync --frozen --extra dev --link-mode copy`.
4. Confirm the gate is genuinely green BEFORE attacking; record exact figures.
5. Attack families in order:
   A. Embargo lower bound (Slice 4 + does Slice 5 holdout inherit the hole?)
   B. Holdout single-use defeat
   C. Promotion verdict integrity / forgeable ModelCardV1 fields / string-vs-tuple siblings
   D. LIVE prohibition bypass
   E. Money correctness: Decimal discipline, dated NSE rules boundary, cost paise sum,
      Greeks vs independently derived numbers, floats touching money
   F. Slice 4 repair variants (evidence tamper, purge derivability, atomic publish)
6. Write report in clone, copy to install root.

## Current step

Step 5 — baseline gate CONFIRMED GREEN in the clone at 5067fa9. Now attacking.

## Baseline gate (measured in the clone, BEFORE any attack)

| Gate | Command | Result |
|---|---|---|
| Repository tests | `.venv/Scripts/python.exe -m pytest tests/ -q --no-header` | `483 passed, 1 warning in 55.93s` exit 0 |
| Ruff lint | `python -m ruff check .` | `All checks passed!` |
| Ruff format | `python -m ruff format --check .` | `273 files already formatted` |
| Strict Mypy | `python -m mypy src` | `Success: no issues found in 109 source files` |

Scope files are byte-identical between install root and HEAD (`git diff --stat HEAD -- src/quant_system/{analytics,portfolio,risk,core,modeling}` is empty), so reading in the install root is safe; all probes run in the clone.

## SCOPE DISCREPANCY (recorded immediately)

The task named `src/quant_system/modeling/lifecycle.py` as a Slice 5 file. **It does not exist.**
`find src tests -iname "*lifecycle*"` returns nothing at 5067fa9. There is no model-lifecycle state
machine in the modeling package; promotion state is a pure function argument.

## Findings so far

None recorded yet.

## Commands and outcomes

- `git rev-parse HEAD` -> `5067fa9e61d569bf31c5e37d83d4a8b318c7d808`

## Blockers and conflicts

None yet.

## Next safe action

Read AGENTS.md/PROTOCOL/DISK-LAYOUT/LAUNCH-PROGRESS/.launch STATE+SLICES, then create the clone.

---

## ANSWER TO THE THREE-TIMES-RAISED EMBARGO QUESTION (definitive, 2026-08-21T21:1xZ)

**Question:** `evaluate_governed_ridge_fold` never receives the session calendar, so a fold can
declare `embargo_sessions=5` and remove nothing. Does Slice 5's holdout inherit this hole?

**Answer: YES, and in a strictly worse form. The holdout evaluator re-derives NOTHING.**

Two halves, separated:

1. `create_holdout_partition` (`src/quant_system/modeling/holdout.py:317-421`) **does** receive
   `calendar: SessionCalendarV1` and derives `embargo_closes` from
   `calendar.sessions[max(0, holdout_ordinal - embargo_sessions):holdout_ordinal]` (line 364-369).
   So the *constructor* is sound: a declared `embargo_sessions` there genuinely removes sessions.
   That half does NOT inherit the Slice 4 hole.

2. `evaluate_governed_holdout` (`holdout.py:424-530`) accepts an arbitrary `HoldoutPartitionV1`.
   `HoldoutPartitionV1` (`holdout.py:107-114`) is a bare frozen dataclass with **no `__post_init__`
   at all**. `_validate_holdout_spec` (`holdout.py:612-648`) checks only id/hash *format*,
   timezone-awareness, `row_count >= 1`, and `embargo_sessions >= label_horizon_sessions`. It never
   checks that `discovery_hash`/`holdout_hash` match the rows, that `*_row_count` matches
   `len(rows)`, that the purge/embargo key tuples correspond to anything, or that discovery rows
   precede `holdout_start`. `evaluate_governed_holdout` re-checks none of it either — it only
   verifies the unlock token, single-use, and `candidate_id`.

   Slice 4's `evaluate_governed_ridge_fold` at least re-derives the purge from the label rows
   (`_validate_removed_rows`, the Blocker 1 repair). The Slice 5 holdout evaluator has no
   equivalent. It is therefore worse than Slice 4, not equal to it.

**Reproduced** (probe `p04_holdout.py`, run in the clone at 5067fa9). Same fixture, same trained
model, same byte-identical `HoldoutSpecV1` object (so identical `spec_hash`), only the
`holdout_rows` tuple swapped for the model's own training rows:

```text
HONEST report spec_hash    : 3dcd25598696e25960d078ed5b274fd441da1a4a467e548226a95c8fbeedc25f
HONEST sharpe              : -0.734271536171
HONEST holdout total_return: -0.009857258981

forged.spec.holdout_row_count     : 5 but len(forged.holdout_rows) = 18
forged.spec.holdout_hash          : e6af730e940157ed2ae8e0bfa2a20230c7d626eb9badbdb05615c94a4fa4f29b
actual hash of evaluated rows     : ebe0bb28e7e3192d2b6b50e04e40450012451c16c73120afcd52a67639060c62
HASHES MATCH?                     : False
FORGED report ACCEPTED. total_return: 0.317716506416
FORGED report sharpe               : 11.417608587498
FORGED report deflated sharpe      : 0.999999947792
FORGED report spec_hash            : 3dcd25598696e25960d078ed5b274fd441da1a4a467e548226a95c8fbeedc25f
```

Deflated Sharpe 0.999999947792 clears the default `GatePolicyV1.min_deflated_sharpe = "0.95"`.
The two reports are indistinguishable by `spec_hash`. This is Blocker H-1 below.

## Findings so far (running list, updated after every attack family)

Probe scripts live in
`C:\Users\teenl\AppData\Local\Temp\claude\D--quant-system\e42ad1da-db2f-437f-aaa6-c222c398fa8d\scratchpad\probes\`.
All run as:
`cd <clone>; PYTHONPATH=<clone> ./.venv/Scripts/python.exe <probe>`

| # | Severity | Finding | Probe |
|---|---|---|---|
| L-1 | Blocker | `DecimalLedger` realized P&L omits the entry-side fee; `reconcile()` returns True | p01 |
| L-2 | Blocker | `get_portfolio_snapshot` silently marks a position to its own average price when the price is missing from the map | p02 |
| H-1 | Blocker | `evaluate_governed_holdout` re-derives nothing; swapping `holdout_rows` for the model's training rows yields sharpe 11.42 under an identical `spec_hash` | p04 |
| H-2 | Blocker | Holdout single-use is defeated by constructing a second `HoldoutVaultTracker()`; state is in-memory only, never persisted, never read back | p05 |
| P-1 | Blocker | Demotion of a model that failed EVERY gate returns `verdict=PAPER` and issues a fresh PAPER model card | p03 |
| P-2 | Blocker | Promotion gates accept fold/holdout/stress evidence belonging to a different candidate and model; no binding check | p03 |
| S-1 | Blocker | `TWICE_TRANSACTION_COSTS` never finds a cost quote (key `(symbol, entry_at)` vs lookup `(symbol, decision_at)`), so it always applies a hardcoded 10 bps. 10 bps and 9500 bps quotes give an identical `scenario_hash` | p06 |
| X-1 | Major | Slice 5 has ZERO callers in `src/`. `grep -rn "evaluate_promotion\|evaluate_governed_holdout\|run_mandatory_stress_suite\|draft_from_holdout_*" src/` outside the defining modules returns nothing. No holdout/stress/promotion evidence is ever published | grep |

Negative results (tried, could NOT break):
- Holdout token reuse under a renamed `holdout_id` on the SAME tracker: correctly refused
  (`HOLDOUT_ALREADY_CONSUMED`) because `token_hash` is tracked separately (probe p05 5C).
- Second unlock on the SAME tracker: correctly refused (p05 5A).
- Sub-paisa symmetric round trip: no leak observed (p02 2B).

## Next probe (exact)

1. Gate 7 `list(score_kinds)[0]` nondeterminism -> `record_hash` instability across `PYTHONHASHSEED`.
2. LIVE prohibition: the guard is `to_state == "LIVE"` string compare against a `StrEnum` with no
   LIVE member -> dead code. Probe reachability of a live-equivalent verdict.
3. Slice 7: `analytics/greeks.py` (`calculate_time_to_expiry_years` uses `current_time.tzinfo`
   not IST; `get_lot_size` fail-open default 1; `validate_strike` accepts negative/zero;
   Binomial zero-vol undiscounted intrinsic; CRR `p>1` with small vol).
4. Slice 7: `analytics/nse_rules.py` dated boundary, cost components summing to the paise.
5. Slice 7: `risk/governor.py`, `risk/checks.py`, `portfolio/**`.

## Checkpoint 2 — Slice 7 families run (greeks, nse_rules, risk, ledger, domain)

Added to the findings table:

| # | Severity | Finding | Probe |
|---|---|---|---|
| R-1 | Blocker | `PreTradeRiskGovernor.evaluate_fill` is a no-op: `governor.py:324-327` is an `if` whose body is `pass`. A Rs 50,000,000,000 fill against Rs 1,000 equity returns `approved=True, reason="FILL_VERIFIED"` | p08 |
| R-2 | Major | `restore_state` silently drops `limits` and the kill-event trail; a restarted governor runs DEFAULT limits (`max_position_weight` 0.25) after being configured 0.01 | p08 |
| R-3 | Major | Portfolio leverage is valued at average COST, not market. Approved decision reports `resulting_leverage=0.1` when the true value is 1.0, and that number is hashed into `decision_hash` | p09 |
| R-4 | Minor | `KillSwitchEvent.timestamp` is `datetime.now(UTC)`, not the decision clock: a 2019 backtest decision produced a 2026 audit timestamp | p08 |
| G-1 | Blocker | `calculate_time_to_expiry_years` builds expiry at 15:30 in the CALLER's tzinfo, not IST. Same instant IST vs UTC -> 6.25 h vs 11.75 h to expiry; ATM 0DTE NIFTY price 38.96 vs 53.73 (Rs 1,107.59 per 75 lot) | p10 |
| G-2 | Blocker | `BinomialOptionModel.price` returns undiscounted intrinsic at zero vol: 0.000000 vs the correct 6.760618 that `BlackScholes` in the same module returns | p10 |
| G-3 | Blocker | No CRR stability guard. vol=0.001, T=1, steps=200 -> risk-neutral p = 2.975289 and the price collapses to 0.000000 vs Black-Scholes 6.760618 | p10 |
| G-4 | Blocker | `BinomialOptionModel.calculate_greeks` gamma is wrong by 465% (0.10184324 vs analytic 0.01802635) at the shipped default `steps=200`; every other Greek agrees to ~0.1% | p10 |
| G-5 | Major | `get_lot_size` fails OPEN: returns 1 for every non-index symbol and for dates before the table. `validate_quantity('RELIANCE', 7, ...)` -> True | p10 |
| G-6 | Major | `validate_strike('NIFTY', Decimal('0'))` and `Decimal('-50')` both return True | p10 |
| N-1 | Major | `DatedExchangeRule.rounding_unit`, `.rounding_method`, `.minimum` are hashed into `rule_hash` but never read by `calculate_costs`. A rule declaring `ROUND_HALF_UP_RUPEE` + `minimum=1000.00` computes 0.33 | p11 |
| N-2 | Major | `NSERuleEngine.register_rule` bypasses `validate_catalog`; the engine stays live in a state its own validator rejects | p11 |

Negative results this round (tried hard, could NOT break):
- NSE dated STT boundary selection is EXACT at 2024-09-30/2024-10-01 (futures) and
  2023-03-31/2023-04-01, 2024-09-30/2024-10-01 (options). Verified rule-by-rule (p11 11A).
- NSE cost components sum to `total_statutory_charges`, `total_fee`, `total_friction` exactly to
  the paise across delivery/intraday/options/futures, both sides, prices 0.01 to 24345.75 (p11 11B).
- Black-Scholes analytic price/delta/theta/vega/rho agree with the binomial lattice to <=1.1% (p10 10G).
- `Fill`, `PriceBar`, `Quote`, `Position`, `PortfolioSnapshot` all reject binary floats (`_assert_no_float`).
- LIVE prohibition: `PromotionState` has no LIVE member; no reachable path to a LIVE verdict (p07).

## Next probe (exact)

6. `portfolio/allocation.py`, `portfolio/optimization.py`, `portfolio/sizing.py`.
7. Slice 4 repair re-attack: `validation.py` Blocker 1 embargo lower bound directly,
   `persisted_trials.py` Blocker 2 re-derivation, `evidence/store.py` Blocker 3 publish-then-verify,
   Blocker 4 `_outcome` suffix.
8. Write `.launch/reports/RED-TEAM-MONEY-PATHS.md` in the clone, copy to the install root.
