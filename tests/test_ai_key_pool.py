"""Unit tests for Multi-Provider AI Key Pool, Failover Rotation, and CLI Diagnostics."""

import json
import urllib.request
from datetime import UTC, datetime, timedelta

from quant_system.alpha.ai_advisor import DirectAPIAdvisor
from quant_system.alpha.cli_manager import CLIManager
from quant_system.alpha.direct_providers import (
    BaseDirectAPIClient,
    parse_json_from_llm_response,
)
from quant_system.alpha.key_pool import (
    KeyPoolManager,
    KeyStatus,
    ManagedKey,
    ProviderType,
    RotationPolicy,
)
from quant_system.core.domain import Side


class MockFailoverClient(BaseDirectAPIClient):
    """Mock client simulating a 429 rate limit on the first key and success on the backup key."""

    def __init__(self) -> None:
        super().__init__(default_model="mock-model")
        self.call_count = 0

    def build_request(
        self, prompt: str, key: ManagedKey, model: str | None = None
    ) -> urllib.request.Request:
        return urllib.request.Request("http://mock.endpoint")

    def parse_response_content(self, response_body: bytes) -> str:
        return ""

    def execute(
        self,
        prompt: str,
        key: ManagedKey,
        model: str | None = None,
    ) -> tuple[str | None, int, float | None, str | None]:
        self.call_count += 1
        if key.key_id == "key_primary":
            # Simulate 429 rate limit with 30s retry after
            return None, 429, 30.0, "Rate limit exceeded"
        # Simulate successful JSON response from backup key
        resp_json = json.dumps(
            {
                "action_bias": "BULLISH",
                "confidence": 0.88,
                "weight_multiplier": 1.2,
                "rationale": f"Backup key {key.key_id} approved.",
            }
        )
        return resp_json, 200, None, None


def test_key_masking() -> None:
    short_k = ManagedKey(key_id="k1", provider=ProviderType.GROQ, secret_value="1234")
    assert short_k.mask_key() == "****"

    long_k = ManagedKey(
        key_id="k2", provider=ProviderType.OPENROUTER, secret_value="sk-or-v1-abcdef1234567890"
    )
    masked = long_k.mask_key()
    assert masked.startswith("sk-o")
    assert masked.endswith("7890")
    assert "****" in masked


def test_priority_failover_dispatch() -> None:
    pool = KeyPoolManager(policy=RotationPolicy.PRIORITY_FAILOVER)
    k1 = pool.add_key("sk-primary", ProviderType.GROQ, key_id="primary", priority=1)
    pool.add_key("sk-backup", ProviderType.GROQ, key_id="backup", priority=2)

    # Primary should be chosen first
    active = pool.get_active_key(ProviderType.GROQ)
    assert active is not None
    assert active.key_id == "primary"

    # Put primary in cooldown
    pool.record_rate_limit(k1, retry_after_seconds=60.0)

    # Now backup should be chosen
    active_after_429 = pool.get_active_key(ProviderType.GROQ)
    assert active_after_429 is not None
    assert active_after_429.key_id == "backup"


def test_round_robin_dispatch() -> None:
    pool = KeyPoolManager(policy=RotationPolicy.ROUND_ROBIN)
    pool.add_key("sk-k1", ProviderType.OPENAI, key_id="key1")
    pool.add_key("sk-k2", ProviderType.OPENAI, key_id="key2")

    first = pool.get_active_key(ProviderType.OPENAI)
    second = pool.get_active_key(ProviderType.OPENAI)
    third = pool.get_active_key(ProviderType.OPENAI)

    assert first is not None and first.key_id == "key1"
    assert second is not None and second.key_id == "key2"
    assert third is not None and third.key_id == "key1"


def test_rate_limit_cooldown_and_auto_recovery() -> None:
    pool = KeyPoolManager()
    now = datetime.now(UTC)
    k1 = pool.add_key("sk-test", ProviderType.OPENROUTER, key_id="k1")

    # Rate limit with 10s cooldown
    pool.record_rate_limit(k1, retry_after_seconds=10.0, now=now)
    assert k1.status.value == KeyStatus.COOLDOWN.value
    assert not k1.is_available(now=now)

    # 5s later -> still in cooldown
    assert not k1.is_available(now=now + timedelta(seconds=5))

    # 11s later -> recovered
    assert k1.is_available(now=now + timedelta(seconds=11))
    recovered = pool.auto_recover_cooldowns(now=now + timedelta(seconds=11))
    assert recovered == 1
    assert k1.status.value == KeyStatus.ACTIVE.value


def test_direct_api_failover_loop_on_rate_limit() -> None:
    pool = KeyPoolManager()
    pool.add_key("sk-prim", ProviderType.OPENROUTER, key_id="key_primary", priority=1)
    pool.add_key("sk-back", ProviderType.OPENROUTER, key_id="key_backup", priority=2)

    mock_client = MockFailoverClient()
    advisor = DirectAPIAdvisor(
        provider=ProviderType.OPENROUTER,
        key_pool=pool,
        client=mock_client,
    )

    opinion = advisor.evaluate_opportunity(
        symbol="RELIANCE",
        quant_side=Side.BUY,
        quant_strength=0.75,
        technical_summary={"rsi": 55.0, "atr_normalized": 0.02},
    )

    # Should have called primary (which 429'd) then backup (which succeeded)
    assert mock_client.call_count == 2
    assert opinion.action_bias == "BULLISH"
    assert opinion.confidence == 0.88
    assert opinion.weight_multiplier == 1.2
    assert "key_backup" in opinion.rationale
    assert opinion.metadata.get("key_id") == "key_backup"


def test_parse_json_from_llm_response() -> None:
    # Standard JSON
    assert parse_json_from_llm_response('{"action_bias": "BULLISH"}') == {"action_bias": "BULLISH"}

    # Markdown wrapped
    markdown_str = 'Here is the response:\n```json\n{"action_bias": "VETO", "confidence": 0.9}\n```'
    assert parse_json_from_llm_response(markdown_str) == {"action_bias": "VETO", "confidence": 0.9}

    # Malformed
    assert parse_json_from_llm_response("Not a json at all") is None


def test_cli_manager_diagnostics() -> None:
    summary = CLIManager.get_summary()
    assert "total_supported" in summary
    assert summary["total_supported"] == 3
    assert len(summary["items"]) == 3
    assert any(item["command"] == "claude" for item in summary["items"])
    assert any(item["command"] == "codex" for item in summary["items"])
    assert any(item["command"] == "agy" for item in summary["items"])
