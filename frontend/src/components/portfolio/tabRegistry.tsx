import { FundamentalsTab } from "./FundamentalsTab";
import { HoldingsTab } from "./HoldingsTab";
import type { PortfolioTab } from "./PortfolioTabs";

/**
 * The tabs of the Portfolio, in the order they appear. This list is the one place to add a tab:
 *
 *   { id: "dividends", label: "Dividends", render: (context) => <DividendsTab {...context} /> }
 */
export const PORTFOLIO_TABS: readonly PortfolioTab[] = [
  { id: "holdings", label: "Holdings", render: (context) => <HoldingsTab {...context} /> },
  { id: "fundamentals", label: "Fundamentals", render: (context) => <FundamentalsTab {...context} /> },
];
