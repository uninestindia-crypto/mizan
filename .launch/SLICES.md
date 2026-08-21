# SLICES — QuantOS Risk-Ordered Build Plan

STATUS: G3 accepted 2026-08-20  
RULE: Each slice is independently demoable and scoped to one focused engineering session. Every slice ends with red-team and clean-state verification appropriate to T2.

## Progress

| Slice | Status | Evidence |
|---:|---|---|
| 1 | PASS | Red Team PASS; Verifier PASS from clean clone `37ccf12`; `.launch/SLICE-01-EVIDENCE.md` |
| 2 | PASS | Red Team PASS; Verifier PASS from clean revision `9c2e7fe` |
| 3 | PASS | Red Team PASS at `be9da7f`; Verifier PASS from exact clean revision `0acbca2` |
| 4 | PASS | Red Team PASS; Verifier PASS; all 4 Blockers and 7 Majors closed; `.launch/SLICE-04-EVIDENCE.md` |
| 5 | PASS | 15/15 Tests PASS, Single-use Holdout vault, Stress testing, Deterministic Promotion; `.launch/SLICE-05-EVIDENCE.md` |
| 6 | PASS | 56/56 Tests PASS, Local loopback API trust boundary, Supervised worker lifecycle; `.launch/SLICE-06-EVIDENCE.md` |
| 7 | PASS | 30/30 Tests PASS, Effective NSE rules, Decimal ledger, Black-Scholes/Binomial Greeks, Risk Governor; `.launch/SLICE-07-EVIDENCE.md` |
| 8 | PASS | 25/25 Tests PASS, Recorded quote shadow replay, Zero broker writes; `.launch/SLICE-08-EVIDENCE.md` |
| 9 | PASS | 12/12 Tests PASS, Read-only Real-Time shadow stream, Freshness budget enforcement; `.launch/SLICE-09-EVIDENCE.md` |
| 10 | PASS | 17/17 Tests PASS, Top-of-book depth simulation, Adverse slippage, Paper ledger; `.launch/SLICE-10-EVIDENCE.md` |
| 11 | PASS | 23/23 Tests PASS, 7 Core operator journeys, Accessible semantic UI, REST APIs; `.launch/SLICE-11-EVIDENCE.md` |
| 12 | PASS | 16/16 Tests PASS, Standalone x64 bundle, SBOM bound to uv.lock, Clean Release Verifier; `.launch/SLICE-12-EVIDENCE.md` |


## Risk order

| # | Vertical slice and largest question answered | Demo boundary | Required test rings | Primary ACs |
|---:|---|---|---|---|
| 1 | **Real point-in-time acquisition.** Can Upstox V3 return one five-year NSE-equity history with complete timestamp/provenance/quality evidence—or an exact typed reason it cannot—without hidden fallback or any broker write capability? | One accepted manifest from real read-only data when credentials/provider permit, plus recorded success and timeout/429/5xx/HTML/auth/schema/empty/partial fixtures; traffic asserts GET-only and zero order endpoints. | R0 static/secret; R1 strict parser/manifest; R2 adapter→quality→manifest; R3 recorded provider contract; R4 acquisition journey; R5 schema drift/staleness/failure injection; R6 clean suite | AC-2–3, 9–22, 74–75 |
| 2 | **Immutable evidence and recovery.** Can content-addressed publication survive duplicate requests, cancellation, crash staging, disk failure, corruption, and concurrent processes without exposing partial state? | Commit/reload a near-limit fixture; kill after every commit phase; reject corruption; rebuild index; demonstrate A→B→A atomic rollback and replay. | R0; R1 canonical/atomic units; R2 store/application; R4 rollback journey; R5 concurrency/failure/path attacks; R6 | AC-21, 35–37, 40, 48, 72–76 |
| 3 | **Executable labels.** Can a close-time decision produce point-in-time features and the first-later-open to following-open label after effective costs, with overlap purge/embargo and deterministic hashes? | Synthetic and recorded-data fixtures produce identical rows twice; deliberate post-cutoff, missing-open, authority, and overlap violations fail closed. | R0; R1 label/time/hash/property tests; R2 data→feature→label; R4 deterministic row journey; R5 leakage/boundary/adverse gaps; R6 | AC-14, 23–34, 37–38, 52–53 |
| 4 | **One governed ridge fold.** Can the existing six-feature ridge family fit with train-side preprocessing, record every attempt, compare the four baselines, and reproduce prediction/metric hashes? | A persisted trial and one expanding walk-forward fold emit candidate, baseline, cost, fill, metric, and multiplicity evidence; a failed/cancelled trial still counts. | R0; R1 model/preprocessing/metric; R2 label→fit→finance; R4 fold journey; R5 non-finite/constant-target/seed/multiplicity attacks; R6 | AC-31, 35–45 |
| 5 | **Final holdout and promotion.** Can a frozen candidate unlock its final holdout exactly once, run all mandatory stresses/gates, and receive a deterministic evidence-only verdict? | Known pass/fail fixtures yield exact gate tables, model card monitoring limits, refused second holdout use, and refused illegal lifecycle transitions. | R0; R1 gates/state; R2 fold→holdout→promotion; R4 candidate journey; R5 tamper/manual-override/stress; R6 | AC-32–51 |
| 6 | **Versioned operation API and local trust boundary.** Can the bundled UI safely create, poll, cancel, and deduplicate a supervised governed worker with one error contract? | Real loopback server runs one training/backtest operation with heartbeats, cancellation, request ID, exact CORS/Host checks, hostile-origin rejection, idempotent retry, and worker-loss recovery. | R0 OpenAPI/security; R1 DTO/error; R2 API/store/worker; R3 legacy adapter; R4 browser/server; R5 hostile inputs/origins/races/worker kill; R6 | AC-1, 5–8, 59–60, 74–76 |
| 7 | **Governed financial research.** Can equity and NIFTY-option calculations select correct dated NSE rules, enforce immutable risk versions, fill after the decision, and reconcile every component to the paise through desktop/API/export? | Before/at/after rule fixture, equity next-open fill, independent option/Greeks fixture, risk rejection, shared evidence bundle, exact desktop/API hashes. | R0; R1 rounding/invariant/property; R2 finance→ledger→evidence; R4 two journeys; R5 mutation/boundary/gap/duplicate; R6 | AC-23–28, 44, 49, 53–58 |
| 8 | **Recorded shadow replay.** Can a SHADOW fixture generate attributable decisions from recorded later quotes while stale, duplicate, out-of-order, offline, and invalid events halt safely? | Recorded shadow session, matured outcome attribution, reconnect/offline halt, end audit, deterministic replay, zero broker writes. | R0; R1 session/idempotency; R2 model→risk→audit; R3 quote contract; R4 session journey; R5 event-order/duplicate/stale/kill attacks; R6 | AC-50–51, 61, 64–70, 72 |
| 9 | **Read-only real-time shadow.** Can current Upstox quotes drive the same SHADOW contract and halt within the freshness/offline budget? | Bounded live read-only session when credentials/market permit or exact typed unavailability; monitoring and captured replay agree; order endpoint traffic remains zero. | R0; R1 quote freshness; R2 adapter→session; R3 live/recorded contract; R4 bounded journey; R5 disconnect/auth/clock attacks; R6 | AC-20, 50, 61, 66–70 |
| 10 | **Quote-driven paper pilot.** Can a PAPER_PILOT use first later quotes, bid/ask, adverse slippage, displayed quantity, partial fills, effective costs, and idempotent ledger mutation? | Bounded campaign fixture produces reconciled partial fills, pending/session-end cancellation states, monitoring halt, rollback exercise, and deterministic replay. | R0; R1 state/cost/idempotency; R2 quote→risk→ledger; R4 pilot journey; R5 zero-liquidity/wide/crossed/duplicate/gap; R6 | AC-62–72 |
| 11 | **Professional desktop and capability journey.** Can a first-time user distinguish source/mode, inspect evidence/gates, understand every required failure state, and avoid duplicate work? | Real browser over real server completes all seven release journeys with safe DOM rendering, accessible progress/cancel/error/recovery UI, and truthful first-view/export notices. | R0 frontend/CSP; R2 browser/API; R4 E2E + accessibility; R5 wrong-click/double-submit/hostile text/human behavior; R6; R7 customer-zero | AC-1–8, 56–60, 72, 77–78 |
| 12 | **Reproducible Windows x64 release.** Can a clean checkout install from lock, make static/tests/audits/build green, and install/restart/rollback/uninstall without evidence loss? | CI-built wheel and PyInstaller x64 artifact, SBOM and build manifest tied to revision/lock, native clean-install seven-journey capture. ARM64 remains unadvertised until separately proven. | R0 all static/audits; R1–R4 automated; R5 operational; R6 verifier; R7 customer-zero; launch readiness | AC-7, 37, 69–78 |

## Slice rules

1. Slice 1 is first because provider history, timestamp availability, completeness, and typed failure semantics can invalidate every governed result built above it.
2. A slice changes all layers necessary for its one demo but may not introduce placeholder success, untyped fallback, or a second calculation path.
3. Every new contract is written before its implementation. Every production defect begins with a failing regression test.
4. Financial, point-in-time, promotion, idempotency, and evidence-publication code requires at least R1, R2, R4, R5, and R6 evidence; documentation-only and styling-only edits do not waive the final critical-journey rings.
5. Red Team attacks each completed slice before the next begins. A Blocker or unresolved Major keeps that slice open.
6. Verifier runs from a clean state and adjudicates claimed commands as `PROVEN`, `DISPROVEN`, or `NOT TESTED`.
7. The active slice must leave the pre-existing synthetic backtest usable or clearly migrate it in the same slice.
8. Live broker order routing, additional model families, remote access, and unsupported markets are rejected as scope changes, not accepted as “small additions.”

## G3 entry and exit

G3 passes when this order, ownership, demo boundary, and test-ring requirement are accepted. P4 begins with Slice 1 only. No parallel slice may edit the same domain contracts or evidence schemas.
