from dataclasses import dataclass
from typing import Optional


@dataclass
class PurificationLedgerModel:
    id: Optional[int]
    entry_uuid: str
    ticker: str
    company_name: str
    record_date: Optional[str]
    payment_date: Optional[str]
    shares_held: int
    dps_inr: float
    gross_dividend: float
    purification_ratio: float
    purification_payable: float
    net_permissible_dividend: float
    charity_name: Optional[str]
    disbursement_status: str
    notes: Optional[str]
    prev_entry_hash: str
    entry_hash: str
    timestamp: Optional[str] = None
