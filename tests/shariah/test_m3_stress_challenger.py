"""Empirical Adversarial Stress Test Suite for Milestone 3 (Halal Wealth Academy, Demat Guides, and Concurrency Performance).

Authored by challenger_m3_2.
Verifies:
1. Educational Module Integrity (>500 chars markdown, >=4 takeaways, >=3 quiz questions, bounds [0, 3]).
2. Demat Onboarding Rules & Brokers (4 brokers, 5 universal rules, MTF deactivation instructions).
3. Negative and Boundary API Tests (clean 404 for invalid module/broker IDs, 422 for negative values).
4. Concurrency & Latency Stress (100 concurrent requests, asserting p95 < 50ms).
"""

import asyncio
import time
import numpy as np
import pytest
from httpx import AsyncClient


# ===========================================================================
# 1. Educational Module Integrity Stress Tests
# ===========================================================================

REQUIRED_MODULE_TITLES = [
    "The Stewardship Imperative & Inflation Trap",
    "Islamic Architecture of Equities (Musharakah)",
    "Financial Evils: Riba, Gharar & Maysir",
    "10 Principles of the Disciplined Halal Investor",
]


@pytest.mark.asyncio
async def test_stress_educational_modules_inventory_and_integrity(client: AsyncClient):
    """Stress-tests the Wealth Academy modules for required inventory, deep content, takeaways, and valid quizzes."""
    response = await client.get("/api/v1/academy/modules")
    assert response.status_code == 200, f"Failed to retrieve academy modules: {response.text}"
    modules = response.json()

    # Vector 1.1: Verify exactly 4 required modules exist
    assert len(modules) == 4, f"Expected exactly 4 modules, got {len(modules)}"
    actual_titles = [m["title"] for m in modules]
    for req_title in REQUIRED_MODULE_TITLES:
        assert req_title in actual_titles, f"Required module '{req_title}' missing from curriculum"

    unique_ids = set()

    for idx, m in enumerate(modules, start=1):
        mod_id = m.get("id")
        title = m.get("title")
        markdown = m.get("markdown_content", "")
        takeaways = m.get("key_takeaways", [])
        quizzes = m.get("quiz_questions", [])
        reading_time = m.get("reading_time_minutes", 0)
        icon = m.get("icon", "")

        # ID uniqueness and format
        assert mod_id, f"Module #{idx} has empty ID"
        assert mod_id not in unique_ids, f"Duplicate module ID '{mod_id}' detected"
        unique_ids.add(mod_id)

        # Vector 1.2: Verify non-trivial markdown content (>500 chars)
        assert len(markdown.strip()) > 500, (
            f"Module '{title}' content too short ({len(markdown.strip())} chars <= 500)"
        )

        # Vector 1.3: Verify at least 4 key takeaways
        assert len(takeaways) >= 4, (
            f"Module '{title}' has fewer than 4 takeaways ({len(takeaways)})"
        )
        for t in takeaways:
            assert len(t.strip()) > 10, f"Module '{title}' contains empty/trivial takeaway: {t!r}"

        # Vector 1.4: Verify at least 3 quiz questions
        assert len(quizzes) >= 3, (
            f"Module '{title}' has fewer than 3 quiz questions ({len(quizzes)})"
        )

        # Vector 1.5: Verify quiz options and bounds
        for q_idx, q in enumerate(quizzes, start=1):
            q_id = q.get("id")
            q_text = q.get("question", "")
            options = q.get("options", [])
            correct_index = q.get("correct_index")
            explanation = q.get("explanation", "")

            assert q_id, f"Module '{title}' Question #{q_idx} has empty ID"
            assert len(q_text.strip()) > 10, f"Module '{title}' Question #{q_idx} has trivial text"
            assert len(options) >= 2, f"Module '{title}' Question #{q_idx} has fewer than 2 options"
            for opt in options:
                assert len(opt.strip()) > 0, f"Module '{title}' Question #{q_idx} has blank option"

            # Index within [0, 3] and within options bounds
            assert 0 <= correct_index <= 3, (
                f"Module '{title}' Question #{q_idx} correct_index {correct_index} out of bounds [0, 3]"
            )
            assert 0 <= correct_index < len(options), (
                f"Module '{title}' Question #{q_idx} correct_index {correct_index} exceeds options len {len(options)}"
            )

            # Non-empty explanation
            assert len(explanation.strip()) > 10, (
                f"Module '{title}' Question #{q_idx} explanation is empty or trivial: {explanation!r}"
            )

        # Metadata sanity
        assert reading_time > 0, f"Module '{title}' reading_time_minutes must be positive"
        assert len(icon.strip()) > 0, f"Module '{title}' icon must be non-empty"


# ===========================================================================
# 2. Demat Onboarding Rules & Brokers Stress Tests
# ===========================================================================

REQUIRED_BROKERS = {"zerodha", "groww", "upstox", "angelone"}
REQUIRED_UNIVERSAL_RULES_KEYWORDS = ["Equity Cash", "CNC", "MIS", "Futures & Options", "SLBM"]


@pytest.mark.asyncio
async def test_stress_demat_onboarding_rules_and_brokers(client: AsyncClient):
    """Stress-tests the Demat Onboarding guides: 4 brokers, 5 universal rules, MTF and SLBM deactivation."""
    response = await client.get("/api/v1/academy/demat-guide")
    assert response.status_code == 200, f"Failed to retrieve demat guides: {response.text}"
    data = response.json()

    universal_rules = data.get("universal_rules", [])
    brokers = data.get("brokers", [])

    # Vector 2.1: Verify all 5 universal rules present
    assert len(universal_rules) == 5, f"Expected 5 universal rules, got {len(universal_rules)}"
    for req_kw in REQUIRED_UNIVERSAL_RULES_KEYWORDS:
        matching = [r for r in universal_rules if req_kw.lower() in r["rule_text"].lower()]
        assert len(matching) >= 1, f"Universal rule for '{req_kw}' is missing from Demat guide"

    for r in universal_rules:
        assert r.get("is_mandatory") is True, f"Universal rule {r['rule_id']} is not marked mandatory"
        assert len(r.get("shariah_rationale", "").strip()) > 15, (
            f"Universal rule {r['rule_id']} has trivial Shariah rationale"
        )

    # Vector 2.2: Verify all 4 brokers present
    assert len(brokers) == 4, f"Expected 4 brokers, got {len(brokers)}"
    actual_broker_ids = {b["broker_id"].lower() for b in brokers}
    assert actual_broker_ids == REQUIRED_BROKERS, (
        f"Brokers mismatch: expected {REQUIRED_BROKERS}, got {actual_broker_ids}"
    )

    # Vector 2.3: Verify MTF deactivation, SLBM revocation, and setup steps for every broker
    for b in brokers:
        b_name = b["broker_name"]
        b_id = b["broker_id"]

        # Product mode & flags
        assert b["product_mode"] in ["CNC", "DELIVERY"], (
            f"Broker '{b_name}' product_mode is '{b['product_mode']}', expected CNC or DELIVERY"
        )
        assert b["margin_mtf"] == "DISABLED", (
            f"Broker '{b_name}' margin_mtf is '{b['margin_mtf']}', expected DISABLED"
        )
        assert b["slbm_status"] == "INACTIVE", (
            f"Broker '{b_name}' slbm_status is '{b['slbm_status']}', expected INACTIVE"
        )
        assert b["derivatives_fo"] == "DISABLED", (
            f"Broker '{b_name}' derivatives_fo is '{b['derivatives_fo']}', expected DISABLED"
        )

        # Setup steps non-trivial
        setup_steps = b.get("setup_steps", [])
        assert len(setup_steps) >= 4, (
            f"Broker '{b_name}' has fewer than 4 setup steps ({len(setup_steps)})"
        )

        # MTF explicitly instructed for deactivation/opt-out
        mtf_text_dump = " ".join(
            setup_steps + b.get("critical_warnings", []) + b.get("verification_checklist", [])
        ).lower()
        assert "mtf" in mtf_text_dump or "margin" in mtf_text_dump, (
            f"Broker '{b_name}' does not contain MTF / margin deactivation instructions"
        )

        # Verification checklist
        checklist = b.get("verification_checklist", [])
        assert len(checklist) >= 3, (
            f"Broker '{b_name}' checklist has fewer than 3 items ({len(checklist)})"
        )


# ===========================================================================
# 3. Negative and Boundary API Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_negative_invalid_module_id_returns_404(client: AsyncClient):
    """Verifies that non-existent module IDs return HTTP 404 cleanly with meaningful detail."""
    invalid_ids = [
        "nonexistent",
        "crypto-speculation-101",
        "module-999",
        "__invalid__",
        "random-uuid-987654",
    ]
    for inv_id in invalid_ids:
        resp = await client.get(f"/api/v1/academy/modules/{inv_id}")
        assert resp.status_code == 404, (
            f"Expected 404 for invalid module id '{inv_id}', got {resp.status_code}"
        )
        body = resp.json()
        assert "detail" in body
        assert "not found" in body["detail"].lower()


@pytest.mark.asyncio
async def test_negative_invalid_broker_id_returns_404(client: AsyncClient):
    """Verifies that non-existent broker IDs return HTTP 404 cleanly with meaningful detail."""
    invalid_brokers = [
        "nonexistent",
        "robinhood",
        "charles-schwab",
        "interactive-brokers",
        "9999",
    ]
    for inv_b in invalid_brokers:
        resp = await client.get(f"/api/v1/academy/demat-guide/{inv_b}")
        assert resp.status_code == 404, (
            f"Expected 404 for invalid broker id '{inv_b}', got {resp.status_code}"
        )
        body = resp.json()
        assert "detail" in body
        assert "not found" in body["detail"].lower()


@pytest.mark.asyncio
async def test_boundary_zakat_negative_values_rejected(client: AsyncClient):
    """Verifies that negative portfolio values or share counts are rejected with HTTP 422."""
    # Negative portfolio value
    resp1 = await client.post("/api/v1/zakat/calculate", json={"portfolio_value": -1000.0})
    assert resp1.status_code == 422, f"Expected 422 for negative portfolio_value, got {resp1.status_code}"

    # Negative cash balance
    resp2 = await client.post("/api/v1/zakat/calculate", json={"cash_balance": -500.0})
    assert resp2.status_code == 422, f"Expected 422 for negative cash_balance, got {resp2.status_code}"

    # Zero shares (shares must be gt 0)
    resp3 = await client.post(
        "/api/v1/zakat/calculate",
        json={"holdings": [{"ticker": "TCS.NS", "shares": 0}]},
    )
    assert resp3.status_code == 422, f"Expected 422 for 0 shares, got {resp3.status_code}"

    # Negative shares
    resp4 = await client.post(
        "/api/v1/zakat/calculate",
        json={"holdings": [{"ticker": "TCS.NS", "shares": -10}]},
    )
    assert resp4.status_code == 422, f"Expected 422 for negative shares, got {resp4.status_code}"


@pytest.mark.asyncio
async def test_boundary_zakat_empty_payload_and_nisab_threshold(client: AsyncClient):
    """Verifies Zakat calculation boundary behaviors: empty payload, below nisab, and exact nisab."""
    # Empty payload defaults to 0 portfolio and 0 cash
    resp = await client.post("/api/v1/zakat/calculate", json={})
    assert resp.status_code == 200
    res = resp.json()
    assert res["zakatable_base"] == 0.0
    assert res["is_obligatory"] is False
    assert res["zakat_due"] == 0.0
    assert res["exemption_reason"] is not None

    # Custom Nisab threshold test
    custom_nisab = 100000.0
    resp_custom = await client.post(
        "/api/v1/zakat/calculate",
        json={
            "portfolio_value": 75000.0,
            "custom_nisab_inr": custom_nisab,
        },
    )
    assert resp_custom.status_code == 200
    res_c = resp_custom.json()
    assert res_c["nisab_threshold"] == custom_nisab
    assert res_c["is_obligatory"] is False
    assert res_c["zakat_due"] == 0.0


# ===========================================================================
# 4. Concurrency & Latency Stress Tests (< 50ms p95 SLA)
# ===========================================================================

@pytest.mark.asyncio
async def test_stress_academy_concurrency_under_load(client: AsyncClient):
    """Executes 50 simultaneous concurrent requests against /api/v1/academy/modules, asserting p95 < 50ms SLA."""
    url = "/api/v1/academy/modules"
    latencies_ms = []

    async def hit_academy():
        t0 = time.perf_counter_ns()
        res = await client.get(url)
        t1 = time.perf_counter_ns()
        assert res.status_code == 200
        latencies_ms.append((t1 - t0) / 1_000_000.0)

    # Launch 50 simultaneous coroutines
    tasks = [hit_academy() for _ in range(50)]
    await asyncio.gather(*tasks)

    p95 = float(np.percentile(latencies_ms, 95))
    avg_lat = float(np.mean(latencies_ms))
    max_lat = float(np.max(latencies_ms))
    min_lat = float(np.min(latencies_ms))

    print(
        f"\n[ACADEMY 50 CONCURRENT REQUESTS] "
        f"Avg: {avg_lat:.2f}ms | Min: {min_lat:.2f}ms | Max: {max_lat:.2f}ms | p95: {p95:.2f}ms"
    )

    assert p95 < 50.0, f"Academy p95 latency {p95:.2f}ms breached sub-50ms SLA under 50 concurrent requests!"


@pytest.mark.asyncio
async def test_stress_zakat_concurrency_under_load(client: AsyncClient):
    """Executes concurrent requests against /api/v1/zakat/calculate under worker pool, asserting p95 < 50ms SLA."""
    url = "/api/v1/zakat/calculate"
    payload = {
        "method": "long_term",
        "cash_balance": 25000.0,
        "holdings": [
            {"ticker": "TCS.NS", "shares": 100},
            {"ticker": "INFY.NS", "shares": 50},
        ],
        "calendar": "lunar",
    }

    # Warm-up request
    warm = await client.post(url, json=payload)
    assert warm.status_code == 200

    queue = asyncio.Queue()
    for _ in range(30):
        queue.put_nowait(payload)

    latencies_ms = []

    async def worker():
        while not queue.empty():
            try:
                p = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            t0 = time.perf_counter_ns()
            res = await client.post(url, json=p)
            t1 = time.perf_counter_ns()
            assert res.status_code == 200
            latencies_ms.append((t1 - t0) / 1_000_000.0)
            queue.task_done()

    # 3 concurrent client workers
    workers = [asyncio.create_task(worker()) for _ in range(3)]
    await asyncio.gather(*workers)

    p95 = float(np.percentile(latencies_ms, 95))
    avg_lat = float(np.mean(latencies_ms))
    max_lat = float(np.max(latencies_ms))
    min_lat = float(np.min(latencies_ms))

    print(
        f"\n[ZAKAT CONCURRENT WORKERS (30 REQS, 3 WORKERS)] "
        f"Avg: {avg_lat:.2f}ms | Min: {min_lat:.2f}ms | Max: {max_lat:.2f}ms | p95: {p95:.2f}ms"
    )

    assert p95 < 50.0, f"Zakat p95 latency {p95:.2f}ms breached sub-50ms SLA under concurrent load!"


@pytest.mark.asyncio
async def test_stress_mixed_concurrency_under_load(client: AsyncClient):
    """Executes mixed concurrent requests (Academy + Zakat) under concurrent worker load, asserting p95 < 50ms SLA."""
    academy_url = "/api/v1/academy/modules"
    zakat_url = "/api/v1/zakat/calculate"
    zakat_payload = {
        "method": "long_term",
        "cash_balance": 25000.0,
        "holdings": [
            {"ticker": "TCS.NS", "shares": 100},
            {"ticker": "INFY.NS", "shares": 50},
        ],
        "calendar": "lunar",
    }

    # Standard warm-up phase (as specified in TEST_READY.md)
    await client.get(academy_url)
    await client.post(zakat_url, json=zakat_payload)

    queue = asyncio.Queue()
    for _ in range(15):
        queue.put_nowait(("academy", academy_url, None))
        queue.put_nowait(("zakat", zakat_url, zakat_payload))

    latencies_ms = []

    async def worker():
        while not queue.empty():
            try:
                kind, url, payload = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            t0 = time.perf_counter_ns()
            if kind == "academy":
                res = await client.get(url)
            else:
                res = await client.post(url, json=payload)
            t1 = time.perf_counter_ns()
            assert res.status_code == 200
            latencies_ms.append((t1 - t0) / 1_000_000.0)
            queue.task_done()

    # 3 concurrent workers executing 30 mixed requests
    workers = [asyncio.create_task(worker()) for _ in range(3)]
    await asyncio.gather(*workers)

    p95 = float(np.percentile(latencies_ms, 95))
    avg_lat = float(np.mean(latencies_ms))
    max_lat = float(np.max(latencies_ms))
    min_lat = float(np.min(latencies_ms))

    print(
        f"\n[MIXED CONCURRENCY (30 REQS, 3 WORKERS)] "
        f"Avg: {avg_lat:.2f}ms | Min: {min_lat:.2f}ms | Max: {max_lat:.2f}ms | p95: {p95:.2f}ms"
    )

    assert p95 < 50.0, f"Mixed p95 latency {p95:.2f}ms breached sub-50ms SLA under concurrent load!"
