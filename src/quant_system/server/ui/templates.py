"""Full Dashboard and Standalone Template Generators for QuantOS UI."""

from __future__ import annotations

from quant_system import __version__
from quant_system.server.ui.constants import (
    JOURNEY_FEATURES_ID,
    JOURNEY_HOLDOUT_ID,
    JOURNEY_INGESTION_ID,
    JOURNEY_LEDGER_ID,
    JOURNEY_METADATA,
    JOURNEY_PILOT_ID,
    JOURNEY_SHADOW_ID,
    JOURNEY_TRAINING_ID,
    VALID_JOURNEY_IDS,
)
from quant_system.server.ui.journeys import (
    render_features_component,
    render_holdout_component,
    render_ingestion_component,
    render_ledger_component,
    render_pilot_component,
    render_shadow_component,
    render_training_component,
)


def render_nav_tabs(active_tab_id: str = JOURNEY_INGESTION_ID) -> str:
    """Renders accessible keyboard-navigable navigation tabs."""
    tab_html = ['<nav class="nav-tabs" role="tablist" aria-label="QuantOS User Journeys">']

    # 7 Core User Journeys
    for meta in JOURNEY_METADATA:
        jid = meta["id"]
        is_active = jid == active_tab_id
        active_cls = " active" if is_active else ""
        aria_selected = "true" if is_active else "false"
        tab_index = "0" if is_active else "-1"

        tab_html.append(
            f'<button class="tab-btn{active_cls}" id="tab-btn-{jid}" data-tab="tab-{jid}" '
            f'role="tab" aria-selected="{aria_selected}" aria-controls="tab-{jid}" '
            f'tabindex="{tab_index}">{meta["nav_label"]}</button>'
        )

    # Secondary tabs: Straddle, Monte Carlo, Risk Governor, Diagnostics, Live Trading
    secondary = [
        ("straddle", "⚡ Options Lab"),
        ("montecarlo", "🎲 Monte Carlo"),
        ("risk", "🛡️ Risk Governor"),
        ("diagnostics", "🩺 Diagnostics"),
    ]
    for sid, label in secondary:
        is_active = sid == active_tab_id
        active_cls = " active" if is_active else ""
        aria_selected = "true" if is_active else "false"
        tab_index = "0" if is_active else "-1"

        tab_html.append(
            f'<button class="tab-btn{active_cls}" id="tab-btn-{sid}" data-tab="tab-{sid}" '
            f'role="tab" aria-selected="{aria_selected}" aria-controls="tab-{sid}" '
            f'tabindex="{tab_index}">{label}</button>'
        )

    # Direct link to Live Trading & P&L Monitor screen
    tab_html.append(
        '<a href="/live" class="tab-btn" style="text-decoration:none; color: var(--color-accent); font-weight:600;" '
        'title="Open Live Trading & P&L Monitor Screen">📈 Live Trading & P&L</a>'
    )

    tab_html.append("</nav>")
    return "\n".join(tab_html)


def render_full_dashboard_html() -> str:
    """Renders the comprehensive single-page dashboard containing all 7 core journeys."""
    nav_tabs = render_nav_tabs(JOURNEY_INGESTION_ID)

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>QuantOS Desktop — Institutional Quant & Risk Engine v{__version__}</title>
  <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
  <!-- Skip link for keyboard accessibility -->
  <a href="#main-content" class="skip-link">Skip to main content</a>

  <!-- Top Navigation Bar -->
  <header class="navbar" role="banner">
    <div class="brand">
      <div class="brand-logo" aria-label="QuantOS Home">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
          <polyline points="22 7 13.5 15.5 8.5 10.5 2 17"></polyline>
          <polyline points="16 7 22 7 22 13"></polyline>
        </svg>
        <span>QuantOS</span>
      </div>
      <span class="brand-badge">v{__version__}</span>
    </div>

    {nav_tabs}

    <div class="nav-controls">
      <div class="status-pill" role="status" aria-live="polite">
        <span class="status-dot" aria-hidden="true"></span>
        <span id="engine-status">ONLINE</span>
      </div>
      <button class="icon-btn" id="theme-toggle" title="Toggle Theme" aria-label="Toggle Dark/Light Mode">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <circle cx="12" cy="12" r="5"></circle>
          <line x1="12" y1="1" x2="12" y2="3"></line>
          <line x1="12" y1="21" x2="12" y2="23"></line>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
          <line x1="1" y1="12" x2="3" y2="12"></line>
          <line x1="21" y1="12" x2="23" y2="12"></line>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
        </svg>
      </button>
    </div>
  </header>

  <!-- Main Application Body -->
  <main class="container" id="main-content" role="main">

    <!-- JOURNEY 1: Data Ingestion & Manifest Inspection -->
    {render_ingestion_component()}

    <!-- JOURNEY 2: Feature Matrix & Label Explorer -->
    {render_features_component()}

    <!-- JOURNEY 3: Governed Ridge Training & Baseline Comparison -->
    {render_training_component()}

    <!-- JOURNEY 4: Single-use Holdout & Stress Testing Tearsheet -->
    {render_holdout_component()}

    <!-- JOURNEY 5: Ledger & Backtest P&L Tearsheet -->
    {render_ledger_component()}

    <!-- JOURNEY 6: Real-Time / Replay Shadow Monitor -->
    {render_shadow_component()}

    <!-- JOURNEY 7: Paper Pilot Campaign Dashboard -->
    {render_pilot_component()}

    <!-- SECONDARY: Options Lab -->
    <section id="tab-straddle" class="tab-panel" data-test="lab-straddle" role="tabpanel" aria-labelledby="tab-btn-straddle" tabindex="0">
      <div class="journey-header">
        <div>
          <h1 class="journey-title">09:20 Intraday Straddle Lab</h1>
          <p class="journey-subtitle">Black-Scholes analytical Greeks computation and theta decay model.</p>
        </div>
      </div>
      <div class="grid-2col">
        <aside class="sidebar">
          <div class="card">
            <h2 class="card-title">09:20 Straddle Setup</h2>
            <div class="form-group">
              <label class="form-label" for="opt-spot">NIFTY Spot Price (₹)</label>
              <input type="number" id="opt-spot" class="form-input" value="24500.0" step="10">
            </div>
            <div class="form-group">
              <label class="form-label" for="opt-vol">Implied Volatility (%)</label>
              <input type="number" id="opt-vol" class="form-input" value="18.0" step="0.5">
            </div>
            <div class="form-group">
              <label class="form-label" for="opt-dte">Days to Expiry (DTE)</label>
              <input type="number" id="opt-dte" class="form-input" value="7" min="1" max="60">
            </div>
            <div class="form-group">
              <label class="form-label" for="opt-qty">Contracts / Quantity</label>
              <input type="number" id="opt-qty" class="form-input" value="25" step="25" min="25">
            </div>
            <button type="button" id="btn-calc-straddle" class="btn-primary" aria-label="Compute Analytical Greeks">
              <span>Compute Analytical Greeks</span>
            </button>
          </div>
        </aside>

        <div class="main-panel">
          <div class="metrics-grid" role="region" aria-label="Straddle Key Metrics">
            <div class="stat-box">
              <div class="stat-label">ATM Strike Selected</div>
              <div class="stat-value" id="opt-atm-strike">--</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Net Delta (Δ)</div>
              <div class="stat-value" id="opt-net-delta">--</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Daily Theta Decay (₹)</div>
              <div class="stat-value positive" id="opt-theta-decay">--</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Total Premium (₹)</div>
              <div class="stat-value" id="opt-total-premium">--</div>
            </div>
          </div>

          <div class="card">
            <h2 class="card-title">Options Greeks Breakdown (Black-Scholes Engine)</h2>
            <div class="table-wrapper">
              <table class="data-table" aria-label="Greeks Breakdown Table">
                <thead>
                  <tr>
                    <th scope="col">Leg</th>
                    <th scope="col">Strike</th>
                    <th scope="col">Premium (₹)</th>
                    <th scope="col">Delta (Δ)</th>
                    <th scope="col">Gamma (Γ)</th>
                    <th scope="col">Theta (Θ/day)</th>
                    <th scope="col">Vega (ν)</th>
                  </tr>
                </thead>
                <tbody id="greeks-tbody">
                  <tr><td colspan="7" style="text-align:center; color:var(--color-text-secondary);">Click "Compute Analytical Greeks" to inspect.</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- SECONDARY: Monte Carlo & Portfolio Optimization -->
    <section id="tab-montecarlo" class="tab-panel" data-test="lab-montecarlo" role="tabpanel" aria-labelledby="tab-btn-montecarlo" tabindex="0">
      <div class="journey-header">
        <div>
          <h1 class="journey-title">Monte Carlo & Markowitz Optimization</h1>
          <p class="journey-subtitle">Vectorized path simulation in RAM and quadratic covariance optimization.</p>
        </div>
      </div>
      <div class="grid-2col">
        <aside class="sidebar">
          <div class="card">
            <h2 class="card-title">Monte Carlo Setup</h2>
            <div class="form-group">
              <label class="form-label" for="mc-sims">Simulated Paths</label>
              <select id="mc-sims" class="form-select">
                <option value="1000">1,000 Paths</option>
                <option value="5000" selected>5,000 Paths</option>
                <option value="10000">10,000 Paths</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label" for="mc-horizon">Horizon (Trading Days)</label>
              <input type="number" id="mc-horizon" class="form-input" value="252" min="30" max="756">
            </div>
            <div class="form-group">
              <label class="form-label" for="mc-capital">Initial Capital (₹)</label>
              <input type="number" id="mc-capital" class="form-input" value="1000000" step="50000">
            </div>
            <button type="button" id="btn-run-mc" class="btn-primary" aria-label="Run Monte Carlo Simulation">
              <span>Run Monte Carlo Simulation</span>
            </button>
          </div>

          <div class="card">
            <h2 class="card-title">Markowitz Optimizer</h2>
            <button type="button" id="btn-run-opt" class="btn-secondary" style="width:100%;" aria-label="Solve Optimal Weights">
              Solve Optimal Weights
            </button>
          </div>
        </aside>

        <div class="main-panel">
          <div class="metrics-grid" role="region" aria-label="Monte Carlo Metrics">
            <div class="stat-box">
              <div class="stat-label">Value at Risk (VaR 95%)</div>
              <div class="stat-value negative" id="mc-var-95">--</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Conditional VaR (CVaR)</div>
              <div class="stat-value negative" id="mc-cvar-95">--</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Prob. of Profit</div>
              <div class="stat-value positive" id="mc-prob-profit">--</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Median Final Equity</div>
              <div class="stat-value" id="mc-median-equity">--</div>
            </div>
          </div>

          <div class="card">
            <h2 class="card-title">Monte Carlo Equity Cones</h2>
            <div class="chart-card">
              <canvas id="mcChart" aria-label="Monte Carlo Chart" role="img"></canvas>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- SECONDARY: Pre-Trade Risk Governor -->
    <section id="tab-risk" class="tab-panel" data-test="lab-risk" role="tabpanel" aria-labelledby="tab-btn-risk" tabindex="0">
      <div class="journey-header">
        <div>
          <h1 class="journey-title">Pre-Trade Risk Governor & Invariant Limits</h1>
          <p class="journey-subtitle">Real-time risk enforcement thresholds, circuit breakers, and cash buffer rules.</p>
        </div>
      </div>
      <div class="card" style="max-width: 800px; margin: 0 auto;">
        <h2 class="card-title">Active Governance Limits</h2>
        <form id="risk-form" onsubmit="return false;">
          <fieldset class="form-fieldset">
            <legend class="sr-only">Risk Limits Configuration</legend>
            <div class="form-group">
              <label class="form-label" for="risk-max-pos">Max Single Position Weight (%)</label>
              <input type="number" id="risk-max-pos" class="form-input" step="1" min="5" max="100">
            </div>
            <div class="form-group">
              <label class="form-label" for="risk-daily-dd">Max Daily Drawdown Stop (%)</label>
              <input type="number" id="risk-daily-dd" class="form-input" step="0.5" min="1" max="20">
            </div>
            <div class="form-group">
              <label class="form-label" for="risk-total-dd">Max Trailing Drawdown (%)</label>
              <input type="number" id="risk-total-dd" class="form-input" step="1" min="2" max="50">
            </div>
            <div class="form-group">
              <label class="form-label" for="risk-spread">Max Allowed Spread (%)</label>
              <input type="number" id="risk-spread" class="form-input" step="0.1" min="0.1" max="5">
            </div>
            <div class="form-group">
              <label class="form-label" for="risk-cash-buffer">Minimum Cash Buffer (%)</label>
              <input type="number" id="risk-cash-buffer" class="form-input" step="1" min="0" max="30">
            </div>
            <button type="submit" class="btn-primary" style="margin-top: 16px;" aria-label="Save Risk Limits">
              <span>Save Active Risk Limits</span>
            </button>
          </fieldset>
        </form>
      </div>
    </section>

    <!-- SECONDARY: Engine Diagnostics -->
    <section id="tab-diagnostics" class="tab-panel" data-test="lab-diagnostics" role="tabpanel" aria-labelledby="tab-btn-diagnostics" tabindex="0">
      <div class="journey-header">
        <div>
          <h1 class="journey-title">Engine Self-Diagnostics & System Health</h1>
          <p class="journey-subtitle">Automated invariant checks, double-entry verification, and platform integrity.</p>
        </div>
      </div>
      <div class="card" style="max-width: 800px; margin: 0 auto;">
        <div class="card-title">
          <h2>Self-Check Suite</h2>
          <button type="button" id="btn-refresh-diag" class="btn-secondary" aria-label="Re-run Diagnostics">
            Re-run Diagnostics
          </button>
        </div>
        <div id="diag-container" role="status" aria-live="polite" style="padding: 10px 0;">
          <p style="color:var(--color-text-secondary);">Loading system diagnostics...</p>
        </div>
      </div>

      <!-- Model & Strategy Profitability Audit Card -->
      <div class="card" style="max-width: 800px; margin: 24px auto 0 auto;">
        <div class="card-title">
          <div>
            <h2>Model &amp; Strategy Profitability Audit</h2>
            <p style="margin: 4px 0 0 0; font-size: 13px; color: var(--color-text-secondary);">
              Quantitative economics, label imbalance, NSE statutory friction (0.224%), and survivorship bias verification.
            </p>
          </div>
          <button type="button" id="btn-audit-model-strategy" class="btn-primary" aria-label="Run Model and Strategy Audit">
            Run Profitability Audit
          </button>
        </div>
        <div id="model-strategy-audit-container" role="status" aria-live="polite" style="padding: 10px 0;">
          <p style="color:var(--color-text-secondary);">Click &quot;Run Profitability Audit&quot; to inspect model validity and NSE execution economics...</p>
        </div>
      </div>
    </section>

  </main>

  <footer class="footer" role="contentinfo">
    <div class="container footer-content">
      <span>QuantOS v{__version__} — Institutional Quantitative Trading & Risk Operating System</span>
      <span class="footer-badge">Zero Float Invariant • Read-Only Broker Guard</span>
    </div>
  </footer>

  <div id="toast" role="alert" aria-live="assertive"></div>

  <script src="/static/app.js"></script>
</body>
</html>
"""


def render_standalone_journey_html(journey_id: str) -> str:
    """Renders a standalone HTML view for a specific journey."""
    if journey_id not in VALID_JOURNEY_IDS:
        return render_error_page(404, "Journey Not Found", f"Unknown journey ID '{journey_id}'.")

    renderer_map = {
        JOURNEY_INGESTION_ID: render_ingestion_component,
        JOURNEY_FEATURES_ID: render_features_component,
        JOURNEY_TRAINING_ID: render_training_component,
        JOURNEY_HOLDOUT_ID: render_holdout_component,
        JOURNEY_LEDGER_ID: render_ledger_component,
        JOURNEY_SHADOW_ID: render_shadow_component,
        JOURNEY_PILOT_ID: render_pilot_component,
    }

    component_html = renderer_map[journey_id]()
    nav_tabs = render_nav_tabs(journey_id)

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>QuantOS Journey: {journey_id.capitalize()} — v{__version__}</title>
  <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
  <a href="#main-content" class="skip-link">Skip to main content</a>

  <header class="navbar" role="banner">
    <div class="brand">
      <a href="/" class="brand-logo" aria-label="QuantOS Dashboard Home">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
          <polyline points="22 7 13.5 15.5 8.5 10.5 2 17"></polyline>
          <polyline points="16 7 22 7 22 13"></polyline>
        </svg>
        <span>QuantOS</span>
      </a>
      <span class="brand-badge">v{__version__}</span>
    </div>

    {nav_tabs}

    <div class="nav-controls">
      <div class="status-pill" role="status">
        <span class="status-dot" aria-hidden="true"></span>
        <span id="engine-status">ONLINE</span>
      </div>
      <button class="icon-btn" id="theme-toggle" title="Toggle Theme" aria-label="Toggle Dark/Light Mode">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <circle cx="12" cy="12" r="5"></circle>
          <line x1="12" y1="1" x2="12" y2="3"></line>
          <line x1="12" y1="21" x2="12" y2="23"></line>
        </svg>
      </button>
    </div>
  </header>

  <main class="container" id="main-content" role="main">
    {component_html}
  </main>

  <footer class="footer" role="contentinfo">
    <div class="container footer-content">
      <span>QuantOS v{__version__} — {journey_id.capitalize()} Journey View</span>
      <span class="footer-badge">Zero Float Invariant • Read-Only Broker Guard</span>
    </div>
  </footer>

  <div id="toast" role="alert" aria-live="assertive"></div>
  <script src="/static/app.js"></script>
</body>
</html>
"""


def render_error_page(status_code: int, title: str, message: str) -> str:
    """Renders an accessible semantic error page."""
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Error {status_code}: {title} — QuantOS</title>
  <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
  <div class="container" style="display:flex; align-items:center; justify-content:center; min-height:80vh;">
    <div class="card" style="max-width:540px; text-align:center; padding:40px;" role="alert">
      <div style="font-size:48px; font-weight:800; color:var(--color-danger); margin-bottom:12px;">{status_code}</div>
      <h1 style="font-size:22px; font-weight:700; margin-bottom:12px;">{title}</h1>
      <p style="color:var(--color-text-secondary); margin-bottom:24px;">{message}</p>
      <a href="/" class="btn-primary" style="display:inline-flex; text-decoration:none; width:auto; padding:0 24px;">
        Return to Dashboard
      </a>
    </div>
  </div>
</body>
</html>
"""
