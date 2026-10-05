from dataclasses import dataclass


@dataclass
class PurificationLedgerModel:
    id: int | None
    entry_uuid: str
    ticker: str
    company_name: str
    record_date: str | None
    payment_date: str | None
    shares_held: int
    dps_inr: float
    gross_dividend: float
    purification_ratio: float
    purification_payable: float
    net_permissible_dividend: float
    charity_name: str | None
    disbursement_status: str
    notes: str | None
    prev_entry_hash: str
    entry_hash: str
    timestamp: str | None = None
