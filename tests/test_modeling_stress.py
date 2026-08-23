"""Comprehensive tests for mandatory stress testing suite and exact Decimal accounting."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from quant_system.modeling import (
    MANDATORY_STRESS_SCENARIOS,
    StressScenarioType,
    evaluate_governed_ridge_fold,
    run_mandatory_stress_suite,
)
from quant_system.modeling.errors import ModelingError
from quant_system.modeling.rows import MoneyV1, RoundTripCostQuoteV1
from tests.modeling_training_fixtures import governed_training_journey


def _sample_cost_quotes(journey) -> tuple[RoundTripCostQuoteV1, ...]:
    return tuple(
        RoundTripCostQuoteV1(
            provider_instrument_id="NSE_EQ|INE009A01021",
            symbol=row.symbol,
            entry_at=row.entry_at,
            exit_at=row.exit_at,
            entry_price=Decimal("100"),
            exit_price=Decimal("101"),
            quantity=1,
            component_costs={"all_in": MoneyV1("0.1", "INR")},
            cost_rule_ids=("nse-test-v1",),
            cost_rule_set_hash="e" * 64,
            execution_contract_version="next-open-v1",
        )
        for row in journey.fold.validation_rows
    )


def test_mandatory_stress_suite_all_scenarios_evaluated() -> None:
    journey = governed_training_journey()
    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )

    cost_quotes = _sample_cost_quotes(journey)

    now = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
    report = run_mandatory_stress_suite(
        evaluation.ridge_report.decisions,
        journey.fold.validation_rows,
        cost_quotes,
        journey.calendar,
        candidate_id=journey.features.candidate_id,
        model_id=evaluation.model_id,
        evaluated_at=now,
    )

    assert report.model_id == evaluation.model_id
    assert report.candidate_id == journey.features.candidate_id
    assert len(report.scenario_results) == 5

    scenario_ids = {res.scenario_id for res in report.scenario_results}
    expected_ids = {s.value for s in MANDATORY_STRESS_SCENARIOS}
    assert scenario_ids == expected_ids

    for res in report.scenario_results:
        assert Decimal(res.baseline_sharpe).is_finite()
        assert Decimal(res.stressed_sharpe).is_finite()
        assert Decimal(res.baseline_total_return).is_finite()
        assert Decimal(res.stressed_total_return).is_finite()
        assert Decimal(res.baseline_max_drawdown).is_finite()
        assert Decimal(res.stressed_max_drawdown).is_finite()


def test_stress_twice_transaction_costs_reduces_returns() -> None:
    journey = governed_training_journey()
    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )

    cost_quotes = _sample_cost_quotes(journey)

    report = run_mandatory_stress_suite(
        evaluation.ridge_report.decisions,
        journey.fold.validation_rows,
        cost_quotes,
        journey.calendar,
        candidate_id=journey.features.candidate_id,
        model_id=evaluation.model_id,
    )

    twice_costs_res = next(
        r
        for r in report.scenario_results
        if r.scenario_id == StressScenarioType.TWICE_TRANSACTION_COSTS.value
    )

    # 2x costs must result in stressed total return <= baseline total return
    assert Decimal(twice_costs_res.stressed_total_return) <= Decimal(
        twice_costs_res.baseline_total_return
    )


def test_stress_adverse_spread_slippage_friction() -> None:
    journey = governed_training_journey()
    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )

    cost_quotes = _sample_cost_quotes(journey)

    report = run_mandatory_stress_suite(
        evaluation.ridge_report.decisions,
        journey.fold.validation_rows,
        cost_quotes,
        journey.calendar,
        candidate_id=journey.features.candidate_id,
        model_id=evaluation.model_id,
        adverse_spread_slippage_bps=Decimal("30"),  # 30 bps
    )

    slippage_res = next(
        r
        for r in report.scenario_results
        if r.scenario_id == StressScenarioType.ADVERSE_SPREAD_SLIPPAGE.value
    )
    assert Decimal(slippage_res.stressed_total_return) <= Decimal(
        slippage_res.baseline_total_return
    )


def test_stress_report_hash_is_deterministic() -> None:
    journey = governed_training_journey()
    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )

    cost_quotes = _sample_cost_quotes(journey)

    now = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)
    report1 = run_mandatory_stress_suite(
        evaluation.ridge_report.decisions,
        journey.fold.validation_rows,
        cost_quotes,
        journey.calendar,
        candidate_id=journey.features.candidate_id,
        model_id=evaluation.model_id,
        evaluated_at=now,
    )
    report2 = run_mandatory_stress_suite(
        evaluation.ridge_report.decisions,
        journey.fold.validation_rows,
        cost_quotes,
        journey.calendar,
        candidate_id=journey.features.candidate_id,
        model_id=evaluation.model_id,
        evaluated_at=now,
    )

    assert report1.report_hash == report2.report_hash
    assert report1.to_canonical_dict() == report2.to_canonical_dict()


# -------------------------------------------------------------------------
# Ring 5: S-1 residual — a missing cost quote must not become a silent 10 bps
# -------------------------------------------------------------------------


def test_missing_cost_quote_refuses_rather_than_assuming_ten_bps() -> None:
    """S-1 residual: an unfound quote silently became 0.001, so the scenario ignored its input.

    That is why a 10 bps quote and a 9500 bps quote produced an identical scenario_hash: the
    stressed cost never depended on the quote at all. A cost that cannot be established makes
    the scenario unevaluable, which is not the same as the model surviving it.
    """
    journey = governed_training_journey()
    evaluation = evaluate_governed_ridge_fold(
        journey.start,
        journey.registry,
        journey.features,
        journey.labels,
        journey.fold,
    )

    with pytest.raises(ModelingError) as excinfo:
        run_mandatory_stress_suite(
            evaluation.ridge_report.decisions,
            journey.fold.validation_rows,
            (),  # no cost quotes at all
            journey.calendar,
            candidate_id=journey.features.candidate_id,
            model_id=evaluation.model_id,
            evaluated_at=datetime(2026, 8, 22, 12, 0, tzinfo=UTC),
        )
    assert "cost quote" in str(excinfo.value).lower()
