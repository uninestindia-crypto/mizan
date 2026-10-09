import { Link } from "react-router";
import { num } from "../../lib/format";
import type { HoldingFundamentals } from "../../lib/fundamentalsTypes";
import { CompanyLine, DataChip } from "../fundamentals/CompanyChips";
import { FigureGrid } from "../fundamentals/FigureGrid";
import { figureText } from "../fundamentals/format";
import { Card, CardHeader } from "../ui";

const SUBTITLE = "Companies file in different months, so each one shows its own latest quarter.";

const figure = (unit: string, value: number | null, key?: string) => figureText({ key, unit, value });

function figuresOf(h: HoldingFundamentals) {
  return [
    { label: "Weight", value: h.weight_pct === null ? "—" : `${num(h.weight_pct, 1)}%` },
    { label: "Quarters with a profit in the last eight", value: figure("quarters", h.profitable_quarters) },
    {
      label: "Profit over four quarters against the four before",
      value: figure("percent", h.profit_growth_ttm_pct, "profit_growth_ttm"),
    },
    { label: "Profit as a share of sales", value: figure("percent", h.net_margin_pct) },
    { label: "Profit as a share of the owners' money (approximate)", value: figure("percent", h.roe_pct) },
    { label: "Borrowings compared with the owners' money", value: figure("times", h.debt_to_equity) },
    { label: "How many times profit covers the interest bill", value: figure("times", h.interest_cover) },
    { label: "Price compared with earnings (P/E)", value: figure("times", h.pe) },
  ];
}

function HoldingCard({ holding: h }: { holding: HoldingFundamentals }) {
  return (
    <li className="space-y-3 rounded-xl border border-line bg-surface p-4" data-symbol={h.symbol}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <Link to={`/stock/${h.symbol}`} className="text-[15px] font-semibold text-ink hover:underline">
          {h.symbol}
        </Link>
        {h.name && <span className="text-[13px] text-ink-2">{h.name}</span>}
        <DataChip status={h.data_status} />
        {h.industry && <span className="text-[12.5px] text-ink-3">{h.industry}</span>}
      </div>
      <CompanyLine latest={h.latest_quarter} counts={h.scorecard_counts} />
      {h.data_status !== "NOT_AVAILABLE" && <FigureGrid figures={figuresOf(h)} />}
    </li>
  );
}

/** Each holding's headline figures from its filings, with how old they are. */
export function FundamentalsHoldings({ holdings }: { holdings: HoldingFundamentals[] }) {
  const shown = holdings.filter((h) => h.data_status !== "NOT_AVAILABLE");
  if (shown.length === 0) return null;
  return (
    <Card>
      <CardHeader title="Each holding, from its own filings" subtitle={SUBTITLE} />
      <ul aria-label="Holdings and their figures" className="space-y-3">
        {shown.map((holding) => (
          <HoldingCard key={holding.symbol} holding={holding} />
        ))}
      </ul>
    </Card>
  );
}
