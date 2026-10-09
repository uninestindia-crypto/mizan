import { ArrowUpCircle, Clock, Database, type LucideIcon, Zap, ZapOff } from "lucide-react";
import type { Status, UpdateInfo } from "../../lib/types";
import { chipWords, type InstallStatus, isWorking } from "../update/updateInstall";
import { type ChipTone, type MarketStatus, marketStatus } from "./marketHours";
import { freshness } from "./priceFreshness";

// What the top bar tells a person, as plain data: one item per thing worth saying. The bar shows each as a chip, and
// the "Status" popover on a narrow bar shows the same items as rows. An item with nothing to say is left out.

export type ItemId = "market" | "prices" | "live" | "update";

export interface StatusItem {
  id: ItemId;
  label: string;
  /** The longer sentence: the chip's tooltip, and the line under the label in the popover. */
  detail: string;
  tone: ChipTone;
  icon: LucideIcon;
  /** An item is a link to a screen... */
  to?: string;
  /** ...or a button that opens the update window. */
  action?: "update";
  /** True when the person may want to do something about it, so the narrow "Status" button carries a dot. */
  attention: boolean;
}

/** What GET /api/v2/copilot/status says about live prices: a broker key is saved and has not run out. */
export interface LivePrices {
  ready: boolean;
  message: string | null;
}

export interface StatusInputs {
  now: Date;
  status: Status | undefined;
  live: LivePrices | undefined;
  update: UpdateInfo | undefined;
  install: InstallStatus | undefined;
}

const DATA_SCREEN = "/settings/data";
const KEYS_SCREEN = "/settings/accounts";
const NOT_CONNECTED =
  "Live prices are not connected yet. Open Settings, then Accounts and keys, to add your Upstox key.";

function marketItem(market: MarketStatus): StatusItem {
  const { label, detail, tone } = market;
  return { id: "market", label, detail, tone, icon: Clock, to: "/markets", attention: false };
}

function pricesItem(status: Status, now: Date): StatusItem {
  const base = { id: "prices", icon: Database, to: DATA_SCREEN } as const;
  const { download, index } = status;
  if (download.state === "RUNNING") {
    const label = `Getting prices, ${download.done} of ${download.total}`;
    const detail = "QuantOS is getting market prices. You can keep using it.";
    return { ...base, label, detail, tone: "brand", attention: false };
  }
  if (index.job.state === "RUNNING") {
    const detail = "QuantOS is getting its prices ready.";
    return { ...base, label: "Preparing prices", detail, tone: "brand", attention: false };
  }
  const fresh = freshness(index.ready ? index.latest_session : null, now);
  const tone = fresh.kind === "current" ? "ok" : "warn";
  return { ...base, label: fresh.label, detail: fresh.detail, tone, attention: fresh.kind !== "current" };
}

function liveItem(live: LivePrices, market: MarketStatus): StatusItem {
  const base = { id: "live", to: KEYS_SCREEN, attention: false } as const;
  if (!live.ready) {
    const detail = live.message || NOT_CONNECTED;
    return { ...base, label: "Live prices off", detail, tone: "neutral", icon: ZapOff };
  }
  const trading = market.phase === "hours" || market.phase === "pre-open";
  if (trading) {
    return { ...base, label: "Live prices on", detail: "Live prices are connected.", tone: "ok", icon: Zap };
  }
  const detail = "Live prices are connected. The market is closed, so prices show the last close until it opens.";
  return { ...base, label: "Prices: last close", detail, tone: "neutral", icon: Zap };
}

function updateItem(update: UpdateInfo | undefined, install: InstallStatus | undefined): StatusItem | null {
  const stopped = install?.state === "failed";
  const available = Boolean(update?.update_available && update.latest);
  if (!available && !isWorking(install)) return null;
  const latest = update?.latest ?? install?.version ?? null;
  const detail = stopped
    ? "The update did not finish. Open this to see why and try again."
    : `QuantOS ${latest ?? "has an update"} is ready. Open this to see what is new and update.`;
  return {
    id: "update",
    label: chipWords(install, latest),
    detail,
    tone: stopped ? "warn" : "brand",
    icon: ArrowUpCircle,
    action: "update",
    attention: true,
  };
}

export function buildStatusItems(inputs: StatusInputs): StatusItem[] {
  const { now, status, live, update, install } = inputs;
  const market = marketStatus(now);
  const items: (StatusItem | null)[] = [
    marketItem(market),
    status ? pricesItem(status, now) : null,
    live ? liveItem(live, market) : null,
    updateItem(update, install),
  ];
  return items.filter((item): item is StatusItem => item !== null);
}

/** The labels of everything that may need doing, so the narrow "Status" button says it in words, not by a dot. */
export function attentionLabels(items: readonly StatusItem[]): string[] {
  return items.filter((item) => item.attention).map((item) => item.label);
}

/**
 * The one item the narrow bar's button speaks for: an update that is waiting or under way first, then prices that are
 * out of date or missing, otherwise the market itself. Anything else is one click away in the list.
 */
export function headline(items: readonly StatusItem[]): StatusItem | undefined {
  const update = items.find((item) => item.id === "update");
  const attention = items.find((item) => item.attention);
  return update ?? attention ?? items.find((item) => item.id === "market") ?? items[0];
}
