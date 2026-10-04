"""Platform AI Assistant Service.

Provides intent parsing, context grounding, LLM-powered reasoning, and
action proposal generation for the QuantOS Copilot.
"""

from __future__ import annotations

import logging
import re
import uuid

from quant_system.alpha.direct_providers import get_direct_client_for_provider
from quant_system.alpha.key_pool import KeyPoolManager, ProviderType
from quant_system.assistant.actions import FINANCIAL_GLOSSARY, TAB_MAPPINGS, PlatformActionExecutor
from quant_system.assistant.schemas import (
    ActionExecutionRequest,
    ActionProposal,
    AssistantChatRequest,
    AssistantChatResponse,
    PlatformActionType,
)

logger = logging.getLogger(__name__)


class PlatformAssistantService:
    """Core intelligence and action routing service for QuantOS Copilot."""

    def __init__(self, key_pool: KeyPoolManager | None = None) -> None:
        self.key_pool = key_pool or KeyPoolManager()

    def process_chat(self, request: AssistantChatRequest) -> AssistantChatResponse:
        """Processes an incoming chat prompt and returns a message with action proposals."""
        prompt = request.prompt.strip()
        lower_prompt = prompt.lower()
        current_tab = request.current_tab or "tab-ingestion"

        # 1. Check for Direct Action Intents
        # Tab Navigation
        nav_match = self._match_navigation_intent(lower_prompt)
        if nav_match:
            action_id = f"act_{uuid.uuid4().hex[:8]}"
            target_tab = nav_match
            proposal = ActionProposal(
                action_id=action_id,
                action_type=PlatformActionType.NAVIGATE_TAB,
                title=f"🧭 Open {self._tab_display_name(target_tab)}",
                description=f"Switch your active screen to {self._tab_display_name(target_tab)}",
                parameters={"tab": target_tab},
                requires_confirmation=False,
                target_tab=target_tab,
            )
            return AssistantChatResponse(
                message=f"I can take you directly to **{self._tab_display_name(target_tab)}**.",
                action_proposals=[proposal],
                suggested_prompts=["Explain this tab", "Run diagnostics", "Check risk limits"],
            )

        # Model & Strategy Profitability & Health Audit
        if any(
            w in lower_prompt
            for w in [
                "model audit",
                "strategy audit",
                "profitable",
                "profitability",
                "why is model failing",
                "problem in strategy",
                "problem in model",
                "model health",
                "strategy health",
                "is the model working",
                "is strategy profitable",
                "is model profitable",
                "friction wall",
                "audit model",
                "audit strategy",
                "analyse model",
                "analyze model",
            ]
        ):
            action_id = f"act_{uuid.uuid4().hex[:8]}"
            exec_res = PlatformActionExecutor.execute(
                ActionExecutionRequest(
                    action_id=action_id,
                    action_type=PlatformActionType.AUDIT_MODEL_STRATEGY,
                    parameters={},
                )
            )
            diag_proposal = ActionProposal(
                action_id=f"act_{uuid.uuid4().hex[:8]}",
                action_type=PlatformActionType.NAVIGATE_TAB,
                title="🩺 View Engine Diagnostics",
                description="Open the Diagnostics tab to see full model and system invariant metrics",
                parameters={"tab": "tab-diagnostics"},
                requires_confirmation=False,
                target_tab="tab-diagnostics",
            )
            ridge_proposal = ActionProposal(
                action_id=f"act_{uuid.uuid4().hex[:8]}",
                action_type=PlatformActionType.NAVIGATE_TAB,
                title="🔬 Open Governed Ridge Lab",
                description="Inspect technical feature sets, walk-forward folds, and hyperparameter tuning",
                parameters={"tab": "tab-training"},
                requires_confirmation=False,
                target_tab="tab-training",
            )
            return AssistantChatResponse(
                message=exec_res.message,
                action_proposals=[diag_proposal, ridge_proposal],
                suggested_prompts=[
                    "Inspect Risk Limits",
                    "Explain Deflated Sharpe Ratio",
                    "Run Diagnostics",
                ],
            )

        # Diagnostics & Health Check
        if any(
            w in lower_prompt
            for w in ["diagnos", "health", "status", "is system ok", "system check"]
        ):
            action_id = f"act_{uuid.uuid4().hex[:8]}"
            exec_res = PlatformActionExecutor.execute(
                ActionExecutionRequest(
                    action_id=action_id,
                    action_type=PlatformActionType.RUN_DIAGNOSTICS,
                    parameters={},
                )
            )
            return AssistantChatResponse(
                message=exec_res.message,
                suggested_prompts=[
                    "Inspect Risk Limits",
                    "Open Backtest Lab",
                    "Calculate Greeks for 24500 CE",
                ],
            )

        # Risk Governor Limits
        if any(
            w in lower_prompt
            for w in ["risk", "limits", "drawdown limit", "stop loss", "exposure limit"]
        ):
            action_id = f"act_{uuid.uuid4().hex[:8]}"
            exec_res = PlatformActionExecutor.execute(
                ActionExecutionRequest(
                    action_id=action_id,
                    action_type=PlatformActionType.INSPECT_RISK_LIMITS,
                    parameters={},
                )
            )
            return AssistantChatResponse(
                message=exec_res.message,
                suggested_prompts=[
                    "Run Diagnostics",
                    "Go to Risk Governor Tab",
                    "Run Backtest on INFY",
                ],
            )

        # Options & Greeks calculation
        if any(
            w in lower_prompt
            for w in [
                "greek",
                "black scholes",
                "delta",
                "gamma",
                "theta",
                "vega",
                "call option",
                "put option",
                "straddle",
            ]
        ):
            strike, spot, opt_type = self._parse_option_params(prompt)
            action_id = f"act_{uuid.uuid4().hex[:8]}"
            exec_res = PlatformActionExecutor.execute(
                ActionExecutionRequest(
                    action_id=action_id,
                    action_type=PlatformActionType.CALCULATE_GREEKS,
                    parameters={"strike": strike, "spot": spot, "option_type": opt_type},
                )
            )
            return AssistantChatResponse(
                message=exec_res.message,
                suggested_prompts=[
                    "Open Options Lab",
                    "Calculate 25000 PE Greeks",
                    "Explain Delta and Gamma",
                ],
            )

        # Backtest Setup & Proposal
        if any(
            w in lower_prompt for w in ["backtest", "simulate", "test strategy", "run strategy"]
        ):
            symbol = self._extract_symbol(prompt) or "INFY"
            action_id = f"act_{uuid.uuid4().hex[:8]}"
            proposal = ActionProposal(
                action_id=action_id,
                action_type=PlatformActionType.PREVIEW_BACKTEST,
                title=f"▶️ Prepare Backtest for {symbol}",
                description=f"Configure Decimal ledger simulation for {symbol} using Dual Momentum strategy",
                parameters={
                    "symbol": symbol,
                    "strategy": "EQUITY_DUAL_MOMENTUM",
                    "initial_cash": 1000000.0,
                },
                requires_confirmation=False,
                target_tab="tab-ledger",
            )
            return AssistantChatResponse(
                message=(
                    f"I can prepare a double-entry backtest simulation for **{symbol}** with ₹1,000,000 capital. "
                    "Click below to load the backtest parameters in the Backtest & Ledger lab."
                ),
                action_proposals=[proposal],
                suggested_prompts=[
                    "Check Risk Limits",
                    "Explain Deflated Sharpe Ratio",
                    "Run Diagnostics",
                ],
            )

        # Financial Concepts / Glossary
        for term, explanation in FINANCIAL_GLOSSARY.items():
            if term in lower_prompt or term.replace("_", " ") in lower_prompt:
                return AssistantChatResponse(
                    message=explanation,
                    suggested_prompts=[
                        "Run Diagnostics",
                        "Explain Purged K-Fold",
                        "Open Governed Ridge Tab",
                    ],
                )

        # Context Help for current tab
        if any(
            w in lower_prompt
            for w in ["explain tab", "what is this tab", "help me here", "guide me"]
        ):
            tab_help = self._get_tab_guidance(current_tab)
            return AssistantChatResponse(
                message=tab_help,
                suggested_prompts=[
                    "Run Diagnostics",
                    "Show Available Datasets",
                    "Inspect Risk Limits",
                ],
            )

        # Fallback to LLM or general guidance
        llm_response = self._try_llm_completion(prompt, current_tab)
        if llm_response:
            return AssistantChatResponse(
                message=llm_response,
                suggested_prompts=["Run Diagnostics", "Prepare Backtest", "Open Options Lab"],
            )

        # General helpful assistant overview
        general_help = (
            "👋 **QuantOS Copilot** at your service! I can help you navigate journeys and perform platform actions:\n\n"
            '- **🧭 Navigation**: *"Go to Options Lab"*, *"Open Risk Governor"*, *"Show Backtest tab"*\n'
            '- **⚡ Greeks & Pricing**: *"Calculate Greeks for 24500 CE strike"*\n'
            '- **📊 Backtesting**: *"Prepare a backtest on INFY with ₹10 Lakhs"*\n'
            '- **🛡️ Risk & Health**: *"Check risk limits"*, *"Run system diagnostics"*\n'
            '- **📚 Quantitative Concepts**: *"Explain Deflated Sharpe Ratio"*, *"What is Purged K-Fold?"*\n\n'
            "*Note: I operate strictly on platform tools and cannot modify repository code.*"
        )
        return AssistantChatResponse(
            message=general_help,
            suggested_prompts=[
                "Run System Diagnostics",
                "Calculate Greeks for 24500 CE",
                "Inspect Risk Governor Limits",
                "Prepare Backtest on INFY",
            ],
        )

    def _match_navigation_intent(self, text: str) -> str | None:
        """Matches a navigation command to a tab ID."""
        for keyword, tab_id in TAB_MAPPINGS.items():
            pattern = (
                rf"\b(go to|open|show|switch to|navigate to|take me to|view|load)\b.*\b{keyword}\b"
            )
            if re.search(pattern, text):
                return tab_id
        return None

    def _tab_display_name(self, tab_id: str) -> str:
        names = {
            "tab-ingestion": "📥 Data & Manifests",
            "tab-features": "📐 Features & Labels",
            "tab-training": "🧠 Governed Ridge",
            "tab-holdout": "🔒 Holdout & Stress",
            "tab-ledger": "📊 Backtest & Ledger",
            "tab-shadow": "👁️ Shadow Monitor",
            "tab-pilot": "🚀 Paper Pilot",
            "tab-straddle": "⚡ Options Lab",
            "tab-montecarlo": "🎲 Monte Carlo",
            "tab-risk": "🛡️ Risk Governor",
            "tab-diagnostics": "🩺 Diagnostics",
        }
        return names.get(tab_id, tab_id)

    def _get_tab_guidance(self, tab_id: str) -> str:
        guides = {
            "tab-ingestion": (
                "**Journey 1: Data Ingestion & Manifests**\n"
                "Acquires point-in-time NSE equity data, enforces corporate action adjustments, "
                "and generates immutable SHA-256 verification manifests."
            ),
            "tab-features": (
                "**Journey 2: Features & Labels**\n"
                "Computes deterministic technical features (RSI, ATR, Momentum) and next-open-to-following-open net labels "
                "with exact statutory transaction costs (0.224% round-trip)."
            ),
            "tab-training": (
                "**Journey 3: Governed Ridge Training**\n"
                "Fits Ridge classifiers under purged & embargoed cross-validation and multiplicity deflation. "
                "Enforces Marcos López de Prado's Deflated Sharpe Ratio (DSR >= 0.95 gate) before model promotion."
            ),
            "tab-ledger": (
                "**Journey 5: Backtest & Double-Entry Ledger**\n"
                "Executes trading simulations with exact Decimal double-entry ledger accounting, zero float drift, "
                "and realistic fill slippage."
            ),
            "tab-straddle": (
                "**Journey 8: Options Lab & Black-Scholes Greeks**\n"
                "Calculates closed-form Black-Scholes option pricing, Delta, Gamma, Theta, Vega, Rho, and Straddle analytics."
            ),
            "tab-risk": (
                "**Journey 10: Pre-Trade Risk Governor**\n"
                "Enforces institutional pre-trade risk controls: single order value caps, gross exposure ceilings, "
                "daily stop losses, and ±5% price collar protections."
            ),
            "tab-diagnostics": (
                "**Journey 11: System Diagnostics**\n"
                "Real-time diagnostic verification of Double-Entry Decimal ledger reconciliation, Alpha Greek pricing, "
                "and market data provider credentials."
            ),
        }
        return guides.get(
            tab_id, f"You are currently viewing **{self._tab_display_name(tab_id)}**."
        )

    def _parse_option_params(self, text: str) -> tuple[float, float, str]:
        strike_match = re.search(r"\b(2\d{4}|[1-9]\d{3,4})\b", text)
        strike = float(strike_match.group(1)) if strike_match else 24500.0
        spot = strike
        opt_type = "PUT" if re.search(r"\b(put|pe)\b", text, re.IGNORECASE) else "CALL"
        return strike, spot, opt_type

    def _extract_symbol(self, text: str) -> str | None:
        for sym in [
            "INFY",
            "TCS",
            "RELIANCE",
            "HDFCBANK",
            "ICICIBANK",
            "SBIN",
            "BHARTIARTL",
            "LT",
        ]:
            if sym.lower() in text.lower():
                return sym
        return None

    def _try_llm_completion(self, prompt: str, current_tab: str) -> str | None:
        """Attempts to generate a completion using an available LLM provider in the KeyPool."""
        for provider in [
            ProviderType.GROQ,
            ProviderType.ANTHROPIC,
            ProviderType.OPENAI,
            ProviderType.OPENROUTER,
            ProviderType.GEMINI,
            ProviderType.DEEPSEEK,
            ProviderType.MISTRAL,
            ProviderType.LIGHTNING,
        ]:
            key = self.key_pool.get_active_key(provider)
            if not key:
                self.key_pool.load_from_env()
                key = self.key_pool.get_active_key(provider)
            if key:
                client = get_direct_client_for_provider(provider)
                if client is not None:
                    client.json_mode = False  # a chat answer is prose, not a forced JSON object
                    try:
                        system_prompt = (
                            "You are QuantOS Copilot, an institutional quantitative trading assistant. "
                            f"The user is viewing '{current_tab}'. "
                            "Answer concisely in Markdown. Explain quant concepts clearly. "
                            "You CANNOT modify code or files."
                        )
                        content, status, _, err = client.execute(
                            prompt=f"{system_prompt}\nUser: {prompt}",
                            key=key,
                            model=None,
                        )
                        if status == 200 and content:
                            self.key_pool.record_success(key)
                            return str(content)
                        else:
                            logger.warning("LLM request error (%d): %s", status, err)
                            self.key_pool.record_error(key, is_fatal=False)
                    except Exception as exc:
                        logger.warning("LLM completion failed for %s: %s", provider, exc)
                        self.key_pool.record_error(key, is_fatal=False)
        return None
