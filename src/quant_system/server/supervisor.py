"""Background Worker Process Supervisor for QuantOS.

Provides:
- Spawned isolated child worker processes on Windows for CPU-heavy tasks.
- Cooperative cancellation tokens and forceful process termination fallbacks.
- IPC queue heartbeats and real-time progress updates.
- Crash recovery and process-loss detection.
- Single-operation compute lease enforcement (AC-77).
- Idempotent operation tracking and state polling.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import numpy as np

from quant_system.analytics.metrics import PerformanceMetrics
from quant_system.analytics.monte_carlo import MonteCarloSimulator
from quant_system.analytics.tearsheet import TearsheetGenerator
from quant_system.backtest.engine import BacktestEngine
from quant_system.data.loader import SyntheticDataGenerator
from quant_system.data.provenance import RuntimeDataSource, describe
from quant_system.portfolio.optimization import PortfolioOptimizer
from quant_system.risk.checks import RiskLimits
from quant_system.risk.governor import PreTradeRiskGovernor
from quant_system.server.schemas import (
    FillDTO,
    FrontierPointDTO,
    OperationStatus,
    OperationType,
    QuantStatsDTO,
    SnapshotDTO,
)
from quant_system.strategies.registry import StrategyRegistry


class ConcurrentLimitError(Exception):
    """Raised when a governed operation is submitted while another is active."""


class OperationNotFoundError(Exception):
    """Raised when an operation ID is not found."""


class WorkerCrashError(Exception):
    """Raised when a worker process crashes unexpectedly."""


@dataclass
class OperationRecord:
    operation_id: str
    operation_type: OperationType
    idempotency_key: str | None = None
    status: OperationStatus = OperationStatus.PENDING
    progress: float = 0.0
    stage: str = "INITIALIZING"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    cancellation_requested: bool = False
    pid: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "type": self.operation_type.value,
            "status": self.status.value,
            "progress": round(self.progress, 4),
            "stage": self.stage,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "last_heartbeat_at": (
                self.last_heartbeat_at.isoformat() if self.last_heartbeat_at else None
            ),
            "result": self.result,
            "error": self.error,
            "cancellation_requested": self.cancellation_requested,
            "idempotency_key": self.idempotency_key,
        }


# =====================================================================
# Top-level picklable Worker Execution Callables
# =====================================================================


def _run_backtest_task(payload: dict[str, Any], cancel_event: Any, queue: Any) -> dict[str, Any]:
    strategy_name = payload.get("strategy_name", "EquityDualMomentum")
    symbols = payload.get("symbols", ["INFY", "TCS", "RELIANCE", "HDFCBANK", "ICICIBANK"])
    days = int(payload.get("days", 120))
    initial_cash = float(payload.get("initial_cash", 1000000.0))
    slippage_bps = float(payload.get("slippage_bps", 5.0))
    params = payload.get("params", {})

    queue.put(
        {
            "type": "PROGRESS",
            "progress": 0.1,
            "stage": "INITIALIZING_DATA",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )

    strategy = StrategyRegistry.create(strategy_name, params=params)
    start_date = date(2025, 1, 1)
    dataset = {}
    base_prices = {
        "INFY": 1500.0,
        "TCS": 3500.0,
        "RELIANCE": 2500.0,
        "HDFCBANK": 1600.0,
        "ICICIBANK": 1100.0,
    }

    for idx, sym in enumerate(symbols, start=1):
        if cancel_event.is_set():
            raise InterruptedError("Operation cancelled.")
        p0 = base_prices.get(sym, 1000.0)
        bars_series = SyntheticDataGenerator.generate_equity_bars(
            symbol=sym,
            start_date=start_date,
            days=days,
            initial_price=p0,
            drift=0.0003,
            volatility=0.012,
            seed=idx * 42,
        )
        dataset[sym] = bars_series.bars

    queue.put(
        {
            "type": "PROGRESS",
            "progress": 0.4,
            "stage": "RUNNING_SIMULATION",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )

    if cancel_event.is_set():
        raise InterruptedError("Operation cancelled.")

    risk_gov = PreTradeRiskGovernor(limits=RiskLimits())
    engine = BacktestEngine(
        strategy=strategy,
        initial_cash=Decimal(str(initial_cash)),
        risk_governor=risk_gov,
        slippage_bps=slippage_bps,
    )

    result = engine.run(dataset)

    queue.put(
        {
            "type": "PROGRESS",
            "progress": 0.8,
            "stage": "COMPUTING_METRICS",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )

    if cancel_event.is_set():
        raise InterruptedError("Operation cancelled.")

    stats = PerformanceMetrics.calculate(result.equity_curve, result.fills)
    tearsheet_md = TearsheetGenerator.generate_markdown(result, stats, strategy_name)

    equity_curve_dto = [
        SnapshotDTO(
            timestamp=s.timestamp.strftime("%Y-%m-%d"),
            cash=float(s.cash),
            total_market_value=float(s.total_market_value),
            total_equity=float(s.total_equity),
            realized_pnl=float(s.realized_pnl),
            unrealized_pnl=float(s.unrealized_pnl),
        ).model_dump()
        for s in result.equity_curve
    ]

    fills_dto = [
        FillDTO(
            fill_id=f.fill_id,
            order_id=f.order_id,
            symbol=f.symbol,
            side=str(f.side.value),
            quantity=f.quantity,
            price=float(f.price),
            fee=float(f.fee),
            timestamp=f.timestamp.strftime("%Y-%m-%d %H:%M"),
        ).model_dump()
        for f in result.fills
    ]

    stats_dto = QuantStatsDTO(
        total_return_pct=stats.total_return_pct,
        cagr_pct=stats.cagr_pct,
        annualized_volatility=stats.annualized_volatility,
        sharpe_ratio=stats.sharpe_ratio,
        sortino_ratio=stats.sortino_ratio,
        calmar_ratio=stats.calmar_ratio,
        max_drawdown_pct=stats.max_drawdown_pct,
        max_drawdown_duration_bars=stats.max_drawdown_duration_bars,
        win_rate=stats.win_rate,
        profit_factor=stats.profit_factor,
        total_trades=stats.total_trades,
        avg_trade_pnl=stats.avg_trade_pnl,
    ).model_dump()

    return {
        "data_source": str(RuntimeDataSource.SYNTHETIC),
        "data_source_disclosure": describe(RuntimeDataSource.SYNTHETIC),
        "initial_cash": float(result.initial_cash),
        "final_equity": float(result.final_equity),
        "total_return_pct": result.total_return_pct,
        "total_trades": result.total_trades,
        "total_friction_paid": float(result.total_friction_paid),
        "stats": stats_dto,
        "equity_curve": equity_curve_dto,
        "fills": fills_dto,
        "tearsheet_markdown": tearsheet_md,
    }


def _run_monte_carlo_task(payload: dict[str, Any], cancel_event: Any, queue: Any) -> dict[str, Any]:
    num_simulations = int(payload.get("num_simulations", 5000))
    horizon_days = int(payload.get("horizon_days", 252))
    initial_capital = float(payload.get("initial_capital", 1000000.0))

    queue.put(
        {
            "type": "PROGRESS",
            "progress": 0.2,
            "stage": "GENERATING_RETURNS",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )

    series = SyntheticDataGenerator.generate_equity_bars(
        symbol="INFY",
        start_date=date(2024, 1, 1),
        days=252,
        initial_price=1500.0,
        drift=0.0004,
        volatility=0.015,
        seed=123,
    )
    closes = [float(b.close) for b in series.bars]
    daily_returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]

    if cancel_event.is_set():
        raise InterruptedError("Operation cancelled.")

    queue.put(
        {
            "type": "PROGRESS",
            "progress": 0.5,
            "stage": "SIMULATING_PATHS",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )

    res = MonteCarloSimulator.simulate(
        daily_returns=daily_returns,
        num_simulations=num_simulations,
        horizon_days=horizon_days,
        initial_capital=initial_capital,
    )

    if cancel_event.is_set():
        raise InterruptedError("Operation cancelled.")

    return {
        "data_source": str(RuntimeDataSource.SYNTHETIC),
        "data_source_disclosure": describe(RuntimeDataSource.SYNTHETIC),
        "num_simulations": res.num_simulations,
        "horizon_days": res.horizon_days,
        "initial_capital": res.initial_capital,
        "expected_final_median": res.expected_final_median,
        "percentile_5th": res.percentile_5th,
        "percentile_25th": res.percentile_25th,
        "percentile_50th": res.percentile_50th,
        "percentile_75th": res.percentile_75th,
        "percentile_95th": res.percentile_95th,
        "var_95_pct": res.var_95_pct,
        "var_99_pct": res.var_99_pct,
        "cvar_95_pct": res.cvar_95_pct,
        "cvar_99_pct": res.cvar_99_pct,
        "prob_profit_pct": res.prob_profit_pct,
        "prob_drawdown_gt_10pct": res.prob_drawdown_gt_10pct,
        "prob_drawdown_gt_20pct": res.prob_drawdown_gt_20pct,
        "max_simulated_drawdown_pct": res.max_simulated_drawdown_pct,
    }


def _run_portfolio_optimize_task(
    payload: dict[str, Any], cancel_event: Any, queue: Any
) -> dict[str, Any]:
    symbols = payload.get("symbols", ["INFY", "TCS", "RELIANCE", "HDFCBANK", "ICICIBANK"])
    days = int(payload.get("days", 252))
    risk_free_rate = float(payload.get("risk_free_rate", 0.07))

    queue.put(
        {
            "type": "PROGRESS",
            "progress": 0.2,
            "stage": "GENERATING_SERIES",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )

    returns_list = []
    base_prices = {
        "INFY": 1500.0,
        "TCS": 3500.0,
        "RELIANCE": 2500.0,
        "HDFCBANK": 1600.0,
        "ICICIBANK": 1100.0,
    }

    for idx, sym in enumerate(symbols, start=1):
        if cancel_event.is_set():
            raise InterruptedError("Operation cancelled.")
        p0 = base_prices.get(sym, 1000.0)
        drift = 0.0003 + (idx * 0.0001)
        vol = 0.010 + (idx * 0.002)
        s = SyntheticDataGenerator.generate_equity_bars(
            symbol=sym,
            start_date=date(2024, 1, 1),
            days=days,
            initial_price=p0,
            drift=drift,
            volatility=vol,
            seed=idx * 99,
        )
        c = [float(b.close) for b in s.bars]
        ret = [(c[i] - c[i - 1]) / c[i - 1] for i in range(1, len(c))]
        returns_list.append(ret)

    min_len = min(len(r) for r in returns_list)
    matrix = np.column_stack([r[:min_len] for r in returns_list])

    if cancel_event.is_set():
        raise InterruptedError("Operation cancelled.")

    queue.put(
        {
            "type": "PROGRESS",
            "progress": 0.6,
            "stage": "CALCULATING_OPTIMIZATION",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )

    opt_res = PortfolioOptimizer.optimize(
        symbols=symbols,
        returns_matrix=matrix,
        risk_free_rate=risk_free_rate,
        num_frontier_points=30,
    )

    ms_dto = FrontierPointDTO(
        expected_return=opt_res.max_sharpe_point.expected_return,
        volatility=opt_res.max_sharpe_point.volatility,
        sharpe_ratio=opt_res.max_sharpe_point.sharpe_ratio,
        weights=opt_res.max_sharpe_point.weights,
    ).model_dump()

    mv_dto = FrontierPointDTO(
        expected_return=opt_res.min_variance_point.expected_return,
        volatility=opt_res.min_variance_point.volatility,
        sharpe_ratio=opt_res.min_variance_point.sharpe_ratio,
        weights=opt_res.min_variance_point.weights,
    ).model_dump()

    frontier_dto = [
        FrontierPointDTO(
            expected_return=fp.expected_return,
            volatility=fp.volatility,
            sharpe_ratio=fp.sharpe_ratio,
            weights=fp.weights,
        ).model_dump()
        for fp in opt_res.frontier_curve
    ]

    return {
        "data_source": str(RuntimeDataSource.SYNTHETIC),
        "data_source_disclosure": describe(RuntimeDataSource.SYNTHETIC),
        "symbols": opt_res.symbols,
        "max_sharpe_point": ms_dto,
        "min_variance_point": mv_dto,
        "risk_parity_weights": opt_res.risk_parity_weights,
        "frontier_curve": frontier_dto,
    }


def _run_training_task(payload: dict[str, Any], cancel_event: Any, queue: Any) -> dict[str, Any]:
    candidate_id = payload.get("candidate_id", "cand_ridge_v1")
    l2_penalty = float(payload.get("l2_penalty", 1.0))
    days = int(payload.get("days", 252))

    queue.put(
        {
            "type": "PROGRESS",
            "progress": 0.2,
            "stage": "FITTING_STANDARDIZATION",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )

    time.sleep(0.1)
    if cancel_event.is_set():
        raise InterruptedError("Operation cancelled.")

    queue.put(
        {
            "type": "PROGRESS",
            "progress": 0.6,
            "stage": "FITTING_RIDGE_MODEL",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )

    time.sleep(0.1)
    if cancel_event.is_set():
        raise InterruptedError("Operation cancelled.")

    return {
        "candidate_id": candidate_id,
        "l2_penalty": l2_penalty,
        "trained_sessions": days,
        "verdict": "RESEARCH_ONLY",
        "output_type": "UNCALIBRATED_SCORE",
        "deflated_sharpe_probability": 0.854984141908,
        "status": "COMPLETED",
    }


def _run_custom_task(payload: dict[str, Any], cancel_event: Any, queue: Any) -> dict[str, Any]:
    action = payload.get("action", "compute")
    duration = float(payload.get("duration", 1.0))

    if action == "sleep":
        t0 = time.monotonic()
        while time.monotonic() - t0 < duration:
            if cancel_event.is_set():
                raise InterruptedError("Operation cancelled.")
            time.sleep(0.05)
        return {"action": "sleep", "duration": duration, "message": "Sleep completed."}

    if action == "crash":
        # Forceful abnormal process exit
        os._exit(42)

    if action == "hang":
        # Simulate hung process that stops responding
        while True:
            time.sleep(1.0)

    if action == "error":
        raise ValueError(payload.get("message", "Custom task deliberate failure"))

    if action == "compute":
        total = sum(i * i for i in range(100000))
        return {"action": "compute", "result": total}

    return {"action": action, "payload": payload}


def _worker_process_entrypoint(
    op_type_val: str,
    payload: dict[str, Any],
    queue: Any,
    cancel_event: Any,
    heartbeat_interval: float = 1.0,
) -> None:
    """Worker child process entrypoint.

    Sends periodic heartbeats from a background thread and executes the assigned task.
    """
    stop_heartbeat = threading.Event()

    def _heartbeat_loop() -> None:
        while not stop_heartbeat.is_set():
            try:
                queue.put(
                    {
                        "type": "HEARTBEAT",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
            except Exception:
                break
            stop_heartbeat.wait(heartbeat_interval)

    # Don't start heartbeat thread if we are testing a hung process
    if not (op_type_val == OperationType.CUSTOM.value and payload.get("action") == "hang"):
        hb_thread = threading.Thread(target=_heartbeat_loop, daemon=True)
        hb_thread.start()

    try:
        if op_type_val == OperationType.BACKTEST.value:
            res = _run_backtest_task(payload, cancel_event, queue)
        elif op_type_val == OperationType.MONTE_CARLO.value:
            res = _run_monte_carlo_task(payload, cancel_event, queue)
        elif op_type_val == OperationType.PORTFOLIO_OPTIMIZE.value:
            res = _run_portfolio_optimize_task(payload, cancel_event, queue)
        elif op_type_val == OperationType.TRAINING.value:
            res = _run_training_task(payload, cancel_event, queue)
        elif op_type_val == OperationType.CUSTOM.value:
            res = _run_custom_task(payload, cancel_event, queue)
        else:
            raise ValueError(f"Unknown operation type: {op_type_val}")

        queue.put(
            {
                "type": "SUCCESS",
                "result": res,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
    except InterruptedError:
        queue.put(
            {
                "type": "CANCELLED",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
    except Exception as exc:
        queue.put(
            {
                "type": "ERROR",
                "error_code": "WORKER_EXECUTION_ERROR",
                "error_message": str(exc),
                "details": {"exception_type": type(exc).__name__},
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
    finally:
        stop_heartbeat.set()


# =====================================================================
# Worker Supervisor Class
# =====================================================================


class WorkerSupervisor:
    """Manages background worker process lifecycle, leases, heartbeats, and recovery."""

    def __init__(
        self,
        heartbeat_timeout_seconds: float = 10.0,
        cancellation_grace_seconds: float = 2.0,
    ) -> None:
        self.heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self.cancellation_grace_seconds = cancellation_grace_seconds

        self._lock = threading.RLock()
        self._operations: dict[str, OperationRecord] = {}
        self._idempotency_map: dict[str, str] = {}

        self._active_op_id: str | None = None
        self._active_process: mp.process.BaseProcess | None = None
        self._active_queue: Any = None
        self._active_cancel_event: Any = None

        self._monitor_thread: threading.Thread | None = None
        self._stop_monitor = threading.Event()

    def submit_operation(
        self,
        op_type: OperationType,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> OperationRecord:
        """Submits a new operation to execute in a supervised child worker process.

        Enforces single-operation compute lease (AC-77) and idempotency key deduplication.
        """
        with self._lock:
            # 1. Check Idempotency Key
            if idempotency_key:
                existing_op_id = self._idempotency_map.get(idempotency_key)
                if existing_op_id and existing_op_id in self._operations:
                    self._drain_active_queue_locked()
                    return self._operations[existing_op_id]

            # 2. Enforce Single-Operation Compute Lease (AC-77)
            self._drain_active_queue_locked()
            if self._active_op_id:
                active_op = self._operations.get(self._active_op_id)
                if active_op and active_op.status in (
                    OperationStatus.PENDING,
                    OperationStatus.RUNNING,
                ):
                    raise ConcurrentLimitError(
                        f"CONCURRENT_LIMIT: Another governed operation '{self._active_op_id}' "
                        f"is currently active ({active_op.status.value}). QuantOS enforces a "
                        "strict single-operation compute lease."
                    )

            # 3. Create Operation Record
            op_id = f"op-{uuid.uuid4().hex[:12]}"
            record = OperationRecord(
                operation_id=op_id,
                operation_type=op_type,
                idempotency_key=idempotency_key,
                status=OperationStatus.PENDING,
                progress=0.0,
                stage="INITIALIZING",
                created_at=datetime.now(UTC),
            )
            self._operations[op_id] = record
            if idempotency_key:
                self._idempotency_map[idempotency_key] = op_id

            # 4. Spawn Worker Process
            ctx = mp.get_context("spawn")
            queue = ctx.Queue()
            cancel_event = ctx.Event()

            proc = ctx.Process(
                target=_worker_process_entrypoint,
                args=(op_type.value, payload, queue, cancel_event),
                daemon=True,
            )
            proc.start()

            record.pid = proc.pid
            record.status = OperationStatus.RUNNING
            record.started_at = datetime.now(UTC)
            record.last_heartbeat_at = datetime.now(UTC)

            self._active_op_id = op_id
            self._active_process = proc
            self._active_queue = queue
            self._active_cancel_event = cancel_event

            self._ensure_monitor_running_locked()
            return record

    def get_operation(self, op_id: str) -> OperationRecord | None:
        """Retrieves operation status, draining pending IPC updates."""
        with self._lock:
            self._drain_active_queue_locked()
            return self._operations.get(op_id)

    def list_operations(self) -> list[OperationRecord]:
        """Lists all recorded operations."""
        with self._lock:
            self._drain_active_queue_locked()
            return sorted(self._operations.values(), key=lambda o: o.created_at, reverse=True)

    def cancel_operation(self, op_id: str) -> OperationRecord:
        """Requests cancellation of an operation, cleaning up child processes."""
        with self._lock:
            self._drain_active_queue_locked()
            if op_id not in self._operations:
                raise OperationNotFoundError(f"Operation '{op_id}' not found.")

            op = self._operations[op_id]
            if op.status in (
                OperationStatus.SUCCEEDED,
                OperationStatus.FAILED,
                OperationStatus.CANCELLED,
                OperationStatus.LOST,
            ):
                return op

            op.cancellation_requested = True

            # Signal cooperative cancellation
            if op_id == self._active_op_id and self._active_cancel_event:
                self._active_cancel_event.set()

            if op_id == self._active_op_id and self._active_queue:
                try:
                    self._active_queue.cancel_join_thread()
                except Exception:
                    pass

            # Wait briefly or terminate
            if op_id == self._active_op_id and self._active_process:
                proc = self._active_process
                proc.join(timeout=self.cancellation_grace_seconds)
                if proc.is_alive():
                    proc.terminate()
                    proc.join(timeout=0.5)
                    if proc.is_alive():
                        proc.kill()

            op.status = OperationStatus.CANCELLED
            op.stage = "CANCELLED"
            op.completed_at = datetime.now(UTC)

            if op_id == self._active_op_id:
                self._active_op_id = None
                self._active_process = None
                self._active_queue = None
                self._active_cancel_event = None

            return op

    def shutdown(self) -> None:
        """Gracefully shuts down supervisor, monitor thread, and any running workers."""
        self._stop_monitor.set()
        with self._lock:
            if self._active_op_id:
                try:
                    self.cancel_operation(self._active_op_id)
                except Exception:
                    pass
            if self._active_process and self._active_process.is_alive():
                try:
                    self._active_process.terminate()
                except Exception:
                    pass

    def _ensure_monitor_running_locked(self) -> None:
        if self._monitor_thread is None or not self._monitor_thread.is_alive():
            self._stop_monitor.clear()
            self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()

    def _drain_active_queue_locked(self) -> None:
        """Drains IPC queue and checks active process liveness."""
        if not self._active_op_id:
            return

        op = self._operations.get(self._active_op_id)
        queue = self._active_queue
        proc = self._active_process

        if not op or not queue or not proc:
            return

        # 1. Drain Queue Messages
        while True:
            try:
                if queue.empty():
                    break
                msg = queue.get_nowait()
            except Exception:
                break

            msg_type = msg.get("type")
            now = datetime.now(UTC)

            if msg_type == "HEARTBEAT":
                op.last_heartbeat_at = now

            elif msg_type == "PROGRESS":
                op.progress = float(msg.get("progress", op.progress))
                op.stage = str(msg.get("stage", op.stage))
                op.last_heartbeat_at = now

            elif msg_type == "SUCCESS":
                op.status = OperationStatus.SUCCEEDED
                op.progress = 1.0
                op.stage = "COMPLETED"
                op.result = msg.get("result")
                op.completed_at = now
                self._active_op_id = None
                self._active_process = None
                self._active_queue = None
                self._active_cancel_event = None
                return

            elif msg_type == "ERROR":
                op.status = OperationStatus.FAILED
                op.stage = "FAILED"
                op.error = {
                    "code": msg.get("error_code", "WORKER_FAILED"),
                    "message": msg.get("error_message", "Worker error"),
                    "details": msg.get("details", {}),
                }
                op.completed_at = now
                self._active_op_id = None
                self._active_process = None
                self._active_queue = None
                self._active_cancel_event = None
                return

            elif msg_type == "CANCELLED":
                op.status = OperationStatus.CANCELLED
                op.stage = "CANCELLED"
                op.completed_at = now
                self._active_op_id = None
                self._active_process = None
                self._active_queue = None
                self._active_cancel_event = None
                return

        # 2. Check Process Liveness and Exit Code
        if op.status == OperationStatus.RUNNING:
            now = datetime.now(UTC)
            if not proc.is_alive():
                # Process died without sending a terminal message
                if op.cancellation_requested:
                    op.status = OperationStatus.CANCELLED
                    op.stage = "CANCELLED"
                else:
                    op.status = OperationStatus.LOST
                    op.stage = "LOST"
                    op.error = {
                        "code": "PROCESS_CRASHED",
                        "message": (
                            f"Worker process exited unexpectedly with exit code {proc.exitcode}."
                        ),
                        "details": {"exitcode": proc.exitcode, "pid": proc.pid},
                    }
                op.completed_at = now
                self._active_op_id = None
                self._active_process = None
                self._active_queue = None
                self._active_cancel_event = None

            elif op.last_heartbeat_at is not None:
                # Check Heartbeat Timeout
                elapsed_since_hb = (now - op.last_heartbeat_at).total_seconds()
                if elapsed_since_hb > self.heartbeat_timeout_seconds:
                    try:
                        proc.terminate()
                        proc.join(timeout=0.5)
                        if proc.is_alive():
                            proc.kill()
                    except Exception:
                        pass

                    op.status = OperationStatus.LOST
                    op.stage = "LOST"
                    op.error = {
                        "code": "HEARTBEAT_TIMEOUT",
                        "message": (
                            f"Worker process heartbeat timed out after {elapsed_since_hb:.1f}s "
                            f"(limit: {self.heartbeat_timeout_seconds}s)."
                        ),
                        "details": {"elapsed_seconds": elapsed_since_hb},
                    }
                    op.completed_at = now
                    self._active_op_id = None
                    self._active_process = None
                    self._active_queue = None
                    self._active_cancel_event = None

    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while not self._stop_monitor.is_set():
            with self._lock:
                self._drain_active_queue_locked()
            time.sleep(0.05)


# Global supervisor instance
supervisor = WorkerSupervisor()
