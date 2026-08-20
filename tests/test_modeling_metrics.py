"""Portfolio-aware governed strategy metric tests."""

from datetime import UTC, datetime

from quant_system.modeling import FoldDecisionV1
from quant_system.modeling.metrics import calculate_strategy_metrics


def test_simultaneous_symbols_use_equal_weight_portfolio_period() -> None:
    decision_at = datetime(2025, 1, 2, 10, 0, tzinfo=UTC)
    decisions = (
        FoldDecisionV1(
            strategy_id="BUY_AND_HOLD",
            symbol="AAA",
            decision_at=decision_at,
            predicted_target="UP",
            actual_target="UP",
            realized_net_return="0.01",
            score=None,
            score_kind="RULE",
        ),
        FoldDecisionV1(
            strategy_id="BUY_AND_HOLD",
            symbol="BBB",
            decision_at=decision_at,
            predicted_target="UP",
            actual_target="DOWN",
            realized_net_return="-0.01",
            score=None,
            score_kind="RULE",
        ),
    )

    metrics = calculate_strategy_metrics(decisions)

    assert metrics.total_return == "0"
    assert metrics.sharpe_ratio == "0"
    assert metrics.turnover == "2"
    assert metrics.exposure == "1"
    assert metrics.concentration == "0.5"
    assert metrics.attributable_count == 2
    assert metrics.trade_count == 2


def test_return_statistics_use_portfolio_period_count_not_instrument_rows(  # test-allow: loop-in-test - fixed table always constructs two complete portfolio periods.
) -> None:
    first = datetime(2025, 1, 2, 10, 0, tzinfo=UTC)
    second = datetime(2025, 1, 3, 10, 0, tzinfo=UTC)
    decisions = tuple(
        FoldDecisionV1(
            strategy_id="BUY_AND_HOLD",
            symbol=symbol,
            decision_at=decision_at,
            predicted_target="UP",
            actual_target="UP" if realized_return != "0" else "DOWN",
            realized_net_return=realized_return,
            score=None,
            score_kind="RULE",
        )
        for decision_at, symbol, realized_return in (
            (first, "AAA", "0.02"),
            (first, "BBB", "0"),
            (second, "AAA", "0"),
            (second, "BBB", "0"),
        )
    )

    metrics = calculate_strategy_metrics(decisions)

    assert metrics.total_return == "0.01"
    assert metrics.annualized_volatility == "0.112249721603"
    assert metrics.sharpe_ratio == "11.224972160322"
