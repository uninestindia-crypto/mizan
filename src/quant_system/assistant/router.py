"""FastAPI Router for In-Platform Actionable AI Assistant (/api/v1/assistant)."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException

from quant_system.alpha.key_pool import ProviderType
from quant_system.assistant.actions import PlatformActionExecutor
from quant_system.assistant.schemas import (
    ActionExecutionRequest,
    ActionExecutionResult,
    AssistantCapabilitiesResponse,
    AssistantChatRequest,
    AssistantChatResponse,
    PlatformActionType,
)
from quant_system.assistant.service import PlatformAssistantService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/assistant", tags=["Assistant"])
_service = PlatformAssistantService()


@router.post("/chat", response_model=AssistantChatResponse)
def assistant_chat(
    request: AssistantChatRequest,
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> AssistantChatResponse:
    """Processes a conversational prompt and returns answers and action proposals."""
    return _service.process_chat(request)


@router.post("/execute-action", response_model=ActionExecutionResult)
def execute_platform_action(
    request: ActionExecutionRequest,
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> ActionExecutionResult:
    """Executes a safe in-platform action (Navigation, Greeks, Diagnostics, Risk Limits)."""
    # Verify CSRF token on mutating actions if required
    if request.action_type in {PlatformActionType.EXECUTE_BACKTEST}:
        from quant_system.server.security import csrf_manager

        if not x_csrf_token or not csrf_manager.validate_token(x_csrf_token):
            raise HTTPException(
                status_code=403, detail="Invalid or missing CSRF token for action execution"
            )

    return PlatformActionExecutor.execute(request)


@router.get("/capabilities", response_model=AssistantCapabilitiesResponse)
def get_assistant_capabilities() -> AssistantCapabilitiesResponse:
    """Returns declared capabilities and safety boundaries of the QuantOS Copilot."""
    available_providers = [p.value for p in ProviderType]
    return AssistantCapabilitiesResponse(
        name="QuantOS Copilot",
        version="1.0.0",
        codebase_modifications_allowed=False,
        supported_actions=list(PlatformActionType),
        available_providers=available_providers,
    )
