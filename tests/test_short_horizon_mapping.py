"""Prove the hold-to-horizon mapping against the real label builder, rather than restating it.

The brief that commissioned this study says: *"Evaluate exactly 1, 2 and 3 trading sessions held
after entry. Test the mapping to the repository's decision/entry/exit convention."*

Testing it matters because the convention has already bitten this repository once. The Flagship book
runs a historical label horizon of **11** that its portfolio policy converts to **10** held sessions,
and the loss diagnosis had to spell that conversion out because the two numbers do not match by eye.
An off-by-one here would not crash anything -- it would quietly evaluate a two-session strategy and
report it as a one-session strategy, and every cost-per-session figure in the study would be wrong by
a factor of two in the direction that flatters the candidate.

So these tests drive ``build_label_dataset`` with a real governed acquisition and read the entry and
exit timestamps it actually produces, then check them against the calendar. If the execution
convention ever changes, this fails instead of silently reinterpreting the results.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from quant_system.modeling import build_feature_dataset, build_label_dataset
from quant_system.research_short_horizon import (
    HOLD_TO_HORIZON_SESSIONS,
    hold_specs,
    horizon_for_hold,
)
from quant_system.research_short_horizon.horizon import MINIMUM_HELD_SESSIONS
from tests.modeling_fixtures import (
    governed_acquisition,
    governed_calendar,
    governed_universe,
)

CANDIDATE = "cand_short_horizon"


def _quotes_for_horizon(acquisition, calendar, *, horizon_sessions: int, cost: Decimal):
    """Cost quotes keyed for one specific horizon.

    The fixture in ``tests/modeling_fixtures`` hard-codes a two-session horizon, so this study needs
    its own. A quote is keyed by (instrument, entry_at, exit_at), which is what makes a horizon
    mismatch surface as ``COST_QUOTE_MISSING`` instead of a silently mispriced label -- so building
    these for the wrong horizon would be caught, not absorbed.
    """
    from quant_system.modeling import MoneyV1, RoundTripCostQuoteV1

    bars = {record.exchange_date: record for record in acquisition.records}
    quotes = []
    for ordinal in range(20, len(calendar.sessions) - horizon_sessions):
        entry_session = calendar.sessions[ordinal + 1]
        exit_session = calendar.sessions[ordinal + horizon_sessions]
        entry_bar = bars.get(entry_session.exchange_date)
        exit_bar = bars.get(exit_session.exchange_date)
        if entry_bar is None or exit_bar is None:
            continue
        quotes.append(
            RoundTripCostQuoteV1(
                provider_instrument_id=entry_bar.provider_instrument_id,
                symbol=entry_bar.symbol,
                entry_at=entry_session.open_at,
                exit_at=exit_session.open_at,
                entry_price=entry_bar.open,
                exit_price=exit_bar.open,
                quantity=1,
                component_costs={"all_in": MoneyV1(cost, "INR")},
                cost_rule_ids=("nse-test-v1",),
                cost_rule_set_hash="e" * 64,
                execution_contract_version="next-open-v1",
            )
        )
    return tuple(quotes)


@pytest.mark.parametrize("held_sessions", sorted(HOLD_TO_HORIZON_SESSIONS))
def test_the_declared_horizon_really_holds_that_many_sessions(held_sessions: int) -> None:
    """Drive the real label builder and count the sessions between the two fills."""
    horizon = horizon_for_hold(held_sessions)
    count = 40
    calendar = governed_calendar(count)
    universe = governed_universe()
    acquisition = governed_acquisition(count=count, calendar=calendar, universe=universe)
    features = build_feature_dataset(acquisition, CANDIDATE, calendar, universe)
    quotes = _quotes_for_horizon(
        acquisition, calendar, horizon_sessions=horizon, cost=Decimal("0")
    )

    labels = build_label_dataset(features, acquisition, calendar, quotes, horizon_sessions=horizon)
    assert labels.rows, "the fixture must produce at least one matured label"
    assert labels.label_horizon_sessions == horizon

    opens = [session.open_at for session in calendar.sessions]
    for row in labels.rows:
        entry_index = opens.index(row.entry_at)
        exit_index = opens.index(row.exit_at)
        assert exit_index - entry_index == held_sessions, (
            f"hold {held_sessions} must span exactly {held_sessions} session boundaries; "
            f"entry ordinal {entry_index}, exit ordinal {exit_index}"
        )


@pytest.mark.parametrize("held_sessions", sorted(HOLD_TO_HORIZON_SESSIONS))
def test_entry_is_always_the_next_eligible_open_after_the_decision(held_sessions: int) -> None:
    """No hold length may change *when* the position is opened. Only when it is closed."""
    horizon = horizon_for_hold(held_sessions)
    count = 40
    calendar = governed_calendar(count)
    universe = governed_universe()
    acquisition = governed_acquisition(count=count, calendar=calendar, universe=universe)
    features = build_feature_dataset(acquisition, CANDIDATE, calendar, universe)
    quotes = _quotes_for_horizon(
        acquisition, calendar, horizon_sessions=horizon, cost=Decimal("0")
    )

    labels = build_label_dataset(features, acquisition, calendar, quotes, horizon_sessions=horizon)
    closes = [session.close_at for session in calendar.sessions]
    opens = [session.open_at for session in calendar.sessions]
    for row in labels.rows:
        decision_index = closes.index(row.decision_at)
        assert row.entry_at == opens[decision_index + 1], (
            "entry must be the very next session open, never the same session as the decision"
        )


def test_the_shortest_expressible_hold_is_one_session() -> None:
    """Entry is the next eligible open, so a zero-session hold has no execution meaning here."""
    assert MINIMUM_HELD_SESSIONS == 1
    with pytest.raises(ValueError, match="no execution meaning"):
        horizon_for_hold(0)


def test_a_hold_outside_the_declared_budget_is_refused() -> None:
    """Adding a fourth hold is a new trial against the frozen budget, not a free parameter."""
    with pytest.raises(ValueError, match="outside the declared experiment budget"):
        horizon_for_hold(5)


def test_every_spec_embargoes_at_least_its_own_horizon() -> None:
    """Overlapping labels are the reason. A shorter embargo leaks the exit window across the fold.

    A decision on day k and one on day k+1 share exit windows whenever the hold exceeds a session,
    so a validation fold starting immediately after a training fold is scored on outcomes the
    training rows already contain.
    """
    for spec in hold_specs():
        assert spec.embargo_sessions >= spec.horizon_sessions
        assert spec.exit_offset - spec.entry_offset == spec.held_sessions


def test_the_hold_table_is_exactly_what_the_brief_asked_for() -> None:
    """1, 2 and 3 sessions. Not a range, not a sweep -- three declared trials."""
    assert sorted(HOLD_TO_HORIZON_SESSIONS) == [1, 2, 3]
    assert HOLD_TO_HORIZON_SESSIONS == {1: 2, 2: 3, 3: 4}
