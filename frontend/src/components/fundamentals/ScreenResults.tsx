import { Link } from "react-router";
import { date, int, plural } from "../../lib/format";
import type { DataDates, ScreenAnswer, ScreenRow } from "../../lib/fundamentalsTypes";
import { Callout, Card, cx } from "../ui";
import { CompanyLine, DataChip } from "./CompanyChips";
import { FigureGrid } from "./FigureGrid";
import { figureText } from "./format";
import { FILTER_NAMES, orderWords, sortWords } from "./screenWords";

function Counts({ answer }: { answer: ScreenAnswer }) {
  const cells: [string, number][] = [
    ["Companies considered", answer.considered],
    ["Left out for missing data", answer.excluded_missing_data],
    ["Left out by your filters", answer.excluded_by_filters],
    ["Match your filters", answer.matched],
  ];
  return (
    <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {cells.map(([label, value]) => (
        <div key={label}>
          <dt className="text-[12.5px] text-ink-3">{label}</dt>
          <dd className="num mt-0.5 text-xl font-semibold text-ink">{int(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function MissingBy({ missing }: { missing: Record<string, number> }) {
  const parts = Object.entries(missing).map(([name, n]) => `${FILTER_NAMES[name] ?? name} (${int(n)})`);
  if (parts.length === 0) return null;
  return (
    <p className="text-[13px] text-ink-2">
      <span className="font-medium text-ink">Left out because the company has no figure for: </span>
      {parts.join(", ")}.
    </p>
  );
}

function FiltersChosen({ answer }: { answer: ScreenAnswer }) {
  if (answer.filters_applied.length === 0) {
    return <p className="text-[13px] text-ink-2">No filters were chosen, so every company is listed.</p>;
  }
  return (
    <ul aria-label="Filters you chose" className="list-disc space-y-0.5 pl-5 text-[13px] text-ink-2">
      {answer.filters_applied.map((f) => (
        <li key={f.filter}>{f.plain}</li>
      ))}
    </ul>
  );
}

function Applied({ answer }: { answer: ScreenAnswer }) {
  const sorted = `Sorted by: ${sortWords(answer.sort.by)}. Order: ${orderWords(answer.sort.order).toLowerCase()}.`;
  return (
    <div className="space-y-1">
      <FiltersChosen answer={answer} />
      <p className="text-[12.5px] text-ink-3">
        {sorted} Showing {int(answer.returned)} of {int(answer.matched)}.
      </p>
    </div>
  );
}

function datesLine(d: DataDates): string {
  const parts = [
    d.newest_filing ? `Newest filing: quarter ended ${date(d.newest_filing)}` : null,
    d.oldest_latest_quarter ? `Oldest latest quarter: ${date(d.oldest_latest_quarter)}` : null,
    d.price_date ? `Prices: ${date(d.price_date)}` : null,
    d.snapshot_built_on ? `Filings gathered: ${date(d.snapshot_built_on)}` : null,
  ];
  return parts.filter(Boolean).join(" · ");
}

function figuresOf(r: ScreenRow) {
  const f = (unit: string, value: number | null, key?: string) => figureText({ key, unit, value });
  return [
    { label: "Quarters with a profit in the last eight", value: f("quarters", r.profitable_quarters) },
    { label: "Profit as a share of the owners' money (approximate)", value: f("percent", r.roe_pct) },
    { label: "Borrowings compared with the owners' money", value: f("times", r.debt_to_equity) },
    { label: "How many times profit covers the interest bill", value: f("times", r.interest_cover) },
    {
      label: "Profit over four quarters against the four before",
      value: f("percent", r.ttm_profit_growth_pct, "profit_growth_ttm"),
    },
    { label: "Price compared with earnings (P/E)", value: f("times", r.pe) },
    { label: "Profit as a share of sales", value: f("percent", r.net_margin_pct) },
    { label: "Sales over the last four quarters", value: f("INR", r.ttm_revenue_inr) },
    { label: "Profit over the last four quarters", value: f("INR", r.ttm_net_profit_inr) },
  ];
}

function ResultCard({ row }: { row: ScreenRow }) {
  return (
    <li className="space-y-3 rounded-xl border border-line bg-surface p-4" data-symbol={row.symbol}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <Link to={`/stock/${row.symbol}`} className="text-[15px] font-semibold text-ink hover:underline">
          {row.symbol}
        </Link>
        {row.company_name && <span className="text-[13px] text-ink-2">{row.company_name}</span>}
        <DataChip status={row.data_status} />
        {row.industry && <span className="text-[12.5px] text-ink-3">{row.industry}</span>}
      </div>
      <CompanyLine latest={row.latest_quarter} basis={row.basis} counts={row.scorecard_counts} />
      <FigureGrid figures={figuresOf(row)} />
    </li>
  );
}

function Stale({ answer }: { answer: ScreenAnswer }) {
  if (answer.stale_in_results === 0) return null;
  return (
    <Callout tone="warn" title="Old data">
      {plural(answer.stale_in_results, "company", "companies")} in these results{" "}
      {answer.stale_in_results === 1 ? "has" : "have"} filing data that is old. Each one is labelled below with its
      latest quarter.
    </Callout>
  );
}

/**
 * The companies that meet the filters a person chose. The statement, the counts and the list of filters are the
 * engine's own. Nothing is ranked or marked as better, and no figure is coloured as good or bad.
 */
export function ScreenResults({ answer, busy }: { answer: ScreenAnswer; busy: boolean }) {
  return (
    <div aria-busy={busy} className={cx("space-y-4 transition-opacity", busy && "opacity-60")}>
      <Card>
        <p className="mb-4 text-[14px] font-medium text-ink">{answer.statement}</p>
        <Counts answer={answer} />
        <div className="mt-4 space-y-3">
          <Applied answer={answer} />
          <MissingBy missing={answer.missing_by_filter} />
          <p className="text-[12.5px] text-ink-3">{datesLine(answer.data_dates)}</p>
        </div>
      </Card>
      <Stale answer={answer} />
      <ul aria-label="Companies that meet your filters" className="space-y-3">
        {answer.results.map((row) => (
          <ResultCard key={row.symbol} row={row} />
        ))}
      </ul>
      {answer.results.length === 0 && (
        <p className="text-[14px] text-ink-2">No company meets all the filters you chose.</p>
      )}
    </div>
  );
}
