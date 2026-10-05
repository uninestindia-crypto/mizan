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

export function useShariahComplianceSummary() {
  return useQuery({
    queryKey: ["shariah", "compliance-summary"],
    queryFn: () => api<ShariahCompliance[]>("/api/v2/shariah/screening/compliance-summary"),
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
