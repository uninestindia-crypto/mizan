"""Pydantic schemas for the Halal Wealth Academy & Demat Onboarding Guides (R6)."""

from typing import List, Optional
from pydantic import BaseModel, Field


class QuizQuestion(BaseModel):
    id: str
    question: str
    options: List[str]
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
    key_takeaways: List[str]
    quiz_questions: List[QuizQuestion]


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
    margin_mtf: str    # e.g. "DISABLED"
    slbm_status: str   # e.g. "INACTIVE"
    derivatives_fo: str  # e.g. "DISABLED"
    mandatory_rules: List[str]
    setup_steps: List[str]
    critical_warnings: List[str]
    verification_checklist: List[str]


class DematGuideResponse(BaseModel):
    universal_rules: List[DematMandatoryRule]
    brokers: List[BrokerDematGuide]
