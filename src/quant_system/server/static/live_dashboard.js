// Live Trading & P&L Monitor. Served from /static so the page runs under the app's
// `script-src 'self'` policy: an inline script, or an inline onclick, is refused by it.
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

const STATUS_URL = "/api/paper-pilot/live-status";
const XS_STATUS_URL = "/api/xs-monthly/status";

// The control endpoints exist only on the supervised dashboard (scripts/serve_live_dashboard.py).
// The desktop app serves this page read-only, so a refused request is reported as it happened
// rather than as the success this page used to announce regardless of the answer.
async function postControl(url, body, label) {
  const msg = document.getElementById("control-message");
  const setMsg = (text, ok) => {
    msg.textContent = text;
    msg.className = "control-message " + (ok ? "text-green" : "text-red");
  };
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    let data = {};
    try { data = await res.json(); } catch (_) { /* a refusal need not carry JSON */ }
    if (res.ok) {
      setMsg(label + ": " + (data.message || "done"), true);
    } else if (res.status === 404 || res.status === 405) {
      setMsg(label + " is not available in this window. Start and halt sessions from the supervised dashboard or the scheduled task.", false);
    } else {
      const reason = (data.error && data.error.message) || data.message || data.detail || ("HTTP " + res.status);
      setMsg(label + " refused: " + reason, false);
    }
  } catch (err) {
    setMsg(label + " failed: " + err, false);
  }
  fetchStatus();
}

// Only the supervised dashboard can start and halt a session. In the desktop app this page is a
// read-only window onto the session the scheduled task runs, so the controls are replaced by a
// plain note instead of buttons that can only fail.
async function configureControls() {
  let available = false;
  try {
    const res = await fetch("/api/control/available");
    available = res.ok && (await res.json()).available === true;
  } catch (_) { /* unreachable counts as unavailable */ }
  if (available) return;
  // `hidden` loses to the panel's own `display: flex`, so hide it with an explicit style.
  document.getElementById("controls-panel").style.display = "none";
  const msg = document.getElementById("control-message");
  msg.textContent = "This window shows the running session. Start and halt sessions from the supervised dashboard or the scheduled task.";
  msg.className = "control-message text-muted";
}

function startAutomatedSession() {
  const capital = document.getElementById("cfg-capital").value || 50000;
  const slippage = document.getElementById("cfg-slippage").value || 5.0;
  const stopTime = document.getElementById("cfg-stop-time").value || "15:30";
  const modelProfile = document.getElementById("cfg-model-profile").value || "sprint_50k";
  const universe = document.getElementById("cfg-universe").value || "NIFTY500";
  const upstoxToken = document.getElementById("cfg-upstox-token").value.trim();
  const stopTimeFormatted = stopTime.length === 5 ? stopTime + ":00" : stopTime;
  return postControl("/api/control/start", {
    capital: parseFloat(capital),
    slippage_bps: parseFloat(slippage),
    end_time_ist: stopTimeFormatted,
    interval_seconds: 10,
    model_profile: modelProfile,
    universe_name: universe,
    upstox_token: upstoxToken || null,
  }, "Start");
}

function stopAutomatedSession() {
  return postControl("/api/control/stop", {}, "Halt");
}

// The header clock is a clock: it ticks every second in Indian Standard Time. The time the prices
// were last marked is shown separately, in the sub-heading.
const istClock = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Kolkata", hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit",
});
function tickClock() {
  document.getElementById("live-time").textContent = istClock.format(new Date()) + " IST";
}

function showNoSession(data) {
  const statusElem = document.getElementById("session-status");
  statusElem.textContent = "NO SESSION";
  statusElem.className = "badge-stopped";
  document.getElementById("session-id").textContent = "Session: none";
  const why = (data && data.status === "ERROR")
    ? "The session status could not be read: " + escapeHtml(data.error || "unknown error")
    : "No live paper session is running. Figures appear here when the scheduled session starts.";
  document.getElementById("header-sub").textContent = why;
}

async function fetchStatus() {
  try {
    const res = await fetch(STATUS_URL);
    if (!res.ok) { showNoSession({ status: "ERROR", error: "HTTP " + res.status }); return; }
    const data = await res.json();
    if (!data || !data.session_id) { showNoSession(data); return; }
    updateDashboard(data);
  } catch (err) {
    showNoSession({ status: "ERROR", error: String(err) });
  }
}

function updateDashboard(data) {
  if (!data || !data.session_id) return;

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
          <td><strong>${escapeHtml(pos.symbol)}</strong></td>
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
          <td>${escapeHtml(f.timestamp_ist)}</td>
          <td><strong>${escapeHtml(f.symbol)}</strong></td>
          <td><span class="badge ${badgeClass}">${escapeHtml(f.side)}</span></td>
          <td class="text-right">${f.quantity}</td>
          <td class="text-right">₹${f.price}</td>
          <td class="text-right">₹${f.fee}</td>
          <td><span class="badge badge-tag">${escapeHtml(String(f.fill_id).split('_').slice(-2).join('_'))}</span></td>
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
          <div style="width: 110px;"><strong>#${escapeHtml(s.rank)} ${escapeHtml(s.symbol)}</strong></div>
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
    const res = await fetch(XS_STATUS_URL);
    if (!res.ok) return;
    const data = await res.json();
    if (data && data.status === "NOT_RUNNING") return;
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
document.querySelectorAll("[data-tab]").forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});
document.getElementById("btn-start").addEventListener("click", startAutomatedSession);
document.getElementById("btn-stop").addEventListener("click", stopAutomatedSession);
configureControls();
tickClock();
setInterval(tickClock, 1000);
fetchStatus();
fetchXsStatus();
setInterval(fetchStatus, 1500);
setInterval(fetchXsStatus, 3000);
