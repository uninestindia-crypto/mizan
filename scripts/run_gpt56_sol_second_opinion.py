#!/usr/bin/env python3
"""QuantOS Deep Quantitative Audit: GPT-5.6-Sol Independent Second Opinion.

Sends the Claude Opus 5 executive audit, System 1 and System 2 live book extracts,
feature IC statistics, and friction data to OpenAI's flagship model `gpt-5.6-sol`
with Maximum Thinking (`reasoning_effort: "high"`) for an unsparing second opinion.
"""

from __future__ import annotations

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

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"
OUTPUT_DIR = REPO_ROOT / "reports" / "mizan_live_audit"
DASHBOARD_PORT = 8093

OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
MODEL_NAME = "gpt-5.6-sol"

dashboard_state: dict[str, Any] = {
    "status": "Initializing GPT-5.6-Sol Second Opinion...",
    "phase": "GPT-5.6-Sol Audit",
    "active_model": MODEL_NAME,
    "tokens": {
        "prompt": 0,
        "completion": 0,
        "reasoning": 0,
        "total": 0,
    },
    "cost_usd": 0.0,
    "reports": {
        "claude_verdict": "",
        "gpt56_second_opinion": "",
    },
    "logs": [],
}


def log_event(msg: str) -> None:
    timestamp = time.strftime("%H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    print(entry, flush=True)
    dashboard_state["logs"].append(entry)
    if len(dashboard_state["logs"]) > 100:
        dashboard_state["logs"].pop(0)


def load_openai_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if ENV_FILE.exists():
        try:
            with open(ENV_FILE, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("OPENAI_API_KEY=") and not key:
                        key = line.split("=", 1)[1].strip().strip("\"'")
        except Exception as e:
            log_event(f"Error reading .env: {e}")
    return key


def read_file_safely(path: Path, max_chars: int = 40000) -> str:
    if not path.exists():
        return f"[FILE NOT FOUND: {path}]"
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        if len(content) > max_chars:
            half = max_chars // 2
            return (
                content[:half]
                + f"\n\n... [TRUNCATED {len(content) - max_chars} CHARS] ...\n\n"
                + content[-half:]
            )
        return content
    except Exception as e:
        return f"[ERROR READING FILE {path}: {e}]"


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>QuantOS - GPT-5.6-Sol Second Opinion Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        :root {
            --bg-primary: #090d16;
            --bg-card: #111827;
            --border-color: #1f2937;
            --text-primary: #f9fafb;
            --text-secondary: #9ca3af;
            --accent-green: #10b981;
            --accent-blue: #3b82f6;
            --accent-purple: #8b5cf6;
            --accent-yellow: #f59e0b;
            --accent-red: #ef4444;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            margin: 0;
            padding: 24px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }
        .title {
            font-size: 24px;
            font-weight: 700;
            background: linear-gradient(135deg, #10b981, #3b82f6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .badge {
            background: #1e1b4b;
            color: #a5b4fc;
            padding: 6px 14px;
            border-radius: 9999px;
            font-size: 13px;
            font-weight: 600;
            border: 1px solid #4338ca;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }
        .stat-card {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 16px;
        }
        .stat-label {
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 6px;
        }
        .stat-val {
            font-size: 22px;
            font-weight: 700;
            color: var(--text-primary);
        }
        .main-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        .panel {
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 20px;
            height: calc(100vh - 270px);
            overflow-y: auto;
            box-sizing: border-box;
        }
        .panel h2 {
            font-size: 17px;
            margin-top: 0;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
            display: flex;
            justify-content: space-between;
        }
        .log-box {
            font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
            font-size: 12px;
            color: #94a3b8;
            line-height: 1.5;
            background: #060911;
            padding: 12px;
            border-radius: 8px;
            max-height: 180px;
            overflow-y: auto;
            margin-bottom: 20px;
            border: 1px solid #1e293b;
        }
        .markdown-body {
            font-size: 14px;
            line-height: 1.6;
            color: #cbd5e1;
        }
        .markdown-body table {
            border-collapse: collapse;
            width: 100%;
            margin: 16px 0;
        }
        .markdown-body th, .markdown-body td {
            border: 1px solid #334155;
            padding: 8px 12px;
            text-align: left;
        }
        .markdown-body th {
            background-color: #1e293b;
        }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <div class="title">QuantOS • GPT-5.6-Sol Independent Second Opinion</div>
            <div style="font-size: 13px; color: var(--text-secondary); margin-top: 4px;">
                Mīzān Live Models Audit Peer Review | Maximum Thinking Mode (reasoning_effort: high)
            </div>
        </div>
        <div class="badge" id="status-badge">Processing...</div>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-label">Model Engine</div>
            <div class="stat-val" id="model-name">gpt-5.6-sol</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Thinking Mode</div>
            <div class="stat-val" style="color: var(--accent-purple);">High (Max)</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Stream Progress</div>
            <div class="stat-val" id="stream-chars">0 chars</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Tokens (Prompt / Reason / Total)</div>
            <div class="stat-val" id="token-usage">0 / 0 / 0</div>
        </div>
    </div>

    <div class="log-box" id="log-container">Loading logs...</div>

    <div class="main-container">
        <div class="panel">
            <h2>
                <span>Claude Opus 5 Executive Briefing</span>
                <span style="font-size: 12px; color: #a5b4fc;">Baseline Audit</span>
            </h2>
            <div class="markdown-body" id="claude-content">Loading baseline report...</div>
        </div>
        <div class="panel">
            <h2>
                <span>GPT-5.6-Sol Independent Critique & Verdict</span>
                <span style="font-size: 12px; color: #10b981;">Second Opinion</span>
            </h2>
            <div class="markdown-body" id="gpt56-content">Awaiting streaming output...</div>
        </div>
    </div>

    <script>
        async function updateDashboard() {
            try {
                const res = await fetch('/api/state');
                const data = await res.json();

                document.getElementById('status-badge').innerText = data.phase || data.status;
                document.getElementById('model-name').innerText = data.active_model;

                const gptText = data.reports.gpt56_second_opinion || "";
                document.getElementById('stream-chars').innerText = gptText.length.toLocaleString() + " chars";

                const t = data.tokens;
                document.getElementById('token-usage').innerText = `${t.prompt} / ${t.reasoning} / ${t.total}`;

                const logBox = document.getElementById('log-container');
                logBox.innerHTML = data.logs.join('<br>');
                logBox.scrollTop = logBox.scrollHeight;

                if (data.reports.claude_verdict) {
                    document.getElementById('claude-content').innerHTML = marked.parse(data.reports.claude_verdict);
                }
                if (gptText) {
                    document.getElementById('gpt56-content').innerHTML = marked.parse(gptText);
                }
            } catch (err) {
                console.error("Dashboard poll error:", err);
            }
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
        log_event(f"Live GPT-5.6-Sol Dashboard running on http://127.0.0.1:{DASHBOARD_PORT}")
    except Exception as e:
        log_event(f"Could not bind dashboard to port {DASHBOARD_PORT}: {e}")


def build_audit_prompt() -> tuple[str, str]:
    claude_verdict = read_file_safely(OUTPUT_DIR / "00_executive_comparison_and_verdict.md", 30000)
    claude_xs = read_file_safely(OUTPUT_DIR / "02_mizan_xs_monthly_audit.md", 15000)
    s1_live_state = read_file_safely(
        REPO_ROOT / "logs" / "paper_runs" / "portfolio_state.json", 6000
    )
    s2_live_state = read_file_safely(
        REPO_ROOT / "logs" / "xs_monthly_new" / "paper_watch" / "state.json", 6000
    )
    mizan_ic_screen = read_file_safely(
        REPO_ROOT
        / "agent_context"
        / "work"
        / "completed"
        / "20260825-1500Z-claude-mizan-pooled-model.md",
        10000,
    )

    dashboard_state["reports"]["claude_verdict"] = (
        claude_verdict[:8000] + "\n\n... [TRUNCATED FOR DISPLAY]"
    )

    sys_prompt = (
        "You are an elite Chief Investment Officer and Head of Quantitative Risk at a Tier-1 multi-strategy quantitative fund. "
        "You are conducting an independent peer review and second opinion of an audit conducted by Claude Opus 5 on two live systematic "
        "equity portfolios running on the National Stock Exchange of India (NSE), each allocated ₹10 Lakh INR (₹10,00,000) notional capital."
    )

    user_prompt = f"""# QuantOS Institutional Audit — Independent Second Opinion (GPT-5.6-Sol)

Please provide an unsparing, highly analytical second opinion on the quantitative audit produced by Claude Opus 5 regarding the two live-running Mīzān models in QuantOS.

## Background: The Two Live ₹10 Lakh Portfolios
1. **System 1: Mīzān Flagship Alpha (Paper Pilot)**
   - **Capital**: ₹10,00,000.00
   - **Equity / P&L**: ₹9,96,751.26 (-₹3,248.74 P&L, -0.325%)
   - **Architecture**: 15 cross-sectional features (ROC, RSI, NATR, Bollinger %b, SMA distances 20/50/200, skew, kurtosis, volume trend) fitted with Ridge regression.
   - **Holding Horizon**: Short-term (1–3 sessions).
   - **Holdings**: 50+ open positions across liquid NSE equities.
   - **Empirical Diagnostics**: Feature Information Coefficient (IC) screening showed 8 of 14 features had negative IC (t < -2). In governed trials, 1-session hold returned -41.6% (122% annual friction drag) and 10-session hold returned -31.6% vs Buy & Hold +22%.

2. **System 2: Mīzān XS-Monthly Momentum (Paper Watch)**
   - **Capital**: ₹10,00,000.00
   - **Equity / P&L**: ₹10,04,223.88 (+₹4,223.88 P&L, +0.422%), Cash uninvested ₹1,37,184.02 (13.72% cash drag).
   - **Architecture**: 21-day formation, 21-day holding horizon. Selects top 20% momentum basket across NIFTY 500.
   - **Holdings**: 99 open positions (~₹8,716 average ticket size).
   - **Empirical Diagnostics**: 10-year backtest (115 rebalances) yielded top quintile Sharpe +0.84 vs Market Equal-Weight +0.83 (Selection edge = +5.3 bps/period, t = 0.60; Rank IC = -0.0096; Long-Short net = -0.063%/period).
   - **Friction Context**: Indian delivery equities incur statutory round-trip charges (0.224%) PLUS flat Depository Participant (DP) debit charges of ₹20 + 18% GST (₹23.60) per scrip per sell.

---

## Baseline Audit from Claude Opus 5:
Here is the complete Executive Briefing from Claude Opus 5:
```markdown
{claude_verdict}
```

Here is Claude Opus 5's Deep Audit on System 2:
```markdown
{claude_xs}
```

---

## Technical Context & Live State Extracts:
### System 1 Live State (`portfolio_state.json` extract):
```json
{s1_live_state}
```

### System 2 Live State (`state.json` extract):
```json
{s2_live_state}
```

### Mīzān Feature IC History:
```markdown
{mizan_ic_screen}
```

---

## Required Second Opinion Deliverables:
1. **Critical Review of Claude Opus 5's Findings**:
   - Do you agree or disagree with Claude's verdict that "there is no winner and no loser" and that the ₹7,472 gap is an accounting artifact (gross vs net) + 1-session noise ($p \\approx 0.24$)?
   - Verify Claude's liquidation waterfall for System 2 (turning +₹4,224 into -₹1,245 to -₹3,400). Is Claude's arithmetic accurate?
2. **The Physics of Indian Delivery Trading on ₹10 Lakh**:
   - Claude claims that with 99 legs on ₹10L, the ₹23.60 flat DP fee imposes a 27.1 bps penalty per leg (exceeding STT), and that portfolio cardinality must be capped at ≤ 15–20 names (minimum ticket size ≥ ₹47,200). Do you concur?
   - Claude asserts that weekly turnover on Indian delivery equity is mathematically fatal (25% to 120% p.a. in friction). What is your mathematical assessment of minimum viable holding horizons on NSE?
3. **Deep Diagnostic on System 1's Negative Feature IC**:
   - Why do 8 of 14 features show negative IC in Indian equities? Is this evidence of short-term mean reversion, look-ahead bias in data joins, or Ridge coefficient instability under collinearity?
   - Can System 1 be salvaged by sign-inversion (beta_hat -> -beta_hat) or horizon elongation (>= 21 days)?
4. **Final Second-Opinion Capital Allocation Verdict**:
   - Give your definitive, unequivocal recommendation for the founder's ₹20,00,000 (₹10L each).
   - Should System 2 be halted immediately? Should System 1 receive real capital or stay in research?
   - What is the single most actionable engineering or quantitative upgrade the founder must implement next?
"""
    return sys_prompt, user_prompt


def run_gpt56_audit() -> None:
    api_key = load_openai_key()
    if not api_key:
        log_event("ERROR: OPENAI_API_KEY not found in environment or .env!")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    start_dashboard_server()

    log_event(f"Preparing audit context for {MODEL_NAME}...")
    sys_prompt, user_prompt = build_audit_prompt()

    log_event(f"Connecting to OpenAI API ({MODEL_NAME}, reasoning_effort: high)...")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "reasoning_effort": "high",
        "stream": True,
    }

    full_text: list[str] = []
    start_time = time.time()
    last_update = time.time()

    dashboard_state["phase"] = "Streaming GPT-5.6-Sol Second Opinion..."
    dashboard_state["status"] = "GPT-5.6-Sol is actively reasoning and generating second opinion..."

    with httpx.Client(timeout=600.0) as client:
        with client.stream("POST", OPENAI_ENDPOINT, headers=headers, json=payload) as resp:
            if resp.status_code != 200:
                err_text = resp.read().decode("utf-8", errors="replace")
                log_event(f"OpenAI API Error {resp.status_code}: {err_text}")
                raise RuntimeError(err_text)

            log_event("HTTP 200 OK — Streaming response chunks...")
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    log_event("Stream completed with [DONE]")
                    break
                try:
                    obj = json.loads(data_str)
                    choices = obj.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        chunk = delta.get("content", "")
                        if chunk:
                            full_text.append(chunk)
                            if time.time() - last_update > 0.6:
                                curr = "".join(full_text)
                                dashboard_state["reports"]["gpt56_second_opinion"] = curr
                                dashboard_state["status"] = (
                                    f"GPT-5.6-Sol writing second opinion... ({len(curr):,} chars)"
                                )
                                last_update = time.time()
                    usage = obj.get("usage")
                    if usage:
                        dashboard_state["tokens"]["prompt"] = usage.get("prompt_tokens", 0)
                        dashboard_state["tokens"]["completion"] = usage.get("completion_tokens", 0)
                        dashboard_state["tokens"]["total"] = usage.get("total_tokens", 0)
                        details = usage.get("completion_tokens_details", {})
                        dashboard_state["tokens"]["reasoning"] = details.get("reasoning_tokens", 0)
                except Exception:
                    pass

    elapsed = time.time() - start_time
    result_text = "".join(full_text).strip()

    # Save second opinion report
    out_file = OUTPUT_DIR / "03_gpt_5_6_sol_second_opinion.md"
    out_file.write_text(result_text, encoding="utf-8")
    log_event(f"Saved GPT-5.6-Sol second opinion to {out_file} ({len(result_text):,} chars)")

    # Update metadata
    meta_file = OUTPUT_DIR / "audit_metadata.json"
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            meta["second_opinion"] = {
                "model": MODEL_NAME,
                "reasoning_effort": "high",
                "completed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "elapsed_seconds": round(elapsed, 1),
                "tokens": dashboard_state["tokens"],
                "report_file": "03_gpt_5_6_sol_second_opinion.md",
            }
            meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        except Exception as e:
            log_event(f"Error updating metadata: {e}")

    dashboard_state["phase"] = "COMPLETED"
    dashboard_state["status"] = f"GPT-5.6-Sol Audit Complete in {elapsed:.1f}s!"
    log_event(f"GPT-5.6-Sol Second Opinion completed successfully in {elapsed:.1f}s!")


if __name__ == "__main__":
    try:
        run_gpt56_audit()
    except Exception as e:
        log_event(f"Fatal execution failure: {e}")
        sys.exit(1)
