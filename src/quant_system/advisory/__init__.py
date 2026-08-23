"""Non-authoritative advisory journal: record what a model said, never obey it.

This package observes an LLM advisory panel and seals what it produced into a tamper-evident
journal. It holds no vote, no gate, and no promotion path. ``tests/test_advisory_isolation.py``
asserts that no module under ``modeling/``, ``evidence/``, ``risk/``, or ``execution/`` imports it,
so observer mode is a property of the build rather than of anyone's discipline.
"""

from quant_system.advisory.capture import (
    SupportsAIOpinion,
    capture_hypothesis,
    capture_opinion,
    capture_panel_members,
    infer_execution_mode,
    observation_fingerprint,
    prompt_fingerprint,
    sanitize_metadata,
)
from quant_system.advisory.errors import AdvisoryError, AdvisoryFailureCode
from quant_system.advisory.journal import GENESIS_SHA256, AdvisoryJournal, JournalEntry
from quant_system.advisory.records import (
    ActionBias,
    AdvisorInterface,
    AdvisoryOpinionRecord,
    AdvisoryRecord,
    AdvisoryRecordType,
    Authority,
    ExecutionMode,
    HindsightStatus,
    ModelIdentity,
    StrategyHypothesisRecord,
    reject_secret_material,
)
from quant_system.advisory.registry import HypothesisRegistry

__all__ = [
    "GENESIS_SHA256",
    "ActionBias",
    "AdvisorInterface",
    "AdvisoryError",
    "AdvisoryFailureCode",
    "AdvisoryJournal",
    "AdvisoryOpinionRecord",
    "AdvisoryRecord",
    "AdvisoryRecordType",
    "Authority",
    "ExecutionMode",
    "HindsightStatus",
    "HypothesisRegistry",
    "JournalEntry",
    "ModelIdentity",
    "StrategyHypothesisRecord",
    "SupportsAIOpinion",
    "capture_hypothesis",
    "capture_opinion",
    "capture_panel_members",
    "infer_execution_mode",
    "observation_fingerprint",
    "prompt_fingerprint",
    "reject_secret_material",
    "sanitize_metadata",
]
