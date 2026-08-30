"""The kernel must reproduce the published feature store, and that must be measured.

`execution/mizan_live_features.py` asserted in a module docstring that the kernel was "verified
bit-identical against the published feature store". No test opened the store. A Red Team sweep of
all 1,015,831 published rows found the claim false: `cs_rank_momentum_5` differed on **244 rows
across 115 of 2,427 dates**, because `apply_cross_sectional_ranks` sorted values that had been
round-tripped through the 10-decimal text while `build_mizan_feature_store.py:174` sorted raw
floats. Two names differing below 1e-10 were a tie to one and ordered by the other.

The sort now takes the raw floats, so the execution path follows the builder's procedure. That is
where the improvement stops, and saying so precisely matters: those 244 rows remain permanently
unreproducible *from the store*, because both names carry byte-identical published text and the
quantisation destroyed the difference the builder sorted on. No ranking rule can recover it.

So these tests bound the claim instead of restating it. They prove every divergence is a
published-text tie -- which is what shows the rule itself matches -- and they prove the tie is real.
They do **not** prove the thirteen instrument-level features reproduce the store, which needs the
original bars rather than the store, and they do not close the libm exposure across architectures.
"""

from __future__ import annotations

import csv
import gzip
import io
from collections import defaultdict
from pathlib import Path

import pytest

from quant_system.modeling.mizan_features import apply_cross_sectional_ranks

REPO_ROOT = Path(__file__).resolve().parent.parent
STORE = REPO_ROOT / "data/evidence/feature-store/mizan/mizan_feature_store.csv.gz"

#: Dates to check. The full sweep is 1,015,831 rows and about nine seconds; this samples enough to
#: catch a systematic regression while keeping the suite proportionate. Two of these are dates the
#: Red Team sweep reported as carrying mismatches under the old sort, so a revert fails here.
SAMPLED_DATES = frozenset(
    {
        "2016-11-07",
        "2019-05-10",  # 4 mismatching rows before the fix
        "2020-03-16",  # 4 mismatching rows before the fix
        "2020-03-23",  # HCC and IRB share the published text -0.2075471698
        "2023-05-16",  # 4 mismatching rows before the fix
        "2024-09-20",
        "2026-08-21",
    }
)

RANKED = (("return_5", "cs_rank_momentum_5"), ("volume_zscore", "cs_rank_volume_surprise"))


def _sampled_rows() -> dict[str, list[dict[str, str]]]:
    by_date: dict[str, list[dict[str, str]]] = defaultdict(list)
    with gzip.open(STORE, "rb") as raw:
        reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8"))
        for row in reader:
            day = row["date"]
            if day in SAMPLED_DATES:
                by_date[day].append(row)
    return dict(by_date)


@pytest.fixture(scope="module")
def sampled() -> dict[str, list[dict[str, str]]]:
    if not STORE.is_file():
        pytest.skip(f"the published feature store is not present at {STORE}")
    rows = _sampled_rows()
    if not rows:
        raise AssertionError(
            "none of the sampled dates are in the store. A skip here would be a false green, "
            "so this fails instead: either the store was rebuilt over a different period or "
            "its `date` column was renamed."
        )
    return rows


def test_the_store_is_present_and_readable(sampled) -> None:
    """A store that cannot be opened would make every test below skip into a false green."""
    assert sampled, "no rows read"
    assert sum(len(rows) for rows in sampled.values()) > 1000


def test_every_rank_the_kernel_cannot_reproduce_is_a_published_text_tie(sampled) -> None:
    """The strongest claim the published store can actually support.

    Re-deriving a date's ranks from its own published `return_5` and `volume_zscore` reproduces the
    published rank columns **except** where two names carry byte-identical published text. Those
    rows are not evidence of a different ranking rule -- they are the only rows where the store
    does not contain the information needed to order them, because the 10-decimal quantisation
    destroyed the difference the builder sorted on.

    So this asserts the divergence is *entirely* the tie class. A single mismatch between names
    whose published text differs would mean the rule itself had drifted, and that is what fails
    here.
    """
    unexplained: list[str] = []
    tied_divergences = 0
    for day, rows in sorted(sampled.items()):
        cross_section = {row["symbol"]: {name: row[name] for name, _ in RANKED} for row in rows}
        published = {row["symbol"]: {t: row[t] for _, t in RANKED} for row in rows}
        raw_values = {row["symbol"]: {name: float(row[name]) for name, _ in RANKED} for row in rows}

        apply_cross_sectional_ranks(cross_section, raw_values)

        for source, target in RANKED:
            texts = [row[source] for row in rows]
            tied_texts = {text for text in texts if texts.count(text) > 1}
            by_symbol = {row["symbol"]: row[source] for row in rows}
            for symbol, expected in published.items():
                if cross_section[symbol][target] == expected[target]:
                    continue
                if by_symbol[symbol] in tied_texts:
                    tied_divergences += 1
                else:
                    unexplained.append(
                        f"{day} {symbol} {target}: kernel={cross_section[symbol][target]} "
                        f"published={expected[target]} {source}={by_symbol[symbol]} (NOT a tie)"
                    )

    assert not unexplained, (
        f"{len(unexplained)} rank value(s) diverge on rows that are NOT tied in the published text. "
        f"The ranking rule has drifted from build_mizan_feature_store.py. First: {unexplained[:5]}"
    )
    assert tied_divergences > 0, (
        "no tied-text divergences were found at all, which means the sampled dates no longer "
        "contain the case this test exists to bound; re-sample rather than assume it is fixed"
    )


def test_the_published_store_cannot_break_its_own_ties(sampled) -> None:
    """Why the rows above are permanently unreproducible, stated as a test rather than a comment.

    This corrects an overreach in the repair that accompanied it. Ranking on raw floats makes the
    *execution* path follow the builder's procedure, which is a real improvement. It does not make
    the 244 published rows reproducible from the store: `float("-0.0365853659")` is the same number
    for both names, so no ranking rule can recover the order the builder produced from raw floats
    that were never published.
    """
    rows = sampled["2019-05-10"]
    by_symbol = {row["symbol"]: row["return_5"] for row in rows}
    assert by_symbol["BAJAJHIND"] == by_symbol["NIFTYBEES"]
    assert float(by_symbol["BAJAJHIND"]) == float(by_symbol["NIFTYBEES"])
