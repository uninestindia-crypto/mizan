"""Tests for Qlib research bridge and upstream release watcher in Mizan."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from quant_system.data.market_data import PointInTimeBar
from quant_system.research.qlib import (
    QLIB_ALPHA158_MINIMUM_BARS,
    QlibAlpha158Extractor,
    QlibModelAdapter,
    QlibRankDataset,
    QlibUpstreamWatcher,
    compute_qlib_alpha_features,
)


def _make_sample_bar(idx: int, price: float, vol: int = 1000) -> PointInTimeBar:
    dt = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    return PointInTimeBar(
        provider_instrument_id="TEST_001",
        symbol="TEST",
        exchange_date=date(2026, 1, 1),
        event_at=dt,
        provider_at=dt,
        ingested_at=dt,
        available_at=dt,
        open=Decimal(str(round(price, 2))),
        high=Decimal(str(round(price * 1.02, 2))),
        low=Decimal(str(round(price * 0.98, 2))),
        close=Decimal(str(round(price * 1.01, 2))),
        volume=vol,
        open_interest=0,
        source_row_index=idx,
    )


# ---------------------------------------------------------------------------
# Alpha158 Feature Extractor Tests
# ---------------------------------------------------------------------------


def test_qlib_alpha158_insufficient_bars_raises() -> None:
    extractor = QlibAlpha158Extractor()
    bars = [_make_sample_bar(i, 100.0) for i in range(QLIB_ALPHA158_MINIMUM_BARS - 1)]
    with pytest.raises(ValueError, match="Insufficient bars for Qlib Alpha158"):
        extractor.extract_features(bars)


def test_qlib_alpha158_factor_calculation() -> None:
    extractor = QlibAlpha158Extractor()
    bars = [_make_sample_bar(i, 100.0 + (i * 0.5), vol=1000 + i * 10) for i in range(70)]

    features = extractor.extract_features(bars)
    assert len(features) == len(extractor.feature_names)

    # Validate essential factor keys exist
    for key in ("kmid", "klen", "ma_5", "std_5", "roc_10", "max_20", "corr_5"):
        assert key in features, f"Expected key {key} in feature set"

    # All values must be valid finite floats
    for k, v in features.items():
        assert isinstance(v, float)
        assert not np.isnan(v), f"Feature {k} returned NaN"
        assert not np.isinf(v), f"Feature {k} returned Inf"

    # Test convenience function
    fn_features = compute_qlib_alpha_features(bars)
    assert fn_features == features


def test_qlib_alpha158_zero_division_safety() -> None:
    # Completely flat price and zero volume bars
    dt = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    flat_bars = [
        PointInTimeBar(
            provider_instrument_id="FLAT",
            symbol="FLAT",
            exchange_date=date(2026, 1, 1),
            event_at=dt,
            provider_at=dt,
            ingested_at=dt,
            available_at=dt,
            open=Decimal("100.0"),
            high=Decimal("100.0"),
            low=Decimal("100.0"),
            close=Decimal("100.0"),
            volume=0,
            open_interest=0,
            source_row_index=i,
        )
        for i in range(70)
    ]

    extractor = QlibAlpha158Extractor()
    features = extractor.extract_features(flat_bars)
    assert features["klen"] == 0.0
    assert features["corr_5"] == 0.0
    assert not any(np.isnan(v) or np.isinf(v) for v in features.values())


# ---------------------------------------------------------------------------
# Qlib Model Adapter Tests
# ---------------------------------------------------------------------------


def test_qlib_model_adapter_fit_predict_evaluate() -> None:
    np.random.seed(42)
    n_samples, n_features = 100, 10
    X = np.random.randn(n_samples, n_features)
    # Target return with strong linear component + noise
    y = X[:, 0] * 0.05 + np.random.randn(n_samples) * 0.01

    dataset = QlibRankDataset(
        symbols=[f"SYM_{i}" for i in range(n_samples)],
        dates=["2026-01-01"] * n_samples,
        feature_names=[f"feat_{i}" for i in range(n_features)],
        X=X,
        y=y,
    )

    adapter = QlibModelAdapter(ridge_alpha=1.0)
    adapter.fit(dataset)

    preds = adapter.predict(X)
    assert len(preds) == n_samples

    report = adapter.evaluate(dataset)
    assert report.sample_size == n_samples
    assert report.ic_mean > 0.5  # Strong correlation expected
    assert report.rank_ic_mean > 0.5
    assert report.top_decile_excess > 0.0

    rep_dict = report.to_dict()
    assert "ic_mean" in rep_dict
    assert "rank_ic_mean" in rep_dict


# ---------------------------------------------------------------------------
# Upstream Watcher Tests
# ---------------------------------------------------------------------------


def test_upstream_watcher_detects_update_and_generates_ticket(tmp_path: Path) -> None:
    mock_payload = {
        "tag_name": "v0.9.3",
        "published_at": "2026-10-08T00:00:00Z",
        "html_url": "https://github.com/microsoft/qlib/releases/tag/v0.9.3",
        "body": "## What's New in Qlib 0.9.3\n- Added Transformer variant\n- Fast factor cache",
        "name": "Qlib v0.9.3 Release",
    }

    state_file = tmp_path / "upstream_state.json"
    inbox_dir = tmp_path / "inbox"
    notifications_file = tmp_path / "notifications.jsonl"

    watcher = QlibUpstreamWatcher(
        state_file=state_file,
        inbox_dir=inbox_dir,
        notifications_file=notifications_file,
        fetcher=lambda _repo: mock_payload,
    )

    # 1. First run: should detect new update
    res1 = watcher.check()
    assert res1["checked"] is True
    assert res1["update_available"] is True
    assert res1["tag"] == "v0.9.3"
    assert res1["ticket_file"] is not None
    assert Path(res1["ticket_file"]).exists()

    # Verify content of generated ticket
    ticket_content = Path(res1["ticket_file"]).read_text(encoding="utf-8")
    assert "v0.9.3" in ticket_content
    assert "Antigravity / Claude / Codex" in ticket_content
    assert "Transformer variant" in ticket_content

    # Verify state was saved
    assert state_file.exists()
    state_data = json.loads(state_file.read_text(encoding="utf-8"))
    assert state_data["last_seen_tag"] == "v0.9.3"

    # Verify notifications file logged event
    assert notifications_file.exists()
    assert "v0.9.3" in notifications_file.read_text(encoding="utf-8")

    # 2. Second run: tag is already seen, so update_available should be False
    res2 = watcher.check()
    assert res2["update_available"] is False
    assert res2["ticket_file"] is None

    # 3. Third run with force_notify: should regenerate ticket
    res3 = watcher.check(force_notify=True)
    assert res3["update_available"] is True
    assert res3["ticket_file"] is not None
