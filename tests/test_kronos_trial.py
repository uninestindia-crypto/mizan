"""Short-horizon trial 10 (Kronos): the declared rules, pinned where a result could be bent.

The declaration is ``reports/kronos_trial/TRIAL-LEDGER.md``. These tests cover the parts of the
generator and the scorer that decide what is forecast, when the machine is left alone, what counts
as a trade, and what the verdict is. None of them loads a model or market data.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "src"))

import generate_kronos_forecasts as generator  # noqa: E402
import run_kronos_trial as scorer  # noqa: E402

from quant_system.research_short_horizon.evaluation import Decision  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))


# --- generator -------------------------------------------------------------------------------


def test_the_prediction_spans_the_labels_open_to_open() -> None:
    assert generator.predicted_return([100.0, 101.0, 102.0, 110.0]) == pytest.approx(0.10)


@pytest.mark.parametrize(
    "opens", [[100.0, 101.0, 102.0], [0.0, 1.0, 1.0, 1.0], [1.0, 1.0, 1.0, -1.0]]
)
def test_a_path_that_cannot_be_priced_is_refused(opens: list[float]) -> None:
    with pytest.raises(ValueError):
        generator.predicted_return(opens)


def test_each_date_has_its_own_fixed_seed() -> None:
    first, second = date(2024, 7, 1), date(2024, 7, 2)
    assert generator.date_seed(first) == generator.date_seed(first)
    assert generator.date_seed(first) != generator.date_seed(second)


@pytest.mark.parametrize(
    ("when", "inside"),
    [
        (datetime(2026, 9, 29, 8, 44, 59, tzinfo=IST), False),
        (datetime(2026, 9, 29, 8, 45, tzinfo=IST), True),
        (datetime(2026, 9, 29, 16, 29, 59, tzinfo=IST), True),
        (datetime(2026, 9, 29, 16, 30, tzinfo=IST), False),
        (datetime(2026, 10, 3, 11, 0, tzinfo=IST), False),  # Saturday
        (datetime(2026, 9, 29, 4, 0, tzinfo=UTC), True),  # 09:30 IST
    ],
)
def test_market_hours_belong_to_the_paper_books(when: datetime, inside: bool) -> None:
    assert generator.in_market_hours(when) is inside


def test_the_forecast_waits_for_market_hours_and_for_mains_power() -> None:
    open_market = datetime(2026, 9, 29, 10, 0, tzinfo=IST)
    evening = datetime(2026, 9, 29, 20, 0, tzinfo=IST)
    assert generator.pause_reason(open_market, True) is not None
    assert generator.pause_reason(evening, False) == "on battery"
    assert generator.pause_reason(evening, True) is None
    assert generator.pause_reason(evening, None) is None


def _bars(days: list[date]) -> list[generator.Bar]:
    return [generator.Bar(day, 10.0, 11.0, 9.0, 10.5, 1000.0) for day in days]


def test_the_plan_starts_at_the_cutoff_needs_context_and_four_later_sessions() -> None:
    days = [date(2024, 6, 24) + timedelta(days=offset) for offset in range(12)]
    bars = {"LONG": _bars(days), "SHORT": _bars(days[5:])}
    planned = generator.plan_dates(bars, start=date(2024, 7, 1), context=5, steps=4)

    assert [item.on for item in planned] == [date(2024, 7, 1)]
    assert planned[0].future == tuple(days[8:12])
    # SHORT starts on day 5, so on 2024-07-01 (day 7) it has only 3 bars of context.
    assert planned[0].symbols == ("LONG",)


def test_a_torn_checkpoint_line_is_dropped_not_fatal(tmp_path: Path) -> None:
    checkpoint = tmp_path / "forecasts.partial.jsonl"
    good = {"on": "2024-07-01", "symbol": "INFY", "predicted_return": 0.01}
    checkpoint.write_text(json.dumps(good) + "\n" + '{"on": "2024-07-02", "sym', encoding="utf-8")
    records, done = generator.read_checkpoint(checkpoint)
    assert records == [good]
    assert done == {("2024-07-01", "INFY")}


def test_the_compute_rule_takes_the_first_configuration_that_fits_a_night() -> None:
    timings = {("base", 5): 200.0, ("base", 1): 60.0, ("small", 5): 50.0, ("small", 1): 10.0}
    assert generator.choose_configuration(timings, dates=530)[:2] == ("base", 1)


def test_when_nothing_fits_the_smallest_runs_longer_rather_than_on_less_data() -> None:
    timings = {("base", 5): 900.0, ("base", 1): 400.0, ("small", 5): 300.0, ("small", 1): 120.0}
    model, samples, hours = generator.choose_configuration(timings, dates=530)
    assert (model, samples) == ("small", 1)
    assert hours > generator.NIGHT_BUDGET_HOURS


# --- scorer ----------------------------------------------------------------------------------


def _decision(on: date, symbol: str, net: str, previous: float = 0.0) -> Decision:
    return Decision(
        on=on, symbol=symbol, features=(), net_return=Decimal(net), previous_return=previous
    )


def test_only_the_declared_window_is_scored_in_date_then_name_order() -> None:
    rows = [
        _decision(date(2024, 7, 2), "B", "0.01"),
        _decision(date(2024, 6, 28), "A", "0.01"),
        _decision(date(2024, 7, 2), "A", "0.01"),
        _decision(date(2024, 7, 1), "C", "0.01"),
    ]
    kept = scorer.in_window(rows, start=date(2024, 7, 1))
    assert [(row.on, row.symbol) for row in kept] == [
        (date(2024, 7, 1), "C"),
        (date(2024, 7, 2), "A"),
        (date(2024, 7, 2), "B"),
    ]


def test_the_rule_needs_the_forecast_to_beat_the_cost_and_missing_is_cash() -> None:
    day = date(2024, 7, 1)
    rows = [
        _decision(day, "ABOVE", "0"),
        _decision(day, "EQUAL", "0"),
        _decision(day, "MISSING", "0"),
    ]
    predictions = {(day, "ABOVE"): 0.00225, (day, "EQUAL"): scorer.THRESHOLD}
    take, missing = scorer.take_by_threshold(rows, predictions)
    assert take == [True, False, False]
    assert missing == 1


def test_all_three_conditions_together_pass() -> None:
    outcome, checks = scorer.verdict(
        gate_passed=True, candidate_sharpe=1.5, noise_sharpes=[0.2, 1.4], always=1.0
    )
    assert outcome == "PASS_PENDING_INDEPENDENT_CHECK"
    assert all(checks.values())


@pytest.mark.parametrize(
    ("gate_passed", "noise_sharpes", "always", "failed_check"),
    [
        (False, [0.2, 1.4], 1.0, "gate_passed"),
        (True, [0.2, 1.6], 1.0, "beats_every_noise_seed"),
        (True, [], 1.0, "beats_every_noise_seed"),
        (True, [0.2, 1.4], 1.5, "beats_always_trade"),
    ],
)
def test_failing_any_one_condition_is_research_only(
    gate_passed: bool, noise_sharpes: list[float], always: float, failed_check: str
) -> None:
    outcome, checks = scorer.verdict(
        gate_passed=gate_passed, candidate_sharpe=1.5, noise_sharpes=noise_sharpes, always=always
    )
    assert outcome == "RESEARCH_ONLY"
    assert checks[failed_check] is False


def test_ranks_share_ties_and_spearman_is_signed() -> None:
    assert list(scorer.average_ranks([3.0, 1.0, 3.0, 2.0])) == [3.5, 1.0, 3.5, 2.0]
    assert scorer.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert scorer.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert scorer.spearman([1, 1, 1], [1, 2, 3]) is None


def test_t_stat_needs_spread() -> None:
    assert scorer.t_stat([1.0]) is None
    assert scorer.t_stat([2.0, 2.0, 2.0]) is None
    assert scorer.t_stat([1.0, 2.0, 3.0]) == pytest.approx(2.0 / (1.0 / 3**0.5))


def test_diagnostics_measure_ranking_and_the_top_quintile_edge() -> None:
    day = date(2024, 7, 1)
    names = [f"N{i}" for i in range(10)]
    rows = [_decision(day, name, str(i / 100)) for i, name in enumerate(names)]
    predictions = {(day, name): float(i) for i, name in enumerate(names)}
    result = scorer.diagnostics(rows, predictions)
    assert result["rank_ic"]["mean_all_dates"] == pytest.approx(1.0)
    # Top 2 of 10 earn 0.085 on average against an equal-weight 0.045.
    edge = result["top_quintile_edge_vs_equal_weight"]["mean_all_dates"]
    assert edge == pytest.approx(0.04)


def test_the_trial_is_scored_once(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    existing = tmp_path / "results-kronos.json"
    existing.write_text("{}", encoding="utf-8")
    forecasts = tmp_path / "kronos-forecasts.json"
    forecasts.write_text('{"forecasts": []}', encoding="utf-8")
    assert scorer.main(["--out", str(existing), "--forecasts", str(forecasts)]) == 2
    assert "scored once" in capsys.readouterr().out
