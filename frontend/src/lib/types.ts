// Shapes returned by /api/v2. Kept in step with src/quant_system/server/v2 by the API tests.

export type Theme = "system" | "light" | "dark";
export type Style = "investor" | "swing" | "both";

export interface Settings {
  style: Style | null;
  money: { capital: string; risk_per_trade_pct: string; daily_loss_limit_pct: string };
  broker: {
    delivery_per_order: string;
    intraday_per_order: string;
    fno_per_order: string;
    dp_charge_per_sell: string;
  };
  theme: Theme;
  data_folder: string | null;
  onboarding_complete: boolean;
  disclaimer_accepted_at: string | null;
}

export interface IndexJob {
  state: "IDLE" | "RUNNING" | "DONE" | "ERROR";
  progress: number;
  message: string;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface Status {
  version: string;
  settings: Settings;
  data_folder: { path: string | null; valid: boolean; candidates: { path: string; datasets: number }[] };
  index: {
    ready: boolean;
    latest_session?: string;
    built_at?: string;
    symbols?: number;
    flags?: number;
    data_folder?: string | null;
    matches_folder?: boolean;
    stale?: boolean;
    job: IndexJob;
  };
  credentials_available: boolean;
  costs_covered_from: string;
  lab_runs: number;
}

export interface Mover {
  symbol: string;
  name: string;
  close: number;
  chg_1d: number;
}

export interface Overview {
  latest_session: string;
  benchmark: {
    symbol: string;
    name: string;
    asof: string;
    close: number;
    chg_1d: number | null;
    ret_1m: number | null;
    ret_1y: number | null;
    spark: number[];
  } | null;
  breadth: {
    universe: string;
    asof: string;
    count: number;
    above_200dma: number;
    above_200dma_pct: number | null;
    advancers: number;
    decliners: number;
    unchanged: number;
    stale: number;
  };
  gainers: Mover[];
  losers: Mover[];
}

export interface ScreenerRow {
  symbol: string;
  name: string;
  asof: string;
  close: number;
  prev_close: number | null;
  chg_1d: number | null;
  ret_1m: number | null;
  ret_6m: number | null;
  ret_1y: number | null;
  vol_1y: number | null;
  high_52w: number | null;
  low_52w: number | null;
  from_52w_high: number | null;
  sma_50: number | null;
  sma_200: number | null;
  turnover_cr: number | null;
  is_etf: number;
  series: string;
  security_type: string;
  stitch: string;
}

export interface Screener {
  universe: string;
  latest: string | null;
  rows: ScreenerRow[];
}

export interface SearchResult {
  symbol: string;
  name: string;
  is_etf: number;
  last_date: string;
}

export interface Bars {
  symbol: string;
  dates: string[];
  open: number[];
  high: number[];
  low: number[];
  close: number[];
  volume: number[];
}

export interface CorporateAction {
  ex_date: string;
  subject: string;
  kinds: string[];
  breaks_history: boolean;
}

export interface DataFlag {
  d: string;
  kind: string;
  change: number;
  note: string;
}

export interface Holding {
  id: number;
  symbol: string;
  quantity: number;
  avg_price: string;
  buy_date: string;
  note: string;
}

export interface StockProfile {
  info: {
    symbol: string;
    name: string;
    isin: string;
    series: string;
    security_type: string;
    is_etf: number;
    first_date: string;
    last_date: string;
    sessions: number;
    stitch: string;
    stitch_note: string;
    universes: string[];
    snapshot: ScreenerRow | null;
    sources: { role: string; cache: string; dataset_id: string; acquired_at: string; first_date: string; last_date: string; rows_used: number }[];
  };
  stats: {
    ret_1m: number | null;
    ret_6m: number | null;
    ret_1y: number | null;
    ret_3y: number | null;
    ret_5y: number | null;
    vol_1y: number | null;
    max_drawdown_1y: number;
    max_drawdown_all: number;
    beta_1y: number | null;
  };
  actions: CorporateAction[];
  flags: DataFlag[];
  in_watchlist: boolean;
  holdings: Holding[];
  benchmark: string;
}

export interface ParamSpec {
  name: string;
  label: string;
  kind: "int" | "bool";
  default: number | boolean;
  min: number;
  max: number;
  help: string;
}

export interface Template {
  id: string;
  name: string;
  summary: string;
  how_it_works: string;
  fails_when: string;
  holding_period: string;
  scopes: ("stocks" | "universe")[];
  params: ParamSpec[];
}

export interface Templates {
  templates: Template[];
  universes: { id: string; label: string }[];
  costs_covered_from: string;
  runs_so_far: number;
}

export interface Performance {
  start_equity: number;
  final_equity: number;
  total_return: number;
  cagr: number | null;
  volatility: number | null;
  sharpe: number | null;
  max_drawdown: number;
  time_invested: number;
  fills: number;
  round_trips: number;
  win_rate: number | null;
  avg_hold_sessions: number | null;
  charges: number;
  slippage: number;
}

export type VerdictLevel = "LOST" | "TOO_SHORT" | "NO_EVIDENCE" | "PROMISING" | "EDGE";

export interface LabTrade {
  symbol: string;
  entry_date: string;
  exit_date: string;
  quantity: number;
  entry_price: number;
  exit_price: number;
  pnl: number;
  return_pct: number | null;
  sessions: number;
}

export interface LabResult {
  id: string;
  created_at: string;
  template: Template;
  params: Record<string, number | boolean>;
  scope: {
    kind: "stocks" | "universe";
    universe: string | null;
    universe_label: string | null;
    requested: string[] | null;
    used: number;
    symbols: string[];
    excluded: { symbol: string; reason: string }[];
  };
  period: { start: string; end: string; sessions: number };
  capital: number;
  strategy: Performance;
  benchmark: Performance;
  comparison: { label: string; performance: Performance } | null;
  verdict: {
    level: VerdictLevel;
    title: string;
    body: string;
    probability: number | null;
    trials: number;
    threshold: number;
  };
  equity: [string, number, number, number | null][];
  trades: LabTrade[];
  open_positions: { symbol: string; quantity: number; average_price: number; last_close: number; unrealized_pnl: number }[];
  notes: string[];
  assumptions: string[];
}

export interface LabRunSummary {
  id: string;
  created_at: string;
  template_id: string;
  template_name: string;
  scope_label: string;
  verdict_level: VerdictLevel;
  verdict_title: string;
  strategy_return: number;
  benchmark_return: number;
  period_start: string;
  period_end: string;
}

export interface PortfolioRow {
  id: number;
  symbol: string;
  name?: string;
  quantity: number;
  avg_price: number;
  buy_date: string;
  note: string;
  cost: number;
  asof?: string;
  close?: number;
  value?: number;
  pnl?: number;
  pnl_pct?: number | null;
  day_change?: number | null;
  exit_charges?: number;
  weight?: number;
  error?: string;
  vs_nifty?: { holding_value: number; nifty_value: number; compare_on: string } | null;
}

export interface Portfolio {
  holdings: PortfolioRow[];
  totals: {
    value: number;
    cost: number;
    pnl: number;
    pnl_pct: number | null;
    day_change: number;
    exit_charges: number;
  } | null;
  warnings: string[];
  nifty: { compare_on: string; holdings_value: number; nifty_value: number; count: number } | null;
}

export interface PaperBook {
  id: string;
  name: string;
  status: string;
  label: string;
  message?: string;
  capital?: number | null;
  cash?: number | null;
  equity?: number | null;
  return?: number | null;
  started?: string | null;
  asof?: string | null;
  position_count?: number | null;
  positions?: { symbol: string; shares: number; entry_date: string; entry_value: number; market_value: number; unrealized: number; asof: string }[];
  closed_count?: number;
  unresolved_count?: number;
  net_pnl?: number | null;
  fees?: number | null;
  model?: string | null;
  halt_reason?: string | null;
}

export interface WatchRow {
  symbol: string;
  name?: string;
  missing?: boolean;
  spark?: number[];
  asof?: string;
  close?: number;
  chg_1d?: number | null;
  ret_1m?: number | null;
  ret_1y?: number | null;
}

export interface ChargeLine {
  label: string;
  amount: number;
  rule_id: string;
}

export interface CostsResult {
  segment: string;
  trade_date: string;
  quantity: number;
  buy: { price: number; turnover: number; lines: ChargeLine[]; total: number };
  sell: { price: number; turnover: number; lines: ChargeLine[]; total: number };
  gross_pnl: number;
  charges: number;
  net_pnl: number;
  charges_pct_of_turnover: number;
  breakeven_price: number;
  breakeven_move_pct: number;
}

export interface PositionSizeResult {
  direction: "long" | "short";
  risk_amount: number;
  risk_per_share: number;
  stop_distance_pct: number;
  quantity: number;
  capital_used: number;
  capital_used_pct: number;
  max_loss: number;
  limited_by_capital: boolean;
}

export interface PayoffResult {
  grid: [number, number, number][];
  breakevens: number[];
  max_profit: number | null;
  max_loss: number | null;
  net_premium: number;
  greeks: { delta: number; gamma: number; theta: number; vega: number };
}

export interface Secret {
  name: string;
  label: string;
  group: string;
  help: string;
  stored: boolean;
  active: boolean;
  source: "credential_manager" | "environment" | null;
}

export interface AiTool {
  command: string;
  name: string;
  maker: string;
  installed: boolean;
  version: string | null;
  install: string;
  sign_in: string;
}

export interface AgentCli {
  id: string;
  name: string;
  maker: string;
  installed: boolean;
  command: string;
  path: string | null;
  version: string | null;
  authenticated: boolean;
  auth_detail: string;
  auth_env_var: string;
  install_cmd: string;
  signin_cmd: string;
  run_cmd: string;
  description: string;
}

export interface CredentialTestResult {
  valid: boolean;
  provider: string;
  message: string;
}

