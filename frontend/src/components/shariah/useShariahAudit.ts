import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import type { ShariahAudit } from "../../lib/types";

/** One stock's full screening result, with the evidence behind it. Nothing is asked until a stock is chosen. */
export function useShariahAudit(ticker: string | null) {
  return useQuery({
    queryKey: ["shariah", "audit", ticker],
    queryFn: () => api<ShariahAudit>(`/api/v2/shariah/stocks/${encodeURIComponent(ticker ?? "")}/audit`),
    enabled: ticker !== null,
  });
}
