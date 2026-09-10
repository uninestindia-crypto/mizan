"""Amazon Bedrock transport for the two frontier audit models.

This module reaches OpenAI **GPT-6 Astra** and Anthropic **Claude Fable 5.1** through a single
Amazon Bedrock account, so one AWS credential and one bill cover both halves of a dual-model audit.
It is an *analysis* transport only: nothing here trains, promotes, or executes anything, and no
caller of this module can place an order.

Both model identifiers, both endpoint shapes, and every constraint encoded below were read from the
AWS Bedrock model cards on 2026-09-10 rather than recalled:

- ``docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-6-astra.html``
- ``docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-fable-5-1.html``

Four properties of that pairing drive the design and are easy to get wrong:

1. **Cross-region inference is mandatory.** Neither model supports In-Region inference on the
   ``bedrock-runtime`` endpoint, so the bare ids ``openai.gpt-6-astra`` and
   ``anthropic.claude-fable-5-1`` are never sent. Every request names a ``global.`` or ``us.``
   inference profile.
2. **The two models speak different dialects on the same host.** GPT-6 Astra is served at
   ``/openai/v1`` and answers the OpenAI Chat Completions shape; Fable 5.1 is served at
   ``/anthropic`` and answers the Anthropic Messages shape. Each gets its own official SDK pointed at
   its own path — never one SDK with a compatibility shim over the other.
3. **Refusal is a normal response, not an exception.** The Fable 5.1 card states refusal rates are
   materially higher than previous Claude models, and a refusal arrives as HTTP 200 with
   ``stop_reason="refusal"``. The server-side ``fallbacks`` rescue does **not** exist on Bedrock, so
   a refusal here is terminal and is reported as such instead of being mistaken for an empty answer.
4. **Fable 5.1 rejects sampling parameters.** Temperature must be 1.0 or unset, ``top_p`` 0.99 or
   unset, never both together, and ``top_k`` is unsupported. This module sends none of them, which is
   the only shape that cannot violate the rule.

Credentials are read from the environment and never logged, echoed, or written to disk.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

if TYPE_CHECKING:
    from openai import Stream
    from openai.types.chat import ChatCompletionChunk, ChatCompletionMessageParam

__all__ = [
    "BedrockAuditConfig",
    "BedrockCredentialsMissing",
    "ModelReply",
    "call_claude_fable",
    "call_gpt6_astra",
]

# Base model ids. Never sent directly: Bedrock requires a cross-region inference profile for both.
_GPT6_BASE_ID: Final = "openai.gpt-6-astra"
_FABLE_BASE_ID: Final = "anthropic.claude-fable-5-1"

#: Environment variable holding a long-term Amazon Bedrock API key.
TOKEN_ENV_VAR: Final = "AWS_BEARER_TOKEN_BEDROCK"

#: Names this module may pull from a local ``.env``. Deliberately narrow: a runner that only needs
#: Bedrock has no business widening the exposure of the broker or provider keys sitting beside it.
ENV_NAMES: Final[tuple[str, ...]] = (
    TOKEN_ENV_VAR,
    "QUANTOS_BEDROCK_REGION",
    "QUANTOS_BEDROCK_SCOPE",
)

BedrockScope = Literal["global", "us"]
EffortLevel = Literal["low", "medium", "high", "xhigh", "max"]

_DEFAULT_REGION: Final = "ap-south-1"
_DEFAULT_SCOPE: Final[BedrockScope] = "global"

# Regions where the US geo profile is offered for both models. Outside these, only global routes.
_US_GEO_REGIONS: Final[frozenset[str]] = frozenset(
    {"us-east-1", "us-east-2", "us-west-1", "us-west-2", "ca-central-1"}
)


class BedrockCredentialsMissing(RuntimeError):
    """Raised when no Amazon Bedrock API key is available in the environment."""


@dataclass(frozen=True, slots=True)
class ModelReply:
    """One completed model turn, with the accounting needed to audit what it cost.

    ``refusal_category`` is populated only when the model declined the request. When it is set,
    ``text`` is not a report and must not be written out as though it were one.
    """

    model: str
    text: str
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    elapsed_seconds: float
    refusal_category: str | None = None

    @property
    def refused(self) -> bool:
        """True when the model declined rather than answered."""
        return self.refusal_category is not None


@dataclass(frozen=True, slots=True)
class BedrockAuditConfig:
    """Resolved Bedrock endpoint settings shared by both models."""

    region: str
    scope: BedrockScope
    token: str

    @classmethod
    def from_env(cls) -> BedrockAuditConfig:
        """Build a config from the process environment.

        Raises:
            BedrockCredentialsMissing: when no Bedrock API key is set.
            ValueError: when ``QUANTOS_BEDROCK_SCOPE`` is set to something other than
                ``global`` or ``us``.
        """
        token = os.getenv(TOKEN_ENV_VAR, "").strip()
        if not token:
            raise BedrockCredentialsMissing(
                f"{TOKEN_ENV_VAR} is not set. Create a long-term API key in the Amazon Bedrock "
                "console (Bedrock -> API keys -> long-term), then put it in .env as "
                f"{TOKEN_ENV_VAR}=<key>. See docs/bedrock-dual-model-setup.md."
            )

        region = os.getenv("QUANTOS_BEDROCK_REGION", "").strip() or _DEFAULT_REGION
        raw_scope = os.getenv("QUANTOS_BEDROCK_SCOPE", "").strip().lower() or _DEFAULT_SCOPE
        if raw_scope not in ("global", "us"):
            raise ValueError(
                f"QUANTOS_BEDROCK_SCOPE must be 'global' or 'us', got {raw_scope!r}. "
                "'global' routes worldwide; 'us' keeps inference inside the US geography."
            )
        scope: BedrockScope = "us" if raw_scope == "us" else "global"

        if scope == "us" and region not in _US_GEO_REGIONS:
            raise ValueError(
                f"Region {region!r} does not offer the US geo inference profile for these models. "
                f"Either set QUANTOS_BEDROCK_REGION to one of {sorted(_US_GEO_REGIONS)}, "
                "or use QUANTOS_BEDROCK_SCOPE=global."
            )
        return cls(region=region, scope=scope, token=token)

    @property
    def gpt6_model_id(self) -> str:
        """Cross-region inference profile id for GPT-6 Astra."""
        return f"{self.scope}.{_GPT6_BASE_ID}"

    @property
    def fable_model_id(self) -> str:
        """Cross-region inference profile id for Claude Fable 5.1."""
        return f"{self.scope}.{_FABLE_BASE_ID}"

    @property
    def openai_base_url(self) -> str:
        """Bedrock's OpenAI-dialect base URL, which serves GPT-6 Astra."""
        return f"https://bedrock-runtime.{self.region}.amazonaws.com/openai/v1"

    @property
    def anthropic_base_url(self) -> str:
        """Bedrock's Anthropic-dialect base URL, which serves Claude Fable 5.1."""
        return f"https://bedrock-runtime.{self.region}.amazonaws.com/anthropic"

    def describe(self) -> str:
        """Human-readable summary safe to log. Never includes the token."""
        residency = (
            "routes worldwide, no data-residency guarantee"
            if self.scope == "global"
            else "inference stays inside the US geography"
        )
        return f"region={self.region} scope={self.scope} ({residency})"


def _emit(on_event: Callable[[str], None] | None, message: str) -> None:
    """Send a progress line to the caller's logger, if it supplied one."""
    if on_event is not None:
        on_event(message)


def call_gpt6_astra(
    config: BedrockAuditConfig,
    *,
    system_prompt: str,
    user_prompt: str,
    max_output_tokens: int = 32000,
    effort: EffortLevel = "high",
    timeout_seconds: float = 3600.0,
    on_event: Callable[[str], None] | None = None,
) -> ModelReply:
    """Run one GPT-6 Astra turn on Bedrock and return the assembled reply.

    Streams the response. GPT-6 Astra is a reasoning model whose hard turns run for many minutes, and
    a non-streaming call of that length is liable to hit an HTTP timeout before the model finishes.

    Args:
        config: Resolved Bedrock endpoint settings.
        system_prompt: The auditor role instruction.
        user_prompt: The dossier and the audit question.
        max_output_tokens: Ceiling on generated tokens. The model card allows up to 128,000.
        effort: Reasoning depth. Higher costs more and thinks longer.
        timeout_seconds: Client-side ceiling for the whole streamed turn.
        on_event: Optional progress callback.

    Returns:
        The assembled reply with token accounting.
    """
    from openai import BadRequestError, OpenAI

    client = OpenAI(
        base_url=config.openai_base_url,
        api_key=config.token,
        timeout=timeout_seconds,
        max_retries=2,
    )
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    def _open_stream(include_effort: bool) -> Stream[ChatCompletionChunk]:
        """Open the streamed completion, with or without the reasoning knob.

        Written as two explicit calls rather than one splatted kwargs dict so the SDK's overloads
        resolve statically and a wrong parameter is caught by the type checker, not at runtime.
        """
        if include_effort:
            return client.chat.completions.create(
                model=config.gpt6_model_id,
                messages=messages,
                max_completion_tokens=max_output_tokens,
                stream=True,
                stream_options={"include_usage": True},
                reasoning_effort=effort,
            )
        return client.chat.completions.create(
            model=config.gpt6_model_id,
            messages=messages,
            max_completion_tokens=max_output_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )

    def _run(include_effort: bool) -> ModelReply:
        started = time.monotonic()
        chunks: list[str] = []
        prompt_tokens = 0
        completion_tokens = 0
        reasoning_tokens = 0
        for event in _open_stream(include_effort):
            if event.usage is not None:
                prompt_tokens = event.usage.prompt_tokens
                completion_tokens = event.usage.completion_tokens
                details = getattr(event.usage, "completion_tokens_details", None)
                reasoning_tokens = int(getattr(details, "reasoning_tokens", 0) or 0)
            if not event.choices:
                continue
            piece = event.choices[0].delta.content
            if piece:
                chunks.append(piece)

        return ModelReply(
            model=config.gpt6_model_id,
            text="".join(chunks).strip(),
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            reasoning_tokens=reasoning_tokens,
            elapsed_seconds=time.monotonic() - started,
        )

    _emit(on_event, f"Calling {config.gpt6_model_id} (effort={effort}, streaming)...")
    try:
        return _run(include_effort=True)
    except BadRequestError as exc:
        # Narrow, deliberate downgrade: retry without the reasoning knob only when that specific
        # parameter is what the endpoint rejected. Every other 400 is a real error and propagates.
        if "reasoning_effort" not in str(exc):
            raise
        _emit(on_event, "Endpoint rejected reasoning_effort; retrying at the model default.")
        return _run(include_effort=False)


def call_claude_fable(
    config: BedrockAuditConfig,
    *,
    system_prompt: str,
    user_prompt: str,
    max_output_tokens: int = 32000,
    effort: EffortLevel = "high",
    timeout_seconds: float = 3600.0,
    on_event: Callable[[str], None] | None = None,
) -> ModelReply:
    """Run one Claude Fable 5.1 turn on Bedrock and return the assembled reply.

    Streams the response. Fable 5.1 runs adaptive thinking that cannot be disabled, so a single
    demanding turn can run for many minutes; streaming is what keeps that from timing out.

    No ``thinking`` parameter is sent. Thinking is always on for this model and any explicit
    configuration of it is rejected with a 400. Depth is controlled through ``effort`` instead.

    A refusal is returned, not raised: the reply carries ``refusal_category`` and the caller decides
    what to do. Bedrock has no server-side fallback, so there is nothing to retry onto here.

    Args:
        config: Resolved Bedrock endpoint settings.
        system_prompt: The auditor role instruction.
        user_prompt: The dossier, the first opinion, and the audit question.
        max_output_tokens: Ceiling on generated tokens. The model card allows up to 128,000.
        effort: Reasoning depth. Higher costs more and thinks longer.
        timeout_seconds: Client-side ceiling for the whole streamed turn.
        on_event: Optional progress callback.

    Returns:
        The assembled reply with token accounting, or a refusal.
    """
    from anthropic import Anthropic

    client = Anthropic(
        base_url=config.anthropic_base_url,
        api_key=config.token,
        timeout=timeout_seconds,
        max_retries=2,
    )

    _emit(on_event, f"Calling {config.fable_model_id} (effort={effort}, streaming)...")
    started = time.monotonic()
    with client.messages.stream(
        model=config.fable_model_id,
        max_tokens=max_output_tokens,
        system=system_prompt,
        output_config={"effort": effort},
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        final = stream.get_final_message()
    elapsed = time.monotonic() - started

    text = "".join(block.text for block in final.content if block.type == "text").strip()

    refusal_category: str | None = None
    if final.stop_reason == "refusal":
        details = final.stop_details
        category = getattr(details, "category", None) if details is not None else None
        refusal_category = str(category) if category else "unspecified"

    return ModelReply(
        model=config.fable_model_id,
        text=text,
        input_tokens=final.usage.input_tokens,
        output_tokens=final.usage.output_tokens,
        reasoning_tokens=0,  # Bedrock bills thinking inside output_tokens; it is not itemised.
        elapsed_seconds=elapsed,
        refusal_category=refusal_category,
    )
