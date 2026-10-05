from pydantic import BaseModel, ConfigDict, Field

from .company import ComplianceStatus, ScreeningStandard


class RatioMeter(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metric_name: str
    actual_value: float = Field(..., description="Decimal ratio value (e.g. 0.058)")
    actual_pct: float = Field(..., description="Percentage value (e.g. 5.80)")
    threshold_pct: float = Field(
        ..., description="Strict upper limit threshold (e.g. 33.00 or 5.00)"
    )
    is_compliant: bool = Field(..., description="True if strictly < threshold")
    is_warning: bool = Field(default=False, description="True if within the 1% warning zone")
    numerator_label: str
    numerator_value_inr_cr: float
    denominator_label: str
    denominator_value_inr_cr: float
    note_reference: str | None = None


class StandardEvaluation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    standard: ScreeningStandard
    status: ComplianceStatus
    is_compliant: bool
    debt_ratio: RatioMeter
    cash_ratio: RatioMeter
    receivables_ratio: RatioMeter
    impermissible_income_ratio: RatioMeter
    summary: str


class AuditEvidenceLine(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_item: str
    value_inr_cr: float
    note_ref: str | None = None
    filing_schedule: str | None = None
    verification_status: str = "VERIFIED"


class ShariahAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    symbol: str
    company_name: str
    isin: str
    filing_date: str
    reporting_period: str
    source_document: str | None = None
    sector: str
    sector_compliant: bool
    sector_failure_reason: str | None = None

    aaoifi_evaluation: StandardEvaluation
    tasis_evaluation: StandardEvaluation
    divergence_noted: bool
    divergence_explanation: str | None = None

    purification_ratio_pct: float
    zakatable_assets_per_share_inr: float

    balance_sheet_lines: list[AuditEvidenceLine]
    income_statement_lines: list[AuditEvidenceLine]
    audit_notes: str | None = None


class ScreeningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    symbol: str
    company_name: str
    sector: str
    standard_requested: str
    overall_status: ComplianceStatus

    aaoifi_evaluation: StandardEvaluation
    tasis_evaluation: StandardEvaluation
    divergence: bool
    divergence_reason: str | None = None
    purification_ratio: float
