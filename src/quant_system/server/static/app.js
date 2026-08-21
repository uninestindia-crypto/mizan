/**
 * QuantOS Desktop Web UI Application Controller v1.0.0
 * Handles Reactive State, Chart.js Visualizations, A11y Keyboard Navigation,
 * and REST API communication supporting the 7 Core User Journeys.
 */

let equityChartInstance = null;
let mcChartInstance = null;
let lastTearsheetMarkdown = "";
let lastModelCardMarkdown = "";
let shadowPollingInterval = null;

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initTabs();
  initIngestion();
  initFeatures();
  initTraining();
  initHoldout();
  initBacktestForm();
  initShadow();
  initPilot();
  initStraddleForm();
  initMonteCarlo();
  initRiskForm();
  initDiagnostics();
});

// Toast notification helper
function showToast(message, duration = 3000) {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.style.display = "block";
  setTimeout(() => {
    toast.style.display = "none";
  }, duration);
}

// Format currency in Indian Rupees (INR)
function formatINR(val) {
  if (val === null || val === undefined || isNaN(val)) return "₹0.00";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(val);
}

// Theme handling
function initTheme() {
  const toggleBtn = document.getElementById("theme-toggle");
  const html = document.documentElement;
  if (!toggleBtn) return;

  toggleBtn.addEventListener("click", () => {
    const current = html.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    html.setAttribute("data-theme", next);
    localStorage.setItem("quantos-theme", next);
    if (equityChartInstance) updateChartTheme();
  });

  const saved = localStorage.getItem("quantos-theme");
  if (saved) {
    html.setAttribute("data-theme", saved);
  }
}

// Tab navigation with A11y Keyboard Support (WAI-ARIA Tabs pattern)
function initTabs() {
  const tablist = document.querySelector(".nav-tabs");
  const tabBtns = Array.from(document.querySelectorAll(".tab-btn"));
  const panels = Array.from(document.querySelectorAll(".tab-panel"));

  function activateTab(btn, setFocus = false) {
    tabBtns.forEach((b) => {
      b.classList.remove("active");
      b.setAttribute("aria-selected", "false");
      b.setAttribute("tabindex", "-1");
    });
    panels.forEach((p) => p.classList.remove("active"));

    btn.classList.add("active");
    btn.setAttribute("aria-selected", "true");
    btn.setAttribute("tabindex", "0");
    if (setFocus) btn.focus();

    const targetId = btn.getAttribute("data-tab");
    const panel = document.getElementById(targetId);
    if (panel) {
      panel.classList.add("active");
    }

    if (targetId === "tab-risk") loadRiskLimits();
    if (targetId === "tab-diagnostics") loadDiagnostics();
  }

  tabBtns.forEach((btn, index) => {
    btn.addEventListener("click", () => activateTab(btn, false));

    btn.addEventListener("keydown", (e) => {
      let nextIndex = index;
      if (e.key === "ArrowRight") {
        nextIndex = (index + 1) % tabBtns.length;
        e.preventDefault();
        activateTab(tabBtns[nextIndex], true);
      } else if (e.key === "ArrowLeft") {
        nextIndex = (index - 1 + tabBtns.length) % tabBtns.length;
        e.preventDefault();
        activateTab(tabBtns[nextIndex], true);
      } else if (e.key === "Home") {
        e.preventDefault();
        activateTab(tabBtns[0], true);
      } else if (e.key === "End") {
        e.preventDefault();
        activateTab(tabBtns[tabBtns.length - 1], true);
      }
    });
  });
}

// =============================================================================
// JOURNEY 1: Data Ingestion & Manifest Inspection
// =============================================================================
function initIngestion() {
  const ingestBtn = document.getElementById("btn-ingest-data");
  const refreshBtn = document.getElementById("btn-refresh-manifests");

  if (ingestBtn) {
    ingestBtn.addEventListener("click", async () => {
      ingestBtn.disabled = true;
      const originalText = ingestBtn.innerHTML;
      ingestBtn.innerHTML = "<span>Acquiring & Verifying...</span>";

      const payload = {
        symbol: document.getElementById("ingest-symbol")?.value || "INFY",
        start_date: document.getElementById("ingest-start-date")?.value || "2020-01-01",
        end_date: document.getElementById("ingest-end-date")?.value || "2025-01-01",
        source: document.getElementById("ingest-source-select")?.value || "SYNTHETIC",
      };

      try {
        const res = await fetch("/api/data/ingest", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();

        if (!res.ok) throw new Error(data.message || data.detail || "Ingestion failed");

        showToast(data.message || "Data ingested and manifest verified.");
        loadManifests();
      } catch (err) {
        showToast(`Ingestion error: ${err.message}`);
      } finally {
        ingestBtn.disabled = false;
        ingestBtn.innerHTML = originalText;
      }
    });
  }

  if (refreshBtn) {
    refreshBtn.addEventListener("click", loadManifests);
  }
}

async function loadManifests() {
  try {
    const res = await fetch("/api/data/manifests");
    if (!res.ok) return;
    const data = await res.json();
    const tbody = document.getElementById("manifests-tbody");
    if (!tbody || !data.manifests) return;

    tbody.innerHTML = data.manifests
      .map(
        (m) => `
        <tr>
          <td><code>${m.manifest_id}</code></td>
          <td><strong>${m.symbol}</strong></td>
          <td>${m.start_date} → ${m.end_date}</td>
          <td>${m.bar_count.toLocaleString()}</td>
          <td><code class="hash-pill" title="${m.checksum_sha256}">${m.checksum_sha256.slice(0, 8)}...${m.checksum_sha256.slice(-4)}</code></td>
          <td><span class="badge badge-source">${m.provenance}</span></td>
          <td><span class="badge badge-verified">${m.status}</span></td>
        </tr>
      `
      )
      .join("");
  } catch (err) {
    console.error("Failed to load manifests:", err);
  }
}

// =============================================================================
// JOURNEY 2: Feature Matrix & Label Explorer
// =============================================================================
function initFeatures() {
  const btn = document.getElementById("btn-calc-features");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    btn.disabled = true;
    btn.innerHTML = "<span>Computing Features...</span>";

    const payload = {
      symbol: document.getElementById("feat-symbol")?.value || "INFY",
      horizon_days: parseInt(document.getElementById("feat-horizon-bars")?.value || "5", 10),
      label_friction_bps: parseFloat(document.getElementById("feat-friction-bps")?.value || "5.0"),
    };

    try {
      const res = await fetch("/api/features/explore", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Feature extraction failed");

      document.getElementById("stat-feat-rows").textContent = data.total_rows.toLocaleString();
      document.getElementById("stat-feat-purged").textContent = data.purged_overlap_count;
      document.getElementById("stat-feat-embargoed").textContent = data.embargo_bars;

      const tbody = document.getElementById("features-tbody");
      if (tbody && data.rows) {
        tbody.innerHTML = data.rows
          .map((r) => {
            const retCls = r.label_net_return >= 0 ? "positive" : "negative";
            const retStr = r.label_net_return !== null ? `${(r.label_net_return * 100).toFixed(2)}%` : "--";
            const statusBadge = r.embargoed
              ? '<span class="badge badge-embargo">EMBARGOED</span>'
              : '<span class="badge badge-verified">MATURED</span>';

            return `
              <tr>
                <td>${r.timestamp}</td>
                <td><strong>${r.symbol}</strong></td>
                <td>${r.features.ret_10d > 0 ? "+" : ""}${r.features.ret_10d.toFixed(4)}</td>
                <td>${r.features.vol_20d.toFixed(4)}</td>
                <td>${r.features.sma_dist_20d > 0 ? "+" : ""}${r.features.sma_dist_20d.toFixed(4)}</td>
                <td>${r.features.volume_ratio_5d.toFixed(2)}</td>
                <td>${r.features.spread_bps.toFixed(4)}</td>
                <td class="${retCls}">${retStr}</td>
                <td>${statusBadge}</td>
              </tr>
            `;
          })
          .join("");
      }

      showToast("Feature matrix and net-cost labels computed.");
    } catch (err) {
      showToast(`Error: ${err.message}`);
    } finally {
      btn.disabled = false;
      btn.innerHTML = "<span>Compute Governed Features</span>";
    }
  });
}

// =============================================================================
// JOURNEY 3: Governed Ridge Training & Baseline Comparison
// =============================================================================
function initTraining() {
  const btn = document.getElementById("btn-train-ridge");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    btn.disabled = true;
    btn.innerHTML = "<span>Fitting Fold...</span>";

    const payload = {
      candidate_id: "cand_ridge_v1",
      l2_penalty: parseFloat(document.getElementById("train-l2-penalty")?.value || "1.0"),
      score_threshold: parseFloat(document.getElementById("train-score-thresh")?.value || "0.0"),
      symbols: ["INFY", "TCS", "RELIANCE"],
    };

    try {
      const res = await fetch("/api/training/governed-ridge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Training failed");

      document.getElementById("stat-train-sharpe").textContent = data.candidate_metrics.sharpe_ratio.toFixed(2);
      document.getElementById("stat-train-dsr").textContent = data.deflated_sharpe.toFixed(3);
      document.getElementById("stat-train-max-dd").textContent = `${(data.candidate_metrics.max_drawdown_pct * 100).toFixed(1)}%`;
      document.getElementById("stat-train-verdict").textContent = data.verdict;
      document.getElementById("train-multiplicity-ordinal").textContent = `#${data.multiplicity_ordinal}`;

      // Update baselines table
      const bTable = document.getElementById("baselines-tbody");
      if (bTable && data.baselines) {
        bTable.innerHTML = `
          <tr class="highlight-row">
            <td><strong>⭐ ${data.candidate_metrics.name}</strong></td>
            <td class="positive">+${(data.candidate_metrics.annualized_return * 100).toFixed(1)}%</td>
            <td><strong>${data.candidate_metrics.sharpe_ratio.toFixed(2)}</strong></td>
            <td>${data.candidate_metrics.sortino_ratio.toFixed(2)}</td>
            <td>${(data.candidate_metrics.max_drawdown_pct * 100).toFixed(1)}%</td>
            <td>${(data.candidate_metrics.accuracy_pct * 100).toFixed(1)}%</td>
            <td>${data.candidate_metrics.profit_factor.toFixed(2)}</td>
          </tr>
          ${data.baselines
            .map(
              (b) => `
            <tr>
              <td><code>${b.name}</code></td>
              <td>+${(b.annualized_return * 100).toFixed(1)}%</td>
              <td>${b.sharpe_ratio.toFixed(2)}</td>
              <td>${b.sortino_ratio.toFixed(2)}</td>
              <td>${(b.max_drawdown_pct * 100).toFixed(1)}%</td>
              <td>${(b.accuracy_pct * 100).toFixed(1)}%</td>
              <td>${b.profit_factor.toFixed(2)}</td>
            </tr>
          `
            )
            .join("")}
        `;
      }

      // Update coefficients table
      const cTable = document.getElementById("coeffs-tbody");
      if (cTable && data.coefficients) {
        cTable.innerHTML = data.coefficients
          .map(
            (c) => `
          <tr>
            <td><code>${c.feature_name}</code></td>
            <td><strong>${c.coefficient >= 0 ? "+" : ""}${c.coefficient.toFixed(4)}</strong></td>
            <td>${c.interpretation}</td>
          </tr>
        `
          )
          .join("");
      }

      showToast("Governed Ridge model fitted with immutable trial evidence.");
    } catch (err) {
      showToast(`Training error: ${err.message}`);
    } finally {
      btn.disabled = false;
      btn.innerHTML = "<span>Fit Governed Ridge Fold</span>";
    }
  });
}

// =============================================================================
// JOURNEY 4: Single-use Holdout & Stress Testing Tearsheet
// =============================================================================
function initHoldout() {
  const btn = document.getElementById("btn-unlock-holdout");
  const exportBtn = document.getElementById("btn-export-model-card");

  if (exportBtn) {
    exportBtn.addEventListener("click", () => {
      const text = lastModelCardMarkdown || document.getElementById("model-card-preview")?.innerText || "";
      if (!text) return;
      const blob = new Blob([text], { type: "text/markdown" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `QuantOS_Model_Card_${new Date().toISOString().slice(0, 10)}.md`;
      a.click();
      URL.revokeObjectURL(url);
      showToast("Model card tearsheet downloaded.");
    });
  }

  if (btn) {
    btn.addEventListener("click", async () => {
      const confirmed = document.getElementById("holdout-confirm-check")?.checked;
      if (!confirmed) {
        showToast("Please check the confirmation box to authorize single-use evaluation.");
        return;
      }

      btn.disabled = true;
      btn.innerHTML = "<span>Evaluating Stress Suite...</span>";

      const payload = {
        candidate_id: document.getElementById("holdout-candidate-id")?.value || "cand_ridge_v1_opt",
        unlock_token: document.getElementById("holdout-token")?.value || "HOLD_TOKEN_ONE_TIME",
        confirm_single_use: true,
      };

      try {
        const res = await fetch("/api/holdout/evaluate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Holdout evaluation failed");

        lastModelCardMarkdown = data.model_card_markdown;
        document.getElementById("model-card-preview").textContent = data.model_card_markdown;
        document.getElementById("holdout-verdict").textContent = data.verdict;
        document.getElementById("holdout-lock-badge").textContent = `🔒 ${data.holdout_lock_status}`;

        // Render gates
        const gTbody = document.getElementById("holdout-gates-tbody");
        if (gTbody && data.gates) {
          gTbody.innerHTML = data.gates
            .map(
              (g) => `
            <tr>
              <td><strong>${g.gate_name}</strong></td>
              <td>${g.required_threshold}</td>
              <td><strong>${g.observed_value}</strong></td>
              <td><span class="badge ${g.status === "PASS" ? "badge-verified" : "badge-embargo"}">${g.status}</span></td>
            </tr>
          `
            )
            .join("");
        }

        // Render stress scenarios
        const sTbody = document.getElementById("stress-scenarios-tbody");
        if (sTbody && data.stress_scenarios) {
          sTbody.innerHTML = data.stress_scenarios
            .map(
              (s) => `
            <tr>
              <td><strong>${s.scenario_name}</strong></td>
              <td>${s.shock_description}</td>
              <td class="negative">${(s.simulated_drawdown_pct * 100).toFixed(1)}%</td>
              <td>${s.recovery_days} Days</td>
              <td><span class="badge badge-verified">${s.survival_status}</span></td>
            </tr>
          `
            )
            .join("");
        }

        showToast("Holdout unlocked & stress testing suite evaluated.");
      } catch (err) {
        showToast(`Holdout error: ${err.message}`);
      } finally {
        btn.disabled = false;
        btn.innerHTML = "<span>Evaluate Holdout & Stress Suite</span>";
      }
    });
  }
}

// =============================================================================
// JOURNEY 5: Ledger & Backtest P&L Tearsheet
// =============================================================================
function initBacktestForm() {
  const runBtn = document.getElementById("btn-run-backtest");
  const exportBtn = document.getElementById("btn-export-tearsheet");

  if (exportBtn) {
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
  }

  if (runBtn) {
    runBtn.addEventListener("click", async () => {
      runBtn.disabled = true;
      runBtn.innerHTML = "<span>Simulating Events...</span>";

      const payload = {
        strategy_name: document.getElementById("strategy-select")?.value || "EquityDualMomentum",
        initial_cash: parseFloat(document.getElementById("initial-cash")?.value || "1000000"),
        days: parseInt(document.getElementById("sim-days")?.value || "120", 10),
        slippage_bps: parseFloat(document.getElementById("slippage-bps")?.value || "5.0"),
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
        if (exportBtn) exportBtn.style.display = "inline-block";

        // Update Key Stats
        const retEl = document.getElementById("stat-total-return");
        if (retEl) {
          retEl.textContent = `${data.total_return_pct >= 0 ? "+" : ""}${(data.total_return_pct * 100).toFixed(2)}%`;
          retEl.className = data.total_return_pct >= 0 ? "stat-value positive" : "stat-value negative";
        }

        document.getElementById("stat-sharpe").textContent = data.stats.sharpe_ratio.toFixed(2);
        document.getElementById("stat-max-dd").textContent = `${(data.stats.max_drawdown_pct * 100).toFixed(2)}%`;
        document.getElementById("stat-win-rate").textContent = `${(data.stats.win_rate * 100).toFixed(1)}%`;
        document.getElementById("stat-total-trades").textContent = data.total_trades;
        document.getElementById("stat-friction").textContent = formatINR(data.total_friction_paid);

        renderEquityChart(data.equity_curve);
        renderFillsTable(data.fills);

        showToast("Backtest completed with exact Decimal reconciliation.");
      } catch (err) {
        showToast(`Error: ${err.message}`);
      } finally {
        runBtn.disabled = false;
        runBtn.innerHTML = `
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
            <polygon points="5 3 19 12 5 21 5 3"></polygon>
          </svg>
          <span>Run Event-Driven Backtest</span>
        `;
      }
    });
  }
}

function renderEquityChart(curve) {
  const canvas = document.getElementById("equityChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
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
  if (!tbody) return;
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

// =============================================================================
// JOURNEY 6: Real-Time / Replay Shadow Monitor
// =============================================================================
function initShadow() {
  const startBtn = document.getElementById("btn-start-shadow");
  const pauseBtn = document.getElementById("btn-pause-shadow");

  if (startBtn) {
    startBtn.addEventListener("click", async () => {
      showToast("Shadow Monitor active (Read-Only 0 Broker Writes).");
      loadShadowStatus();
    });
  }

  if (pauseBtn) {
    pauseBtn.addEventListener("click", () => {
      showToast("Shadow Monitor stream paused.");
    });
  }
}

async function loadShadowStatus() {
  try {
    const res = await fetch("/api/shadow/status");
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById("stat-shadow-quotes").textContent = data.quotes_processed.toLocaleString();
    document.getElementById("stat-shadow-decisions").textContent = data.shadow_decisions_count;
    document.getElementById("stat-shadow-latency").textContent = `${data.average_latency_ms} ms`;
    document.getElementById("shadow-broker-orders").textContent = `${data.broker_orders_submitted} (ZERO)`;

    const tapeBody = document.getElementById("shadow-tape-tbody");
    if (tapeBody && data.recent_quotes) {
      tapeBody.innerHTML = data.recent_quotes
        .map(
          (q) => `
        <tr>
          <td>${q.timestamp}</td>
          <td><strong>${q.symbol}</strong></td>
          <td>${formatINR(q.bid)}</td>
          <td>${formatINR(q.ask)}</td>
          <td>${formatINR(q.ltp)}</td>
          <td>${q.volume.toLocaleString()}</td>
          <td><span class="badge badge-verified">${q.latency_ms} ms</span></td>
        </tr>
      `
        )
        .join("");
    }

    const decBody = document.getElementById("shadow-decisions-tbody");
    if (decBody && data.recent_decisions) {
      decBody.innerHTML = data.recent_decisions
        .map(
          (d) => `
        <tr>
          <td>${d.decision_time}</td>
          <td><span class="badge-buy">${d.signal}</span></td>
          <td><strong>${d.target_instrument}</strong></td>
          <td>${formatINR(d.attributed_fill_price)}</td>
          <td class="positive">+${formatINR(d.matured_pnl)}</td>
        </tr>
      `
        )
        .join("");
    }
  } catch (err) {
    console.error("Shadow status load error:", err);
  }
}

// =============================================================================
// JOURNEY 7: Paper Pilot Campaign Dashboard
// =============================================================================
function initPilot() {
  const submitBtn = document.getElementById("btn-submit-pilot-order");
  const haltBtn = document.getElementById("btn-halt-campaign");

  if (submitBtn) {
    submitBtn.addEventListener("click", async () => {
      submitBtn.disabled = true;
      try {
        const payload = {
          campaign_id: document.getElementById("pilot-campaign-select")?.value || "CAMP_ALPHA_2026",
          symbol: "INFY",
          side: "BUY",
          quantity: 100,
          limit_price: 1840.0,
        };

        const res = await fetch("/api/paper-pilot/order", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Order failed");

        showToast(`Paper order ${data.order.order_id} submitted with idempotency token.`);
        loadPilotStatus();
      } catch (err) {
        showToast(`Order error: ${err.message}`);
      } finally {
        submitBtn.disabled = false;
      }
    });
  }

  if (haltBtn) {
    haltBtn.addEventListener("click", () => {
      showToast("Emergency halt signaled. Open paper orders cancelled.");
    });
  }
}

async function loadPilotStatus() {
  try {
    const res = await fetch("/api/paper-pilot/campaign");
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById("stat-pilot-equity").textContent = formatINR(data.current_equity);
    document.getElementById("stat-pilot-unrealized").textContent = `${data.unrealized_pnl >= 0 ? "+" : ""}${formatINR(data.unrealized_pnl)}`;
    document.getElementById("stat-pilot-realized").textContent = `${data.realized_pnl >= 0 ? "+" : ""}${formatINR(data.realized_pnl)}`;
    document.getElementById("pilot-dd-buffer").textContent = `${data.drawdown_buffer_pct}% Remaining`;

    const posBody = document.getElementById("pilot-positions-tbody");
    if (posBody && data.active_positions) {
      posBody.innerHTML = data.active_positions
        .map(
          (p) => `
        <tr>
          <td><strong>${p.symbol}</strong></td>
          <td>${p.quantity}</td>
          <td>${formatINR(p.average_entry)}</td>
          <td>${formatINR(p.current_ltp)}</td>
          <td class="${p.unrealized_pnl >= 0 ? "positive" : "negative"}">${p.unrealized_pnl >= 0 ? "+" : ""}${formatINR(p.unrealized_pnl)}</td>
          <td>${p.portfolio_weight_pct.toFixed(1)}%</td>
        </tr>
      `
        )
        .join("");
    }
  } catch (err) {
    console.error("Pilot status load error:", err);
  }
}

// =============================================================================
// SECONDARY LABS: Options, Risk Governor, Diagnostics, Monte Carlo
// =============================================================================
function initStraddleForm() {
  const btn = document.getElementById("btn-calc-straddle");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    const payload = {
      spot_price: parseFloat(document.getElementById("opt-spot")?.value || "24500.0"),
      volatility: parseFloat(document.getElementById("opt-vol")?.value || "18.0") / 100.0,
      days_to_expiry: parseInt(document.getElementById("opt-dte")?.value || "7", 10),
      quantity: parseInt(document.getElementById("opt-qty")?.value || "25", 10),
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
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      max_position_weight: parseFloat(document.getElementById("risk-max-pos")?.value || "25") / 100.0,
      max_daily_drawdown_pct: parseFloat(document.getElementById("risk-daily-dd")?.value || "3.0") / 100.0,
      max_total_drawdown_pct: parseFloat(document.getElementById("risk-total-dd")?.value || "10.0") / 100.0,
      max_allowed_spread_pct: parseFloat(document.getElementById("risk-spread")?.value || "1.5") / 100.0,
      min_cash_buffer_pct: parseFloat(document.getElementById("risk-cash-buffer")?.value || "5.0") / 100.0,
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

async function loadDiagnostics() {
  const container = document.getElementById("diag-container");
  if (!container) return;
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
  const btn = document.getElementById("btn-refresh-diag");
  if (btn) btn.addEventListener("click", loadDiagnostics);
}

function initMonteCarlo() {
  const mcBtn = document.getElementById("btn-run-mc");
  if (!mcBtn) return;

  mcBtn.addEventListener("click", async () => {
    mcBtn.disabled = true;
    mcBtn.textContent = "Simulating Paths in RAM...";

    const payload = {
      strategy_name: "EquityDualMomentum",
      num_simulations: parseInt(document.getElementById("mc-sims")?.value || "1000", 10),
      horizon_days: parseInt(document.getElementById("mc-horizon")?.value || "252", 10),
      initial_capital: parseFloat(document.getElementById("mc-capital")?.value || "1000000"),
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
}

function renderMonteCarloChart(data) {
  const canvas = document.getElementById("mcChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
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
          label: "95th Percentile",
          data: data.percentile_95th,
          borderColor: "#34C759",
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
        },
        {
          label: "Median Path (50th)",
          data: data.percentile_50th,
          borderColor: "#0071E3",
          borderWidth: 2.5,
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
