"""Data Transfer Objects and Schemas for In-Platform Actionable AI Assistant."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlatformActionType(StrEnum):
    """Supported in-platform action primitives."""

    NAVIGATE_TAB = "NAVIGATE_TAB"
    RUN_DIAGNOSTICS = "RUN_DIAGNOSTICS"
    INSPECT_RISK_LIMITS = "INSPECT_RISK_LIMITS"
    CALCULATE_GREEKS = "CALCULATE_GREEKS"
    PREVIEW_BACKTEST = "PREVIEW_BACKTEST"
    EXECUTE_BACKTEST = "EXECUTE_BACKTEST"
    LIST_DATASETS = "LIST_DATASETS"
    EXPLAIN_METRIC = "EXPLAIN_METRIC"
    AUDIT_MODEL_STRATEGY = "AUDIT_MODEL_STRATEGY"


class ActionProposal(BaseModel):
    """A proposed platform action presented to the user with 1-click execution."""

    model_config = ConfigDict(frozen=True)

    action_id: str = Field(description="Unique ID for this proposed action")
    action_type: PlatformActionType = Field(description="Type of platform action")
    title: str = Field(description="Display title for the action button")
    description: str = Field(description="Short human-readable summary of what will happen")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Action arguments")
    requires_confirmation: bool = Field(
        default=False, description="True if action mutates state and needs confirmation"
    )
    target_tab: str | None = Field(default=None, description="UI Tab ID to switch to")


class ActionExecutionRequest(BaseModel):
    """Request to execute a specific in-platform action."""

    model_config = ConfigDict(frozen=True)

    action_id: str
    action_type: PlatformActionType
    parameters: dict[str, Any] = Field(default_factory=dict)


class ActionExecutionResult(BaseModel):
    """Result of executing an in-platform action."""

    model_config = ConfigDict(frozen=True)

    action_id: str
    action_type: PlatformActionType
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    message: str
    navigate_to: str | None = None


class ChatMessageDTO(BaseModel):
    """A message in the assistant conversation stream."""

    model_config = ConfigDict(frozen=True)

    role: str = Field(description="Message author: user | assistant | system")
    content: str = Field(description="Markdown text content")
    action_proposals: list[ActionProposal] = Field(default_factory=list)
    action_result: ActionExecutionResult | None = None


class AssistantChatRequest(BaseModel):
    """Inbound query to the platform AI assistant."""

    model_config = ConfigDict(frozen=True)

    prompt: str = Field(min_length=1, max_length=4000)
    current_tab: str | None = Field(default="tab-ingestion")
    history: list[ChatMessageDTO] = Field(default_factory=list)


class AssistantChatResponse(BaseModel):
    """Response returned by the platform AI assistant."""

    model_config = ConfigDict(frozen=True)

    message: str
    action_proposals: list[ActionProposal] = Field(default_factory=list)
    suggested_prompts: list[str] = Field(default_factory=list)


class AssistantCapabilitiesResponse(BaseModel):
    """Declaration of assistant tool capabilities and safety guarantees."""

    model_config = ConfigDict(frozen=True)

    name: str = "QuantOS Copilot"
    version: str = "1.0.0"
    codebase_modifications_allowed: bool = False
    supported_actions: list[PlatformActionType]
    available_providers: list[str]
