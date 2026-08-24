# Active work: close program Major #4 — capability claims exceed implemented behaviour

STATUS: COMPLETE — claims corrected; STATE.md closure is the coordinator's  
OWNER: Claude Code — capability claims  
TOOL: Claude Code  
STARTED_UTC: 2026-08-24T14:00:00Z  
STARTING_REVISION: `c804e74`  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main`

## Objective

`.launch/STATE.md` Major #4, open since 2026-08-20, owner Product: "Product capability claims exceed
implemented live-execution behavior." Close it by making the claims true, verified against code
rather than against intent.

## Audit, every claim checked against the tree at `c804e74`

| Claim (README.md) | Verified status |
|---|---|
| "Quantitative **Trading** & Backtesting System" | **Overstated.** Nothing has ever placed an order. `realtime_shadow.py:203` enforces `broker_orders_submitted == 0` as an invariant; `paper_broker.submit_order` is a simulator |
| "optimized for NSE India **and US Equities**" | **FALSE.** `market_data.py:28` is `NSE_EQ\|[A-Z0-9]{12}` and `:148` raises "instrument_key must identify one NSE cash equity". Zero US support anywhere in `src/` |
| "**Fundamental** Balance Sheet Factor Scoring" | **FALSE.** No balance sheet, book value, earnings or P/E anywhere in `src/`. A grep matched only `sharpe_ratio` |
| "AI/NLP Sentiment Feeds" | Partly real — `alpha/` and `advisory/` exist, and the advisory panel records but never decides |
| "Exact Decimal Accounting" | **TRUE**, and load-bearing throughout |
| "Strict Pre-Trade Risk" | **TRUE** — `PreTradeRiskGovernor` is on the shadow and paper paths |
| "No Lookahead Bias / next-bar fills" | **TRUE**, and strengthened: S9-B1 made same-quote fills structurally impossible |
| "Realistic Market Friction" — STT, GST, turnover, stamp duty | **TRUE** — `NSERuleEngine` with dated statutory rules; measured 0.224% round trip |
| Options / derivatives modules | **REAL** — `alpha/greeks.py`, `data/option_chain.py`, and a runnable example |

Two claims are flatly false and one framing claim is unsupported. Everything else holds, and several
of the true claims are stronger than the README suggests.

## What replaces them

Not a smaller product — a truthfully described one. What actually exists is unusual and worth
stating plainly: a governed quantitative **research** platform for NSE equities that enforces
point-in-time discipline, real statutory costs, multiplicity accounting and immutable evidence, and
that has repeatedly refused to promote models — including ones its own authors wanted to promote.

The gap between "trading platform" and "research platform that has never traded" is the honest
content of Major #4.

## Owned paths

- `README.md`
- `docs/ARCHITECTURE.md` (diagram only; unclaimed — checked against every active record)
- `agent_context/work/active/20260824-claude-capability-claims-audit.md` (this file)

`README.md` is a root guidance file, which PROTOCOL §4 flags as single-owner. Edited on explicit
founder instruction to "do what needs to be done" after Major #4 was named as the target. No other
record claims it.

## Non-goals

- Rewriting `.launch/PRD.md`, ADRs or slice contracts. Those record what was *intended and
  contracted*; the defect is in the outward-facing claim, not the design record.
- Removing working capability. Nothing is deleted; two false claims are corrected and one framing
  claim is made accurate.
- Marking Major #4 closed in `.launch/STATE.md`. That file is claimed by
  `20260821-0530Z-claude-slice4-certification.md` and the closure is the coordinator's to record.

## Plan

1. COMPLETE — audit every claim against code; this record.
2. Correct `README.md`.
3. COMPLETE — verified no claim in the corrected text is unsupported.

## What changed

**`README.md`**

- Headline: "Quantitative Trading & Backtesting System ... NSE India and US Equities" ->
  a governed research and backtesting platform for NSE India, with **"It has never placed an order"**
  stated in the opening, not buried.
- Removed the false "Fundamental Balance Sheet Factor Scoring" invariant. Replaced with two
  invariants that are true and were previously unstated: the governed model lifecycle, and
  multiplicity accounting.
- Added a "What this does and does not do" section, verified line by line, which states plainly that
  there is no live trading, no US equities, no fundamentals — and no profitable model, with the
  0.398-against-0.95 figure named.

**`docs/ARCHITECTURE.md`**

The alpha diagram presented "Value (P/E, EV/EBIT) / Quality (ROE, D/E) / Earnings Surprises" as
current architecture. Verified: the only `ebit` match in `src/` is `total_debits`, and ROE, FinBERT
and earnings-surprise have zero implementations. arXiv RAG is real and was kept. The box now reads
PLANNED, NOT BUILT. Replacement lines were length-matched so the ASCII alignment is unchanged.

## Verification

`grep -i "US Equit|Fundamental Balance"` over `README.md` returns only the corrected lines that
explicitly deny those capabilities. Every remaining claim was checked against the tree; the
`DATA_AND_ALPHA_ROADMAP.md` references were left alone because that document is explicitly a
roadmap and does not assert the capabilities exist.

## Not done

`.launch/STATE.md` Major #4 is **not** marked closed here. That file is claimed by
`20260821-0530Z-claude-slice4-certification.md`, and a coordinator should record the closure after
reading this audit rather than taking the word of the agent who performed it.
