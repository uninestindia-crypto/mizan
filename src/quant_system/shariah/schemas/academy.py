"""Pydantic schemas for the Halal Wealth Academy & Demat Onboarding Guides (R6)."""

from pydantic import BaseModel, Field


class QuizQuestion(BaseModel):
    id: str
    question: str
    options: list[str]
    correct_index: int = Field(..., ge=0, le=3)
    explanation: str


class AcademyModuleSummary(BaseModel):
    id: str
    title: str
    subtitle: str
    icon: str
    reading_time_minutes: int
    key_takeaways_count: int
    quiz_questions_count: int


class AcademyModuleDetail(BaseModel):
    id: str
    title: str
    subtitle: str
    icon: str
    reading_time_minutes: int
    markdown_content: str
    key_takeaways: list[str]
    quiz_questions: list[QuizQuestion]


class DematMandatoryRule(BaseModel):
    rule_id: str
    rule_text: str
    is_mandatory: bool = True
    shariah_rationale: str


class BrokerDematGuide(BaseModel):
    broker_id: str
    broker_name: str
    tagline: str
    account_type: str
    product_mode: str  # e.g. "CNC" or "DELIVERY"
    margin_mtf: str  # e.g. "DISABLED"
    slbm_status: str  # e.g. "INACTIVE"
    derivatives_fo: str  # e.g. "DISABLED"
    mandatory_rules: list[str]
    setup_steps: list[str]
    critical_warnings: list[str]
    verification_checklist: list[str]


class DematGuideResponse(BaseModel):
    universal_rules: list[DematMandatoryRule]
    brokers: list[BrokerDematGuide]
