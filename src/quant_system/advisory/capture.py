"""Adapter turning a live advisory opinion into a sealed, non-authoritative record.

The advisory panel is not imported here. `capture_opinion` accepts anything structurally shaped like
`quant_system.alpha.ai_advisor.AIOpinion` via :class:`SupportsAIOpinion`, so this package stays a
leaf: it depends on canonical hashing and nothing else in the platform. That keeps the one-way
boundary — ``advisory`` may observe the panel, the panel may never reach back.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from quant_system.advisory.errors import AdvisoryError, AdvisoryFailureCode
from quant_system.advisory.records import (
    ActionBias,
    AdvisorInterface,
    AdvisoryOpinionRecord,
    ExecutionMode,
    ModelIdentity,
    StrategyHypothesisRecord,
)
from quant_system.data.market_data_evidence import canonical_sha256

# Keys stripped from captured metadata before a record is built. The panel emits `key_id` and
# `masked_key` today; they are masked rather than raw, but key-shaped material does not belong on a
# persistence path, and `records.reject_secret_material` would refuse the record outright.
_STRIPPED_METADATA_KEYS = frozenset(
    {
        "key_id",
        "masked_key",
        "api_key",
        "apikey",
        "token",
        "secret",
        "password",
        "authorization",
        "credential",
        "access_key",
        "private_key",
        "session_id",
    }
)


# The panel's own `metadata["mode"]` strings, mapped to what they actually mean. Kept here rather
# than in `alpha/` so the advisory layer owns its own interpretation of what it observes.
_MODE_MARKERS = {
    "CLI_SUBSCRIPTION": ExecutionMode.LIVE_MODEL,
    "DIRECT_API": ExecutionMode.LIVE_MODEL,
    "HEURISTIC_FALLBACK": ExecutionMode.HEURISTIC_FALLBACK,
    "DETERMINISTIC_RULE": ExecutionMode.DETERMINISTIC_RULE,
    "CACHED_REPLAY": ExecutionMode.CACHED_REPLAY,
}

# How the member was actually reached. A rule-based advisor recorded as `AGGREGATE` — the panel's
# own interface — would misdescribe it, so each member's interface is derived from its own marker.
_MARKER_INTERFACES = {
    "CLI_SUBSCRIPTION": AdvisorInterface.CLI,
    "DIRECT_API": AdvisorInterface.DIRECT_API,
    "HEURISTIC_FALLBACK": AdvisorInterface.HEURISTIC,
    "DETERMINISTIC_RULE": AdvisorInterface.HEURISTIC,
}


class SupportsAIOpinion(Protocol):
    """The structural shape of an advisory opinion, without importing the panel."""

    @property
    def advisor_name(self) -> str: ...

    @property
    def action_bias(self) -> str: ...

    @property
    def confidence(self) -> float: ...

    @property
    def rationale(self) -> str: ...

    @property
    def weight_multiplier(self) -> float: ...

    @property
    def metadata(self) -> Mapping[str, Any]: ...


def prompt_fingerprint(prompt: str) -> str:
    """SHA-256 of the exact prompt text, so prompt drift is detectable after the fact."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def observation_fingerprint(observation: Mapping[str, Any]) -> str:
    """SHA-256 of what a panel was shown, for callers that never see the rendered prompt.

    Each advisor builds its prompt text privately inside `evaluate_opportunity`, so a strategy can
    attest to the *input* it handed the panel but not to the words any advisor sent. Hashing the
    input canonically is the faithful answer at that layer.

    Values are stringified before hashing: canonical JSON rejects non-finite floats, and a `NaN`
    arriving from an indicator series must not raise inside a fingerprint and cost a record.
    """
    normalized = {str(key): str(value) for key, value in observation.items()}
    return canonical_sha256(normalized)


def sanitize_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Drop credential-shaped keys. Values are left to the record's own secret scan."""
    return {
        str(key): value
        for key, value in metadata.items()
        if str(key).casefold() not in _STRIPPED_METADATA_KEYS
    }


def infer_execution_mode(opinion: SupportsAIOpinion) -> ExecutionMode | None:
    """Best-effort read of the panel's own mode marker.

    Every `AIOpinion` construction site in `alpha/ai_advisor.py` now emits a marker, but a
    third-party or future advisor need not, and a panel aggregate deliberately carries none of its
    own. ``None`` therefore still means *undetermined*, never *live* — absence of a marker is not
    evidence a model answered. This helper exists to be checked, not to supply a default.
    """
    return _MODE_MARKERS.get(str(opinion.metadata.get("mode")))


def _to_decimal(value: float, field_name: str) -> Decimal:
    try:
        converted = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise AdvisoryError(
            AdvisoryFailureCode.NON_FINITE_VALUE,
            f"{field_name} is not convertible to Decimal: {value!r}",
            offending_field=field_name,
        ) from exc
    if not converted.is_finite():
        raise AdvisoryError(
            AdvisoryFailureCode.NON_FINITE_VALUE,
            f"{field_name} must be finite; got {value!r}",
            offending_field=field_name,
        )
    return converted


def _to_action_bias(raw: str) -> ActionBias:
    try:
        return ActionBias(raw.strip().upper())
    except ValueError as exc:
        raise AdvisoryError(
            AdvisoryFailureCode.JOURNAL_RECORD_MALFORMED,
            f"unrecognised action_bias {raw!r}",
            offending_field="action_bias",
        ) from exc


def _resolve_prompt_hash(prompt: str | None, prompt_sha256: str | None) -> str:
    if (prompt is None) == (prompt_sha256 is None):
        raise AdvisoryError(
            AdvisoryFailureCode.PROVENANCE_INCOMPLETE,
            "supply exactly one of prompt or prompt_sha256",
            offending_field="prompt",
        )
    return prompt_sha256 if prompt_sha256 is not None else prompt_fingerprint(str(prompt))


def capture_opinion(
    opinion: SupportsAIOpinion,
    *,
    symbol: str,
    model: ModelIdentity,
    execution_mode: ExecutionMode,
    recorded_at: datetime,
    anchored_on_quant_signal: bool,
    prompt: str | None = None,
    prompt_sha256: str | None = None,
    observation_window_end: date | None = None,
    quant_side_shown: str | None = None,
    quant_strength_shown: Decimal | None = None,
    extra_metadata: Mapping[str, Any] | None = None,
) -> AdvisoryOpinionRecord:
    """Seal one advisory opinion. Recording it must never change what the caller then does.

    Supply exactly one of ``prompt`` (raw text, hashed here) or ``prompt_sha256`` (already hashed,
    for callers that never see the rendered prompt and fingerprint the observation instead).

    ``execution_mode`` is required rather than inferred: see :func:`infer_execution_mode` for why a
    missing marker cannot be read as a live model response.
    """
    metadata = sanitize_metadata(opinion.metadata)
    if extra_metadata:
        metadata.update(sanitize_metadata(extra_metadata))

    return AdvisoryOpinionRecord(
        recorded_at=recorded_at,
        advisor_name=opinion.advisor_name,
        model=model,
        execution_mode=execution_mode,
        symbol=symbol,
        action_bias=_to_action_bias(opinion.action_bias),
        confidence=_to_decimal(opinion.confidence, "confidence"),
        weight_multiplier=_to_decimal(opinion.weight_multiplier, "weight_multiplier"),
        rationale=opinion.rationale,
        prompt_sha256=_resolve_prompt_hash(prompt, prompt_sha256),
        anchored_on_quant_signal=anchored_on_quant_signal,
        observation_window_end=observation_window_end,
        quant_side_shown=quant_side_shown,
        quant_strength_shown=quant_strength_shown,
        metadata=metadata,
    )


def capture_panel_members(
    aggregate: SupportsAIOpinion,
    *,
    symbol: str,
    model: ModelIdentity,
    recorded_at: datetime,
    anchored_on_quant_signal: bool,
    prompt_sha256: str,
    observation_window_end: date | None = None,
    quant_side_shown: str | None = None,
    quant_strength_shown: Decimal | None = None,
    extra_metadata: Mapping[str, Any] | None = None,
) -> list[AdvisoryOpinionRecord]:
    """Expand a panel aggregate into one record per advisor, each with its own execution mode.

    Reads the `panel_members` detail that `MultiAgentConsensusEngine` attaches. Returns an empty
    list when that key is absent, so a panel that has not been taught to preserve provenance
    degrades to aggregate-only capture rather than failing.

    Each member's mode comes from its own marker; a member whose mode cannot be resolved is
    recorded as ``UNDETERMINED`` rather than assumed live.
    """
    members = aggregate.metadata.get("panel_members")
    if not isinstance(members, (list, tuple)):
        return []

    records: list[AdvisoryOpinionRecord] = []
    for member in members:
        if not isinstance(member, Mapping):
            continue
        raw_mode = str(member.get("mode"))
        mode = _MODE_MARKERS.get(raw_mode, ExecutionMode.UNDETERMINED)
        advisor_name = str(member.get("advisor_name", "unknown_advisor"))
        metadata: dict[str, Any] = {"panel_role": "MEMBER"}
        if extra_metadata:
            metadata.update(sanitize_metadata(extra_metadata))

        # The member is its own thing, not the panel: name it and describe how it was reached.
        member_model = ModelIdentity(
            provider=model.provider,
            model_id=advisor_name,
            interface=_MARKER_INTERFACES.get(raw_mode, model.interface),
            model_version=model.model_version,
            knowledge_cutoff=model.knowledge_cutoff,
        )

        records.append(
            AdvisoryOpinionRecord(
                recorded_at=recorded_at,
                advisor_name=advisor_name,
                model=member_model,
                execution_mode=mode,
                symbol=symbol,
                action_bias=_to_action_bias(str(member.get("action_bias", "NEUTRAL"))),
                confidence=_to_decimal(float(member.get("confidence", 0.0)), "confidence"),
                weight_multiplier=_to_decimal(
                    float(member.get("weight_multiplier", 0.0)), "weight_multiplier"
                ),
                rationale=str(member.get("rationale", "")),
                prompt_sha256=prompt_sha256,
                anchored_on_quant_signal=anchored_on_quant_signal,
                observation_window_end=observation_window_end,
                quant_side_shown=quant_side_shown,
                quant_strength_shown=quant_strength_shown,
                metadata=metadata,
            )
        )
    return records


def capture_hypothesis(
    *,
    title: str,
    model: ModelIdentity,
    prompt: str,
    reasoning: str,
    proposed_rule: str,
    execution_mode: ExecutionMode,
    recorded_at: datetime,
    hypothesis_id: str | None = None,
    universe_scope: str | None = None,
    observation_window_end: date | None = None,
    extra_metadata: Mapping[str, Any] | None = None,
) -> StrategyHypothesisRecord:
    """Seal one strategy or pattern hypothesis, unregistered.

    The returned record holds no trial ordinal. It must be registered against the multiplicity
    counter before it is backtested; :meth:`StrategyHypothesisRecord.assert_registered_for_backtest`
    is the guard.
    """
    if hypothesis_id is None:
        seed = "\x00".join((title, proposed_rule))
        derived_id = f"hyp_{prompt_fingerprint(seed)[:24]}"
    else:
        derived_id = hypothesis_id
    metadata = sanitize_metadata(extra_metadata) if extra_metadata else {}

    return StrategyHypothesisRecord(
        recorded_at=recorded_at,
        hypothesis_id=derived_id,
        title=title,
        model=model,
        execution_mode=execution_mode,
        reasoning=reasoning,
        proposed_rule=proposed_rule,
        prompt_sha256=prompt_fingerprint(prompt),
        universe_scope=universe_scope,
        observation_window_end=observation_window_end,
        metadata=metadata,
    )
