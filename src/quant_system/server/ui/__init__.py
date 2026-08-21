"""QuantOS UI Package supporting the 7 Core User Journeys."""

from __future__ import annotations

from quant_system.server.ui.constants import (
    JOURNEY_FEATURES_ID,
    JOURNEY_HOLDOUT_ID,
    JOURNEY_INGESTION_ID,
    JOURNEY_LEDGER_ID,
    JOURNEY_METADATA,
    JOURNEY_PILOT_ID,
    JOURNEY_SHADOW_ID,
    JOURNEY_TRAINING_ID,
    VALID_JOURNEY_IDS,
)
from quant_system.server.ui.templates import (
    render_error_page,
    render_full_dashboard_html,
    render_standalone_journey_html,
)

__all__ = [
    "JOURNEY_INGESTION_ID",
    "JOURNEY_FEATURES_ID",
    "JOURNEY_TRAINING_ID",
    "JOURNEY_HOLDOUT_ID",
    "JOURNEY_LEDGER_ID",
    "JOURNEY_SHADOW_ID",
    "JOURNEY_PILOT_ID",
    "JOURNEY_METADATA",
    "VALID_JOURNEY_IDS",
    "render_full_dashboard_html",
    "render_standalone_journey_html",
    "render_error_page",
]
