import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, useLocation } from "react-router";
import { TooltipProvider } from "../ui";
import { routeApi } from "../agents/testHarness";
import { COMPLIANT_ROW, NON_COMPLIANT_ROW, statusFor, statuses, statusUrl } from "../mode/modeKit";

// Shared set-up for the Portfolio account tests: three accounts with holdings, the engine's answer for each view, and
// a page to render into. Numbers are round on purpose so a test can read them.
//
//   My account        TCS 10 shares                     worth 1,200
//   Asha's Zerodha    TCS 5 shares, INFY 20 shares      worth 1,800
//   Papa's HUF        nothing yet                       worth 0

const ASHA = { account_id: 2, account_name: "Asha's Zerodha" };
const MINE = { account_id: 1, account_name: "My account" };
const LOT = { avg_price: 100, buy_date: "2026-01-02", note: "", cost: 1000, close: 120, pnl_pct: 0.2 };

export const LOT_TCS_MINE = { ...LOT, ...MINE, id: 1, symbol: "TCS", quantity: 10, value: 1200, pnl: 200 };
export const LOT_TCS_ASHA = {
  ...LOT,
  ...ASHA,
  id: 2,
  symbol: "TCS",
  quantity: 5,
  cost: 500,
  value: 600,
  pnl: 100,
  buy_date: "2026-02-03",
};
export const LOT_INFY_ASHA = {
  ...LOT,
  ...ASHA,
  id: 3,
  symbol: "INFY",
  quantity: 20,
  avg_price: 50,
  close: 60,
  value: 1200,
  pnl: 200,
};

const ACCOUNT_IDENTITY = [
  { id: 1, name: "My account", owner: "Me", kind: "Demat account", broker: "" },
  { id: 2, name: "Asha's Zerodha", owner: "Asha", kind: "Demat account", broker: "Zerodha" },
  { id: 3, name: "Papa's HUF", owner: "Papa", kind: "HUF account", broker: "" },
];
const FIGURES = [
  { holdings: 1, value: 1200, cost: 1000, pnl: 200, pnl_pct: 0.2, weight: 0.4 },
  { holdings: 2, value: 1800, cost: 1500, pnl: 300, pnl_pct: 0.2, weight: 0.6 },
  { holdings: 0, value: 0, cost: 0, pnl: 0, pnl_pct: null, weight: 0 },
];
export const ACCOUNT_LINES = ACCOUNT_IDENTITY.map((who, i) => ({ ...who, ...FIGURES[i]! }));

const place = (who: typeof ASHA, quantity: number, value: number) => ({ ...who, quantity, value });
const WORTH = { avg_price: 100, close: 120, pnl_pct: 0.2 };
const TCS = { ...WORTH, symbol: "TCS", name: "Tata Consultancy", quantity: 15, cost: 1500, value: 1800, pnl: 300 };
const INFY = { ...WORTH, symbol: "INFY", name: "Infosys", quantity: 20, cost: 1000, value: 1200, pnl: 200 };
const TOTALS = { value: 3000, cost: 2500, pnl: 500, pnl_pct: 0.2, day_change: 15, exit_charges: 40 };
const ASHA_TOTALS = { value: 1800, cost: 1500, pnl: 300, pnl_pct: 0.2, day_change: 9, exit_charges: 25 };
const NO_HOLDINGS = { totals: null, warnings: [], nifty: null, holdings: [], positions: [] };

export const EVERYTHING = {
  scope: { account: "all", name: "All accounts" },
  accounts: ACCOUNT_LINES,
  holdings: [LOT_TCS_MINE, LOT_TCS_ASHA, LOT_INFY_ASHA],
  positions: [
    { ...TCS, weight: 0.6, accounts: [place(MINE, 10, 1200), place(ASHA, 5, 600)] },
    { ...INFY, avg_price: 50, close: 60, weight: 0.4, accounts: [place(ASHA, 20, 1200)] },
  ],
  totals: TOTALS,
  warnings: [],
  nifty: null,
};

export const ASHA_ONLY = {
  ...EVERYTHING,
  scope: { account: 2, name: "Asha's Zerodha" },
  holdings: [LOT_TCS_ASHA, LOT_INFY_ASHA],
  positions: [
    { ...TCS, quantity: 5, cost: 500, value: 600, pnl: 100, weight: 0.33, accounts: [place(ASHA, 5, 600)] },
    { ...INFY, avg_price: 50, close: 60, weight: 0.67, accounts: [place(ASHA, 20, 1200)] },
  ],
  totals: ASHA_TOTALS,
};

export const MINE_ONLY = {
  ...EVERYTHING,
  scope: { account: 1, name: "My account" },
  holdings: [LOT_TCS_MINE],
  positions: [
    { ...TCS, quantity: 10, cost: 1000, value: 1200, pnl: 200, weight: 1, accounts: [place(MINE, 10, 1200)] },
  ],
  totals: { value: 1200, cost: 1000, pnl: 200, pnl_pct: 0.2, day_change: 6, exit_charges: 15 },
};
export const HUF_ONLY = { ...EVERYTHING, ...NO_HOLDINGS, scope: { account: 3, name: "Papa's HUF" } };

const EMPTIED = { holdings: 0, value: 0, cost: 0, pnl: 0, pnl_pct: null, weight: 0 };
export const NOTHING_AT_ALL = {
  ...EVERYTHING,
  ...NO_HOLDINGS,
  accounts: ACCOUNT_LINES.map((a) => ({ ...a, ...EMPTIED })),
};

/** What "GET /api/v2/accounts" says: each account with how many holdings it has, and the kinds to choose from. */
export const KINDS = [
  "Demat account",
  "Trading account",
  "Mutual fund account",
  "Retirement account",
  "Child's account",
  "HUF account",
  "Company account",
  "Other",
];
export const ACCOUNT_LIST = {
  accounts: ACCOUNT_LINES.map(({ id, name, owner, kind, broker, holdings }) => ({
    id,
    name,
    owner,
    kind,
    broker,
    holdings,
  })),
  kinds: KINDS,
};

const MARKET = {
  "GET /api/v2/portfolio": EVERYTHING,
  "GET /api/v2/portfolio?account=1": MINE_ONLY,
  "GET /api/v2/portfolio?account=2": ASHA_ONLY,
  "GET /api/v2/portfolio?account=3": HUF_ONLY,
  "GET /api/v2/accounts": ACCOUNT_LIST,
};
const SHARIAH = statuses({ TCS: COMPLIANT_ROW, INFY: NON_COMPLIANT_ROW });

/** The engine as it answers when everything is fine. `more` adds to or replaces any answer. */
export function engine(more: Record<string, unknown> = {}, shariah = false) {
  routeApi({
    "GET /api/v2/status": statusFor(shariah),
    [statusUrl("INFY", "TCS")]: SHARIAH,
    ...MARKET,
    ...more,
  });
}

function Where() {
  const where = useLocation();
  return <span data-testid="where">{where.pathname + where.search}</span>;
}

const QUIET = { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } };

export function renderAt(ui: ReactElement, path = "/portfolio") {
  const client = new QueryClient({ defaultOptions: QUIET });
  const view = render(
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <MemoryRouter initialEntries={[path]}>
          {ui}
          <Where />
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  );
  return { client, ...view };
}
