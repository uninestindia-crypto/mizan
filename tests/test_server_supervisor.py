"""Tests for QuantOS Background Worker Supervisor and Process Lifecycle."""

import queue
import time
from collections.abc import Callable, Iterator
from types import SimpleNamespace

import pytest

from quant_system.server.schemas import OperationStatus, OperationType
from quant_system.server.supervisor import (
    ConcurrentLimitError,
    OperationNotFoundError,
    OperationRecord,
    WorkerSupervisor,
)

_POLL_SECONDS = 0.05
# A worker is a freshly spawned Python process that imports the server stack before it runs its
# action. On the reference machine (Snapdragon X, Windows 11 ARM64) that start-up alone is about
# 3 s, so a 0.8 s task finishes at about 4 s (measured 2026-10-03). The deadline only has to be
# longer than a healthy start; it is not an assertion about speed.
_WORKER_START_BUDGET = 15.0


def _failed_or_lost(record: OperationRecord) -> str | None:
    if record.status in (OperationStatus.FAILED, OperationStatus.LOST):
        return f"operation reached a terminal failure while waiting: {record}"
    return None


def _await_operation(
    supervisor: WorkerSupervisor,
    operation_id: str,
    predicate: Callable[[OperationRecord], bool],
    *,
    timeout: float,
    describe: str,
    abort_on: Callable[[OperationRecord], str | None] | None = None,
) -> OperationRecord:
    """Wait for a real subprocess-backed operation to reach a condition, or fail saying which.

    These tests drive an actual worker process, so the state they assert on genuinely arrives
    asynchronously. The previous code either slept a fixed guess and then asserted — which asserts
    the timing, not the condition, and fails on a loaded machine — or repeated this poll inline in
    five places.

    Waiting on the predicate makes the test deterministic in outcome: it passes as soon as the
    condition holds and fails with a specific message if it never does, rather than passing or
    failing according to how busy the host was.
    """
    deadline = time.monotonic() + timeout
    last: OperationRecord | None = None
    while time.monotonic() < deadline:
        last = supervisor.get_operation(operation_id)
        assert last is not None, (
            f"operation {operation_id} disappeared while waiting for {describe}"
        )
        if abort_on is not None:
            reason = abort_on(last)
            if reason is not None:
                pytest.fail(reason)
        if predicate(last):
            return last
        # test-allow: sleep-in-test - poll interval; the assertion is the predicate, not the clock
        time.sleep(_POLL_SECONDS)
    pytest.fail(f"timed out after {timeout}s waiting for {describe}; last seen: {last}")


@pytest.fixture
def supervisor_instance() -> Iterator[WorkerSupervisor]:
    sup = WorkerSupervisor(heartbeat_timeout_seconds=5.0, cancellation_grace_seconds=1.0)
    yield sup
    sup.shutdown()


def test_supervisor_successful_execution(supervisor_instance: WorkerSupervisor) -> None:
    payload = {"action": "compute"}
    op = supervisor_instance.submit_operation(OperationType.CUSTOM, payload)
    assert op.status in (OperationStatus.PENDING, OperationStatus.RUNNING)
    assert op.operation_id.startswith("op-")

    final_op = _await_operation(
        supervisor_instance,
        op.operation_id,
        lambda record: record.status == OperationStatus.SUCCEEDED,
        timeout=10.0,
        describe="the compute operation to succeed",
        abort_on=_failed_or_lost,
    )
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

    _await_operation(
        supervisor_instance,
        op.operation_id,
        lambda record: record.last_heartbeat_at is not None,
        timeout=_WORKER_START_BUDGET,
        describe="the worker to emit its first heartbeat",
        abort_on=_failed_or_lost,
    )

    final_op = _await_operation(
        supervisor_instance,
        op.operation_id,
        lambda record: record.status == OperationStatus.SUCCEEDED,
        timeout=_WORKER_START_BUDGET,
        describe="the operation to succeed",
    )
    assert final_op.status == OperationStatus.SUCCEEDED


def test_supervisor_cooperative_cancellation(supervisor_instance: WorkerSupervisor) -> None:
    payload = {"action": "sleep", "duration": 5.0}
    op = supervisor_instance.submit_operation(OperationType.CUSTOM, payload)

    _await_operation(
        supervisor_instance,
        op.operation_id,
        lambda record: record.status == OperationStatus.RUNNING,
        timeout=5.0,
        describe="the worker to start before cancelling it",
        abort_on=_failed_or_lost,
    )
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


def test_cancellation_preserves_a_worker_success_that_won_during_grace() -> None:
    events: queue.Queue[dict[str, object]] = queue.Queue()

    class SuccessOnJoinProcess:
        pid = 1234
        exitcode = 0

        def __init__(self) -> None:
            self.alive = True

        def join(self, timeout: float) -> None:
            assert timeout == 0.25
            events.put({"type": "SUCCESS", "result": {"published": True}})
            self.alive = False

        def is_alive(self) -> bool:
            return self.alive

    supervisor = WorkerSupervisor(cancellation_grace_seconds=0.25)
    operation = OperationRecord(
        operation_id="op-123456789abc",
        operation_type=OperationType.DATA_SYNC,
        status=OperationStatus.RUNNING,
    )
    process = SuccessOnJoinProcess()
    with supervisor._lock:
        supervisor._operations[operation.operation_id] = operation
        supervisor._active_op_id = operation.operation_id
        supervisor._active_process = process  # type: ignore[assignment]
        supervisor._active_queue = events
        supervisor._active_cancel_event = SimpleNamespace(set=lambda: None)

    result = supervisor.cancel_operation(operation.operation_id)

    assert result.status == OperationStatus.SUCCEEDED
    assert result.result == {"published": True}
    assert result.cancellation_requested is True


def test_supervisor_process_crash_recovery(supervisor_instance: WorkerSupervisor) -> None:
    # Action 'crash' causes the worker to call os._exit(42)
    payload = {"action": "crash"}
    op = supervisor_instance.submit_operation(OperationType.CUSTOM, payload)

    lost_op = _await_operation(
        supervisor_instance,
        op.operation_id,
        lambda record: record.status in (OperationStatus.LOST, OperationStatus.FAILED),
        timeout=5.0,
        describe="the supervisor to detect the crashed worker",
    )
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

        lost_op = _await_operation(
            sup,
            op.operation_id,
            lambda record: record.status == OperationStatus.LOST,
            timeout=5.0,
            describe="the hung worker to be declared LOST",
        )
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

    final_op = _await_operation(
        supervisor_instance,
        op.operation_id,
        lambda record: record.status == OperationStatus.SUCCEEDED,
        timeout=15.0,
        describe="the backtest worker to succeed",
        abort_on=_failed_or_lost,
    )
    assert final_op.result is not None
    assert "equity_curve" in final_op.result
    assert "stats" in final_op.result
