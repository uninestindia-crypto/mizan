// What the engine sends for long-term fundamentals: facts from a company's own filings, with their proof and dates.
// GET /api/v2/fundamentals/{symbol}            one company
// GET /api/v2/fundamentals/screen              companies that meet the filters a person chose
// GET /api/v2/fundamentals/compare?symbols=    two to four companies side by side
// GET /api/v2/portfolio/fundamentals?account=  the holdings in view
// POST /api/v2/fundamentals/fetch              read a company's latest results from NSE, in the background
// Every sentence and label here is the engine's own and is shown as sent. Nothing is worked out in the app.

export type DataStatus = "VERIFIED_FILING" | "STALE" | "NOT_AVAILABLE";

/** Whether a fact sits inside the rule of thumb, outside it, is just a fact, or could not be worked out. */
export type FactStatus = "OK" | "WATCH" | "INFO" | "NOT_AVAILABLE";

export type FactCounts = Record<FactStatus, number>;

/** One number a figure was worked out from, and where a person can check it. */
export interface FundamentalsProof {
  kind: "FILING" | "PRICE";
  label: string;
  tag: string;
  value: number;
  unit: string;
  period: string;
  period_end: string;
  filed_on: string | null;
  filing_url: string | null;
  sha256: string | null;
}

export interface FundamentalsMetric {
  key: string;
  label: string;
  /** "INR", "INR per share", "percent", "times" or "quarters". */
  unit: string;
  value: number | null;
  available: boolean;
  /** Why it could not be worked out, when it could not. */
  reason: string | null;
  formula: string;
  period: string | null;
  as_of: string | null;
  approximate: boolean;
  note: string | null;
  extra: Record<string, unknown>;
  inputs: FundamentalsProof[];
}

export interface ScorecardFact {
  key: string;
  status: FactStatus;
  sentence: string;
  rule_of_thumb: string | null;
  metric: string | null;
}

export interface FundamentalsScorecard {
  /** The line that goes above the facts, shown exactly as sent. */
  header: string;
  facts: ScorecardFact[];
  counts: FactCounts;
}

export interface QuarterFacts {
  period_end: string;
  period_label: string;
  filed_on: string | null;
  audited: boolean | null;
  consolidated: boolean | null;
  revenue_inr: number | null;
  net_profit_inr: number | null;
  eps: number | null;
  filing_url: string | null;
  sha256: string | null;
}

/** A quarter that was read but is left out of every figure, with the engine's reason. */
export interface ExcludedQuarter {
  period_end: string;
  status: string;
  reason: string;
}

export interface QuarterSeries {
  held: number;
  quarters: QuarterFacts[];
  gaps: string[];
  excluded: ExcludedQuarter[];
  notes: string[];
}

export interface PriceFact {
  close: number;
  as_of: string;
  source: string;
}

export interface CompanyFundamentals {
  symbol: string;
  company_name: string | null;
  industry: string | null;
  data_status: DataStatus;
  /** The sentence about how old the data is, or why there is none. Shown as sent. */
  data_notice: string;
  read_status: string;
  basis: { consolidated: boolean | null; label: string | null };
  latest_quarter: QuarterFacts | null;
  series: QuarterSeries;
  metrics: Record<string, FundamentalsMetric>;
  scorecard: FundamentalsScorecard;
  price: PriceFact | null;
  today: string;
  not_covered: string[];
  statement: string;
}

// ---------------------------------------------------------------------------------------------- reading from NSE

export type FetchState = "running" | "done" | "failed" | "cancelled";

export interface FetchFailure {
  symbol: string;
  reason: string;
}

export interface FetchJob {
  status: FetchState;
  symbol: string;
  done: number;
  total: number;
  saved: number;
  message: string;
  failures: FetchFailure[];
}

// ---------------------------------------------------------------------------------------------------- the screen

export interface AppliedFilter {
  filter: string;
  value: number | string;
  /** The filter in words, as the engine wrote it. */
  plain: string;
}

export interface DataDates {
  newest_filing: string | null;
  oldest_latest_quarter: string | null;
  price_date: string | null;
  snapshot_built_on?: string | null;
}

export interface ScreenRow {
  symbol: string;
  company_name: string | null;
  industry: string | null;
  data_status: DataStatus;
  latest_quarter: string | null;
  basis: "consolidated" | "standalone" | null;
  scorecard_counts: FactCounts;
  profitable_quarters: number | null;
  roe_pct: number | null;
  debt_to_equity: number | null;
  interest_cover: number | null;
  ttm_profit_growth_pct: number | null;
  pe: number | null;
  net_margin_pct: number | null;
  ttm_revenue_inr: number | null;
  ttm_net_profit_inr: number | null;
}

export interface ScreenAnswer {
  /** "These are filters you chose, not a recommendation." Shown as sent. */
  statement: string;
  filters_applied: AppliedFilter[];
  sort: { by: string; order: "asc" | "desc" };
  considered: number;
  matched: number;
  returned: number;
  excluded_missing_data: number;
  excluded_by_filters: number;
  missing_by_filter: Record<string, number>;
  stale_in_results: number;
  data_dates: DataDates;
  results: ScreenRow[];
}

/** The filters, the sort and the number of results a person chose. Empty text means "not chosen". */
export interface ScreenParams {
  min_profitable_quarters: string;
  min_roe_pct: string;
  max_debt_to_equity: string;
  min_interest_cover: string;
  min_ttm_profit_growth_pct: string;
  max_pe: string;
  sector: string;
  sort: string;
  order: "asc" | "desc";
  limit: string;
}

// -------------------------------------------------------------------------------------------------- compare

export interface CompareValue {
  value: number | null;
  unit: string;
  available: boolean;
  reason: string | null;
  as_of: string | null;
  period: string | null;
  approximate: boolean;
}

export interface CompareRow {
  key: string;
  label: string;
  unit: string;
  values: Record<string, CompareValue>;
}

export interface CompareColumn {
  symbol: string;
  company_name: string | null;
  industry: string | null;
  included: boolean;
  /** Why the company is not in the lines below, when it is not. */
  reason: string | null;
  basis: "consolidated" | "standalone" | null;
  data_status: DataStatus;
  latest_quarter: string | null;
  scorecard_counts: FactCounts;
}

export interface CompareAnswer {
  statement: string;
  comparable: boolean;
  basis: "consolidated" | "standalone" | null;
  companies: CompareColumn[];
  rows: CompareRow[];
  notes: string[];
}

// --------------------------------------------------------------------------------------------------- portfolio

export interface HoldingFundamentals {
  symbol: string;
  name: string | null;
  weight_pct: number | null;
  value: number | null;
  industry: string | null;
  data_status: DataStatus;
  latest_quarter: string | null;
  scorecard_counts: FactCounts;
  profitable_quarters: number | null;
  profit_growth_ttm_pct: number | null;
  net_margin_pct: number | null;
  roe_pct: number | null;
  debt_to_equity: number | null;
  interest_cover: number | null;
  pe: number | null;
}

export interface SectorWeight {
  sector: string;
  weight_pct: number;
}

export interface WeightedPe {
  value: number | null;
  method: string;
  holdings_included: number;
  weight_included_pct: number;
  note: string;
}

export interface PortfolioFundamentals {
  statement: string;
  weights_note: string;
  scope: { account: "all" | number; name: string };
  holdings_count: number;
  top5_weight_pct: number;
  sector_weights: SectorWeight[];
  weighted_average_pe: WeightedPe;
  without_data_count: number;
  without_data: string[];
  stale_count: number;
  holdings_without_value: string[];
  data_dates: DataDates;
  holdings: HoldingFundamentals[];
}

/** One buy lot of a position, with how long it has been held. The engine adds no tax amounts or rates. */
export interface PositionLot {
  holding_id: number | null;
  account_id: number;
  account_name: string | null;
  quantity: number;
  buy_date: string;
  days_held: number;
  /** The date after which the lot counts as held more than 12 months. */
  long_term_on: string;
  is_long_term: boolean;
}

/** What the portfolio answer adds to each stock: its lots, and one sentence about them that is shown as sent. */
export interface PositionLots {
  lots?: PositionLot[];
  lots_note?: string;
}
