# XS Portfolio Alpha: Pre-Declared Trial Ledger

**Frozen 2026-09-25, before production validation runs.** Every model, horizon, and parameter trial is
counted here whether or not it is published, because an unrecorded search is invisible multiplicity
to whoever screens this family next.

The rule that makes this binding: **a trial not listed here cannot be added after a result is seen.**
Adding one is a new declaration, dated, with the reason stated, and it deflates everything that follows.

## Budget Summary

| Parameter | Value | Notes |
|---|---:|---|
| **Declared trial budget** | **5** | Hard cap on candidate parameter & formulation variations |
| Consumed SPENT trials | 1 | Baseline XS Monthly Multi-Factor Composite Strategy |
| Remaining budget | 4 | Reserved for pre-declared variations only |
| Multiplicity accounting | DSR | Bailey & Lopez de Prado (2014) Deflated Sharpe Ratio |

## Controls & Baselines (Excluded from Trial Multiplicity)

Controls and baselines do not consume trial budget ordinals. A control cannot be promoted under any outcome;
counting it would penalize the real candidate for being measured carefully.

| Baseline / Control | Type | Purpose | Multiplicity Ordinal |
|---|---|---|---:|
| `CASH` | Baseline | Risk-free / zero-return baseline (Sharpe = 0.0) | Excluded (0) |
| `ALWAYS_TRADE` | Baseline | Broad market equal-weight paying 0.224% statutory friction | Excluded (0) |
| `NOISE_30_SEED` | Control | 30-seed Gaussian pseudo-random rankings through identical ledger | Excluded (0) |

## Pre-Declared Strategy Design

Declared in full before evaluation, ensuring no parameter was chosen after seeing an outcome.

| Element | Specification |
|---|---|
| Universe | `data/authorities/nse-research-universe-liquid-10y.csv` (423 liquid names, >=9.5y history, >=5cr turnover) |
| Factors | Intermediate Momentum (21–63d), Reversion Dampening (3–5d, lambda=0.5), Idiosyncratic Volatility Scaling (63d) |
| Portfolio | 4 autonomous weekly tranches, 25% max capital per tranche, total leverage <= 100% |
| Holding period | 21 trading sessions per tranche (approx 1 calendar month), rebalanced every 5 sessions |
| Execution | Next-open (T+1) execution with circuit-lock guards (volume > 0, high != low) |
| Friction | Exact 0.224% round-trip statutory fee model (0.00112 entry + 0.00112 exit) in Decimal math |
| Final holdout | Chronological holdout (2025-08-14 to 2026-08-21, 252 sessions) strictly quarantined |

## Declared Candidate Trials

| # | Family | Parameters | Status | Description | Recorded |
|---|---|---|---|---|---|
| 1 | `xs_multi_factor_v1` | mom=63, rev=5, vol=63, hold=21, lambda=0.5 | **SPENT** | Baseline composite ranking with 4-tranche weekly ledger | 2026-09-25 |
| 2 | `xs_multi_factor_v2` | mom=42, rev=5, vol=63, hold=21, lambda=0.5 | PLANNED | Intermediate momentum window variation (2 months) | 2026-09-25 |
| 3 | `xs_multi_factor_v3` | mom=63, rev=3, vol=63, hold=21, lambda=0.7 | PLANNED | Aggressive short-term reversion dampening | 2026-09-25 |
| 4 | `xs_multi_factor_v4` | mom=63, rev=5, vol=42, hold=21, lambda=0.5 | PLANNED | Shorter idiosyncratic volatility estimation window | 2026-09-25 |
| 5 | `xs_multi_factor_v5` | mom=63, rev=5, vol=63, hold=21, lambda=0.3 | PLANNED | Lower reversion penalty dampening | 2026-09-25 |

## Verification Criteria
1. Net annualized Sharpe > 0.0 strictly after deducting 0.224% round-trip statutory fees.
2. Spearman rank IC > 0.0 with Student's t-statistic `t > 2.0`.
3. Decile monotonicity: Q1 annualized return exceeds Q10 annualized return (`Q1 > Q10`).
4. Strategy DSR strictly exceeds the median DSR of the 30-seed NOISE control.
5. Capital preservation invariant: total exposure strictly `<= 1.0000` at all times.
