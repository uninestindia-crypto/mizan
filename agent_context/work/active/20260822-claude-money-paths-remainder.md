# Repair the remaining money-paths findings

TASK_ID: 20260822-claude-money-paths-remainder
AGENT: Claude Code (Opus 5)
STATUS: IN_PROGRESS
STARTED_UTC: 2026-08-22
STARTING_REVISION: dff14cf (main, install root)
WORKTREE_OR_BRANCH: D:\quant_system on main (shared checkout)

## Objective

Founder-directed: repair what remains open in
`agent_context/work/active/20260822-redteam-money-paths.md`.

## What actually remains

Most of that record was already addressed by `20260822-antigravity-multi-agent-repairs`, whose
diffs I audited earlier this session and found substantive for nine of ten files. Verified
individually at `dff14cf` before starting — the six below still reproduce:

| # | Sev | Finding | Status at dff14cf |
|---|---|---|---|
| G-4 | Blocker | Binomial gamma wrong by 465% at the shipped default `steps=200` | **masked, not fixed** — `greeks.py:449-454` returns Black-Scholes gamma for European options instead of correcting the lattice |
| S-1 | Blocker (residual) | `TWICE_TRANSACTION_COSTS` silently applies a hardcoded 10 bps when no cost quote is found | lookup repaired; the fail-open default remains |
| R-3 | Major | Portfolio leverage valued at average COST, and hashed into `decision_hash` | open — `governor.py:335-338` uses `p.average_price` for every position except the traded symbol |
| G-5 | Major | `get_lot_size` fails OPEN, returning 1 for unknown symbols and pre-table dates | open — `greeks.py:92` |
| N-1 | Major | `rounding_unit`, `rounding_method`, `minimum` are hashed into `rule_hash` but never applied | open — declared at `nse_rules.py:85`, appear only in the canonical dict |
| N-2 | Major | `register_rule` bypasses `validate_catalog`; the engine stays live in a state its own validator rejects | open — `nse_rules.py:729-733` type-checks only |

Already closed and NOT re-touched: L-1, L-2, H-1, H-2, P-1, P-2, R-1, R-2, R-4, G-1, G-2, G-3,
G-6, X-1.

## Non-goals

- Not re-opening or re-verifying findings the antigravity round closed.
- Not touching the API/shadow/paper Red Team's scope (slices 6, 8, 10).

## Owned paths

All four source files were checked against every active record and are **unclaimed**:

- `src/quant_system/analytics/greeks.py` (G-4, G-5)
- `src/quant_system/analytics/nse_rules.py` (N-1, N-2)
- `src/quant_system/risk/governor.py` (R-3)
- `src/quant_system/modeling/stress.py` (S-1 residual — already adopted by
  `20260822-claude-h2-l2-repair`, adoption carries here)
- corresponding `tests/` files

## Design notes

**G-4 is the interesting one.** The existing "repair" makes `BinomialOptionModel.calculate_greeks`
return `BlackScholes.calculate_greeks(...).gamma` for European options. That is not a fix: it hides
a defective lattice behind a different model, so the binomial gamma is never actually correct, and
an American option — the case a lattice exists for — still gets the broken value. The lattice
itself must produce a correct gamma.

**R-3 follows the L-2 precedent.** A leverage number that cannot be computed must not be
fabricated from cost. The governor is given prices only for the order's own symbol, so it needs a
price map; when a held position cannot be valued, the order is refused rather than approved
against an unknown exposure.

## Plan

Per finding: verify it reproduces, write the failing regression, repair, re-run.
Then full suite, ruff, mypy, both audits, and a notice for the in-flight adjudications.

## Outcome — all six repaired, each failing-first

### G-4 — binomial gamma (Blocker)

The prior "repair" returned `BlackScholes.calculate_greeks(...).gamma` for European options. That
hid the defect instead of fixing it, and left the American case — the reason a lattice exists —
**wrong by 182.5%** (0.05300048 against an analytic 0.01876202).

Root cause: gamma was a second difference of three separately re-priced trees. A bump smaller than
the lattice node spacing lands inside one cell, so the difference measures grid noise, not
curvature.

Repair: `_induct()` now performs the backward induction once and can stop at any step, shared by
both `price()` and gamma, so the lattice is defined exactly once. `_lattice_gamma()` reads the
standard CRR estimate off the step-2 nodes. It returns `None` where the lattice genuinely cannot
supply gamma (steps < 2, zero vol, degenerate `u == d`, risk-neutral `p` out of range) and the
existing fallback handles those.

Measured after repair, against analytic: European call 0.42%, European put 0.42%, American call
0.42%. The American **put** deviates 22.9% and that is correct, not a defect — early exercise is
genuinely optimal there, which is why the regression pins the American *call*.

### G-5 — `get_lot_size` failed open (Major)

Returned `1` for any unknown symbol or pre-table date, so `validate_quantity` approved 7 shares of
a 75-lot contract. Now raises. `validate_quantity` catches and returns `False`, because an unknown
lot cannot validate a quantity.

### N-1 — declared rule fields were hashed but never applied (Major)

`cap`, `minimum`, `rounding_unit` and `rounding_method` are hashed into `rule_hash`, so a rule is
*identified* by them, yet every component hardcoded `quantize(_PAISA, ROUND_HALF_UP)` and only
brokerage honoured a cap. A rule declaring `ROUND_HALF_UP_RUPEE` with `minimum=1000.00` priced at
0.33.

New `_finalize(raw, rule)` applies cap, then minimum, then the declared rounding, and all eight
component computations route through it.

Blast radius checked before applying: every canonical rule already declares `_PAISA` /
`ROUND_HALF_UP_PAISA`, and **no** canonical rule declares a `minimum`. The change is therefore
inert for the shipped catalog and only affects custom rules.

### N-2 — `register_rule` bypassed its own validator (Major)

Appended unconditionally, so the engine could be driven into a state `validate_catalog()` rejects
and then keep pricing from it. Registration now validates and rolls the rule back on failure.

### R-3 — leverage marked to cost (Major)

`governor.py` valued every position except the traded symbol at `average_price`. Cost-based
leverage understates real exposure, and the understated number was hashed into `decision_hash` as
evidence.

`evaluate_order` gained an optional `current_prices` map. The traded symbol is still valued from
its own quote; other symbols need a supplied price; a position that cannot be valued means leverage
is **unknown**, which is not the same as acceptable, so the order is refused with
`PORTFOLIO_VALUATION_UNAVAILABLE`.

Verified: with TCS held at cost 100 but marked at 1200, leverage moves from an approved 0.11 to a
refused 1.21. No existing caller broke — single-symbol and empty portfolios are unaffected.

### S-1 residual — silent 10 bps (Blocker)

The antigravity round repaired the `(symbol, entry_at)` lookup but left
`cost = Decimal("0.001")` as the fallback. That is what made a 10 bps and a 9500 bps quote produce
an identical `scenario_hash`: the stressed cost never depended on the quote. It now raises
`STRESS_TEST_FAILED` naming the symbol and decision time. A cost that cannot be established makes
the scenario unevaluable, and reporting unevaluable as survived is a false pass.

## Gate

| Gate | Result |
|---|---|
| `pytest tests/ --ignore=tests/test_advisory_registry.py` | **756 passed**, 1 warning |
| `ruff check .` | All checks passed! |
| `ruff format --check` (my 8 files) | 8 files already formatted |
| `mypy src launcher.py scripts` | Success, 128 source files |

## Not mine, found while verifying

`tests/test_advisory_registry.py::test_deleting_a_row_cannot_lower_the_attempt_count` **fails**.
The file is untracked working-tree work belonging to another agent, and it fails **in isolation**,
so it is not a consequence of this work. Not touched. `scripts/run_hypothesis_session.py` also
needs reformatting and is likewise another agent's file. Both are reported, not repaired.

## Not claimed

None of these repairs is certified. No Red Team recheck and no clean-clone Verifier has adjudicated
them. Measured in a shared checkout with several agents committing concurrently, so the suite total
is a working signal, not a baseline.

## Next safe action

Await adjudication. Do not treat any figure here as a gate.
