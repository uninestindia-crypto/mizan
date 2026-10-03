"""Multi-Provider API Key Pool and Automatic Failover/Rotation Engine."""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class ProviderType(StrEnum):
    """Supported AI provider categories."""

    OPENROUTER = "OPENROUTER"
    GROQ = "GROQ"
    OPENAI = "OPENAI"
    ANTHROPIC = "ANTHROPIC"
    GEMINI = "GEMINI"
    DEEPSEEK = "DEEPSEEK"
    MISTRAL = "MISTRAL"
    CLAUDE_CLI = "CLAUDE_CLI"
    CODEX_CLI = "CODEX_CLI"
    ANTIGRAVITY_CLI = "ANTIGRAVITY_CLI"


class KeyStatus(StrEnum):
    """Lifecycle status of a managed API key or account profile."""

    ACTIVE = "ACTIVE"
    COOLDOWN = "COOLDOWN"
    EXHAUSTED = "EXHAUSTED"
    INVALID = "INVALID"


class RotationPolicy(StrEnum):
    """Rotation dispatch strategy across keys in a pool."""

    PRIORITY_FAILOVER = "PRIORITY_FAILOVER"
    ROUND_ROBIN = "ROUND_ROBIN"


@dataclass(slots=True)
class ManagedKey:
    """A managed API key or profile with rate-limit tracking and masking."""

    key_id: str
    provider: ProviderType
    secret_value: str
    status: KeyStatus = KeyStatus.ACTIVE
    cooldown_until: datetime | None = None
    priority: int = 1  # 1 is highest priority
    total_requests: int = 0
    failed_requests: int = 0
    rate_limit_count: int = 0
    last_used_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def mask_key(self) -> str:
        """Return a masked representation for logging and UI presentation."""
        val = self.secret_value.strip()
        if len(val) <= 8:
            return "****"
        return f"{val[:4]}****{val[-4:]}"

    def is_available(self, now: datetime | None = None) -> bool:
        """Check if key is ready for requests."""
        current_time = now or datetime.now(UTC)
        if self.status == KeyStatus.ACTIVE:
            return True
        if self.status == KeyStatus.COOLDOWN and self.cooldown_until is not None:
            return current_time >= self.cooldown_until
        return False


class KeyPoolManager:
    """Thread-safe key pool supporting multi-key rotation and automatic failover."""

    def __init__(
        self,
        keys: Sequence[ManagedKey] | None = None,
        policy: RotationPolicy = RotationPolicy.PRIORITY_FAILOVER,
        default_cooldown_seconds: float = 60.0,
    ) -> None:
        self.policy = policy
        self.default_cooldown_seconds = default_cooldown_seconds
        self._keys: list[ManagedKey] = list(keys or [])
        self._round_robin_index: dict[ProviderType, int] = {}

    @property
    def keys(self) -> list[ManagedKey]:
        return self._keys

    def add_key(
        self,
        secret_value: str,
        provider: ProviderType,
        key_id: str | None = None,
        priority: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> ManagedKey:
        """Register a new key into the managed pool."""
        clean_secret = secret_value.strip()
        if not clean_secret:
            raise ValueError("API key secret cannot be empty")
        generated_id = key_id or f"{provider.value.lower()}_{len(self._keys) + 1:02d}"
        key = ManagedKey(
            key_id=generated_id,
            provider=provider,
            secret_value=clean_secret,
            priority=priority,
            metadata=metadata or {},
        )
        self._keys.append(key)
        return key

    def load_from_env(self) -> None:
        """Auto-discover and load single or comma-separated API keys from environment."""
        env_mappings = [
            ("OPENROUTER_API_KEY", "OPENROUTER_API_KEYS", ProviderType.OPENROUTER),
            ("GROQ_API_KEY", "GROQ_API_KEYS", ProviderType.GROQ),
            ("OPENAI_API_KEY", "OPENAI_API_KEYS", ProviderType.OPENAI),
            ("ANTHROPIC_API_KEY", "ANTHROPIC_API_KEYS", ProviderType.ANTHROPIC),
            ("GEMINI_API_KEY", "GEMINI_API_KEYS", ProviderType.GEMINI),
            ("DEEPSEEK_API_KEY", "DEEPSEEK_API_KEYS", ProviderType.DEEPSEEK),
            ("MISTRAL_API_KEY", "MISTRAL_API_KEYS", ProviderType.MISTRAL),
        ]
        for single_var, multi_var, provider in env_mappings:
            raw_keys: list[str] = []
            single_val = os.getenv(single_var, "").strip()
            if single_val:
                raw_keys.append(single_val)
            multi_val = os.getenv(multi_var, "").strip()
            if multi_val:
                raw_keys.extend([k.strip() for k in multi_val.split(",") if k.strip()])

            # De-duplicate while preserving order
            seen: set[str] = {k.secret_value for k in self._keys if k.provider == provider}
            for i, raw_k in enumerate(raw_keys, start=1):
                if raw_k not in seen:
                    self.add_key(
                        secret_value=raw_k,
                        provider=provider,
                        key_id=f"{provider.value.lower()}_env_{i:02d}",
                        priority=i,
                    )
                    seen.add(raw_k)

    def get_active_key(
        self,
        provider: ProviderType | None = None,
        now: datetime | None = None,
    ) -> ManagedKey | None:
        """Retrieve an eligible active key according to the active rotation policy."""
        current_time = now or datetime.now(UTC)
        self.auto_recover_cooldowns(current_time)

        candidate_keys = [
            k
            for k in self._keys
            if (provider is None or k.provider == provider) and k.is_available(current_time)
        ]
        if not candidate_keys:
            return None

        if self.policy == RotationPolicy.PRIORITY_FAILOVER:
            # Sort primarily by priority (ascending), secondarily by failure count
            candidate_keys.sort(key=lambda k: (k.priority, k.failed_requests))
            selected = candidate_keys[0]
        else:  # ROUND_ROBIN
            p_key = provider or ProviderType.OPENROUTER
            idx = self._round_robin_index.get(p_key, 0) % len(candidate_keys)
            selected = candidate_keys[idx]
            self._round_robin_index[p_key] = (idx + 1) % len(candidate_keys)

        selected.last_used_at = current_time
        selected.total_requests += 1
        return selected

    def record_success(self, key: ManagedKey) -> None:
        """Mark successful execution on a key."""
        key.status = KeyStatus.ACTIVE
        key.cooldown_until = None

    def record_rate_limit(
        self,
        key: ManagedKey,
        retry_after_seconds: float | None = None,
        now: datetime | None = None,
    ) -> None:
        """Trigger automatic failover by putting the rate-limited key into cooldown."""
        current_time = now or datetime.now(UTC)
        duration = retry_after_seconds or self.default_cooldown_seconds
        key.status = KeyStatus.COOLDOWN
        key.cooldown_until = current_time + timedelta(seconds=duration)
        key.rate_limit_count += 1
        key.failed_requests += 1
        logger.warning(
            f"Key {key.key_id} ({key.mask_key()}) rate-limited for {duration:.1f}s until {key.cooldown_until.isoformat()}"
        )

    def record_error(self, key: ManagedKey, is_fatal: bool = False) -> None:
        """Record a general error on a key."""
        key.failed_requests += 1
        if is_fatal:
            key.status = KeyStatus.INVALID

    def auto_recover_cooldowns(self, now: datetime | None = None) -> int:
        """Bring keys out of cooldown if their expiry timestamp has elapsed."""
        current_time = now or datetime.now(UTC)
        recovered = 0
        for k in self._keys:
            if k.status == KeyStatus.COOLDOWN and k.cooldown_until is not None:
                if current_time >= k.cooldown_until:
                    k.status = KeyStatus.ACTIVE
                    k.cooldown_until = None
                    recovered += 1
        return recovered

    def get_pool_status(self) -> list[dict[str, Any]]:
        """Return human-readable metadata for user-facing UI / dashboards."""
        return [
            {
                "key_id": k.key_id,
                "provider": k.provider.value,
                "masked_key": k.mask_key(),
                "status": k.status.value,
                "priority": k.priority,
                "total_requests": k.total_requests,
                "rate_limit_count": k.rate_limit_count,
                "cooldown_remaining_seconds": (
                    max(0.0, (k.cooldown_until - datetime.now(UTC)).total_seconds())
                    if k.cooldown_until
                    else 0.0
                ),
            }
            for k in self._keys
        ]
