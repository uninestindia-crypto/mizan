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
  </style>
</head>
<body>
  <div class="container">
    <!-- Header -->
    <header class="header">
      <div class="header-left">
        <h1>QuantOS Live Trading & P&L Monitor <span class="badge-live" id="session-status">LIVE STREAM</span></h1>
        <div class="header-sub">Model: Mīzān Flagship Alpha (NSE 50) | 15-Feature Cross-Sectional Ridge (v1.0.0)</div>
      </div>
      <div class="header-right">
        <div class="clock-ist" id="live-time">--:--:-- IST</div>
        <div class="session-id" id="session-id">Session: Loading...</div>
      </div>
    </header>

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
        <div class="kpi-label">Statutory NSE Fees Paid</div>
        <div class="kpi-val text-muted" id="kpi-fees">₹0.00</div>
        <div class="kpi-sub text-muted">STT, Exchange, SEBI, GST, Stamp</div>
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
            <span class="card-title">Mīzān Alpha Signals & Rankings (NIFTY 50)</span>
            <span class="badge badge-top" id="alpha-count">50 Stocks Evaluated</span>
          </div>
          <div class="card-body" id="alpha-signals-container" style="max-height: 480px; overflow-y: auto;">
            <div class="empty-state">Loading model alpha predictions for NIFTY 50 universe...</div>
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
  </div>

  <script>
    function formatINR(val) {
      const num = parseFloat(val);
      if (isNaN(num)) return "₹0.00";
      return "₹" + num.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
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
      document.getElementById("kpi-fees").textContent = formatINR(data.total_fees_paid || 0);

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

    // Auto-poll every 1500ms
    fetchStatus();
    setInterval(fetchStatus, 1500);
  </script>
</body>
</html>
"""
