"""Constants and descriptors for the 7 QuantOS Core User Journeys."""

from __future__ import annotations

from typing import Any

# Identifiers for the 7 core journeys
JOURNEY_INGESTION_ID = "ingestion"
JOURNEY_FEATURES_ID = "features"
JOURNEY_TRAINING_ID = "training"
JOURNEY_HOLDOUT_ID = "holdout"
JOURNEY_LEDGER_ID = "ledger"
JOURNEY_SHADOW_ID = "shadow"
JOURNEY_PILOT_ID = "pilot"

JOURNEY_METADATA: list[dict[str, Any]] = [
    {
        "id": JOURNEY_INGESTION_ID,
        "title": "Data Ingestion & Manifest Inspection",
        "nav_label": "📥 Data & Manifests",
        "description": "Point-in-time NSE equity data acquisition, SHA-256 manifest inspection, quality checks, and provenance verification.",
        "icon": "database",
        "route_path": f"/ui/journey/{JOURNEY_INGESTION_ID}",
        "badge": "UPSTOX_V3 / SYNTHETIC",
        "data_test": "journey-ingestion",
        "status": "ONLINE",
    },
    {
        "id": JOURNEY_FEATURES_ID,
        "title": "Feature Matrix & Label Explorer",
        "nav_label": "📐 Features & Labels",
        "description": "Governed 6-feature schema generation, decision-time alignment, next-open labels, net friction costs, and embargo enforcement.",
        "icon": "layers",
        "route_path": f"/ui/journey/{JOURNEY_FEATURES_ID}",
        "badge": "GOVERNED_PIT",
        "data_test": "journey-features",
        "status": "ONLINE",
    },
    {
        "id": JOURNEY_TRAINING_ID,
        "title": "Governed Ridge Training & Baseline Comparison",
        "nav_label": "🧠 Governed Ridge",
        "description": "Expanding walk-forward fold fitting, train-side standardization, multiplicity tracking, Deflated Sharpe, and comparison against 4 baselines.",
        "icon": "cpu",
        "route_path": f"/ui/journey/{JOURNEY_TRAINING_ID}",
        "badge": "RESEARCH_ONLY",
        "data_test": "journey-training",
        "status": "ONLINE",
    },
    {
        "id": JOURNEY_HOLDOUT_ID,
        "title": "Single-use Holdout & Stress Testing Tearsheet",
        "nav_label": "🔒 Holdout & Stress",
        "description": "Single-use holdout gate evaluation, volatility/liquidity stress tests, tail-risk CVaR analysis, and model card export.",
        "icon": "shield-check",
        "route_path": f"/ui/journey/{JOURNEY_HOLDOUT_ID}",
        "badge": "SINGLE_USE_LOCK",
        "data_test": "journey-holdout",
        "status": "ONLINE",
    },
    {
        "id": JOURNEY_LEDGER_ID,
        "title": "Ledger & Backtest P&L Tearsheet",
        "nav_label": "📊 Backtest & Ledger",
        "description": "Decimal double-entry accounting reconciliation, zero lookahead event-driven backtesting, friction breakdown, and tearsheet generation.",
        "icon": "file-text",
        "route_path": f"/ui/journey/{JOURNEY_LEDGER_ID}",
        "badge": "DECIMAL_EXACT",
        "data_test": "journey-ledger",
        "status": "ONLINE",
    },
    {
        "id": JOURNEY_SHADOW_ID,
        "title": "Real-Time / Replay Shadow Monitor",
        "nav_label": "👁️ Shadow Monitor",
        "description": "Read-only live quote feed and recorded shadow replay with zero broker write guarantee, latency tracking, and decision attribution.",
        "icon": "activity",
        "route_path": f"/ui/journey/{JOURNEY_SHADOW_ID}",
        "badge": "READ_ONLY",
        "data_test": "journey-shadow",
        "status": "ONLINE",
    },
    {
        "id": JOURNEY_PILOT_ID,
        "title": "Paper Pilot Campaign Dashboard",
        "nav_label": "🚀 Paper Pilot",
        "description": "Simulated quote-driven execution with bid/ask depth, adverse slippage, partial fills, idempotency verification, and risk bounds.",
        "icon": "crosshair",
        "route_path": f"/ui/journey/{JOURNEY_PILOT_ID}",
        "badge": "PAPER_SIM",
        "data_test": "journey-pilot",
        "status": "ONLINE",
    },
]

VALID_JOURNEY_IDS = {item["id"] for item in JOURNEY_METADATA}
