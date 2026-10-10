"""What a verdict says about itself, built from the same row the verdict was computed from."""

from datetime import UTC, datetime
from typing import Any

from quant_system.shariah.schemas.company import DataStatus
from quant_system.shariah.schemas.screening import SectorRuleResult, TransparencyFields
from quant_system.shariah.services.sector_rules import explain_sector_compliance


def resolve_data_status(_company: dict[str, Any]) -> DataStatus:
    """Today every figure is a hand-entered sample, and no check exists that could earn a stronger label."""
    return DataStatus.UNVERIFIED_SAMPLE


def sector_rule_for(company: dict[str, Any]) -> SectorRuleResult:
    """Report the sector verdict the screening used, naming a rule only when the rules agree with it."""
    compliant = bool(company.get("sector_compliant", True))
    reason = None if compliant else company.get("sector_failure_reason")
    found = explain_sector_compliance(
        str(company.get("sector") or ""),
        str(company.get("industry") or ""),
        str(company.get("business_summary") or ""),
    )
    if compliant or found.compliant:
        return SectorRuleResult(compliant=compliant, reason=reason)
    return SectorRuleResult(
        compliant=False,
        rule=found.rule,
        matched_keyword=found.matched_keyword,
        reason=reason or found.reason,
    )


def build_screening_transparency(
    company: dict[str, Any], now: datetime | None = None
) -> TransparencyFields:
    """The data status, notice, rules version, time, sector rule and gaps for one screening."""
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    return TransparencyFields(
        data_status=resolve_data_status(company),
        screened_at=moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        sector_rule=sector_rule_for(company),
    )
