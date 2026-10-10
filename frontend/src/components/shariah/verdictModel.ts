// Turns one stock's screening result into the sentences the "How this verdict was reached" panel shows.
// It restates what the screener decided and never decides anything itself.

import { date, inrCompact, num } from "../../lib/format";
import { overallStatus } from "../../lib/shariah";
import type { ShariahAudit, ShariahRatio, ShariahStandardResult } from "../../lib/types";
import type { ScreenStatus } from "./labels";

export type RatioState = "within" | "close" | "over";

export interface RatioView {
  key: string;
  name: string;
  formula: string;
  figures: string;
  limit: string;
  headroom: string;
  state: RatioState;
}

export interface StandardView {
  name: string;
  status: ScreenStatus;
  reason: string;
  ratios: RatioView[];
}

export interface SectorView {
  passed: boolean;
  heading: string;
  detail: string;
}

export interface VerdictView {
  overall: ScreenStatus;
  standards: [StandardView, StandardView];
  sector: SectorView;
  sources: { label: string; value: string }[];
  dataStatus: string | null | undefined;
  dataNotice: string | null;
  screenedAt: string | null;
  methodology: string | null;
  notCovered: string[];
}

const RATIO_KEYS = ["debt_ratio", "cash_ratio", "receivables_ratio", "impermissible_income_ratio"] as const;
type RatioKey = (typeof RATIO_KEYS)[number];

const RATIO_NAME: Record<RatioKey, string> = {
  debt_ratio: "Debt",
  cash_ratio: "Cash and bank balances",
  receivables_ratio: "Money owed to the company",
  impermissible_income_ratio: "Income from interest or not-allowed activities",
};

const CRORE = 1e7;
const HAS_ZONE = /(Z|[+-]\d{2}:?\d{2})$/;

/** A UTC timestamp written for a person in India, like "7 Oct 2026, 10:15 am India time". Null when none. */
export function indiaTime(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const when = new Date(HAS_ZONE.test(iso) ? iso : `${iso}Z`);
  if (Number.isNaN(when.getTime())) return null;
  const text = when.toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
  return `${text} India time`;
}

function stateOf(ratio: ShariahRatio): RatioState {
  if (!ratio.is_compliant) return "over";
  return ratio.is_warning ? "close" : "within";
}

function trimmed(value: number): string {
  return String(Number(value.toFixed(2)));
}

function headroomLine(ratio: ShariahRatio, state: RatioState): string {
  const gap = Math.round((ratio.threshold_pct - ratio.actual_pct) * 100) / 100;
  if (state === "over") {
    if (gap >= 0) return "Exactly at the limit, which does not pass.";
    return `Over the limit by ${num(-gap, 2)} percentage points.`;
  }
  return gap > 0 ? `Headroom: ${num(gap, 2)} percentage points under the limit.` : "Just under the limit.";
}

function ratioView(key: RatioKey, ratio: ShariahRatio): RatioView {
  const state = stateOf(ratio);
  const top = inrCompact(ratio.numerator_value_inr_cr * CRORE);
  const bottom = inrCompact(ratio.denominator_value_inr_cr * CRORE);
  return {
    key,
    name: RATIO_NAME[key],
    formula: `${ratio.numerator_label} divided by ${ratio.denominator_label}`,
    figures: `${top} divided by ${bottom} = ${num(ratio.actual_pct, 2)}%`,
    limit: `under ${trimmed(ratio.threshold_pct)}%`,
    headroom: headroomLine(ratio, state),
    state,
  };
}

function listOf(names: string[]): string {
  if (names.length < 2) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

function reasonFor(status: ScreenStatus, ratios: RatioView[], sectorPassed: boolean): string {
  if (!sectorPassed) return "Fails the business-line test, whatever its figures.";
  const named = (state: RatioState) => ratios.filter((r) => r.state === state).map((r) => r.name.toLowerCase());
  if (status === "NON_COMPLIANT" && named("over").length > 0) return `Over the limit: ${listOf(named("over"))}.`;
  if (status === "QUESTIONABLE" && named("close").length > 0) return `Close to the limit: ${listOf(named("close"))}.`;
  if (status === "COMPLIANT") return "All four ratios are within their limits and the business line passed.";
  return "Did not pass every test.";
}

function standardView(result: ShariahStandardResult, sectorPassed: boolean): StandardView {
  const ratios = RATIO_KEYS.map((key) => ratioView(key, result[key]));
  const reason = reasonFor(result.status, ratios, sectorPassed);
  return { name: result.standard, status: result.status, reason, ratios };
}

/** "interest_based_finance" is a name for the screener, not a phrase for a person: "Interest based finance". */
function readable(name: string): string {
  const spaced = name.replace(/_/g, " ").trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function sentence(text: string): string {
  const clean = text.trim();
  return clean === "" || /[.!?]$/.test(clean) ? clean : `${clean}.`;
}

function sectorView(audit: ShariahAudit): SectorView {
  const rule = audit.sector_rule;
  const passed = rule?.compliant ?? audit.sector_compliant;
  if (passed) {
    const detail = "No not-allowed business rule matched.";
    return { passed, heading: `Business line: ${audit.sector}. Passed.`, detail };
  }
  const why = sentence(rule?.reason ?? audit.sector_failure_reason ?? "");
  const named = rule?.rule && rule.matched_keyword;
  const hit = named ? `The rule "${readable(rule.rule ?? "")}" matched the word "${rule.matched_keyword}". ` : "";
  return { passed, heading: `Business line: ${audit.sector}. Failed.`, detail: `${hit}${why}`.trim() };
}

function sourceRows(audit: ShariahAudit): { label: string; value: string }[] {
  const rows = [
    { label: "Source document", value: audit.source_document ?? "" },
    { label: "Reporting period", value: audit.reporting_period },
    { label: "Filed on", value: audit.filing_date ? date(audit.filing_date) : "" },
  ];
  return rows.filter((row) => row.value.trim() !== "");
}

export function buildVerdictView(audit: ShariahAudit): VerdictView {
  const sector = sectorView(audit);
  const aaoifi = standardView(audit.aaoifi_evaluation, sector.passed);
  const tasis = standardView(audit.tasis_evaluation, sector.passed);
  return {
    overall: overallStatus(aaoifi.status, tasis.status, audit.overall_status),
    standards: [aaoifi, tasis],
    sector,
    sources: sourceRows(audit),
    dataStatus: audit.data_status,
    dataNotice: audit.data_notice ?? null,
    screenedAt: indiaTime(audit.screened_at),
    methodology: audit.methodology_version ?? null,
    notCovered: (audit.not_covered ?? []).filter((line) => line.trim() !== ""),
  };
}
