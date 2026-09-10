#!/usr/bin/env python3
"""Dual-model Mīzān audit over Amazon Bedrock: GPT-6 Astra then Claude Fable 5.1.

Context: 100% virtual money. Both Mīzān systems trade paper capital of Rs 10,00,000 each. Nothing
in this script places an order, promotes a model, or touches the governed training path. It reads
state and asks two frontier models to criticise it.

Flow:
  1. Read the **live** state of both paper books from disk.
  2. GPT-6 Astra (`global.openai.gpt-6-astra`) gives a first opinion.
  3. Claude Fable 5.1 (`global.anthropic.claude-fable-5-1`) reads that first opinion and gives an
     adversarial second opinion.
  4. A consensus file records both, with the token accounting.

This is a **sibling** of `scripts/run_mizan_dual_opinion.py`, not a replacement. That script is
claimed by another agent's active work record and routes through router.one; this one routes through
one Amazon Bedrock account, so a single AWS credential and bill covers both models.

Two differences from the router.one runner are deliberate:

- **The dossier is read, not typed.** The router.one runner embeds the paper equity, P&L, and
  position counts as literal prose. Those figures have since drifted, and one of them has drifted far
  enough to flip sign. This runner reads `data/evidence/paper/portfolio_state.json` and
  `logs/xs_monthly_new/paper_watch/state.json` at run time and stamps every number with its own
  as-of date, so the models cannot be asked to explain a profit that no longer exists.
- **Both calls stream.** Fable 5.1's thinking cannot be disabled and GPT-6 Astra is a reasoning
  model; a demanding turn from either runs for minutes, which a non-streaming call is liable to time
  out on.

Usage:
    python scripts/run_mizan_dual_opinion_bedrock.py --dry-run     # no API call, no spend
    python scripts/run_mizan_dual_opinion_bedrock.py               # full audit
    python scripts/run_mizan_dual_opinion_bedrock.py --effort max  # deeper, slower, dearer

Prerequisites are in `docs/bedrock-dual-model-setup.md`.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from quant_system.alpha.bedrock_providers import (  # noqa: E402
    ENV_NAMES,
    BedrockAuditConfig,
    BedrockCredentialsMissing,
    EffortLevel,
    ModelReply,
    call_claude_fable,
    call_gpt6_astra,
)
from quant_system.config.env import load_env_file  # noqa: E402

OUTPUT_DIR = REPO_ROOT / "reports" / "mizan_bedrock_audit"
SYSTEM1_STATE = REPO_ROOT / "data" / "evidence" / "paper" / "portfolio_state.json"
SYSTEM2_STATE = REPO_ROOT / "logs" / "xs_monthly_new" / "paper_watch" / "state.json"

FIRST_OPINION_FILE = "01_gpt_6_astra_first_opinion.md"
SECOND_OPINION_FILE = "02_claude_fable_5_1_second_opinion.md"
CONSENSUS_FILE = "03_dual_model_consensus.md"

# Published Bedrock rates for GPT-6 Astra, global cross-region, short context (272K), USD per 1M
# tokens. Source: the model's AWS model card, read 2026-09-10. Claude Fable 5.1's Bedrock rate is
# not stated on its own card - it defers to the Bedrock pricing page - so this script reports Fable
# token counts without inventing a dollar figure for them.
GPT6_INPUT_USD_PER_MTOK = Decimal("10.00")
GPT6_OUTPUT_USD_PER_MTOK = Decimal("50.00")


def log_event(message: str) -> None:
    """Print a timestamped progress line."""
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


@dataclass(frozen=True, slots=True)
class FlagshipState:
    """Live state of System 1, the Mīzān Flagship Alpha paper pilot."""

    holdings: int
    cash: Decimal
    cost_basis: Decimal
    anchor_equity: Decimal
    anchor_on: str
    last_completed_on: str
    last_rebalance_on: str
    halted: bool
    halt_reason: str


@dataclass(frozen=True, slots=True)
class MonthlyState:
    """Live state of System 2, the Mīzān XS-Monthly Momentum paper watch."""

    open_legs: int
    closed_legs: int
    capital: Decimal
    cash: Decimal
    market_value: Decimal
    entry_value: Decimal
    asof_date: str
    last_run_at: str
    formation_sessions: int
    hold_sessions: int
    top_frac: str
    cost_ratio: str

    @property
    def equity(self) -> Decimal:
        """Cash plus the marked value of every open leg."""
        return self.cash + self.market_value

    @property
    def pnl(self) -> Decimal:
        """Equity less the notional capital the book started with."""
        return self.equity - self.capital

    @property
    def pnl_pct(self) -> Decimal:
        """Profit and loss as a percentage of notional capital."""
        if self.capital == 0:
            return Decimal(0)
        return self.pnl / self.capital * Decimal(100)


def _read_json(path: Path) -> dict[str, Any]:
    """Read one JSON object, failing with a message that names the missing runner."""
    if not path.exists():
        raise FileNotFoundError(
            f"Paper state not found at {path}. Run the paper session that owns it before auditing; "
            "this script refuses to audit a book whose state it cannot read."
        )
    parsed: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return parsed


def read_flagship_state() -> FlagshipState:
    """Read System 1's live paper book.

    Equity is reported as the daily anchor rather than a fresh mark: the state file carries entry
    cost per holding but no current price, so marking it here would mean inventing prices. The
    anchor is a real recorded figure and travels with its own date.
    """
    payload = _read_json(SYSTEM1_STATE)["payload"]
    holdings = payload["holdings"]
    cost_basis = sum(
        (Decimal(str(h["average_cost"])) * Decimal(str(h["quantity"])) for h in holdings),
        Decimal(0),
    )
    return FlagshipState(
        holdings=len(holdings),
        cash=Decimal(str(payload["cash"])),
        cost_basis=cost_basis,
        anchor_equity=Decimal(str(payload["daily_anchor_equity"])),
        anchor_on=str(payload["daily_anchor_on"]),
        last_completed_on=str(payload["last_completed_on"]),
        last_rebalance_on=str(payload["last_rebalance_on"]),
        halted=payload["halted_on"] is not None,
        halt_reason=str(payload.get("halt_reason") or ""),
    )


def read_monthly_state() -> MonthlyState:
    """Read System 2's live paper watch, which marks every open leg to market."""
    payload = _read_json(SYSTEM2_STATE)
    open_legs = payload["open"]
    runs = payload["runs"]
    rule = payload["rule"]
    asof = sorted({str(leg["asof_date"]) for leg in open_legs}) or ["unknown"]
    return MonthlyState(
        open_legs=len(open_legs),
        closed_legs=len(payload["closed"]),
        capital=Decimal(str(payload["capital"])),
        cash=Decimal(str(payload["cash"])),
        market_value=sum(
            (Decimal(str(leg["market_value"])) for leg in open_legs), Decimal(0)
        ),
        entry_value=sum((Decimal(str(leg["entry_value"])) for leg in open_legs), Decimal(0)),
        asof_date=asof[-1],
        last_run_at=str(runs[-1]["at"]) if runs else "never",
        formation_sessions=int(rule["formation_sessions"]),
        hold_sessions=int(rule["hold_sessions"]),
        top_frac=str(rule["top_frac"]),
        cost_ratio=str(rule["cost_ratio"]),
    )


def _rupees(amount: Decimal) -> str:
    """Format a Decimal as rupees with two places and a thousands separator."""
    return f"Rs {amount:,.2f}"


def build_dossier(flagship: FlagshipState, monthly: MonthlyState) -> str:
    """Assemble the audit dossier from live state plus the fixed governed-trial evidence.

    The live block is read at run time. The trial block below is historical evidence from completed
    governed trials and does not change, so it is stated as a constant.
    """
    return f"""# QuantOS Institutional Audit Dossier: Dual Mizan Systems

## TESTING PREMISE
- This is **100% VIRTUAL MONEY (paper trading simulation)**. No real capital is at risk.
- We are engineering an institutional algorithmic trading platform for Indian equities (NSE).
- Each system is allocated Rs 10,00,000 of virtual test capital.
- The objective is an unsparing audit: find the flaws, and establish whether any genuine,
  cost-surviving edge exists at all.

## DATA PROVENANCE
Every live figure below was read from the running paper books at audit time, not transcribed.
Source files: `data/evidence/paper/portfolio_state.json` and
`logs/xs_monthly_new/paper_watch/state.json`. Each number carries its own as-of date. Where a
figure is a cost basis rather than a mark, it says so.

---

## SYSTEM 1: Mizan Flagship Alpha (multi-session paper pilot)

**Live state, as of {flagship.last_completed_on}:**
- Allocated virtual capital: Rs 10,00,000.00
- Daily anchor equity: {_rupees(flagship.anchor_equity)} (recorded {flagship.anchor_on})
- Implied drawdown against notional: {(flagship.anchor_equity - Decimal(1000000)) / Decimal(10000):+.3f}%
- Cash available: {_rupees(flagship.cash)}
- Open holdings: {flagship.holdings}
- Cost basis of open holdings: {_rupees(flagship.cost_basis)}
- Average position size: {_rupees(flagship.cost_basis / max(flagship.holdings, 1))}
- Last rebalance: {flagship.last_rebalance_on}; last completed session: {flagship.last_completed_on}
- Halted: {"YES - " + flagship.halt_reason if flagship.halted else "no"}

**Model architecture:** Ridge classifier over 15 pooled cross-sectional features
(`quantos.mizan_crosssectional_fifteen`): `return_1`, `return_5`, `return_21`,
`garman_klass_volatility`, `parkinson_volatility`, `rsi_14_centered`, `sma_20_distance`,
`sma_50_distance`, `volume_zscore`, `money_flow_multiplier`, `india_vix_level`,
`india_vix_change_5`, `nifty_return_5`, `cs_rank_momentum_5`, `cs_rank_volume_surprise`.

**Governed trial evidence (historical, fixed):**
- `trial_mizan_001` (1-session hold): gross mean return +0.076% across all 45 symbols, but after
  NSE statutory friction of 0.2225% round trip, **45 of 45 symbols turned negative**.
  Sharpe -3.2427, total return -41.57%.
- `trial_mizan_h11_002` (10-session hold): Sharpe -0.4108, total return -31.57%, while buy-and-hold
  returned +22.0% over the same window. DSR 0.1760 against a 0.95 gate.
- **Feature IC inversion:** of 14 measurable features, 8 carry statistically significant
  **negative** IC (|t| > 2, all negative): `return_1` t = -4.2, `return_5` t = -3.8,
  `rsi_14_centered` t = -2.9, `sma_20_distance` t = -3.1, `cs_rank_momentum_5` t = -2.7.
  The model bets on continuation at horizons where these names mean-revert.

---

## SYSTEM 2: Mizan XS-Monthly Momentum (21-day paper watch)

**Live state, as of {monthly.asof_date} (last run {monthly.last_run_at}):**
- Allocated virtual capital: {_rupees(monthly.capital)}
- **Marked equity: {_rupees(monthly.equity)}**
- **Net P&L: {_rupees(monthly.pnl)} ({monthly.pnl_pct:+.3f}%)**
- Cash available: {_rupees(monthly.cash)}
- Open legs: {monthly.open_legs} (closed so far: {monthly.closed_legs})
- Entry value: {_rupees(monthly.entry_value)}; current market value: {_rupees(monthly.market_value)}
- Average position size: {_rupees(monthly.entry_value / max(monthly.open_legs, 1))}

**Frozen rule:** formation {monthly.formation_sessions} sessions, hold {monthly.hold_sessions}
sessions, top {monthly.top_frac} by momentum across NIFTY 500, cost ratio {monthly.cost_ratio}.

**10-year backtest evidence (2016-2026, 423 liquid NSE names, 115 rebalances):**
- Top-20% momentum longs: net mean +1.74%/period, Sharpe **+0.84**
- Market equal-weight benchmark: net mean +1.69%/period, Sharpe **+0.83**
- **Selection edge over the unselected market: +5.3 bps/period (+0.053%)**
- Rank IC: -0.0096 (t = -0.85)
- 3-year breadth test (499 names, 2023-2026): longs Sharpe +0.91 vs market +0.89 (+10 bps/period)

**Friction and microstructure drag:**
- Indian delivery selling incurs a flat Depository Participant (DP) debit of Rs 13-20 plus 18% GST
  (about Rs 15.50-23.60) **per scrip per day**, independent of position size.
- At {monthly.open_legs} legs averaging
  {_rupees(monthly.entry_value / max(monthly.open_legs, 1))}, a Rs 20 DP fee is roughly
  **{Decimal(20) / (monthly.entry_value / max(monthly.open_legs, 1)) * Decimal(10000):.1f} bps**
  on the sell leg alone, before STT (0.1%), exchange fees, SEBI turnover fees, stamp duty, and
  brokerage.
- That flat charge is several times the entire measured selection edge of +5.3 bps.

---

## THE CENTRAL QUESTION

Both books are now **below** their notional capital. Neither system has yet demonstrated an edge
that survives real Indian statutory friction. The audit must establish whether either architecture
can be repaired, or whether this model class on this market is simply dead.
"""


GPT6_SYSTEM_PROMPT = (
    "You are an institutional quantitative research director conducting an independent audit of two "
    "systematic Indian equity trading models in a 100% virtual-money paper-trading sandbox. Be "
    "unsparing and quantitative. Where the evidence supports a negative verdict, state it plainly "
    "rather than softening it; a false positive here costs the team far more than a harsh review. "
    "Compute friction hurdles explicitly. Do not congratulate the team."
)

FABLE_SYSTEM_PROMPT = (
    "You are a senior quantitative strategist and system architect delivering an adversarial second "
    "opinion on two Indian equity models in a 100% virtual-money paper-trading sandbox. You have "
    "the full dossier and a first opinion from another frontier model. Your value is in "
    "disagreement, not agreement: identify where the first opinion is wrong, overconfident, or has "
    "missed NSE-specific microstructure. Where you agree, say so briefly and move on."
)


def build_first_opinion_prompt(dossier: str) -> str:
    """The audit question put to GPT-6 Astra."""
    return f"""{dossier}

---

# AUDIT INSTRUCTION - FIRST OPINION

Deliver your independent first opinion on both Mizan systems. All capital is virtual test money.

Address in order:

1. **System 1 - feature IC inversion.** Why would 8 of 14 features carry significant negative IC?
   Is the 1-5 session horizon in Indian equities structurally mean-reverting? What exactly happens
   when a momentum-shaped Ridge model is fitted to mean-reverting microstructure, and does simple
   sign inversion of the fitted coefficients recover an edge or merely invert the noise?

2. **System 1 - friction vs gross alpha.** Trial 1 produced +0.076% gross across 45 symbols and lost
   on all 45 after 0.2225% round-trip statutory cost. Is sub-5-day delivery trading on NSE
   arithmetically dead for this account size? Show the hurdle calculation.

3. **System 2 - alpha or beta?** The top-20% momentum basket backtested at Sharpe +0.84 against an
   unselected market equal-weight at +0.83. The live book is currently **below** its notional
   capital. Is the +5.3 bps/period selection edge distinguishable from zero given 115 rebalances?

4. **System 2 - the DP fee penalty.** A flat per-scrip DP debit on ~100 small legs. Quantify the
   drag and state whether cardinality reduction can recover the edge, and at what leg count.

5. **Comparative verdict and roadmap.** Head to head. Should the team invert System 1, move to
   intraday cash or futures to avoid delivery STT and DP fees, concentrate cardinality, or abandon
   this model class entirely? Give a definitive recommendation, including the option of stopping.
"""


def build_second_opinion_prompt(dossier: str, first_opinion: str) -> str:
    """The audit question put to Claude Fable 5.1, carrying the first opinion."""
    return f"""{dossier}

---

# FIRST OPINION FROM GPT-6 ASTRA

{first_opinion}

---

# AUDIT INSTRUCTION - SECOND OPINION

Deliver an adversarial second opinion. All capital is virtual test money.

1. **Critique the first opinion.** Where is it right, where is it wrong, and what did it miss about
   NSE microstructure, opening auctions, circuit limits, or factor dynamics? Be specific. If it
   asserted something the dossier does not support, name it.

2. **System 1.** Does sign inversion survive costs, or does it just invert noise? What holding
   horizon or execution structure is mathematically viable at 0.2225% round trip, if any?

3. **System 2.** What is the optimal leg count given a flat per-scrip DP fee, and show the
   arithmetic. Does any leg count make a +5.3 bps/period edge bankable?

4. **The stopping question.** Given both books are below notional and the governed evidence has
   produced nothing promotable, make the case for and against continuing this line of work at all.
   Then give your own verdict.

5. **Actionable roadmap.** Concrete, ordered engineering steps for the paper-trading environment.
"""


def _usd(amount: Decimal) -> str:
    """Format a USD amount to four decimal places."""
    return f"${amount:.4f}"


def gpt6_cost_usd(reply: ModelReply) -> Decimal:
    """Estimate the Bedrock cost of one GPT-6 Astra turn from its published rates."""
    million = Decimal(1_000_000)
    return (
        Decimal(reply.input_tokens) / million * GPT6_INPUT_USD_PER_MTOK
        + Decimal(reply.output_tokens) / million * GPT6_OUTPUT_USD_PER_MTOK
    )


def write_consensus(
    flagship: FlagshipState,
    monthly: MonthlyState,
    first: ModelReply,
    second: ModelReply,
    config: BedrockAuditConfig,
) -> None:
    """Write the consensus file recording both opinions and what they cost."""
    cost = gpt6_cost_usd(first)
    body = f"""# QuantOS Dual-Model Consensus: the two live Mizan systems

**Audit date:** {time.strftime("%Y-%m-%d %H:%M:%S")}
**Transport:** Amazon Bedrock, {config.describe()}
**First opinion:** OpenAI `{first.model}`
**Second opinion:** Anthropic `{second.model}`
**Environment:** 100% virtual money / paper trading simulation

---

## Live position at audit time

| | System 1 (Flagship Alpha) | System 2 (XS-Monthly Momentum) |
|---|---|---|
| Notional capital | Rs 10,00,000.00 | {_rupees(monthly.capital)} |
| Equity | {_rupees(flagship.anchor_equity)} (anchor {flagship.anchor_on}) | {_rupees(monthly.equity)} (marked {monthly.asof_date}) |
| Net P&L | {_rupees(flagship.anchor_equity - Decimal(1000000))} | {_rupees(monthly.pnl)} ({monthly.pnl_pct:+.3f}%) |
| Cash | {_rupees(flagship.cash)} | {_rupees(monthly.cash)} |
| Open legs | {flagship.holdings} | {monthly.open_legs} |
| Average position | {_rupees(flagship.cost_basis / max(flagship.holdings, 1))} | {_rupees(monthly.entry_value / max(monthly.open_legs, 1))} |

**Both books are below their notional capital.** Every figure above was read from the live paper
state at audit time, not transcribed from a previous report.

---

## Model accounting

| | First opinion | Second opinion |
|---|---|---|
| Model | `{first.model}` | `{second.model}` |
| Input tokens | {first.input_tokens:,} | {second.input_tokens:,} |
| Output tokens | {first.output_tokens:,} | {second.output_tokens:,} |
| Reasoning tokens | {first.reasoning_tokens:,} | not itemised by Bedrock |
| Wall clock | {first.elapsed_seconds:.1f}s | {second.elapsed_seconds:.1f}s |
| Estimated cost | {_usd(cost)} | see the Bedrock pricing page |

GPT-6 Astra's cost is computed from the rates published on its AWS model card (global cross-region,
short context: ${GPT6_INPUT_USD_PER_MTOK}/MTok input, ${GPT6_OUTPUT_USD_PER_MTOK}/MTok output).
Claude Fable 5.1's model card does not publish a rate, so no dollar figure is invented for it here.

---

## Reports

- [First opinion - GPT-6 Astra]({FIRST_OPINION_FILE})
- [Second opinion - Claude Fable 5.1]({SECOND_OPINION_FILE})

## Standing caveat

Two frontier models reviewing the same dossier is a **critique**, not evidence. Nothing either model
says promotes a candidate, satisfies a governance gate, or substitutes for a governed trial with a
pre-declared screen and a spent multiplicity ordinal. Treat both reports as informed argument to be
checked, not as an adjudication.
"""
    (OUTPUT_DIR / CONSENSUS_FILE).write_text(body, encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read state, build the dossier, print the config, and exit without calling any model.",
    )
    parser.add_argument(
        "--effort",
        choices=("low", "medium", "high", "xhigh", "max"),
        default="high",
        help="Reasoning depth for both models. Default: high.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=32000,
        help="Ceiling on generated tokens per model turn. Default: 32000.",
    )
    parser.add_argument(
        "--reuse-first-opinion",
        action="store_true",
        help="Reuse an existing first-opinion file instead of paying for it again.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the dual-model audit. Returns a process exit code."""
    args = parse_args(argv)
    # The dossier carries rupee symbols and Mīzān's macron; a cp1252 console would otherwise raise.
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass

    loaded = load_env_file(REPO_ROOT / ".env", only=ENV_NAMES)
    if loaded:
        log_event(f"Loaded from .env: {', '.join(loaded)}")

    flagship = read_flagship_state()
    monthly = read_monthly_state()
    log_event(
        f"System 1: {flagship.holdings} legs, anchor equity {_rupees(flagship.anchor_equity)} "
        f"({flagship.anchor_on})"
    )
    log_event(
        f"System 2: {monthly.open_legs} legs, marked equity {_rupees(monthly.equity)} "
        f"({monthly.pnl_pct:+.3f}%, {monthly.asof_date})"
    )

    dossier = build_dossier(flagship, monthly)
    effort: EffortLevel = args.effort

    if args.dry_run:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        preview = OUTPUT_DIR / "00_dossier_preview.md"
        preview.write_text(dossier, encoding="utf-8")
        log_event(f"Dry run. Dossier written to {preview.relative_to(REPO_ROOT)}")
        try:
            config = BedrockAuditConfig.from_env()
        except BedrockCredentialsMissing as exc:
            log_event(f"No Bedrock credential yet: {exc}")
            return 0
        log_event(f"Bedrock config: {config.describe()}")
        log_event(f"  first opinion  -> {config.gpt6_model_id} at {config.openai_base_url}")
        log_event(f"  second opinion -> {config.fable_model_id} at {config.anthropic_base_url}")
        return 0

    try:
        config = BedrockAuditConfig.from_env()
    except (BedrockCredentialsMissing, ValueError) as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 2

    log_event(f"Bedrock: {config.describe()}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    first_path = OUTPUT_DIR / FIRST_OPINION_FILE

    if args.reuse_first_opinion and first_path.exists() and first_path.read_text(
        encoding="utf-8"
    ).strip():
        log_event(f"Reusing existing {FIRST_OPINION_FILE}")
        first = ModelReply(
            model=config.gpt6_model_id,
            text=first_path.read_text(encoding="utf-8"),
            input_tokens=0,
            output_tokens=0,
            reasoning_tokens=0,
            elapsed_seconds=0.0,
        )
    else:
        log_event("=== Step 1: GPT-6 Astra first opinion ===")
        first = call_gpt6_astra(
            config,
            system_prompt=GPT6_SYSTEM_PROMPT,
            user_prompt=build_first_opinion_prompt(dossier),
            max_output_tokens=args.max_output_tokens,
            effort=effort,
            on_event=log_event,
        )
        if not first.text:
            print(
                "[!] GPT-6 Astra returned no text. Aborting before the second call.",
                file=sys.stderr,
            )
            return 3
        first_path.write_text(first.text, encoding="utf-8")
        log_event(
            f"First opinion: {first.output_tokens:,} output tokens in {first.elapsed_seconds:.1f}s "
            f"(~{_usd(gpt6_cost_usd(first))})"
        )

    log_event("=== Step 2: Claude Fable 5.1 second opinion ===")
    second = call_claude_fable(
        config,
        system_prompt=FABLE_SYSTEM_PROMPT,
        user_prompt=build_second_opinion_prompt(dossier, first.text),
        max_output_tokens=args.max_output_tokens,
        effort=effort,
        on_event=log_event,
    )

    if second.refused:
        # A refusal is a real outcome, not an empty report. Bedrock offers no server-side fallback,
        # so record it plainly rather than writing a blank file that reads like a finished audit.
        notice = (
            f"# Second opinion refused\n\n"
            f"`{second.model}` declined this request.\n\n"
            f"- Refusal category: `{second.refusal_category}`\n"
            f"- Nothing was written as a report because nothing was produced.\n\n"
            f"Bedrock has no server-side fallback parameter, so there is no automatic rescue. "
            f"Rephrase the audit instruction, or run the second opinion on another model.\n"
        )
        (OUTPUT_DIR / SECOND_OPINION_FILE).write_text(notice, encoding="utf-8")
        print(f"[!] Second opinion refused (category: {second.refusal_category}).", file=sys.stderr)
        return 4

    if not second.text:
        print("[!] Claude Fable 5.1 returned no text.", file=sys.stderr)
        return 3

    (OUTPUT_DIR / SECOND_OPINION_FILE).write_text(second.text, encoding="utf-8")
    log_event(
        f"Second opinion: {second.output_tokens:,} output tokens in {second.elapsed_seconds:.1f}s"
    )

    write_consensus(flagship, monthly, first, second, config)
    log_event(f"Wrote {CONSENSUS_FILE}")
    print(f"\n[OK] Dual-model audit complete. Reports in {OUTPUT_DIR.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
