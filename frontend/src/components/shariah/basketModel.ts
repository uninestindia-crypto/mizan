// What a basket card says about a price and about what has not been computed. Never a number without its words.

import { inr } from "../../lib/format";
import type { ShariahBasket, ShariahBasketConstituent } from "../../lib/types";

export const NOT_COMPUTED_LEAD = "Not computed yet.";
export const NOT_COMPUTED_FALLBACK = "QuantOS has not back-tested this basket, so no return or risk figure is shown.";
export const NO_REBALANCES = "No rebalances have been recorded yet.";

const NO_PRICE = "No price";
const PRICE_WORDS: Record<string, string> = { SAMPLE: "Sample price", NOT_AVAILABLE: NO_PRICE };

/** "₹4,210.50 · Sample price", or just "Sample price" or "No price". A status nobody knows reads "No price". */
export function priceText(stock: ShariahBasketConstituent): string {
  const words = PRICE_WORDS[stock.price_status ?? ""] ?? NO_PRICE;
  const shown = stock.price_status === "SAMPLE" && typeof stock.current_price === "number";
  return shown ? `${inr(stock.current_price)} · ${words}` : words;
}

/** The sentence under "Not computed yet." Comes from the engine when it sends one. */
export function notComputedMessage(basket: ShariahBasket): string {
  return basket.performance?.message?.trim() || NOT_COMPUTED_FALLBACK;
}

/** Until a rebalance is really recorded there is none to show, so this is the only history line there is. */
export function historyMessage(basket: ShariahBasket): string | null {
  const status = basket.history_status;
  if (status && status !== "NONE_RECORDED") return null;
  return basket.history_message?.trim() || NO_REBALANCES;
}
