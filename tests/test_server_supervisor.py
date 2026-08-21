"""Tests for QuantOS Background Worker Supervisor and Process Lifecycle."""

import time

import pytest

from quant_system.server.schemas import OperationStatus, OperationType
from quant_system.server.supervisor import (
    ConcurrentLimitError,
    OperationNotFoundError,
    WorkerSupervisor,
)


@pytest.fixture
def supervisor_instance() -> WorkerSupervisor:
    sup = WorkerSupervisor(heartbeat_timeout_seconds=5.0, cancellation_grace_seconds=1.0)
    yield sup
    sup.shutdown()


def test_supervisor_successful_execution(supervisor_instance: WorkerSupervisor) -> None:
    payload = {"action": "compute"}
    op = supervisor_instance.submit_operation(OperationType.CUSTOM, payload)
    assert op.status in (OperationStatus.PENDING, OperationStatus.RUNNING)
    assert op.operation_id.startswith("op-")

    # Poll until success
    max_wait = 10.0
    t0 = time.monotonic()
    final_op = None

    while time.monotonic() - t0 < max_wait:
        current = supervisor_instance.get_operation(op.operation_id)
        assert current is not None
        if current.status == OperationStatus.SUCCEEDED:
            final_op = current
            break
        elif current.status in (OperationStatus.FAILED, OperationStatus.LOST):
            pytest.fail(f"Operation failed unexpectedly: {current}")
        time.sleep(0.05)

    assert final_op is not None
    assert final_op.status == OperationStatus.SUCCEEDED
    assert final_op.progress == 1.0
    assert final_op.stage == "COMPLETED"
    assert final_op.result is not None
    assert final_op.result["action"] == "compute"
    assert final_op.completed_at is not None


def test_supervisor_heartbeats_and_progress_tracking(
    supervisor_instance: WorkerSupervisor,
) -> None:
    payload = {"action": "sleep", "duration": 0.8}
    op = supervisor_instance.submit_operation(OperationType.CUSTOM, payload)

    time.sleep(0.3)
    current = supervisor_instance.get_operation(op.operation_id)
    assert current is not None
    assert current.last_heartbeat_at is not None

    # Wait for completion
    max_wait = 3.0
    t0 = time.monotonic()
    final_op = None
    while time.monotonic() - t0 < max_wait:
        final_op = supervisor_instance.get_operation(op.operation_id)
        if final_op and final_op.status == OperationStatus.SUCCEEDED:
            break
        time.sleep(0.05)

    assert final_op is not None
    assert final_op.status == OperationStatus.SUCCEEDED


def test_supervisor_cooperative_cancellation(supervisor_instance: WorkerSupervisor) -> None:
    payload = {"action": "sleep", "duration": 5.0}
    op = supervisor_instance.submit_operation(OperationType.CUSTOM, payload)

    time.sleep(0.1)
    cancelled_op = supervisor_instance.cancel_operation(op.operation_id)
    assert cancelled_op.status == OperationStatus.CANCELLED
    assert cancelled_op.cancellation_requested is True

    # Check polled status
    polled = supervisor_instance.get_operation(op.operation_id)
    assert polled is not None
    assert polled.status == OperationStatus.CANCELLED

    # Verify that the compute lease is released and a new operation can run
    new_op = supervisor_instance.submit_operation(OperationType.CUSTOM, {"action": "compute"})
    assert new_op.status in (OperationStatus.PENDING, OperationStatus.RUNNING)


def test_supervisor_process_crash_recovery(supervisor_instance: WorkerSupervisor) -> None:
    # Action 'crash' causes the worker to call os._exit(42)
    payload = {"action": "crash"}
    op = supervisor_instance.submit_operation(OperationType.CUSTOM, payload)

    # Poll for supervisor detecting process loss
    max_wait = 5.0
    t0 = time.monotonic()
    lost_op = None

    while time.monotonic() - t0 < max_wait:
        current = supervisor_instance.get_operation(op.operation_id)
        assert current is not None
        if current.status in (OperationStatus.LOST, OperationStatus.FAILED):
            lost_op = current
            break
        time.sleep(0.05)

    assert lost_op is not None
    assert lost_op.status in (OperationStatus.LOST, OperationStatus.FAILED)
    assert lost_op.error is not None
    assert lost_op.error["code"] == "PROCESS_CRASHED"
    assert "42" in lost_op.error["message"]

    # Verify that the compute lease was released and new operations succeed
    next_op = supervisor_instance.submit_operation(OperationType.CUSTOM, {"action": "compute"})
    assert next_op.status in (OperationStatus.PENDING, OperationStatus.RUNNING)


def test_supervisor_heartbeat_timeout_handling() -> None:
    # Create supervisor with very short heartbeat timeout
    sup = WorkerSupervisor(heartbeat_timeout_seconds=0.6, cancellation_grace_seconds=0.5)
    try:
        # Action 'hang' blocks worker and prevents heartbeats
        payload = {"action": "hang"}
        op = sup.submit_operation(OperationType.CUSTOM, payload)

        max_wait = 5.0
        t0 = time.monotonic()
        lost_op = None

        while time.monotonic() - t0 < max_wait:
            current = sup.get_operation(op.operation_id)
            assert current is not None
            if current.status == OperationStatus.LOST:
                lost_op = current
                break
            time.sleep(0.05)

        assert lost_op is not None
        assert lost_op.status == OperationStatus.LOST
        assert lost_op.error is not None
        assert lost_op.error["code"] == "HEARTBEAT_TIMEOUT"

        # Verify lease was freed
        next_op = sup.submit_operation(OperationType.CUSTOM, {"action": "compute"})
        assert next_op.status in (OperationStatus.PENDING, OperationStatus.RUNNING)
    finally:
        sup.shutdown()


def test_supervisor_single_operation_compute_lease_enforcement(
    supervisor_instance: WorkerSupervisor,
) -> None:
    payload = {"action": "sleep", "duration": 2.0}
    op1 = supervisor_instance.submit_operation(OperationType.CUSTOM, payload)
    assert op1.status in (OperationStatus.PENDING, OperationStatus.RUNNING)

    # Second submission with different key -> raises ConcurrentLimitError
    with pytest.raises(ConcurrentLimitError) as exc_info:
        supervisor_instance.submit_operation(
            OperationType.CUSTOM,
            {"action": "compute"},
            idempotency_key="diff-key",
        )
    assert "CONCURRENT_LIMIT" in str(exc_info.value)

    # Cancel op1
    supervisor_instance.cancel_operation(op1.operation_id)


def test_supervisor_idempotency_key_deduplication(
    supervisor_instance: WorkerSupervisor,
) -> None:
    payload = {"action": "sleep", "duration": 1.5}
    idem_key = "idempotency-token-xyz-100"

    op1 = supervisor_instance.submit_operation(
        OperationType.CUSTOM, payload, idempotency_key=idem_key
    )
    op2 = supervisor_instance.submit_operation(
        OperationType.CUSTOM, payload, idempotency_key=idem_key
    )

    assert op1.operation_id == op2.operation_id
    assert op1.idempotency_key == idem_key

    supervisor_instance.cancel_operation(op1.operation_id)


def test_supervisor_cancel_non_existent_operation(
    supervisor_instance: WorkerSupervisor,
) -> None:
    with pytest.raises(OperationNotFoundError):
        supervisor_instance.cancel_operation("op-does-not-exist-999")


def test_supervisor_backtest_worker_task(supervisor_instance: WorkerSupervisor) -> None:
    payload = {
        "strategy_name": "EquityDualMomentum",
        "symbols": ["INFY", "TCS"],
        "days": 30,
        "initial_cash": 100000.0,
        "slippage_bps": 5.0,
    }
    op = supervisor_instance.submit_operation(OperationType.BACKTEST, payload)

    max_wait = 15.0
    t0 = time.monotonic()
    final_op = None

    while time.monotonic() - t0 < max_wait:
        current = supervisor_instance.get_operation(op.operation_id)
        assert current is not None
        if current.status == OperationStatus.SUCCEEDED:
            final_op = current
            break
        elif current.status in (OperationStatus.FAILED, OperationStatus.LOST):
            pytest.fail(f"Backtest worker failed: {current}")
        time.sleep(0.1)

    assert final_op is not None
    assert final_op.result is not None
    assert "equity_curve" in final_op.result
    assert "stats" in final_op.result
