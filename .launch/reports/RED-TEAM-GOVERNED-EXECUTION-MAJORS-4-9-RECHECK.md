# Governed execution Majors 4-9 independent recheck

## 1. Release verdict

**NOT READY.** At exact repair revision `deccec176c3791c010238f54452dacd00e212b14`,
the audit is 100.00% complete but verified coverage is 70.83%, leaving 29.16% of weighted item
coverage unresolved. The run has 17 passed, 5 failed, and 1 blocked item; the five failed items
collapse into **2 P1 Critical defects and 1 P2 Major defect**. There are no P0, P3, or P4 findings.

After this report is registered, run milestones are 4/7 complete (57.14%) with 3/7 remaining
(42.85%). The blocked feature-window item carries weight 8. The largest risk is that a provider can
serve another instrument's bars under the expected map key and the governed session will approve a
proposal as though those bars belonged to the bound model symbol.

Tested target: detached local Windows clone at `deccec1`, frozen dependencies, no broker writes,
no promotion override, and no live session.

## 2. Progress dashboard

See [coverage-dashboard.md](coverage-dashboard.md).

- Total weighted scope: 144.
- Passed weight: 102.
- Failed weight: 34.
- Blocked weight: 8.
- Python execution scope: 65.00% verified.
- Build, installation, and static baselines: 100.00% verified.
- Clean-clone full suite: 845 passed.
- Repair-author suites: 68 passed.
- Independent matrix: 16 passed, 5 failed.
- Original probes: 6 passed against their original inputs.

No denominator items were removed. Three adjacent cases were added during structural review:
inner-bar instrument identity, public-session error containment, and multi-entry maturity atomicity.

## 3. Product topology and scope

| Surface | Entry point | Status | Evidence |
|---|---|---|---|
| Governed strategy | `GovernedModelStrategy.generate_signals()` | Failed on inner-bar instrument identity; original unexpected-key repair passes | `wrong-instrument-defect.json`, `adversarial-matrix.json` |
| Shadow session | `RealtimeShadowRunner.run_session()` | Failed on wrong-instrument provider and provider-error audit recovery | `wrong-instrument-defect.json`, `runner-audit-escape-defect.json` |
| Maturity policy | `SessionHorizonMaturity.matures_at()` | Boundary cases pass; multi-entry settlement is non-atomic | `adversarial-matrix.json`, `maturity-atomicity-defect.json` |
| Audit report | `ShadowAuditReport` | Open-exposure fields/hash pass; mixed maturity failure produces contradictory state | same evidence |
| Real evidence CLI | `run_governed_shadow_session.py` | Passed: bound GRASIM then refused `RESEARCH_ONLY` with exit 3 | `real-evidence-runner.json` |
| Feature-window policy | execution feature computation | Blocked by missing founder decision | handoff Blocker 2 |

The target has no user-facing web/mobile/desktop surface in this narrow handoff. Visual and
accessibility testing are therefore not applicable. The operator-facing surfaces are Python APIs,
a session audit object, and one CLI.

## 4. Critical journey results

| Journey | Role/platform | Happy path | Failure/recovery | Persistence/downstream | Experience | Evidence |
|---|---|---|---|---|---|---|
| Bind model to one instrument and score | Execution adapter / Python | Unexpected map keys are refused | **Failed:** internally RELIANCE bars under key INFY are accepted | One approved INFY shadow proposal; audit says COMPLETED | Trust-breaking silent misattribution | `wrong-instrument-defect.json` |
| Consume governed history in public session | Operator / Python | Valid and empty history paths pass | **Failed:** malformed and duplicate provider output escape `run_session()` | No terminal audit is returned | No recovery or durable failure record | `runner-audit-escape-defect.json` |
| Hold and mature across sessions | Operator / Python | Pre-open, post-close, coverage floor, and single error pass | **Failed:** mixed maturity batch partially settles before halt | Proposal `old` is both matured and still open | Contradictory money/audit state | `maturity-atomicity-defect.json` |
| Inspect open exposure | Operator / Python | Passed | Empty/open cases pass | Count and symbols alter audit hash | Clear and attributable | `adversarial-matrix.json` |
| Attempt real-evidence shadow start | Operator / CLI | Evidence binds one model/symbol/threshold | Passed refusal for non-executable verdict | Exit 3, no session and no order | Clear gate feedback | `real-evidence-runner.json` |

## 5. Defects by severity

### RT-GE-01 — Another instrument can be scored under the bound symbol

| Field | Detail |
|---|---|
| Severity | **P1 Critical** — the core governed-execution identity promise fails with no warning |
| Ledger items | `m4.inner-symbol.reject`, `m4.public-session.reject` |
| Build/environment | `deccec1`, detached Windows clone, frozen environment |
| Platform/role/state | Python governed strategy and public shadow session; 55 available daily bars |
| Preconditions | SHADOW-verdict INFY bundle; provider returns bars whose `PointInTimeBar.symbol` is RELIANCE while the map key is INFY |
| Steps | Build the public strategy, serve relabeled bars under the expected key, then call direct scoring and `run_session(max_quotes=1)` |
| Expected | Reject before feature computation; public session halts with zero proposals and an audit |
| Actual | Direct call raises nothing. Public session completes, generates one INFY proposal, approves it, and reports no halt |
| Customer impact | Shadow/paper evidence can attribute another instrument's price history to the promoted model, invalidating decisions, monitoring, and post-training evidence |
| Evidence | [wrong-instrument-defect.json](evidence/records/wrong-instrument-defect.json); [confirmed JUnit](evidence/logs/redteam-confirmed-defects-v2.xml) |
| Recurrence | Reproduced in both the installed environment and the clean clone; direct and public paths both fail |
| Scope | Any injected/custom `BarHistoryProvider`; provider-instrument ID binding may also need review |
| Likely source | **Hypothesis:** `_require_bar_sequence` validates types and duplicate dates but never checks every `bar.symbol == map_key`; the runner keys provider output by quote symbol without validating returned records |
| Fix direction | Validate the internal symbol for every bar at the adapter boundary and exercise the same invariant through `run_session()`; consider binding provider instrument identity where evidence supports it |

### RT-GE-02 — Maturity halt can publish a partially settled, contradictory audit

| Field | Detail |
|---|---|
| Severity | **P1 Critical** — Decimal financial state and immutable audit identity disagree |
| Ledger items | `m6.multi-entry.atomic` |
| Build/environment | `deccec1`, detached Windows clone |
| Platform/role/state | Public shadow session with two same-symbol open entries; older entry resolvable, newer entry beyond calendar horizon |
| Preconditions | Both proposals are approved/open before one quote triggers maturity evaluation |
| Steps | Run one quote after the old horizon while the new entry cannot resolve against the calendar |
| Expected | Preflight all maturities; if any is unresolvable, halt with zero settlement mutation |
| Actual | The old entry is settled at net PnL `-3.23`; the new entry then halts the session. The audit lists `old` as matured while `open_entries=2`, and the internal open map still contains `old` |
| Customer impact | Reconciliation and model-learning evidence can double-count or contradict exposure and realized outcome state |
| Evidence | [maturity-atomicity-defect.json](evidence/records/maturity-atomicity-defect.json); [confirmed JUnit](evidence/logs/redteam-confirmed-defects-v2.xml) |
| Recurrence | Reproduced on both independent matrix runs |
| Scope | Any session with multiple same-symbol open entries spanning resolvable and uncovered horizons |
| Likely source | **Hypothesis:** `_check_matured_outcomes` mutates cash, positions, and outcomes inside the loop, then returns on a later policy error before applying `to_remove` |
| Fix direction | Use a two-phase operation: resolve/preflight every applicable maturity first, then perform all Decimal settlements and removals only after preflight succeeds |

### RT-GE-03 — Governed provider errors escape the public session without an audit

| Field | Detail |
|---|---|
| Severity | **P2 Major** — an important failure/recovery path loses the operator's terminal evidence |
| Ledger items | `m5.public-session.audit`, `m8.public-session.audit` |
| Build/environment | `deccec1`, detached Windows clone |
| Platform/role/state | Public `run_session()`; provider returns `None` or duplicate exchange dates |
| Preconditions | Governed strategy and bar-history provider configured; one valid live quote |
| Steps | Return malformed or duplicate history from the provider, then run one quote |
| Expected | Fail closed with a typed halt reason and return a terminal audit with zero proposals |
| Actual | `GovernedExecutionError` escapes through `process_live_quote`; `run_session()` returns no audit |
| Customer impact | The operator receives a crash instead of durable reason/evidence; already-observed session state may be lost |
| Evidence | [runner-audit-escape-defect.json](evidence/records/runner-audit-escape-defect.json); [confirmed JUnit](evidence/logs/redteam-confirmed-defects-v2.xml) |
| Recurrence | Both malformed and duplicate cases reproduced in both matrix runs |
| Scope | Other provider and strategy integrity exceptions may escape through the same uncaught boundary |
| Likely source | **Hypothesis:** the streaming loop catches feed-read errors but not exceptions raised by `process_live_quote()`, provider invocation, or strategy generation |
| Fix direction | Introduce a stable model/input-integrity halt reason, catch the narrow governed exception at the session boundary, preserve the audit, and prove no financial/proposal mutation precedes the halt |

## 6. Consumer experience scorecard

The relevant consumer is a QuantOS operator reviewing a read-only shadow session. Visual,
findability, accessibility, fit-and-finish, and delight are **N/T** because no rendered UI is in this
handoff.

| Journey | Comprehension | Feedback | Error prevention | Recovery | Consistency | Trust |
|---|---:|---:|---:|---:|---:|---:|
| Wrong-instrument history | N/T | 1/5 | 1/5 | 1/5 | 1/5 | 1/5 |
| Provider integrity failure | N/T | 1/5 | 3/5 | 1/5 | 2/5 | 2/5 |
| Mixed maturity failure | N/T | 2/5 | 1/5 | 1/5 | 1/5 | 1/5 |
| Real-evidence gate refusal | 4/5 | 4/5 | 5/5 | 3/5 | 4/5 | 4/5 |

Why not one point higher: wrong-instrument execution provides no feedback; provider failures expose
a technical exception and no durable next action; maturity reports a halt but contradicts its own
state; the real runner is clear and safe but stops at refusal and does not provide an operator
workflow for resolving promotion readiness.

Observed trust trigger: an audit labeled `COMPLETED` contains an approved INFY proposal produced
from RELIANCE bars. Likely perception: an operator cannot trust model attribution or downstream
evidence. Confidence is high because the mismatch and approved proposal were observed together.

## 7. Compatibility, accessibility, performance, and resilience

- Windows ARM64 / CPython 3.13.15: executed.
- Frozen install: passed.
- Full repository suite: 845/845 passed in 59.338 seconds.
- Ruff lint/format: passed; 341 files already formatted.
- Strict Mypy: passed over 120 source files.
- Focused author suites: 68/68 passed.
- Original probes: 6/6 passed on their original inputs.
- Independent matrix: 16/21 passed.
- Real evidence CLI: passed its safe refusal contract.
- Browser, desktop rendering, keyboard, screen reader, mobile, and visual compatibility: not
  applicable to this narrow Python/CLI execution handoff.
- No broker writes occurred. Every observed audit retained `broker_orders_submitted=0`.

The green full suite does not cover the three failed adjacent cases.

## 8. Blockers, assumptions, and blind spots

- **Blocked item:** `blocker2.feature-window-policy`, weight 8. The founder has not selected a
  canonical execution history-window policy. Minimum unblock: document the intended window and
  bind provider/strategy behavior to it, then independently test invariance and replay.
- Assumption: a provider returning bars whose internal symbol differs from the requested symbol is
  malformed and must be refused. This follows the single-instrument model contract and the repair's
  own claim that the model cannot score another instrument.
- Assumption: a maturity failure is transaction-like and must not partially mutate Decimal
  accounting before returning a terminal audit.
- Blind spot: all real models remain `RESEARCH_ONLY`, so a real promoted live-feed session could
  not be exercised without violating the handoff. The real gate path was tested and correctly
  refused; synthetic fixtures were used only for controlled public-session attacks.
- Testing cannot prove there are no unknown defects. The 70.83% figure describes this explicit
  inventory only.

## 9. Prioritized repair plan

1. **Instrument identity containment (RT-GE-01):** update the governed strategy boundary and its
   public-session tests. Retest wrong map key, wrong internal symbol, mixed symbols, valid symbol,
   real evidence symbol derivation, and all five existing repair suites.
2. **Atomic maturity settlement (RT-GE-02):** separate maturity preflight from financial mutation.
   Retest one/many entries, mixed symbols, calendar exhaustion at every ordering, Decimal cash and
   positions, audit hash, and idempotent rerun behavior.
3. **Terminal audit for governed input failures (RT-GE-03):** catch only the stable governed
   integrity error at the public session boundary, map it to a durable halt code, and prove malformed,
   duplicate, wrong-symbol, and provider failures preserve zero-mutation audit state.
4. **Founder decision for Blocker 2:** choose the canonical feature-window policy before claiming
   governed execution parity.
5. After the final repair, rerun the 21-case independent matrix, 68 repair tests, original probes,
   real-evidence refusal, repository static checks, both repository audits, and the 845-test full
   suite (with any newly added regressions).

No product repair was made during this audit.

## 10. Approval request

Phase 1 is complete. No product repairs were made.
Approve Phase 2 to repair the confirmed defects, retest them through the real interfaces, and run the full regression.
