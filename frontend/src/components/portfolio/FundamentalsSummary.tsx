import { date, int, num } from "../../lib/format";
import type { PortfolioFundamentals } from "../../lib/fundamentalsTypes";
import { Disclosure } from "../fundamentals/Disclosure";
import { Card, Stat } from "../ui";

const share = (percent: number) => `${num(percent, 1)}%`;

function peStat(data: PortfolioFundamentals) {
  const pe = data.weighted_average_pe;
  const of = `${int(pe.holdings_included)} of ${int(data.holdings_count)} holdings`;
  const sub =
    pe.holdings_included === 0
      ? "Worked out from 0 holdings"
      : `From ${of}, ${share(pe.weight_included_pct)} of the weight`;
  return { value: pe.value === null ? "—" : `${num(pe.value, 2)} times`, sub };
}

function datesLine(data: PortfolioFundamentals): string {
  const d = data.data_dates;
  const parts = [
    d.newest_filing ? `Newest filing: quarter ended ${date(d.newest_filing)}` : null,
    d.oldest_latest_quarter ? `Oldest latest quarter: ${date(d.oldest_latest_quarter)}` : null,
    d.price_date ? `Prices: ${date(d.price_date)}` : null,
  ];
  return parts.filter(Boolean).join(" · ");
}

/** The whole portfolio in a few facts: how many holdings, how concentrated, its P/E, and how old the data is. */
export function FundamentalsSummary({ data }: { data: PortfolioFundamentals }) {
  const pe = peStat(data);
  return (
    <Card>
      <div className="grid grid-cols-2 gap-6 lg:grid-cols-4">
        <Stat label="Holdings" value={int(data.holdings_count)} />
        <Stat label="Weight of the five biggest holdings" value={`${num(data.top5_weight_pct, 1)}%`} />
        <Stat label="P/E of the holdings together" value={pe.value} sub={pe.sub} />
        <Stat
          label="Holdings with old filing data"
          value={`${int(data.stale_count)} of ${int(data.holdings_count)}`}
          sub={`${int(data.without_data_count)} with no filing data`}
        />
      </div>
      <p className="mt-4 text-[12.5px] text-ink-3">{datesLine(data)}</p>
      <div className="mt-2">
        <Disclosure title="How the P/E of the holdings together is worked out">
          <p className="text-ink-2">{data.weighted_average_pe.note}</p>
        </Disclosure>
      </div>
    </Card>
  );
}
