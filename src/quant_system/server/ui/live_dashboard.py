"""The live paper-trading dashboard page.

This markup lived in ``scripts/serve_live_dashboard.py`` and was imported *back* into the library by
``server/app.py``, which pointed the dependency the wrong way: `quant_system` is installed, `scripts`
is not a package, and mypy resolved the same file under two module names
(``serve_live_dashboard`` and ``scripts.serve_live_dashboard``), failing the repository gate. It only
worked at runtime because the install root happens to sit on ``sys.path`` and implicit namespace
packages allow it; a packaged build would have raised ``ModuleNotFoundError`` on
``/ui/trading-live``.

The page is a server-rendered asset, so it belongs beside the other templates in this package. The
standalone dashboard script now imports it from here rather than the other way round.
"""

from __future__ import annotations

HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>QuantOS Live Trading & Market Automation Dashboard</title>
  <link rel="icon" href="data:,">
  <style>
    :root {
      --bg-dark: #000000;
      --card-bg: #1c1c1e;
      --card-border: rgba(255, 255, 255, 0.08);
      --card-border-subtle: rgba(255, 255, 255, 0.04);
      --surface-secondary: #2c2c2e;
      --surface-tertiary: #3a3a3c;
      --text-main: #f5f5f7;
      --text-muted: rgba(235, 235, 245, 0.60);
      --text-subtle: rgba(235, 235, 245, 0.35);
      --accent-blue: #0a84ff;
      --accent-blue-hover: #0071e3;
      --accent-cyan: #64d2ff;
      --profit-green: #30d158;
      --profit-bg: rgba(48, 209, 88, 0.14);
      --profit-border: rgba(48, 209, 88, 0.30);
      --loss-red: #ff453a;
      --loss-bg: rgba(255, 69, 58, 0.14);
      --loss-border: rgba(255, 69, 58, 0.30);
      --badge-bg: rgba(255, 255, 255, 0.08);
      --highlight: #5e5ce6;
      --input-bg: rgba(255, 255, 255, 0.05);
      --radius-outer: 16px;
      --radius-inner: 10px;
      --radius-pill: 9999px;
      --shadow-card: 0 4px 20px rgba(0, 0, 0, 0.35);
      --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.2);
      --font-display: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Segoe UI Variable Display", "Segoe UI", system-ui, sans-serif;
      --font-mono: "SF Mono", "Cascadia Code", "JetBrains Mono", Menlo, Consolas, monospace;
      --transition-apple: 0.18s cubic-bezier(0.16, 1, 0.3, 1);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg-dark);
      color: var(--text-main);
      font-family: var(--font-display);
      padding: 24px 32px;
      line-height: 1.47;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }
    .container { max-width: 1400px; margin: 0 auto; }

    /* Header */
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding-bottom: 18px;
      border-bottom: 1px solid var(--card-border);
    }
    .header-left h1 {
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -0.02em;
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .badge-live {
      background-color: var(--profit-bg);
      color: #86efac;
      border: 1px solid var(--profit-border);
      padding: 3px 10px;
      font-size: 11px;
      font-weight: 600;
      border-radius: var(--radius-pill);
      letter-spacing: 0.04em;
      animation: pulse 2.5s infinite;
    }
    .badge-stopped {
      background-color: var(--loss-bg);
      color: var(--loss-red);
      border: 1px solid var(--loss-border);
      padding: 3px 10px;
      font-size: 11px;
      font-weight: 600;
      border-radius: var(--radius-pill);
      letter-spacing: 0.04em;
    }
    @media (prefers-reduced-motion: reduce) {
      .badge-live { animation: none; }
    }
    @keyframes pulse {
      0% { opacity: 1; }
      50% { opacity: 0.55; }
      100% { opacity: 1; }
    }
    .header-sub {
      font-size: 13px;
      color: var(--text-muted);
      margin-top: 6px;
      font-family: var(--font-mono);
      font-variant-numeric: tabular-nums;
    }
    .header-right {
      text-align: right;
    }
    .clock-ist {
      font-size: 19px;
      font-weight: 600;
      color: var(--accent-cyan);
      font-family: var(--font-display);
      font-variant-numeric: tabular-nums;
      letter-spacing: -0.01em;
    }
    .session-id {
      font-size: 12px;
      color: var(--text-muted);
      font-family: var(--font-mono);
      margin-top: 2px;
    }

    /* Model Switcher Segmented Control */
    .model-nav {
      display: flex;
      gap: 4px;
      margin-bottom: 24px;
      background: rgba(118, 118, 128, 0.24);
      padding: 4px;
      border-radius: 12px;
      flex-wrap: wrap;
      align-items: center;
    }
    .nav-tab {
      background: transparent;
      border: none;
      border-radius: 9px;
      color: var(--text-muted);
      padding: 8px 16px;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      min-height: 44px;
      transition: background 0.15s cubic-bezier(0.16, 1, 0.3, 1), color 0.15s ease;
      font-family: inherit;
    }
    .nav-tab:hover {
      color: var(--text-main);
      background: rgba(255, 255, 255, 0.05);
    }
    .nav-tab.active {
      background: #636366;
      color: #ffffff;
      font-weight: 600;
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.35);
    }
    .tab-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.3);
    }
    .nav-tab.active .tab-dot.dot-mizan {
      background: var(--profit-green);
      box-shadow: 0 0 6px var(--profit-green);
    }
    .nav-tab.active .tab-dot.dot-xs {
      background: var(--accent-cyan);
      box-shadow: 0 0 6px var(--accent-cyan);
    }
    .nav-tab.active .tab-dot.dot-registry {
      background: var(--highlight);
      box-shadow: 0 0 6px var(--highlight);
    }
    .tab-badge {
      font-size: 11px;
      font-weight: 600;
      padding: 2px 8px;
      border-radius: var(--radius-pill);
      background: rgba(255, 255, 255, 0.1);
      color: var(--text-muted);
    }
    .nav-tab.active .tab-badge {
      background: rgba(0, 0, 0, 0.4);
      color: #ffffff;
    }

    /* Automation Controls Panel */
    .controls-panel {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: var(--radius-outer);
      padding: 20px 24px;
      margin-bottom: 24px;
      box-shadow: var(--shadow-card);
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)) auto;
      gap: 16px;
      align-items: flex-end;
    }
    .control-group { display: flex; flex-direction: column; gap: 6px; }
    .control-label {
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
    }
    .control-input, .control-select {
      background: var(--input-bg);
      border: 1px solid var(--card-border);
      border-radius: var(--radius-inner);
      color: var(--text-main);
      padding: 9px 12px;
      font-family: var(--font-mono);
      font-size: 13px;
      font-variant-numeric: tabular-nums;
      min-height: 44px;
      outline: none;
      transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }
    .control-input:focus, .control-select:focus {
      border-color: var(--accent-blue);
      box-shadow: 0 0 0 3px rgba(10, 132, 255, 0.25);
    }
    .btn-group { display: flex; gap: 10px; }
    .btn {
      min-height: 44px;
      padding: 0 20px;
      font-size: 13px;
      font-weight: 600;
      border-radius: var(--radius-inner);
      cursor: pointer;
      border: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      font-family: inherit;
      transition: background 0.15s cubic-bezier(0.16, 1, 0.3, 1), transform 0.1s ease;
    }
    .btn:active { transform: scale(0.98); }
    .btn-start {
      background: var(--accent-blue);
      color: #ffffff;
      box-shadow: 0 2px 8px rgba(10, 132, 255, 0.35);
    }
    .btn-start:hover { background: var(--accent-blue-hover); }
    .btn-stop {
      background: var(--loss-red);
      color: #ffffff;
      box-shadow: 0 2px 8px rgba(255, 69, 58, 0.35);
    }
    .btn-stop:hover { background: #d70015; }

    /* KPI Grid */
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .kpi-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: var(--radius-outer);
      padding: 20px;
      box-shadow: var(--shadow-sm);
      transition: border-color 0.15s ease;
    }
    .kpi-card:hover {
      border-color: rgba(255, 255, 255, 0.16);
    }
    .kpi-label {
      font-size: 11px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 8px;
    }
    .kpi-val {
      font-family: var(--font-display);
      font-size: 26px;
      font-weight: 700;
      letter-spacing: -0.025em;
      font-variant-numeric: tabular-nums;
    }
    .kpi-sub {
      font-size: 12px;
      margin-top: 6px;
      font-variant-numeric: tabular-nums;
    }
    .text-green { color: var(--profit-green); }
    .text-red { color: var(--loss-red); }
    .text-cyan { color: var(--accent-cyan); }
    .text-blue { color: var(--accent-blue); }
    .text-muted { color: var(--text-muted); }

    /* Main Content Grid */
    .content-grid {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 24px;
      margin-bottom: 24px;
    }
    @media (max-width: 1024px) {
      .content-grid { grid-template-columns: 1fr; }
    }

    /* Section Cards */
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: var(--radius-outer);
      overflow: hidden;
      margin-bottom: 24px;
      box-shadow: var(--shadow-card);
    }
    .card-head {
      background: var(--card-bg);
      padding: 16px 20px;
      border-bottom: 1px solid var(--card-border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .card-title {
      font-size: 14px;
      font-weight: 600;
      letter-spacing: -0.01em;
      color: var(--text-main);
    }
    .card-body { padding: 20px; }

    /* Tables */
    table {
      width: 100%;
      border-collapse: collapse;
      font-family: var(--font-mono);
      font-size: 13px;
      font-variant-numeric: tabular-nums;
    }
    th {
      text-align: left;
      padding: 12px 16px;
      color: var(--text-muted);
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      border-bottom: 1px solid var(--card-border);
      background: rgba(255, 255, 255, 0.02);
    }
    th.text-right, td.text-right { text-align: right; }
    td {
      padding: 12px 16px;
      border-bottom: 1px solid var(--card-border-subtle);
      color: var(--text-main);
    }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background-color: rgba(255, 255, 255, 0.025); }

    /* Badges */
    .badge {
      display: inline-flex;
      align-items: center;
      padding: 3px 9px;
      border-radius: var(--radius-pill);
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.02em;
    }
    .badge-buy { background-color: var(--profit-bg); color: var(--profit-green); border: 1px solid var(--profit-border); }
    .badge-sell { background-color: var(--loss-bg); color: var(--loss-red); border: 1px solid var(--loss-border); }
    .badge-tag { background-color: rgba(255, 255, 255, 0.06); color: var(--text-muted); border: 1px solid var(--card-border); }
    .badge-top { background-color: rgba(94, 92, 230, 0.16); color: #8e8cf8; border: 1px solid rgba(94, 92, 230, 0.32); }

    /* Alpha Signals Progress Bars */
    .alpha-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 0;
      border-bottom: 1px solid var(--card-border-subtle);
      font-family: var(--font-mono);
      font-size: 13px;
      font-variant-numeric: tabular-nums;
    }
    .alpha-row:last-child { border-bottom: none; }
    .alpha-bar-bg {
      flex: 1;
      height: 6px;
      background: rgba(255, 255, 255, 0.08);
      border-radius: 3px;
      margin: 0 16px;
      overflow: hidden;
    }
    .alpha-bar-fill {
      height: 100%;
      background: linear-gradient(90deg, #0a84ff, #64d2ff);
      border-radius: 3px;
    }

    /* Risk Metrics Box */
    .risk-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      font-family: var(--font-mono);
      font-size: 12px;
      font-variant-numeric: tabular-nums;
    }
    .risk-item {
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--card-border);
      border-radius: var(--radius-inner);
      padding: 14px;
    }
    .risk-item-label { color: var(--text-muted); font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 6px; }
    .risk-item-val { font-size: 14px; font-weight: 600; font-variant-numeric: tabular-nums; }

    .control-message { min-height: 20px; margin: -8px 0 16px; font-size: 13px; }

    /* Empty state */
    .empty-state {
      padding: 36px;
      text-align: center;
      color: var(--text-muted);
      font-style: italic;
    }
  </style>
</head>
<body>
  <div class="container">
    <!-- Header -->
    <header class="header">
      <div class="header-left">
        <h1>QuantOS Live Trading & P&L Monitor <span class="badge-stopped" id="session-status">CONNECTING</span></h1>
        <div class="header-sub" id="header-sub">Model: waiting for the session to report&#8230;</div>
      </div>
      <div class="header-right">
        <div class="clock-ist" id="live-time">--:--:-- IST</div>
        <div class="session-id" id="session-id">Session: checking&#8230;</div>
      </div>
    </header>

    <!-- Model Switcher Navigation -->
    <nav class="model-nav">
      <button class="nav-tab active" id="tab-btn-mizan" data-tab="mizan">
        <span class="tab-dot dot-mizan"></span>
        <span>Mīzān Flagship Alpha</span>
        <span class="tab-badge">Intraday Paper Pilot</span>
      </button>
      <button class="nav-tab" id="tab-btn-xs" data-tab="xs">
        <span class="tab-dot dot-xs"></span>
        <span>Mīzān XS-Monthly Momentum</span>
        <span class="tab-badge">21-Day Paper Watch</span>
      </button>
      <button class="nav-tab" id="tab-btn-registry" data-tab="registry">
        <span class="tab-dot dot-registry"></span>
        <span>Strategy Directory & Governance</span>
        <span class="tab-badge">All Models</span>
      </button>
    </nav>

    <!-- TAB 1: Mīzān Model View -->
    <div id="view-mizan" class="model-view">

    <!-- Platform GUI Controls: Market Hours Schedule & Session Runner -->
    <section class="controls-panel" id="controls-panel">
      <div class="control-group">
        <label class="control-label" for="cfg-start-time">Market Start (IST)</label>
        <input type="time" id="cfg-start-time" class="control-input" value="09:15" step="1">
      </div>
      <div class="control-group">
        <label class="control-label" for="cfg-stop-time">Market Close (IST)</label>
        <input type="time" id="cfg-stop-time" class="control-input" value="15:30" step="1">
      </div>
      <div class="control-group">
        <label class="control-label" for="cfg-capital">Capital (₹ INR)</label>
        <input type="number" id="cfg-capital" class="control-input" value="1000000" step="100000">
      </div>
      <div class="control-group">
        <label class="control-label" for="cfg-slippage">Slippage (bps)</label>
        <input type="number" id="cfg-slippage" class="control-input" value="5.0" step="0.5">
      </div>
      <div class="control-group">
        <label class="control-label" for="cfg-model-profile">Model Engine Profile</label>
        <select id="cfg-model-profile" class="control-select">
          <option value="sprint_50k" selected>⚡ Mīzān 50K Sprint (Pure Stocks)</option>
          <option value="default">🏛️ Mīzān Flagship (Core Multi-Asset)</option>
        </select>
      </div>
      <div class="control-group">
        <label class="control-label" for="cfg-universe">Market Universe</label>
        <select id="cfg-universe" class="control-select">
          <option value="NIFTY500" selected>NIFTY 500 (96.1% Indian Market)</option>
          <option value="NIFTY200">NIFTY 200 (Top 200 Large & Mid-Caps)</option>
          <option value="NIFTY100">NIFTY 100 (Top 100 Blue Chips)</option>
          <option value="NIFTY50">NIFTY 50 (Benchmark 50)</option>
        </select>
      </div>
      <div class="control-group" style="min-width: 200px;">
        <label class="control-label" for="cfg-upstox-token">Upstox Access Token</label>
        <input type="password" id="cfg-upstox-token" class="control-input" placeholder="Paste Upstox Access Token..." autocomplete="off">
      </div>
      <div class="btn-group">
        <button id="btn-start" class="btn btn-start">▶ Start Automation</button>
        <button id="btn-stop" class="btn btn-stop">⏹ Halt & Reconcile</button>
      </div>
    </section>
    <div id="control-message" class="control-message" role="status" aria-live="polite"></div>

    <!-- Key Performance Metrics (KPIs) -->
    <section class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Total Portfolio Equity</div>
        <div class="kpi-val text-cyan" id="kpi-equity">₹--</div>
        <div class="kpi-sub text-muted">Initial: <span id="kpi-initial-cash">₹10,00,000.00</span></div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Net Profit & Loss</div>
        <div class="kpi-val" id="kpi-net-pnl">₹0.00</div>
        <div class="kpi-sub" id="kpi-net-pnl-pct">0.00%</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Unrealized (MtM) P&L</div>
        <div class="kpi-val" id="kpi-unrealized-pnl">₹0.00</div>
        <div class="kpi-sub text-muted">Active open exposure</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Available Cash Balance</div>
        <div class="kpi-val text-blue" id="kpi-cash">₹--</div>
        <div class="kpi-sub text-muted">Min Buffer: 5% (₹50,000)</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Statutory NSE Fees, Lifetime</div>
        <div class="kpi-val text-muted" id="kpi-fees">₹0.00</div>
        <div class="kpi-sub text-muted" id="kpi-fees-sub">STT, Exchange, SEBI, GST, Stamp</div>
      </div>
    </section>

    <!-- Main Grid: Positions vs Signals & Risk -->
    <div class="content-grid">
      <!-- Left Column: Open Positions Matrix -->
      <div>
        <div class="card">
          <div class="card-head">
            <span class="card-title">Live Positions Matrix & Mark-to-Market P&L</span>
            <span class="badge badge-tag" id="positions-count">0 Open Positions</span>
          </div>
          <div class="card-body" style="padding: 0;">
            <table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th class="text-right">Qty</th>
                  <th class="text-right">Entry (₹)</th>
                  <th class="text-right">Current (₹)</th>
                  <th class="text-right">Market Val (₹)</th>
                  <th class="text-right">Unrealized P&L</th>
                  <th class="text-right">Alloc %</th>
                </tr>
              </thead>
              <tbody id="positions-table-body">
                <tr><td colspan="7" class="empty-state">Waiting for active positions...</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Executed Fills Table -->
        <div class="card">
          <div class="card-head">
            <span class="card-title">Live Trade Executions & Fills Log</span>
            <span class="badge badge-tag" id="fills-count">0 Fills</span>
          </div>
          <div class="card-body" style="padding: 0;">
            <table>
              <thead>
                <tr>
                  <th>Time (IST)</th>
                  <th>Symbol</th>
                  <th>Side</th>
                  <th class="text-right">Quantity</th>
                  <th class="text-right">Price (₹)</th>
                  <th class="text-right">Statutory Fee (₹)</th>
                  <th>Fill ID</th>
                </tr>
              </thead>
              <tbody id="fills-table-body">
                <tr><td colspan="7" class="empty-state">No fills executed yet...</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Right Column: Model Alpha Signals & Risk Governor -->
      <div>
        <!-- Mīzān Model Alpha Predictions (Full NIFTY 50 Universe) -->
        <div class="card">
          <div class="card-head">
            <span class="card-title" id="alpha-title">Mīzān Alpha Signals &amp; Rankings</span>
            <span class="badge badge-top" id="alpha-count">—</span>
          </div>
          <div class="card-body" id="alpha-signals-container" style="max-height: 480px; overflow-y: auto;">
            <div class="empty-state">Loading model alpha predictions...</div>
          </div>
        </div>

        <!-- Pre-Trade Risk Governor & Reconciliation -->
        <div class="card">
          <div class="card-head">
            <span class="card-title">Pre-Trade Risk & Reconciliation</span>
            <span class="badge badge-tag">0.00 Paisa Exact</span>
          </div>
          <div class="card-body">
            <div class="risk-grid">
              <div class="risk-item">
                <div class="risk-item-label">Kill Switch Status</div>
                <div class="risk-item-val text-green" id="risk-kill-switch">NORMAL (SAFE)</div>
              </div>
              <div class="risk-item">
                <div class="risk-item-label">Position Weight Cap</div>
                <div class="risk-item-val text-cyan">Max 30% / Asset</div>
              </div>
              <div class="risk-item">
                <div class="risk-item-label">Daily Drawdown Limit</div>
                <div class="risk-item-val text-cyan">4.00% Max</div>
              </div>
              <div class="risk-item">
                <div class="risk-item-label">Ledger Discrepancy</div>
                <div class="risk-item-val text-green">₹0.00 Paisa (Pass)</div>
              </div>
            </div>
            <div style="margin-top: 16px; font-size: 12px; color: var(--text-muted); font-family: 'JetBrains Mono', monospace;">
              Configured Market Close: <span id="market-close-time" style="color: var(--accent-cyan);">15:30:00 IST</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div> <!-- /view-mizan -->

  <!-- TAB 2: Mīzān XS-Monthly Momentum View -->
  <div id="view-xs" class="model-view" style="display: none;">
    <!-- XS Model Banner -->
    <div class="card" style="border-left: 4px solid var(--accent-cyan); margin-bottom: 24px;">
      <div class="card-body" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
        <div>
          <h2 style="font-size: 16px; font-weight: 700; color: var(--text-main); display: flex; align-items: center; gap: 8px;">
            Mīzān XS-Monthly Momentum Strategy
            <span class="badge" style="background: rgba(100, 210, 255, 0.16); color: var(--accent-cyan); border: 1px solid rgba(100, 210, 255, 0.32);">21-Day Hold · Top 20%</span>
            <span class="badge" style="background: var(--loss-bg); color: var(--loss-red); border: 1px solid var(--loss-border);">RESEARCH ONLY · NO REAL ORDERS</span>
          </h2>
          <div style="font-size: 13px; color: var(--text-muted); margin-top: 4px; font-family: var(--font-mono);">
            Cross-sectional momentum ranking on NIFTY 500 universe · 0.224% round-trip friction · Forward paper watch
          </div>
        </div>
        <div style="text-align: right; font-family: var(--font-mono); font-size: 12px; color: var(--text-muted);">
          Task: <span style="color: var(--accent-cyan);">QuantOS-XSMonthly-PaperWatch</span><br>
          Cadence: Mon–Fri 16:00 IST
        </div>
      </div>
    </div>

    <!-- XS KPIs -->
    <section class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Total Book Equity</div>
        <div class="kpi-val text-cyan" id="xs-kpi-equity">₹--</div>
        <div class="kpi-sub text-muted">Capital: <span id="xs-kpi-capital">₹10,00,000.00</span></div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Unrealized (MtM) P&L</div>
        <div class="kpi-val" id="xs-kpi-pnl">₹--</div>
        <div class="kpi-sub" id="xs-kpi-pnl-pct">--% vs Capital</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Available Cash Balance</div>
        <div class="kpi-val text-blue" id="xs-kpi-cash">₹--</div>
        <div class="kpi-sub text-muted">Unallocated liquidity</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Open Market Exposure</div>
        <div class="kpi-val text-green" id="xs-kpi-market-val">₹--</div>
        <div class="kpi-sub text-muted" id="xs-kpi-open-legs">99 active open legs</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Strategy Specifications</div>
        <div class="kpi-val" style="font-size: 16px; padding-top: 6px;" id="xs-kpi-rule">21F / 21H / 20%</div>
        <div class="kpi-sub text-muted">Friction: 0.224% Round-Trip</div>
      </div>
    </section>

    <div id="xs-unpriced-note" hidden style="margin: 0 0 16px; padding: 12px 16px; border-left: 3px solid #ff9f0a; background: rgba(255, 159, 10, 0.12); border-radius: 0 var(--radius-inner) var(--radius-inner) 0; font-size: 12px; line-height: 1.5;"></div>

    <!-- XS Content Grid -->
    <div class="content-grid">
      <!-- Open Legs Table -->
      <div>
        <div class="card">
          <div class="card-head">
            <span class="card-title">Active Holdings Matrix (Top-20% Momentum Basket)</span>
            <span class="badge badge-tag" id="xs-open-count">Loading...</span>
          </div>
          <div class="card-body" style="padding: 0; max-height: 520px; overflow-y: auto;">
            <table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th class="text-right">Shares</th>
                  <th class="text-right">Entry (₹)</th>
                  <th class="text-right">Market Val (₹)</th>
                  <th class="text-right">Gross Mark</th>
                  <th class="text-right">Unrealized P&L</th>
                  <th>Entry Date</th>
                </tr>
              </thead>
              <tbody id="xs-positions-table-body">
                <tr><td colspan="7" class="empty-state">Loading XS-Monthly positions...</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- XS Right Column: Runs & Strategy Rules -->
      <div>
        <div class="card">
          <div class="card-head">
            <span class="card-title">Strategy Rules & Invariants</span>
            <span class="badge badge-tag">FROZEN RULE</span>
          </div>
          <div class="card-body">
            <div class="risk-grid">
              <div class="risk-item">
                <div class="risk-item-label">Formation Window</div>
                <div class="risk-item-val text-cyan">21 Sessions (~1 Mo)</div>
              </div>
              <div class="risk-item">
                <div class="risk-item-label">Holding Period</div>
                <div class="risk-item-val text-cyan">21 Sessions (~1 Mo)</div>
              </div>
              <div class="risk-item">
                <div class="risk-item-label">Selection Fraction</div>
                <div class="risk-item-val text-cyan">Top 20% Momentum</div>
              </div>
              <div class="risk-item">
                <div class="risk-item-label">Statutory NSE Friction</div>
                <div class="risk-item-val text-cyan">0.224% Round-Trip</div>
              </div>
            </div>
            <div style="margin-top: 16px; font-size: 12px; color: var(--text-muted); line-height: 1.6;">
              <strong>Research Governance Finding:</strong> Historical 10-year test on 423 liquid names gave a selection edge of only <strong>+5 bps</strong> over holding the market equal-weight, with negative Rank IC. Forward paper watch tests whether this +5 bps reproduces out-of-sample or collapses to zero.
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-head">
            <span class="card-title">Watch Execution History</span>
            <span class="badge badge-tag" id="xs-runs-count">0 Runs</span>
          </div>
          <div class="card-body" style="padding: 0; max-height: 240px; overflow-y: auto;">
            <table>
              <thead>
                <tr>
                  <th>Timestamp (UTC)</th>
                  <th>Action</th>
                  <th class="text-right">Legs</th>
                  <th class="text-right">Equity (₹)</th>
                </tr>
              </thead>
              <tbody id="xs-runs-table-body">
                <tr><td colspan="4" class="empty-state">No execution runs recorded yet.</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- TAB 3: Strategy Directory & Governance Overview -->
  <div id="view-registry" class="model-view" style="display: none;">
    <div class="card">
      <div class="card-head">
        <span class="card-title">QuantOS Model & Strategy Directory</span>
        <span class="badge badge-tag">Governance Snapshot</span>
      </div>
      <div class="card-body" style="padding: 0;">
        <table>
          <thead>
            <tr>
              <th>Model / Strategy Name</th>
              <th>Candidate ID</th>
              <th>Architecture & Horizon</th>
              <th>Validation Finding</th>
              <th>Promotion Verdict</th>
              <th>Live Execution Gate</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Mīzān Flagship Alpha</strong><br><span style="color: var(--text-muted); font-size: 11px;">quant_system.strategies.mizan_strategy</span></td>
              <td><code>cand_mizan_v1</code></td>
              <td>15-feature cross-sectional pooled L2 ridge regression · Intraday to multi-day</td>
              <td>Sharpe -0.4108, Deflated Sharpe 0.1760 (fails 0.95 gate)</td>
              <td><span class="badge" style="background: var(--loss-bg); color: var(--loss-red); border: 1px solid var(--loss-border);">RESEARCH_ONLY</span></td>
              <td><span class="badge" style="background: var(--profit-bg); color: var(--profit-green); border: 1px solid var(--profit-border);">Paper Pilot Active</span><br><span style="font-size: 10px; color: var(--text-muted);">Refused on live routing</span></td>
            </tr>
            <tr>
              <td><strong>Mīzān XS-Monthly Momentum</strong><br><span style="color: var(--text-muted); font-size: 11px;">quant_system.research_xs_monthly</span></td>
              <td><code>xs_monthly_top20</code></td>
              <td>Cross-sectional top-20% relative momentum ranker · 21 sessions (~1 month)</td>
              <td>Long-only +1.74%/period vs Market +1.69%/period; Selection edge +5 bps (noise); Long-short Sharpe -0.12</td>
              <td><span class="badge" style="background: var(--loss-bg); color: var(--loss-red); border: 1px solid var(--loss-border);">RESEARCH_ONLY</span></td>
              <td><span class="badge" style="background: rgba(100, 210, 255, 0.16); color: var(--accent-cyan); border: 1px solid rgba(100, 210, 255, 0.32);">Paper Watch Active</span><br><span style="font-size: 10px; color: var(--text-muted);">Scheduled out-of-sample test</span></td>
            </tr>
            <tr>
              <td><strong>Governed Single-Name Ridge</strong><br><span style="color: var(--text-muted); font-size: 11px;">quant_system.modeling.ridge</span></td>
              <td><code>cand_ridge_v1</code></td>
              <td>6-feature technical linear model with L2 regularization · Daily</td>
              <td>INFY Sharpe -0.704; NIFTY 50 median Sharpe -0.228; Best DSR 0.218 vs 0.95 gate. No edge after 0.224% costs.</td>
              <td><span class="badge" style="background: rgba(255, 255, 255, 0.08); color: var(--text-muted); border: 1px solid var(--card-border);">RETIRED / RESEARCH_ONLY</span></td>
              <td><span class="badge" style="background: var(--loss-bg); color: var(--loss-red); border: 1px solid var(--loss-border);">Blocked</span><br><span style="font-size: 10px; color: var(--text-muted);">Refused at promotion gate</span></td>
            </tr>
            <tr>
              <td><strong>Equity Dual Momentum</strong><br><span style="color: var(--text-muted); font-size: 11px;">quant_system.strategies.equity_momentum</span></td>
              <td><code>EquityDualMomentum</code></td>
              <td>Dual SMA trend filter (20/50) + 50-day relative momentum ranker · Swing</td>
              <td>Median Sharpe -2.2591 across NIFTY 50; beaten by losing Ridge on 26/40 names due to friction and whipsaws.</td>
              <td><span class="badge" style="background: rgba(255, 255, 255, 0.08); color: var(--text-muted); border: 1px solid var(--card-border);">INFERIOR BASELINE</span></td>
              <td><span class="badge" style="background: rgba(255, 255, 255, 0.08); color: var(--text-muted); border: 1px solid var(--card-border);">Registry Only</span></td>
            </tr>
            <tr>
              <td><strong>Rolling ML Equity / AI-Enhanced</strong><br><span style="color: var(--text-muted); font-size: 11px;">quant_system.strategies.ml_equity</span></td>
              <td><code>RollingRidgeClassifier</code></td>
              <td>Rolling unpurged ridge classifier with technical indicators & multi-agent AI advisory</td>
              <td>Lacks purging, embargoing, and multiplicity accounting.</td>
              <td><span class="badge" style="background: var(--loss-bg); color: var(--loss-red); border: 1px solid var(--loss-border);">RESEARCH_ONLY</span></td>
              <td><span class="badge" style="background: var(--loss-bg); color: var(--loss-red); border: 1px solid var(--loss-border);">Blocked</span><br><span style="font-size: 10px; color: var(--text-muted);">Refused at execution boundary (85ff535)</span></td>
            </tr>
            <tr>
              <td><strong>Intraday ATM Straddle</strong><br><span style="color: var(--text-muted); font-size: 11px;">quant_system.strategies.options_straddle</span></td>
              <td><code>IntradayATMStraddle</code></td>
              <td>Options theta writing: Sell 09:20 IST ATM Call/Put, 25% stop-loss, 15:15 IST square-off</td>
              <td>Code complete; not yet run through governed historical options evidence pipeline.</td>
              <td><span class="badge" style="background: rgba(255, 159, 10, 0.16); color: #ff9f0a; border: 1px solid rgba(255, 159, 10, 0.32);">UNADJUDICATED</span></td>
              <td><span class="badge" style="background: rgba(255, 255, 255, 0.08); color: var(--text-muted); border: 1px solid var(--card-border);">Registry Only</span></td>
            </tr>
            <tr>
              <td><strong>Directional Vertical Spreads</strong><br><span style="color: var(--text-muted); font-size: 11px;">quant_system.strategies.options_spreads</span></td>
              <td><code>DirectionalVerticalSpreads</code></td>
              <td>Defined-risk 2-leg vertical options spreads (Bull Call / Bear Put)</td>
              <td>Code complete; awaiting point-in-time options chain datasets.</td>
              <td><span class="badge" style="background: rgba(255, 159, 10, 0.16); color: #ff9f0a; border: 1px solid rgba(255, 159, 10, 0.32);">UNADJUDICATED</span></td>
              <td><span class="badge" style="background: rgba(255, 255, 255, 0.08); color: var(--text-muted); border: 1px solid var(--card-border);">Registry Only</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>

  <script src="/static/live_dashboard.js" defer></script>
</body>
</html>
"""
