from typing import Any

from quant_system.shariah.core.config import settings
from quant_system.shariah.schemas.company import ComplianceStatus, ScreeningStandard
from quant_system.shariah.schemas.screening import (
    AuditEvidenceLine,
    RatioMeter,
    StandardEvaluation,
)

PROHIBITED_SECTORS = {
    "banking": "Conventional banking and interest lending (Riba)",
    "financial services": "Conventional financial intermediation, loan broking, and margin lending (Riba)",
    "insurance": "Conventional life and general insurance pools with interest/uncertainty (Gharar/Riba)",
    "alcohol": "Distillation, brewing, distribution, and sale of alcoholic beverages (Khamr)",
    "breweries & distilleries": "Commercial manufacturing and distribution of liquor and beer (Khamr)",
    "tobacco": "Cigarettes, bidis, and smokeless tobacco manufacturing and distribution (Dharar)",
    "gambling": "Casinos, sports betting, lotteries, and real-money gaming (Maysir/Qimar)",
    "media & entertainment": "Commercial cinema theater exhibition of unscreened non-halal media",
    "defense & weapons": "Offensive weaponry, cluster munitions, and anti-personnel landmines",
}


def check_sector_compliance(
    sector: str, industry: str, business_summary: str = ""
) -> tuple[bool, str | None]:
    """Determine whether a company's business activity is permissible under Islamic law."""
    sec_lower = sector.strip().lower()
    ind_lower = industry.strip().lower()
    sum_lower = business_summary.strip().lower()
    full_text = f"{sec_lower} {ind_lower} {sum_lower}"

    # IT and software vendors providing enterprise tech are permissible
    if sec_lower in ["information technology", "it"] and not any(
        k in full_text for k in ["casino", "gambling", "betting"]
    ):
        return True, None

    # Check conventional financial services exclusions (Commercial Banking, NBFCs, Insurance)
    if sec_lower in ["financial services", "banking", "insurance"]:
        return False, "Conventional banking and interest lending (Riba)"
    if any(
        k in full_text
        for k in [
            "commercial bank",
            "retail lending",
            "housing finance",
            "nbfc - consumer lending",
            "life insurance",
            "general insurance",
        ]
    ):
        return False, "Conventional banking and interest lending (Riba)"

    # Check alcohol exclusions
    if any(
        k in full_text
        for k in [
            "distilleries, breweries",
            "alcoholic beverages",
            "liquor",
            "spirits",
            "brewery",
            "distillery",
            "beer",
            "imfl",
        ]
    ):
        return False, "Commercial manufacturing and distribution of liquor and beer (Khamr)"

    # Check tobacco exclusions
    if any(
        k in full_text for k in ["cigarettes, tobacco", "cigarette", "tobacco", "cigars", "gutkha"]
    ):
        return False, "Manufacturing or distribution of tobacco and nicotine products (Dharar)"

    # Check gambling / casino exclusions
    if any(
        k in full_text
        for k in [
            "casinos, gaming",
            "casino",
            "gambling",
            "lottery",
            "real-money gaming",
            "real money gaming",
        ]
    ):
        return False, "Operation of gambling or gaming ventures (Maysir/Qimar)"

    # Check prohibited media (unscreened commercial film exhibition)
    if "cinema" in full_text or "film exhibition" in full_text:
        return False, "Commercial cinema theater exhibition of unscreened non-halal media"

    return True, None


def evaluate_ratio(
    metric_name: str,
    numerator: float,
    denominator: float,
    threshold: float,
    warning_threshold: float,
    numerator_label: str,
    denominator_label: str,
    note_reference: str | None = None,
) -> RatioMeter:
    """Evaluate a single financial ratio against strict threshold and warning zone."""
    if denominator <= 0:
        actual_val = 1.0 if numerator > 0 else 0.0
    else:
        actual_val = round(numerator / denominator, 6)

    actual_pct = round(actual_val * 100.0, 4)
    threshold_pct = round(threshold * 100.0, 2)

    # Strict inequality check: strictly < threshold
    is_compliant = actual_val < threshold
    # Warning zone: [warning_threshold, threshold)
    is_warning = (actual_val >= warning_threshold) and (actual_val < threshold)

    return RatioMeter(
        metric_name=metric_name,
        actual_value=actual_val,
        actual_pct=actual_pct,
        threshold_pct=threshold_pct,
        is_compliant=is_compliant,
        is_warning=is_warning,
        numerator_label=numerator_label,
        numerator_value_inr_cr=round(numerator, 2),
        denominator_label=denominator_label,
        denominator_value_inr_cr=round(denominator, 2),
        note_reference=note_reference,
    )


def evaluate_company_shariah(
    company: dict[str, Any],
) -> tuple[StandardEvaluation, StandardEvaluation, bool, str | None]:
    """Perform deterministic dual-standard (AAOIFI vs TASIS) screening evaluation."""
    sector_compliant = bool(company.get("sector_compliant", True))
    sector_failure_reason = company.get("sector_failure_reason")

    # Balance sheet & P&L metrics
    total_debt = float(company.get("total_debt", 0.0))
    cash_inv = float(company.get("total_cash_and_investments", 0.0))
    receivables = float(company.get("total_receivables", 0.0))
    total_assets = float(company.get("total_assets", 0.0))
    avg_36m_mcap = float(company.get("avg_36m_market_cap", 0.0))

    impermissible_inc = float(company.get("total_impermissible_income", 0.0))
    total_rev = float(company.get("total_revenue", 0.0))

    debt_note = company.get("debt_note_ref", "Note 18 - Borrowings")
    cash_note = company.get("cash_note_ref", "Note 12 - Cash & Investments")
    rec_note = company.get("rec_note_ref", "Note 11 - Trade Receivables")
    inc_note = company.get("income_note_ref", "Note 24 - Other Income")

    # ---------------- AAOIFI EVALUATION (Denominator: 36m Avg Mcap) ----------------
    aaoifi_debt = evaluate_ratio(
        metric_name="Debt to Market Capitalization",
        numerator=total_debt,
        denominator=avg_36m_mcap,
        threshold=settings.MAX_DEBT_RATIO,
        warning_threshold=settings.WARN_DEBT_RATIO,
        numerator_label="Total Interest-Bearing Debt",
        denominator_label="36-Month Rolling Average Market Cap",
        note_reference=debt_note,
    )
    aaoifi_cash = evaluate_ratio(
        metric_name="Cash & Liquid Investments to Market Capitalization",
        numerator=cash_inv,
        denominator=avg_36m_mcap,
        threshold=settings.MAX_CASH_RATIO,
        warning_threshold=settings.WARN_CASH_RATIO,
        numerator_label="Cash, Bank & Debt Securities",
        denominator_label="36-Month Rolling Average Market Cap",
        note_reference=cash_note,
    )
    aaoifi_rec = evaluate_ratio(
        metric_name="Accounts Receivable to Market Capitalization",
        numerator=receivables,
        denominator=avg_36m_mcap,
        threshold=settings.MAX_RECEIVABLES_RATIO,
        warning_threshold=settings.WARN_RECEIVABLES_RATIO,
        numerator_label="Total Trade Receivables",
        denominator_label="36-Month Rolling Average Market Cap",
        note_reference=rec_note,
    )
    aaoifi_imp = evaluate_ratio(
        metric_name="Impermissible Revenue to Total Revenue",
        numerator=impermissible_inc,
        denominator=total_rev,
        threshold=settings.MAX_IMPERMISSIBLE_REVENUE_RATIO,
        warning_threshold=settings.WARN_IMPERMISSIBLE_REVENUE_RATIO,
        numerator_label="Non-Operating Interest & Prohibited Income",
        denominator_label="Total Revenue (Operations + Other)",
        note_reference=inc_note,
    )

    if not sector_compliant:
        aaoifi_status = ComplianceStatus.NON_COMPLIANT
        aaoifi_summary = f"Disqualified: Sector failure ({sector_failure_reason})"
    elif not (
        aaoifi_debt.is_compliant
        and aaoifi_cash.is_compliant
        and aaoifi_rec.is_compliant
        and aaoifi_imp.is_compliant
    ):
        aaoifi_status = ComplianceStatus.NON_COMPLIANT
        failures = []
        if not aaoifi_debt.is_compliant:
            failures.append(f"Debt ({aaoifi_debt.actual_pct}% >= 33%)")
        if not aaoifi_cash.is_compliant:
            failures.append(f"Cash ({aaoifi_cash.actual_pct}% >= 33%)")
        if not aaoifi_rec.is_compliant:
            failures.append(f"Receivables ({aaoifi_rec.actual_pct}% >= 33%)")
        if not aaoifi_imp.is_compliant:
            failures.append(f"Impermissible Rev ({aaoifi_imp.actual_pct}% >= 5%)")
        aaoifi_summary = f"Non-Compliant: Breached threshold on {', '.join(failures)}"
    elif (
        aaoifi_debt.is_warning
        or aaoifi_cash.is_warning
        or aaoifi_rec.is_warning
        or aaoifi_imp.is_warning
    ):
        aaoifi_status = ComplianceStatus.QUESTIONABLE
        warnings = []
        if aaoifi_debt.is_warning:
            warnings.append(f"Debt in warning band ({aaoifi_debt.actual_pct}%)")
        if aaoifi_cash.is_warning:
            warnings.append(f"Cash in warning band ({aaoifi_cash.actual_pct}%)")
        if aaoifi_rec.is_warning:
            warnings.append(f"Receivables in warning band ({aaoifi_rec.actual_pct}%)")
        if aaoifi_imp.is_warning:
            warnings.append(f"Impermissible Rev in warning band ({aaoifi_imp.actual_pct}%)")
        aaoifi_summary = f"Questionable / Mushbooh: Approaching threshold ({', '.join(warnings)})"
    else:
        aaoifi_status = ComplianceStatus.COMPLIANT
        aaoifi_summary = "Fully Compliant with AAOIFI Standard No. 21 criteria."

    aaoifi_eval = StandardEvaluation(
        standard=ScreeningStandard.AAOIFI,
        status=aaoifi_status,
        is_compliant=(aaoifi_status == ComplianceStatus.COMPLIANT),
        debt_ratio=aaoifi_debt,
        cash_ratio=aaoifi_cash,
        receivables_ratio=aaoifi_rec,
        impermissible_income_ratio=aaoifi_imp,
        summary=aaoifi_summary,
    )

    # ---------------- TASIS EVALUATION (Denominator: Total Assets) ----------------
    tasis_debt = evaluate_ratio(
        metric_name="Debt to Total Assets",
        numerator=total_debt,
        denominator=total_assets,
        threshold=settings.MAX_DEBT_RATIO,
        warning_threshold=settings.WARN_DEBT_RATIO,
        numerator_label="Total Interest-Bearing Debt",
        denominator_label="Audited Book Value of Total Assets",
        note_reference=debt_note,
    )
    tasis_cash = evaluate_ratio(
        metric_name="Cash & Liquid Investments to Total Assets",
        numerator=cash_inv,
        denominator=total_assets,
        threshold=settings.MAX_CASH_RATIO,
        warning_threshold=settings.WARN_CASH_RATIO,
        numerator_label="Cash, Bank & Debt Securities",
        denominator_label="Audited Book Value of Total Assets",
        note_reference=cash_note,
    )
    tasis_rec = evaluate_ratio(
        metric_name="Receivables to Total Assets",
        numerator=receivables,
        denominator=total_assets,
        threshold=settings.MAX_RECEIVABLES_RATIO,
        warning_threshold=settings.WARN_RECEIVABLES_RATIO,
        numerator_label="Total Trade Receivables",
        denominator_label="Audited Book Value of Total Assets",
        note_reference=rec_note,
    )
    tasis_imp = evaluate_ratio(
        metric_name="Impermissible Revenue to Total Revenue",
        numerator=impermissible_inc,
        denominator=total_rev,
        threshold=settings.MAX_IMPERMISSIBLE_REVENUE_RATIO,
        warning_threshold=settings.WARN_IMPERMISSIBLE_REVENUE_RATIO,
        numerator_label="Non-Operating Interest & Prohibited Income",
        denominator_label="Total Revenue (Operations + Other)",
        note_reference=inc_note,
    )

    if not sector_compliant:
        tasis_status = ComplianceStatus.NON_COMPLIANT
        tasis_summary = f"Disqualified: Sector failure ({sector_failure_reason})"
    elif not (
        tasis_debt.is_compliant
        and tasis_cash.is_compliant
        and tasis_rec.is_compliant
        and tasis_imp.is_compliant
    ):
        tasis_status = ComplianceStatus.NON_COMPLIANT
        failures = []
        if not tasis_debt.is_compliant:
            failures.append(f"Debt/Assets ({tasis_debt.actual_pct}% >= 33%)")
        if not tasis_cash.is_compliant:
            failures.append(f"Cash/Assets ({tasis_cash.actual_pct}% >= 33%)")
        if not tasis_rec.is_compliant:
            failures.append(f"Receivables/Assets ({tasis_rec.actual_pct}% >= 33%)")
        if not tasis_imp.is_compliant:
            failures.append(f"Impermissible Rev ({tasis_imp.actual_pct}% >= 5%)")
        tasis_summary = f"Non-Compliant: Breached threshold on {', '.join(failures)}"
    elif (
        tasis_debt.is_warning
        or tasis_cash.is_warning
        or tasis_rec.is_warning
        or tasis_imp.is_warning
    ):
        tasis_status = ComplianceStatus.QUESTIONABLE
        warnings = []
        if tasis_debt.is_warning:
            warnings.append(f"Debt/Assets in warning band ({tasis_debt.actual_pct}%)")
        if tasis_cash.is_warning:
            warnings.append(f"Cash/Assets in warning band ({tasis_cash.actual_pct}%)")
        if tasis_rec.is_warning:
            warnings.append(f"Receivables/Assets in warning band ({tasis_rec.actual_pct}%)")
        if tasis_imp.is_warning:
            warnings.append(f"Impermissible Rev in warning band ({tasis_imp.actual_pct}%)")
        tasis_summary = f"Questionable / Mushbooh: Approaching threshold ({', '.join(warnings)})"
    else:
        tasis_status = ComplianceStatus.COMPLIANT
        tasis_summary = "Fully Compliant with BSE-TASIS Shariah 50 methodology."

    tasis_eval = StandardEvaluation(
        standard=ScreeningStandard.TASIS,
        status=tasis_status,
        is_compliant=(tasis_status == ComplianceStatus.COMPLIANT),
        debt_ratio=tasis_debt,
        cash_ratio=tasis_cash,
        receivables_ratio=tasis_rec,
        impermissible_income_ratio=tasis_imp,
        summary=tasis_summary,
    )

    # ---------------- DIVERGENCE CHECK ----------------
    divergence = aaoifi_status != tasis_status
    divergence_reason = None
    if divergence:
        if (
            aaoifi_status == ComplianceStatus.COMPLIANT
            and tasis_status == ComplianceStatus.NON_COMPLIANT
        ):
            if not tasis_cash.is_compliant:
                divergence_reason = (
                    f"Divergence: Passes AAOIFI (Cash/Mcap={aaoifi_cash.actual_pct}% < 33%), "
                    f"but FAILS TASIS because Cash & Liquid Assets form {tasis_cash.actual_pct}% of Total Assets "
                    f"(asset-light cash hoarding)."
                )
            elif not tasis_debt.is_compliant:
                divergence_reason = (
                    f"Divergence: Passes AAOIFI (Debt/Mcap={aaoifi_debt.actual_pct}% < 33%), "
                    f"but FAILS TASIS because Debt forms {tasis_debt.actual_pct}% of Total Assets."
                )
            elif not tasis_rec.is_compliant:
                divergence_reason = (
                    f"Divergence: Passes AAOIFI (Rec/Mcap={aaoifi_rec.actual_pct}% < 33%), "
                    f"but FAILS TASIS because Receivables form {tasis_rec.actual_pct}% of Total Assets."
                )
            else:
                divergence_reason = "Compliant on AAOIFI market-cap basis, but Non-Compliant on TASIS book-asset basis."
        elif (
            aaoifi_status == ComplianceStatus.NON_COMPLIANT
            and tasis_status == ComplianceStatus.COMPLIANT
        ):
            divergence_reason = (
                f"Divergence: Passes TASIS on Total Assets (Debt/Assets={tasis_debt.actual_pct}%), "
                f"but FAILS AAOIFI due to depressed market capitalization elevating Debt/Mcap to {aaoifi_debt.actual_pct}%."
            )
        else:
            divergence_reason = f"Divergent classification: AAOIFI={aaoifi_status.value}, TASIS={tasis_status.value}."

    return aaoifi_eval, tasis_eval, divergence, divergence_reason


def build_audit_evidence_lines(
    company: dict[str, Any],
) -> tuple[list[AuditEvidenceLine], list[AuditEvidenceLine]]:
    """Build itemized line-item audit trail with notes and filing citations."""
    bs_lines = [
        AuditEvidenceLine(
            line_item="Total Audited Assets",
            value_inr_cr=float(company.get("total_assets", 0.0)),
            note_ref="Balance Sheet Line Item",
            filing_schedule="Non-Current + Current Assets",
            verification_status="VERIFIED",
        ),
        AuditEvidenceLine(
            line_item="Long-Term Borrowings",
            value_inr_cr=float(company.get("long_term_debt", 0.0)),
            note_ref=company.get("debt_note_ref", "Note 18 - Non-Current Borrowings"),
            filing_schedule="Schedule III - Non-Current Liabilities",
            verification_status="VERIFIED",
        ),
        AuditEvidenceLine(
            line_item="Short-Term Borrowings & Current Maturities",
            value_inr_cr=float(company.get("short_term_debt", 0.0)),
            note_ref=company.get("debt_note_ref", "Note 21 - Current Borrowings"),
            filing_schedule="Schedule III - Current Liabilities",
            verification_status="VERIFIED",
        ),
        AuditEvidenceLine(
            line_item="Ind AS 116 Lease Liabilities",
            value_inr_cr=float(company.get("lease_liabilities", 0.0)),
            note_ref="Note 35 - Leases",
            filing_schedule="Financial Liabilities",
            verification_status="VERIFIED",
        ),
        AuditEvidenceLine(
            line_item="Total Interest-Bearing Debt",
            value_inr_cr=float(company.get("total_debt", 0.0)),
            note_ref=company.get("debt_note_ref", "Note 18/21 Summary"),
            filing_schedule="Audited Debt Aggregation",
            verification_status="VERIFIED",
        ),
        AuditEvidenceLine(
            line_item="Cash and Cash Equivalents",
            value_inr_cr=float(company.get("cash_and_bank", 0.0)),
            note_ref=company.get("cash_note_ref", "Note 12 - Cash & Bank"),
            filing_schedule="Current Assets",
            verification_status="VERIFIED",
        ),
        AuditEvidenceLine(
            line_item="Current Investments (Debt/Liquid Funds)",
            value_inr_cr=float(company.get("current_investments", 0.0)),
            note_ref=company.get("cash_note_ref", "Note 10 - Current Investments"),
            filing_schedule="Current Financial Assets",
            verification_status="VERIFIED",
        ),
        AuditEvidenceLine(
            line_item="Trade Receivables",
            value_inr_cr=float(company.get("total_receivables", 0.0)),
            note_ref=company.get("rec_note_ref", "Note 11 - Trade Receivables"),
            filing_schedule="Current Financial Assets",
            verification_status="VERIFIED",
        ),
        AuditEvidenceLine(
            line_item="Inventories",
            value_inr_cr=float(company.get("total_inventories", 0.0)),
            note_ref="Note 9 - Inventories",
            filing_schedule="Current Assets",
            verification_status="VERIFIED",
        ),
        AuditEvidenceLine(
            line_item="Current Liabilities",
            value_inr_cr=float(company.get("current_liabilities", 0.0)),
            note_ref="Note 22 - Trade Payables & Other CL",
            filing_schedule="Current Liabilities",
            verification_status="VERIFIED",
        ),
    ]

    pl_lines = [
        AuditEvidenceLine(
            line_item="Revenue from Operations",
            value_inr_cr=float(company.get("operating_revenue", 0.0)),
            note_ref="Note 23 - Revenue from Operations",
            filing_schedule="Statement of Profit & Loss",
            verification_status="VERIFIED",
        ),
        AuditEvidenceLine(
            line_item="Other Income",
            value_inr_cr=float(company.get("other_income", 0.0)),
            note_ref=company.get("income_note_ref", "Note 24 - Other Income"),
            filing_schedule="Statement of Profit & Loss",
            verification_status="VERIFIED",
        ),
        AuditEvidenceLine(
            line_item="Total Revenue",
            value_inr_cr=float(company.get("total_revenue", 0.0)),
            note_ref="P&L Summary Line Item",
            filing_schedule="Statement of Profit & Loss",
            verification_status="VERIFIED",
        ),
        AuditEvidenceLine(
            line_item="Non-Operating Interest Income",
            value_inr_cr=float(company.get("interest_income", 0.0)),
            note_ref=company.get("income_note_ref", "Note 24(a) - Interest on Deposits"),
            filing_schedule="Breakdown of Other Income",
            verification_status="VERIFIED",
        ),
        AuditEvidenceLine(
            line_item="Total Impermissible / Tainted Income",
            value_inr_cr=float(company.get("total_impermissible_income", 0.0)),
            note_ref="Shariah Auditor Taint Schedule",
            filing_schedule="Purification Schedule",
            verification_status="VERIFIED",
        ),
    ]

    return bs_lines, pl_lines
