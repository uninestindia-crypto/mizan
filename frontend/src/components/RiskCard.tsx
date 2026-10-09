import { errorMessage } from "../lib/api";
import { date, int, num } from "../lib/format";
import { useRisk } from "../lib/queries";
import { Badge, Callout, Card, CardHeader, Skeleton, Stat } from "./ui";

/** A holding that carries at least this many points more of the risk than of the money is called out. */
const HEAVY_BY = 5;

/**
 * How the holdings have moved together over the last year, in plain words: the typical yearly swing of the whole
 * portfolio, how many independent holdings it behaves like, and each holding's share of the risk next to its share of the
 * money. It describes the past; it never forecasts, and the card says so.
 */
export function RiskCard({ source }: { source: "portfolio" | "broker" }) {
  const risk = useRisk(source);

  if (risk.isPending) return <Skeleton className="h-40" />;
  if (risk.isError) {
    return (
      <Callout tone="info" title="How your holdings move together could not load">
        {errorMessage(risk.error)}
      </Callout>
    );
  }
  const data = risk.data;
  if (!data.available || data.volatility_pct === null || data.effective_bets === null || !data.window) {
    return (
      <Card>
        <CardHeader title="How your holdings move together" subtitle="Looks at the past, not the future" />
        <p className="text-sm text-ink-2">{data.message}</p>
        <LeftOut items={data.left_out} />
      </Card>
    );
  }

  const owned = data.diversification?.holdings ?? data.holdings.length;
  const link = data.diversification?.average_correlation ?? null;
  return (
    <Card>
      <CardHeader
        title="How your holdings move together"
        subtitle={`The last ${int(data.window.sessions)} sessions, ${date(data.window.from)} to ${date(data.window.to)} · describes the past, not a forecast`}
      />
      <div className="grid grid-cols-2 gap-6 lg:grid-cols-3">
        <Stat
          label="Typical yearly swing"
          value={`${num(data.volatility_pct, 1)}%`}
          sub="of the whole portfolio"
          hint={`How much the whole portfolio has typically gone up and down in a year, going by how these holdings moved over the last ${int(data.window.sessions)} sessions. A bad year can be worse.`}
        />
        <Stat
          label="Behaves like"
          value={data.effective_bets < 1.05 ? "1 holding" : `${num(data.effective_bets, 1)} holdings`}
          sub={`of the ${int(owned)} you own`}
          hint="If all your holdings moved in lockstep this would be 1. If none of them affected the others it would equal how many you own."
        />
        {link !== null && (
          <Stat
            label="How closely they move together"
            value={num(link, 2)}
            sub="1 is in lockstep, 0 is unrelated"
            hint="The average, over every pair of your holdings, of how closely they have moved together."
          />
        )}
      </div>

      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[420px] text-sm">
          <caption className="sr-only">Each holding's share of the money and of the risk</caption>
          <thead>
            <tr className="border-y border-line bg-surface-2/60 text-[12px] font-semibold uppercase tracking-wide text-ink-3">
              <th scope="col" className="px-3 py-2.5 text-left">Holding</th>
              <th scope="col" className="px-3 py-2.5 text-right">Share of money</th>
              <th scope="col" className="px-3 py-2.5 text-right">Share of risk</th>
              <th scope="col" className="px-3 py-2.5 text-right">
                <span className="sr-only">Note</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {data.holdings.map((row) => (
              <tr key={row.symbol}>
                <td className="px-3 py-3 font-semibold text-ink">{row.symbol}</td>
                <td className="num px-3 py-3 text-right text-ink-2">{num(row.money_pct, 1)}%</td>
                <td className="num px-3 py-3 text-right font-medium text-ink">{num(row.risk_pct, 1)}%</td>
                <td className="px-3 py-3 text-right">
                  {row.risk_pct - row.money_pct >= HEAVY_BY && <Badge tone="warn">More risk than its size</Badge>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <LeftOut items={data.left_out} />
      {data.window.days_left_out > 0 && (
        <p className="mt-3 text-[12.5px] text-ink-3">
          {int(data.window.days_left_out)} {data.window.days_left_out === 1 ? "day" : "days"} with a known break in the price data {data.window.days_left_out === 1 ? "was" : "were"} left out.
        </p>
      )}
      <p className="mt-3 text-[12.5px] text-ink-3">{data.note}</p>
    </Card>
  );
}

function LeftOut({ items }: { items: { symbol: string; reason: string }[] }) {
  if (items.length === 0) return null;
  return (
    <ul className="mt-3 space-y-0.5 text-[12.5px] text-ink-3">
      {items.map((item) => (
        <li key={item.symbol}>
          Left out: {item.symbol}. {item.reason}
        </li>
      ))}
    </ul>
  );
}
