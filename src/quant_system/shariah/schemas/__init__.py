"""Pydantic schemas for the Halal Investment platform."""

from .company import (
    ComplianceStatus,
    ScreeningStandard,
    MarketCapCategory,
    BalanceSheetEvidence,
    IncomeStatementEvidence,
    CompanyProfile,
    CompanySummary,
    CompanyDetail,
    SearchSuggestion,
)
from .screening import (
    RatioMeter,
    StandardEvaluation,
    AuditEvidenceLine,
    ShariahAuditResponse,
    ScreeningResponse,
)
from .zakat import (
    ZakatMethod,
    ZakatCalendar,
    ZakatHoldingItem,
    ZakatHoldingBreakdown,
    ZakatCalculateRequest,
    ZakatCalculateResponse,
)
from .academy import (
    QuizQuestion,
    AcademyModuleSummary,
    AcademyModuleDetail,
    DematMandatoryRule,
    BrokerDematGuide,
    DematGuideResponse,
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
