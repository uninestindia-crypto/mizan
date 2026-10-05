from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class ComplianceStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    QUESTIONABLE = "QUESTIONABLE"


class ScreeningStandard(str, Enum):
    AAOIFI = "AAOIFI"
    TASIS = "TASIS"
    BOTH = "BOTH"


class MarketCapCategory(str, Enum):
    LARGE = "LARGE"
    MID = "MID"
    SMALL = "SMALL"


class BalanceSheetEvidence(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    total_assets: float = Field(..., description="Total Assets in INR Crores (TASIS denominator)")
    long_term_debt: float = Field(default=0.0, description="Long-Term Borrowings in INR Crores")
    short_term_debt: float = Field(default=0.0, description="Short-Term Borrowings in INR Crores")
    lease_liabilities: float = Field(default=0.0, description="Ind AS 116 Lease Liabilities in INR Crores")
    total_debt: float = Field(..., description="Total Interest-Bearing Debt in INR Crores")
    cash_and_bank: float = Field(..., description="Cash and Bank Balances in INR Crores")
    current_investments: float = Field(default=0.0, description="Current Debt/Mutual Fund Investments in INR Crores")
    total_cash_and_investments: float = Field(..., description="Liquid Cash and Interest-Bearing Assets in INR Crores")
    total_receivables: float = Field(..., description="Trade and Bills Receivable in INR Crores")
    total_inventories: float = Field(default=0.0, description="Inventories in INR Crores")
    current_liabilities: float = Field(..., description="Current Liabilities in INR Crores")
    
    debt_note_ref: Optional[str] = Field(default=None, description="Note reference for debt in annual report")
    cash_note_ref: Optional[str] = Field(default=None, description="Note reference for cash in annual report")
    rec_note_ref: Optional[str] = Field(default=None, description="Note reference for receivables in annual report")


class IncomeStatementEvidence(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    operating_revenue: float = Field(..., description="Revenue from Operations in INR Crores")
    other_income: float = Field(default=0.0, description="Other Income in INR Crores")
    total_revenue: float = Field(..., description="Total Revenue in INR Crores (Operating + Other)")
    interest_income: float = Field(default=0.0, description="Non-Operating Interest Income in INR Crores")
    prohibited_secondary_revenue: float = Field(default=0.0, description="Prohibited Segment Revenue in INR Crores")
    total_impermissible_income: float = Field(..., description="Total Impermissible / Tainted Income in INR Crores")
    
    income_note_ref: Optional[str] = Field(default=None, description="Note reference for income in annual report")


class CompanySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    ticker: str
    symbol: str
    isin: str
    bse_code: Optional[str] = None
    company_name: str
    sector: str
    industry: str
    current_price: float
    market_cap: float
    avg_36m_market_cap: float
    aaoifi_status: ComplianceStatus
    tasis_status: ComplianceStatus
    purification_ratio: float
    is_nifty_50: bool = False
    is_nifty_500: bool = True
    aaoifi_debt_ratio: Optional[float] = None
    aaoifi_cash_ratio: Optional[float] = None
    tasis_debt_ratio: Optional[float] = None
    tasis_cash_ratio: Optional[float] = None


class SearchSuggestion(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    ticker: str
    symbol: str
    company_name: str
    isin: str
    sector: str
    industry: str
    current_price: float
    aaoifi_status: ComplianceStatus
    tasis_status: ComplianceStatus


class CompanyProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    ticker: str
    symbol: str
    isin: str
    bse_code: Optional[str] = None
    company_name: str
    sector: str
    industry: str
    business_summary: Optional[str] = None
    
    current_price: float
    market_cap: float
    avg_36m_market_cap: float
    shares_outstanding: int
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    last_dividend_per_share: Optional[float] = 0.0
    
    filing_date: str
    reporting_period: str
    source_document: Optional[str] = None
    is_nifty_50: bool = False
    is_nifty_500: bool = True


class CompanyDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    profile: CompanyProfile
    balance_sheet: BalanceSheetEvidence
    income_statement: IncomeStatementEvidence
    
    sector_compliant: bool
    sector_failure_reason: Optional[str] = None
    
    aaoifi_status: ComplianceStatus
    aaoifi_debt_ratio: float
    aaoifi_cash_ratio: float
    aaoifi_rec_ratio: float
    aaoifi_imp_ratio: float
    
    tasis_status: ComplianceStatus
    tasis_debt_ratio: float
    tasis_cash_ratio: float
    tasis_rec_ratio: float
    tasis_imp_ratio: float
    
    purification_ratio: float
    zakatable_assets_per_share: float
    audit_notes: Optional[str] = None
