"""FastAPI endpoints for Halal Wealth Academy Curriculum & Demat Guides (R6)."""

from fastapi import APIRouter, HTTPException, Path

from quant_system.shariah.schemas.academy import (
    AcademyModuleDetail,
    BrokerDematGuide,
    DematGuideResponse,
)
from quant_system.shariah.services.academy_service import (
    get_all_modules,
    get_broker_guide,
    get_demat_onboarding_guide,
    get_module_by_id,
)

router = APIRouter(prefix="/academy", tags=["Halal Wealth Academy & Demat Guides"])


@router.get(
    "/modules",
    response_model=list[AcademyModuleDetail],
    summary="List Wealth Academy Curriculum Modules",
    description="Returns the 4 core interactive educational modules with full lesson markdown, takeaways, and quiz questions.",
)
async def list_modules() -> list[AcademyModuleDetail]:
    return get_all_modules()


@router.get(
    "/modules/{module_id}",
    response_model=AcademyModuleDetail,
    summary="Get Detailed Module Content & Quiz",
    description="Returns lesson content and quiz questions for a single educational module.",
)
async def get_module(
    module_id: str = Path(..., description="Unique module slug (e.g. stewardship-and-inflation)"),
) -> AcademyModuleDetail:
    module = get_module_by_id(module_id)
    if not module:
        raise HTTPException(
            status_code=404,
            detail=f"Module '{module_id}' not found. Available modules: stewardship-and-inflation, islamic-architecture-equities, financial-evils-riba-gharar-maysir, ten-principles-disciplined-investor.",
        )
    return module


@router.get(
    "/demat-guide",
    response_model=DematGuideResponse,
    summary="Get Non-Margin Demat Onboarding Guides",
    description="Returns universal Shariah Demat rules and dedicated setup walkthroughs for Zerodha, Groww, Upstox, and AngelOne.",
)
async def get_demat_guide() -> DematGuideResponse:
    return get_demat_onboarding_guide()


@router.get(
    "/demat-guide/{broker_id}",
    response_model=BrokerDematGuide,
    summary="Get Broker-Specific Demat Setup Guide",
    description="Returns step-by-step setup, MTF deactivation instructions, and SLBM checks for a specific broker.",
)
async def get_single_broker_guide(
    broker_id: str = Path(
        ..., description="Broker identifier: zerodha, groww, upstox, or angelone"
    ),
) -> BrokerDematGuide:
    guide = get_broker_guide(broker_id)
    if not guide:
        raise HTTPException(
            status_code=404,
            detail=f"Broker guide for '{broker_id}' not found. Supported brokers: zerodha, groww, upstox, angelone.",
        )
    return guide
