import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type {
  CompanyFundamentals,
  CompareAnswer,
  PortfolioFundamentals,
  ScreenAnswer,
  ScreenParams,
} from "./fundamentalsTypes";

// Reading fundamentals from the engine. Everything here is read-only; reading a company's results from NSE is a
// separate, started-by-a-button job (see components/fundamentals/useGetResults.ts).

export const FUNDAMENTALS_KEY = ["fundamentals"] as const;
const FIVE_MINUTES = 5 * 60_000;

/** The engine accepts two to four companies in one comparison. */
export const COMPARE_MIN = 2;
export const COMPARE_MAX = 4;

export const companyKey = (symbol: string) => [...FUNDAMENTALS_KEY, "company", symbol.toUpperCase()] as const;

export function companyUrl(symbol: string): string {
  return `/api/v2/fundamentals/${encodeURIComponent(symbol.toUpperCase())}`;
}

export function portfolioUrl(account: string): string {
  return `/api/v2/portfolio/fundamentals?account=${encodeURIComponent(account)}`;
}

export function compareUrl(symbols: readonly string[]): string {
  return `/api/v2/fundamentals/compare?symbols=${symbols.map((s) => encodeURIComponent(s.toUpperCase())).join(",")}`;
}

/** The screen's address: only what the person chose, so the engine's own defaults apply to the rest. */
export function screenUrl(params: ScreenParams): string {
  const query = new URLSearchParams();
  for (const [name, text] of Object.entries(params)) {
    const value = String(text).trim();
    if (value !== "") query.set(name, value);
  }
  return `/api/v2/fundamentals/screen?${query.toString()}`;
}

export function useCompanyFundamentals(symbol: string) {
  return useQuery({
    queryKey: companyKey(symbol),
    queryFn: () => api<CompanyFundamentals>(companyUrl(symbol)),
    staleTime: FIVE_MINUTES,
    retry: false,
  });
}

/** The holdings in view. Follows the account: "all" or the account's number. */
export function usePortfolioFundamentals(account: string) {
  return useQuery({
    queryKey: [...FUNDAMENTALS_KEY, "portfolio", account] as const,
    queryFn: () => api<PortfolioFundamentals>(portfolioUrl(account)),
    placeholderData: keepPreviousData,
    retry: false,
  });
}

/** Runs the screen only once the person has pressed the button (`params` is null until then). */
export function useFundamentalsScreen(params: ScreenParams | null) {
  return useQuery({
    queryKey: [...FUNDAMENTALS_KEY, "screen", params] as const,
    queryFn: () => api<ScreenAnswer>(screenUrl(params as ScreenParams)),
    enabled: params !== null,
    placeholderData: keepPreviousData,
    retry: false,
  });
}

/** Compares the companies once there are enough of them (`symbols` is null until the person presses the button). */
export function useFundamentalsCompare(symbols: readonly string[] | null) {
  return useQuery({
    queryKey: [...FUNDAMENTALS_KEY, "compare", symbols] as const,
    queryFn: () => api<CompareAnswer>(compareUrl(symbols ?? [])),
    enabled: symbols !== null && symbols.length >= COMPARE_MIN,
    placeholderData: keepPreviousData,
    retry: false,
  });
}
