#!/usr/bin/env python3
"""QuantOS Deep Quantitative Audit: The Two Live Mīzān ₹10 Lakh Models.

Performs an unsparing, institutional-grade audit using Claude Opus 5 (Maximum Adaptive Thinking)
on the two active, live-running Mīzān systems in QuantOS:
  Phase 1: Mīzān Flagship Alpha (Intraday Paper Pilot, ₹10 Lakh Book)
           - 15-feature cross-sectional Ridge architecture (Schema v3)
           - Active paper pilot state (logs/paper_runs/portfolio_state.json, live_paper_status.json)
           - Governed empirical trials (trial_mizan_001, trial_mizan_h11_002)
           - Feature IC inversion (8 of 14 features negative IC)
  Phase 2: Mīzān XS-Monthly Momentum (21-Day Paper Watch, ₹10 Lakh Book)
           - 21-day holding horizon, top-20% momentum basket on NIFTY 500
           - Active paper watch state (logs/xs_monthly_new/paper_watch/state.json)
           - 10-year backtest validation across 423 and 499 names (selection edge vs market beta)
           - Depository Participant (DP) fee drag on 99 separate holdings
  Phase 3: Comparative Executive Synthesis & Capital Allocation
           - Direct head-to-head evaluation of both ₹10 Lakh allocations
           - Definitive recommendations on whether to keep, invert, merge, or restructure the books
"""

from __future__ import annotations

import argparse
import http.server
import json
import os
import socketserver
import sys
import threading
import time
from pathlib import Path
from typing import Any

import httpx

# Repository paths
REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "reports" / "mizan_live_audit"
DASHBOARD_PORT = 8093

ANTHROPIC_ENDPOINT = "https://lightning.ai/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-opus-5"

PRICING = {
    "claude-opus-5": {
        "input": 15.00,
        "cache_write": 18.75,
        "cache_read": 1.50,
        "output": 75.00,
    },
}

dashboard_state: dict[str, Any] = {
    "status": "Initializing...",
    "phase": "Starting",
    "active_model": DEFAULT_MODEL,
    "tokens": {
        "input": 0,
        "cache_read": 0,
        "output": 0,
    },
    "cost_usd": 0.0,
    "reports": {
        "mizan_flagship": "",
        "mizan_xs_monthly": "",
        "consensus": "",
    },
    "logs": [],
}


def log_event(msg: str) -> None:
    timestamp = time.strftime("%H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    print(entry)
    dashboard_state["logs"].append(entry)
    if len(dashboard_state["logs"]) > 100:
        dashboard_state["logs"].pop(0)


def load_env_keys() -> str:
    lit_key = os.environ.get("LIGHTNING_API_KEY", "").strip()
    anth_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if ENV_FILE.exists():
        try:
            with open(ENV_FILE, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("LIGHTNING_API_KEY=") and not lit_key:
                        lit_key = line.split("=", 1)[1].strip().strip("\"'")
                    elif line.startswith("ANTHROPIC_API_KEY=") and not anth_key:
                        anth_key = line.split("=", 1)[1].strip().strip("\"'")
        except Exception as e:
            log_event(f"Error reading .env: {e}")
    return lit_key or anth_key


def read_file_safely(path: Path, max_chars: int = 35000) -> str:
    if not path.exists():
        return f"[FILE NOT FOUND: {path}]"
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        if len(content) > max_chars:
            half = max_chars // 2
            return (
                content[:half]
                + f"\n\n... [TRUNCATED {len(content) - max_chars} CHARS FOR CONTEXT EFFICIENCY] ...\n\n"
                + content[-half:]
            )
        return content
    except Exception as e:
        return f"[ERROR READING FILE {path}: {e}]"


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>QuantOS Live Mīzān Dual-Model Audit</title>
<style>
  :root {
    --bg: #090d16;
    --card: #131a29;
    --border: #1e293b;
    --text: #f1f5f9;
    --muted: #94a3b8;
    --accent: #38bdf8;
    --green: #4ade80;
    --purple: #c084fc;
    --red: #f87171;
  }
  body {
    margin: 0; padding: 24px; background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }
  .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 24px; }
  .title { font-size: 20px; font-weight: 700; color: var(--accent); }
  .kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .kpi-card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
  .kpi-label { font-size: 11px; text-transform: uppercase; color: var(--muted); font-weight: 600; letter-spacing: 0.5px; }
  .kpi-value { font-size: 22px; font-weight: 700; margin-top: 6px; font-family: 'JetBrains Mono', monospace; }
  .kpi-sub { font-size: 12px; color: var(--muted); margin-top: 4px; }
  .content-grid { display: grid; grid-template-columns: 1fr; gap: 24px; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 20px; }
  .card-title { font-size: 16px; font-weight: 700; margin-bottom: 12px; display: flex; justify-content: space-between; }
  pre { background: #0b1120; border: 1px solid var(--border); border-radius: 6px; padding: 14px; overflow-x: auto; font-family: 'JetBrains Mono', monospace; font-size: 13px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
  .badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
  .badge-pulse { background: rgba(56, 189, 248, 0.15); color: var(--accent); border: 1px solid var(--accent); }
</style>
</head>
<body>
  <div class="header">
    <div>
      <div class="title">⚡ QuantOS Live Mīzān Dual-Model Audit</div>
      <div style="font-size: 13px; color: var(--muted); margin-top: 4px;">Evaluating the 2 Active ₹10 Lakh Paper Systems with Claude Opus 5 (Maximum Thinking)</div>
    </div>
    <div style="text-align: right;">
      <span class="badge badge-pulse" id="status-badge">Running</span>
      <div style="font-size: 12px; color: var(--muted); margin-top: 4px;" id="active-model-label">Model: claude-opus-5</div>
    </div>
  </div>

  <div class="kpi-row">
    <div class="kpi-card">
      <div class="kpi-label">Current Pipeline Phase</div>
      <div class="kpi-value" style="color: var(--accent);" id="kpi-phase">Initializing...</div>
      <div class="kpi-sub" id="kpi-status">Starting run</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Claude Opus 5 Tokens</div>
      <div class="kpi-value" style="color: var(--green);" id="kpi-tokens">0</div>
      <div class="kpi-sub" id="kpi-tokens-sub">In: 0 | Out: 0</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Accumulated Cost</div>
      <div class="kpi-value" style="color: #fbbf24;" id="kpi-cost">$0.0000</div>
      <div class="kpi-sub">Exact USD dollar cost</div>
    </div>
  </div>

  <div class="content-grid">
    <div class="card">
      <div class="card-title"><span>Console Log Stream</span></div>
      <pre id="log-box" style="max-height: 180px; overflow-y: auto;">Connecting to live state...</pre>
    </div>

    <div class="card">
      <div class="card-title"><span>Live Stream: Phase 1 (Mīzān Flagship Alpha ₹10L Audit)</span></div>
      <pre id="mizan-flagship-box" style="max-height: 400px; overflow-y: auto;">Waiting to start...</pre>
    </div>

    <div class="card">
      <div class="card-title"><span>Live Stream: Phase 2 (Mīzān XS-Monthly Momentum ₹10L Audit)</span></div>
      <pre id="mizan-xs-box" style="max-height: 400px; overflow-y: auto;">Pending Phase 1 completion...</pre>
    </div>

    <div class="card">
      <div class="card-title"><span>Live Stream: Phase 3 (Comparative Executive Synthesis & Action Plan)</span></div>
      <pre id="consensus-box" style="max-height: 400px; overflow-y: auto;">Pending Phase 2 completion...</pre>
    </div>
  </div>

  <script>
    async function updateDashboard() {
      try {
        const res = await fetch('/api/state');
        if (!res.ok) return;
        const data = await res.json();
        document.getElementById('kpi-phase').innerText = data.phase || '--';
        document.getElementById('kpi-status').innerText = data.status || '--';
        document.getElementById('status-badge').innerText = data.phase === 'COMPLETED' ? 'Completed' : 'Running';

        const inTok = data.tokens.input || 0;
        const outTok = data.tokens.output || 0;
        document.getElementById('kpi-tokens').innerText = (inTok + outTok).toLocaleString();
        document.getElementById('kpi-tokens-sub').innerText = `In: ${inTok.toLocaleString()} | Out: ${outTok.toLocaleString()}`;
        document.getElementById('kpi-cost').innerText = `$${(data.cost_usd || 0).toFixed(4)}`;

        if (data.reports.mizan_flagship) {
          document.getElementById('mizan-flagship-box').innerText = data.reports.mizan_flagship;
        }
        if (data.reports.mizan_xs_monthly) {
          document.getElementById('mizan-xs-box').innerText = data.reports.mizan_xs_monthly;
        }
        if (data.reports.consensus) {
          document.getElementById('consensus-box').innerText = data.reports.consensus;
        }
        if (data.logs && data.logs.length) {
          const logBox = document.getElementById('log-box');
          logBox.innerText = data.logs.join('\\n');
          logBox.scrollTop = logBox.scrollHeight;
        }
      } catch (err) {}
    }
    setInterval(updateDashboard, 1000);
    updateDashboard();
  </script>
</body>
</html>
"""


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        pass

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))
        elif self.path == "/api/state":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(dashboard_state).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


def start_dashboard_server() -> None:
    try:
        httpd = socketserver.TCPServer(("0.0.0.0", DASHBOARD_PORT), DashboardHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        log_event(f"Live Mīzān Dashboard running on http://127.0.0.1:{DASHBOARD_PORT}")
    except Exception as e:
        log_event(f"Could not bind dashboard to port {DASHBOARD_PORT}: {e}")


def call_claude_opus(
    client: httpx.Client,
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    phase_key: str,
    max_tokens: int = 32768,
) -> str:
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "anthropic-beta": "prompt-caching-2024-07-31",
        "content-type": "application/json",
    }

    payload: dict[str, Any] = {
        "model": DEFAULT_MODEL,
        "max_tokens": max_tokens,
        "stream": True,
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": "max"},
        "system": [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": [{"role": "user", "content": user_prompt}],
    }

    log_event(f"Streaming from Claude Opus 5 (Adaptive Thinking: max, phase: {phase_key})...")
    start_time = time.time()

    full_text: list[str] = []
    thinking_text: list[str] = []
    in_tok = 0
    out_tok = 0
    cache_read = 0
    cache_write = 0

    with client.stream(
        "POST",
        ANTHROPIC_ENDPOINT,
        headers=headers,
        json=payload,
        timeout=httpx.Timeout(connect=60.0, read=450.0, write=60.0, pool=60.0),
    ) as response:
        if response.status_code != 200:
            err_body = response.read().decode("utf-8", errors="replace")
            err = f"Claude API Error {response.status_code}: {err_body}"
            log_event(err)
            raise RuntimeError(err)

        last_update = time.time()
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            data_str = line[6:].strip()
            if data_str == "[DONE]":
                break
            try:
                event = json.loads(data_str)
                event_type = event.get("type")

                if event_type == "message_start":
                    msg = event.get("message", {})
                    usage = msg.get("usage", {})
                    in_tok = usage.get("input_tokens", 0)
                    cache_read = usage.get("cache_read_input_tokens", 0)
                    cache_write = usage.get("cache_creation_input_tokens", 0)

                elif event_type == "content_block_delta":
                    delta = event.get("delta", {})
                    delta_type = delta.get("type")
                    if delta_type == "thinking_delta":
                        t_chunk = delta.get("thinking", "")
                        thinking_text.append(t_chunk)
                        if time.time() - last_update > 0.8:
                            tot_t = sum(len(x) for x in thinking_text)
                            dashboard_state["status"] = (
                                f"Claude Opus 5 is reasoning deeply... (~{tot_t} chars)"
                            )
                            last_update = time.time()
                    elif delta_type == "text_delta":
                        chunk = delta.get("text", "")
                        full_text.append(chunk)
                        if time.time() - last_update > 0.8:
                            curr_text = "".join(full_text)
                            dashboard_state["reports"][phase_key] = curr_text
                            dashboard_state["status"] = (
                                f"Claude Opus 5 is generating audit report... ({len(curr_text)} chars)"
                            )
                            last_update = time.time()

                elif event_type == "message_delta":
                    usage = event.get("usage", {})
                    out_tok = usage.get("output_tokens", 0)

            except Exception:
                pass

    elapsed = time.time() - start_time
    result_text = "".join(full_text).strip()

    p = PRICING["claude-opus-5"]
    cost = (
        ((in_tok - cache_read) * p["input"] / 1e6)
        + (cache_write * p["cache_write"] / 1e6)
        + (cache_read * p["cache_read"] / 1e6)
        + (out_tok * p["output"] / 1e6)
    )

    dashboard_state["tokens"]["input"] += in_tok
    dashboard_state["tokens"]["cache_read"] += cache_read
    dashboard_state["tokens"]["output"] += out_tok
    dashboard_state["cost_usd"] += cost

    log_event(
        f"Claude Opus 5 finished {phase_key} in {elapsed:.1f}s | In: {in_tok} (Cache: {cache_read}), "
        f"Out: {out_tok} | Cost: +${cost:.4f}"
    )

    dashboard_state["reports"][phase_key] = result_text
    return result_text


# ==============================================================================
# Context Extraction for the 2 Live Mīzān Systems
# ==============================================================================
def get_mizan_flagship_context() -> tuple[str, str]:
    sys_prompt = (
        "You are a Senior Quantitative Portfolio Manager and Execution Specialist auditing Indian equity trading systems (NSE). "
        "Audit 'Mīzān Flagship Alpha' — the live-running intraday/multi-session paper pilot system currently allocated ₹10 Lakh INR. "
        "Deliver an unsparing, mathematically rigorous evaluation of its 15 cross-sectional features, historical negative IC findings, "
        "and its live active portfolio holdings."
    )

    mizan_model_code = read_file_safely(
        REPO_ROOT / "src" / "quant_system" / "modeling" / "mizan_model.py", 14000
    )
    mizan_features_code = read_file_safely(
        REPO_ROOT / "src" / "quant_system" / "modeling" / "mizan_features.py", 12000
    )
    live_status = read_file_safely(
        REPO_ROOT / "logs" / "paper_runs" / "live_paper_status.json", 8000
    )
    portfolio_state = read_file_safely(
        REPO_ROOT / "logs" / "paper_runs" / "portfolio_state.json", 8000
    )
    mizan_history = read_file_safely(
        REPO_ROOT
        / "agent_context"
        / "work"
        / "completed"
        / "20260825-1500Z-claude-mizan-pooled-model.md",
        12000,
    )
    mizan_decision = read_file_safely(
        REPO_ROOT
        / "agent_context"
        / "decisions"
        / "20260826-label-horizon-is-a-declared-parameter.md",
        6000,
    )

    user_prompt = f"""# QuantOS Deep Audit — Phase 1: Mīzān Flagship Alpha (Live ₹10 Lakh Paper Pilot)

Audit the architecture, live portfolio state, and quantitative economics of **System 1: Mīzān Flagship Alpha**.

## 1. Live Operational State of System 1:
- **Allocated Capital**: ₹10,00,000.00 (Rs 10 Lac)
- **Current Book Equity**: ₹9,96,751.26
- **Cash Available**: ₹1,45,520.31
- **Net P&L**: -₹3,248.74 (-0.325%)
- **Active Open Positions**: 50+ stocks across NIFTY 500 (e.g. AADHARHFC, AAVAS, ADANIENT, ADANIGREEN, ADANIPOWER, ANGELONE, CANBK, CENTRALBK, etc.)
- **Execution Engine**: `src/quant_system/execution/paper_pilot.py` driven by `MizanModel`
- **Execution Cadence**: Market hours (09:15–15:30 IST)

## 2. Model Architecture:
- 15 Pooled Cross-Sectional Features (`quantos.mizan_crosssectional_fifteen`):
  `return_1`, `return_5`, `return_21`, `garman_klass_volatility`, `parkinson_volatility`, `rsi_14_centered`,
  `sma_20_distance`, `sma_50_distance`, `volume_zscore`, `money_flow_multiplier`, `india_vix_level`,
  `india_vix_change_5`, `nifty_return_5`, `cs_rank_momentum_5`, `cs_rank_volume_surprise`.

## 3. Historical Governed Campaign Trials:
- **Trial 1 (`trial_mizan_001`, 1-session hold)**:
  Sharpe: -3.2427, Total Return: -41.57%. Across 108,995 governed labels, 45 of 45 symbols had a positive gross mean (+0.076%), but 0 of 45 were net-positive after 0.2225% round-trip statutory costs.
- **Trial 2 (`trial_mizan_h11_002`, 10-session hold)**:
  Sharpe: -0.4108, Total Return: -31.57% (while Buy-and-Hold gained +22.0%!). DSR = 0.1760.
- **Diagnostic IC Finding (`scripts/screen_mizan_feature_ic.py`)**:
  8 of 14 measurable features had |t| > 2, and **every single one of them was NEGATIVE**:
  `return_1` (t = -4.2), `return_5` (t = -3.8), `rsi_14_centered` (t = -2.9), `sma_20_distance` (t = -3.1), etc.

---
## Relevant Code & Data Extracts:
### `mizan_model.py`:
```python
{mizan_model_code}
```
### `mizan_features.py`:
```python
{mizan_features_code}
```
### Live Status (`live_paper_status.json`):
```json
{live_status}
```
### Live Portfolio State (`portfolio_state.json`):
```json
{portfolio_state}
```
### Historical Development Record:
```markdown
{mizan_history}
```
### Decision Context:
```markdown
{mizan_decision}
```

---
## Required Phase 1 Evaluation:
1. **Feature Inversion / Negative Skill**: Why are 8 of the 14 features negatively correlated with forward returns in Indian equities? Does this prove the market is mean-reverting at this horizon while Mīzān bets on continuation?
2. **Evaluation of the Live ₹10L Portfolio**: Critique the 50+ open positions, position sizing (~₹10,000–₹15,000 per stock), and the -₹3,248.74 drawdown.
3. **Friction vs Holding Horizon**: Can Mīzān Flagship Alpha ever achieve profitability on NSE equities in its current format?
4. **Specific Fixes**: Would sign inversion (beta_hat -> -beta_hat), regime gating, or horizon elongation rescue System 1?
"""
    return sys_prompt, user_prompt


def get_mizan_xs_monthly_context() -> tuple[str, str]:
    sys_prompt = (
        "You are a Head of Quantitative Asset Management auditing a systematic equity momentum strategy on the National Stock Exchange of India (NSE). "
        "Audit 'Mīzān XS-Monthly Momentum' — the second live-running system currently allocated ₹10 Lakh INR. "
        "Evaluate its 21-day holding horizon, top-20% momentum selection, 10-year backtest performance, and live 99-leg paper holdings."
    )

    xs_paper_code = read_file_safely(
        REPO_ROOT / "src" / "quant_system" / "research_xs_monthly" / "paper.py", 12000
    )
    xs_ranker_code = read_file_safely(
        REPO_ROOT / "src" / "quant_system" / "research_xs_monthly" / "ranker.py", 10000
    )
    xs_state = read_file_safely(
        REPO_ROOT / "logs" / "xs_monthly_new" / "paper_watch" / "state.json", 12000
    )
    xs_active_record = read_file_safely(
        REPO_ROOT
        / "agent_context"
        / "work"
        / "active"
        / "20260903-hermes-xs-monthly-screen-new.md",
        15000,
    )

    user_prompt = f"""# QuantOS Deep Audit — Phase 2: Mīzān XS-Monthly Momentum (Live ₹10 Lakh Paper Watch)

Audit the quantitative viability, portfolio construction, transaction costs, and live holdings of **System 2: Mīzān XS-Monthly Momentum**.

## 1. Live Operational State of System 2:
- **Allocated Capital**: ₹10,00,000.00 (Rs 10 Lac)
- **Current Book Equity**: ₹10,04,223.88
- **Cash Available**: ₹1,37,184.02
- **Net P&L**: +₹4,223.88 (+0.422%)
- **Active Open Holdings**: **99 active open legs** (equal-weighted top-20% basket across NIFTY 500)
- **Execution Cadence**: Automated daily check at 16:00 IST (Mon–Fri) via `QuantOS-XSMonthly-PaperWatch`
- **Dashboard**: Port 8091 (`http://127.0.0.1:8091`) and Tab 2 on `http://127.0.0.1:8080`

## 2. Strategy Specifications:
- **Formation Horizon**: 21 sessions (trailing 1 month close-to-close return)
- **Holding Horizon**: 21 sessions (monthly rotation)
- **Selection Rule**: Top 20% by momentum score, equal-weighted
- **Friction Model**: 0.224% round-trip statutory costs applied per leg

## 3. Backtest Evidence (from `agent_context/work/active/20260903-hermes-xs-monthly-screen-new.md`):
- **423 Liquid NSE Names (10-Year Decade: 2016–2026, 115 Rebalances)**:
  - Top 20% Momentum Longs: Net Mean +1.74%/period, t = +2.59, Sharpe **+0.84**
  - Market Equal-Weight (Benchmark): Net Mean +1.69%/period, t = +2.58, Sharpe **+0.83**
  - **Selection Edge (Long - Market)**: **+0.00053 (+5.3 bps/period)**
  - Long-Short Diagnostic: Mean net -0.063%/period, t = -0.36, Sharpe -0.12
  - Rank IC: **-0.0096** (t = -0.85, n=115)
- **499 NIFTY 500 Names (3-Year Breadth: 2023–2026, 33 Rebalances)**:
  - Top 20% Momentum Longs: Net Mean +1.50%/period, Sharpe **+0.91**
  - Market Equal-Weight (Benchmark): Net Mean +1.40%/period, Sharpe **+0.89**
  - Selection Edge: **+10 bps/period**
  - Rank IC: **-0.0087**

---
## Relevant Code & Data Extracts:
### `research_xs_monthly/paper.py`:
```python
{xs_paper_code}
```
### `research_xs_monthly/ranker.py`:
```python
{xs_ranker_code}
```
### Live Paper State (`logs/xs_monthly_new/paper_watch/state.json`):
```json
{xs_state}
```
### Hermes Active Research Record:
```markdown
{xs_active_record}
```

---
## Required Phase 2 Evaluation:
1. **The Selection Edge vs Market Beta**: The top-20% basket produced a +0.84 Sharpe, but the unselected market equal-weight produced a +0.83 Sharpe. Is the current +₹4,223.88 live profit genuine stock selection alpha, or simply market beta riding a bull market?
2. **The 99-Leg Friction Penalty on ₹10 Lakh**:
   - In India, selling delivery incurs flat Depository Participant (DP) debit charges of ₹13–20 + GST per scrip per sell.
   - On a ₹10,00,000 capital book with 99 legs, each leg is only ~₹8,700.
   - What does a ₹20 DP fee do to the transaction cost on an ₹8,700 leg? Calculate the true all-in friction rate.
3. **Turnover & Survivorship Bias**: The backtest used active listings only. How much phantom alpha does survivorship bias introduce into a 10-year Indian equity momentum study?
4. **Viability Verdict**: Is System 2 deployable with real money at ₹10 Lakh notional?
"""
    return sys_prompt, user_prompt


def get_comparative_synthesis_context(flagship_rpt: str, xs_rpt: str) -> tuple[str, str]:
    sys_prompt = (
        "You are an Executive Chief Investment Officer. Synthesize your independent quantitative audits of "
        "System 1 (Mīzān Flagship Alpha) and System 2 (Mīzān XS-Monthly Momentum), both running on ₹10 Lakh INR paper books. "
        "Deliver a definitive institutional capital-allocation briefing for the founder."
    )

    user_prompt = f"""# QuantOS Executive Briefing: Comparative Audit of the Two Live Mīzān Systems

Synthesize your evaluations of the two live-running ₹10 Lakh Mīzān systems into an authoritative capital allocation roadmap.

## Audit Findings for System 1 (Mīzān Flagship Alpha):
{flagship_rpt[:5000]}

## Audit Findings for System 2 (Mīzān XS-Monthly Momentum):
{xs_rpt[:5000]}

---
## Required Executive Synthesis:
1. **Head-to-Head Comparison**:
   - Compare System 1 (15-feature ML Ridge, short-term holding, 50+ legs, -₹3,248.74) vs System 2 (21-day momentum rank, 99 legs, +₹4,223.88).
   - Why is System 1 losing while System 2 is winning in the live paper runs?
2. **The True Alpha Reality**:
   - Deconstruct whether System 2's positive return is true alpha or just broad-market beta.
   - Deconstruct whether System 1's negative return is due to feature inversion (buying into reversal).
3. **The Capital Structure Problem of ₹10 Lakh**:
   - Contrast running 50 legs (System 1) vs 99 legs (System 2) on ₹10,00,000 capital under Indian statutory and flat DP debit fees.
   - Why is high diversification on a small notional book a mathematical penalty on NSE?
4. **Definitive Capital Allocation Verdict**:
   - For real money: Should the founder keep System 1, keep System 2, merge them, or halt both?
5. **Top 3 Actionable Engineering & Quantitative Upgrades**:
   - Exactly what changes must be made to these models to achieve scalable, friction-surviving institutional edge in India?
"""
    return sys_prompt, user_prompt


# ==============================================================================
# Main Execution Loop
# ==============================================================================
def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        description="Audit the 2 Live Mīzān ₹10L Systems with Claude Opus 5"
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    api_key = load_env_keys()
    if not api_key:
        print(
            "[!] FATAL: No API key found in .env (expected LIGHTNING_API_KEY or ANTHROPIC_API_KEY)",
            file=sys.stderr,
        )
        return 1

    start_dashboard_server()
    dashboard_state["status"] = "Mīzān Live Audit pipeline started"

    client = httpx.Client(timeout=450.0)

    print("\n" + "=" * 70)
    print(" QuantOS Deep Quantitative Audit: The Two Live Mīzān ₹10 Lakh Models")
    print(f" Model Engine     : {DEFAULT_MODEL} (Adaptive Thinking: max)")
    print(f" API Gateway      : {ANTHROPIC_ENDPOINT}")
    print(f" Live Dashboard   : http://127.0.0.1:{DASHBOARD_PORT}")
    print(f" Reports Output   : {output_dir}")
    print("=" * 70 + "\n")

    # Phase 1: Mīzān Flagship Alpha
    dashboard_state["phase"] = "Phase 1: Mīzān Flagship Alpha (₹10L)"
    dashboard_state["status"] = "Auditing System 1: Mīzān Flagship Alpha..."
    log_event("Starting Phase 1: Mīzān Flagship Alpha (Intraday Paper Pilot, ₹10L)...")

    sys_1, usr_1 = get_mizan_flagship_context()
    mizan_flagship_rpt = call_claude_opus(client, api_key, sys_1, usr_1, phase_key="mizan_flagship")
    (output_dir / "01_mizan_flagship_alpha_audit.md").write_text(
        mizan_flagship_rpt, encoding="utf-8"
    )

    # Phase 2: Mīzān XS-Monthly Momentum
    dashboard_state["phase"] = "Phase 2: Mīzān XS-Monthly Momentum (₹10L)"
    dashboard_state["status"] = "Auditing System 2: Mīzān XS-Monthly Momentum..."
    log_event("Starting Phase 2: Mīzān XS-Monthly Momentum (21-Day Paper Watch, ₹10L)...")

    sys_2, usr_2 = get_mizan_xs_monthly_context()
    mizan_xs_rpt = call_claude_opus(client, api_key, sys_2, usr_2, phase_key="mizan_xs_monthly")
    (output_dir / "02_mizan_xs_monthly_audit.md").write_text(mizan_xs_rpt, encoding="utf-8")

    # Phase 3: Comparative Executive Synthesis
    dashboard_state["phase"] = "Phase 3: Comparative Executive Synthesis"
    dashboard_state["status"] = "Generating Comparative Executive Synthesis..."
    log_event("Starting Phase 3: Comparative Executive Synthesis & Capital Allocation...")

    sys_3, usr_3 = get_comparative_synthesis_context(mizan_flagship_rpt, mizan_xs_rpt)
    consensus_rpt = call_claude_opus(client, api_key, sys_3, usr_3, phase_key="consensus")
    (output_dir / "00_executive_comparison_and_verdict.md").write_text(
        consensus_rpt, encoding="utf-8"
    )

    # Metadata & Cost
    metadata = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": DEFAULT_MODEL,
        "thinking_mode": "adaptive (effort: max)",
        "total_cost_usd": round(dashboard_state["cost_usd"], 4),
        "tokens": dashboard_state["tokens"],
        "reports": [
            "00_executive_comparison_and_verdict.md",
            "01_mizan_flagship_alpha_audit.md",
            "02_mizan_xs_monthly_audit.md",
        ],
    }
    (output_dir / "audit_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    dashboard_state["phase"] = "COMPLETED"
    dashboard_state["status"] = (
        f"Mīzān Audit Completed! Total Cost: ${dashboard_state['cost_usd']:.4f}"
    )
    log_event(
        f"Audit finished successfully! Total accumulated cost: ${dashboard_state['cost_usd']:.4f}"
    )

    print("\n" + "=" * 70)
    print(" Mīzān Live Dual-Model Audit Finished Successfully!")
    print(f" Total Cost Accumulated : ${dashboard_state['cost_usd']:.4f} USD")
    print(f" Total Input Tokens     : {dashboard_state['tokens']['input']:,}")
    print(f" Total Output Tokens    : {dashboard_state['tokens']['output']:,}")
    print(f" Reports Saved to       : {output_dir}")
    print(f" Dashboard Viewable at  : http://127.0.0.1:{DASHBOARD_PORT}")
    print("=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
