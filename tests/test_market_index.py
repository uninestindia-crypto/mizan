"""Market index: stitching, provenance, universes, snapshots, actions and the read API."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from quant_system.market import (
    IndexNotReadyError,
    MarketIndex,
    SymbolNotFoundError,
    build_market_index,
    metrics,
)
from quant_system.market.index_builder import IndexBuildError, detect_gap_flags, stitch
from quant_system.market.reference import classify_action, load_corporate_actions
from quant_system.market.sources import RawBar
from tests.market_fixtures import DATES, HISTORY, build_standard_store, sessions, write_dataset


@pytest.fixture()
def data_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "data"
    build_standard_store(folder)
    return folder


@pytest.fixture()
def built(data_folder: Path, tmp_path: Path) -> MarketIndex:
    build_market_index(data_folder, tmp_path / "index")
    return MarketIndex(tmp_path / "index")


# ------------------------------------------------------------------------------ stitching


def _bars(dates: list[str], closes: list[float]) -> list[RawBar]:
    return [RawBar(d=d, o=c, h=c, low=c, c=c, v=1) for d, c in zip(dates, closes, strict=True)]


def test_stitch_joins_only_when_every_overlapping_session_agrees() -> None:
    history = _bars(["d1", "d2", "d3"], [10.0, 11.0, 12.0])
    refresh = _bars(["d2", "d3", "d4"], [11.0, 12.0, 13.0])
    result = stitch(history, refresh)
    assert result.status == "STITCHED"
    assert [b.d for b in result.bars] == ["d1", "d2", "d3", "d4"]
    assert result.used == {"REFRESH": (3, "d2", "d4"), "HISTORY": (1, "d1", "d1")}


def test_stitch_refuses_a_readjusted_history_and_keeps_the_refresh() -> None:
    history = _bars(["d1", "d2", "d3"], [10.0, 11.0, 12.0])
    refresh = _bars(["d2", "d3", "d4"], [5.5, 6.0, 6.5])
    result = stitch(history, refresh)
    assert result.status == "REFRESH_ONLY_READJUSTED"
    assert [b.d for b in result.bars] == ["d2", "d3", "d4"]
    assert "re-adjusted" in result.note and "d2" in result.note


def test_stitch_tolerates_differences_within_tolerance_only() -> None:
    history = _bars(["d1", "d2"], [100.0, 100.0])
    assert stitch(history, _bars(["d2", "d3"], [100.09, 101.0])).status == "STITCHED"
    assert stitch(history, _bars(["d2", "d3"], [100.2, 101.0])).status == "REFRESH_ONLY_READJUSTED"


@pytest.mark.parametrize(
    ("history", "refresh", "status"),
    [
        (_bars(["d1"], [1.0]), None, "HISTORY_ONLY"),
        (None, _bars(["d1"], [1.0]), "REFRESH_ONLY"),
        (_bars(["d1", "d2"], [1.0, 1.0]), _bars(["d0"], [1.0]), "HISTORY_ONLY"),
        (_bars(["d1"], [1.0]), _bars(["d2"], [1.0]), "REFRESH_ONLY"),
        (None, None, "EMPTY"),
    ],
)
def test_stitch_edge_cases(
    history: list[RawBar] | None, refresh: list[RawBar] | None, status: str
) -> None:
    assert stitch(history, refresh).status == status


# ------------------------------------------------------------------------------- build


def test_build_reports_every_symbol_and_how_it_was_joined(
    data_folder: Path, tmp_path: Path
) -> None:
    report = build_market_index(data_folder, tmp_path / "index")
    assert report.symbols == 4
    assert report.stitch_counts == {
        "STITCHED": 1,
        "REFRESH_ONLY_READJUSTED": 1,
        "HISTORY_ONLY": 1,
        "REFRESH_ONLY": 1,
    }
    assert report.invalid_rows == 1
    assert report.latest_session == DATES[-1]
    assert report.bars == 320 + 220 + 300 + 220


def test_uncommitted_datasets_are_ignored(built: MarketIndex) -> None:
    with pytest.raises(SymbolNotFoundError):
        built.symbol_info("CCC")


def test_newest_history_vintage_wins(built: MarketIndex) -> None:
    series = built.bars("AAA")
    assert series.close[0] == pytest.approx(100.1)


def test_stitched_symbol_keeps_history_and_records_both_sources(built: MarketIndex) -> None:
    info = built.symbol_info("AAA")
    assert info["stitch"] == "STITCHED"
    assert (info["first_date"], info["last_date"], info["sessions"]) == (DATES[0], DATES[-1], 320)
    roles = {
        s["role"]: (s["rows_used"], s["dataset_id"], s["manifest_hash"]) for s in info["sources"]
    }
    assert roles == {
        "HISTORY": (100, "dset_aaa", "mh-dset_aaa"),
        "REFRESH": (220, "dset_aaa_r", "mh-dset_aaa_r"),
    }
    assert sorted(info["universes"]) == ["all", "liquid", "nifty500"]
    assert info["name"] == "ALPHA LTD"


def test_readjusted_symbol_uses_refresh_only_and_says_why(built: MarketIndex) -> None:
    info = built.symbol_info("BBB")
    assert info["stitch"] == "REFRESH_ONLY_READJUSTED"
    assert info["sessions"] == 220 and info["first_date"] == DATES[100]
    assert "different price basis" in info["stitch_note"]


def test_etf_and_surveillance_flags_come_from_listings(built: MarketIndex) -> None:
    assert built.symbol_info("NIFTYBEES")["is_etf"] == 1
    ddd = built.symbol_info("DDD")
    assert (ddd["series"], ddd["security_type"], ddd["is_etf"]) == ("BE", "PCA", 0)


def test_universes(built: MarketIndex) -> None:
    assert built.universe("liquid") == ["AAA", "BBB"]
    assert built.universe("nifty500") == ["AAA", "BBB", "DDD"]
    assert built.universe("all") == ["AAA", "BBB", "DDD", "NIFTYBEES"]


def test_snapshot_values_match_the_last_bars(built: MarketIndex) -> None:
    rows = {r["symbol"]: r for r in built.snapshot("all")}
    series = built.bars("AAA")
    aaa = rows["AAA"]
    assert aaa["asof"] == DATES[-1]
    assert aaa["close"] == series.close[-1]
    assert aaa["chg_1d"] == pytest.approx(series.close[-1] / series.close[-2] - 1)
    assert aaa["ret_1m"] == pytest.approx(series.close[-1] / series.close[-22] - 1)
    assert aaa["high_52w"] == pytest.approx(series.high[-252:].max())
    assert aaa["sma_200"] == pytest.approx(series.close[-200:].mean())
    assert rows["NIFTYBEES"]["asof"] == DATES[299]


def test_corporate_actions_are_classified_and_breaks_are_windowed(built: MarketIndex) -> None:
    actions = built.actions("BBB")
    assert [(a["ex_date"], a["breaks_history"]) for a in actions] == [
        ("2020-03-01", False),
        ("2020-06-15", True),
    ]
    assert built.breaking_actions(["AAA", "BBB"], "2020-01-01", "2020-12-31") == {
        "BBB": [{"ex_date": "2020-06-15", "subject": "Demerger"}]
    }
    assert built.breaking_actions(["BBB"], "2020-06-15", "2020-12-31") == {}
    assert built.breaking_actions(["BBB"], "2020-01-01", "2020-06-14") == {}


def test_search_ranks_exact_and_prefix_matches_first(built: MarketIndex) -> None:
    results = built.search("aaa")
    assert results[0]["symbol"] == "AAA"
    assert built.search("delta")[0]["symbol"] == "DDD"
    assert built.search("   ") == []


def test_bars_filters_by_date_and_rejects_unknown_symbols(built: MarketIndex) -> None:
    series = built.bars("AAA", start=DATES[10], end=DATES[19])
    assert series.dates == DATES[10:20]
    with pytest.raises(SymbolNotFoundError):
        built.bars("ZZZ")
    many = built.bars_many(["aaa", "BBB", "ZZZ"], end=DATES[150])
    assert sorted(many) == ["AAA", "BBB"]
    assert many["AAA"].dates[-1] == DATES[150]


def test_overview_counts_only_current_symbols_and_reports_stale_ones(built: MarketIndex) -> None:
    overview = built.overview()
    breadth = overview["breadth"]
    assert (breadth["count"], breadth["stale"]) == (2, 0)
    assert breadth["advancers"] + breadth["decliners"] + breadth["unchanged"] == 2
    assert overview["benchmark"]["symbol"] == "NIFTYBEES"
    assert len(overview["benchmark"]["spark"]) == 63


def test_missing_index_is_not_ready(tmp_path: Path) -> None:
    index = MarketIndex(tmp_path / "nothing")
    assert not index.is_ready()
    with pytest.raises(IndexNotReadyError):
        index.meta()


def test_build_without_caches_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(IndexBuildError):
        build_market_index(tmp_path / "empty", tmp_path / "index")


def test_rebuild_repoints_current_even_while_a_reader_holds_the_old_file(
    data_folder: Path, tmp_path: Path
) -> None:
    index_dir = tmp_path / "index"
    first = build_market_index(data_folder, index_dir)
    reader = sqlite3.connect(first.index_path)
    try:
        second = build_market_index(data_folder, index_dir)
        assert MarketIndex(index_dir).current_path() == second.index_path
    finally:
        reader.close()
    third = build_market_index(data_folder, index_dir)
    remaining = sorted(p.name for p in index_dir.glob("market-index-*.sqlite"))
    assert remaining == [third.index_path.name]
    assert MarketIndex(index_dir).is_ready()


def test_stored_prices_round_trip_to_the_provider_decimal_strings(built: MarketIndex) -> None:
    from decimal import Decimal

    for value in built.bars("AAA").close[:50]:
        assert Decimal(repr(float(value))) == Decimal(str(round(float(value), 2)))


# ----------------------------------------------------------------------------- metrics


def test_period_return_and_short_history() -> None:
    close = np.array([100.0, 110.0, 121.0])
    assert metrics.period_return(close, 1) == pytest.approx(0.1)
    assert metrics.period_return(close, 2) == pytest.approx(0.21)
    assert metrics.period_return(close, 3) is None


def test_rolling_windows_and_drawdown() -> None:
    values = np.array([1.0, 2.0, 3.0, 4.0])
    assert np.isnan(metrics.rolling_mean(values, 3)[1])
    assert metrics.rolling_mean(values, 3)[-1] == pytest.approx(3.0)
    assert metrics.rolling_max(values, 2)[-1] == 4.0
    assert metrics.rolling_min(values, 2)[-1] == 3.0
    assert metrics.max_drawdown(np.array([1.0, 2.0, 1.0, 1.5])) == pytest.approx(-0.5)
    assert metrics.max_drawdown(np.array([])) == 0.0


def test_rsi_is_100_for_a_rising_series_and_uses_no_future_data() -> None:
    rising = np.arange(1.0, 31.0)
    out = metrics.rsi(rising, 14)
    assert np.isnan(out[13]) and out[14] == pytest.approx(100.0)
    changed = rising.copy()
    changed[-1] = 1.0
    assert metrics.rsi(changed, 14)[20] == out[20]


def test_beta_of_a_series_against_itself_is_one() -> None:
    series = 100 * np.cumprod(1 + np.sin(np.arange(100)) / 100)
    assert metrics.beta(series, series) == pytest.approx(1.0)
    assert metrics.beta(series[:30], series[:30]) is None


# --------------------------------------------------------------------------- reference


@pytest.mark.parametrize(
    ("subject", "kinds", "breaks"),
    [
        ("Demerger", ("demerger",), True),
        ("Scheme Of Arrangement Of Demerger", ("demerger",), True),
        ("Rights 1:5 @ Premium Rs 100/-", ("rights",), True),
        ("Bonus 1:1", ("bonus",), False),
        (
            "Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share",
            ("split",),
            False,
        ),
        ("Interim Dividend - Rs 5 Per Share", ("dividend",), False),
        ("Annual General Meeting", ("meeting",), False),
        ("Something else entirely", ("other",), False),
    ],
)
def test_classify_action(subject: str, kinds: tuple[str, ...], breaks: bool) -> None:
    action = classify_action("X", "2020-01-01", subject)
    assert action.kinds == kinds
    assert action.breaks_history is breaks


def test_load_corporate_actions_skips_unparseable_records(tmp_path: Path) -> None:
    path = tmp_path / "ca.json"
    path.write_text(
        '[{"exDate": "07-Sep-2026", "subject": " Demerger "}, {"exDate": "-", "subject": "x"}, "junk"]',
        encoding="utf-8",
    )
    actions = load_corporate_actions(path, "HEG")
    assert [(a.ex_date, a.subject, a.breaks_history) for a in actions] == [
        ("2026-09-07", "Demerger", True)
    ]


# --------------------------------------------------------------------------- data breaks


def _gap_bars(before: float, after: float, n_before: int = 30, n_after: int = 30) -> list[RawBar]:
    dates = sessions(date(2021, 1, 1), n_before + n_after)
    bars = [RawBar(d=d, o=before, h=before, low=before, c=before, v=100) for d in dates[:n_before]]
    bars += [RawBar(d=d, o=after, h=after, low=after, c=after, v=100) for d in dates[n_before:]]
    return bars


def test_unexplained_overnight_collapse_is_a_data_break() -> None:
    bars = _gap_bars(850.95, 433.10)
    flags = detect_gap_flags("SPLPETRO", bars, [])
    assert [(f.d, f.kind) for f in flags] == [(bars[30].d, "UNEXPLAINED_GAP")]
    assert "no recorded corporate action" in flags[0].note


def test_listing_day_jump_from_pre_listing_records_is_a_data_break() -> None:
    flags = detect_gap_flags("RAINBOW", _gap_bars(1.0, 680.0, n_before=5), [])
    assert flags[0].kind == "UNEXPLAINED_GAP" and flags[0].change == pytest.approx(679.0)


def test_demerger_on_the_gap_date_is_handled_as_a_corporate_action_not_a_flag() -> None:
    bars = _gap_bars(100.0, 40.0)
    action = classify_action("HEG", bars[30].d, "Demerger")
    assert detect_gap_flags("HEG", bars, [action]) == []


def test_recorded_bonus_the_provider_did_not_apply_is_flagged_as_unadjusted() -> None:
    bars = _gap_bars(100.0, 50.0)
    action = classify_action("X", bars[30].d, "Bonus 1:1")
    assert [f.kind for f in detect_gap_flags("X", bars, [action])] == ["UNADJUSTED_ACTION"]


@pytest.mark.parametrize("after", [61.0, 179.0])
def test_moves_inside_the_bounds_are_not_flagged(after: float) -> None:
    assert detect_gap_flags("X", _gap_bars(100.0, after), []) == []


def test_build_drops_prices_before_the_last_data_break_and_says_why(tmp_path: Path) -> None:
    folder = tmp_path / "data"
    build_standard_store(folder)
    gap_rows = [(b.d, b.o, b.h, b.low, b.c, b.v) for b in _gap_bars(850.95, 433.10, 40, 260)]
    write_dataset(
        folder / "evidence" / "market-cache",
        HISTORY,
        "dset_gap",
        "GAPCO",
        gap_rows,
        "2021-01-01T00:00:00Z",
    )
    report = build_market_index(folder, tmp_path / "index")
    index = MarketIndex(tmp_path / "index")
    info = index.symbol_info("GAPCO")
    assert report.flags == 1
    assert (info["first_date"], info["sessions"]) == (gap_rows[40][0], 260)
    assert "are not used" in info["stitch_note"] and "40 sessions" in info["stitch_note"]
    assert [f["kind"] for f in index.flags("GAPCO")] == ["UNEXPLAINED_GAP"]
    assert index.bars("GAPCO").close.max() == pytest.approx(433.10)
    assert index.flags_in_window(["GAPCO", "AAA"], "2020-01-01", "2030-01-01") == {
        "GAPCO": [index.flags("GAPCO")[0]]
    }


def test_a_ten_year_refresh_only_symbol_is_not_called_a_recent_refresh() -> None:
    """The first-run download writes one ten-year refresh cache; warning that only the 'recent
    refresh' exists, directly above '2,474 sessions from 2016', contradicted itself."""
    ten_years = _bars(["2016-10-05", "2021-10-05", "2026-10-01"], [1.0, 1.0, 1.0])
    long_result = stitch(None, ten_years)
    assert long_result.status == "REFRESH_ONLY" and long_result.note == ""
    short = stitch(None, _bars(["2026-09-01", "2026-10-01"], [1.0, 1.0]))
    assert short.note == "Only the recent refresh exists for this symbol."
