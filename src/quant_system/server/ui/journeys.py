"""Accessible Semantic HTML Component Renderers for the 7 QuantOS Core User Journeys."""

from __future__ import annotations


def render_ingestion_component() -> str:
    """Journey 1: Data Ingestion & Manifest Inspection."""
    return """
    <section id="tab-ingestion" class="tab-panel active" data-test="journey-ingestion" role="tabpanel" aria-labelledby="tab-btn-ingestion" tabindex="0">
      <div class="journey-header">
        <div>
          <h1 class="journey-title">Data Ingestion & Manifest Inspection</h1>
          <p class="journey-subtitle">Point-in-time NSE equity data acquisition, SHA-256 manifest inspection, and data quality provenance.</p>
        </div>
        <span class="badge badge-source" id="ingestion-source-badge">Upstox V3 read-only</span>
      </div>

      <div class="grid-2col">
        <!-- Sidebar: Ingestion Request Form -->
        <aside class="sidebar">
          <div class="card">
            <h2 class="card-title">Acquisition Parameters</h2>
            <form id="form-ingestion" onsubmit="return false;">
              <fieldset class="form-fieldset">
                <legend class="sr-only">Data Ingestion Configuration</legend>

                <div class="form-group">
                  <label class="form-label" for="ingest-symbol">NSE Equity Symbol</label>
                  <select id="ingest-symbol" class="form-select" aria-describedby="ingest-symbol-hint">
                    <option value="NSE_EQ|INE009A01021" data-symbol="INFY" selected>INFY (Infosys Ltd)</option>
                    <option value="NSE_EQ|INE467B01029" data-symbol="TCS">TCS (Tata Consultancy Services)</option>
                    <option value="NSE_EQ|INE002A01018" data-symbol="RELIANCE">RELIANCE (Reliance Industries)</option>
                    <option value="NSE_EQ|INE040A01034" data-symbol="HDFCBANK">HDFCBANK (HDFC Bank Ltd)</option>
                    <option value="NSE_EQ|INE090A01021" data-symbol="ICICIBANK">ICICIBANK (ICICI Bank Ltd)</option>
                  </select>
                  <span id="ingest-symbol-hint" class="form-hint">Governed NSE Cash Market Universe</span>
                </div>

                <div class="form-group">
                  <label class="form-label" for="ingest-start-date">Start Date</label>
                  <input type="date" id="ingest-start-date" class="form-input" value="2020-01-01">
                </div>

                <div class="form-group">
                  <label class="form-label" for="ingest-end-date">End Date</label>
                  <input type="date" id="ingest-end-date" class="form-input" value="2025-01-01">
                </div>

                <div class="form-group">
                  <label class="form-label" for="ingest-source-select">Data provider</label>
                  <select id="ingest-source-select" class="form-select" disabled aria-describedby="ingest-source-hint">
                    <option value="UPSTOX_V3" selected>Upstox V3 API (read-only token)</option>
                  </select>
                  <span id="ingest-source-hint" class="form-hint">Configure the provider token and evidence root on the server.</span>
                </div>

                <button type="button" id="btn-ingest-data" class="btn-primary" aria-label="Acquire Data & Generate Manifest">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="7 10 12 15 17 10"></polyline>
                    <line x1="12" y1="15" x2="12" y2="3"></line>
                  </svg>
                  <span>Acquire dataset</span>
                </button>
              </fieldset>
            </form>
          </div>

          <div class="card">
            <h2 class="card-title">Quality Invariant Gates</h2>
            <ul class="checklist" id="ingestion-quality-checklist" aria-label="Ingestion Quality Gates">
              <li class="check-item" id="chk-zero-lookahead">
                <span class="check-icon" aria-hidden="true">—</span>
                <span>Timestamp alignment checked after acquisition</span>
              </li>
              <li class="check-item" id="chk-monotonic">
                <span class="check-icon" aria-hidden="true">—</span>
                <span>Calendar monotonicity checked after acquisition</span>
              </li>
              <li class="check-item" id="chk-ohlc-sanity">
                <span class="check-icon" aria-hidden="true">—</span>
                <span>OHLC price sanity checked after acquisition</span>
              </li>
              <li class="check-item" id="chk-checksum-match">
                <span class="check-icon" aria-hidden="true">—</span>
                <span>SHA-256 integrity checked on verified readback</span>
              </li>
            </ul>
          </div>
        </aside>

        <!-- Main Panel: Manifest Details & Inspections -->
        <div class="main-panel">
          <!-- Metrics Overview -->
          <div class="metrics-grid" role="region" aria-label="Ingestion Overview Metrics">
            <div class="stat-box">
              <div class="stat-label">Catalog state</div>
              <div class="stat-value" id="stat-manifest-status">Not loaded</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Total Verified Bars</div>
              <div class="stat-value" id="stat-manifest-bars">—</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Verified datasets</div>
              <div class="stat-value" id="stat-manifest-coverage">—</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Latest provenance</div>
              <div class="stat-value" id="stat-manifest-anomalies">—</div>
            </div>
          </div>

          <!-- Manifest Inspection Table -->
          <div class="card">
            <div class="card-title">
              <h2>Immutable Dataset Manifests</h2>
              <button type="button" id="btn-refresh-manifests" class="btn-secondary" aria-label="Refresh Manifests Table">
                Refresh Manifests
              </button>
            </div>
            <div class="table-wrapper">
              <table class="data-table" id="manifests-table" aria-label="Dataset Manifests Table">
                <thead>
                  <tr>
                    <th scope="col">Manifest ID</th>
                    <th scope="col">Symbol</th>
                    <th scope="col">Date Range</th>
                    <th scope="col">Bars</th>
                    <th scope="col">SHA-256 Digest</th>
                    <th scope="col">Provenance</th>
                    <th scope="col">Status</th>
                  </tr>
                </thead>
                <tbody id="manifests-tbody">
                  <tr>
                    <td colspan="7">Reading verified dataset evidence…</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Ingestion Audit Log -->
          <div class="card">
            <h2 class="card-title">Point-in-Time Audit Trail</h2>
            <div class="log-stream" id="ingestion-log-stream" role="log" aria-live="polite">
              <div class="log-entry"><span class="log-info">[Ready]</span> Acquire a dataset to create immutable point-in-time evidence.</div>
            </div>
          </div>
        </div>
      </div>
    </section>
    """


def render_features_component() -> str:
    """Journey 2: Feature Matrix & Label Explorer."""
    return """
    <section id="tab-features" class="tab-panel" data-test="journey-features" role="tabpanel" aria-labelledby="tab-btn-features" tabindex="0">
      <div class="journey-header">
        <div>
          <h1 class="journey-title">Feature Matrix & Label Explorer</h1>
          <p class="journey-subtitle">Point-in-time 6-feature governed schema, decision-time alignment, net friction labels, and embargo purge explorer.</p>
        </div>
        <span class="badge badge-source">Evidence required</span>
      </div>

      <div class="grid-2col">
        <aside class="sidebar">
          <div class="card">
            <h2 class="card-title">Feature Configuration</h2>
            <form id="form-features" onsubmit="return false;">
              <fieldset class="form-fieldset">
                <legend class="sr-only">Feature Matrix Settings</legend>

                <div class="form-group">
                  <label class="form-label" for="feat-symbol">Target Asset</label>
                  <select id="feat-symbol" class="form-select">
                    <option value="INFY" selected>INFY</option>
                    <option value="TCS">TCS</option>
                    <option value="RELIANCE">RELIANCE</option>
                    <option value="HDFCBANK">HDFCBANK</option>
                  </select>
                </div>

                <div class="form-group">
                  <label class="form-label" for="feat-horizon-bars">Label Horizon (Trading Days)</label>
                  <input type="number" id="feat-horizon-bars" class="form-input" value="5" min="1" max="60">
                </div>

                <div class="form-group">
                  <label class="form-label" for="feat-friction-bps">Net Friction Deduction (BPS)</label>
                  <input type="number" id="feat-friction-bps" class="form-input" value="5.0" step="0.5" min="0.0">
                </div>

                <div class="form-group">
                  <label class="form-label" for="feat-embargo-bars">Embargo Buffer (Bars)</label>
                  <input type="number" id="feat-embargo-bars" class="form-input" value="1" min="1" max="10">
                </div>

                <button type="button" id="btn-calc-features" class="btn-primary" aria-label="Extract Features & Compute Labels" disabled aria-describedby="features-adapter-hint">
                  <span>Compute Governed Features</span>
                </button>
                <p class="form-hint" id="features-adapter-hint">
                  Feature computation becomes available after the immutable feature-evidence adapter lands.
                </p>
              </fieldset>
            </form>
          </div>

          <div class="card">
            <h2 class="card-title">Governed 6-Feature Schema</h2>
            <ul class="feature-schema-list" aria-label="Feature Schema">
              <li><code>ret_10d</code>: 10-day log return</li>
              <li><code>vol_20d</code>: 20-day realized volatility</li>
              <li><code>sma_dist_20d</code>: Distance to 20-day SMA</li>
              <li><code>volume_ratio_5d</code>: 5d relative volume</li>
              <li><code>spread_bps</code>: Point-in-time spread</li>
              <li><code>rsi_14d</code>: 14-day relative strength</li>
            </ul>
          </div>
        </aside>

        <div class="main-panel">
          <div class="metrics-grid" role="region" aria-label="Feature Matrix Summary">
            <div class="stat-box">
              <div class="stat-label">Total Matrix Rows</div>
              <div class="stat-value" id="stat-feat-rows">—</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Purged Overlap Rows</div>
              <div class="stat-value" id="stat-feat-purged">—</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Embargoed Bars</div>
              <div class="stat-value" id="stat-feat-embargoed">—</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Feature Variance Sanity</div>
              <div class="stat-value" id="stat-feat-variance">Not evaluated</div>
            </div>
          </div>

          <!-- Feature & Label Table -->
          <div class="card">
            <h2 class="card-title">Verified feature matrix</h2>
            <div class="table-wrapper">
              <table class="data-table" id="features-table" aria-label="Feature Matrix Table">
                <thead>
                  <tr>
                    <th scope="col">Decision Time</th>
                    <th scope="col">Symbol</th>
                    <th scope="col">ret_10d</th>
                    <th scope="col">vol_20d</th>
                    <th scope="col">sma_dist_20d</th>
                    <th scope="col">vol_ratio</th>
                    <th scope="col">spread</th>
                    <th scope="col">Next-Open Net Label</th>
                    <th scope="col">Status</th>
                  </tr>
                </thead>
                <tbody id="features-tbody">
                  <tr>
                    <td colspan="9">No verified feature matrix is available yet. Build one from governed dataset evidence before exploring rows.</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Embargo & Purge Notice -->
          <div class="notice-box info" role="status">
            <strong>Point-in-Time Contract:</strong> Decision is fixed at 15:30 Close. Execution fills strictly at 09:15 Next Open. Overlapping lookaheads are automatically purged.
          </div>
        </div>
      </div>
    </section>
    """


def render_training_component() -> str:
    """Journey 3: Governed Ridge Training & Baseline Comparison."""
    return """
    <section id="tab-training" class="tab-panel" data-test="journey-training" role="tabpanel" aria-labelledby="tab-btn-training" tabindex="0">
      <div class="journey-header">
        <div>
          <h1 class="journey-title">Governed Ridge Training & Baseline Comparison</h1>
          <p class="journey-subtitle">Expanding walk-forward fold fit, train-side standardization, multiplicity tracking, and 4-baseline comparative metrics.</p>
        </div>
        <span class="badge badge-source">Adapter pending</span>
      </div>

      <div class="grid-2col">
        <aside class="sidebar">
          <div class="card">
            <h2 class="card-title">Training Fold Hyperparameters</h2>
            <form id="form-training" onsubmit="return false;">
              <fieldset class="form-fieldset">
                <legend class="sr-only">Ridge Hyperparameters</legend>

                <div class="form-group">
                  <label class="form-label" for="train-l2-penalty">L2 Regularization Penalty (λ)</label>
                  <input type="number" id="train-l2-penalty" class="form-input" value="1.0" step="0.1" min="0.001">
                </div>

                <div class="form-group">
                  <label class="form-label" for="train-score-thresh">Score Decision Threshold</label>
                  <input type="number" id="train-score-thresh" class="form-input" value="0.0" step="0.01">
                </div>

                <div class="form-group">
                  <label class="form-label" for="train-fold-type">Fold Structure</label>
                  <select id="train-fold-type" class="form-select">
                    <option value="EXPANDING_WF" selected>Expanding Walk-Forward (Fold 1)</option>
                  </select>
                </div>

                <button type="button" id="btn-train-ridge" class="btn-primary" aria-label="Fit Governed Ridge Fold" disabled aria-describedby="training-adapter-hint">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                    <polygon points="5 3 19 12 5 21 5 3"></polygon>
                  </svg>
                  <span>Fit Governed Ridge Fold</span>
                </button>
                <p class="form-hint" id="training-adapter-hint">
                  Training becomes available after the feature contract is independently certified.
                </p>
              </fieldset>
            </form>
          </div>

          <div class="card">
            <h2 class="card-title">Multiplicity & Deflation State</h2>
            <div class="multiplicity-card">
              <div class="stat-label">Attempt Multiplicity Ordinal</div>
              <div class="stat-value" id="train-multiplicity-ordinal">—</div>
              <p class="form-hint" style="margin-top:6px;">Shown only after an immutable model trial is recorded.</p>
            </div>
          </div>
        </aside>

        <div class="main-panel">
          <div class="metrics-grid" role="region" aria-label="Candidate Model Metrics">
            <div class="stat-box">
              <div class="stat-label">Candidate Sharpe</div>
              <div class="stat-value" id="stat-train-sharpe">—</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Deflated Sharpe Ratio (DSR)</div>
              <div class="stat-value" id="stat-train-dsr">—</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Max Fold Drawdown</div>
              <div class="stat-value" id="stat-train-max-dd">—</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Research Verdict</div>
              <div class="stat-value" id="stat-train-verdict">Not trained</div>
            </div>
          </div>

          <!-- Baseline Comparison Table -->
          <div class="card">
            <h2 class="card-title">Candidate vs. 4 Governed Baselines</h2>
            <div class="table-wrapper">
              <table class="data-table" id="baselines-table" aria-label="Model and Baselines Comparison Table">
                <thead>
                  <tr>
                    <th scope="col">Model / Strategy</th>
                    <th scope="col">Annual Return</th>
                    <th scope="col">Sharpe</th>
                    <th scope="col">Sortino</th>
                    <th scope="col">Max DD</th>
                    <th scope="col">Accuracy</th>
                    <th scope="col">Profit Factor</th>
                  </tr>
                </thead>
                <tbody id="baselines-tbody">
                  <tr>
                    <td colspan="7">No governed model trial is available. Metrics appear only after the training adapter records immutable evidence.</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Fitted Coefficients Table -->
          <div class="card">
            <h2 class="card-title">Learned Ridge Feature Weights (Train-Side Preprocessed)</h2>
            <div class="table-wrapper">
              <table class="data-table" id="coeffs-table" aria-label="Ridge Model Coefficients Table">
                <thead>
                  <tr>
                    <th scope="col">Feature Name</th>
                    <th scope="col">Standardized Coefficient (β)</th>
                    <th scope="col">Weight Impact</th>
                  </tr>
                </thead>
                <tbody id="coeffs-tbody">
                  <tr><td colspan="3">No learned coefficients are available.</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </section>
    """


def render_holdout_component() -> str:
    """Journey 4: Single-use Holdout & Stress Testing Tearsheet."""
    return """
    <section id="tab-holdout" class="tab-panel" data-test="journey-holdout" role="tabpanel" aria-labelledby="tab-btn-holdout" tabindex="0">
      <div class="journey-header">
        <div>
          <h1 class="journey-title">Single-use Holdout & Stress Testing Tearsheet</h1>
          <p class="journey-subtitle">Strict single-use holdout evaluation gate, tail-risk CVaR analysis, macroeconomic stress scenarios, and model card certification.</p>
        </div>
        <span class="badge badge-holdout" id="holdout-lock-badge">🔒 Not evaluated</span>
      </div>

      <div class="grid-2col">
        <aside class="sidebar">
          <div class="card">
            <h2 class="card-title">Holdout Gate Authority</h2>
            <form id="form-holdout" onsubmit="return false;">
              <fieldset class="form-fieldset">
                <legend class="sr-only">Single-Use Holdout Verification</legend>

                <div class="form-group">
                  <label class="form-label" for="holdout-candidate-id">Candidate ID</label>
                  <input type="text" id="holdout-candidate-id" class="form-input" value="cand_ridge_v1_opt" readonly>
                </div>

                <div class="form-group">
                  <label class="form-label" for="holdout-token">Single-Use Unlock Token</label>
                  <input type="text" id="holdout-token" class="form-input" placeholder="Enter one-time holdout key...">
                </div>

                <div class="form-group checkbox-group">
                  <input type="checkbox" id="holdout-confirm-check">
                  <label for="holdout-confirm-check" class="form-checkbox-label">I acknowledge this holdout dataset can be evaluated exactly once.</label>
                </div>

                <button type="button" id="btn-unlock-holdout" class="btn-primary" style="background-color: var(--color-warning);" aria-label="Unlock Single-Use Holdout & Run Stress Tests" disabled aria-describedby="holdout-adapter-hint">
                  <span>Evaluate Holdout & Stress Suite</span>
                </button>
                <p class="form-hint" id="holdout-adapter-hint">
                  Holdout remains locked until a governed candidate and persisted single-use adapter exist.
                </p>
              </fieldset>
            </form>
          </div>

          <div class="card">
            <h2 class="card-title">Certification Status</h2>
            <div class="cert-status-box">
              <div class="stat-label">Model Promotion Status</div>
              <div class="stat-value" id="holdout-verdict">Not evaluated</div>
              <p class="form-hint" style="margin-top:6px;">No holdout is consumed until a governed adapter records the single-use evaluation.</p>
            </div>
          </div>
        </aside>

        <div class="main-panel">
          <!-- Gate Checks Grid -->
          <div class="card">
            <h2 class="card-title">Mandatory Promotion & Risk Gates</h2>
            <div class="table-wrapper">
              <table class="data-table" id="holdout-gates-table" aria-label="Holdout Gates Table">
                <thead>
                  <tr>
                    <th scope="col">Gate Invariant</th>
                    <th scope="col">Required Limit</th>
                    <th scope="col">Observed Metric</th>
                    <th scope="col">Verdict</th>
                  </tr>
                </thead>
                <tbody id="holdout-gates-tbody">
                  <tr>
                    <td colspan="4">No single-use holdout result is available. No gate has passed or failed.</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Stress Test Scenarios -->
          <div class="card">
            <h2 class="card-title">Macroeconomic & Liquidity Stress Scenarios</h2>
            <div class="table-wrapper">
              <table class="data-table" id="stress-scenarios-table" aria-label="Stress Scenarios Table">
                <thead>
                  <tr>
                    <th scope="col">Stress Scenario</th>
                    <th scope="col">Shock Applied</th>
                    <th scope="col">Simulated Drawdown</th>
                    <th scope="col">Recovery Days</th>
                    <th scope="col">Engine Response</th>
                  </tr>
                </thead>
                <tbody id="stress-scenarios-tbody">
                  <tr>
                    <td colspan="5">No stress evidence is available for this candidate.</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Model Card Export -->
          <div class="card">
            <div class="card-title">
              <h2>Governed Model Card Tearsheet</h2>
              <button type="button" id="btn-export-model-card" class="btn-secondary" aria-label="Download Model Card Tearsheet" disabled aria-describedby="model-card-preview">
                Download Model Card (.MD)
              </button>
            </div>
            <div class="code-preview" id="model-card-preview" tabindex="0" role="region" aria-label="Model Card Markdown Preview">
No governed model card is available. Evaluate a real candidate through the single-use holdout adapter first.
            </div>
          </div>
        </div>
      </div>
    </section>
    """


def render_ledger_component() -> str:
    """Journey 5: Ledger & Backtest P&L Tearsheet."""
    return """
    <section id="tab-ledger" class="tab-panel" data-test="journey-ledger" role="tabpanel" aria-labelledby="tab-btn-ledger" tabindex="0">
      <div class="journey-header">
        <div>
          <h1 class="journey-title">Ledger & Backtest P&L Tearsheet</h1>
          <p class="journey-subtitle">Decimal double-entry accounting reconciliation, zero lookahead backtest execution, and exact transaction friction breakdown.</p>
        </div>
        <span class="badge badge-source">Ready to simulate</span>
      </div>

      <div class="grid-2col">
        <aside class="sidebar">
          <div class="card">
            <h2 class="card-title">Backtest Execution Setup</h2>
            <form id="form-backtest" onsubmit="return false;">
              <fieldset class="form-fieldset">
                <legend class="sr-only">Backtest Configuration</legend>

                <div class="form-group">
                  <label class="form-label" for="strategy-select">Quantitative Strategy</label>
                  <select id="strategy-select" class="form-select">
                    <option value="EquityDualMomentum" selected>Equity Dual Momentum & Trend</option>
                    <option value="DirectionalVerticalSpreads">Directional Vertical Spreads</option>
                    <option value="IntradayATMStraddle">09:20 Intraday Straddle</option>
                  </select>
                </div>

                <div class="form-group">
                  <label class="form-label" for="initial-cash">Initial Capital (INR ₹)</label>
                  <input type="number" id="initial-cash" class="form-input" value="1000000" step="50000" min="10000">
                </div>

                <div class="form-group">
                  <label class="form-label" for="sim-days">Horizon (Trading Days)</label>
                  <input type="number" id="sim-days" class="form-input" value="120" min="30" max="500">
                </div>

                <div class="form-group">
                  <label class="form-label" for="slippage-bps">Simulated Slippage (BPS)</label>
                  <input type="number" id="slippage-bps" class="form-input" value="5.0" step="0.5" min="0">
                </div>

                <button type="button" id="btn-run-backtest" class="btn-primary" aria-label="Run Event-Driven Backtest">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
                    <polygon points="5 3 19 12 5 21 5 3"></polygon>
                  </svg>
                  <span>Run Event-Driven Backtest</span>
                </button>
              </fieldset>
            </form>
          </div>

          <div class="card">
            <h2 class="card-title">Decimal Ledger Invariant</h2>
            <div class="ledger-audit-box">
              <div class="stat-label">Double-Entry Balance Check</div>
              <div class="stat-value" id="ledger-reconcile-badge">Not run</div>
              <p class="form-hint" style="margin-top:6px;">Reconciliation appears after a completed Decimal-ledger backtest.</p>
            </div>
          </div>
        </aside>

        <div class="main-panel">
          <div class="metrics-grid" role="region" aria-label="Backtest Key Performance Stats">
            <div class="stat-box">
              <div class="stat-label">Total Return</div>
              <div class="stat-value" id="stat-total-return">—</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Sharpe Ratio</div>
              <div class="stat-value" id="stat-sharpe">—</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Max Drawdown</div>
              <div class="stat-value" id="stat-max-dd">—</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Win Rate</div>
              <div class="stat-value" id="stat-win-rate">—</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Total Trades</div>
              <div class="stat-value" id="stat-total-trades">—</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Total Friction Paid</div>
              <div class="stat-value" id="stat-friction">—</div>
            </div>
          </div>

          <!-- Mark-to-Market Equity Chart -->
          <div class="card">
            <div class="card-title">
              <h2>Mark-to-Market Equity Curve (₹)</h2>
              <button type="button" id="btn-export-tearsheet" class="btn-secondary" aria-label="Download Backtest Tearsheet">
                Download Tearsheet (.MD)
              </button>
            </div>
            <div class="chart-card">
              <canvas id="equityChart" aria-label="Equity Curve Chart" role="img"></canvas>
            </div>
          </div>

          <!-- Trade Fills Log -->
          <div class="card">
            <h2 class="card-title">Executed Trade Log (Zero Lookahead Next-Open Fills)</h2>
            <div class="table-wrapper">
              <table class="data-table" id="fills-table" aria-label="Executed Fills Table">
                <thead>
                  <tr>
                    <th scope="col">Timestamp</th>
                    <th scope="col">Symbol</th>
                    <th scope="col">Side</th>
                    <th scope="col">Quantity</th>
                    <th scope="col">Fill Price (₹)</th>
                    <th scope="col">Total Friction (₹)</th>
                  </tr>
                </thead>
                <tbody id="fills-tbody">
                  <tr>
                    <td colspan="6">Run a backtest to generate a reconciled fill log.</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </section>
    """


def render_shadow_component() -> str:
    """Journey 6: Real-Time / Replay Shadow Monitor."""
    return """
    <section id="tab-shadow" class="tab-panel" data-test="journey-shadow" role="tabpanel" aria-labelledby="tab-btn-shadow" tabindex="0">
      <div class="journey-header">
        <div>
          <h1 class="journey-title">Real-Time / Replay Shadow Monitor</h1>
          <p class="journey-subtitle">Read-only live quote feed and recorded shadow replay with strictly zero broker order write submissions.</p>
        </div>
        <span class="badge badge-source" id="shadow-mode-badge">No session</span>
      </div>

      <div class="grid-2col">
        <aside class="sidebar">
          <div class="card">
            <h2 class="card-title">Shadow Session Controls</h2>
            <form id="form-shadow" onsubmit="return false;">
              <fieldset class="form-fieldset">
                <legend class="sr-only">Shadow Monitor Settings</legend>

                <div class="form-group">
                  <label class="form-label" for="shadow-feed-mode">Feed Source</label>
                  <select id="shadow-feed-mode" class="form-select">
                    <option value="RECORDED_REPLAY" selected>Recorded Quote Replay Fixture</option>
                    <option value="REAL_TIME_STREAM">Real-Time Upstox Feed (Read-Only)</option>
                  </select>
                </div>

                <div class="form-group">
                  <label class="form-label" for="shadow-symbol">Monitored Instrument</label>
                  <select id="shadow-symbol" class="form-select">
                    <option value="INFY" selected>INFY (Equity)</option>
                    <option value="NIFTY_OPT">NIFTY ATM Straddle</option>
                  </select>
                </div>

                <div class="form-group">
                  <label class="form-label" for="shadow-speed">Replay Speed Multiplier</label>
                  <select id="shadow-speed" class="form-select">
                    <option value="1">1x (Real-Time Pace)</option>
                    <option value="5" selected>5x (Accelerated)</option>
                    <option value="20">20x (Fast Replay)</option>
                  </select>
                </div>

                <div class="button-group">
                  <button type="button" id="btn-start-shadow" class="btn-primary" aria-label="Start Shadow Stream" disabled aria-describedby="shadow-control-hint">
                    <span>Start Shadow Monitor</span>
                  </button>
                  <button type="button" id="btn-pause-shadow" class="btn-secondary" aria-label="Pause Stream" disabled aria-describedby="shadow-control-hint">
                    <span>Pause</span>
                  </button>
                </div>
                <p class="form-hint" id="shadow-control-hint">
                  Configure a persisted read-only shadow session before starting or pausing replay.
                </p>
              </fieldset>
            </form>
          </div>

          <div class="card">
            <h2 class="card-title">Broker Order Safety Guarantee</h2>
            <div class="safety-box">
              <div class="stat-label">Broker Orders Submitted</div>
              <div class="stat-value" id="shadow-broker-orders">0 (broker writes disabled)</div>
              <p class="form-hint" style="margin-top:6px;">Hard architectural invariant: Read-only pipeline has no broker write capabilities.</p>
            </div>
          </div>
        </aside>

        <div class="main-panel">
          <div class="metrics-grid" role="region" aria-label="Shadow Session Stats">
            <div class="stat-box">
              <div class="stat-label">Quotes Processed</div>
              <div class="stat-value" id="stat-shadow-quotes">—</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Shadow Decisions</div>
              <div class="stat-value" id="stat-shadow-decisions">—</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Feed Latency</div>
              <div class="stat-value" id="stat-shadow-latency">—</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Stream Health</div>
              <div class="stat-value" id="stat-shadow-health">Not configured</div>
            </div>
          </div>

          <!-- Live / Replay Tape Table -->
          <div class="card">
            <h2 class="card-title">Real-Time Quote Tape (Read-Only Stream)</h2>
            <div class="table-wrapper">
              <table class="data-table" id="shadow-tape-table" aria-label="Real-Time Quotes Table">
                <thead>
                  <tr>
                    <th scope="col">Timestamp</th>
                    <th scope="col">Symbol</th>
                    <th scope="col">Bid (₹)</th>
                    <th scope="col">Ask (₹)</th>
                    <th scope="col">LTP (₹)</th>
                    <th scope="col">Volume</th>
                    <th scope="col">Latency</th>
                  </tr>
                </thead>
                <tbody id="shadow-tape-tbody">
                  <tr>
                    <td colspan="7">No shadow session is configured. Start requires a persisted read-only session adapter.</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Attributed Shadow Decisions -->
          <div class="card">
            <h2 class="card-title">Shadow Decision Attribution Log</h2>
            <div class="table-wrapper">
              <table class="data-table" id="shadow-decisions-table" aria-label="Attributed Decisions Table">
                <thead>
                  <tr>
                    <th scope="col">Decision Time</th>
                    <th scope="col">Signal</th>
                    <th scope="col">Target Instrument</th>
                    <th scope="col">Attributed Fill Price</th>
                    <th scope="col">Matured P&L</th>
                  </tr>
                </thead>
                <tbody id="shadow-decisions-tbody">
                  <tr>
                    <td colspan="5">No attributed shadow decisions yet.</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </section>
    """


def render_pilot_component() -> str:
    """Journey 7: Paper Pilot Campaign Dashboard."""
    return """
    <section id="tab-pilot" class="tab-panel" data-test="journey-pilot" role="tabpanel" aria-labelledby="tab-btn-pilot" tabindex="0">
      <div class="journey-header">
        <div>
          <h1 class="journey-title">Paper Pilot Campaign Dashboard</h1>
          <p class="journey-subtitle">Quote-driven paper trading pilot with bid/ask depth, adverse slippage simulation, and idempotent campaign ledger.</p>
        </div>
        <span class="badge badge-source">No campaign</span>
      </div>

      <div class="grid-2col">
        <aside class="sidebar">
          <div class="card">
            <h2 class="card-title">Campaign Controls</h2>
            <form id="form-pilot" onsubmit="return false;">
              <fieldset class="form-fieldset">
                <legend class="sr-only">Paper Pilot Settings</legend>

                <div class="form-group">
                  <label class="form-label" for="pilot-campaign-select">Active Campaign</label>
                  <select id="pilot-campaign-select" class="form-select" disabled aria-describedby="pilot-control-hint">
                    <option value="" selected>No campaign configured</option>
                  </select>
                </div>

                <div class="form-group">
                  <label class="form-label" for="pilot-alloc-capital">Allocated Capital (₹)</label>
                  <input type="number" id="pilot-alloc-capital" class="form-input" placeholder="Not configured" step="100000" disabled>
                </div>

                <div class="form-group">
                  <label class="form-label" for="pilot-max-dd-limit">Emergency Drawdown Stop (%)</label>
                  <input type="number" id="pilot-max-dd-limit" class="form-input" placeholder="Not configured" step="0.5" disabled>
                </div>

                <div class="button-group">
                  <button type="button" id="btn-submit-pilot-order" class="btn-primary" aria-label="Place Paper Order" disabled aria-describedby="pilot-control-hint">
                    <span>Place paper order</span>
                  </button>
                  <button type="button" id="btn-halt-campaign" class="btn-danger" aria-label="Halt Campaign" disabled aria-describedby="pilot-control-hint">
                    <span>Halt campaign</span>
                  </button>
                </div>
                <p class="form-hint" id="pilot-control-hint">Configure a persisted paper campaign before placing or halting orders.</p>
              </fieldset>
            </form>
          </div>

          <div class="card">
            <h2 class="card-title">Campaign Risk Health</h2>
            <div class="risk-meter-box">
              <div class="stat-label">Current Drawdown Buffer</div>
              <div class="stat-value" id="pilot-dd-buffer">Not configured</div>
              <p class="form-hint" style="margin-top:6px;">The drawdown buffer appears after campaign evidence is available.</p>
            </div>
          </div>
        </aside>

        <div class="main-panel">
          <div class="metrics-grid" role="region" aria-label="Paper Pilot Performance Metrics">
            <div class="stat-box">
              <div class="stat-label">Campaign Equity</div>
              <div class="stat-value" id="stat-pilot-equity">—</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Unrealized P&L</div>
              <div class="stat-value" id="stat-pilot-unrealized">—</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Realized P&L</div>
              <div class="stat-value" id="stat-pilot-realized">—</div>
            </div>
            <div class="stat-box">
              <div class="stat-label">Active Orders</div>
              <div class="stat-value" id="stat-pilot-orders">—</div>
            </div>
          </div>

          <!-- Active Positions Table -->
          <div class="card">
            <h2 class="card-title">Open Paper Positions</h2>
            <div class="table-wrapper">
              <table class="data-table" id="pilot-positions-table" aria-label="Open Positions Table">
                <thead>
                  <tr>
                    <th scope="col">Symbol</th>
                    <th scope="col">Quantity</th>
                    <th scope="col">Avg Entry (₹)</th>
                    <th scope="col">LTP (₹)</th>
                    <th scope="col">Unrealized P&L (₹)</th>
                    <th scope="col">Portfolio Weight</th>
                  </tr>
                </thead>
                <tbody id="pilot-positions-tbody">
                  <tr>
                    <td colspan="6">No paper campaign is configured. Positions appear only from persisted paper state.</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Simulated Order Ladder -->
          <div class="card">
            <h2 class="card-title">Order Execution Ladder & Depth Matching</h2>
            <div class="table-wrapper">
              <table class="data-table" id="pilot-orders-table" aria-label="Order Ladder Table">
                <thead>
                  <tr>
                    <th scope="col">Order ID</th>
                    <th scope="col">Symbol</th>
                    <th scope="col">Side</th>
                    <th scope="col">Quantity</th>
                    <th scope="col">Limit Price</th>
                    <th scope="col">Filled Price</th>
                    <th scope="col">Status</th>
                  </tr>
                </thead>
                <tbody id="pilot-orders-tbody">
                  <tr>
                    <td colspan="7">No paper orders yet.</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </section>
    """
