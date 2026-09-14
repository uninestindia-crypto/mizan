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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-dark: #0a0e17;
      --card-bg: #111827;
      --card-border: #1f2937;
      --card-header: #1a2234;
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
      --accent-blue: #3b82f6;
      --accent-cyan: #06b6d4;
      --profit-green: #10b981;
      --profit-bg: rgba(16, 185, 129, 0.12);
      --loss-red: #ef4444;
      --loss-bg: rgba(239, 68, 68, 0.12);
      --badge-bg: #374151;
      --highlight: #6366f1;
      --input-bg: #0f172a;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg-dark);
      color: var(--text-main);
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      padding: 24px;
      line-height: 1.5;
    }
    .container { max-width: 1400px; margin: 0 auto; }

    /* Header */
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--card-border);
    }
    .header-left h1 {
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -0.5px;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .badge-live {
      background-color: rgba(16, 185, 129, 0.2);
      color: var(--profit-green);
      border: 1px solid var(--profit-green);
      padding: 2px 8px;
      font-size: 11px;
      font-weight: 600;
      border-radius: 9999px;
      letter-spacing: 0.5px;
      animation: pulse 2s infinite;
    }
    .badge-stopped {
      background-color: rgba(239, 68, 68, 0.2);
      color: var(--loss-red);
      border: 1px solid var(--loss-red);
      padding: 2px 8px;
      font-size: 11px;
      font-weight: 600;
      border-radius: 9999px;
    }
    @keyframes pulse {
      0% { opacity: 1; }
      50% { opacity: 0.5; }
      100% { opacity: 1; }
    }
    .header-sub {
      font-size: 13px;
      color: var(--text-muted);
      margin-top: 4px;
      font-family: 'JetBrains Mono', monospace;
    }
    .header-right {
      text-align: right;
      font-family: 'JetBrains Mono', monospace;
    }
    .clock-ist {
      font-size: 18px;
      font-weight: 600;
      color: var(--accent-cyan);
    }
    .session-id {
      font-size: 12px;
      color: var(--text-muted);
    }

    /* Automation Controls Panel */
    .controls-panel {
      background: linear-gradient(180deg, #162032 0%, #111827 100%);
      border: 1px solid #2563eb;
      border-radius: 12px;
      padding: 18px 24px;
      margin-bottom: 24px;
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
      letter-spacing: 0.5px;
      color: #93c5fd;
    }
    .control-input, .control-select {
      background: var(--input-bg);
      border: 1px solid var(--card-border);
      border-radius: 6px;
      color: var(--text-main);
      padding: 8px 12px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 13px;
    }
    .control-input:focus, .control-select:focus {
      border-color: var(--accent-blue);
      outline: none;
    }
    .btn-group { display: flex; gap: 10px; }
    .btn {
      padding: 9px 18px;
      font-size: 13px;
      font-weight: 600;
      border-radius: 6px;
      cursor: pointer;
      border: none;
      transition: all 0.15s ease;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .btn-start {
      background: #10b981;
      color: #064e3b;
    }
    .btn-start:hover { background: #059669; color: #ffffff; }
    .btn-stop {
      background: #ef4444;
      color: #7f1d1d;
    }
    .btn-stop:hover { background: #dc2626; color: #ffffff; }

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
      border-radius: 12px;
      padding: 18px;
      transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .kpi-card:hover {
      border-color: #374151;
      transform: translateY(-2px);
    }
    .kpi-label {
      font-size: 12px;
      font-weight: 500;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 6px;
    }
    .kpi-val {
      font-family: 'JetBrains Mono', monospace;
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.5px;
    }
    .kpi-sub {
      font-size: 12px;
      margin-top: 4px;
      font-family: 'JetBrains Mono', monospace;
    }
    .text-green { color: var(--profit-green); }
    .text-red { color: var(--loss-red); }
    .text-cyan { color: var(--accent-cyan); }
    .text-blue { color: var(--accent-blue); }

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
      border-radius: 12px;
      overflow: hidden;
      margin-bottom: 24px;
    }
    .card-head {
      background: var(--card-header);
      padding: 14px 20px;
      border-bottom: 1px solid var(--card-border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .card-title {
      font-size: 14px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: var(--text-main);
    }
    .card-body { padding: 16px; }

    /* Tables */
    table {
      width: 100%;
      border-collapse: collapse;
      font-family: 'JetBrains Mono', monospace;
      font-size: 13px;
    }
    th {
      text-align: left;
      padding: 10px 14px;
      color: var(--text-muted);
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      border-bottom: 1px solid var(--card-border);
    }
    th.text-right, td.text-right { text-align: right; }
    td {
      padding: 12px 14px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background-color: rgba(255, 255, 255, 0.02); }

    /* Badges */
    .badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.3px;
    }
    .badge-buy { background-color: var(--profit-bg); color: var(--profit-green); border: 1px solid var(--profit-green); }
    .badge-sell { background-color: var(--loss-bg); color: var(--loss-red); border: 1px solid var(--loss-red); }
    .badge-tag { background-color: #1e293b; color: #94a3b8; border: 1px solid #334155; }
    .badge-top { background-color: rgba(99, 102, 241, 0.2); color: #818cf8; border: 1px solid #6366f1; }

    /* Alpha Signals Progress Bars */
    .alpha-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      font-family: 'JetBrains Mono', monospace;
      font-size: 13px;
    }
    .alpha-row:last-child { border-bottom: none; }
    .alpha-bar-bg {
      flex: 1;
      height: 8px;
      background: #1f2937;
      border-radius: 4px;
      margin: 0 16px;
      overflow: hidden;
    }
    .alpha-bar-fill {
      height: 100%;
      background: linear-gradient(90deg, #3b82f6, #06b6d4);
      border-radius: 4px;
    }

    /* Risk Metrics Box */
    .risk-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
    }
    .risk-item {
      background: #0f172a;
      border: 1px solid #1e293b;
      border-radius: 8px;
      padding: 12px;
    }
    .risk-item-label { color: var(--text-muted); font-size: 11px; margin-bottom: 4px; }
    .risk-item-val { font-size: 14px; font-weight: 600; }

    /* Empty state */
    .empty-state {
      padding: 30px;
      text-align: center;
      color: var(--text-muted);
      font-style: italic;
    }
    /* Model Navigation Bar */
    .model-nav {
      display: flex;
      gap: 12px;
      margin-bottom: 24px;
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 14px;
      flex-wrap: wrap;
    }
    .nav-tab {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 8px;
      color: var(--text-muted);
      padding: 10px 18px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 10px;
      transition: all 0.15s ease;
    }
    .nav-tab:hover {
      background: #1f2937;
      color: var(--text-main);
      border-color: #374151;
    }
    .nav-tab.active {
      background: #1e293b;
      color: #ffffff;
      border-color: var(--accent-blue);
      box-shadow: 0 0 12px rgba(59, 130, 246, 0.25);
    }
    .tab-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #64748b;
    }
    .nav-tab.active .tab-dot.dot-mizan {
      background: var(--profit-green);
      box-shadow: 0 0 8px var(--profit-green);
    }
    .nav-tab.active .tab-dot.dot-xs {
      background: var(--accent-cyan);
      box-shadow: 0 0 8px var(--accent-cyan);
    }
    .nav-tab.active .tab-dot.dot-registry {
      background: var(--highlight);
      box-shadow: 0 0 8px var(--highlight);
    }
    .tab-badge {
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      padding: 2px 6px;
      border-radius: 4px;
      background: #374151;
      color: #d1d5db;
    }
    .nav-tab.active .tab-badge {
      background: rgba(59, 130, 246, 0.2);
      color: #93c5fd;
      border: 1px solid rgba(59, 130, 246, 0.4);
    }
  </style>
</head>
<body>
  <div class="container">
    <!-- Header -->
    <header class="header">
      <div class="header-left">
        <h1>QuantOS Live Trading & P&L Monitor <span class="badge-live" id="session-status">LIVE STREAM</span></h1>
        <div class="header-sub" id="header-sub">Model: waiting for the session to report&#8230;</div>
      </div>
      <div class="header-right">
        <div class="clock-ist" id="live-time">--:--:-- IST</div>
        <div class="session-id" id="session-id">Session: Loading...</div>
      </div>
    </header>

    <!-- Model Switcher Navigation -->
    <nav class="model-nav">
      <button class="nav-tab active" id="tab-btn-mizan" onclick="switchTab('mizan')">
        <span class="tab-dot dot-mizan"></span>
        <span>Mīzān Flagship Alpha</span>
        <span class="tab-badge">Intraday Paper Pilot</span>
      </button>
      <button class="nav-tab" id="tab-btn-xs" onclick="switchTab('xs')">
        <span class="tab-dot dot-xs"></span>
        <span>Mīzān XS-Monthly Momentum</span>
        <span class="tab-badge">21-Day Paper Watch</span>
      </button>
      <button class="nav-tab" id="tab-btn-registry" onclick="switchTab('registry')">
        <span class="tab-dot dot-registry"></span>
        <span>Strategy Directory & Governance</span>
        <span class="tab-badge">All Models</span>
      </button>
    </nav>

    <!-- TAB 1: Mīzān Model View -->
    <div id="view-mizan" class="model-view">

    <!-- Platform GUI Controls: Market Hours Schedule & Session Runner -->
    <section class="controls-panel">
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
        <button id="btn-start" class="btn btn-start" onclick="startAutomatedSession()">▶ Start Automation</button>
        <button id="btn-stop" class="btn btn-stop" onclick="stopAutomatedSession()">⏹ Halt & Reconcile</button>
      </div>
    </section>

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
          <h2 style="font-size: 16px; font-weight: 700; color: #ffffff; display: flex; align-items: center; gap: 8px;">
            Mīzān XS-Monthly Momentum Strategy
            <span class="badge" style="background: rgba(6, 182, 212, 0.2); color: var(--accent-cyan); border: 1px solid var(--accent-cyan);">21-Day Hold · Top 20%</span>
            <span class="badge" style="background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3);">RESEARCH ONLY · NO REAL ORDERS</span>
          </h2>
          <div style="font-size: 13px; color: var(--text-muted); margin-top: 4px; font-family: 'JetBrains Mono', monospace;">
            Cross-sectional momentum ranking on NIFTY 500 universe · 0.224% round-trip friction · Forward paper watch
          </div>
        </div>
        <div style="text-align: right; font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--text-muted);">
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

    <div id="xs-unpriced-note" hidden style="margin: 0 0 16px; padding: 10px 14px; border-left: 3px solid var(--accent-amber, #d98e04); background: rgba(217, 142, 4, 0.08); font-size: 12px; line-height: 1.5;"></div>

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
              <td><span class="badge" style="background: rgba(239, 68, 68, 0.15); color: #f87171;">RESEARCH_ONLY</span></td>
              <td><span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #34d399;">Paper Pilot Active</span><br><span style="font-size: 10px; color: var(--text-muted);">Refused on live routing</span></td>
            </tr>
            <tr>
              <td><strong>Mīzān XS-Monthly Momentum</strong><br><span style="color: var(--text-muted); font-size: 11px;">quant_system.research_xs_monthly</span></td>
              <td><code>xs_monthly_top20</code></td>
              <td>Cross-sectional top-20% relative momentum ranker · 21 sessions (~1 month)</td>
              <td>Long-only +1.74%/period vs Market +1.69%/period; Selection edge +5 bps (noise); Long-short Sharpe -0.12</td>
              <td><span class="badge" style="background: rgba(239, 68, 68, 0.15); color: #f87171;">RESEARCH_ONLY</span></td>
              <td><span class="badge" style="background: rgba(6, 182, 212, 0.15); color: #22d3ee;">Paper Watch Active</span><br><span style="font-size: 10px; color: var(--text-muted);">Scheduled out-of-sample test</span></td>
            </tr>
            <tr>
              <td><strong>Governed Single-Name Ridge</strong><br><span style="color: var(--text-muted); font-size: 11px;">quant_system.modeling.ridge</span></td>
              <td><code>cand_ridge_v1</code></td>
              <td>6-feature technical linear model with L2 regularization · Daily</td>
              <td>INFY Sharpe -0.704; NIFTY 50 median Sharpe -0.228; Best DSR 0.218 vs 0.95 gate. No edge after 0.224% costs.</td>
              <td><span class="badge" style="background: rgba(156, 163, 175, 0.2); color: #9ca3af;">RETIRED / RESEARCH_ONLY</span></td>
              <td><span class="badge" style="background: rgba(239, 68, 68, 0.15); color: #f87171;">Blocked</span><br><span style="font-size: 10px; color: var(--text-muted);">Refused at promotion gate</span></td>
            </tr>
            <tr>
              <td><strong>Equity Dual Momentum</strong><br><span style="color: var(--text-muted); font-size: 11px;">quant_system.strategies.equity_momentum</span></td>
              <td><code>EquityDualMomentum</code></td>
              <td>Dual SMA trend filter (20/50) + 50-day relative momentum ranker · Swing</td>
              <td>Median Sharpe -2.2591 across NIFTY 50; beaten by losing Ridge on 26/40 names due to friction and whipsaws.</td>
              <td><span class="badge" style="background: rgba(156, 163, 175, 0.2); color: #9ca3af;">INFERIOR BASELINE</span></td>
              <td><span class="badge" style="background: rgba(156, 163, 175, 0.2); color: #9ca3af;">Registry Only</span></td>
            </tr>
            <tr>
              <td><strong>Rolling ML Equity / AI-Enhanced</strong><br><span style="color: var(--text-muted); font-size: 11px;">quant_system.strategies.ml_equity</span></td>
              <td><code>RollingRidgeClassifier</code></td>
              <td>Rolling unpurged ridge classifier with technical indicators & multi-agent AI advisory</td>
              <td>Lacks purging, embargoing, and multiplicity accounting.</td>
              <td><span class="badge" style="background: rgba(239, 68, 68, 0.15); color: #f87171;">RESEARCH_ONLY</span></td>
              <td><span class="badge" style="background: rgba(239, 68, 68, 0.15); color: #f87171;">Blocked</span><br><span style="font-size: 10px; color: var(--text-muted);">Refused at execution boundary (85ff535)</span></td>
            </tr>
            <tr>
              <td><strong>Intraday ATM Straddle</strong><br><span style="color: var(--text-muted); font-size: 11px;">quant_system.strategies.options_straddle</span></td>
              <td><code>IntradayATMStraddle</code></td>
              <td>Options theta writing: Sell 09:20 IST ATM Call/Put, 25% stop-loss, 15:15 IST square-off</td>
              <td>Code complete; not yet run through governed historical options evidence pipeline.</td>
              <td><span class="badge" style="background: rgba(245, 158, 11, 0.2); color: #fbbf24;">UNADJUDICATED</span></td>
              <td><span class="badge" style="background: rgba(156, 163, 175, 0.2); color: #9ca3af;">Registry Only</span></td>
            </tr>
            <tr>
              <td><strong>Directional Vertical Spreads</strong><br><span style="color: var(--text-muted); font-size: 11px;">quant_system.strategies.options_spreads</span></td>
              <td><code>DirectionalVerticalSpreads</code></td>
              <td>Defined-risk 2-leg vertical options spreads (Bull Call / Bear Put)</td>
              <td>Code complete; awaiting point-in-time options chain datasets.</td>
              <td><span class="badge" style="background: rgba(245, 158, 11, 0.2); color: #fbbf24;">UNADJUDICATED</span></td>
              <td><span class="badge" style="background: rgba(156, 163, 175, 0.2); color: #9ca3af;">Registry Only</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>

  <script>
    function formatINR(val) {
      const num = parseFloat(val);
      if (isNaN(num)) return "₹0.00";
      return "₹" + num.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function switchTab(tabId) {
      document.querySelectorAll(".nav-tab").forEach(btn => btn.classList.remove("active"));
      const activeBtn = document.getElementById("tab-btn-" + tabId);
      if (activeBtn) activeBtn.classList.add("active");

      document.querySelectorAll(".model-view").forEach(view => view.style.display = "none");
      const targetView = document.getElementById("view-" + tabId);
      if (targetView) targetView.style.display = "block";
    }

    async function startAutomatedSession() {
      const capital = document.getElementById("cfg-capital").value || 50000;
      const slippage = document.getElementById("cfg-slippage").value || 5.0;
      const stopTime = document.getElementById("cfg-stop-time").value || "15:30";
      const interval = 10;
      const modelProfile = document.getElementById("cfg-model-profile").value || "sprint_50k";
      const universe = document.getElementById("cfg-universe").value || "NIFTY500";
      const upstoxToken = document.getElementById("cfg-upstox-token").value.trim();

      const stopTimeFormatted = stopTime.length === 5 ? stopTime + ":00" : stopTime;

      try {
        const res = await fetch("/api/control/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            capital: parseFloat(capital),
            slippage_bps: parseFloat(slippage),
            end_time_ist: stopTimeFormatted,
            interval_seconds: parseFloat(interval),
            model_profile: modelProfile,
            universe_name: universe,
            upstox_token: upstoxToken || null
          })
        });
        const data = await res.json();
        alert("Automated Trading Started on " + universe + ": " + (data.message || "Running until " + stopTimeFormatted + " IST"));
        fetchStatus();
      } catch (err) {
        alert("Failed to start session: " + err);
      }
    }

    async function stopAutomatedSession() {
      try {
        const res = await fetch("/api/control/stop", { method: "POST" });
        const data = await res.json();
        alert("Trading Session Halted: " + (data.message || "Reconciled with 0.00 Paisa discrepancy."));
        fetchStatus();
      } catch (err) {
        alert("Failed to halt session: " + err);
      }
    }

    async function fetchStatus() {
      try {
        const res = await fetch("/api/status");
        if (!res.ok) return;
        const data = await res.json();
        updateDashboard(data);
      } catch (err) {
        console.error("Failed to fetch live status:", err);
      }
    }

    function updateDashboard(data) {
      if (!data || !data.session_id) return;

      document.getElementById("live-time").textContent = data.timestamp_ist || "--:--:-- IST";
      document.getElementById("session-id").textContent = "Session: " + data.session_id;

      const statusElem = document.getElementById("session-status");
      statusElem.textContent = data.status || "RUNNING";
      if (data.status === "COMPLETED") {
        statusElem.className = "badge-stopped";
      } else {
        statusElem.className = "badge-live";
      }

      // KPIs
      document.getElementById("kpi-equity").textContent = formatINR(data.total_equity);
      document.getElementById("kpi-cash").textContent = formatINR(data.cash);
      document.getElementById("kpi-initial-cash").textContent = formatINR(data.initial_cash || 1000000);
      // Every other KPI in this row is lifetime. `total_fees_paid` is session-scoped, so pairing it
      // with them showed "₹0.00" on a hold day against a lifetime loss that already contained
      // ₹1,072.65 of fees. Prefer the lifetime figure, and say which one is on screen.
      const lifetimeFees = data.lifetime_fees_paid;
      const sessionFees = data.session_fees_paid ?? data.total_fees_paid ?? 0;
      const feesSub = document.getElementById("kpi-fees-sub");
      if (lifetimeFees === undefined) {
        document.getElementById("kpi-fees").textContent = formatINR(sessionFees);
        if (feesSub) feesSub.textContent = "This session only — lifetime not published";
      } else {
        document.getElementById("kpi-fees").textContent = formatINR(lifetimeFees);
        if (feesSub) feesSub.textContent =
          "Already inside Net P&L · " + formatINR(sessionFees) + " this session";
      }

      // Net PnL formatting
      const netPnl = parseFloat(data.net_pnl || 0);
      const netPnlPct = parseFloat(data.net_pnl_pct || 0);
      const netPnlElem = document.getElementById("kpi-net-pnl");
      const netPnlPctElem = document.getElementById("kpi-net-pnl-pct");

      netPnlElem.textContent = (netPnl >= 0 ? "+" : "") + formatINR(netPnl);
      netPnlPctElem.textContent = (netPnlPct >= 0 ? "+" : "") + netPnlPct.toFixed(2) + "% vs Capital";

      if (netPnl >= 0) {
        netPnlElem.className = "kpi-val text-green";
        netPnlPctElem.className = "kpi-sub text-green";
      } else {
        netPnlElem.className = "kpi-val text-red";
        netPnlPctElem.className = "kpi-sub text-red";
      }

      // Unrealized PnL
      const uPnl = parseFloat(data.unrealized_pnl || 0);
      const uPnlElem = document.getElementById("kpi-unrealized-pnl");
      uPnlElem.textContent = (uPnl >= 0 ? "+" : "") + formatINR(uPnl);
      uPnlElem.className = "kpi-val " + (uPnl >= 0 ? "text-green" : "text-red");

      // Positions Table
      const posBody = document.getElementById("positions-table-body");
      const posCountElem = document.getElementById("positions-count");
      const positions = data.positions_detail || [];
      posCountElem.textContent = positions.length + " Open Positions";

      if (positions.length === 0) {
        posBody.innerHTML = '<tr><td colspan="7" class="empty-state">Waiting for active positions...</td></tr>';
      } else {
        posBody.innerHTML = positions.map(pos => {
          const pnl = parseFloat(pos.unrealized_pnl);
          const pnlClass = pnl >= 0 ? "text-green" : "text-red";
          const pnlSign = pnl >= 0 ? "+" : "";
          return `
            <tr>
              <td><strong>${pos.symbol}</strong></td>
              <td class="text-right">${pos.quantity}</td>
              <td class="text-right">₹${pos.entry_price}</td>
              <td class="text-right">₹${pos.current_price}</td>
              <td class="text-right">₹${pos.market_value}</td>
              <td class="text-right ${pnlClass}"><strong>${pnlSign}₹${pos.unrealized_pnl}</strong> (${pnlSign}${pos.unrealized_pnl_pct}%)</td>
              <td class="text-right">${pos.allocation_pct}%</td>
            </tr>
          `;
        }).join("");
      }

      // Fills Log Table
      const fillsBody = document.getElementById("fills-table-body");
      const fillsCountElem = document.getElementById("fills-count");
      const fills = data.recent_fills || [];
      fillsCountElem.textContent = (data.fills_count || fills.length) + " Total Fills";

      if (fills.length === 0) {
        fillsBody.innerHTML = '<tr><td colspan="7" class="empty-state">No fills executed yet...</td></tr>';
      } else {
        fillsBody.innerHTML = fills.slice().reverse().map(f => {
          const badgeClass = f.side === "BUY" ? "badge-buy" : "badge-sell";
          return `
            <tr>
              <td>${f.timestamp_ist}</td>
              <td><strong>${f.symbol}</strong></td>
              <td><span class="badge ${badgeClass}">${f.side}</span></td>
              <td class="text-right">${f.quantity}</td>
              <td class="text-right">₹${f.price}</td>
              <td class="text-right">₹${f.fee}</td>
              <td><span class="badge badge-tag">${f.fill_id.split('_').slice(-2).join('_')}</span></td>
            </tr>
          `;
        }).join("");
      }

      // Alpha Signals
      // Labels come from the session, not from a constant. They previously said NIFTY 50 and
      // "50 Stocks Evaluated" regardless of what was running.
      const universeName = data.universe_name || "";
      const scored = data.scored_count;
      const universeSize = data.universe_size;
      if (universeName) {
        document.getElementById("alpha-title").textContent =
          "Mīzān Alpha Signals & Rankings (" + universeName + ")";
        // Derived, not asserted. The feature count and version were string literals here and
        // in the static header until 2026-09-10. Both happened to be correct, which is worse
        // than being wrong: nothing would have announced them going stale when the model
        // changed. Same defect as the hardcoded "NIFTY 50" title this line already fixed for
        // the universe -- half of it was repaired and half was left.
        var modelName = data.model_name || "Mīzān Flagship Alpha";
        var featureCount = data.feature_count;
        var modelVersion = data.model_version;
        var descriptor = (featureCount ? featureCount + "-Feature " : "") +
          "Cross-Sectional Ridge" + (modelVersion ? " (v" + modelVersion + ")" : "");
        // The name and version are shared by every retrain of this product, so they do not identify
        // what is running. The trial id does, and a newer flagship card describes a *different*
        // trial: training one does not replace these frozen weights. Say which is loaded, and as of
        // when the prices were marked, so neither is inferred.
        var prov = data.model_provenance || {};
        var trial = prov.source_trial_id ? " | Trial: " + prov.source_trial_id : "";
        var verdict = prov.verdict ? " · " + prov.verdict : "";
        var markedAt = data.timestamp_ist ? " | Marked: " + data.timestamp_ist : "";
        document.getElementById("header-sub").textContent =
          "Model: " + modelName + " (" + universeName + ") | " + descriptor +
          trial + verdict + markedAt;
      }
      if (scored !== undefined && scored !== null) {
        document.getElementById("alpha-count").textContent =
          universeSize ? scored + " of " + universeSize + " Scored" : scored + " Scored";
      }

      const alphaCont = document.getElementById("alpha-signals-container");
      const signals = data.alpha_signals || [];
      if (signals.length === 0) {
        alphaCont.innerHTML = '<div class="empty-state">No alpha signals yet...</div>';
      } else {
        const maxScore = Math.max(...signals.map(s => Math.abs(s.score)), 0.08);
        alphaCont.innerHTML = signals.map(s => {
          const widthPct = Math.min(100, Math.max(5, (Math.abs(s.score) / maxScore) * 100));
          const topPickTag = s.is_top_pick ? '<span class="badge badge-top">TOP PICK</span>' : '';
          const scoreSign = s.score >= 0 ? "+" : "";
          const scoreColor = s.score >= 0 ? "var(--accent-cyan)" : "#ef4444";
          return `
            <div class="alpha-row">
              <div style="width: 110px;"><strong>#${s.rank} ${s.symbol}</strong></div>
              <div class="alpha-bar-bg">
                <div class="alpha-bar-fill" style="width: ${widthPct}%; background: ${s.score >= 0 ? 'var(--accent-cyan)' : 'rgba(239, 68, 68, 0.5)'};"></div>
              </div>
              <div style="width: 75px; text-align: right; color: ${scoreColor}; font-weight: 600;">${scoreSign}${s.score.toFixed(4)}</div>
              <div style="width: 80px; text-align: right;">${topPickTag}</div>
            </div>
          `;
        }).join("");
      }

      // Market close
      if (data.market_close_ist) {
        document.getElementById("market-close-time").textContent = data.market_close_ist;
      }
    }

    function escapeHtml(str) {
      if (!str) return "";
      return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    }

    async function fetchXsStatus() {
      try {
        const res = await fetch("/api/xs_status");
        if (!res.ok) return;
        const data = await res.json();
        updateXsDashboard(data);
      } catch (err) {
        console.error("Failed to fetch XS status:", err);
      }
    }

    function updateXsDashboard(data) {
      if (!data) return;
      const capital = parseFloat(data.capital) || 1000000;
      const cash = parseFloat(data.cash) || 0;
      const openLegs = data.open || [];
      const runs = data.runs || [];

      // `parseFloat(x) || 0` reads a holding nobody can value as worth zero. A leg flagged
      // `unpriced` carries no market_value and no unrealized key at all, on purpose, so it is
      // counted separately and its entry cost is disclosed rather than folded into either total.
      let totalMarketVal = 0;
      let totalUnrealized = 0;
      const unpricedLegs = [];
      let unpricedAtCost = 0;
      openLegs.forEach(leg => {
        if (leg.unpriced || leg.market_value === undefined) {
          unpricedLegs.push(leg);
          unpricedAtCost += parseFloat(leg.entry_value) || 0;
          return;
        }
        totalMarketVal += parseFloat(leg.market_value) || 0;
        totalUnrealized += parseFloat(leg.unrealized) || 0;
      });
      (data.unresolved || []).forEach(leg => {
        unpricedLegs.push(leg);
        unpricedAtCost += parseFloat(leg.entry_value) || 0;
      });

      const totalEquity = cash + totalMarketVal;
      const pnlPct = capital > 0 ? (totalUnrealized / capital) * 100 : 0;

      document.getElementById("xs-kpi-equity").textContent = formatINR(totalEquity);
      document.getElementById("xs-kpi-capital").textContent = formatINR(capital);
      document.getElementById("xs-kpi-cash").textContent = formatINR(cash);
      document.getElementById("xs-kpi-market-val").textContent = formatINR(totalMarketVal);
      document.getElementById("xs-kpi-open-legs").textContent = openLegs.length + " active open legs";

      const unpricedElem = document.getElementById("xs-unpriced-note");
      if (unpricedElem) {
        if (unpricedLegs.length === 0) {
          unpricedElem.hidden = true;
          unpricedElem.textContent = "";
        } else {
          unpricedElem.hidden = false;
          const names = unpricedLegs.map(l => escapeHtml(l.symbol)).join(", ");
          unpricedElem.innerHTML =
            "<strong>Equity and P&amp;L above exclude " + unpricedLegs.length +
            " unpriced holding(s):</strong> " + names + ". Entry cost " +
            formatINR(unpricedAtCost) +
            " is still committed; its current value is unknown — not zero, and not break-even.";
        }
      }

      const pnlElem = document.getElementById("xs-kpi-pnl");
      const pnlPctElem = document.getElementById("xs-kpi-pnl-pct");
      const pnlSign = totalUnrealized >= 0 ? "+" : "";
      pnlElem.textContent = pnlSign + formatINR(totalUnrealized);
      pnlPctElem.textContent = pnlSign + pnlPct.toFixed(2) + "% vs Capital";

      if (totalUnrealized >= 0) {
        pnlElem.className = "kpi-val text-green";
        pnlPctElem.className = "kpi-sub text-green";
      } else {
        pnlElem.className = "kpi-val text-red";
        pnlPctElem.className = "kpi-sub text-red";
      }

      document.getElementById("xs-open-count").textContent = openLegs.length + " Positions";
      const posBody = document.getElementById("xs-positions-table-body");
      if (openLegs.length === 0) {
        posBody.innerHTML = '<tr><td colspan="7" class="empty-state">No active open legs in XS-Monthly watch.</td></tr>';
      } else {
        posBody.innerHTML = openLegs.map(leg => {
          if (leg.unpriced || leg.market_value === undefined) {
            // Every numeric cell is refused, not zeroed. A "0.00%" or "₹0" here would be read as a
            // measurement, which is the assertion this whole path exists to avoid making.
            return `
            <tr>
              <td><strong>${escapeHtml(leg.symbol)}</strong></td>
              <td class="text-right">${leg.shares}</td>
              <td class="text-right">₹${parseFloat(leg.entry_open).toLocaleString('en-IN', {minimumFractionDigits: 1})}</td>
              <td class="text-right text-muted" colspan="3" title="${escapeHtml(leg.unpriced_reason || '')}">unpriced — value unknown</td>
              <td>${escapeHtml(leg.entry_date)}</td>
            </tr>
          `;
          }
          const uPnl = parseFloat(leg.unrealized) || 0;
          const uPnlClass = uPnl >= 0 ? "text-green" : "text-red";
          const uPnlSign = uPnl >= 0 ? "+" : "";
          const grossMark = parseFloat(leg.gross_mark) || 0;
          const grossPct = (grossMark * 100).toFixed(2) + "%";
          return `
            <tr>
              <td><strong>${escapeHtml(leg.symbol)}</strong></td>
              <td class="text-right">${leg.shares}</td>
              <td class="text-right">₹${parseFloat(leg.entry_open).toLocaleString('en-IN', {minimumFractionDigits: 1})}</td>
              <td class="text-right">₹${parseFloat(leg.market_value).toLocaleString('en-IN', {minimumFractionDigits: 1})}</td>
              <td class="text-right ${grossMark >= 0 ? 'text-green' : 'text-red'}">${grossMark >= 0 ? '+' : ''}${grossPct}</td>
              <td class="text-right ${uPnlClass}"><strong>${uPnlSign}₹${uPnl.toFixed(1)}</strong></td>
              <td>${leg.entry_date}</td>
            </tr>
          `;
        }).join("");
      }

      document.getElementById("xs-runs-count").textContent = runs.length + " Runs";
      const runsBody = document.getElementById("xs-runs-table-body");
      if (runs.length === 0) {
        runsBody.innerHTML = '<tr><td colspan="4" class="empty-state">No execution runs recorded yet.</td></tr>';
      } else {
        runsBody.innerHTML = runs.slice().reverse().map(r => `
          <tr>
            <td><code>${r.at ? r.at.replace('T', ' ').replace('Z', ' UTC') : '--'}</code></td>
            <td><span class="badge badge-tag">${escapeHtml(r.note || 'run')}</span></td>
            <td class="text-right">${r.open_legs !== undefined ? r.open_legs : '--'}</td>
            <td class="text-right text-cyan">₹${r.equity ? parseFloat(r.equity).toLocaleString('en-IN', {minimumFractionDigits: 2}) : '--'}</td>
          </tr>
        `).join("");
      }
    }

    // Auto-poll Mīzān every 1500ms, XS-Monthly every 3000ms
    fetchStatus();
    fetchXsStatus();
    setInterval(fetchStatus, 1500);
    setInterval(fetchXsStatus, 3000);
  </script>
</body>
</html>
"""
