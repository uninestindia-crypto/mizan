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
}

/** Both standards must pass; any failure fails the share, any doubt leaves it questionable. */
export function overallStatus(aaoifi: ScreenStatus, tasis: ScreenStatus): ScreenStatus {
  if (aaoifi === "NON_COMPLIANT" || tasis === "NON_COMPLIANT") return "NON_COMPLIANT";
  if (aaoifi === "QUESTIONABLE" || tasis === "QUESTIONABLE") return "QUESTIONABLE";
  return "COMPLIANT";
}

export function toCompliance(row: ShariahStockRow): ShariahCompliance {
  const status = overallStatus(row.aaoifi_status, row.tasis_status);
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
