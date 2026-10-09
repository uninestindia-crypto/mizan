import { RefreshCw } from "lucide-react";
import { useEffect, useRef } from "react";
import { Link } from "react-router";
import { errorMessage } from "../lib/api";
import { dateTime, inr, inrSigned, int, num, pct, tone } from "../lib/format";
import { useBrokerRefresh, useBrokerSnapshot } from "../lib/queries";
import type { BrokerHolding, BrokerPosition } from "../lib/types";
import { RiskCard } from "./RiskCard";
import { Badge, Button, Callout, Card, CardHeader, Delta, Skeleton, Stat } from "./ui";

/** The broker sends percent points (5 means 5%); the shared formatter takes a fraction. */
const points = (value: number | null | undefined) => pct(value == null ? null : value / 100);

/**
 * Portfolio: the account as the broker shows it. View only: nothing here can buy, sell, move money or change anything,
 * and every figure carries the time it was fetched.
 */
export function BrokerAccountCard() {
  const snapshot = useBrokerSnapshot();
  const refresh = useBrokerRefresh();
  const asked = useRef(false);
  const data = snapshot.data;

  // One automatic refresh when the figures are old and the sign-in is still good. The engine limits how often
  // Upstox is asked, so opening the screen again and again does not.
  useEffect(() => {
    if (data?.connected && data.freshness !== "UP_TO_DATE" && !asked.current) {
      asked.current = true;
      refresh.mutate();
    }
  }, [data?.connected, data?.freshness, refresh]);

  if (snapshot.isPending) return <Skeleton className="h-40" />;
  if (snapshot.isError || !data) {
    return (
      <Callout tone="warn" title="Your broker account could not load">
        {snapshot.isError ? errorMessage(snapshot.error) : "Try again in a moment."}
      </Callout>
    );
  }

  const hasFigures = data.fetched_at !== null && data.totals !== null;
  if (!hasFigures) {
    return (
      <Card>
        <CardHeader
          title="From your Upstox account"
          subtitle="View only"
          action={<Badge tone={data.connected ? "brand" : "neutral"}>{data.connected ? "Connected" : "Not connected"}</Badge>}
        />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="max-w-2xl text-sm text-ink-2">
            {data.connected ? (data.message ?? "Fetching your account from Upstox…") : data.message}
          </p>
          <Link to="/settings/broker">
            <Button variant="secondary" size="sm">
              Open Broker view
            </Button>
          </Link>
        </div>
      </Card>
    );
  }

  const totals = data.totals!;
  const holdings = data.holdings;
  const positions = data.positions;
  const skipped = data.skipped.holdings + data.skipped.positions;

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title="From your Upstox account"
          subtitle={`View only · Updated ${dateTime(data.fetched_at)}`}
          action={
            <div className="flex flex-wrap items-center justify-end gap-2">
              <Badge tone={data.freshness === "UP_TO_DATE" ? "up" : "warn"}>{data.freshness === "UP_TO_DATE" ? "Up to date" : "Older"}</Badge>
              {data.connected && (
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<RefreshCw className="size-4" aria-hidden />}
                  loading={refresh.isPending}
                  onClick={() => refresh.mutate()}
                >
                  Refresh
                </Button>
              )}
            </div>
          }
        />

        {data.message && (
          <Callout tone="warn" className="mb-4">
            {data.message}
          </Callout>
        )}

        <div className="grid grid-cols-2 gap-6 lg:grid-cols-5">
          <Stat label="Value of holdings" value={inr(totals.value, 0)} sub={`Invested ${inr(totals.invested, 0)}`} />
          <Stat label="Profit or loss" value={inrSigned(totals.pnl)} tone={tone(totals.pnl)} sub={points(totals.pnl_pct)} />
          <Stat label="Today" value={inrSigned(totals.today)} tone={tone(totals.today)} />
          <Stat label="Cash available" value={inr(data.cash?.available, 0)} sub={data.cash?.in_use != null ? `In use ${inr(data.cash.in_use, 0)}` : undefined} />
          <Stat label="Updated" value={dateTime(data.fetched_at)} sub={data.freshness === "UP_TO_DATE" ? "Up to date" : "Older than 5 minutes"} />
        </div>

        {totals.arriving_note && <p className="mt-3 text-[13px] text-ink-3">{totals.arriving_note}</p>}

        {data.warnings.length > 0 && (
          <Callout tone="warn" title="Too much in one place" className="mt-4">
            <ul className="list-disc space-y-0.5 pl-4">
              {data.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </Callout>
        )}

        {(data.notes.length > 0 || skipped > 0) && (
          <Callout tone="info" className="mt-4">
            <ul className="space-y-0.5">
              {data.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </Callout>
        )}

        <HoldingsTable holdings={holdings} />
        {positions.length > 0 && <PositionsTable positions={positions} />}
      </Card>
      {holdings.length > 0 && <RiskCard source="broker" />}
    </div>
  );
}

function HoldingsTable({ holdings }: { holdings: BrokerHolding[] }) {
  if (holdings.length === 0) {
    return <p className="mt-5 text-sm text-ink-2">Upstox shows no holdings in this account.</p>;
  }
  return (
    <div className="mt-5 overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <caption className="sr-only">Holdings in your Upstox account</caption>
        <thead>
          <tr className="border-y border-line bg-surface-2/60 text-[12px] font-semibold uppercase tracking-wide text-ink-3">
            <th scope="col" className="px-3 py-2.5 text-left">Stock</th>
            <th scope="col" className="px-3 py-2.5 text-right">Qty</th>
            <th scope="col" className="px-3 py-2.5 text-right">Avg price</th>
            <th scope="col" className="px-3 py-2.5 text-right">Last price</th>
            <th scope="col" className="px-3 py-2.5 text-right">Value</th>
            <th scope="col" className="px-3 py-2.5 text-right">Gain</th>
            <th scope="col" className="px-3 py-2.5 text-right">Share</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {holdings.map((holding) => (
            <tr key={`${holding.exchange ?? ""}:${holding.symbol}`}>
              <td className="px-3 py-3 font-semibold text-ink">
                {holding.symbol}
                {holding.t1_quantity > 0 && <div className="text-[12px] font-normal text-ink-3">{int(holding.t1_quantity)} arriving</div>}
              </td>
              <td className="num px-3 py-3 text-right text-ink-2">{int(holding.quantity)}</td>
              <td className="num px-3 py-3 text-right text-ink-2">{num(holding.average_price)}</td>
              <td className="num px-3 py-3 text-right text-ink-2">{num(holding.last_price)}</td>
              <td className="num px-3 py-3 text-right font-medium text-ink">{inr(holding.value, 0)}</td>
              <td className="px-3 py-3 text-right">
                <Delta value={holding.pnl} strong>
                  {inrSigned(holding.pnl)}
                </Delta>
                <div className="num text-[12px] text-ink-3">{points(holding.pnl_pct)}</div>
              </td>
              <td className="num px-3 py-3 text-right text-ink-2">{holding.weight_pct == null ? "—" : `${num(holding.weight_pct, 1)}%`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PositionsTable({ positions }: { positions: BrokerPosition[] }) {
  return (
    <div className="mt-6 overflow-x-auto">
      <h3 className="mb-2 text-[13px] font-semibold text-ink">Open positions</h3>
      <table className="w-full min-w-[520px] text-sm">
        <caption className="sr-only">Open positions in your Upstox account</caption>
        <thead>
          <tr className="border-y border-line bg-surface-2/60 text-[12px] font-semibold uppercase tracking-wide text-ink-3">
            <th scope="col" className="px-3 py-2.5 text-left">Stock</th>
            <th scope="col" className="px-3 py-2.5 text-left">Type</th>
            <th scope="col" className="px-3 py-2.5 text-right">Qty</th>
            <th scope="col" className="px-3 py-2.5 text-right">Last price</th>
            <th scope="col" className="px-3 py-2.5 text-right">Profit or loss</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {positions.map((position) => (
            <tr key={`${position.exchange ?? ""}:${position.symbol}:${position.product}`}>
              <td className="px-3 py-3 font-semibold text-ink">{position.symbol}</td>
              <td className="px-3 py-3 text-ink-2">
                {position.product}
                {position.closed && <span className="text-ink-3"> · closed today</span>}
              </td>
              <td className="num px-3 py-3 text-right text-ink-2">{int(position.quantity)}</td>
              <td className="num px-3 py-3 text-right text-ink-2">{num(position.last_price)}</td>
              <td className="px-3 py-3 text-right">
                <Delta value={position.pnl} strong>
                  {inrSigned(position.pnl)}
                </Delta>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
