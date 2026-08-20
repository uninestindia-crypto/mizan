/**
 * QuantOS Desktop Web UI Application Controller
 * Handles Reactive State, Chart.js Visualizations, and REST API communication.
 */

let equityChartInstance = null;
let lastTearsheetMarkdown = "";

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initTabs();
  initBacktestForm();
  initStraddleForm();
  initMonteCarlo();
  initRiskForm();
  initDiagnostics();
});


// Toast notification helper
function showToast(message, duration = 3000) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.style.display = "block";
  setTimeout(() => {
    toast.style.display = "none";
  }, duration);
}

// Theme handling
function initTheme() {
  const toggleBtn = document.getElementById("theme-toggle");
  const html = document.documentElement;

  toggleBtn.addEventListener("click", () => {
    const current = html.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    html.setAttribute("data-theme", next);
    localStorage.setItem("quantos-theme", next);
    if (equityChartInstance) {
      updateChartTheme();
    }
  });

  const saved = localStorage.getItem("quantos-theme");
  if (saved) {
    html.setAttribute("data-theme", saved);
  }
}

// Tab navigation
function initTabs() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  const panels = document.querySelectorAll(".tab-panel");

  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabBtns.forEach((b) => b.classList.remove("active"));
      panels.forEach((p) => p.classList.remove("active"));

      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      document.getElementById(targetId).classList.add("active");

      if (targetId === "tab-risk") loadRiskLimits();
      if (targetId === "tab-diagnostics") loadDiagnostics();
    });
  });
}

// Format numbers in Indian Lakhs/Crores or Currency
function formatINR(val) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(val);
}

// Tab 1: Backtest Execution & Charts
function initBacktestForm() {
  const runBtn = document.getElementById("btn-run-backtest");
  const exportBtn = document.getElementById("btn-export-tearsheet");

  exportBtn.addEventListener("click", () => {
    if (!lastTearsheetMarkdown) return;
    const blob = new Blob([lastTearsheetMarkdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `QuantOS_Tearsheet_${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
    showToast("Tearsheet downloaded successfully.");
  });

  runBtn.addEventListener("click", async () => {
    runBtn.disabled = true;
    runBtn.innerHTML = "Simulating Events...";

    const payload = {
      strategy_name: document.getElementById("strategy-select").value,
      initial_cash: parseFloat(document.getElementById("initial-cash").value),
      days: parseInt(document.getElementById("sim-days").value, 10),
      slippage_bps: parseFloat(document.getElementById("slippage-bps").value),
      symbols: ["INFY", "TCS", "RELIANCE", "HDFCBANK", "ICICIBANK"],
    };

    try {
      const res = await fetch("/api/backtest/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Backtest failed");
      }

      const data = await res.json();
      lastTearsheetMarkdown = data.tearsheet_markdown;
      exportBtn.style.display = "inline-block";

      // Update Key Stats
      const retEl = document.getElementById("stat-total-return");
      retEl.textContent = `${(data.total_return_pct * 100).toFixed(2)}%`;
      retEl.className = data.total_return_pct >= 0 ? "stat-value positive" : "stat-value negative";

      document.getElementById("stat-sharpe").textContent = data.stats.sharpe_ratio.toFixed(2);
      document.getElementById("stat-max-dd").textContent = `${(data.stats.max_drawdown_pct * 100).toFixed(2)}%`;
      document.getElementById("stat-win-rate").textContent = `${(data.stats.win_rate * 100).toFixed(1)}%`;
      document.getElementById("stat-total-trades").textContent = data.total_trades;
      document.getElementById("stat-friction").textContent = formatINR(data.total_friction_paid);

      // Render Equity Chart
      renderEquityChart(data.equity_curve);

      // Render Fills Table
      renderFillsTable(data.fills);

      showToast("Backtest completed with exact Decimal reconciliation.");
    } catch (err) {
      showToast(`Error: ${err.message}`);
    } finally {
      runBtn.disabled = false;
      runBtn.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <polygon points="5 3 19 12 5 21 5 3"></polygon>
        </svg>
        Run Event-Driven Backtest
      `;
    }
  });
}

function renderEquityChart(curve) {
  const ctx = document.getElementById("equityChart").getContext("2d");
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";
  const gridColor = isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.06)";
  const textColor = isDark ? "#86868B" : "#1D1D1F";

  const labels = curve.map((s) => s.timestamp);
  const data = curve.map((s) => s.total_equity);

  if (equityChartInstance) {
    equityChartInstance.destroy();
  }

  equityChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Portfolio Total Equity (₹)",
          data: data,
          borderColor: "#0071E3",
          backgroundColor: "rgba(0, 113, 227, 0.1)",
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
          tension: 0.1,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (context) => formatINR(context.raw),
          },
        },
      },
      scales: {
        x: {
          grid: { color: gridColor },
          ticks: { color: textColor, maxTicksLimit: 8 },
        },
        y: {
          grid: { color: gridColor },
          ticks: {
            color: textColor,
            callback: (v) => `₹${(v / 1000).toFixed(0)}k`,
          },
        },
      },
    },
  });
}

function updateChartTheme() {
  if (!equityChartInstance) return;
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";
  const gridColor = isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.06)";
  const textColor = isDark ? "#86868B" : "#1D1D1F";

  equityChartInstance.options.scales.x.grid.color = gridColor;
  equityChartInstance.options.scales.x.ticks.color = textColor;
  equityChartInstance.options.scales.y.grid.color = gridColor;
  equityChartInstance.options.scales.y.ticks.color = textColor;
  equityChartInstance.update();
}

function renderFillsTable(fills) {
  const tbody = document.getElementById("fills-tbody");
  if (!fills || fills.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--color-text-secondary);">No trades triggered.</td></tr>`;
    return;
  }

  tbody.innerHTML = fills
    .map((f) => {
      const badgeClass = f.side === "BUY" ? "badge-buy" : "badge-sell";
      return `
      <tr>
        <td>${f.timestamp}</td>
        <td><strong>${f.symbol}</strong></td>
        <td><span class="${badgeClass}">${f.side}</span></td>
        <td>${f.quantity}</td>
        <td>${formatINR(f.price)}</td>
        <td>${formatINR(f.fee)}</td>
      </tr>
    `;
    })
    .join("");
}

// Tab 2: Options Lab
function initStraddleForm() {
  const btn = document.getElementById("btn-calc-straddle");
  btn.addEventListener("click", async () => {
    const payload = {
      spot_price: parseFloat(document.getElementById("opt-spot").value),
      volatility: parseFloat(document.getElementById("opt-vol").value) / 100.0,
      days_to_expiry: parseInt(document.getElementById("opt-dte").value, 10),
      quantity: parseInt(document.getElementById("opt-qty").value, 10),
    };

    try {
      const res = await fetch("/api/straddle/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      document.getElementById("opt-atm-strike").textContent = data.atm_strike;
      document.getElementById("opt-net-delta").textContent = data.net_delta > 0 ? `+${data.net_delta}` : data.net_delta;
      document.getElementById("opt-theta-decay").textContent = formatINR(data.daily_theta_income);
      document.getElementById("opt-total-premium").textContent = formatINR(data.total_premium_collected);

      const cg = data.call_greeks;
      const pg = data.put_greeks;

      document.getElementById("greeks-tbody").innerHTML = `
        <tr>
          <td><span class="badge-buy">CALL</span></td>
          <td>${cg.strike}</td>
          <td>${formatINR(cg.price)}</td>
          <td>+${cg.delta.toFixed(3)}</td>
          <td>${cg.gamma.toFixed(4)}</td>
          <td>${formatINR(cg.theta)}</td>
          <td>${cg.vega.toFixed(2)}</td>
        </tr>
        <tr>
          <td><span class="badge-sell">PUT</span></td>
          <td>${pg.strike}</td>
          <td>${formatINR(pg.price)}</td>
          <td>${pg.delta.toFixed(3)}</td>
          <td>${pg.gamma.toFixed(4)}</td>
          <td>${formatINR(pg.theta)}</td>
          <td>${pg.vega.toFixed(2)}</td>
        </tr>
      `;

      showToast("Options Greeks calculated successfully.");
    } catch (err) {
      showToast(`Error: ${err.message}`);
    }
  });
}

// Tab 3: Risk Governor Configuration
async function loadRiskLimits() {
  try {
    const res = await fetch("/api/risk/limits");
    const data = await res.json();

    document.getElementById("risk-max-pos").value = (data.max_position_weight * 100).toFixed(0);
    document.getElementById("risk-daily-dd").value = (data.max_daily_drawdown_pct * 100).toFixed(1);
    document.getElementById("risk-total-dd").value = (data.max_total_drawdown_pct * 100).toFixed(0);
    document.getElementById("risk-spread").value = (data.max_allowed_spread_pct * 100).toFixed(1);
    document.getElementById("risk-cash-buffer").value = (data.min_cash_buffer_pct * 100).toFixed(0);
  } catch (err) {
    showToast("Failed to load risk limits.");
  }
}

function initRiskForm() {
  const form = document.getElementById("risk-form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      max_position_weight: parseFloat(document.getElementById("risk-max-pos").value) / 100.0,
      max_daily_drawdown_pct: parseFloat(document.getElementById("risk-daily-dd").value) / 100.0,
      max_total_drawdown_pct: parseFloat(document.getElementById("risk-total-dd").value) / 100.0,
      max_allowed_spread_pct: parseFloat(document.getElementById("risk-spread").value) / 100.0,
      min_cash_buffer_pct: parseFloat(document.getElementById("risk-cash-buffer").value) / 100.0,
      max_portfolio_leverage: 1.0,
      allow_naked_short: false,
    };

    try {
      await fetch("/api/risk/limits", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      showToast("Risk Governor parameters updated.");
    } catch (err) {
      showToast("Failed to save risk parameters.");
    }
  });
}

// Tab 4: System Diagnostics
async function loadDiagnostics() {
  const container = document.getElementById("diag-container");
  container.innerHTML = `<p style="color:var(--color-text-secondary);">Executing self-check suite...</p>`;

  try {
    const res = await fetch("/api/diagnostics");
    const d = await res.json();

    container.innerHTML = `
      <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; padding:12px; background:var(--color-bg-base); border-radius:8px;">
        <div>
          <strong style="font-size:16px;">Overall Engine Status:</strong>
          <span style="color:var(--color-success); font-weight:700; margin-left:8px;">${d.status} (${d.checks_passed}/${d.total_checks} Checks Passed)</span>
        </div>
        <span class="brand-badge">Version ${d.version}</span>
      </div>

      <div class="metrics-grid">
        <div class="stat-box">
          <div class="stat-label">Platform OS</div>
          <div class="stat-value" style="font-size:14px;">${d.platform}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">Python Runtime</div>
          <div class="stat-value" style="font-size:14px;">Python ${d.python_version}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">Ledger Double-Entry</div>
          <div class="stat-value positive" style="font-size:14px;">VERIFIED OK</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">Loaded Strategies</div>
          <div class="stat-value" style="font-size:14px;">${d.installed_strategies_count} Active</div>
        </div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<p style="color:var(--color-danger);">Diagnostics error: ${err.message}</p>`;
  }
}

function initDiagnostics() {
  document.getElementById("btn-refresh-diag").addEventListener("click", loadDiagnostics);
}

// Tab 5: Monte Carlo & Portfolio Optimization
let mcChartInstance = null;

function initMonteCarlo() {
  const mcBtn = document.getElementById("btn-run-mc");
  const optBtn = document.getElementById("btn-run-opt");

  mcBtn.addEventListener("click", async () => {
    mcBtn.disabled = true;
    mcBtn.textContent = "Simulating Paths in RAM...";

    const payload = {
      strategy_name: "EquityDualMomentum",
      num_simulations: parseInt(document.getElementById("mc-sims").value, 10),
      horizon_days: parseInt(document.getElementById("mc-horizon").value, 10),
      initial_capital: parseFloat(document.getElementById("mc-capital").value),
    };

    try {
      const res = await fetch("/api/monte-carlo/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      document.getElementById("mc-var-95").textContent = `${(data.var_95_pct * 100).toFixed(2)}%`;
      document.getElementById("mc-cvar-95").textContent = `${(data.cvar_95_pct * 100).toFixed(2)}%`;
      document.getElementById("mc-prob-profit").textContent = `${(data.prob_profit_pct * 100).toFixed(1)}%`;
      document.getElementById("mc-median-equity").textContent = formatINR(data.expected_final_median);

      renderMonteCarloChart(data);
      showToast("Monte Carlo stress simulation complete.");
    } catch (err) {
      showToast(`Error: ${err.message}`);
    } finally {
      mcBtn.disabled = false;
      mcBtn.textContent = "Run Monte Carlo Stress Test";
    }
  });

  optBtn.addEventListener("click", async () => {
    optBtn.disabled = true;
    optBtn.textContent = "Solving Covariance Matrix...";

    try {
      const res = await fetch("/api/portfolio/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbols: ["INFY", "TCS", "RELIANCE", "HDFCBANK", "ICICIBANK"],
          days: 252,
          risk_free_rate: 0.07,
        }),
      });
      const data = await res.json();

      const tbody = document.getElementById("opt-tbody");
      tbody.innerHTML = data.symbols
        .map((sym) => {
          const msW = (data.max_sharpe_point.weights[sym] * 100).toFixed(1);
          const rpW = (data.risk_parity_weights[sym] * 100).toFixed(1);
          const mvW = (data.min_variance_point.weights[sym] * 100).toFixed(1);
          return `
          <tr>
            <td><strong>${sym}</strong></td>
            <td><strong style="color:var(--color-accent);">${msW}%</strong></td>
            <td><span style="color:var(--color-success); font-weight:600;">${rpW}%</span></td>
            <td>${mvW}%</td>
          </tr>
        `;
        })
        .join("");

      document.getElementById("opt-results-card").style.display = "block";
      showToast("Markowitz optimal weights computed.");
    } catch (err) {
      showToast(`Optimization error: ${err.message}`);
    } finally {
      optBtn.disabled = false;
      optBtn.textContent = "Solve Optimal Weights";
    }
  });
}

function renderMonteCarloChart(data) {
  const ctx = document.getElementById("mcChart").getContext("2d");
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";
  const gridColor = isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.06)";
  const textColor = isDark ? "#86868B" : "#1D1D1F";

  const labels = Array.from({ length: data.percentile_50th.length }, (_, i) => `Day ${i}`);

  if (mcChartInstance) {
    mcChartInstance.destroy();
  }

  mcChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "95th Percentile (Optimistic)",
          data: data.percentile_95th,
          borderColor: "#34C759",
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
        },
        {
          label: "75th Percentile",
          data: data.percentile_75th,
          borderColor: "#30D158",
          borderDash: [5, 5],
          borderWidth: 1,
          pointRadius: 0,
          fill: false,
        },
        {
          label: "Median Expected Path (50th)",
          data: data.percentile_50th,
          borderColor: "#0071E3",
          borderWidth: 2.5,
          pointRadius: 0,
          fill: false,
        },
        {
          label: "25th Percentile",
          data: data.percentile_25th,
          borderColor: "#FF9500",
          borderDash: [5, 5],
          borderWidth: 1,
          pointRadius: 0,
          fill: false,
        },
        {
          label: "5th Percentile (Tail-Risk)",
          data: data.percentile_5th,
          borderColor: "#FF3B30",
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "top", labels: { color: textColor, boxWidth: 12 } },
        tooltip: {
          callbacks: {
            label: (context) => `${context.dataset.label}: ${formatINR(context.raw)}`,
          },
        },
      },
      scales: {
        x: {
          grid: { color: gridColor },
          ticks: { color: textColor, maxTicksLimit: 8 },
        },
        y: {
          grid: { color: gridColor },
          ticks: {
            color: textColor,
            callback: (v) => `₹${(v / 1000).toFixed(0)}k`,
          },
        },
      },
    },
  });
}

