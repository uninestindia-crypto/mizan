# CHARTER — QuantOS Professionalization

TIER: T2  
DATE: 2026-08-20  
FOUNDER: Repository owner

## The one sentence

Turn the existing QuantOS research and paper-trading application into a trustworthy, maintainable, professionally engineered desktop quantitative-analysis product, with financial correctness, explicit failure behavior, reproducible builds, and evidence-backed release readiness.

Status: confirmed by the founder on 2026-08-20.

## The user

Primary: an individual quantitative researcher or systematic trader on Windows who needs to test equity and NSE-options ideas without risking live capital.

Secondary: an engineer extending strategies, data connectors, analytics, or the API and needing stable contracts and a reliable development workflow.

## The job to be done

“I need to load or generate market data, run a strategy through realistic risk and cost controls, and understand the result well enough to decide whether the idea deserves further research.”

## “No problems for users” means

MUST NEVER HAPPEN: silently wrong cash/P&L/tax calculations; lookahead-biased fills presented as valid; secrets exposed; live orders placed; corrupt or partial results presented as successful.

MUST ALWAYS WORK: install/start diagnostics; a deterministic synthetic-data backtest; risk rejection; Decimal ledger reconciliation; result/tearsheet generation; an actionable error when an optional external service is unavailable.

MAY BE IMPERFECT: live market-data availability; advanced AI-advisor quality; breadth of strategies; visual richness beyond the primary research journeys.

## The first ten minutes

A new Windows user installs or starts QuantOS and sees a local-only application. The application explains that it is a research and paper-trading tool, not a live broker. Startup diagnostics make missing or optional capabilities visible. The user runs a deterministic example backtest without credentials, sees the selected strategy and risk assumptions, receives a performance summary and trade ledger, and can distinguish simulated data from broker data. If they try Upstox without credentials or lose connectivity, the application explains the limitation and offers an explicit simulated-data path without pretending that live data was used.

## Kill criteria

- Stop release work if any reproducible financial-accounting, lookahead, or risk-gate defect remains open.
- Cut a feature from the release if it cannot expose whether its data is synthetic, cached, or broker-sourced.
- Do not add live order routing until it is separately chartered as T4 money-movement work.
- Do not certify a release without version control, CI, a clean build, a clean static-analysis baseline, and independent red-team and verification evidence.

## Success metric

From a clean checkout on supported Windows, 100% of the five critical journeys complete with zero unhandled exceptions, zero reconciliation failures, and no undocumented external prerequisite.

## Non-goals for this effort

- Real-money broker order submission or autonomous trading.
- Cloud deployment, multi-user accounts, or tenancy.
- A database or migration subsystem unless an accepted slice proves persistence is required.
- Claims of guaranteed returns, investment advice, or regulatory approval.
