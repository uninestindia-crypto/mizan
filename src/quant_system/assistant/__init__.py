"""In-Platform Actionable AI Assistant package."""

from quant_system.assistant.actions import PlatformActionExecutor
from quant_system.assistant.router import router as assistant_router
from quant_system.assistant.schemas import (
    ActionExecutionRequest,
    ActionExecutionResult,
    ActionProposal,
    AssistantCapabilitiesResponse,
    AssistantChatRequest,
    AssistantChatResponse,
    PlatformActionType,
)
from quant_system.assistant.service import PlatformAssistantService

__all__ = [
    "ActionExecutionRequest",
    "ActionExecutionResult",
    "ActionProposal",
    "AssistantCapabilitiesResponse",
    "AssistantChatRequest",
    "AssistantChatResponse",
    "PlatformActionExecutor",
    "PlatformActionType",
    "PlatformAssistantService",
    "assistant_router",
]
