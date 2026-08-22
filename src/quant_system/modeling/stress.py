"""Mandatory stress test suite with exact Decimal financial accounting."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from enum import StrEnum
from typing import Any

from quant_system.data.market_data_evidence import canonical_sha256, decimal_text, utc_text
from quant_system.modeling.authorities import SessionCalendarV1
from quant_system.modeling.errors import ModelingError, ModelingFailureCode
from quant_system.modeling.metrics import (
    FoldDecisionV1,
    StrategyMetricsV1,
    calculate_strategy_metrics,
    metric_decimal,
)
from quant_system.modeling.rows import LabelRowV1, RoundTripCostQuoteV1

_METRIC_QUANTUM = Decimal("0.000000000001")


class StressScenarioType(StrEnum):
    TWICE_TRANSACTION_COSTS = "TWICE_TRANSACTION_COSTS"
    ONE_BAR_EXECUTION_DELAY = "ONE_BAR_EXECUTION_DELAY"
    ADVERSE_SPREAD_SLIPPAGE = "ADVERSE_SPREAD_SLIPPAGE"
    ADVERSE_GAP_REGIME = "ADVERSE_GAP_REGIME"
    DATA_ANOMALY_RESILIENCE = "DATA_ANOMALY_RESILIENCE"


MANDATORY_STRESS_SCENARIOS = (
    StressScenarioType.TWICE_TRANSACTION_COSTS,
    StressScenarioType.ONE_BAR_EXECUTION_DELAY,
    StressScenarioType.ADVERSE_SPREAD_SLIPPAGE,
    StressScenarioType.ADVERSE_GAP_REGIME,
    StressScenarioType.DATA_ANOMALY_RESILIENCE,
)


@dataclass(frozen=True, slots=True)
class StressScenarioResultV1:
    scenario_id: str
    scenario_name: str
    passed: bool
    baseline_sharpe: str
    stressed_sharpe: str
    baseline_total_return: str
    stressed_total_return: str
    baseline_max_drawdown: str
    stressed_max_drawdown: str
    details: dict[str, Any]
    failure_reason: str | None
    scenario_hash: str = field(init=False)

    def __post_init__(self) -> None:
        _validate_stress_result_fields(self)
        object.__setattr__(self, "scenario_hash", canonical_sha256(self._unsigned_dict()))

    def to_canonical_dict(self) -> dict[str, Any]:
        payload = self._unsigned_dict()
        payload["scenario_hash"] = self.scenario_hash
        return payload

    def _unsigned_dict(self) -> dict[str, Any]:
        return {
            "baseline_max_drawdown": self.baseline_max_drawdown,
            "baseline_sharpe": self.baseline_sharpe,
            "baseline_total_return": self.baseline_total_return,
            "details": self.details,
            "failure_reason": self.failure_reason,
            "passed": self.passed,
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "schema_id": "quantos.stress_scenario_result",
            "schema_version": 1,
            "stressed_max_drawdown": self.stressed_max_drawdown,
            "stressed_sharpe": self.stressed_sharpe,
            "stressed_total_return": self.stressed_total_return,
        }


@dataclass(frozen=True, slots=True)
class StressReportV1:
    model_id: str
    candidate_id: str
    evaluated_at: datetime
    scenario_results: tuple[StressScenarioResultV1, ...]
    all_passed: bool
    report_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if not self.scenario_results:
            raise ValueError("stress report requires at least one scenario result")
        if self.evaluated_at.tzinfo is None or self.evaluated_at.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        passed = all(result.passed for result in self.scenario_results)
        if self.all_passed != passed:
            raise ValueError("all_passed does not match scenario results")
        object.__setattr__(self, "report_hash", canonical_sha256(self._unsigned_dict()))

    def to_canonical_dict(self) -> dict[str, Any]:
        payload = self._unsigned_dict()
        payload["report_hash"] = self.report_hash
        return payload

    def _unsigned_dict(self) -> dict[str, Any]:
        return {
            "all_passed": self.all_passed,
            "candidate_id": self.candidate_id,
            "evaluated_at": utc_text(self.evaluated_at),
            "model_id": self.model_id,
            "scenario_results": [r.to_canonical_dict() for r in self.scenario_results],
            "schema_id": "quantos.stress_report",
            "schema_version": 1,
        }


def run_mandatory_stress_suite(
    decisions: tuple[FoldDecisionV1, ...],
    labels: tuple[LabelRowV1, ...],
    cost_quotes: tuple[RoundTripCostQuoteV1, ...]
    | Mapping[tuple[str, datetime], RoundTripCostQuoteV1],
    calendar: SessionCalendarV1,
    *,
    candidate_id: str,
    model_id: str,
    evaluated_at: datetime | None = None,
    adverse_spread_slippage_bps: Decimal = Decimal("20"),  # 20 bps = 0.0020
    max_tolerated_drawdown: Decimal = Decimal("0.25"),  # 25% max drawdown under stress
) -> StressReportV1:
    """Execute all mandatory stress test scenarios with exact Decimal accounting."""
    now = evaluated_at or datetime.now(UTC)
    if not decisions:
        raise ModelingError(
            ModelingFailureCode.STRESS_TEST_FAILED,
            "stress test suite requires non-empty decisions",
        )

    quotes_map: Mapping[Any, Any]
    if isinstance(cost_quotes, Mapping):
        quotes_map = cost_quotes
    else:
        quotes_map = {(q.symbol, q.entry_at): q for q in cost_quotes}

    # Baseline metrics from decisions
    baseline_metrics = calculate_strategy_metrics(decisions)

    scenario_results: list[StressScenarioResultV1] = []

    # Scenario 1: 2x Transaction Costs
    scenario_results.append(
        _stress_twice_transaction_costs(
            decisions,
            labels,
            quotes_map,
            baseline_metrics,
        )
    )

    # Scenario 2: 1-Bar Execution Delay
    scenario_results.append(
        _stress_one_bar_execution_delay(
            decisions,
            labels,
            calendar,
            quotes_map,
            baseline_metrics,
        )
    )

    # Scenario 3: Adverse Spread / Slippage
    scenario_results.append(
        _stress_adverse_spread_slippage(
            decisions,
            baseline_metrics,
            extra_friction=adverse_spread_slippage_bps / Decimal(10000),
        )
    )

    # Scenario 4: Adverse Gap Regime
    scenario_results.append(
        _stress_adverse_gap_regime(
            decisions,
            baseline_metrics,
            max_tolerated_drawdown=max_tolerated_drawdown,
        )
    )

    # Scenario 5: Data Anomaly Resilience
    scenario_results.append(
        _stress_data_anomaly_resilience(
            decisions,
            baseline_metrics,
        )
    )

    all_passed = all(result.passed for result in scenario_results)

    return StressReportV1(
        model_id=model_id,
        candidate_id=candidate_id,
        evaluated_at=now,
        scenario_results=tuple(scenario_results),
        all_passed=all_passed,
    )


def _stress_twice_transaction_costs(
    decisions: tuple[FoldDecisionV1, ...],
    labels: tuple[LabelRowV1, ...],
    cost_quotes: Mapping[Any, Any],
    baseline_metrics: StrategyMetricsV1,
) -> StressScenarioResultV1:
    """Stress test: 2x transaction costs applied to all active trades."""
    with localcontext() as context:
        context.prec = 60
        context.rounding = ROUND_HALF_EVEN

        label_map = {(lbl.symbol, lbl.decision_at): lbl for lbl in labels}
        stressed_period_returns: list[Decimal] = []
        decision_by_time: dict[datetime, list[Decimal]] = {}
        for decision in decisions:
            decision_by_time.setdefault(decision.decision_at, [])
            if decision.predicted_target == "UP":
                # Find cost quote for this decision
                label = label_map.get((decision.symbol, decision.decision_at))
                entry_at = label.entry_at if label is not None else None
                quote = (
                    cost_quotes.get((decision.symbol, decision.decision_at))
                    or (
                        cost_quotes.get((decision.symbol, entry_at))
                        if entry_at is not None
                        else None
                    )
                    or cost_quotes.get(decision.symbol)
                )
                if (
                    quote is not None
                    and hasattr(quote, "component_costs")
                    and hasattr(quote, "entry_price")
                    and hasattr(quote, "quantity")
                ):
                    total_amount = sum(
                        (m.amount_decimal for m in quote.component_costs.values()), start=Decimal(0)
                    )
                    cost = total_amount / (quote.entry_price * Decimal(quote.quantity))
                elif quote is not None and hasattr(quote, "total_bps"):
                    cost = Decimal(str(quote.total_bps)) / Decimal(10000)
                elif quote is not None and isinstance(quote, (Decimal, int, float, str)):
                    cost = Decimal(str(quote))
                else:
                    cost = Decimal("0.001")  # 10 bps default fallback

                # Stressed net return = base net return - 1x additional cost (since base net already subtracted 1x cost)
                base_net = Decimal(decision.realized_net_return)
                stressed_net = base_net - cost
                decision_by_time[decision.decision_at].append(stressed_net)

        for dt in sorted(decision_by_time):
            trades = decision_by_time[dt]
            if trades:
                stressed_period_returns.append(sum(trades) / Decimal(len(trades)))
            else:
                stressed_period_returns.append(Decimal(0))

        sharpe, total_ret, max_dd = _compute_return_metrics(tuple(stressed_period_returns))

        # Pass condition: total return remains positive
        passed = total_ret > Decimal(0)
        failure_reason = (
            None if passed else "Total return becomes negative under 2x transaction costs"
        )

        return StressScenarioResultV1(
            scenario_id=StressScenarioType.TWICE_TRANSACTION_COSTS.value,
            scenario_name="Twice Transaction Costs (2x Fees)",
            passed=passed,
            baseline_sharpe=baseline_metrics.sharpe_ratio,
            stressed_sharpe=metric_decimal(sharpe),
            baseline_total_return=baseline_metrics.total_return,
            stressed_total_return=metric_decimal(total_ret),
            baseline_max_drawdown=baseline_metrics.max_drawdown,
            stressed_max_drawdown=metric_decimal(max_dd),
            details={"multiplier": "2.0", "active_trades_stressed": baseline_metrics.trade_count},
            failure_reason=failure_reason,
        )


def _stress_one_bar_execution_delay(
    decisions: tuple[FoldDecisionV1, ...],
    labels: tuple[LabelRowV1, ...],
    calendar: SessionCalendarV1,
    cost_quotes: Mapping[tuple[str, datetime], RoundTripCostQuoteV1],
    baseline_metrics: StrategyMetricsV1,
) -> StressScenarioResultV1:
    """Stress test: 1-bar execution delay for fill timing."""
    with localcontext() as context:
        context.prec = 60
        context.rounding = ROUND_HALF_EVEN

        # When execution is delayed by 1 bar:
        # Signal at close[t] fills at open[t+2] and exits at open[t+3] instead of open[t+1] to open[t+2].
        # We simulate the lagged return series or lagged decision application.
        decision_times = sorted({d.decision_at for d in decisions})

        stressed_period_returns: list[Decimal] = []
        for i, dt in enumerate(decision_times):
            if i == 0:
                stressed_period_returns.append(Decimal(0))
                continue
            # Apply decision from previous time step (1-bar delay)
            prev_dt = decision_times[i - 1]
            prev_decisions = [
                d for d in decisions if d.decision_at == prev_dt and d.predicted_target == "UP"
            ]
            current_decisions = [d for d in decisions if d.decision_at == dt]

            if not prev_decisions:
                stressed_period_returns.append(Decimal(0))
                continue

            # Return of the delayed position during current bar
            current_returns = [
                Decimal(d.realized_net_return)
                for d in current_decisions
                if d.symbol in {p.symbol for p in prev_decisions}
            ]
            if current_returns:
                stressed_period_returns.append(sum(current_returns) / Decimal(len(current_returns)))
            else:
                stressed_period_returns.append(Decimal(0))

        sharpe, total_ret, max_dd = _compute_return_metrics(tuple(stressed_period_returns))

        # Pass condition: total return is positive or drawdown <= 20%
        passed = total_ret > Decimal(0) and max_dd <= Decimal("0.20")
        failure_reason = None if passed else "Strategy fails under 1-bar execution delay"

        return StressScenarioResultV1(
            scenario_id=StressScenarioType.ONE_BAR_EXECUTION_DELAY.value,
            scenario_name="One-Bar Execution Delay",
            passed=passed,
            baseline_sharpe=baseline_metrics.sharpe_ratio,
            stressed_sharpe=metric_decimal(sharpe),
            baseline_total_return=baseline_metrics.total_return,
            stressed_total_return=metric_decimal(total_ret),
            baseline_max_drawdown=baseline_metrics.max_drawdown,
            stressed_max_drawdown=metric_decimal(max_dd),
            details={"delay_bars": 1},
            failure_reason=failure_reason,
        )


def _stress_adverse_spread_slippage(
    decisions: tuple[FoldDecisionV1, ...],
    baseline_metrics: StrategyMetricsV1,
    *,
    extra_friction: Decimal,
) -> StressScenarioResultV1:
    """Stress test: Adverse spread and slippage (+20 bps per trade)."""
    with localcontext() as context:
        context.prec = 60
        context.rounding = ROUND_HALF_EVEN

        decision_by_time: dict[datetime, list[Decimal]] = {}
        for decision in decisions:
            decision_by_time.setdefault(decision.decision_at, [])
            if decision.predicted_target == "UP":
                base_net = Decimal(decision.realized_net_return)
                stressed_net = base_net - extra_friction
                decision_by_time[decision.decision_at].append(stressed_net)

        stressed_period_returns: list[Decimal] = []
        for dt in sorted(decision_by_time):
            trades = decision_by_time[dt]
            if trades:
                stressed_period_returns.append(sum(trades) / Decimal(len(trades)))
            else:
                stressed_period_returns.append(Decimal(0))

        sharpe, total_ret, max_dd = _compute_return_metrics(tuple(stressed_period_returns))

        passed = total_ret > Decimal(0) and sharpe >= Decimal(0)
        failure_reason = None if passed else "Strategy fails under adverse spread/slippage regime"

        return StressScenarioResultV1(
            scenario_id=StressScenarioType.ADVERSE_SPREAD_SLIPPAGE.value,
            scenario_name="Adverse Spread and Slippage Regime",
            passed=passed,
            baseline_sharpe=baseline_metrics.sharpe_ratio,
            stressed_sharpe=metric_decimal(sharpe),
            baseline_total_return=baseline_metrics.total_return,
            stressed_total_return=metric_decimal(total_ret),
            baseline_max_drawdown=baseline_metrics.max_drawdown,
            stressed_max_drawdown=metric_decimal(max_dd),
            details={"extra_friction_bps": str(extra_friction * Decimal(10000))},
            failure_reason=failure_reason,
        )


def _stress_adverse_gap_regime(
    decisions: tuple[FoldDecisionV1, ...],
    baseline_metrics: StrategyMetricsV1,
    *,
    max_tolerated_drawdown: Decimal,
) -> StressScenarioResultV1:
    """Stress test: Adverse gap shock on the worst active decision session."""
    with localcontext() as context:
        context.prec = 60
        context.rounding = ROUND_HALF_EVEN

        decision_by_time: dict[datetime, list[Decimal]] = {}
        for decision in decisions:
            decision_by_time.setdefault(decision.decision_at, [])
            if decision.predicted_target == "UP":
                decision_by_time[decision.decision_at].append(Decimal(decision.realized_net_return))

        returns: list[Decimal] = []
        for dt in sorted(decision_by_time):
            trades = decision_by_time[dt]
            returns.append(sum(trades) / Decimal(len(trades)) if trades else Decimal(0))

        # Inject an adverse 10% gap shock on the worst active trading day
        active_indices = [i for i, r in enumerate(returns) if r != Decimal(0)]
        if active_indices:
            worst_idx = min(active_indices, key=lambda i: returns[i])
            returns[worst_idx] -= Decimal("0.10")  # -10% gap shock

        sharpe, total_ret, max_dd = _compute_return_metrics(tuple(returns))

        passed = max_dd <= max_tolerated_drawdown
        failure_reason = (
            None
            if passed
            else f"Max drawdown {max_dd} exceeds limit {max_tolerated_drawdown} under gap shock"
        )

        return StressScenarioResultV1(
            scenario_id=StressScenarioType.ADVERSE_GAP_REGIME.value,
            scenario_name="Adverse Gap Regime (-10% shock)",
            passed=passed,
            baseline_sharpe=baseline_metrics.sharpe_ratio,
            stressed_sharpe=metric_decimal(sharpe),
            baseline_total_return=baseline_metrics.total_return,
            stressed_total_return=metric_decimal(total_ret),
            baseline_max_drawdown=baseline_metrics.max_drawdown,
            stressed_max_drawdown=metric_decimal(max_dd),
            details={
                "injected_gap_fraction": "0.10",
                "max_tolerated_drawdown": str(max_tolerated_drawdown),
            },
            failure_reason=failure_reason,
        )


def _stress_data_anomaly_resilience(
    decisions: tuple[FoldDecisionV1, ...],
    baseline_metrics: StrategyMetricsV1,
) -> StressScenarioResultV1:
    """Stress test: Verify fail-closed data integrity and absence of non-finite outputs."""
    with localcontext() as context:
        context.prec = 60
        context.rounding = ROUND_HALF_EVEN

        passed = True
        failure_reason = None
        for d in decisions:
            if d.score is not None:
                parsed_score = Decimal(d.score)
                if not parsed_score.is_finite():
                    passed = False
                    failure_reason = "Non-finite score encountered in strategy decision"
                    break
            parsed_ret = Decimal(d.realized_net_return)
            if not parsed_ret.is_finite():
                passed = False
                failure_reason = "Non-finite realized return encountered in decision"
                break

        return StressScenarioResultV1(
            scenario_id=StressScenarioType.DATA_ANOMALY_RESILIENCE.value,
            scenario_name="Data Anomaly and Integrity Resilience",
            passed=passed,
            baseline_sharpe=baseline_metrics.sharpe_ratio,
            stressed_sharpe=baseline_metrics.sharpe_ratio,
            baseline_total_return=baseline_metrics.total_return,
            stressed_total_return=baseline_metrics.total_return,
            baseline_max_drawdown=baseline_metrics.max_drawdown,
            stressed_max_drawdown=baseline_metrics.max_drawdown,
            details={"checked_records": len(decisions)},
            failure_reason=failure_reason,
        )


def _compute_return_metrics(returns: tuple[Decimal, ...]) -> tuple[Decimal, Decimal, Decimal]:
    """Compute (annualized_sharpe, total_return, max_drawdown) with Decimal precision."""
    if not returns:
        return Decimal(0), Decimal(0), Decimal(0)
    count = Decimal(len(returns))
    mean = sum(returns) / count
    volatility = _sample_deviation(returns, mean)
    sharpe = mean / volatility * Decimal(252).sqrt() if volatility > 0 else Decimal(0)

    # Compound total return
    equity = Decimal(1)
    peak = equity
    max_dd = Decimal(0)
    for r in returns:
        equity *= Decimal(1) + r
        if equity > peak:
            peak = equity
        else:
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd
    total_ret = equity - Decimal(1)
    return sharpe, total_ret, max_dd


def _sample_deviation(values: tuple[Decimal, ...], mean: Decimal) -> Decimal:
    if len(values) < 2:
        return Decimal(0)
    variance = sum((v - mean) ** 2 for v in values) / Decimal(len(values) - 1)
    return variance.sqrt()


def _validate_stress_result_fields(result: StressScenarioResultV1) -> None:
    for field_name in (
        "baseline_sharpe",
        "stressed_sharpe",
        "baseline_total_return",
        "stressed_total_return",
        "baseline_max_drawdown",
        "stressed_max_drawdown",
    ):
        val = getattr(result, field_name)
        _require_canonical_decimal(val, field_name)


def _require_canonical_decimal(value: str, field_name: str) -> None:
    try:
        parsed = Decimal(value)
    except ArithmeticError as error:
        raise ValueError(f"{field_name} must be canonical decimal text") from error
    if not parsed.is_finite() or decimal_text(parsed) != value:
        raise ValueError(f"{field_name} must be finite canonical decimal text")
