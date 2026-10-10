import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "./api";
import type { ShariahBasket, ZakatCalculationResult, ShariahCompliance } from "./types";

export interface ShariahSummary {
  status: string;
  storage_mode: string;
  companies_seeded: number;
}

export function useShariahStatus() {
  return useQuery({
    queryKey: ["shariah", "health"],
    queryFn: () => api<ShariahSummary>("/api/v2/shariah/health"),
  });
}

export function useShariahBaskets() {
  return useQuery({
    queryKey: ["shariah", "baskets"],
    queryFn: () => api<ShariahBasket[]>("/api/v2/shariah/baskets"),
  });
}

type ScreenStatus = "COMPLIANT" | "QUESTIONABLE" | "NON_COMPLIANT";

/** One row of /api/v2/shariah/stocks, the fields the screener reads. */
interface ShariahStockRow {
  ticker: string;
  symbol: string;
  company_name: string;
  aaoifi_status: ScreenStatus;
  tasis_status: ScreenStatus;
  aaoifi_debt_ratio: number;
  aaoifi_cash_ratio: number;
  purification_ratio: number;
  /** New: what a check backs. An older response lacks it and the screen says "Not verified". */
  data_status?: string | null;
  /** The engine's own verdict for this row, when it sends one. An older response lacks it. */
  overall_status?: string | null;
}

const SCREEN_STATUSES: readonly string[] = ["COMPLIANT", "QUESTIONABLE", "NON_COMPLIANT"];

/**
 * One verdict from the two standards, by the same rule as the engine's proof (the Shariah proof contract): a share is
 * not compliant only when both standards say so, compliant only when both pass, and questionable in every other case,
 * including when the two disagree. That is what the badge beside every symbol says, so this screen must say it too.
 *
 * When the engine has already worked out the verdict for this very row (`engine`), that one stands: it knows things the
 * two statuses cannot show, such as a business it could not confirm or a standard it could not work out. A value this
 * app does not know is ignored, never trusted.
 */
export function overallStatus(aaoifi: ScreenStatus, tasis: ScreenStatus, engine?: string | null): ScreenStatus {
  if (engine && SCREEN_STATUSES.includes(engine)) return engine as ScreenStatus;
  if (aaoifi === "NON_COMPLIANT" && tasis === "NON_COMPLIANT") return "NON_COMPLIANT";
  if (aaoifi === "COMPLIANT" && tasis === "COMPLIANT") return "COMPLIANT";
  return "QUESTIONABLE";
}

export function toCompliance(row: ShariahStockRow): ShariahCompliance {
  const status = overallStatus(row.aaoifi_status, row.tasis_status, row.overall_status);
  return {
    ticker: row.ticker,
    symbol: row.symbol,
    company_name: row.company_name,
    is_compliant: status === "COMPLIANT",
    aaoifi_compliant: row.aaoifi_status === "COMPLIANT",
    tasis_compliant: row.tasis_status === "COMPLIANT",
    aaoifi_status: row.aaoifi_status,
    tasis_status: row.tasis_status,
    debt_ratio: row.aaoifi_debt_ratio,
    cash_ratio: row.aaoifi_cash_ratio,
    purification_ratio: row.purification_ratio,
    compliance_status: status,
    data_status: row.data_status ?? null,
  };
}

const PAGE = 100;

/** The screener's list. It reads the stock listing page by page; there is no separate summary route. */
export function useShariahComplianceSummary() {
  return useQuery({
    queryKey: ["shariah", "compliance-summary"],
    queryFn: async () => {
      const rows: ShariahStockRow[] = [];
      for (;;) {
        const page = await api<{ total: number; items: ShariahStockRow[] }>(
          `/api/v2/shariah/stocks?limit=${PAGE}&offset=${rows.length}`,
        );
        rows.push(...page.items);
        if (page.items.length === 0 || rows.length >= page.total) break;
      }
      return rows.map(toCompliance);
    },
  });
}

export function useZakatCalculate() {
  return useMutation({
    mutationFn: (variables: { portfolio_value: number; calculation_method?: string; cash_balance?: number }) =>
      api<ZakatCalculationResult>("/api/v2/shariah/zakat/calculate", "POST", variables),
  });
}

export function usePurificationCalculate() {
  return useMutation({
    mutationFn: (variables: { dividend_amount: number; impermissible_ratio: number }) =>
      api<{ purification_due: number; payable: number }>("/api/v2/shariah/purification/calculate", "POST", variables),
  });
}
