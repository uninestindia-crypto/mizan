"""The declared exemption that lets an unpromotable model run on a paper-only surface.

Red Team finding P1-1: `scripts/run_paper_pilot_session.py` called `MizanModel.default_model()`
directly and hand-rolled scoring, so `CrossSectionalModelStrategy` -- where the verdict check lives
-- had **zero production callers** while three docstrings asserted that a `RESEARCH_ONLY` model
"cannot execute anywhere". The gate was never defeated; it was never reached.

The decision recorded at `agent_context/decisions/20260830-paper-surface-research-only-exemption.md`
is that such a model *may* run, on one surface, under a stated exemption. These tests guard the two
halves that make that a policy rather than a hole: the exemption admits exactly one verdict on
exactly one surface, and it cannot be reached by accident.

The last test is the one that matters most. Every P1 in that report passed ruff, mypy and 1104
tests, so a guard nothing detects is worth very little.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from quant_system.execution.governed_strategy import (
    RESEARCH_PAPER_DECISION_RECORD,
    ExecutionSurface,
    GovernedExecutionError,
    ResearchPaperExemptionV1,
    require_surface_admits,
)
from quant_system.execution.mizan_execution import (
    PAPER_OBSERVATION_EXEMPTION,
    load_mizan_for_execution,
)
from quant_system.modeling.promotion import PromotionState

REPO_ROOT = Path(__file__).resolve().parent.parent

PROMOTION_SURFACES = (
    ExecutionSurface.SHADOW,
    ExecutionSurface.PAPER_PILOT,
    ExecutionSurface.PAPER,
)


def _exemption(**overrides: str) -> ResearchPaperExemptionV1:
    base = {
        "decision_record": RESEARCH_PAPER_DECISION_RECORD,
        "acknowledged_by": "founder",
        "reason": "observing an unpromotable model against live prices",
    }
    base.update(overrides)
    return ResearchPaperExemptionV1(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------------------------------------
# The ceilings the exemption must not have moved.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("surface", PROMOTION_SURFACES)
def test_research_only_still_drives_no_promotion_surface(surface: ExecutionSurface) -> None:
    """The exemption adds a surface; it must not widen the three that already existed."""
    with pytest.raises(GovernedExecutionError, match="may not drive the"):
        require_surface_admits(PromotionState.RESEARCH_ONLY, surface)


@pytest.mark.parametrize("surface", (*PROMOTION_SURFACES, ExecutionSurface.RESEARCH_PAPER))
def test_reject_may_execute_on_no_surface_at_all(surface: ExecutionSurface) -> None:
    """The line the exemption does not cross.

    A REJECT model failed a gate it was measured against. A RESEARCH_ONLY model was never eligible
    for one. Only the second is admitted anywhere, and the observation surface is not a loophole for
    the first.
    """
    exemption = _exemption() if surface is ExecutionSurface.RESEARCH_PAPER else None
    with pytest.raises(GovernedExecutionError, match="may not drive the"):
        require_surface_admits(PromotionState.REJECT, surface, exemption)


@pytest.mark.parametrize(
    "verdict", (PromotionState.PAPER, PromotionState.PAPER_PILOT, PromotionState.SHADOW)
)
def test_a_promotable_model_may_not_run_on_the_observation_surface(
    verdict: PromotionState,
) -> None:
    """RESEARCH_PAPER is a purpose, not a permission level.

    A promotable model running there would file its results as research observation rather than as
    a pilot -- the inverse of the mistake the exemption exists to prevent.
    """
    with pytest.raises(GovernedExecutionError, match="may not drive the RESEARCH_PAPER"):
        require_surface_admits(verdict, ExecutionSurface.RESEARCH_PAPER, _exemption())


# --------------------------------------------------------------------------------------------
# The exemption cannot be reached by accident, or reused as a skeleton key.
# --------------------------------------------------------------------------------------------


def test_the_observation_surface_admits_research_only_with_an_exemption() -> None:
    require_surface_admits(
        PromotionState.RESEARCH_ONLY, ExecutionSurface.RESEARCH_PAPER, _exemption()
    )


def test_the_observation_surface_refuses_research_only_without_one() -> None:
    """Otherwise the new surface is just the old bypass with a name."""
    with pytest.raises(GovernedExecutionError, match="requires an explicit"):
        require_surface_admits(PromotionState.RESEARCH_ONLY, ExecutionSurface.RESEARCH_PAPER)


@pytest.mark.parametrize("surface", PROMOTION_SURFACES)
def test_an_exemption_is_refused_on_every_other_surface(surface: ExecutionSurface) -> None:
    """It must not become a general way past the ceilings."""
    with pytest.raises(GovernedExecutionError, match="does not apply to the"):
        require_surface_admits(PromotionState.PAPER, surface, _exemption())


def test_the_verdict_is_reported_before_the_missing_exemption() -> None:
    """A promotable model offered to RESEARCH_PAPER must not be told to supply an exemption.

    Supplying one would not have helped. Naming the exemption first would send the reader down a
    dead end, so the verdict check runs first.
    """
    with pytest.raises(GovernedExecutionError, match="may not drive the RESEARCH_PAPER"):
        require_surface_admits(PromotionState.PAPER, ExecutionSurface.RESEARCH_PAPER)


def test_an_exemption_must_cite_the_decision_record() -> None:
    """The citation is the whole audit value; free text would record nothing checkable."""
    with pytest.raises(GovernedExecutionError, match="must cite"):
        _exemption(decision_record="because I said so")


@pytest.mark.parametrize("field", ("acknowledged_by", "reason"))
def test_an_unattributed_exemption_is_refused(field: str) -> None:
    with pytest.raises(GovernedExecutionError, match="must name who"):
        _exemption(**{field: "   "})


# --------------------------------------------------------------------------------------------
# The gated loader.
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("surface", PROMOTION_SURFACES)
def test_the_real_published_model_is_refused_on_a_promotion_surface(
    surface: ExecutionSurface,
) -> None:
    """Not a synthetic card: the actual model the paper session runs, on the real gate."""
    with pytest.raises(GovernedExecutionError, match="may not drive the"):
        load_mizan_for_execution(surface)


@pytest.mark.parametrize("profile", ("default", "sprint_50k"))
def test_both_published_profiles_load_on_the_observation_surface(profile: str) -> None:
    model = load_mizan_for_execution(
        ExecutionSurface.RESEARCH_PAPER, PAPER_OBSERVATION_EXEMPTION, profile=profile
    )
    assert model.model_card.verdict == "RESEARCH_ONLY"


def test_both_published_profiles_are_refused_without_the_exemption() -> None:
    for profile in ("default", "sprint_50k"):
        with pytest.raises(GovernedExecutionError, match="requires an explicit"):
            load_mizan_for_execution(ExecutionSurface.RESEARCH_PAPER, profile=profile)


def test_an_unknown_profile_is_refused_rather_than_resolved() -> None:
    """A closed map, so adding a profile passes through this gate deliberately."""
    with pytest.raises(KeyError, match="unknown Mizan profile"):
        load_mizan_for_execution(
            ExecutionSurface.RESEARCH_PAPER, PAPER_OBSERVATION_EXEMPTION, profile="from_pretrained"
        )


def test_the_standing_exemption_cites_the_decision_record() -> None:
    assert PAPER_OBSERVATION_EXEMPTION.decision_record == RESEARCH_PAPER_DECISION_RECORD
    assert (REPO_ROOT / RESEARCH_PAPER_DECISION_RECORD).is_file(), (
        "the exemption cites a decision record that does not exist; the citation is the only thing "
        "making the exemption auditable"
    )


# --------------------------------------------------------------------------------------------
# The detector. This is the one that would have caught P1-1.
# --------------------------------------------------------------------------------------------


def test_no_executing_script_obtains_a_model_outside_the_gate() -> None:
    """A script that persists portfolio state is executing, so it must come through the chokepoint.

    This is a detector for the known surface, not for the class -- a new execution path that calls
    `default_model()` under some other shape still slips by. That residual is recorded in
    `execution/mizan_execution.py` and in the decision record. It is narrowed here rather than
    closed, which is the honest description.
    """
    ungated = {"default_model", "sprint_50k_model"}
    offenders = []
    for script in sorted((REPO_ROOT / "scripts").glob("*.py")):
        source = script.read_text(encoding="utf-8")
        if "save_portfolio" not in source and "PaperPilotEngine" not in source:
            continue
        # Parsed rather than grepped, so that a comment or docstring naming the ungated
        # constructor -- this file and that module both do, unavoidably -- is not a finding.
        tree = ast.parse(source, filename=str(script))
        called = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        if called & ungated:
            offenders.append(f"{script.name} calls {sorted(called & ungated)}")
    assert not offenders, (
        f"{offenders} execute and obtain a model outside the surface gate. Use "
        f"`load_mizan_for_execution(surface, exemption)` so the published verdict is enforced at "
        f"the point of acquisition; see {RESEARCH_PAPER_DECISION_RECORD}"
    )
