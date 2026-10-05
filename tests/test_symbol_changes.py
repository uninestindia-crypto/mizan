"""Tests for the NSE symbol changes parser and history resolver."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from quant_system.market.symbol_changes import (
    SymbolChange,
    SymbolHistory,
    parse_symbol_changes,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "nse-symbolchange-sample.csv"


def _load_sample_csv() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_real_sample_file_parses_to_11_sorted_changes_with_collapsed_spacing() -> None:
    """Verify the real sample file parses to 11 changes, sorted by date, with collapsed spacing."""
    text = _load_sample_csv()
    changes = parse_symbol_changes(text)

    assert len(changes) == 11

    # Verify changes are sorted by (effective, old, new)
    effective_dates = [c.effective for c in changes]
    assert effective_dates == sorted(effective_dates)
    assert changes == tuple(sorted(changes, key=lambda c: (c.effective, c.old, c.new)))

    # Verify Nippon row retains collapsed whitespace (leading space stripped,
    # internal doubled space collapsed)
    nippon = next(c for c in changes if c.old == "RDAXEDG")
    assert nippon.company == "NIPPON INDIA MF - NIPPON INDIA Dual Advantage FTF Sr. x Plan E - GO"
    assert nippon.new == "NDAXEDG"
    assert nippon.effective == date(2019, 10, 30)


def test_heg_to_hegam_single_hop_and_current() -> None:
    """Verify HEG -> HEGAM resolution: successors, predecessors, and current symbol resolution."""
    changes = parse_symbol_changes(_load_sample_csv())
    history = SymbolHistory(changes)

    assert history.successors("HEG") == ("HEGAM",)
    assert history.predecessors("HEGAM") == ("HEG",)
    assert history.current("HEG") == "HEGAM"
    assert history.current("HEGAM") == "HEGAM"


def test_zomato_to_eternal_former_symbols_and_company() -> None:
    """Verify ZOMATO -> ETERNAL former_symbols alias and company_for lookup."""
    changes = parse_symbol_changes(_load_sample_csv())
    history = SymbolHistory(changes)

    assert history.former_symbols("ETERNAL") == ("ZOMATO",)
    assert history.company_for("ZOMATO") == "ETERNAL LIMITED"
    assert history.company_for("ETERNAL") == "ETERNAL LIMITED"


def test_chain_across_three_symbols_pdumjeagro() -> None:
    """Verify 3-symbol chain: PDUMJEAGRO -> PDUMJEIND -> 3PLAND with nearest/recent ordering."""
    changes = parse_symbol_changes(_load_sample_csv())
    history = SymbolHistory(changes)

    assert history.successors("PDUMJEAGRO") == ("PDUMJEIND", "3PLAND")
    assert history.predecessors("3PLAND") == ("PDUMJEIND", "PDUMJEAGRO")
    assert history.current("PDUMJEAGRO") == "3PLAND"


def test_telco_to_tatamotors_to_tmpv_chain() -> None:
    """Verify TELCO -> TATAMOTORS (2003) -> TMPV (2025) forward and backward traversal."""
    changes = parse_symbol_changes(_load_sample_csv())
    history = SymbolHistory(changes)

    assert history.successors("TELCO") == ("TATAMOTORS", "TMPV")
    assert history.predecessors("TMPV") == ("TATAMOTORS", "TELCO")


def test_date_rule_prevents_chaining_recycled_symbols_backwards_in_time() -> None:
    """Verify date rule: links followed only if non-decreasing forward, non-increasing backward."""
    # X -> Y in 2010; a DIFFERENT older row Y -> Z is dated 2005 (predates link into Y)
    change_xy = SymbolChange(
        company="Company XY",
        old="X",
        new="Y",
        effective=date(2010, 6, 1),
    )
    change_yz = SymbolChange(
        company="Company YZ",
        old="Y",
        new="Z",
        effective=date(2005, 1, 1),
    )
    history = SymbolHistory([change_xy, change_yz])

    # Z must not be chained because it predates the link into Y
    assert history.successors("X") == ("Y",)
    # Tracing backward from Z must not include X because X -> Y postdates the link into Z
    assert "X" not in history.predecessors("Z")
    assert history.predecessors("Z") == ("Y",)


def test_cycle_safety_terminates_without_repeating_or_including_start_symbol() -> None:
    """Verify cycle safety: A -> B (2001) and B -> A (2002) terminates and excludes start symbol."""
    change_ab = SymbolChange(
        company="Cycle Corp",
        old="A",
        new="B",
        effective=date(2001, 1, 1),
    )
    change_ba = SymbolChange(
        company="Cycle Corp",
        old="B",
        new="A",
        effective=date(2002, 1, 1),
    )
    history = SymbolHistory([change_ab, change_ba])

    succ_a = history.successors("A")
    assert succ_a == ("B",)
    assert "A" not in succ_a

    succ_b = history.successors("B")
    assert succ_b == ("A",)
    assert "B" not in succ_b


def test_case_and_whitespace_insensitivity_and_unknown_symbol() -> None:
    """Verify case- and whitespace-insensitive lookups, and unknown symbols return default."""
    changes = parse_symbol_changes(_load_sample_csv())
    history = SymbolHistory(changes)

    # Whitespace and case insensitivity
    assert history.successors("  heg  ") == ("HEGAM",)
    assert history.predecessors("  hegam  ") == ("HEG",)
    assert history.current("  heg  ") == "HEGAM"
    assert history.company_for("  heg  ") == "HEG Advanced Materials Limited"

    # Unknown symbol
    assert history.successors("UNKNOWN_SYM") == ()
    assert history.predecessors("UNKNOWN_SYM") == ()
    assert history.former_symbols("UNKNOWN_SYM") == ()
    assert history.company_for("UNKNOWN_SYM") is None
    assert history.current("UNKNOWN_SYM") == "UNKNOWN_SYM"
    assert history.current("  unknown_sym  ") == "UNKNOWN_SYM"


def test_adversarial_rows_skipped_bom_tolerated_duplicates_collapsed() -> None:
    """Verify adversarial CSV rows are skipped, BOM is tolerated, and duplicate rows collapse."""
    clean_text = _load_sample_csv()
    clean_changes = parse_symbol_changes(clean_text)
    assert len(clean_changes) == 11

    # Adversarial additions as strings:
    # 1. 3 columns only
    row_three_columns = "Broken Row,ONLY_THREE,COLS"
    # 2. Unparseable date
    row_bad_date = "Bad Date Limited,OLD1,NEW1,31-FOO-2025"
    # 3. Old equals new
    row_old_equals_new = "Same Symbol Limited,IDENTICAL,IDENTICAL,01-JAN-2025"
    # 4. Blank lines
    blank_lines = "\n   \n\n"
    # 5. Empty old or new symbol
    row_empty_old = "Empty Old Corp,,SOME_NEW,01-JAN-2025"
    row_empty_new = "Empty New Corp,SOME_OLD,,01-JAN-2025"
    # 6. Duplicate rows from sample
    duplicate_rows = clean_text

    adversarial_payload = (
        f"{row_three_columns}\n"
        f"{row_bad_date}\n"
        f"{row_old_equals_new}\n"
        f"{blank_lines}"
        f"{clean_text}\n"
        f"{row_empty_old}\n"
        f"{row_empty_new}\n"
        f"{duplicate_rows}\n"
    )

    # Parsing adversarial payload must not raise and must collapse duplicates to the exact clean set
    parsed_adversarial = parse_symbol_changes(adversarial_payload)
    assert parsed_adversarial == clean_changes

    # Tolerating UTF-8 BOM prefix
    bom_text = "\ufeff" + clean_text
    parsed_bom = parse_symbol_changes(bom_text)
    assert parsed_bom == clean_changes


def test_a_symbol_with_two_incoming_changes_lists_predecessors_most_recent_first() -> None:
    """Verify a symbol with two incoming changes lists predecessors most recent first."""
    change_xs = SymbolChange(
        company="Company XS",
        old="X",
        new="S",
        effective=date(2005, 1, 1),
    )
    change_ys = SymbolChange(
        company="Company YS",
        old="Y",
        new="S",
        effective=date(2010, 1, 1),
    )
    changes = [change_xs, change_ys]

    assert SymbolHistory(changes).predecessors("S") == ("Y", "X")
    assert SymbolHistory(list(reversed(changes))).predecessors("S") == ("Y", "X")


def test_a_symbol_with_two_outgoing_changes_follows_them_in_date_order() -> None:
    """Verify a symbol with two outgoing changes follows them in date order."""
    change_xa = SymbolChange(
        company="Company XA",
        old="X",
        new="A",
        effective=date(2005, 1, 1),
    )
    change_xb = SymbolChange(
        company="Company XB",
        old="X",
        new="B",
        effective=date(2010, 1, 1),
    )
    changes = [change_xa, change_xb]

    assert SymbolHistory(changes).successors("X") == ("A", "B")
    assert SymbolHistory(list(reversed(changes))).successors("X") == ("A", "B")
