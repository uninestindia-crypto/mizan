"""The one way an execution surface obtains a Mizan model.

`MizanModel.default_model()` returns a model whose card carries `verdict=RESEARCH_ONLY`, and its own
docstring says enforcement "lives at the surface". That was the design, and the paper session broke
it -- not by defeating a guard but by never reaching one. It called `default_model()` and hand-rolled
scoring, so `CrossSectionalModelStrategy`, where the verdict check lives, had zero production
callers while three docstrings asserted a `RESEARCH_ONLY` model "cannot execute anywhere".

This module is the chokepoint that makes the original design true: an execution surface asks *here*
for a model, and the verdict is enforced at the point of acquisition rather than somewhere the
caller might not go.

`default_model()` itself is deliberately left ungated. The CLI, the server's model display and
research callers legitimately construct the model without executing it, and gating construction
would break reading in order to police trading.

## The residual

A future execution script that calls `MizanModel.default_model()` directly bypasses this, exactly as
the paper session did. That is the same shape as the residual recorded for `85ff535`: the guarantee
rests on callers coming through the front door. It is narrowed by
`tests/test_research_paper_exemption.py`, which fails when a script that persists portfolio state
imports `default_model` directly -- a detector for the known surface, not for the class.

See `agent_context/decisions/20260830-paper-surface-research-only-exemption.md`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

from quant_system.execution.governed_strategy import (
    RESEARCH_PAPER_DECISION_RECORD,
    ExecutionSurface,
    ResearchPaperExemptionV1,
    require_surface_admits,
)
from quant_system.modeling.mizan_model import MizanModel
from quant_system.modeling.promotion import PromotionState

__all__ = [
    "PAPER_OBSERVATION_EXEMPTION",
    "load_mizan_for_execution",
]

#: The standing exemption under which the paper observation session runs.
#:
#: A module constant rather than a value each caller builds, so that every session runs under the
#: same recorded reason and a reader has one place to find it.
PAPER_OBSERVATION_EXEMPTION: Final = ResearchPaperExemptionV1(
    decision_record=RESEARCH_PAPER_DECISION_RECORD,
    acknowledged_by="founder",
    reason=(
        "Observing how an unpromotable model behaves against live prices is the stated purpose of "
        "the paper pilot. The best campaign deflated Sharpe is 0.397794 against a 0.95 gate, so no "
        "Mizan model is promotable and none is expected to become so; running it here measures "
        "execution behaviour, not edge, and every result inherits the RESEARCH_ONLY label."
    ),
)


#: The published profiles an execution surface may ask for, by name.
#:
#: A closed map rather than a `getattr` on `MizanModel`, so that adding a profile is a deliberate
#: act that passes through this gate rather than an attribute that happens to resolve.
_PROFILES: Final[dict[str, Callable[[], MizanModel]]] = {
    "default": MizanModel.default_model,
    "sprint_50k": MizanModel.sprint_50k_model,
}


def load_mizan_for_execution(
    surface: ExecutionSurface,
    exemption: ResearchPaperExemptionV1 | None = None,
    *,
    profile: str = "default",
) -> MizanModel:
    """Return a published Mizan model, or refuse if its verdict may not drive `surface`.

    Args:
        surface: Where the model's decisions will be executed.
        exemption: Required on `RESEARCH_PAPER`, refused everywhere else.
        profile: Which published profile to load. Both currently carry `RESEARCH_ONLY`.

    Raises:
        GovernedExecutionError: The card's verdict is not admitted by the surface, or the exemption
            is missing where it is required or supplied where it does not apply.
        KeyError: No such profile.
    """
    if profile not in _PROFILES:
        raise KeyError(f"unknown Mizan profile {profile!r}; known: {sorted(_PROFILES)}")
    model = _PROFILES[profile]()
    require_surface_admits(PromotionState(model.model_card.verdict), surface, exemption)
    return model
