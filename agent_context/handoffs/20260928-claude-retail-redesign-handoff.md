# Handoff: QuantOS 2.0 retail redesign (stopped at usage limit, 2026-09-28)

RECORD: `agent_context/work/active/20260928-claude-retail-redesign-build.md` (ACTIVE, HANDOFF_REQUIRED)  
WORKSPACE: `D:\quant_system_workspaces\worktrees\feature-retail-redesign-e787ac4-20260928-000443`  
BRANCH: `claude/retail-redesign` from `main` at e787ac462. Nothing committed yet.

## Done

- Current app tested in a browser (findings in `work/completed/20260928-claude-redesign-discovery.md`).
- Build contract: `docs/product/PRD-quantos-2.md` (screens, acceptance criteria, honesty rules).
- Architecture: `docs/product/ADR-0001-retail-frontend-and-market-index.md`.
- Both files exist only in the worktree, uncommitted.

## Facts established (verified 2026-09-28)

- Data: `data/evidence/market-cache/all-market-20160822-20260821/store` has 3,322 datasets (3,267
  symbols, ETFs included; NIFTYBEES `NSE_EQ|INF204KB14I2`, 2,476 rows) ending 2026-08-21.
  `nifty500-refresh-20230828-20260827/store` has rolling 3-year vintages re-acquired daily for 499
  symbols; the newest (acquired 2026-09-24) covers 2023-09-25..2026-09-23. Manifest
  `metadata` holds `symbol`, `received_range`, `row_count`, `provider_instrument_id`,
  `acquired_at`. Reader: `quant_system/research_xs_monthly/bars.py::load_cache_bars`.
- Costs: `analytics/nse_rules.py::NSERuleEngine().calculate_costs(segment, side, quantity, price,
  trade_date, custom_brokerage_rule, slippage_bps)`, effective-dated, with rule IDs.
- `backtest/engine.py`: signals at close, fills at next open, slippage in fill price, fixed-rate
  `IndianMarketCostModel`. `/api/v1/backtest/run` uses `SyntheticDataGenerator` (app.py:993).
- Verdict math: `analytics/multiplicity.py::OverfittingDiagnostics.deflated_sharpe_ratio`; gate 0.95
  (`modeling/promotion.py::GatePolicyV1`).
- Paper books (read-only, notice `20260924-NOTICE-paper-books-system-test-running.md`):
  XS state `logs/xs_monthly_new/paper_watch/state.json` (99 open, cash 94,409.99 on 2026-09-25);
  flagship status `logs/paper_runs/live_paper_status.json` (absent until its first session).
- Server: CSRF header `X-CSRF-Token` from `/api/v1/csrf-token`; CSP `script-src 'self'`,
  `img-src 'self' data:`. pytest `pythonpath = ["src", "."]`; mypy strict on `src`.
- Tooling: npm works (vite 8.3.1, tailwindcss 4.3.3, lightweight-charts 5.2.1). Codex image
  generation works: `codex exec --skip-git-repo-check -s workspace-write -C <dir> "<prompt>"`.
  The PNG lands in `%USERPROFILE%\.codex\generated_images\<session>\`; Codex's own shell helper
  fails on Windows, so copy the file yourself. The tool reports no model name.

## Do not touch

`backtest/engine.py`, `backtest/costs.py`, `risk/governor.py`, `analytics/multiplicity.py`,
`analytics/nse_rules.py` (money-path claims); `/live`, `live_dashboard.py`, `security.py`
(task_c889215d is fixing the CSP bug); paper-book code and state; `main`.

## Next safe action, in order

1. `src/quant_system/market/` index builder (SQLite, stitching rule from ADR decision 4) + tests.
2. `app.sqlite` state, `/api/v2` router, SPA serving at `/`, old console at `/classic`.
3. `src/quant_system/lab/` simulator + parity test against `BacktestEngine` + verdict.
4. `frontend/` scaffold, design system, screens per PRD section 4.
5. Codex illustrations (onboarding, empty states), resized and logged.
6. Tests: pytest, vitest, Playwright on the installed Edge (`channel: 'msedge'`).
7. Installer: npm build before PyInstaller in `build-windows-release.ps1`, version 2.0.0,
   silent install + launch test.
