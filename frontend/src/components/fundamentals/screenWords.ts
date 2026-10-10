import type { ScreenParams } from "../../lib/fundamentalsTypes";

// The words on the filter form. The engine's own sentences (what was applied, the counts, the statement) are shown as
// sent; these are only the names of the boxes, in plain language.

export interface FilterField {
  name: keyof ScreenParams;
  label: string;
  unit?: string;
  hint?: string;
}

export const FILTER_FIELDS: FilterField[] = [
  {
    name: "min_profitable_quarters",
    label: "Quarters with a profit in the last eight, at least",
    hint: "A number from 0 to 8.",
  },
  { name: "min_roe_pct", label: "Profit as a share of the owners' money (approximate), at least", unit: "%" },
  { name: "max_debt_to_equity", label: "Borrowings compared with the owners' money, at most", unit: "times" },
  { name: "min_interest_cover", label: "How many times profit covers the interest bill, at least", unit: "times" },
  {
    name: "min_ttm_profit_growth_pct",
    label: "Profit over four quarters against the four before, at least",
    unit: "%",
  },
  { name: "max_pe", label: "Price compared with earnings (P/E), at most", unit: "times" },
];

export const SECTOR_FIELD: FilterField = {
  name: "sector",
  label: "Industry group contains",
  hint: "Type a few letters of an industry group, for example bank.",
};

/** What a person can sort by: the engine's name for it, and the words for it. */
export const SORT_CHOICES: { value: string; label: string }[] = [
  { value: "symbol", label: "Company symbol (A to Z)" },
  { value: "profitable_quarters", label: "Quarters with a profit in the last eight" },
  { value: "roe_pct", label: "Profit as a share of the owners' money (approximate)" },
  { value: "debt_to_equity", label: "Borrowings compared with the owners' money" },
  { value: "interest_cover", label: "How many times profit covers the interest bill" },
  { value: "ttm_profit_growth_pct", label: "Profit over four quarters against the four before" },
  { value: "pe", label: "Price compared with earnings (P/E)" },
  { value: "net_margin_pct", label: "Profit as a share of sales" },
  { value: "ttm_revenue_inr", label: "Sales over the last four quarters" },
  { value: "ttm_net_profit_inr", label: "Profit over the last four quarters" },
];

export const ORDER_CHOICES: { value: "asc" | "desc"; label: string }[] = [
  { value: "asc", label: "Lowest first" },
  { value: "desc", label: "Highest first" },
];

/** Nothing chosen: the engine's own defaults apply (by symbol, lowest first, 25 results). */
export const EMPTY_PARAMS: ScreenParams = {
  min_profitable_quarters: "",
  min_roe_pct: "",
  max_debt_to_equity: "",
  min_interest_cover: "",
  min_ttm_profit_growth_pct: "",
  max_pe: "",
  sector: "",
  sort: "symbol",
  order: "asc",
  limit: "25",
};

export function sortWords(by: string): string {
  return SORT_CHOICES.find((choice) => choice.value === by)?.label ?? by;
}

export function orderWords(order: string): string {
  return ORDER_CHOICES.find((choice) => choice.value === order)?.label ?? order;
}

/** The names of the filters, for "left out because the company has no figure for ...". */
export const FILTER_NAMES: Record<string, string> = {
  min_profitable_quarters: "quarters with a profit",
  min_roe_pct: "profit as a share of the owners' money",
  max_debt_to_equity: "borrowings compared with the owners' money",
  min_interest_cover: "interest cover",
  min_ttm_profit_growth_pct: "profit over four quarters against the four before",
  max_pe: "price compared with earnings",
  sector: "industry group",
};
