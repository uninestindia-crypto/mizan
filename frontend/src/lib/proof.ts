import { useQuery } from "@tanstack/react-query";
import { ApiError, api } from "./api";
import { DATA_STATUSES, type DataStatus, VERDICTS, type Verdict } from "./shariahStatus";

// The proof behind one stock's Shariah verdict: real figures, where each came from, and what it does not cover.
// GET /api/v2/shariah/stocks/{symbol}/proof  ->  StockProof
// (the contract: agent_context/decisions/20261007-shariah-mode-and-filing-proof.md)
// GET /api/v2/shariah/filings/coverage       ->  FilingCoverage

export type StandardStatus = "COMPLIANT" | "NON_COMPLIANT" | "QUESTIONABLE" | "NOT_COMPUTED";
export type TestResult = "PASS" | "FAIL" | "BORDERLINE" | "DEPENDS" | "NOT_COMPUTED";

const STANDARD_STATUSES: readonly StandardStatus[] = ["COMPLIANT", "NON_COMPLIANT", "QUESTIONABLE", "NOT_COMPUTED"];
const TEST_RESULTS: readonly TestResult[] = ["PASS", "FAIL", "BORDERLINE", "DEPENDS", "NOT_COMPUTED"];

export interface ProofFigure {
  /** A percentage: 12.5 means 12.5%. */
  pct: number | null;
  numerator_cr: number | null;
  denominator_cr: number | null;
}

export type InputRole = "numerator" | "denominator" | "derived";
/** Which reading counts a line: both the lower and the upper, or only one of them. */
export type CountedIn = "both" | "lower_only" | "upper_only";

export interface ProofInput {
  label: string;
  /** The field's name in the filing. Shown only in the figures list, under "Source field". Null for a sample figure. */
  xbrl_tag: string | null;
  /** The value in rupees as filed, as exact text. Null when no filing backs it. */
  value_inr: string | null;
  value_cr: number | null;
  role: InputRole;
  counted_in: CountedIn;
}

export interface ProofTest {
  key: string;
  title: string;
  limit_pct: number | null;
  warning_pct: number | null;
  result: TestResult;
  low: ProofFigure | null;
  high: ProofFigure | null;
  plain: string;
  inputs: ProofInput[];
}

export interface ProofStandard {
  standard: string;
  status: StandardStatus;
  summary: string;
  tests: ProofTest[];
}

export type ActivityStatus = "PASS" | "FAIL" | "NOT_CONFIRMED";

export interface ProofSector {
  /** What the business test decided. A screen reads this, never `compliant`. */
  status: ActivityStatus;
  compliant: boolean | null;
  /** What it was decided on: "the filing's segments", "company name", "industry group only", and so on. */
  basis: string | null;
  industry_group: string | null;
  /** Business segments the filing lists. Text from outside the app: shown as plain text only. */
  segments: string[];
  matched_in: "name" | "segment" | "sample" | null;
  /** One plain sentence: what was checked and what it could not tell. */
  plain: string | null;
  rule: string | null;
  matched_keyword: string | null;
  reason: string | null;
}

export interface ProofCheck {
  name: string;
  ok: boolean;
  detail: string;
}

export interface ProofFiling {
  source_url: string | null;
  detail_url: string | null;
  period_end: string | null;
  period_label: string | null;
  filed_on: string | null;
  consolidated: boolean | null;
  audited: boolean | null;
  sha256: string | null;
  tie_out: { ok: boolean; checks: ProofCheck[] };
}

export interface StockProof {
  symbol: string;
  company_name: string | null;
  verdict: Verdict;
  headline: string;
  data_status: DataStatus;
  data_notice: string | null;
  methodology_version: string | null;
  screened_at: string | null;
  sector: ProofSector | null;
  filing: ProofFiling | null;
  standards: ProofStandard[];
  divergence: { noted: boolean; explanation: string | null };
  what_would_change_it: string[];
  not_covered: string[];
  sample_comparison: { differs: boolean; note: string | null };
}

const text = (v: unknown): string | null => (typeof v === "string" && v.trim() ? v : null);
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const list = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
const lines = (v: unknown): string[] => list(v).filter((x): x is string => typeof x === "string" && x.trim() !== "");
const obj = (v: unknown): Record<string, unknown> =>
  typeof v === "object" && v !== null ? (v as Record<string, unknown>) : {};

function oneOf<T extends string>(all: readonly T[], v: unknown, fallback: T): T {
  return typeof v === "string" && (all as readonly string[]).includes(v) ? (v as T) : fallback;
}

function parseFigure(raw: unknown): ProofFigure | null {
  if (typeof raw !== "object" || raw === null) return null;
  const f = obj(raw);
  return { pct: num(f.pct), numerator_cr: num(f.numerator_cr), denominator_cr: num(f.denominator_cr) };
}

const ROLES: readonly InputRole[] = ["numerator", "denominator", "derived"];
const COUNTED: readonly CountedIn[] = ["both", "lower_only", "upper_only"];

/** The figure in rupees as filed, kept as exact text. A number is turned into text; anything else is "no value". */
function rupees(v: unknown): string | null {
  if (typeof v === "string" && /^-?\d+(\.\d+)?$/.test(v.trim())) return v.trim();
  return typeof v === "number" && Number.isFinite(v) ? String(v) : null;
}

/** A line is kept when it has a value to show. Whether a filing backs it shows in its field name and the filing box. */
function parseInputs(raw: unknown): ProofInput[] {
  const inputs: ProofInput[] = [];
  for (const item of list(raw)) {
    const i = obj(item);
    const inr = rupees(i.value_inr);
    const cr = num(i.value_cr) ?? (inr === null ? null : Number(inr) / 1e7);
    if (cr === null) continue;
    inputs.push({
      label: text(i.label) ?? "Figure",
      xbrl_tag: text(i.xbrl_tag),
      value_inr: inr,
      value_cr: cr,
      role: oneOf(ROLES, i.role, "numerator"),
      counted_in: oneOf(COUNTED, i.counted_in, "both"),
    });
  }
  return inputs;
}

function parseTest(raw: unknown): ProofTest {
  const t = obj(raw);
  return {
    key: text(t.key) ?? "test",
    title: text(t.title) ?? "Test",
    limit_pct: num(t.limit_pct),
    warning_pct: num(t.warning_pct),
    result: oneOf(TEST_RESULTS, t.result, "NOT_COMPUTED"),
    low: parseFigure(t.low),
    high: parseFigure(t.high),
    plain: text(t.plain) ?? "",
    inputs: parseInputs(t.inputs),
  };
}

function parseStandard(raw: unknown): ProofStandard {
  const s = obj(raw);
  return {
    standard: text(s.standard) ?? "Standard",
    status: oneOf(STANDARD_STATUSES, s.status, "NOT_COMPUTED"),
    summary: text(s.summary) ?? "",
    tests: list(s.tests).map(parseTest),
  };
}

function parseFiling(raw: unknown): ProofFiling | null {
  if (typeof raw !== "object" || raw === null) return null;
  const f = obj(raw);
  const tie = obj(f.tie_out);
  const checks = list(tie.checks).map((c): ProofCheck => {
    const k = obj(c);
    return { name: text(k.name) ?? "Check", ok: k.ok === true, detail: text(k.detail) ?? "" };
  });
  return {
    source_url: text(f.source_url),
    detail_url: text(f.detail_url),
    period_end: text(f.period_end),
    period_label: text(f.period_label),
    filed_on: text(f.filed_on),
    consolidated: typeof f.consolidated === "boolean" ? f.consolidated : null,
    audited: typeof f.audited === "boolean" ? f.audited : null,
    sha256: text(f.sha256),
    tie_out: { ok: tie.ok === true, checks },
  };
}

const MARKUP = /[<>\u0000-\u001f\u007f]/g;
const MAX_SEGMENTS = 20;
const MAX_SEGMENT_CHARS = 120;

/** Segment names come from outside the app. Whatever arrives is kept as plain text: no angle brackets, bounded. */
export function plainSegments(raw: unknown): string[] {
  const out: string[] = [];
  for (const item of list(raw)) {
    if (typeof item !== "string") continue;
    const clean = item.replace(MARKUP, " ").split(/\s+/).filter(Boolean).join(" ").slice(0, MAX_SEGMENT_CHARS);
    if (clean && !out.includes(clean)) out.push(clean);
  }
  return out.slice(0, MAX_SEGMENTS);
}

const ACTIVITY: readonly ActivityStatus[] = ["PASS", "FAIL", "NOT_CONFIRMED"];
const MATCHED_IN = ["name", "segment", "sample"] as const;

function parseSector(raw: unknown): ProofSector | null {
  if (typeof raw !== "object" || raw === null) return null;
  const s = obj(raw);
  const compliant = typeof s.compliant === "boolean" ? s.compliant : null;
  const older: ActivityStatus = compliant === true ? "PASS" : compliant === false ? "FAIL" : "NOT_CONFIRMED";
  const found = oneOf(MATCHED_IN, s.matched_in, "name");
  return {
    status: oneOf(ACTIVITY, s.status, older),
    compliant,
    basis: text(s.basis),
    industry_group: text(s.industry_group) ?? text(s.industry) ?? text(s.sector),
    segments: plainSegments(s.segments),
    matched_in: typeof s.matched_in === "string" && s.matched_in === found ? found : null,
    plain: text(s.plain),
    rule: text(s.rule),
    matched_keyword: text(s.matched_keyword),
    reason: text(s.reason),
  };
}

/** Whatever the engine sent, made safe to show. A verdict or status this app does not know becomes "not screened". */
export function parseProof(raw: unknown): StockProof {
  const p = obj(raw);
  const divergence = obj(p.divergence);
  const comparison = obj(p.sample_comparison);
  return {
    symbol: text(p.symbol) ?? "",
    company_name: text(p.company_name),
    verdict: oneOf(VERDICTS, p.verdict, "NOT_SCREENED"),
    headline: text(p.headline) ?? "",
    data_status: oneOf(DATA_STATUSES, p.data_status, "NOT_SCREENED"),
    data_notice: text(p.data_notice),
    methodology_version: text(p.methodology_version),
    screened_at: text(p.screened_at),
    sector: parseSector(p.sector),
    filing: parseFiling(p.filing),
    standards: list(p.standards).map(parseStandard),
    divergence: { noted: divergence.noted === true, explanation: text(divergence.explanation) },
    what_would_change_it: lines(p.what_would_change_it),
    not_covered: lines(p.not_covered),
    sample_comparison: { differs: comparison.differs === true, note: text(comparison.note) },
  };
}

export const PROOF_KEY = ["shariah-proof"] as const;
const FIVE_MINUTES = 5 * 60_000;

export function useStockProof(symbol: string, enabled = true) {
  const upper = symbol.trim().toUpperCase();
  return useQuery({
    queryKey: [...PROOF_KEY, upper],
    queryFn: async () => parseProof(await api<unknown>(`/api/v2/shariah/stocks/${encodeURIComponent(upper)}/proof`)),
    enabled: enabled && upper !== "",
    staleTime: FIVE_MINUTES,
    retry: false,
  });
}

export type ProofProblem = "missing" | "offline" | "other";

/** Why the proof could not be had: no screening for this stock yet, the engine unreachable, or anything else. */
export function proofProblem(error: unknown): ProofProblem {
  if (error instanceof ApiError && error.status === 404) return "missing";
  if (error instanceof ApiError && error.status === 0) return "offline";
  return "other";
}

export interface FilingCoverage {
  screened: number;
  total_listed: number | null;
  newest_filing: string | null;
  snapshot_built_on: string | null;
}

export const COVERAGE_KEY = ["shariah-coverage"] as const;

function parseCoverage(raw: unknown): FilingCoverage {
  const c = obj(raw);
  return {
    screened: num(c.screened) ?? 0,
    total_listed: num(c.total_listed),
    newest_filing: text(c.newest_filing),
    snapshot_built_on: text(c.snapshot_built_on),
  };
}

/** How many stocks are screened from real filings. A missing answer just means the line is not shown. */
export function useFilingCoverage(enabled: boolean) {
  return useQuery({
    queryKey: COVERAGE_KEY,
    queryFn: async () => parseCoverage(await api<unknown>("/api/v2/shariah/filings/coverage")),
    enabled,
    staleTime: 10 * 60_000,
    retry: false,
  });
}

/** Only the filing pages on NSE itself are ever made into links. Anything else is shown as plain text. */
const NSE_HOSTS = new Set(["www.nseindia.com", "nsearchives.nseindia.com"]);

export function safeNseUrl(raw: string | null | undefined): string | null {
  if (!raw) return null;
  try {
    const url = new URL(raw);
    const plain = url.protocol === "https:" && url.username === "" && url.password === "" && url.port === "";
    return plain && NSE_HOSTS.has(url.hostname) ? url.href : null;
  } catch {
    return null;
  }
}
