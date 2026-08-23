"""Immutable, provenance-complete records of what an advisory model said.

Nothing in this module may influence a governed decision. Every record carries
``authority = NON_AUTHORITATIVE`` as a validated field, and the package boundary is asserted by
``tests/test_advisory_isolation.py``: no module under ``modeling/``, ``evidence/``, ``risk/``, or
``execution/`` may import ``quant_system.advisory``.

An advisory record is deliberately weaker evidence than an ``EvidenceStore`` resource. Model
versions drift, providers deprecate endpoints, and an identical prompt returns different text on
different days. These records are therefore tamper-evident and complete, but they are *not*
reproducible, and they are stored apart from governed evidence so that the store's re-verifiability
guarantee is not diluted to the level of its weakest member.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from quant_system.advisory.errors import AdvisoryError, AdvisoryFailureCode
from quant_system.data.market_data_evidence import canonical_sha256, decimal_text, utc_text

_HASH_PATTERN = re.compile(r"\A[0-9a-f]{64}\Z")
# `|` is permitted because real instrument keys in this platform look like `NSE_EQ|INE009A01021`.
_IDENTIFIER_PATTERN = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9 ._:@/+|-]{0,127}\Z")

# Metadata keys that must never reach disk. `masked_key` and `key_id` are emitted today by
# `DirectAPIAdvisor` (`alpha/ai_advisor.py`); they are masked rather than raw, but key material
# shape does not belong on a persistence path.
_SECRET_KEY_PATTERN = re.compile(
    r"(api[_-]?key|secret|token|password|passwd|authorization|bearer|credential"
    r"|private[_-]?key|access[_-]?key|masked[_-]?key|key[_-]?id|session[_-]?id)",
    re.IGNORECASE,
)

# Known live-credential prefixes. Deliberately prefix-based rather than entropy-based so that a
# legitimate 64-character SHA-256 quoted in a rationale is not mistaken for a leaked secret.
_SECRET_VALUE_PATTERN = re.compile(
    r"(sk-ant-[A-Za-z0-9_-]{8,}|sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{16,}"
    r"|gsk_[A-Za-z0-9]{16,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[A-Za-z0-9_-]{20,})"
)

_ZERO = Decimal("0")
_ONE = Decimal("1")


class Authority(StrEnum):
    """The only authority an advisory record may carry."""

    NON_AUTHORITATIVE = "NON_AUTHORITATIVE"


class AdvisoryRecordType(StrEnum):
    OPINION = "OPINION"
    STRATEGY_HYPOTHESIS = "STRATEGY_HYPOTHESIS"


class AdvisorInterface(StrEnum):
    CLI = "CLI"
    DIRECT_API = "DIRECT_API"
    HEURISTIC = "HEURISTIC"
    # A panel verdict is none of the three above. Labelling an aggregate as `CLI` or `DIRECT_API`
    # would assert a single call that never happened.
    AGGREGATE = "AGGREGATE"


class ExecutionMode(StrEnum):
    """How the opinion was actually produced.

    ``HEURISTIC_FALLBACK`` exists because `BaseAIAdvisor._fallback_heuristic` returns a confident
    rule-based verdict whenever no CLI is on PATH and no API key works. Without this field on the
    record, a panel that has silently degraded to one RSI rule is indistinguishable from four
    working models.
    """

    LIVE_MODEL = "LIVE_MODEL"
    HEURISTIC_FALLBACK = "HEURISTIC_FALLBACK"
    # No model was ever attempted: this advisor *is* a rule. Distinct from HEURISTIC_FALLBACK,
    # which means a model was tried and failed. Collapsing the two would make "how often did the
    # panel actually reach a model?" unanswerable, and that is the first question any analysis of
    # this dataset has to ask. `TrendDivergenceRuleAdvisor` and `SignalStrengthRuleAdvisor` are both this.
    DETERMINISTIC_RULE = "DETERMINISTIC_RULE"
    CACHED_REPLAY = "CACHED_REPLAY"
    # An admission, never a default. Correct for a panel *aggregate*, which is a verdict over
    # several advisors rather than a single call — its members carry the real modes. Also used when
    # an advisor emits no recognisable mode marker, where guessing `LIVE_MODEL` would recreate the
    # fail-open this field exists to expose. Counting these is how the dataset reports its own
    # blind spots.
    UNDETERMINED = "UNDETERMINED"


class ActionBias(StrEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    VETO = "VETO"


class HindsightStatus(StrEnum):
    """Whether the model could have known the outcome of the window it was shown.

    ``CONTAMINATED`` is the expected value for any backtest: a model whose pretraining ends after
    the observation window has read what happened next, and no prompt removes that. Recording it as
    ``UNDETERMINED`` when it is knowable would be the actual error.
    """

    CLEAN = "CLEAN"
    CONTAMINATED = "CONTAMINATED"
    UNDETERMINED = "UNDETERMINED"


def _require_utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AdvisoryError(
            AdvisoryFailureCode.TIMESTAMP_NOT_UTC,
            "advisory timestamps must be timezone-aware UTC",
            offending_field=field_name,
        )
    return value


def _require_finite(value: Decimal, field_name: str) -> Decimal:
    if not value.is_finite():
        raise AdvisoryError(
            AdvisoryFailureCode.NON_FINITE_VALUE,
            "advisory decimals must be finite",
            offending_field=field_name,
        )
    return value


def _require_identifier(value: str, field_name: str) -> str:
    if not _IDENTIFIER_PATTERN.fullmatch(value):
        raise AdvisoryError(
            AdvisoryFailureCode.PROVENANCE_INCOMPLETE,
            f"{field_name} must be a non-empty identifier of at most 128 characters",
            offending_field=field_name,
        )
    return value


def _scan_value_for_secrets(value: Any, path: str, field_name: str) -> None:
    """Recurse through nested containers. A flat scan misses `{"opinions": ["sk-ant-..."]}`."""
    if isinstance(value, str):
        if _SECRET_VALUE_PATTERN.search(value):
            raise AdvisoryError(
                AdvisoryFailureCode.SECRET_MATERIAL_PRESENT,
                f"metadata value at {path} matches a known credential prefix",
                offending_field=field_name,
            )
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _reject_secret_key(key, f"{path}.{key}", field_name)
            _scan_value_for_secrets(item, f"{path}.{key}", field_name)
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _scan_value_for_secrets(item, f"{path}[{index}]", field_name)


def _reject_secret_key(key: Any, path: str, field_name: str) -> None:
    if _SECRET_KEY_PATTERN.search(str(key)):
        raise AdvisoryError(
            AdvisoryFailureCode.SECRET_MATERIAL_PRESENT,
            f"metadata key at {path} is credential-shaped and must not be persisted",
            offending_field=field_name,
        )


def reject_secret_material(payload: Mapping[str, Any], field_name: str) -> None:
    """Fail closed when a mapping carries credential-shaped keys or values, at any depth.

    Enforced at record construction rather than at write time so that a secret cannot exist in a
    sealed record even in memory. The scan recurses because the panel emits nested structures —
    `MultiAgentConsensusEngine` puts a list of per-advisor rationales under `individual_opinions`,
    and a flat scan would never look inside it.
    """
    for key, value in payload.items():
        _reject_secret_key(key, str(key), field_name)
        _scan_value_for_secrets(value, str(key), field_name)


def _scan_text_for_secrets(value: str, field_name: str) -> str:
    if _SECRET_VALUE_PATTERN.search(value):
        raise AdvisoryError(
            AdvisoryFailureCode.SECRET_MATERIAL_PRESENT,
            f"{field_name} matches a known credential prefix",
            offending_field=field_name,
        )
    return value


@dataclass(frozen=True, slots=True)
class ModelIdentity:
    """Exactly which model produced an opinion, and how far its knowledge reaches.

    ``knowledge_cutoff`` is *declared*, not verified — no API reports it reliably. It is recorded so
    that hindsight contamination can be computed rather than guessed, and ``None`` is honest when
    the cutoff is genuinely unknown.
    """

    provider: str
    model_id: str
    interface: AdvisorInterface
    model_version: str | None = None
    knowledge_cutoff: date | None = None

    def __post_init__(self) -> None:
        _require_identifier(self.provider, "model.provider")
        _require_identifier(self.model_id, "model.model_id")
        if self.model_version is not None:
            _require_identifier(self.model_version, "model.model_version")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model_id": self.model_id,
            "interface": self.interface.value,
            "model_version": self.model_version,
            "knowledge_cutoff": (
                self.knowledge_cutoff.isoformat() if self.knowledge_cutoff is not None else None
            ),
        }


def _hindsight_status(
    model: ModelIdentity,
    observation_window_end: date | None,
) -> HindsightStatus:
    if model.knowledge_cutoff is None or observation_window_end is None:
        return HindsightStatus.UNDETERMINED
    if model.knowledge_cutoff > observation_window_end:
        return HindsightStatus.CONTAMINATED
    return HindsightStatus.CLEAN


@dataclass(frozen=True, slots=True)
class AdvisoryOpinionRecord:
    """One model's opinion on one instrument, recorded but never obeyed."""

    recorded_at: datetime
    advisor_name: str
    model: ModelIdentity
    execution_mode: ExecutionMode
    symbol: str
    action_bias: ActionBias
    confidence: Decimal
    weight_multiplier: Decimal
    rationale: str
    prompt_sha256: str
    anchored_on_quant_signal: bool
    observation_window_end: date | None = None
    quant_side_shown: str | None = None
    quant_strength_shown: Decimal | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    authority: Authority = Authority.NON_AUTHORITATIVE
    record_type: AdvisoryRecordType = AdvisoryRecordType.OPINION

    def __post_init__(self) -> None:
        if self.authority is not Authority.NON_AUTHORITATIVE:
            raise AdvisoryError(
                AdvisoryFailureCode.AUTHORITY_ESCALATION_ATTEMPTED,
                "advisory records are non-authoritative by construction",
                offending_field="authority",
            )
        if self.record_type is not AdvisoryRecordType.OPINION:
            raise AdvisoryError(
                AdvisoryFailureCode.JOURNAL_RECORD_MALFORMED,
                "record_type must be OPINION",
                offending_field="record_type",
            )
        _require_utc(self.recorded_at, "recorded_at")
        _require_identifier(self.advisor_name, "advisor_name")
        _require_identifier(self.symbol, "symbol")
        _require_finite(self.confidence, "confidence")
        _require_finite(self.weight_multiplier, "weight_multiplier")
        if not _ZERO <= self.confidence <= _ONE:
            raise AdvisoryError(
                AdvisoryFailureCode.CONFIDENCE_OUT_OF_RANGE,
                f"confidence must lie in [0, 1]; got {self.confidence}",
                offending_field="confidence",
            )
        if self.weight_multiplier < _ZERO:
            raise AdvisoryError(
                AdvisoryFailureCode.WEIGHT_MULTIPLIER_INVALID,
                f"weight_multiplier must be non-negative; got {self.weight_multiplier}",
                offending_field="weight_multiplier",
            )
        if self.quant_strength_shown is not None:
            _require_finite(self.quant_strength_shown, "quant_strength_shown")
        if not _HASH_PATTERN.fullmatch(self.prompt_sha256):
            raise AdvisoryError(
                AdvisoryFailureCode.HASH_INVALID,
                "prompt_sha256 must be 64 lowercase hex characters",
                offending_field="prompt_sha256",
            )
        # An opinion claiming it was not anchored, while carrying the quant answer it was shown,
        # is self-contradictory and would corrupt any later independence analysis.
        if not self.anchored_on_quant_signal and (
            self.quant_side_shown is not None or self.quant_strength_shown is not None
        ):
            raise AdvisoryError(
                AdvisoryFailureCode.PROVENANCE_INCOMPLETE,
                "record claims no anchoring but carries the quant signal it was shown",
                offending_field="anchored_on_quant_signal",
            )
        _scan_text_for_secrets(self.rationale, "rationale")
        reject_secret_material(self.metadata, "metadata")

    @property
    def hindsight(self) -> HindsightStatus:
        return _hindsight_status(self.model, self.observation_window_end)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "record_type": self.record_type.value,
            "authority": self.authority.value,
            "recorded_at": utc_text(self.recorded_at),
            "advisor_name": self.advisor_name,
            "model": self.model.canonical_payload(),
            "execution_mode": self.execution_mode.value,
            "symbol": self.symbol,
            "action_bias": self.action_bias.value,
            "confidence": decimal_text(self.confidence),
            "weight_multiplier": decimal_text(self.weight_multiplier),
            "rationale": self.rationale,
            "prompt_sha256": self.prompt_sha256,
            "anchored_on_quant_signal": self.anchored_on_quant_signal,
            "observation_window_end": (
                self.observation_window_end.isoformat()
                if self.observation_window_end is not None
                else None
            ),
            "quant_side_shown": self.quant_side_shown,
            "quant_strength_shown": (
                decimal_text(self.quant_strength_shown)
                if self.quant_strength_shown is not None
                else None
            ),
            "hindsight": self.hindsight.value,
            "metadata": dict(self.metadata),
        }

    def content_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())


@dataclass(frozen=True, slots=True)
class StrategyHypothesisRecord:
    """A strategy or pattern hypothesis proposed by a reasoning model.

    This is the countable use of an LLM. A per-bar forecast cannot be deflated against, because the
    attempts are unbounded and invisible; a hypothesis can, because it is one declared attempt.
    ``trial_ordinal`` stays ``None`` until the hypothesis is registered against the multiplicity
    counter, and :meth:`assert_registered_for_backtest` refuses to let an unregistered hypothesis
    become a backtest — that path is undeclared multiplicity, which is exactly how the 51-trial
    NIFTY campaign recorded in ``agent_context/CURRENT.md`` would have manufactured a false
    positive had its ordinals not been counted.
    """

    recorded_at: datetime
    hypothesis_id: str
    title: str
    model: ModelIdentity
    execution_mode: ExecutionMode
    reasoning: str
    proposed_rule: str
    prompt_sha256: str
    universe_scope: str | None = None
    observation_window_end: date | None = None
    trial_ordinal: int | None = None
    registered_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    authority: Authority = Authority.NON_AUTHORITATIVE
    record_type: AdvisoryRecordType = AdvisoryRecordType.STRATEGY_HYPOTHESIS

    def __post_init__(self) -> None:
        if self.authority is not Authority.NON_AUTHORITATIVE:
            raise AdvisoryError(
                AdvisoryFailureCode.AUTHORITY_ESCALATION_ATTEMPTED,
                "advisory records are non-authoritative by construction",
                offending_field="authority",
            )
        if self.record_type is not AdvisoryRecordType.STRATEGY_HYPOTHESIS:
            raise AdvisoryError(
                AdvisoryFailureCode.JOURNAL_RECORD_MALFORMED,
                "record_type must be STRATEGY_HYPOTHESIS",
                offending_field="record_type",
            )
        _require_utc(self.recorded_at, "recorded_at")
        _require_identifier(self.hypothesis_id, "hypothesis_id")
        _require_identifier(self.title, "title")
        if self.universe_scope is not None:
            _require_identifier(self.universe_scope, "universe_scope")
        if not _HASH_PATTERN.fullmatch(self.prompt_sha256):
            raise AdvisoryError(
                AdvisoryFailureCode.HASH_INVALID,
                "prompt_sha256 must be 64 lowercase hex characters",
                offending_field="prompt_sha256",
            )
        if self.trial_ordinal is not None:
            if self.trial_ordinal < 1:
                raise AdvisoryError(
                    AdvisoryFailureCode.TRIAL_ORDINAL_INVALID,
                    f"trial_ordinal must be >= 1; got {self.trial_ordinal}",
                    offending_field="trial_ordinal",
                )
            if self.registered_at is None:
                raise AdvisoryError(
                    AdvisoryFailureCode.PROVENANCE_INCOMPLETE,
                    "a registered hypothesis must record when it was registered",
                    offending_field="registered_at",
                )
        if self.registered_at is not None:
            _require_utc(self.registered_at, "registered_at")
            if self.trial_ordinal is None:
                raise AdvisoryError(
                    AdvisoryFailureCode.PROVENANCE_INCOMPLETE,
                    "registered_at is set but no trial ordinal was spent",
                    offending_field="trial_ordinal",
                )
        _scan_text_for_secrets(self.reasoning, "reasoning")
        _scan_text_for_secrets(self.proposed_rule, "proposed_rule")
        reject_secret_material(self.metadata, "metadata")

    @property
    def hindsight(self) -> HindsightStatus:
        return _hindsight_status(self.model, self.observation_window_end)

    @property
    def is_registered(self) -> bool:
        return self.trial_ordinal is not None

    def register(self, trial_ordinal: int, registered_at: datetime) -> StrategyHypothesisRecord:
        """Return a copy that has spent one trial ordinal. Registration is not reversible."""
        if self.trial_ordinal is not None:
            raise AdvisoryError(
                AdvisoryFailureCode.HYPOTHESIS_ALREADY_REGISTERED,
                f"hypothesis {self.hypothesis_id} already holds ordinal {self.trial_ordinal}",
                offending_field="trial_ordinal",
            )
        return replace(self, trial_ordinal=trial_ordinal, registered_at=registered_at)

    def assert_registered_for_backtest(self) -> None:
        """Fail closed when an unregistered hypothesis is about to be tested."""
        if self.trial_ordinal is None:
            raise AdvisoryError(
                AdvisoryFailureCode.HYPOTHESIS_NOT_REGISTERED,
                (
                    f"hypothesis {self.hypothesis_id} has not spent a trial ordinal; "
                    "backtesting it would be undeclared multiplicity"
                ),
                offending_field="trial_ordinal",
            )

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "record_type": self.record_type.value,
            "authority": self.authority.value,
            "recorded_at": utc_text(self.recorded_at),
            "hypothesis_id": self.hypothesis_id,
            "title": self.title,
            "model": self.model.canonical_payload(),
            "execution_mode": self.execution_mode.value,
            "reasoning": self.reasoning,
            "proposed_rule": self.proposed_rule,
            "prompt_sha256": self.prompt_sha256,
            "universe_scope": self.universe_scope,
            "observation_window_end": (
                self.observation_window_end.isoformat()
                if self.observation_window_end is not None
                else None
            ),
            "trial_ordinal": self.trial_ordinal,
            "registered_at": (
                utc_text(self.registered_at) if self.registered_at is not None else None
            ),
            "hindsight": self.hindsight.value,
            "metadata": dict(self.metadata),
        }

    def content_sha256(self) -> str:
        return canonical_sha256(self.canonical_payload())


AdvisoryRecord = AdvisoryOpinionRecord | StrategyHypothesisRecord
