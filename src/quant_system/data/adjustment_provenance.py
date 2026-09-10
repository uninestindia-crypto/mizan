"""Versioned provenance for corporate-action-adjusted price series.

Why this module exists
----------------------
``DatasetManifest.to_canonical_dict`` used to emit the literal::

    "adjustment": {"method": "PROVIDER_UNSPECIFIED", "status": "RAW"}

for every dataset, unconditionally. That is honest for a provider response and dishonest for
anything derived from one: a series that has had demerger factors applied is not RAW, but the
manifest said it was, permanently and immutably. Any governed evidence built on adjusted bars
therefore carried a false provenance claim -- the exact defect class the adjustment work exists to
remove.

The rule this module encodes is the one from ``point-in-time-market-data``: *preserve raw
observations; derive corrected datasets reproducibly with a versioned transformation manifest.* The
provider's own acquisition keeps its RAW manifest and its existing hash forever. An adjusted series
is a **separate derived artifact** whose manifest carries an :class:`AdjustmentReference` binding
the method, the authority, the code revision, the derivation time, the source dataset hash and every
individual factor. Two series that differ in adjustment cannot collide on one identity.

What an adjustment may and may not claim
----------------------------------------
A factor is only as trustworthy as the evidence that sized it, so every factor carries its own
:class:`FactorValidation`:

``PARSED_AND_GAP_CONFIRMED``
    The authority published a ratio *and* the ex-date gap corroborates that the provider had not
    already applied it. Two independent sources agree on the number.

``INDEPENDENTLY_VALIDATED``
    A ratio-less action (a demerger) whose size was corroborated against evidence outside the price
    gap itself. The corroborating evidence is named in ``detail``.

``GAP_INFERRED_ONLY``
    A ratio-less action sized from the ex-date gap and nothing else. **This is not proof of the
    adjustment amount.** A gap is the sum of the corporate action and whatever the market did that
    day, so dividing it out erases genuine market movement along with the action. Consumers that
    compute returns must treat these as *unresolved* rather than apply them -- see
    :func:`spans_unresolved`.

``DIVIDEND_POLICY``
    A dividend removed because the configured return basis is total return. No gap can corroborate
    this and none is claimed: it is a return-definition choice, not the repair of a provider error.

The distinction matters most for labels. Applying a gap-inferred factor to a training target would
manufacture a return of exactly zero across the event -- which looks like a clean correction and is
in fact a fabricated observation. Refusing the label instead loses a handful of rows and keeps the
dataset honest.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Final

__all__ = [
    "ADJUSTMENT_METHOD_V1",
    "ADJUSTMENT_METHOD_VERSION_V1",
    "AdjustmentBasis",
    "AdjustmentFactorRecord",
    "AdjustmentProvenanceError",
    "AdjustmentReference",
    "AdjustmentStatus",
    "FactorValidation",
    "UnresolvedAction",
    "carry_factor",
    "spans_unresolved",
]

ADJUSTMENT_METHOD_V1: Final = "quantos.corporate_action_backadjust"
"""Identifier of the transformation implemented by ``quant_system.data.corporate_actions``."""

ADJUSTMENT_METHOD_VERSION_V1: Final = 1
"""Bump when the arithmetic changes, so two derived series cannot share one identity."""


class AdjustmentProvenanceError(ValueError):
    """An adjustment reference could not be constructed from defensible evidence."""


class AdjustmentStatus(StrEnum):
    """Whether a series carries provider values or derived ones."""

    RAW = "RAW"
    ADJUSTED = "ADJUSTED"


class AdjustmentBasis(StrEnum):
    """Which return definition the derived series expresses."""

    PRICE_RETURN = "PRICE_RETURN"
    """Structural actions removed; a dividend still shows as a price drop."""

    TOTAL_RETURN = "TOTAL_RETURN"
    """Structural actions *and* dividends removed."""


class FactorValidation(StrEnum):
    """The strength of the evidence that sized one factor. See the module docstring."""

    PARSED_AND_GAP_CONFIRMED = "PARSED_AND_GAP_CONFIRMED"
    INDEPENDENTLY_VALIDATED = "INDEPENDENTLY_VALIDATED"
    GAP_INFERRED_ONLY = "GAP_INFERRED_ONLY"
    DIVIDEND_POLICY = "DIVIDEND_POLICY"

    @property
    def is_corroborated(self) -> bool:
        """Whether a return calculation may divide this factor out.

        ``GAP_INFERRED_ONLY`` is excluded deliberately: the gap is the only evidence of the size, so
        removing it removes the day's genuine market movement too.
        """
        return self in (
            FactorValidation.PARSED_AND_GAP_CONFIRMED,
            FactorValidation.INDEPENDENTLY_VALIDATED,
            FactorValidation.DIVIDEND_POLICY,
        )


@dataclass(frozen=True, slots=True)
class AdjustmentFactorRecord:
    """One price multiplier applied to every bar strictly before ``ex_date``."""

    ex_date: date
    factor: Decimal
    kinds: tuple[str, ...]
    validation: FactorValidation
    detail: str

    def __post_init__(self) -> None:
        if self.factor <= 0:
            raise AdjustmentProvenanceError(
                f"non-positive adjustment factor {self.factor} on {self.ex_date.isoformat()}"
            )

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "detail": self.detail,
            "ex_date": self.ex_date.isoformat(),
            "factor": format(self.factor.normalize(), "f"),
            "kinds": list(self.kinds),
            "validation": self.validation.value,
        }


@dataclass(frozen=True, slots=True)
class UnresolvedAction:
    """A corporate action that could not be sized from defensible evidence.

    Recorded rather than dropped. A consumer that spans one of these ex-dates is computing a return
    across an event of unknown size, which is not a measurement; :func:`spans_unresolved` lets it
    refuse instead of guessing.
    """

    ex_date: date
    reason: str
    subject: str

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "ex_date": self.ex_date.isoformat(),
            "reason": self.reason,
            "subject": self.subject,
        }


@dataclass(frozen=True, slots=True)
class AdjustmentReference:
    """Complete, hashable provenance for one derived adjusted series.

    Everything a reproduction needs is bound here: the method and its version, the authority the
    actions came from, the code revision that ran, when it ran, which raw dataset it consumed, and
    every individual factor with the evidence that sized it.
    """

    method: str
    method_version: int
    status: AdjustmentStatus
    basis: AdjustmentBasis
    authority_id: str
    authority_content_hash: str
    authority_source_url: str
    authority_publication_date: date | None
    code_revision: str
    derived_at: datetime
    source_dataset_id: str
    source_manifest_hash: str
    factors: tuple[AdjustmentFactorRecord, ...]
    unresolved: tuple[UnresolvedAction, ...] = ()
    factor_set_hash: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        if self.status is AdjustmentStatus.RAW and self.factors:
            raise AdjustmentProvenanceError("a RAW series cannot carry adjustment factors")
        if any(
            self.factors[i].ex_date > self.factors[i + 1].ex_date
            for i in range(len(self.factors) - 1)
        ):
            raise AdjustmentProvenanceError("adjustment factors must be in ascending ex-date order")
        if not self.factor_set_hash:
            object.__setattr__(self, "factor_set_hash", self._compute_factor_set_hash())

    def _compute_factor_set_hash(self) -> str:
        payload = {
            "basis": self.basis.value,
            "factors": [item.to_canonical_dict() for item in self.factors],
            "method": self.method,
            "method_version": self.method_version,
            "unresolved": [item.to_canonical_dict() for item in self.unresolved],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @property
    def corroborated_factors(self) -> tuple[AdjustmentFactorRecord, ...]:
        """Only the factors a return calculation may divide out."""
        return tuple(item for item in self.factors if item.validation.is_corroborated)

    @property
    def uncorroborated_ex_dates(self) -> tuple[date, ...]:
        """Ex-dates of factors that exist but may not be applied to a return."""
        return tuple(item.ex_date for item in self.factors if not item.validation.is_corroborated)

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "authority": {
                "authority_id": self.authority_id,
                "content_hash": self.authority_content_hash,
                "publication_date": (
                    self.authority_publication_date.isoformat()
                    if self.authority_publication_date
                    else None
                ),
                "source_url": self.authority_source_url,
            },
            "basis": self.basis.value,
            "code_revision": self.code_revision,
            "derived_at": self.derived_at.isoformat().replace("+00:00", "Z"),
            "factor_count": len(self.factors),
            "factor_set_hash": self.factor_set_hash,
            "factors": [item.to_canonical_dict() for item in self.factors],
            "method": self.method,
            "method_version": self.method_version,
            "source_dataset_id": self.source_dataset_id,
            "source_manifest_hash": self.source_manifest_hash,
            "status": self.status.value,
            "unresolved": [item.to_canonical_dict() for item in self.unresolved],
            "unresolved_count": len(self.unresolved),
        }


def carry_factor(
    reference: AdjustmentReference | None,
    *,
    after: date,
    through: date,
) -> Decimal:
    """Product of every corroborated factor whose ex-date falls in ``(after, through]``.

    A raw price ratio is converted to an economic return by dividing by this number::

        economic_ratio = (raw[through] / carry) / raw[after]

    A 1:1 bonus halves the quote and doubles the share count, so its factor is ``0.5``; the raw
    ratio of ``0.5`` divided by ``0.5`` gives the economic return of zero that the holder actually
    experienced. Uncorroborated factors are **excluded** -- they are handled by
    :func:`spans_unresolved`, which refuses the window outright.
    """
    if reference is None:
        return Decimal(1)
    carry = Decimal(1)
    for item in reference.factors:
        if after < item.ex_date <= through and item.validation.is_corroborated:
            carry *= item.factor
    return carry


def spans_unresolved(
    reference: AdjustmentReference | None,
    *,
    after: date,
    through: date,
) -> bool:
    """Whether ``(after, through]`` contains an action of unknown or unproven size.

    A return measured across such a window is not a measurement of anything: the raw ratio contains
    a corporate action nobody has sized, and the inferred size would be indistinguishable from the
    day's market movement. Callers refuse the observation rather than publish a fabricated one.
    """
    if reference is None:
        return False
    if any(after < action.ex_date <= through for action in reference.unresolved):
        return True
    return any(
        after < factor.ex_date <= through and not factor.validation.is_corroborated
        for factor in reference.factors
    )
