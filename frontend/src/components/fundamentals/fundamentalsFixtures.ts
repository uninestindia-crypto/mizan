import type {
  PositionLots,
  CompanyFundamentals,
  CompareAnswer,
  PortfolioFundamentals,
  ScreenAnswer,
} from "../../lib/fundamentalsTypes";
import type { PortfolioPosition } from "../../lib/types";
import data from "./fundamentalsFixtures.data.json";

// What the real engine sends, built from the engine's own code over its own test filings (see
// tests/fundamentals): a company with fresh figures, the same company with old figures, one with nothing held, one
// with a quarter that failed its check, real TCS filings, a bank, a screen, comparisons and a portfolio.
// Only for tests. Nothing here is made up by hand, except that each filing's fingerprint (a public hash, not a secret) is
// swapped for a simple stand-in, so a secret scanner does not mistake the file for one.

const as = <T>(value: unknown): T => value as T;

export const COMPANY_FRESH = as<CompanyFundamentals>(data.company_fresh);
export const COMPANY_STALE = as<CompanyFundamentals>(data.company_stale);
export const COMPANY_NONE = as<CompanyFundamentals>(data.company_none);
export const COMPANY_EXCLUDED = as<CompanyFundamentals>(data.company_excluded);
export const COMPANY_TCS = as<CompanyFundamentals>(data.company_tcs);
export const COMPANY_BANK = as<CompanyFundamentals>(data.company_bank);

export const SCREEN_ROE = as<ScreenAnswer>(data.screen_roe);
export const SCREEN_ALL = as<ScreenAnswer>(data.screen_all);
export const SCREEN_STALE = as<ScreenAnswer>(data.screen_stale);

export const COMPARE_OK = as<CompareAnswer>(data.compare_ok);
export const COMPARE_MIXED = as<CompareAnswer>(data.compare_mixed);
export const COMPARE_GAPS = as<CompareAnswer>(data.compare_gaps);
export const COMPARE_ONE_BASIS = as<CompareAnswer>(data.compare_one_basis_only);

export const PORTFOLIO_ALL = as<PortfolioFundamentals>(data.portfolio_all);
export const PORTFOLIO_STALE = as<PortfolioFundamentals>(data.portfolio_stale);
export const PORTFOLIO_EMPTY = as<PortfolioFundamentals>(data.portfolio_empty);

/** Positions as the portfolio sends them, with each purchase and how long it has been held (as of 9 Oct 2026). */
export const POSITIONS_LOTS = as<(PortfolioPosition & PositionLots)[]>(data.positions_lots);
