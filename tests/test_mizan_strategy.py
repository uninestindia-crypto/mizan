"""Tests for MizanStrategy, registry discovery, and server API endpoints."""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from quant_system.core.domain import PriceBar, Side
from quant_system.modeling.rows import FEATURE_NAMES_V3
from quant_system.server.app import app
from quant_system.strategies.base import MarketContext
from quant_system.strategies.mizan_strategy import MizanStrategy
from quant_system.strategies.registry import StrategyRegistry


def _mock_bars(symbol: str, count: int = 60, start_price: float = 100.0) -> list[PriceBar]:
    bars: list[PriceBar] = []
    base_time = datetime(2026, 1, 1, 9, 15, tzinfo=UTC)
    price = start_price
    for i in range(count):
        price += 0.5 * (1 if i % 2 == 0 else -0.3)
        bars.append(
            PriceBar(
                symbol=symbol,
                timestamp=base_time,
                open=Decimal(str(round(price - 0.2, 2))),
                high=Decimal(str(round(price + 0.8, 2))),
                low=Decimal(str(round(price - 0.5, 2))),
                close=Decimal(str(round(price, 2))),
                volume=1000 + i * 10,
            )
        )
    return bars


def test_mizan_strategy_in_registry() -> None:
    assert "MizanStrategy" in StrategyRegistry.list_strategies()
    assert "Mizan" in StrategyRegistry.list_strategies()

    strat = StrategyRegistry.create("MizanStrategy")
    assert isinstance(strat, MizanStrategy)
    assert strat.name == "MizanStrategy"

    strat2 = StrategyRegistry.create("Mizan")
    assert isinstance(strat2, MizanStrategy)


def test_mizan_strategy_signal_generation() -> None:
    strat = MizanStrategy(params={"top_n": 2, "confidence_threshold": -100.0})

    bars_infy = _mock_bars("INFY", count=60, start_price=1500.0)
    bars_tcs = _mock_bars("TCS", count=60, start_price=3500.0)
    bars_rel = _mock_bars("RELIANCE", count=60, start_price=2500.0)

    ctx = MarketContext(
        current_time=datetime(2026, 3, 1, 15, 30, tzinfo=UTC),
        current_bars={
            "INFY": bars_infy[-1],
            "TCS": bars_tcs[-1],
            "RELIANCE": bars_rel[-1],
        },
        historical_bars={
            "INFY": bars_infy,
            "TCS": bars_tcs,
            "RELIANCE": bars_rel,
        },
        current_positions={},
        available_cash=Decimal("1000000.00"),
        extra_data={},
    )

    signals = strat.generate_signals(ctx)
    assert len(signals) <= 2
    assert all(s.side == Side.BUY for s in signals)
    assert all(s.strategy_name == "MizanStrategy" for s in signals)


def test_mizan_server_endpoints() -> None:
    client = TestClient(app)

    # 1. CSRF Token
    csrf_res = client.get("/api/v1/csrf-token")
    assert csrf_res.status_code == 200
    token = csrf_res.json()["csrf_token"]
    headers = {"X-CSRF-Token": token}

    # 2. Info endpoint
    resp_info = client.get("/api/v1/models/mizan/info")
    assert resp_info.status_code == 200
    info_data = resp_info.json()
    assert info_data["model_id"] == "mizan-v1"
    assert info_data["candidate_id"] == "cand_mizan_v1"
    assert len(info_data["feature_names"]) == 15

    # 3. Predict endpoint (single vector)
    single_feats = dict.fromkeys(FEATURE_NAMES_V3, 0.05)
    resp_pred = client.post(
        "/api/v1/models/mizan/predict",
        json={"features": single_feats},
        headers=headers,
    )
    assert resp_pred.status_code == 200
    pred_data = resp_pred.json()
    assert "score" in pred_data
    assert isinstance(pred_data["score"], float)

    # 4. Predict endpoint (universe)
    univ_feats = {
        "INFY": dict.fromkeys(FEATURE_NAMES_V3, 0.1),
        "TCS": dict.fromkeys(FEATURE_NAMES_V3, -0.1),
    }
    resp_univ = client.post(
        "/api/v1/models/mizan/predict",
        json={"features": univ_feats},
        headers=headers,
    )
    assert resp_univ.status_code == 200
    univ_data = resp_univ.json()
    assert "scores" in univ_data
    assert len(univ_data["scores"]) == 2
    assert "ranked" in univ_data
    assert len(univ_data["ranked"]) == 2

    # 5. Download endpoint
    resp_dl = client.get("/api/v1/models/mizan/download")
    assert resp_dl.status_code == 200
    assert resp_dl.headers["content-type"] == "application/zip"
    zip_bytes = resp_dl.content
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        namelist = zf.namelist()
        assert "config.json" in namelist
        assert "weights.json" in namelist
        assert "model_card.json" in namelist
        assert "checksums.json" in namelist
