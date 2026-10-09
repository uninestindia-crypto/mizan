import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { api } from "../../lib/api";
import { useStatus, useUpdate } from "../../lib/queries";
import { useInstallStatus } from "../update/useInstallUpdate";
import { buildStatusItems, type LivePrices, type StatusItem } from "./statusItems";

const MINUTE = 60_000;

/** The clock, looked at again every half minute so "Market closed" turns into "Pre-open" without a reload. */
export function useNow(everyMs = MINUTE / 2): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), everyMs);
    return () => window.clearInterval(timer);
  }, [everyMs]);
  return now;
}

/** Whether live prices can be asked for. Quiet when the engine cannot say: the chip is then simply not shown. */
export function useLivePrices() {
  return useQuery({
    queryKey: ["copilot", "status", "live-prices"],
    queryFn: async () => (await api<{ live_prices: LivePrices }>("/api/v2/copilot/status")).live_prices,
    staleTime: MINUTE,
    refetchInterval: MINUTE,
    refetchOnWindowFocus: true,
    retry: false,
  });
}

/** Everything the top bar has to say right now, ready to show as chips or as rows. */
export function useStatusItems(): StatusItem[] {
  const now = useNow();
  const status = useStatus().data;
  const live = useLivePrices().data;
  const update = useUpdate().data;
  const install = useInstallStatus(Boolean(update?.update_available)).data;
  return useMemo(() => buildStatusItems({ now, status, live, update, install }), [now, status, live, update, install]);
}
