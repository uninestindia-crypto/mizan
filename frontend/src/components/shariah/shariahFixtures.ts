// Shapes the Shariah screens read, as the engine returns them. Shared by the tests in this folder.

import type { ShariahAudit, ShariahBasket, ShariahRatio, ShariahStandardResult } from "../../lib/types";

export function ratio(over: Partial<ShariahRatio> = {}): ShariahRatio {
  return {
    metric_name: "Debt to Market Capitalization",
    actual_value: 0.005753,
    actual_pct: 0.5753,
    threshold_pct: 33,
    is_compliant: true,
    is_warning: false,
    numerator_label: "Total Interest-Bearing Debt",
    numerator_value_inr_cr: 7970,
    denominator_label: "36-Month Rolling Average Market Cap",
    denominator_value_inr_cr: 1385400,
    note_reference: "Note 18",
    ...over,
  };
}

export function standard(name: string, over: Partial<ShariahStandardResult> = {}): ShariahStandardResult {
  return {
    standard: name,
    status: "COMPLIANT",
    is_compliant: true,
    debt_ratio: ratio(),
    cash_ratio: ratio({
      metric_name: "Cash & Liquid Investments to Market Capitalization",
      actual_pct: 1.8587,
      numerator_label: "Cash, Bank & Debt Securities",
      numerator_value_inr_cr: 25750,
    }),
    receivables_ratio: ratio({
      metric_name: "Accounts Receivable to Market Capitalization",
      actual_pct: 2.8093,
      numerator_label: "Total Trade Receivables",
      numerator_value_inr_cr: 38920,
    }),
    impermissible_income_ratio: ratio({
      metric_name: "Impermissible Revenue to Total Revenue",
      actual_pct: 0.58,
      threshold_pct: 5,
      numerator_label: "Non-Operating Interest & Prohibited Income",
      numerator_value_inr_cr: 1420,
      denominator_label: "Total Revenue (Operations + Other)",
      denominator_value_inr_cr: 244843,
    }),
    summary: "Fully Compliant with AAOIFI Standard No. 21 criteria.",
    ...over,
  };
}

/** A response from before the transparency fields existed: it has none of the new ones. */
export function olderAudit(over: Partial<ShariahAudit> = {}): ShariahAudit {
  return {
    ticker: "TCS.NS",
    symbol: "TCS",
    company_name: "Tata Consultancy Services Limited",
    filing_date: "2024-04-12",
    reporting_period: "Q4 FY24 Audited Consolidated",
    source_document: "BSE/NSE Annual Audited Report",
    sector: "Information Technology",
    sector_compliant: true,
    sector_failure_reason: null,
    aaoifi_evaluation: standard("AAOIFI"),
    tasis_evaluation: standard("TASIS"),
    divergence_noted: false,
    divergence_explanation: null,
    ...over,
  };
}

export function fullAudit(over: Partial<ShariahAudit> = {}): ShariahAudit {
  return olderAudit({
    data_status: "UNVERIFIED_SAMPLE",
    data_notice: "Illustrative sample entered by hand from FY24 reports; not read from audited filings and not live.",
    methodology_version: "shariah-screen-v1",
    screened_at: "2026-10-07T04:45:00+00:00",
    sector_rule: { compliant: true, rule: null, matched_keyword: null, reason: null },
    not_covered: [
      "No scholar has reviewed this result.",
      "The figures are a hand-entered sample, not read from filings.",
      "It is a screening aid, not a religious ruling (fatwa).",
    ],
    ...over,
  });
}

/** A bank: the business-line rule fails it, and its debt is far over the limit. */
export function bankAudit(): ShariahAudit {
  const over = { is_compliant: false, actual_pct: 88.2041 };
  return fullAudit({
    ticker: "HDFCBANK.NS",
    symbol: "HDFCBANK",
    company_name: "HDFC Bank Limited",
    sector: "Financial Services",
    sector_compliant: false,
    sector_failure_reason: "Conventional banking and interest lending (Riba)",
    sector_rule: {
      compliant: false,
      rule: "interest_based_finance",
      matched_keyword: "financial services",
      reason: "Conventional banking and interest lending (Riba)",
    },
    aaoifi_evaluation: standard("AAOIFI", {
      status: "NON_COMPLIANT",
      is_compliant: false,
      debt_ratio: ratio(over),
    }),
    tasis_evaluation: standard("TASIS", { status: "NON_COMPLIANT", is_compliant: false }),
  });
}

export function basket(over: Partial<ShariahBasket> = {}): ShariahBasket {
  return {
    id: "halal-tech-giants",
    name: "Halal Tech Giants",
    thesis: "Large Indian IT companies with little debt.",
    category: "Information Technology & Software",
    constituents: [
      { ticker: "TCS.NS", symbol: "TCS", company_name: "Tata Consultancy", weight: 0.25, price_status: "SAMPLE" },
      { ticker: "INFY.NS", symbol: "INFY", company_name: "Infosys", weight: 0.25, price_status: "NOT_AVAILABLE" },
    ],
    performance: {
      status: "NOT_COMPUTED",
      message: "QuantOS has not back-tested this basket, so no return or risk figure is shown.",
    },
    history_status: "NONE_RECORDED",
    history_message: "No rebalances have been recorded yet.",
    ...over,
  };
}
