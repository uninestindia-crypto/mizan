from pydantic import BaseModel, Field


class PurificationCalculateRequest(BaseModel):
    ticker: str = Field(..., description="Equity ticker (e.g. TCS.NS or TCS)")
    dividend_amount: float = Field(
        ..., gt=0.0, description="Declared Dividend Per Share (DPS) or total dividend amount"
    )
    shares_held: int = Field(default=1, gt=0, description="Quantity of shares held in portfolio")


class PurificationCalculateResponse(BaseModel):
    ticker: str
    shares_held: int
    dividend_per_share: float
    gross_dividend: float
    purification_ratio: float
    purification_ratio_pct: float
    purification_payable: float
    net_permissible_dividend: float


class PurificationLedgerCreate(BaseModel):
    ticker: str = Field(..., description="Equity ticker (e.g. TCS.NS or TCS)")
    shares_held: int = Field(..., gt=0, description="Quantity of shares held")
    dps: float = Field(..., gt=0.0, description="Dividend per share in INR")
    gross_dividend: float | None = Field(
        default=None, description="Optional gross dividend amount; computed if omitted"
    )
    charity_name: str | None = Field(default=None, description="Beneficiary charity / NGO name")
    disbursement_status: str | None = Field(
        default="UNPURIFIED", description="UNPURIFIED, PURIFIED, or DONATED"
    )
    notes: str | None = Field(default=None, description="Optional audit notes or receipt reference")
    record_date: str | None = None
    payment_date: str | None = None


class PurificationLedgerEntry(BaseModel):
    id: int
    entry_uuid: str
    ticker: str
    company_name: str
    record_date: str | None = None
    payment_date: str | None = None
    shares_held: int
    dps_inr: float
    gross_dividend: float
    purification_ratio: float
    purification_payable: float
    net_permissible_dividend: float
    charity_name: str | None = None
    disbursement_status: str
    notes: str | None = None
    prev_entry_hash: str
    entry_hash: str
    timestamp: str | None = None
    hash_version: int = Field(
        default=1,
        description="Which hash rule protects this row: 1 covers the id and amount, 2 covers six figures",
    )


class PurificationLedgerListResponse(BaseModel):
    total_entries: int
    is_chain_valid: bool
    latest_entry_hash: str
    items: list[PurificationLedgerEntry]


class PurificationReceipt(BaseModel):
    certificate_id: str
    ticker: str
    company_name: str
    gross_dividend_inr: float
    purification_ratio_pct: float
    purification_payable_inr: float
    net_permissible_inr: float
    verification_hash: str
    prev_hash: str
    charity_name: str | None = None
    disbursement_status: str
    timestamp: str
    hash_version: int = 1
    charity_disclaimer: str
    printable_receipt: str
