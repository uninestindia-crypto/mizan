"""Pydantic schemas for the Halal Investment platform."""

from .academy import (
    AcademyModuleDetail,
    AcademyModuleSummary,
    BrokerDematGuide,
    DematGuideResponse,
    DematMandatoryRule,
    QuizQuestion,
)
from .company import (
    BalanceSheetEvidence,
    CompanyDetail,
    CompanyProfile,
    CompanySummary,
    ComplianceStatus,
    IncomeStatementEvidence,
    MarketCapCategory,
    ScreeningStandard,
    SearchSuggestion,
)
from .screening import (
    AuditEvidenceLine,
    RatioMeter,
    ScreeningResponse,
    ShariahAuditResponse,
    StandardEvaluation,
)
from .zakat import (
    ZakatCalculateRequest,
    ZakatCalculateResponse,
    ZakatCalendar,
    ZakatHoldingBreakdown,
    ZakatHoldingItem,
    ZakatMethod,
)

__all__ = [
    "ComplianceStatus",
    "ScreeningStandard",
    "MarketCapCategory",
    "BalanceSheetEvidence",
    "IncomeStatementEvidence",
    "CompanyProfile",
    "CompanySummary",
    "CompanyDetail",
    "SearchSuggestion",
    "RatioMeter",
    "StandardEvaluation",
    "AuditEvidenceLine",
    "ShariahAuditResponse",
    "ScreeningResponse",
    "ZakatMethod",
    "ZakatCalendar",
    "ZakatHoldingItem",
    "ZakatHoldingBreakdown",
    "ZakatCalculateRequest",
    "ZakatCalculateResponse",
    "QuizQuestion",
    "AcademyModuleSummary",
    "AcademyModuleDetail",
    "DematMandatoryRule",
    "BrokerDematGuide",
    "DematGuideResponse",
]
