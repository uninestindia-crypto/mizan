import statistics
import time

import pytest
from httpx import AsyncClient

BENCHMARK_TARGETS = [
    ("/api/v1/health", "System Health Check"),
    ("/api/v1/stocks/TCS.NS", "Full Stock Detail & Fundamentals"),
    ("/api/v1/stocks/search?q=tcs", "Instant FTS5 Search Autocomplete"),
    (
        "/api/v1/stocks?sector=Information%20Technology&status=COMPLIANT",
        "Multi-Filter Screener Query",
    ),
    ("/api/v1/stocks/TCS.NS/screen?standard=both", "Dual-Standard Shariah Screen"),
    ("/api/v1/stocks/TCS.NS/audit", "Line-Item Audit Trail"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint,endpoint_name", BENCHMARK_TARGETS)
async def test_endpoint_sub_50ms_p95_latency(
    client: AsyncClient, endpoint: str, endpoint_name: str
):
    """
    Automated Latency Benchmark SLA:
    Runs 5 warm-up queries followed by 50 timed iterations using high-resolution perf_counter.
    Asserts strictly that the 95th percentile (p95) latency remains < 50.0 milliseconds.
    """
    # 1. Warm-up phase (5 requests to prime SQLite cache & connections)
    for _ in range(5):
        warm_res = await client.get(endpoint)
        assert warm_res.status_code == 200

    # 2. Benchmark phase (50 iterations)
    latencies_ms = []
    for _ in range(50):
        t0 = time.perf_counter_ns()
        response = await client.get(endpoint)
        t1 = time.perf_counter_ns()

        assert response.status_code == 200
        latency_ms = (t1 - t0) / 1_000_000.0
        latencies_ms.append(latency_ms)

    # Calculate statistics
    avg_latency = statistics.mean(latencies_ms)
    min_latency = min(latencies_ms)
    max_latency = max(latencies_ms)
    # 95th percentile: 95% of 50 samples is index 47
    sorted_latencies = sorted(latencies_ms)
    p95_latency = sorted_latencies[int(0.95 * len(sorted_latencies))]

    print(
        f"\n[BENCHMARK] {endpoint_name} ({endpoint}) -> "
        f"Avg: {avg_latency:.2f}ms | Min: {min_latency:.2f}ms | Max: {max_latency:.2f}ms | p95: {p95_latency:.2f}ms"
    )

    # Platform SLA: Sub-50ms query response time
    assert p95_latency < 50.0, (
        f"SLA Breached for {endpoint_name}: p95 was {p95_latency:.2f}ms (Target: < 50.0ms)"
    )
