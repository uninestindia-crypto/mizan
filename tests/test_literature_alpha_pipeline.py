"""Test the literature-grounded alpha training pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

# Add scripts directory
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from train_literature_alpha_model import run_pipeline  # noqa: E402


def test_literature_alpha_pipeline_runs_end_to_end() -> None:
    results = run_pipeline(
        universe=["TCS", "INFY"],
        query="cross-sectional momentum volatility",
        max_papers=2,
        offline=True,
    )

    assert "report" in results
    rep = results["report"]
    assert rep["sample_size"] > 0
    assert "ic_mean" in rep
    assert "rank_ic_mean" in rep
    assert results["papers_indexed"] == 2
    assert len(results["citations"]) == 2
    assert results["total_time"] < 10.0
