"""A 200 with no candles must not destroy a good macro cache. (R6-16)

`macro_covers` goes permanently false when it does, and the scheduled session then refuses at
exit 5 until someone re-ingests by hand. A 401 was always safe here because it raised; a 200 was
not, because it did not.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ingest_macro_regimes import existing_bar_count, may_overwrite_macro_cache


def _cache(path: Path, bars: int) -> Path:
    path.write_text(
        json.dumps({"symbol": "INDIAVIX", "candles": [["d", 1, 2, 3, 4]] * bars}),
        encoding="utf-8",
    )
    return path


def test_an_empty_response_may_not_replace_a_populated_cache() -> None:
    assert may_overwrite_macro_cache(new_bar_count=0, cached_bar_count=743) is False


def test_a_populated_response_may_replace_a_populated_cache() -> None:
    assert may_overwrite_macro_cache(new_bar_count=744, cached_bar_count=743) is True


def test_a_shorter_but_non_empty_response_is_still_allowed() -> None:
    """A shortened window is a legitimate request, not a provider failure."""
    assert may_overwrite_macro_cache(new_bar_count=30, cached_bar_count=743) is True


def test_a_first_ingest_with_nothing_cached_may_write_an_empty_result() -> None:
    """Otherwise an empty first run looks like a run that never happened."""
    assert may_overwrite_macro_cache(new_bar_count=0, cached_bar_count=0) is True


def test_the_cached_count_is_read_from_the_file(tmp_path) -> None:
    assert existing_bar_count(_cache(tmp_path / "macro_INDIAVIX.json", 743)) == 743


def test_a_missing_cache_counts_as_zero(tmp_path) -> None:
    assert existing_bar_count(tmp_path / "absent.json") == 0


@pytest.mark.parametrize(
    "content", ['{"candles": "not-a-list"}', "{}", "not json at all", ""], ids=range(4)
)
def test_an_unreadable_cache_counts_as_zero_so_a_fetch_can_repair_it(tmp_path, content) -> None:
    """A corrupt cache is worth less than an empty fetch result; it must not be protected."""
    path = tmp_path / "macro_X.json"
    path.write_text(content, encoding="utf-8")

    assert existing_bar_count(path) == 0
    assert may_overwrite_macro_cache(new_bar_count=0, cached_bar_count=existing_bar_count(path))


def test_the_real_cached_indices_would_be_protected_today() -> None:
    """Against the files actually on disk, not a fixture."""
    cache_dir = (
        Path(__file__).resolve().parent.parent
        / "data/evidence/market-cache/macro-refresh-20230828-20260827"
    )
    if not cache_dir.is_dir():  # pragma: no cover - the cache is not committed everywhere
        pytest.skip("macro cache not present in this checkout")

    for name in ("macro_INDIAVIX", "macro_NIFTY50", "macro_NIFTYBANK", "macro_NIFTYIT"):
        cached = existing_bar_count(cache_dir / f"{name}.json")
        assert cached > 0, f"{name} has no cached bars"
        assert may_overwrite_macro_cache(0, cached) is False, f"{name} is not protected"
