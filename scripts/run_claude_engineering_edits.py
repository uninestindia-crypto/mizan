#!/usr/bin/env python3
"""QuantOS Engineering Upgrades Generator via Claude Opus 5 (Maximum Thinking).

Queries Claude Opus 5 on Lightning AI to design and write the production-grade Python code
for the three quantitative engineering upgrades identified in the Mīzān dual-model audit:
  1. Dual P&L Engine (Gross Signal P&L vs. True Liquidation-Equivalent NAV) in research_xs_monthly/paper.py
  2. Pre-registered Horizon Protection Invariants in scripts/run_mizan_live_audit.py
  3. Cardinality & Minimum Ticket Sizing Module in execution/cardinality_optimizer.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"
OUTPUT_DIR = REPO_ROOT / "reports" / "claude_engineering_edits"

ANTHROPIC_ENDPOINT = "https://lightning.ai/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MODEL_NAME = "claude-opus-5"


def log_event(msg: str) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)


def load_lightning_key() -> str:
    key = os.environ.get("LIGHTNING_API_KEY", "").strip()
    if ENV_FILE.exists():
        try:
            with open(ENV_FILE, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("LIGHTNING_API_KEY=") and not key:
                        key = line.split("=", 1)[1].strip().strip("\"'")
        except Exception as e:
            log_event(f"Error reading .env: {e}")
    return key


def read_file_safely(path: Path, max_chars: int = 25000) -> str:
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


def build_engineering_prompt() -> tuple[str, str]:
    sys_prompt = (
        "You are an elite Lead Quantitative Software Engineer and Core Architect at a Tier-1 quantitative hedge fund. "
        "You design and write immaculate, institutional-grade Python code adhering strictly to QuantOS principles: "
        "Decimal arithmetic (never float for prices or fees), next-bar execution, fail-closed safety, and zero external dependencies."
    )

    paper_code = read_file_safely(
        REPO_ROOT / "src" / "quant_system" / "research_xs_monthly" / "paper.py"
    )
    audit_code = read_file_safely(REPO_ROOT / "scripts" / "run_mizan_live_audit.py", 18000)

    user_prompt = rf"""# QuantOS Engineering Implementation Task: The 3 Core Upgrades

Based on the quantitative audits of the two live ₹10 Lakh Mīzān systems (Flagship Alpha and XS-Monthly Momentum), please write the exact, complete, production-ready Python code for three key upgrades.

---

### Background Context:
- **System 1 (Mīzān Flagship Alpha)**: 15-feature cross-sectional Ridge model. Has a mandatory **10-session carried holding horizon** (`trial_mizan_h11_002`) and is on session 4 of 10.
- **System 2 (Mīzān XS-Monthly Momentum)**: 21-day formation, 21-day holding horizon across NIFTY 500. Currently on session 2 of 21. Currently marks open positions gross, which creates an illusion of +₹4,223 gain when liquidation NAV is actually slightly negative.
- **NSE Indian Delivery Frictions**:
  - Statutory taxes: 0.224% round-trip (STT 0.1% each side, exchange transaction charges ~0.003%, stamp duty 0.015%, SEBI fees + GST).
  - Depository Participant (DP) debit charge: Flat ₹20 + 18% GST = **₹23.60 per scrip per sell** regardless of trade size.
  - Estimated bid-ask half-spread: 7.5 bps (15 bps round-trip).

---

### Required Deliverables:

Please provide the complete, pristine Python code for each of the following 3 files, clearly demarcated with markdown code blocks:

#### Deliverable 1: `src/quant_system/research_xs_monthly/paper.py` (Refactored / Enhanced)
- Add `calculate_liquidation_equivalent_nav(open_holdings: list[dict], cash: Decimal, dp_fee_per_scrip: Decimal = Decimal("23.60"), statutory_rate: Decimal = Decimal("0.00224"), exit_half_spread: Decimal = Decimal("0.00075")) -> dict`
- Update `_book_open` and `settle_positions` so that every open position and the overall portfolio state computes BOTH:
  1. `gross_market_value` & `gross_unrealized_pnl` (raw model signal tracking)
  2. `liquidation_equivalent_nav` & `liquidation_unrealized_pnl` (reserving prospective exit statutory taxes, flat ₹23.60 DP charges for unique filled scrips, and exit spread).
- Ensure 100% Decimal precision, zero floats, and backwards compatibility with existing `state.json` consumers.

#### Deliverable 2: `src/quant_system/execution/cardinality_optimizer.py` (New Module)
- A dedicated portfolio cardinality and ticket sizing optimizer for Version 2:
  - Enforces the **Minimum Viable Ticket Sizing Rule**: On ₹10,00,000 capital, to prevent flat ₹23.60 DP fees from exceeding 5 basis points of position size, ticket size must be $\ge ₹47,200$.
  - Hard cardinality cap: Maximum 20 stocks (`MAX_LEGS = 20`) for ₹10 Lakh capital base.
  - Implements integer share lotting (`floor(target_inr / price)`), explicit uninvested cash buffer tracking, and validation ensuring total deployed + cash equals notional.

#### Deliverable 3: `scripts/run_mizan_live_audit.py` (Horizon Guardrail Patch)
- In the audit prompt generator functions (`get_mizan_flagship_context` and `get_mizan_xs_monthly_context`):
  - Read `sessions_held` / `sessions_completed` from `portfolio_state.json` (System 1) and calculate elapsed sessions for System 2.
  - Inject explicit **MANDATORY AUDIT PRECONDITIONS** into the prompt:
    1. Declare that this is an active forward paper pilot / training run with virtual money, NOT an immediate live capital allocation decision.
    2. Enforce the **10-Session Holding Invariant** for System 1: State that System 1 is in session N of 10 and that premature drawdown evaluation or exit recommendations before session 10 are scientifically invalid.
    3. Enforce the **21-Session Rotation Invariant** for System 2: State that System 2 is in session N of 21 and premature exit recommendations before session 21 are scientifically invalid.

---

### Reference Existing Code:
`src/quant_system/research_xs_monthly/paper.py`:
```python
{paper_code}
```

`scripts/run_mizan_live_audit.py` extract:
```python
{audit_code}
```

Write the code clearly, cleanly, and completely so it can be integrated directly into QuantOS.
"""
    return sys_prompt, user_prompt


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:
        pass

    api_key = load_lightning_key()
    if not api_key:
        log_event("ERROR: LIGHTNING_API_KEY not found in .env or environment!")
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    log_event("Connecting to Claude Opus 5 (Lightning AI, Maximum Thinking: effort=high)...")
    sys_prompt, user_prompt = build_engineering_prompt()

    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "anthropic-beta": "prompt-caching-2024-07-31",
        "content-type": "application/json",
    }

    payload = {
        "model": MODEL_NAME,
        "max_tokens": 32768,
        "stream": True,
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": "high"},
        "system": [
            {
                "type": "text",
                "text": sys_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": [{"role": "user", "content": user_prompt}],
    }

    log_event("Streaming code generation from Claude Opus 5...")
    start_time = time.time()
    full_text: list[str] = []
    thinking_chars = 0

    with httpx.Client(timeout=600.0) as client:
        with client.stream("POST", ANTHROPIC_ENDPOINT, headers=headers, json=payload) as resp:
            if resp.status_code != 200:
                err_text = resp.read().decode("utf-8", errors="replace")
                log_event(f"Claude API Error {resp.status_code}: {err_text}")
                return 1

            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    event = json.loads(data_str)
                    etype = event.get("type")
                    if etype == "content_block_delta":
                        delta = event.get("delta", {})
                        dtype = delta.get("type")
                        if dtype == "thinking_delta":
                            thinking_chars += len(delta.get("thinking", ""))
                            if thinking_chars % 5000 < 100:
                                log_event(f"Claude Opus 5 reasoning... (~{thinking_chars:,} chars)")
                        elif dtype == "text_delta":
                            chunk = delta.get("text", "")
                            full_text.append(chunk)
                            if len("".join(full_text)) % 2000 < 100:
                                log_event(
                                    f"Generating code... (~{len(''.join(full_text)):,} chars)"
                                )
                except Exception:
                    pass

    elapsed = time.time() - start_time
    result_text = "".join(full_text).strip()
    log_event(f"Finished code generation in {elapsed:.1f}s ({len(result_text):,} chars).")

    out_file = OUTPUT_DIR / "claude_generated_edits.md"
    out_file.write_text(result_text, encoding="utf-8")
    log_event(f"Saved generated code to {out_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
