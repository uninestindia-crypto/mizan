import type { FundamentalsMetric } from "../../lib/fundamentalsTypes";
import { MetricCard } from "./MetricCard";

// The figures in the order a person reads them, under plain headings. A figure the engine adds later is not lost:
// it goes under "Other figures".
const GROUPS: { title: string; keys: string[] }[] = [
  { title: "Sales and profit", keys: ["ttm_revenue", "ttm_net_profit", "ttm_eps"] },
  {
    title: "How they have changed",
    keys: [
      "revenue_growth_quarter",
      "profit_growth_quarter",
      "revenue_growth_ttm",
      "profit_growth_ttm",
      "revenue_change_3y",
      "profit_change_3y",
    ],
  },
  { title: "Margins and profit record", keys: ["net_margin", "operating_margin", "profitable_quarters"] },
  { title: "Borrowings and returns", keys: ["interest_cover", "debt_to_equity", "roe"] },
  { title: "Price compared with the company's figures", keys: ["pe", "pb", "earnings_yield"] },
];

function Group({ title, items }: { title: string; items: FundamentalsMetric[] }) {
  if (items.length === 0) return null;
  return (
    <section className="space-y-2.5">
      <h3 className="text-[14.5px] font-semibold text-ink">{title}</h3>
      <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {items.map((metric) => (
          <MetricCard key={metric.key} metric={metric} />
        ))}
      </ul>
    </section>
  );
}

/** Every figure from the filings, each with its label, value, date, formula in words and the numbers behind it. */
export function MetricGroups({ metrics }: { metrics: Record<string, FundamentalsMetric> }) {
  const known = new Set(GROUPS.flatMap((g) => g.keys));
  const others = Object.values(metrics).filter((m) => !known.has(m.key));
  return (
    <div className="space-y-6">
      {GROUPS.map((group) => (
        <Group
          key={group.title}
          title={group.title}
          items={group.keys.flatMap((key) => (metrics[key] ? [metrics[key]] : []))}
        />
      ))}
      <Group title="Other figures" items={others} />
    </div>
  );
}
