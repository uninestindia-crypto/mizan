import { RiskCard } from "../RiskCard";
import type { TabContext } from "./PortfolioTabs";

/** How the holdings in view have moved together: the swing of the whole portfolio and each holding's share of the risk. */
export function RiskTab({ choice }: TabContext) {
  return <RiskCard source="portfolio" account={choice} />;
}
