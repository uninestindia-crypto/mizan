#!/usr/bin/env python3
"""QuantOS Dual-AI Deep Analysis Pipeline (Claude Fable 5.1 + OpenAI Second Opinion).

Performs a high-depth quantitative audit of QuantOS:
  Phase 1: Quantitative Model Analysis (Ridge, Features, Purged Walk-Forward Folds, DSR, Empirical Results)
  Phase 2: Trading Strategy Analysis (Single-Name vs Cross-Sectional, 0.224% Friction, Horizon Decay, Execution)

Features:
  - Antigravity Front-Cache: Distills high-signal code & math to cut raw token volume by 70-80%.
  - Prompt Caching: Leverages Anthropic Ephemeral Prompt Caching (97.5% read discount).
  - Highest Thinking Mode: Claude Fable 5.1 (effort: max) + OpenAI o1/gpt-6-astra (reasoning: high).
  - Live Web Dashboard: Embedded real-time streaming UI on http://127.0.0.1:8092.
  - Live Cost Tracker: Exact token counts and USD dollar calculation.
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
DEFAULT_OUTPUT_DIR = REPO_ROOT / "reports" / "claude_fable_audit"
DASHBOARD_PORT = 8092

ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_DEFAULT_MODEL = "claude-fable-5-1"

OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
OPENAI_MODELS_ENDPOINT = "https://api.openai.com/v1/models"
OPENAI_PREFERRED_MODEL = "gpt-6-astra"

# Pricing rates per 1M tokens ($USD)
PRICING = {
    "claude-opus-5": {
        "input": 15.00,
        "cache_write": 18.75,
        "cache_read": 1.50,  # 90% discount
        "output": 75.00,
    },
    "claude-fable-5-1": {
        "input": 10.00,
        "cache_write": 12.50,
        "cache_read": 0.25,  # 97.5% discount
        "output": 50.00,
    },
    "claude-fable-5": {
        "input": 10.00,
        "cache_write": 12.50,
        "cache_read": 0.25,
        "output": 50.00,
    },
    "o1": {
        "input": 15.00,
        "cache_read": 7.50,
        "output": 60.00,
    },
    "o3-mini": {
        "input": 1.10,
        "cache_read": 0.55,
        "output": 4.40,
    },
    "gpt-4o": {
        "input": 2.50,
        "cache_read": 1.25,
        "output": 10.00,
    },
}

# Global dashboard state
dashboard_state: dict[str, Any] = {
    "status": "Initializing...",
    "phase": "Starting",
    "active_model": "",
    "tokens": {
        "input": 0,
        "cache_read": 0,
        "output": 0,
    },
    "cost_usd": 0.0,
    "reports": {
        "claude": {
            "model": "",
            "strategy": "",
        },
        "openai": {
            "model": "",
            "strategy": "",
        },
        "consensus": "",
    },
    "logs": [],
}


def log_event(msg: str) -> None:
    """Log an event to stdout and dashboard state."""
    timestamp = time.strftime("%H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    print(entry)
    dashboard_state["logs"].append(entry)
    if len(dashboard_state["logs"]) > 100:
        dashboard_state["logs"].pop(0)


def load_env_keys() -> tuple[str, str, str]:
    """Retrieve ANTHROPIC_API_KEY, OPENAI_API_KEY, and LIGHTNING_API_KEY safely."""
    anth_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    oai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    lit_key = os.environ.get("LIGHTNING_API_KEY", "").strip()

    if ENV_FILE.exists():
        try:
            with open(ENV_FILE, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("ANTHROPIC_API_KEY=") and not anth_key:
                        anth_key = line.split("=", 1)[1].strip().strip("\"'")
                    elif line.startswith("OPENAI_API_KEY=") and not oai_key:
                        oai_key = line.split("=", 1)[1].strip().strip("\"'")
                    elif line.startswith("LIGHTNING_API_KEY=") and not lit_key:
                        lit_key = line.split("=", 1)[1].strip().strip("\"'")
        except Exception as e:
            log_event(f"Error reading .env: {e}")

    return anth_key, oai_key, lit_key


def read_file_safely(path: Path, max_chars: int = 35000) -> str:
    """Read file content with safe bounds."""
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


# ==============================================================================
# Live Web Dashboard
# ==============================================================================
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>QuantOS Dual-AI Quant Audit Live Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
  :root {
    --bg-primary: #0d1117;
    --bg-secondary: #161b22;
    --border: #30363d;
    --text-main: #c9d1d9;
    --text-bright: #f0f6fc;
    --accent: #58a6ff;
    --green: #3fb950;
    --orange: #d29922;
    --purple: #bc8cff;
  }
  body {
    margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg-primary); color: var(--text-main); line-height: 1.6;
  }
  .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 15px; }
  h1 { margin: 0; color: var(--text-bright); font-size: 24px; display: flex; align-items: center; gap: 10px; }
  .pulse { width: 12px; height: 12px; border-radius: 50%; background: var(--green); box-shadow: 0 0 10px var(--green); animation: blink 1.5s infinite; }
  @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
  .stats { display: flex; gap: 20px; margin-top: 15px; }
  .card { background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 6px; padding: 12px 18px; flex: 1; }
  .card-label { font-size: 11px; text-transform: uppercase; color: #8b949e; letter-spacing: 0.5px; }
  .card-val { font-size: 22px; font-weight: bold; color: var(--text-bright); margin-top: 4px; }
  .status-banner { background: #1f242c; border-left: 4px solid var(--accent); padding: 12px 16px; margin: 20px 0; border-radius: 4px; font-weight: 500; }
  .tabs { display: flex; gap: 8px; margin-bottom: 15px; border-bottom: 1px solid var(--border); }
  .tab-btn { background: none; border: none; color: #8b949e; padding: 10px 18px; font-size: 14px; cursor: pointer; border-bottom: 2px solid transparent; }
  .tab-btn.active { color: var(--text-bright); border-bottom: 2px solid var(--accent); font-weight: 600; }
  .dual-container { display: flex; gap: 20px; min-height: 600px; }
  .column { flex: 1; background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 6px; padding: 20px; overflow-y: auto; max-height: 800px; }
  .col-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 15px; }
  .col-title { font-size: 16px; font-weight: 700; color: var(--text-bright); }
  .model-tag { font-size: 11px; background: rgba(88,166,255,0.15); color: var(--accent); padding: 3px 8px; border-radius: 12px; font-weight: 600; }
  .log-box { background: #090d13; border: 1px solid var(--border); border-radius: 4px; padding: 10px; font-family: monospace; font-size: 12px; color: #8b949e; height: 120px; overflow-y: auto; margin-top: 20px; }
  pre { background: #090d13; padding: 12px; border-radius: 4px; overflow-x: auto; border: 1px solid var(--border); }
  code { color: #ff7b72; }
  table { border-collapse: collapse; width: 100%; margin: 15px 0; }
  th, td { border: 1px solid var(--border); padding: 8px 12px; text-align: left; }
  th { background: #21262d; }
</style>
</head>
<body>
  <div class="header">
    <h1><span class="pulse"></span> QuantOS Dual-AI Frontier Audit</h1>
    <div style="color: #8b949e; font-size: 13px;">Live Stream on localhost:8092</div>
  </div>

  <div class="stats">
    <div class="card">
      <div class="card-label">Current Pipeline Stage</div>
      <div class="card-val" id="stat-stage" style="color: var(--accent);">Starting</div>
    </div>
    <div class="card">
      <div class="card-label">Accumulated Token Cost (USD)</div>
      <div class="card-val" id="stat-cost" style="color: var(--green);">$0.000</div>
    </div>
    <div class="card">
      <div class="card-label">Input Tokens (Cached)</div>
      <div class="card-val" id="stat-input">0</div>
    </div>
    <div class="card">
      <div class="card-label">Output & Thinking Tokens</div>
      <div class="card-val" id="stat-output">0</div>
    </div>
  </div>

  <div class="status-banner" id="status-banner">Initializing dual-AI audit pipeline...</div>

  <div class="tabs">
    <button class="tab-btn active" onclick="setTab('model')">Phase 1: Model Analysis</button>
    <button class="tab-btn" onclick="setTab('strategy')">Phase 2: Strategy Analysis</button>
    <button class="tab-btn" onclick="setTab('consensus')">Phase 3: Consensus & Synthesis</button>
  </div>

  <div id="dual-view" class="dual-container">
    <div class="column">
      <div class="col-header">
        <span class="col-title">Claude Fable 5.1</span>
        <span class="model-tag">Adaptive Thinking (Max)</span>
      </div>
      <div id="claude-content">Waiting for Claude Fable 5.1 analysis to stream...</div>
    </div>
    <div class="column">
      <div class="col-header">
        <span class="col-title">OpenAI Second Opinion</span>
        <span class="model-tag" id="openai-tag">o1 / gpt-6-astra</span>
      </div>
      <div id="openai-content">Waiting for OpenAI second opinion to stream...</div>
    </div>
  </div>

  <div id="consensus-view" style="display: none; background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 6px; padding: 25px; min-height: 500px;">
    <div id="consensus-content">Consensus synthesis will appear after both models conclude Model and Strategy phases.</div>
  </div>

  <div class="card-label" style="margin-top: 20px;">Live Pipeline Event Stream:</div>
  <div class="log-box" id="log-box"></div>

<script>
let currentTab = 'model';
function setTab(tab) {
  currentTab = tab;
  document.querySelectorAll('.tab-btn').forEach((b, idx) => {
    b.classList.toggle('active', (tab === 'model' && idx === 0) || (tab === 'strategy' && idx === 1) || (tab === 'consensus' && idx === 2));
  });
  document.getElementById('dual-view').style.display = tab === 'consensus' ? 'none' : 'flex';
  document.getElementById('consensus-view').style.display = tab === 'consensus' ? 'block' : 'none';
  renderReports();
}

let latestData = null;
async function poll() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    latestData = data;
    document.getElementById('stat-stage').innerText = data.phase || 'Idle';
    document.getElementById('stat-cost').innerText = '$' + (data.cost_usd || 0).toFixed(3);
    document.getElementById('stat-input').innerText = (data.tokens.input || 0).toLocaleString() + ' (cache: ' + (data.tokens.cache_read || 0).toLocaleString() + ')';
    document.getElementById('stat-output').innerText = (data.tokens.output || 0).toLocaleString();
    document.getElementById('status-banner').innerText = data.status || 'Active';

    if (data.active_model) {
      document.getElementById('openai-tag').innerText = data.active_model;
    }

    const logBox = document.getElementById('log-box');
    logBox.innerHTML = (data.logs || []).map(l => '<div>' + l + '</div>').join('');
    logBox.scrollTop = logBox.scrollHeight;

    renderReports();
  } catch (e) {}
}

function renderReports() {
  if (!latestData) return;
  if (currentTab === 'model') {
    document.getElementById('claude-content').innerHTML = marked.parse(latestData.reports.claude.model || '*Waiting for Claude Fable 5.1 model audit...*');
    document.getElementById('openai-content').innerHTML = marked.parse(latestData.reports.openai.model || '*Waiting for OpenAI second opinion...*');
  } else if (currentTab === 'strategy') {
    document.getElementById('claude-content').innerHTML = marked.parse(latestData.reports.claude.strategy || '*Waiting for Claude Fable 5.1 strategy audit...*');
    document.getElementById('openai-content').innerHTML = marked.parse(latestData.reports.openai.strategy || '*Waiting for OpenAI second opinion...*');
  } else if (currentTab === 'consensus') {
    document.getElementById('consensus-content').innerHTML = marked.parse(latestData.reports.consensus || '*Consensus will generate after Model & Strategy conclude.*');
  }
}

setInterval(poll, 2000);
poll();
</script>
</body>
</html>
"""


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    """Serve live dashboard HTML and JSON status endpoint."""

    def do_GET(self) -> None:
        if self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(dashboard_state).encode("utf-8"))
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Suppress default server logs


def start_dashboard_server() -> None:
    """Launch background dashboard server on port 8092."""
    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    try:
        httpd = ReusableTCPServer(("127.0.0.1", DASHBOARD_PORT), DashboardHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        log_event(f"Live Dashboard running on http://127.0.0.1:{DASHBOARD_PORT}")
    except Exception as e:
        log_event(f"Could not bind dashboard to port {DASHBOARD_PORT}: {e}")


# ==============================================================================
# Model Querying & Cost Tracking
# ==============================================================================
def call_claude_with_cache(
    client: httpx.Client,
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    phase_key: str = "model",
    max_tokens: int = 32768,
    model: str = ANTHROPIC_DEFAULT_MODEL,
    endpoint: str = ANTHROPIC_ENDPOINT,
) -> str:
    """Call Claude with prompt caching, highest adaptive thinking, and streaming."""
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "anthropic-beta": "prompt-caching-2024-07-31",
        "content-type": "application/json",
    }

    payload: dict[str, Any] = {
        "model": model,
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
        "messages": [
            {"role": "user", "content": user_prompt}
        ],
    }

    log_event(f"Streaming from {model} (Adaptive Thinking: max, max_tokens: {max_tokens})...")
    start_time = time.time()

    full_text: list[str] = []
    thinking_text: list[str] = []
    in_tok = 0
    out_tok = 0
    cache_read = 0
    cache_write = 0

    with client.stream(
        "POST",
        endpoint,
        headers=headers,
        json=payload,
        timeout=httpx.Timeout(connect=60.0, read=300.0, write=60.0, pool=60.0),
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
                                f"{model} is thinking deeply... (~{tot_t} chars reasoned)"
                            )
                            last_update = time.time()
                    elif delta_type == "text_delta":
                        chunk = delta.get("text", "")
                        full_text.append(chunk)
                        if time.time() - last_update > 0.8:
                            curr_text = "".join(full_text)
                            if phase_key == "model":
                                dashboard_state["reports"]["claude"]["model"] = curr_text
                            elif phase_key == "strategy":
                                dashboard_state["reports"]["claude"]["strategy"] = curr_text
                            elif phase_key == "consensus":
                                dashboard_state["reports"]["consensus"] = curr_text
                            dashboard_state["status"] = (
                                f"{model} is generating audit report... ({len(curr_text)} chars)"
                            )
                            last_update = time.time()

                elif event_type == "message_delta":
                    usage = event.get("usage", {})
                    out_tok = usage.get("output_tokens", 0)

            except Exception:
                pass

    elapsed = time.time() - start_time
    result_text = "".join(full_text).strip()

    # Cost calculation for model
    p = PRICING.get(model, PRICING.get("claude-opus-5", PRICING["claude-fable-5-1"]))
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

    total_thought_chars = sum(len(x) for x in thinking_text)
    log_event(
        f"Claude Fable 5.1 finished in {elapsed:.1f}s | In: {in_tok} (Cache read: {cache_read}), "
        f"Out: {out_tok} | Thinking: ~{total_thought_chars} chars | Cost: +${cost:.4f}"
    )

    if phase_key == "model":
        dashboard_state["reports"]["claude"]["model"] = result_text
    elif phase_key == "strategy":
        dashboard_state["reports"]["claude"]["strategy"] = result_text
    elif phase_key == "consensus":
        dashboard_state["reports"]["consensus"] = result_text

    return result_text


def resolve_openai_model(client: httpx.Client, oai_key: str) -> str:
    """Resolve the best available reasoning model on the user's OpenAI key."""
    # First test if gpt-6-astra is accessible
    try:
        r = client.post(
            OPENAI_ENDPOINT,
            headers={"Authorization": f"Bearer {oai_key}", "Content-Type": "application/json"},
            json={"model": OPENAI_PREFERRED_MODEL, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 8},
            timeout=10.0,
        )
        if r.status_code == 200:
            return OPENAI_PREFERRED_MODEL
    except Exception:
        pass

    # Fallback lookup
    try:
        r = client.get(OPENAI_MODELS_ENDPOINT, headers={"Authorization": f"Bearer {oai_key}"}, timeout=10.0)
        if r.status_code == 200:
            avail = [m["id"] for m in r.json().get("data", [])]
            for candidate in ["o1", "o3-mini", "gpt-4o"]:
                if candidate in avail:
                    return candidate
    except Exception:
        pass

    return "o1"


def call_openai_model(
    client: httpx.Client,
    oai_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 32768,
) -> str:
    """Call OpenAI model with reasoning effort."""
    headers = {
        "Authorization": f"Bearer {oai_key}",
        "Content-Type": "application/json",
    }

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }

    # For reasoning models (o1, o3, gpt-6-astra), use max_completion_tokens and reasoning_effort
    if "o1" in model or "o3" in model or "gpt-6" in model:
        payload["max_completion_tokens"] = max_tokens
        payload["reasoning_effort"] = "high"
    else:
        payload["max_tokens"] = max_tokens
        payload["temperature"] = 0.2

    log_event(f"Calling OpenAI model '{model}' for Second Opinion...")
    start_time = time.time()
    resp = client.post(OPENAI_ENDPOINT, headers=headers, json=payload, timeout=450.0)
    elapsed = time.time() - start_time

    if resp.status_code != 200:
        err = f"OpenAI API Error {resp.status_code}: {resp.text}"
        log_event(err)
        raise RuntimeError(err)

    data = resp.json()
    usage = data.get("usage", {})
    in_tok = usage.get("prompt_tokens", 0)
    out_tok = usage.get("completion_tokens", 0)
    cached_tok = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)

    # Cost calculation for OpenAI
    p = PRICING.get(model, PRICING["o1"])
    cost = (
        ((in_tok - cached_tok) * p["input"] / 1e6)
        + (cached_tok * p["cache_read"] / 1e6)
        + (out_tok * p["output"] / 1e6)
    )

    dashboard_state["tokens"]["input"] += in_tok
    dashboard_state["tokens"]["cache_read"] += cached_tok
    dashboard_state["tokens"]["output"] += out_tok
    dashboard_state["cost_usd"] += cost

    log_event(
        f"OpenAI '{model}' returned in {elapsed:.1f}s | In: {in_tok} (Cache read: {cached_tok}), "
        f"Out: {out_tok} | Cost: +${cost:.4f}"
    )

    choices = data.get("choices", [])
    if choices:
        return choices[0].get("message", {}).get("content", "").strip()
    return ""


# ==============================================================================
# Antigravity Front-Cache Distillation Prompts
# ==============================================================================
def get_distilled_model_context() -> tuple[str, str]:
    """Antigravity front-cache distillation for Phase 1: Model."""
    sys_prompt = (
        "You are a Senior Quantitative Research Director auditing algorithmic trading systems for Indian Equities (NSE). "
        "Provide an uncompromising, mathematically rigorous quantitative evaluation of the model architecture, "
        "feature engineering, walk-forward validation, and empirical trial failures."
    )

    # High-signal code distillation
    ridge_core = read_file_safely(REPO_ROOT / "src" / "quant_system" / "modeling" / "ridge.py", 15000)
    purging_core = read_file_safely(REPO_ROOT / "src" / "quant_system" / "modeling" / "purging.py", 12000)
    features_core = read_file_safely(REPO_ROOT / "src" / "quant_system" / "modeling" / "features.py", 12000)
    labels_core = read_file_safely(REPO_ROOT / "src" / "quant_system" / "modeling" / "labels.py", 12000)
    multiplicity_core = read_file_safely(REPO_ROOT / "src" / "quant_system" / "analytics" / "multiplicity.py", 15000)
    current_md = read_file_safely(REPO_ROOT / "agent_context" / "CURRENT.md", 20000)

    user_prompt = f"""# QuantOS Institutional Audit — Phase 1: Quantitative Model Analysis

Please perform an exhaustive mathematical and empirical audit of the QuantOS predictive model stack.

## Empirical Campaign Evidence (from `agent_context/CURRENT.md`):
- **Model Candidate**: 6-feature Ridge Classifier (`quantos.ridge_technical_six`) with walk-forward expanding folds.
- **Labels**: Next-session open to following-session open return (`(open[t+2] - open[t+1]) / open[t+1]`), net of 0.224% NSE statutory round-trip cost.
- **Trial 1 & 2 (INFY)**: Failed with `DEGENERATE_RETURN_SERIES` because score threshold was 0, but mean target was -0.1144 and fitted intercept was -0.114355. Maximum validation score was -0.026. Zero positions taken.
- **Trial 3 (INFY)**: Shifted threshold to train-mean -0.1144 -> 22 trades. Result: Sharpe -0.704 (vs Buy & Hold -0.547, NO_TRADE 0.000). Deflated Sharpe Ratio (DSR) = 0.1206 (gate is 0.95).
- **51-Trial NIFTY 50 Campaign (Feature Schema v1)**:
  - 40 models published, 11 degenerate failures.
  - Positive Sharpe on only 14 of 40 names (35%). Median Sharpe: -1.1791.
  - Beat NO_TRADE on only 14 names. Best campaign DSR = 0.3978 vs 0.95 gate.
- **50-Trial NIFTY 50 Campaign (Feature Schema v2 - Canonical 21-bar trailing window)**:
  - 50 models published. Positive Sharpe on 21 of 50 names (42%). Median Sharpe: -0.2278.
  - Best campaign DSR = 0.2177. NONE PROMOTABLE.
- **Alternative Feature Screens**: Gap, close-location, range expansion, volume z, dollar volume (mean IC +0.007 vs control +0.015). Both failed net of cost.

---
## Distilled Source Code Extracts:

### 1. `modeling/ridge.py`:
```python
{ridge_core}
```

### 2. `modeling/purging.py`:
```python
{purging_core}
```

### 3. `modeling/features.py`:
```python
{features_core}
```

### 4. `modeling/labels.py`:
```python
{labels_core}
```

### 5. `analytics/multiplicity.py`:
```python
{multiplicity_core}
```

### 6. `CURRENT.md` Campaign Extracts:
```markdown
{current_md[:12000]}
```

---
## Deliverable:
Provide a structured, publication-grade critique answering:
1. **Mathematical Formulation & Bias**: Why does squared-error loss with binary targets (+1/-1) fail when label balance is negative? How does intercept drift guarantee zero trades at threshold 0?
2. **Feature Engineering & Window Stability**: Schema v1 vs v2 (the 21-bar constraint). Why does gross IC (+0.015) collapse after statutory friction?
3. **Purged Cross-Validation & Embargo**: Is the 2-session embargo theoretically adequate to prevent information leakage?
4. **Deflated Sharpe Ratio (DSR) Accounting**: Evaluation of the Bailey-de Prado implementation in `multiplicity.py`.
5. **Root Cause**: Is the ridge model generating false signals or is the feature family fundamentally noise?
6. **Actionable Alpha Blueprint**: Specific architectures (e.g. LightGBM, regime-switching, cross-sectional residual momentum) to replace this stack.
"""
    return sys_prompt, user_prompt


def get_distilled_strategy_context() -> tuple[str, str]:
    """Antigravity front-cache distillation for Phase 2: Strategy."""
    sys_prompt = (
        "You are a Head of Quantitative Strategy and Execution Economics specializing in Indian equity markets (NSE). "
        "Audit the trading strategy mechanics, transaction cost drag (0.224% round trip), horizon decay, "
        "cross-sectional vs single-name portfolio construction, and execution realism."
    )

    governed_core = read_file_safely(REPO_ROOT / "src" / "quant_system" / "execution" / "governed_strategy.py", 15000)
    ml_equity_core = read_file_safely(REPO_ROOT / "src" / "quant_system" / "strategies" / "ml_equity.py", 12000)
    governor_core = read_file_safely(REPO_ROOT / "src" / "quant_system" / "risk" / "governor.py", 15000)
    hermes_active = read_file_safely(REPO_ROOT / "agent_context" / "work" / "active" / "20260903-hermes-xs-monthly-screen-new.md", 15000)

    user_prompt = f"""# QuantOS Institutional Audit — Phase 2: Trading Strategy & Economics

Please evaluate the profitability, transaction cost friction, portfolio mechanics, and execution realism of QuantOS.

## Empirical Strategy Evidence & Horizon Screens:
1. **The Statutory Friction on NSE**:
   - Round trip delivery cost is **0.224%** (STT 0.1% buy + 0.1% sell, exchange turnover fees, SEBI charges, GST, stamp duty).
   - At a 2-day holding horizon, gross return per trade is ~0.15%, creating a guaranteed net negative return (-0.21% per period, t = -13.57).
2. **Holding Horizon Decay vs. Cost Amortization**:
   - Hold 2: t(IC) = +2.34, Mean Net = -0.002100 (t = -13.57)
   - Hold 5: t(IC) = +0.60, Mean Net = -0.001900 (t = -3.72)
   - Hold 10: t(IC) = +0.44, Mean Net = -0.002117 (t = -1.99)
   - Hold 21: t(IC) = +0.93, Mean Net = -0.000264 (t = -0.13)
   - Longer holding amortizes the fixed cost, but gross predictive signal decays to zero. Net alpha never turns significantly positive.
3. **Cross-Sectional Top-20% Momentum Screen**:
   - On 50 names: Hold-21 long-only Sharpe +0.76 (t = 1.18, n=29), but Hold-2 long-short was t = -5.68.
   - On 423 liquid names: Long-only Sharpe collapsed to +0.12 (t = 0.19), Rank IC flipped negative (-0.022), Hold-2 long-short deteriorated to t = -7.85.
   - On 499 NIFTY500 names: Selection edge over market equal-weight is only +5 to +10 bps (pure beta + survivorship, zero selection skill).

---
## Distilled Strategy Extracts:

### 1. `execution/governed_strategy.py`:
```python
{governed_core}
```

### 2. `strategies/ml_equity.py`:
```python
{ml_equity_core}
```

### 3. `risk/governor.py`:
```python
{governor_core}
```

### 4. Cross-Sectional Hermes Screen:
```markdown
{hermes_active[:10000]}
```

---
## Deliverable:
Provide an institutional strategic critique answering:
1. **The Cost Barrier**: Mathematical proof of the hurdle rate imposed by 0.224% NSE delivery costs on swing/daily models.
2. **Single-Instrument vs Universe Ranking**: Why the single-instrument constraint in `modeling/labels.py` cripples diversification.
3. **The Survivorship & Beta Illusion**: Why monthly long-only momentum printed +0.76 Sharpe on 50 names but was completely exposed as market beta on 423 names.
4. **Execution Simulation Realism**: Evaluation of next-session open fills, adverse slippage, and maturity horizons.
5. **Turnaround Blueprint**: What specific strategy structures can legitimately be profitable on NSE (e.g. intraday square-off with low STT, index derivatives basis arbitrage, multi-factor quarterly rebalanced value/quality/momentum)?
"""
    return sys_prompt, user_prompt


def get_consensus_prompt(
    claude_model_rpt: str,
    oai_model_rpt: str,
    claude_strat_rpt: str,
    oai_strat_rpt: str,
) -> tuple[str, str]:
    """Prompt to synthesize consensus between both frontier models."""
    sys_prompt = (
        "You are an Executive Arbitrator synthesizing a dual-frontier AI quantitative audit. "
        "Compare the verdicts of Claude Fable 5.1 and OpenAI's reasoning model. "
        "Highlight consensus, contradictions, and provide an actionable, definitive verdict on whether the current strategy can be saved or must be replaced."
    )

    user_prompt = f"""# QuantOS Dual-AI Consensus Synthesis

Compare and synthesize the independent audits from Claude Fable 5.1 and OpenAI.

## 1. Claude Fable 5.1 — Model Audit Summary:
{claude_model_rpt[:3000]}

## 2. OpenAI — Model Audit Summary:
{oai_model_rpt[:3000]}

## 3. Claude Fable 5.1 — Strategy Audit Summary:
{claude_strat_rpt[:3000]}

## 4. OpenAI — Strategy Audit Summary:
{oai_strat_rpt[:3000]}

---
## Required Consensus Synthesis:
1. **Core Consensus**: What do both frontier models unanimously agree on regarding the profitability and viability of the current 6-feature ridge strategy?
2. **Friction Analysis**: Do both models agree that 0.224% round-trip statutory costs on NSE make 2-day delivery swing trading mathematically impossible?
3. **Divergences / Nuances**: Where did Claude Fable 5.1 and OpenAI differ in their diagnosis or recommendations?
4. **Definitive Go / No-Go Verdict**: Is the current strategy salvagable, or is QuantOS a world-class institutional platform running a non-viable strategy?
5. **Action Plan**: The top 3 immediate steps for the founder to achieve genuine profitability on NSE.
"""
    return sys_prompt, user_prompt


# ==============================================================================
# Main Runner Loop
# ==============================================================================
def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="QuantOS Dual-AI Deep Analysis Pipeline")
    parser.add_argument("--skip-openai", action="store_true", help="Run Claude only")
    parser.add_argument("--model", default=None, help="Claude model (e.g. claude-opus-5, claude-fable-5-1)")
    parser.add_argument("--endpoint", default=None, help="Claude API endpoint URL")
    parser.add_argument("--output-dir", default=None, help="Output directory")
    args = parser.parse_args()

    anth_key, oai_key, lit_key = load_env_keys()
    effective_claude_key = lit_key or anth_key
    if not effective_claude_key:
        print("[!] FATAL: No Anthropic or Lightning API key found in .env", file=sys.stderr)
        return 1

    is_lightning = effective_claude_key.startswith("sk-lit-")
    default_model = "claude-opus-5" if is_lightning else ANTHROPIC_DEFAULT_MODEL
    default_endpoint = "https://lightning.ai/v1/messages" if is_lightning else ANTHROPIC_ENDPOINT

    selected_model = args.model or default_model
    selected_endpoint = args.endpoint or default_endpoint

    default_output_name = "claude_opus_audit" if "opus" in selected_model else "claude_fable_audit"
    output_dir = Path(args.output_dir) if args.output_dir else (REPO_ROOT / "reports" / default_output_name)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Start live dashboard server
    start_dashboard_server()
    dashboard_state["status"] = f"Audit pipeline started ({selected_model})"
    dashboard_state["active_model"] = selected_model

    client = httpx.Client(timeout=450.0)

    # Determine OpenAI model
    openai_model = "None"
    if not args.skip_openai and oai_key:
        openai_model = resolve_openai_model(client, oai_key)
        dashboard_state["active_model"] = f"{selected_model} + {openai_model}"
        log_event(f"Resolved OpenAI model for second opinion: {openai_model}")

    print("\n" + "=" * 70)
    print(f" QuantOS Dual-AI Quant Audit: {selected_model} + OpenAI Second Opinion")
    print(f" Model 1 (Primary) : {selected_model} (Adaptive Thinking: max)")
    print(f" Model 2 (Opinion) : {openai_model} (Reasoning: high)")
    print(f" API Gateway       : {selected_endpoint}")
    print(f" Live Dashboard    : http://127.0.0.1:{DASHBOARD_PORT}")
    print("=" * 70 + "\n")

    # --------------------------------------------------------------------------
    # Phase 1: Model Analysis
    # --------------------------------------------------------------------------
    dashboard_state["phase"] = "Phase 1: Model Analysis"
    dashboard_state["status"] = f"Running Phase 1: Model Analysis with {selected_model}..."
    log_event(f"Starting Phase 1: Quantitative Model Analysis ({selected_model})...")

    sys_m, usr_m = get_distilled_model_context()
    claude_model_rpt = call_claude_with_cache(
        client,
        effective_claude_key,
        sys_m,
        usr_m,
        phase_key="model",
        model=selected_model,
        endpoint=selected_endpoint,
    )
    dashboard_state["reports"]["claude"]["model"] = claude_model_rpt
    (output_dir / "01_claude_model_analysis.md").write_text(claude_model_rpt, encoding="utf-8")

    oai_model_rpt = ""
    if not args.skip_openai and oai_key:
        dashboard_state["status"] = f"Running Phase 1: Model Analysis with OpenAI ({openai_model})..."
        log_event(f"Starting Phase 1: Model Analysis Second Opinion ({openai_model})...")
        oai_model_rpt = call_openai_model(client, oai_key, openai_model, sys_m, usr_m)
        dashboard_state["reports"]["openai"]["model"] = oai_model_rpt
        (output_dir / "01_openai_model_analysis.md").write_text(oai_model_rpt, encoding="utf-8")

    # --------------------------------------------------------------------------
    # Phase 2: Strategy Analysis
    # --------------------------------------------------------------------------
    dashboard_state["phase"] = "Phase 2: Strategy Analysis"
    dashboard_state["status"] = f"Running Phase 2: Strategy Analysis with {selected_model}..."
    log_event(f"Starting Phase 2: Trading Strategy & Economics ({selected_model})...")

    sys_s, usr_s = get_distilled_strategy_context()
    claude_strat_rpt = call_claude_with_cache(
        client,
        effective_claude_key,
        sys_s,
        usr_s,
        phase_key="strategy",
        model=selected_model,
        endpoint=selected_endpoint,
    )
    dashboard_state["reports"]["claude"]["strategy"] = claude_strat_rpt
    (output_dir / "02_claude_strategy_analysis.md").write_text(claude_strat_rpt, encoding="utf-8")

    oai_strat_rpt = ""
    if not args.skip_openai and oai_key:
        dashboard_state["status"] = f"Running Phase 2: Strategy Analysis with OpenAI ({openai_model})..."
        log_event(f"Starting Phase 2: Strategy Analysis Second Opinion ({openai_model})...")
        oai_strat_rpt = call_openai_model(client, oai_key, openai_model, sys_s, usr_s)
        dashboard_state["reports"]["openai"]["strategy"] = oai_strat_rpt
        (output_dir / "02_openai_strategy_analysis.md").write_text(oai_strat_rpt, encoding="utf-8")

    # --------------------------------------------------------------------------
    # Phase 3: Executive Synthesis / Consensus
    # --------------------------------------------------------------------------
    dashboard_state["phase"] = "Phase 3: Executive Synthesis"
    dashboard_state["status"] = "Synthesizing executive audit summary..."
    log_event(f"Generating Executive Synthesis Report ({selected_model})...")

    if args.skip_openai or not oai_key:
        sys_c = (
            "You are an Executive Quantitative Director. Synthesize your findings from Phase 1 (Model) and "
            "Phase 2 (Strategy) into a high-level, definitive institutional briefing for the fund founder."
        )
        usr_c = f"""# QuantOS Institutional Audit — Executive Synthesis

Synthesize your deep evaluations of the QuantOS Model and Trading Strategy into an authoritative Executive Summary.

## Phase 1 (Model Findings):
{claude_model_rpt[:4000]}

## Phase 2 (Strategy Findings):
{claude_strat_rpt[:4000]}

---
## Required Executive Briefing:
1. **The Executive Verdict**: Answer bluntly: Is the current 6-feature ridge strategy profitable or viable on NSE equities?
2. **The Core Paradox of QuantOS**: The platform's world-class engineering (content-addressed evidence, strict point-in-time invariants, clean test gates) vs the unprofitability of the 6-feature technical model.
3. **The Friction Wall**: Why 0.224% statutory round-trip cost on NSE creates an insurmountable mathematical hurdle for daily swing trading.
4. **Key Flaws Identified in Model & Strategy**:
   - Model flaws (loss function, negative drift, score collapse, 21-bar window).
   - Strategy flaws (single-name constraint, momentum decay, survivorship bias on broader universe).
5. **Top 3 Actionable Pivots to Achieve Real Profitability**:
   - What specific alpha concepts and holding horizons should the founder implement immediately?
"""
        exec_rpt = call_claude_with_cache(
            client,
            effective_claude_key,
            sys_c,
            usr_c,
            phase_key="consensus",
            model=selected_model,
            endpoint=selected_endpoint,
        )
        dashboard_state["reports"]["consensus"] = exec_rpt
        (output_dir / "00_executive_summary.md").write_text(exec_rpt, encoding="utf-8")
        (output_dir / "01_model_analysis.md").write_text(claude_model_rpt, encoding="utf-8")
        (output_dir / "02_strategy_analysis.md").write_text(claude_strat_rpt, encoding="utf-8")
    else:
        sys_c, usr_c = get_consensus_prompt(claude_model_rpt, oai_model_rpt, claude_strat_rpt, oai_strat_rpt)
        consensus_rpt = call_claude_with_cache(
            client,
            effective_claude_key,
            sys_c,
            usr_c,
            phase_key="consensus",
            model=selected_model,
            endpoint=selected_endpoint,
        )
        dashboard_state["reports"]["consensus"] = consensus_rpt
        (output_dir / "00_dual_ai_consensus_summary.md").write_text(consensus_rpt, encoding="utf-8")

    # Save audit metadata and cost record
    metadata = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": selected_model,
        "thinking_mode": "adaptive (effort: max)",
        "endpoint": selected_endpoint,
        "total_cost_usd": round(dashboard_state["cost_usd"], 4),
        "tokens": dashboard_state["tokens"],
        "reports": [
            "00_executive_summary.md",
            "01_model_analysis.md",
            "02_strategy_analysis.md",
        ],
    }
    (output_dir / "audit_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    dashboard_state["phase"] = "COMPLETED"
    dashboard_state["status"] = f"Audit Completed! Total Cost: ${dashboard_state['cost_usd']:.4f}"
    log_event(f"Audit pipeline finished successfully! Total accumulated cost: ${dashboard_state['cost_usd']:.4f}")

    print("\n" + "=" * 70)
    print(f" {selected_model} Audit Finished Successfully!")
    print(f" Total Cost Accumulated : ${dashboard_state['cost_usd']:.4f} USD")
    print(f" Total Input Tokens     : {dashboard_state['tokens']['input']:,} (Cache read: {dashboard_state['tokens']['cache_read']:,})")
    print(f" Total Output Tokens    : {dashboard_state['tokens']['output']:,}")
    print(f" Reports Saved to       : {output_dir}")
    print(f" Dashboard Viewable at  : http://127.0.0.1:{DASHBOARD_PORT}")
    print("=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
