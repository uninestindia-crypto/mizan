"""Tests for symbol rename handling and aliases in the market index."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import numpy as np

from quant_system.market import MarketIndex, build_market_index
from quant_system.market.index_builder import merge_renames
from quant_system.market.reference import load_symbol_history
from quant_system.market.sources import DatasetRef, Role
from quant_system.market.symbol_changes import SymbolChange, SymbolHistory
from tests.market_fixtures import (
    DATES,
    HISTORY,
    REFRESH,
    trending_rows,
    write_actions,
    write_dataset,
    write_reference,
)


def _write_symbol_changes(data_folder: Path, lines: list[str]) -> None:
    authorities = data_folder / "authorities"
    authorities.mkdir(parents=True, exist_ok=True)
    (authorities / "nse-symbol-changes.csv").write_text(
        "".join(line + "\n" for line in lines), encoding="utf-8"
    )


def test_renamed_stock_is_one_continuous_series(tmp_path: Path) -> None:
    """A renamed stock is one continuous series: history dataset under OLDCO (first 300 DATES),
    refresh dataset under NEWCO (DATES[100:], same price path so the overlap agrees),
    CSV OLDCO -> NEWCO. After build: symbols has NEWCO with stitch STITCHED and more bars
    than refresh alone; OLDCO not in symbols; aliases has (OLDCO, NEWCO, FORMER);
    stitch_note mentions OLDCO; bars("OLDCO") == bars("NEWCO"); search("oldco") returns NEWCO;
    meta renames_merged is 1.
    """
    data_folder = tmp_path / "data"
    index_dir = tmp_path / "index"
    cache = data_folder / "evidence" / "market-cache"
    rows = trending_rows(DATES, 100.0, 0.001)

    write_dataset(cache, HISTORY, "dset_old", "OLDCO", rows[:300], "2021-01-01T00:00:00Z")
    write_dataset(cache, REFRESH, "dset_new_r", "NEWCO", rows[100:], "2021-02-01T00:00:00Z")
    write_reference(
        data_folder,
        listings=["NEWCO,NEWCO LIMITED,INE0NEW,NSE_EQ|INE0NEW,EQ,NORMAL,1,1.0"],
        liquid=["NEWCO"],
    )
    _write_symbol_changes(data_folder, ["NewCo Limited,OLDCO,NEWCO,22-SEP-2020"])

    report = build_market_index(data_folder, index_dir)
    index = MarketIndex(index_dir)
    assert report.renames_merged == 1
    assert index.meta().get("renames_merged") == "1"

    # symbols has NEWCO with stitch "STITCHED" and more bars than refresh alone
    info = index.symbol_info("NEWCO")
    assert info["stitch"] == "STITCHED"
    assert info["sessions"] > len(DATES[100:])
    assert info["sessions"] == len(rows)

    # stitch_note mentions OLDCO
    assert "OLDCO" in info["stitch_note"]
    assert "History continues from the former symbol(s) OLDCO." in info["stitch_note"]

    # OLDCO is NOT a row in symbols
    with sqlite3.connect(index.current_path()) as conn:
        assert conn.execute("SELECT 1 FROM symbols WHERE symbol = 'OLDCO'").fetchone() is None
        # aliases has (OLDCO, NEWCO, FORMER)
        row = conn.execute(
            "SELECT alias, symbol, kind FROM aliases WHERE alias = 'OLDCO'"
        ).fetchone()
        assert row == ("OLDCO", "NEWCO", "FORMER")

    # index.bars("OLDCO") returns the same bars as index.bars("NEWCO")
    bars_old = index.bars("OLDCO")
    bars_new = index.bars("NEWCO")
    assert len(bars_old) == len(bars_new)
    assert bars_old.symbol == "NEWCO"
    assert np.array_equal(bars_old.close, bars_new.close)

    # index.search("oldco") returns NEWCO with matched_alias == "OLDCO"
    search_res = index.search("oldco")
    assert len(search_res) >= 1
    assert search_res[0]["symbol"] == "NEWCO"
    assert search_res[0]["matched_alias"] == "OLDCO"


def test_without_csv_nothing_changes(tmp_path: Path) -> None:
    """Without the CSV nothing changes: the same datasets build two separate symbols
    (OLDCO history-only, NEWCO refresh-only), the aliases table exists and is empty,
    and resolve("OLDCO") is 'OLDCO'.
    """
    data_folder = tmp_path / "data"
    index_dir = tmp_path / "index"
    cache = data_folder / "evidence" / "market-cache"
    rows = trending_rows(DATES, 100.0, 0.001)

    write_dataset(cache, HISTORY, "dset_old", "OLDCO", rows[:300], "2021-01-01T00:00:00Z")
    write_dataset(cache, REFRESH, "dset_new_r", "NEWCO", rows[100:], "2021-02-01T00:00:00Z")
    write_reference(
        data_folder,
        listings=[
            "OLDCO,OLDCO LIMITED,INE0OLD,NSE_EQ|INE0OLD,EQ,NORMAL,1,1.0",
            "NEWCO,NEWCO LIMITED,INE0NEW,NSE_EQ|INE0NEW,EQ,NORMAL,1,1.0",
        ],
        liquid=["NEWCO"],
    )

    build_market_index(data_folder, index_dir)
    index = MarketIndex(index_dir)

    with sqlite3.connect(index.current_path()) as conn:
        syms = [r[0] for r in conn.execute("SELECT symbol FROM symbols ORDER BY symbol").fetchall()]
        assert syms == ["NEWCO", "OLDCO"]
        count = conn.execute("SELECT COUNT(*) FROM aliases").fetchone()[0]
        assert count == 0

    assert index.resolve("OLDCO") == "OLDCO"
    assert index.resolve("NEWCO") == "NEWCO"
    assert index.symbol_info("OLDCO")["stitch"] == "HISTORY_ONLY"
    assert index.symbol_info("NEWCO")["stitch"] == "REFRESH_ONLY"


def test_safety_readjusted_prices_refuse_old_history(tmp_path: Path) -> None:
    """Safety: if the old history's prices disagree with the new refresh on overlapping dates,
    the symbols still merge under NEWCO but stitch is 'REFRESH_ONLY_READJUSTED' and old history
    is not used (stored bars equal the refresh alone).
    """
    data_folder = tmp_path / "data"
    index_dir = tmp_path / "index"
    cache = data_folder / "evidence" / "market-cache"
    rows = trending_rows(DATES, 100.0, 0.001)

    # Halved prices for history
    halved = [(d, o / 2, h / 2, low / 2, c / 2, v) for d, o, h, low, c, v in rows[:300]]
    write_dataset(cache, HISTORY, "dset_old", "OLDCO", halved, "2021-01-01T00:00:00Z")
    write_dataset(cache, REFRESH, "dset_new_r", "NEWCO", rows[100:], "2021-02-01T00:00:00Z")
    write_reference(
        data_folder,
        listings=["NEWCO,NEWCO LIMITED,INE0NEW,NSE_EQ|INE0NEW,EQ,NORMAL,1,1.0"],
        liquid=["NEWCO"],
    )
    _write_symbol_changes(data_folder, ["NewCo Limited,OLDCO,NEWCO,22-SEP-2020"])

    build_market_index(data_folder, index_dir)
    index = MarketIndex(index_dir)

    info = index.symbol_info("NEWCO")
    assert info["stitch"] == "REFRESH_ONLY_READJUSTED"
    assert info["sessions"] == len(DATES[100:])
    assert len(index.bars("NEWCO")) == len(DATES[100:])
    assert "different price basis" in info["stitch_note"]
    assert "History continues from the former symbol(s) OLDCO." in info["stitch_note"]


def test_live_former_label_never_merged(tmp_path: Path) -> None:
    """A live former label is never merged: OLDCO has both history AND refresh datasets,
    NEWCO has a refresh dataset, CSV OLDCO -> NEWCO. Both stay separate symbols;
    no alias row is created for either.
    """
    data_folder = tmp_path / "data"
    index_dir = tmp_path / "index"
    cache = data_folder / "evidence" / "market-cache"
    rows_old = trending_rows(DATES, 50.0, 0.001)
    rows_new = trending_rows(DATES, 100.0, 0.001)

    write_dataset(cache, HISTORY, "dset_old_h", "OLDCO", rows_old[:300], "2021-01-01T00:00:00Z")
    write_dataset(cache, REFRESH, "dset_old_r", "OLDCO", rows_old[100:], "2021-02-01T00:00:00Z")
    write_dataset(cache, REFRESH, "dset_new_r", "NEWCO", rows_new[100:], "2021-02-01T00:00:00Z")
    write_reference(
        data_folder,
        listings=[
            "OLDCO,OLDCO LIMITED,INE0OLD,NSE_EQ|INE0OLD,EQ,NORMAL,1,1.0",
            "NEWCO,NEWCO LIMITED,INE0NEW,NSE_EQ|INE0NEW,EQ,NORMAL,1,1.0",
        ],
        liquid=["OLDCO", "NEWCO"],
    )
    _write_symbol_changes(data_folder, ["NewCo Limited,OLDCO,NEWCO,22-SEP-2020"])

    report = build_market_index(data_folder, index_dir)
    assert report.renames_merged == 0

    index = MarketIndex(index_dir)
    with sqlite3.connect(index.current_path()) as conn:
        syms = [r[0] for r in conn.execute("SELECT symbol FROM symbols ORDER BY symbol").fetchall()]
        assert "OLDCO" in syms and "NEWCO" in syms
        alias_rows = conn.execute("SELECT alias, symbol FROM aliases").fetchall()
        assert not any(a[0] in ("OLDCO", "NEWCO") or a[1] in ("OLDCO", "NEWCO") for a in alias_rows)


def test_forward_alias_when_only_old_symbol_indexed(tmp_path: Path) -> None:
    """Forward alias: only OLDCO is indexed (history and refresh both under OLDCO),
    CSV OLDCO -> NEWCO, NEWCO has no data. index.search("newco") returns OLDCO with
    matched_alias == "NEWCO", index.bars("NEWCO") equals index.bars("OLDCO"),
    and alias row kind is 'NEW'.
    """
    data_folder = tmp_path / "data"
    index_dir = tmp_path / "index"
    cache = data_folder / "evidence" / "market-cache"
    rows = trending_rows(DATES, 100.0, 0.001)

    write_dataset(cache, HISTORY, "dset_old_h", "OLDCO", rows[:300], "2021-01-01T00:00:00Z")
    write_dataset(cache, REFRESH, "dset_old_r", "OLDCO", rows[100:], "2021-02-01T00:00:00Z")
    write_reference(
        data_folder,
        listings=["OLDCO,OLDCO LIMITED,INE0OLD,NSE_EQ|INE0OLD,EQ,NORMAL,1,1.0"],
        liquid=["OLDCO"],
    )
    _write_symbol_changes(data_folder, ["NewCo Limited,OLDCO,NEWCO,22-SEP-2020"])

    build_market_index(data_folder, index_dir)
    index = MarketIndex(index_dir)

    with sqlite3.connect(index.current_path()) as conn:
        row = conn.execute(
            "SELECT alias, symbol, kind FROM aliases WHERE alias = 'NEWCO'"
        ).fetchone()
        assert row == ("NEWCO", "OLDCO", "NEW")

    search_res = index.search("newco")
    assert len(search_res) >= 1
    assert search_res[0]["symbol"] == "OLDCO"
    assert search_res[0]["matched_alias"] == "NEWCO"

    bars_new = index.bars("NEWCO")
    bars_old = index.bars("OLDCO")
    assert bars_new.symbol == bars_old.symbol
    assert bars_new.dates == bars_old.dates
    assert np.array_equal(bars_new.close, bars_old.close)


def test_alias_that_is_indexed_symbol_never_wins(tmp_path: Path) -> None:
    """An alias that is an indexed symbol never wins: CSV claims OLDCO -> NEWCO while
    BOTH exist as indexed live symbols with their own data; resolve("OLDCO") is 'OLDCO'.
    """
    data_folder = tmp_path / "data"
    index_dir = tmp_path / "index"
    cache = data_folder / "evidence" / "market-cache"
    rows_old = trending_rows(DATES, 50.0, 0.001)
    rows_new = trending_rows(DATES, 100.0, 0.001)

    write_dataset(cache, HISTORY, "dset_old_h", "OLDCO", rows_old[:300], "2021-01-01T00:00:00Z")
    write_dataset(cache, REFRESH, "dset_old_r", "OLDCO", rows_old[100:], "2021-02-01T00:00:00Z")
    write_dataset(cache, REFRESH, "dset_new_r", "NEWCO", rows_new[100:], "2021-02-01T00:00:00Z")
    write_reference(
        data_folder,
        listings=[
            "OLDCO,OLDCO LIMITED,INE0OLD,NSE_EQ|INE0OLD,EQ,NORMAL,1,1.0",
            "NEWCO,NEWCO LIMITED,INE0NEW,NSE_EQ|INE0NEW,EQ,NORMAL,1,1.0",
        ],
        liquid=["OLDCO", "NEWCO"],
    )
    _write_symbol_changes(data_folder, ["NewCo Limited,OLDCO,NEWCO,22-SEP-2020"])

    build_market_index(data_folder, index_dir)
    index = MarketIndex(index_dir)

    assert index.resolve("OLDCO") == "OLDCO"
    assert index.resolve("NEWCO") == "NEWCO"


def test_old_index_without_aliases_table_still_works(tmp_path: Path) -> None:
    """An index built before this change still works: build an index, then remove the table
    (DROP TABLE aliases), then search, bars, symbol_info and resolve behave normally
    with no exception (matched_alias None).
    """
    data_folder = tmp_path / "data"
    index_dir = tmp_path / "index"
    cache = data_folder / "evidence" / "market-cache"
    rows = trending_rows(DATES, 100.0, 0.001)
    write_dataset(cache, HISTORY, "dset_aaa", "AAA", rows[:300], "2021-01-01T00:00:00Z")
    write_reference(
        data_folder,
        listings=["AAA,ALPHA LTD,INE0AAA,NSE_EQ|INE0AAA,EQ,NORMAL,1,1.0"],
        liquid=["AAA"],
    )

    build_market_index(data_folder, index_dir)
    index = MarketIndex(index_dir)

    # Drop the aliases table
    with sqlite3.connect(index.current_path()) as conn:
        conn.execute("DROP TABLE aliases")
        conn.commit()

    assert index.resolve("AAA") == "AAA"
    assert index.resolve("UNKNOWN") == "UNKNOWN"

    bars = index.bars("AAA")
    assert len(bars) == 300

    info = index.symbol_info("AAA")
    assert info["symbol"] == "AAA"

    search_res = index.search("aaa")
    assert len(search_res) == 1
    assert search_res[0]["symbol"] == "AAA"
    assert search_res[0]["matched_alias"] is None


def test_bars_many_returns_both_keys_after_merge(tmp_path: Path) -> None:
    """bars_many(["OLDCO", "NEWCO"]) after merge returns both keys, each with the same series."""
    data_folder = tmp_path / "data"
    index_dir = tmp_path / "index"
    cache = data_folder / "evidence" / "market-cache"
    rows = trending_rows(DATES, 100.0, 0.001)

    write_dataset(cache, HISTORY, "dset_old", "OLDCO", rows[:300], "2021-01-01T00:00:00Z")
    write_dataset(cache, REFRESH, "dset_new_r", "NEWCO", rows[100:], "2021-02-01T00:00:00Z")
    write_reference(
        data_folder,
        listings=["NEWCO,NEWCO LIMITED,INE0NEW,NSE_EQ|INE0NEW,EQ,NORMAL,1,1.0"],
        liquid=["NEWCO"],
    )
    _write_symbol_changes(data_folder, ["NewCo Limited,OLDCO,NEWCO,22-SEP-2020"])

    build_market_index(data_folder, index_dir)
    index = MarketIndex(index_dir)

    many = index.bars_many(["oldco", "NEWCO"])
    assert "OLDCO" in many and "NEWCO" in many
    assert many["OLDCO"].dates == many["NEWCO"].dates
    assert np.array_equal(many["OLDCO"].close, many["NEWCO"].close)


def test_search_ranking_order_and_deduplication(tmp_path: Path) -> None:
    """Search ranking: build symbols so an exact symbol match, an exact alias match,
    and a prefix match all occur; assert the documented order and that a symbol matched
    both ways appears once.
    Ranking order:
    1. exact symbol
    2. exact alias
    3. symbol prefix
    4. alias prefix
    5. other direct match
    6. other alias match
    then by symbol.
    """
    data_folder = tmp_path / "data"
    index_dir = tmp_path / "index"
    cache = data_folder / "evidence" / "market-cache"
    dates = DATES[:50]

    # Symbols:
    # 1. TARGET (exact symbol match)
    # 2. ALIASEXACT (exact alias match via alias TARGET; also direct match via name containing TARGET)
    # 3. TARGETPFX (symbol prefix match)
    # 4. ALIASPFX (alias prefix match via alias TARGETMORE)
    # 5. DIFFSYM (other direct match via name containing TARGET)
    # 6. OTHERALIAS (other alias match via alias X_TARGET_Y)
    syms = ["TARGET", "ALIASEXACT", "TARGETPFX", "ALIASPFX", "DIFFSYM", "OTHERALIAS"]
    for s in syms:
        write_dataset(
            cache, HISTORY, f"dset_{s}", s, trending_rows(dates, 100.0, 0.0), "2021-01-01T00:00:00Z"
        )

    write_reference(
        data_folder,
        listings=[
            "TARGET,First Co,INE0001,NSE_EQ|INE0001,EQ,NORMAL,1,1.0",
            "ALIASEXACT,Target Holding Co,INE0002,NSE_EQ|INE0002,EQ,NORMAL,1,1.0",
            "TARGETPFX,Prefix Co,INE0003,NSE_EQ|INE0003,EQ,NORMAL,1,1.0",
            "ALIASPFX,Alias Prefix Co,INE0004,NSE_EQ|INE0004,EQ,NORMAL,1,1.0",
            "DIFFSYM,A TARGET Product Co,INE0005,NSE_EQ|INE0005,EQ,NORMAL,1,1.0",
            "OTHERALIAS,Other Co,INE0006,NSE_EQ|INE0006,EQ,NORMAL,1,1.0",
        ],
        liquid=syms,
    )

    build_market_index(data_folder, index_dir)
    index = MarketIndex(index_dir)

    # Insert test aliases
    with sqlite3.connect(index.current_path()) as conn:
        conn.execute("INSERT INTO aliases VALUES ('TARGET', 'ALIASEXACT', 'FORMER')")
        conn.execute("INSERT INTO aliases VALUES ('TARGETMORE', 'ALIASPFX', 'FORMER')")
        conn.execute("INSERT INTO aliases VALUES ('X_TARGET_Y', 'OTHERALIAS', 'FORMER')")
        conn.commit()

    results = index.search("TARGET")
    returned_symbols = [r["symbol"] for r in results]
    assert returned_symbols == [
        "TARGET",
        "ALIASEXACT",
        "TARGETPFX",
        "ALIASPFX",
        "DIFFSYM",
        "OTHERALIAS",
    ]

    # Verify matched_alias for each
    by_sym = {r["symbol"]: r for r in results}
    assert by_sym["TARGET"]["matched_alias"] is None
    assert by_sym["ALIASEXACT"]["matched_alias"] == "TARGET"
    assert by_sym["TARGETPFX"]["matched_alias"] is None
    assert by_sym["ALIASPFX"]["matched_alias"] == "TARGETMORE"
    assert by_sym["DIFFSYM"]["matched_alias"] is None
    assert by_sym["OTHERALIAS"]["matched_alias"] == "X_TARGET_Y"

    # Verify ALIASEXACT matched both ways but appears only once
    assert returned_symbols.count("ALIASEXACT") == 1


def test_corporate_actions_under_old_label_indexed_under_new(tmp_path: Path) -> None:
    """Corporate actions: put an action file under the OLD label only;
    after the merge index.actions("NEWCO") returns it.
    """
    data_folder = tmp_path / "data"
    index_dir = tmp_path / "index"
    cache = data_folder / "evidence" / "market-cache"
    rows = trending_rows(DATES, 100.0, 0.001)

    write_dataset(cache, HISTORY, "dset_old", "OLDCO", rows[:300], "2021-01-01T00:00:00Z")
    write_dataset(cache, REFRESH, "dset_new_r", "NEWCO", rows[100:], "2021-02-01T00:00:00Z")
    write_reference(
        data_folder,
        listings=["NEWCO,NEWCO LIMITED,INE0NEW,NSE_EQ|INE0NEW,EQ,NORMAL,1,1.0"],
        liquid=["NEWCO"],
    )
    _write_symbol_changes(data_folder, ["NewCo Limited,OLDCO,NEWCO,22-SEP-2020"])

    # Write action file under OLDCO only
    write_actions(cache, HISTORY, "OLDCO", [("15-Jun-2020", "Demerger")])

    build_market_index(data_folder, index_dir)
    index = MarketIndex(index_dir)

    actions = index.actions("NEWCO")
    assert len(actions) == 1
    assert actions[0]["ex_date"] == "2020-06-15"
    assert actions[0]["subject"] == "Demerger"
    assert actions[0]["breaks_history"] is True


def test_merge_renames_unit_tests() -> None:
    """Unit tests of merge_renames itself (no filesystem): merging,
    own history wins case, former is live case, names=None, and input dicts not mutated.
    """

    def _ref(sym: str, role: Role = "HISTORY") -> DatasetRef:
        return DatasetRef(
            cache="c",
            role=role,
            dataset_id=f"d_{sym}",
            manifest_hash="mh",
            symbol=sym,
            instrument_key=f"NSE_EQ|{sym}",
            acquired_at="2020-01-01T00:00:00Z",
            range_start="2020-01-01",
            range_end="2020-12-31",
            row_count=10,
            blob_paths=(),
        )

    names = SymbolHistory([SymbolChange("Company", "OLDCO", "NEWCO", date(2020, 1, 1))])

    # 1. Merging
    h1 = {"OLDCO": _ref("OLDCO")}
    r1 = {"NEWCO": _ref("NEWCO", "REFRESH")}
    out_h, out_r, merged = merge_renames(h1, r1, names)
    assert "NEWCO" in out_h and out_h["NEWCO"] == h1["OLDCO"]
    assert "OLDCO" not in out_h
    assert out_r == r1
    assert merged == {"NEWCO": ("OLDCO",)}

    # 2. Own history wins
    h2 = {"OLDCO": _ref("OLDCO"), "NEWCO": _ref("NEWCO")}
    r2 = {"NEWCO": _ref("NEWCO", "REFRESH")}
    out_h2, out_r2, merged2 = merge_renames(h2, r2, names)
    assert out_h2["NEWCO"] == h2["NEWCO"]
    assert "OLDCO" in out_h2
    assert merged2 == {}

    # 3. Former is live (still in refresh)
    h3 = {"OLDCO": _ref("OLDCO")}
    r3 = {"OLDCO": _ref("OLDCO", "REFRESH"), "NEWCO": _ref("NEWCO", "REFRESH")}
    out_h3, out_r3, merged3 = merge_renames(h3, r3, names)
    assert "OLDCO" in out_h3
    assert "NEWCO" not in out_h3
    assert merged3 == {}

    # 4. names is None
    h4 = {"OLDCO": _ref("OLDCO")}
    r4 = {"NEWCO": _ref("NEWCO", "REFRESH")}
    out_h4, out_r4, merged4 = merge_renames(h4, r4, None)
    assert out_h4 == h4
    assert out_r4 == r4
    assert merged4 == {}

    # 5. Input dicts are not mutated
    h5 = {"OLDCO": _ref("OLDCO")}
    r5 = {"NEWCO": _ref("NEWCO", "REFRESH")}
    h5_copy = dict(h5)
    r5_copy = dict(r5)
    merge_renames(h5, r5, names)
    assert h5 == h5_copy
    assert r5 == r5_copy


def test_load_symbol_history_unit_tests(tmp_path: Path) -> None:
    """Unit tests of load_symbol_history: missing file -> None;
    file with only junk lines -> None; good file -> SymbolHistory.
    """
    # 1. Missing file -> None
    assert load_symbol_history(tmp_path / "nonexistent") is None

    # 2. File with only junk lines -> None
    data_junk = tmp_path / "data_junk"
    _write_symbol_changes(data_junk, ["junk,bad,line", "another,junk", ""])
    assert load_symbol_history(data_junk) is None

    # 3. Good file -> SymbolHistory
    data_good = tmp_path / "data_good"
    _write_symbol_changes(data_good, ["NewCo Limited,OLDCO,NEWCO,22-SEP-2020"])
    hist = load_symbol_history(data_good)
    assert hist is not None
    assert hist.current("OLDCO") == "NEWCO"
