"""Tests for the QuantOS Automated Daily Pipeline."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from quant_system.data.provenance import RuntimeDataSource, describe
from scripts.daily_pipeline import DailyPipelineSummary, main, run_daily_pipeline


def test_daily_pipeline_executes_end_to_end_and_persists_evidence(tmp_path: Path) -> None:
    """Verify that run_daily_pipeline runs both strategies and creates reports."""
    summary = run_daily_pipeline(
        target_date=date(2026, 8, 20),
        universe=["INFY", "TCS"],
        history_days=100,
        output_dir=tmp_path,
    )

    assert isinstance(summary, DailyPipelineSummary)
    assert summary.execution_date == "2026-08-20"
    assert summary.status == "SUCCESS"
    assert summary.universe == ["INFY", "TCS"]
    assert len(summary.strategies_run) == 2

    # Check generated files
    report_file = tmp_path / "daily_report_2026-08-20.md"
    summary_file = tmp_path / "daily_summary_2026-08-20.json"

    assert report_file.exists()
    assert summary_file.exists()

    report_content = report_file.read_text(encoding="utf-8")
    assert "# QuantOS Daily Automated Report — 2026-08-20" in report_content
    assert "MLEquity_RollingRidge_Daily" in report_content
    assert "EquityDualMomentum_Daily" in report_content

    with open(summary_file, encoding="utf-8") as f:
        data = json.load(f)
    assert data["status"] == "SUCCESS"
    assert "ml_cagr_pct" in data
    assert "momentum_cagr_pct" in data


def test_daily_pipeline_cli_success(tmp_path: Path) -> None:
    """Verify CLI main entrypoint with custom arguments."""
    test_args = [
        "daily_pipeline.py",
        "--date",
        "2026-08-20",
        "--days",
        "80",
        "--universe",
        "INFY",
        "TCS",
        "--output-dir",
        str(tmp_path),
    ]
    with patch("sys.argv", test_args):
        exit_code = main()
        assert exit_code == 0

    assert (tmp_path / "daily_report_2026-08-20.md").exists()
    assert (tmp_path / "daily_summary_2026-08-20.json").exists()


def test_daily_pipeline_cli_invalid_date() -> None:
    """Verify CLI handles invalid date gracefully."""
    test_args = ["daily_pipeline.py", "--date", "invalid-date-format"]
    with patch("sys.argv", test_args):
        exit_code = main()
        assert exit_code == 1


def test_daily_pipeline_declares_synthetic_source_in_every_artifact(tmp_path: Path) -> None:
    """The pipeline runs on generated bars; each artifact it leaves behind must admit that.

    The markdown report is the artifact most likely to be read out of context, so the disclosure
    is asserted above the first performance figure rather than merely present somewhere.
    """
    summary = run_daily_pipeline(
        target_date=date(2026, 8, 20),
        universe=["INFY", "TCS"],
        history_days=100,
        output_dir=tmp_path,
    )

    assert summary.data_source == str(RuntimeDataSource.SYNTHETIC)
    assert summary.data_source_disclosure == describe(RuntimeDataSource.SYNTHETIC)

    report_content = (tmp_path / "daily_report_2026-08-20.md").read_text(encoding="utf-8")
    assert f"**DATA SOURCE: {RuntimeDataSource.SYNTHETIC}.**" in report_content
    assert describe(RuntimeDataSource.SYNTHETIC) in report_content
    assert report_content.index("DATA SOURCE") < report_content.index("Tearsheet")

    with open(tmp_path / "daily_summary_2026-08-20.json", encoding="utf-8") as f:
        data = json.load(f)
    assert data["data_source"] == str(RuntimeDataSource.SYNTHETIC)
    assert data["data_source_disclosure"] == describe(RuntimeDataSource.SYNTHETIC)


# test-allow: no-assertion - check-tests.mjs caseBody() truncates every multi-line Python signature, so the assertions below are invisible to it
def test_daily_pipeline_does_not_claim_to_ingest_market_data(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No log line may describe generated bars as ingested market data."""
    with caplog.at_level(logging.INFO, logger="quant_system.daily_pipeline"):
        run_daily_pipeline(
            target_date=date(2026, 8, 20),
            universe=["INFY"],
            history_days=60,
            output_dir=tmp_path,
        )

    log_text = caplog.text
    assert "Ingesting and validating point-in-time market data" not in log_text
    assert str(RuntimeDataSource.SYNTHETIC) in log_text
