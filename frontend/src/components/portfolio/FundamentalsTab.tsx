import { errorMessage } from "../../lib/api";
import { usePortfolioFundamentals } from "../../lib/fundamentalsQueries";
import type { PortfolioFundamentals } from "../../lib/fundamentalsTypes";
import { Callout, cx, Skeleton } from "../ui";
import { FundamentalsHoldings } from "./FundamentalsHoldings";
import { FundamentalsNoData } from "./FundamentalsNoData";
import { FundamentalsSummary } from "./FundamentalsSummary";
import type { TabContext } from "./PortfolioTabs";
import { SectorWeights } from "./SectorWeights";

function Loaded({ data, busy }: { data: PortfolioFundamentals; busy: boolean }) {
  return (
    <div aria-busy={busy} className={cx("space-y-5 transition-opacity", busy && "opacity-60")}>
      <div className="space-y-1">
        <p className="text-[13px] text-ink-2">{data.statement}</p>
        <p className="text-[12.5px] text-ink-3">{data.weights_note}</p>
      </div>
      <FundamentalsSummary data={data} />
      <SectorWeights rows={data.sector_weights} />
      <FundamentalsHoldings holdings={data.holdings} />
      <FundamentalsNoData symbols={data.without_data} unpriced={data.holdings_without_value} />
    </div>
  );
}

/** Facts from each company's own filings, beside the holdings in view. It follows the account being viewed. */
export function FundamentalsTab({ choice }: TabContext) {
  const found = usePortfolioFundamentals(choice);
  if (found.isPending) return <Skeleton className="h-64" />;
  if (found.isError) {
    return (
      <Callout tone="danger" title="The fundamentals could not be loaded">
        {errorMessage(found.error)}
      </Callout>
    );
  }
  return <Loaded data={found.data} busy={found.isPlaceholderData} />;
}
