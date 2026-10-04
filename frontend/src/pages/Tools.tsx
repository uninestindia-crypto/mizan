import { useQuery } from "@tanstack/react-query";
import { Minus, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, useParams } from "react-router";
import { PayoffChart } from "../components/charts";
import { Button, Callout, Card, CardHeader, cx, Delta, Field, Input, PageHeader, Segmented, Select, Skeleton, Stat } from "../components/ui";
import { errorMessage } from "../lib/api";
import { inr, inrSigned, int, num, pct, tone } from "../lib/format";
import { tools, useStatus } from "../lib/queries";

import { AgentCliBridge } from "../components/AgentCliBridge";

const TOOLS = [
  { id: "costs", label: "Trade costs" },
  { id: "position-size", label: "Position size" },
  { id: "options", label: "Options payoff" },
  { id: "agents", label: "Coding agents" },
];

function useDebounced<T>(value: T, ms = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return debounced;
}

const clean = (value: string) => value.replace(/[^\d.]/g, "");

export default function Tools() {
  const { tool = "costs" } = useParams();
  return (
    <>
      <PageHeader title="Tools" subtitle="Know the numbers before you place an order." />
      <nav aria-label="Tools" className="mb-5 flex gap-1 border-b border-line">
        {TOOLS.map((t) => (
          <NavLink
            key={t.id}
            to={`/tools/${t.id}`}
            className={({ isActive }) =>
              cx("-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition-colors", isActive ? "border-brand text-ink" : "border-transparent text-ink-3 hover:text-ink")
            }
          >
            {t.label}
          </NavLink>
        ))}
      </nav>
      {tool === "position-size" ? <PositionSize /> : tool === "options" ? <OptionsPayoff /> : tool === "agents" ? <AgentCliBridge /> : <Costs />}
    </>
  );
}

// ------------------------------------------------------------------------------ costs

type Segment = "delivery" | "intraday" | "futures" | "options";

function Costs() {
  const [segment, setSegment] = useState<Segment>("delivery");
  const [buy, setBuy] = useState("1500");
  const [sell, setSell] = useState("1530");
  const [qty, setQty] = useState("100");
  const [tradeDate, setTradeDate] = useState(new Date().toISOString().slice(0, 10));
  const input = useDebounced({ segment, buy_price: buy, sell_price: sell, quantity: Number(qty), trade_date: tradeDate });
  const valid = Number(input.buy_price) > 0 && Number(input.sell_price) > 0 && input.quantity > 0;
  const result = useQuery({ queryKey: ["tool-costs", input], queryFn: () => tools.costs(input), enabled: valid, retry: false });
  const data = result.data;

  return (
    <div className="grid gap-5 lg:grid-cols-5">
      <Card className="lg:col-span-2">
        <CardHeader title="Your trade" subtitle="Charges use the NSE rates in force on the trade date, plus your broker's charges from Settings." />
        <div className="space-y-4">
          <Segmented<Segment>
            label="Segment"
            value={segment}
            onChange={setSegment}
            options={[
              { value: "delivery", label: "Delivery" },
              { value: "intraday", label: "Intraday" },
              { value: "futures", label: "Futures" },
              { value: "options", label: "Options" },
            ]}
          />
          <div className="grid grid-cols-2 gap-4">
            <Field label={segment === "options" ? "Buy premium" : "Buy price"} htmlFor="c-buy">
              <Input id="c-buy" prefix="₹" inputMode="decimal" value={buy} onChange={(e) => setBuy(clean(e.target.value))} />
            </Field>
            <Field label={segment === "options" ? "Sell premium" : "Sell price"} htmlFor="c-sell">
              <Input id="c-sell" prefix="₹" inputMode="decimal" value={sell} onChange={(e) => setSell(clean(e.target.value))} />
            </Field>
            <Field label="Quantity" htmlFor="c-qty" hint={segment === "futures" || segment === "options" ? "Lots × lot size" : undefined}>
              <Input id="c-qty" inputMode="numeric" value={qty} onChange={(e) => setQty(e.target.value.replace(/\D/g, ""))} />
            </Field>
            <Field label="Trade date" htmlFor="c-date">
              <Input id="c-date" type="date" min="2020-07-01" value={tradeDate} onChange={(e) => setTradeDate(e.target.value)} />
            </Field>
          </div>
        </div>
      </Card>
      <div className="space-y-5 lg:col-span-3">
        {result.isError && <Callout tone="danger">{errorMessage(result.error)}</Callout>}
        {!valid && <Callout tone="info">Enter both prices and a quantity of at least 1.</Callout>}
        {valid && !data && !result.isError && <Skeleton className="h-64" />}
        {data && (
          <>
            <Card>
              <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
                <Stat label="Profit before charges" value={inrSigned(data.gross_pnl, 2)} tone={tone(data.gross_pnl)} />
                <Stat label="Total charges" value={inr(data.charges)} sub={`${pct(data.charges_pct_of_turnover, 3, false)} of turnover`} />
                <Stat label="Profit after charges" value={inrSigned(data.net_pnl, 2)} tone={tone(data.net_pnl)} />
                <Stat
                  label="Break-even sell price"
                  value={inr(data.breakeven_price)}
                  sub={`Needs ${pct(data.breakeven_move_pct, 2)} move`}
                  hint="The lowest sell price at which you do not lose money once every charge is paid."
                />
              </div>
            </Card>
            <Card padded={false}>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line bg-surface-2/60 text-[12px] font-semibold uppercase tracking-wide text-ink-3">
                    <th className="px-5 py-2.5 text-left">Charge</th>
                    <th className="px-3 py-2.5 text-right">Buy</th>
                    <th className="px-3 py-2.5 text-right">Sell</th>
                    <th className="hidden px-5 py-2.5 text-left sm:table-cell">NSE rule</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {mergeLines(data.buy.lines, data.sell.lines).map((line) => (
                    <tr key={line.label}>
                      <td className="px-5 py-2.5 text-ink-2">{line.label}</td>
                      <td className="num px-3 py-2.5 text-right text-ink">{line.buy === null ? "—" : inr(line.buy)}</td>
                      <td className="num px-3 py-2.5 text-right text-ink">{line.sell === null ? "—" : inr(line.sell)}</td>
                      <td className="hidden px-5 py-2.5 font-mono text-[11.5px] text-ink-3 sm:table-cell">{line.rule}</td>
                    </tr>
                  ))}
                  <tr className="font-semibold">
                    <td className="px-5 py-3 text-ink">Total</td>
                    <td className="num px-3 py-3 text-right text-ink">{inr(data.buy.total)}</td>
                    <td className="num px-3 py-3 text-right text-ink">{inr(data.sell.total)}</td>
                    <td className="hidden sm:table-cell" />
                  </tr>
                </tbody>
              </table>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}

function mergeLines(buy: { label: string; amount: number; rule_id: string }[], sell: { label: string; amount: number; rule_id: string }[]) {
  const labels = [...new Set([...buy.map((l) => l.label), ...sell.map((l) => l.label)])];
  return labels.map((label) => {
    const b = buy.find((l) => l.label === label);
    const s = sell.find((l) => l.label === label);
    return { label, buy: b?.amount ?? null, sell: s?.amount ?? null, rule: b?.rule_id ?? s?.rule_id ?? "" };
  });
}

// ---------------------------------------------------------------------- position size

function PositionSize() {
  const status = useStatus();
  const money = status.data?.settings.money;
  const [capital, setCapital] = useState(money?.capital ?? "1000000");
  const [risk, setRisk] = useState(money?.risk_per_trade_pct ?? "1");
  const [entry, setEntry] = useState("850");
  const [stop, setStop] = useState("820");
  const [lot, setLot] = useState("1");
  const input = useDebounced({ capital, risk_pct: risk, entry, stop, lot_size: Number(lot) || 1 });
  const valid = Number(input.capital) > 0 && Number(input.risk_pct) > 0 && Number(input.entry) > 0 && Number(input.stop) > 0 && input.entry !== input.stop;
  const result = useQuery({ queryKey: ["tool-size", input], queryFn: () => tools.positionSize(input), enabled: valid, retry: false });
  const data = result.data;
  return (
    <div className="grid gap-5 lg:grid-cols-5">
      <Card className="lg:col-span-2">
        <CardHeader title="Your plan" subtitle="Decide where you will exit if you are wrong, then size the position so that exit costs only what you chose to risk." />
        <div className="grid grid-cols-2 gap-4">
          <Field label="Capital" htmlFor="s-cap">
            <Input id="s-cap" prefix="₹" inputMode="numeric" value={capital} onChange={(e) => setCapital(clean(e.target.value))} />
          </Field>
          <Field label="Risk per trade" htmlFor="s-risk">
            <Input id="s-risk" suffix="%" inputMode="decimal" value={risk} onChange={(e) => setRisk(clean(e.target.value))} />
          </Field>
          <Field label="Entry price" htmlFor="s-entry">
            <Input id="s-entry" prefix="₹" inputMode="decimal" value={entry} onChange={(e) => setEntry(clean(e.target.value))} />
          </Field>
          <Field label="Stop-loss price" htmlFor="s-stop">
            <Input id="s-stop" prefix="₹" inputMode="decimal" value={stop} onChange={(e) => setStop(clean(e.target.value))} />
          </Field>
          <Field label="Lot size" htmlFor="s-lot" hint="1 for stocks">
            <Input id="s-lot" inputMode="numeric" value={lot} onChange={(e) => setLot(e.target.value.replace(/\D/g, ""))} />
          </Field>
        </div>
      </Card>
      <div className="space-y-5 lg:col-span-3">
        {result.isError && <Callout tone="danger">{errorMessage(result.error)}</Callout>}
        {!valid && <Callout tone="info">Enter a stop-loss that differs from the entry price.</Callout>}
        {valid && Number(input.stop) > Number(input.entry) && (
          <Callout tone="warn" title="Your stop-loss is above your entry price">
            That means a short sale: you would make money if the price falls. If you meant to buy, put the stop-loss below the entry price.
          </Callout>
        )}
        {data && (
          <Card>
            <div className="text-[13px] text-ink-3">{data.direction === "long" ? "Buy" : "Sell short"}</div>
            <div className="num mt-1 text-5xl font-semibold tracking-tight text-ink">{int(data.quantity)}</div>
            <div className="text-sm text-ink-2">shares</div>
            <div className="mt-6 grid grid-cols-2 gap-6 sm:grid-cols-4">
              <Stat label="Money needed" value={inr(data.capital_used, 0)} sub={`${pct(data.capital_used_pct, 0, false)} of capital`} />
              <Stat label="Loss if stopped out" value={inr(data.max_loss, 0)} tone="down" sub="before charges" />
              <Stat label="Risk per share" value={inr(data.risk_per_share)} />
              <Stat label="Stop distance" value={pct(data.stop_distance_pct, 1, false)} />
            </div>
            {data.limited_by_capital && (
              <Callout tone="warn" className="mt-5">
                Your capital, not your risk rule, limits this position. The stop is close enough that full risk would need more money than you have.
              </Callout>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------- options payoff

interface Leg {
  kind: "call" | "put";
  side: "buy" | "sell";
  strike: string;
  premium: string;
  lots: string;
}

const PRESETS: { id: string; label: string; legs: (spot: number) => Leg[] }[] = [
  { id: "long-call", label: "Buy call", legs: (s) => [{ kind: "call", side: "buy", strike: String(s), premium: "180", lots: "1" }] },
  { id: "long-put", label: "Buy put", legs: (s) => [{ kind: "put", side: "buy", strike: String(s), premium: "170", lots: "1" }] },
  {
    id: "straddle",
    label: "Long straddle",
    legs: (s) => [
      { kind: "call", side: "buy", strike: String(s), premium: "180", lots: "1" },
      { kind: "put", side: "buy", strike: String(s), premium: "170", lots: "1" },
    ],
  },
  {
    id: "bull-spread",
    label: "Bull call spread",
    legs: (s) => [
      { kind: "call", side: "buy", strike: String(s), premium: "180", lots: "1" },
      { kind: "call", side: "sell", strike: String(s + 200), premium: "90", lots: "1" },
    ],
  },
  {
    id: "iron-condor",
    label: "Iron condor",
    legs: (s) => [
      { kind: "put", side: "buy", strike: String(s - 400), premium: "30", lots: "1" },
      { kind: "put", side: "sell", strike: String(s - 200), premium: "70", lots: "1" },
      { kind: "call", side: "sell", strike: String(s + 200), premium: "75", lots: "1" },
      { kind: "call", side: "buy", strike: String(s + 400), premium: "32", lots: "1" },
    ],
  },
];

function OptionsPayoff() {
  const [spot, setSpot] = useState("24000");
  const [days, setDays] = useState("7");
  const [iv, setIv] = useState("14");
  const [lotSize, setLotSize] = useState("75");
  const [legs, setLegs] = useState<Leg[]>(PRESETS[2]!.legs(24000));
  const input = useDebounced({
    spot: Number(spot),
    days_to_expiry: Number(days),
    volatility_pct: Number(iv),
    legs: legs.map((l) => ({ kind: l.kind, side: l.side, strike: Number(l.strike), premium: Number(l.premium), lots: Number(l.lots) || 1, lot_size: Number(lotSize) || 1 })),
  });
  const valid = input.spot > 0 && input.volatility_pct > 0 && input.legs.every((l) => l.strike > 0 && l.premium >= 0);
  const result = useQuery({ queryKey: ["tool-payoff", input], queryFn: () => tools.payoff(input), enabled: valid, retry: false });
  const data = result.data;
  const setLeg = (i: number, patch: Partial<Leg>) => setLegs(legs.map((l, j) => (j === i ? { ...l, ...patch } : l)));

  return (
    <div className="space-y-5">
      <Card>
        <div className="grid gap-4 sm:grid-cols-4">
          <Field label="Underlying price" htmlFor="o-spot">
            <Input id="o-spot" inputMode="decimal" value={spot} onChange={(e) => setSpot(clean(e.target.value))} />
          </Field>
          <Field label="Days to expiry" htmlFor="o-days">
            <Input id="o-days" inputMode="numeric" value={days} onChange={(e) => setDays(e.target.value.replace(/\D/g, ""))} />
          </Field>
          <Field label="Implied volatility" htmlFor="o-iv">
            <Input id="o-iv" suffix="%" inputMode="decimal" value={iv} onChange={(e) => setIv(clean(e.target.value))} />
          </Field>
          <Field label="Lot size" htmlFor="o-lot" hint="NIFTY lot size is set by NSE; check before trading.">
            <Input id="o-lot" inputMode="numeric" value={lotSize} onChange={(e) => setLotSize(e.target.value.replace(/\D/g, ""))} />
          </Field>
        </div>
        <div className="mt-5 flex flex-wrap gap-2">
          {PRESETS.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setLegs(p.legs(Math.round((Number(spot) || 24000) / 50) * 50))}
              className="h-8 rounded-full border border-line bg-surface px-3.5 text-[13px] font-medium text-ink-2 hover:border-line-strong hover:text-ink"
            >
              {p.label}
            </button>
          ))}
        </div>
        <div className="mt-5 space-y-2">
          {legs.map((leg, i) => (
            <div key={i} className="grid grid-cols-2 items-end gap-3 rounded-xl border border-line bg-surface-2/50 p-3 sm:grid-cols-[repeat(5,minmax(0,1fr))_auto]">
              <Field label="Action" htmlFor={`leg-side-${i}`}>
                <Select id={`leg-side-${i}`} value={leg.side} onChange={(e) => setLeg(i, { side: e.target.value as Leg["side"] })}>
                  <option value="buy">Buy</option>
                  <option value="sell">Sell</option>
                </Select>
              </Field>
              <Field label="Type" htmlFor={`leg-kind-${i}`}>
                <Select id={`leg-kind-${i}`} value={leg.kind} onChange={(e) => setLeg(i, { kind: e.target.value as Leg["kind"] })}>
                  <option value="call">Call</option>
                  <option value="put">Put</option>
                </Select>
              </Field>
              <Field label="Strike" htmlFor={`leg-strike-${i}`}>
                <Input id={`leg-strike-${i}`} inputMode="decimal" value={leg.strike} onChange={(e) => setLeg(i, { strike: clean(e.target.value) })} />
              </Field>
              <Field label="Premium" htmlFor={`leg-prem-${i}`}>
                <Input id={`leg-prem-${i}`} prefix="₹" inputMode="decimal" value={leg.premium} onChange={(e) => setLeg(i, { premium: clean(e.target.value) })} />
              </Field>
              <Field label="Lots" htmlFor={`leg-lots-${i}`}>
                <Input id={`leg-lots-${i}`} inputMode="numeric" value={leg.lots} onChange={(e) => setLeg(i, { lots: e.target.value.replace(/\D/g, "") })} />
              </Field>
              <Button variant="ghost" size="md" aria-label={`Remove leg ${i + 1}`} disabled={legs.length === 1} onClick={() => setLegs(legs.filter((_, j) => j !== i))}>
                <Minus className="size-4" aria-hidden />
              </Button>
            </div>
          ))}
          {legs.length < 4 && (
            <Button variant="secondary" size="sm" icon={<Plus className="size-4" aria-hidden />} onClick={() => setLegs([...legs, { kind: "call", side: "buy", strike: spot, premium: "100", lots: "1" }])}>
              Add leg
            </Button>
          )}
        </div>
      </Card>
      {result.isError && <Callout tone="danger">{errorMessage(result.error)}</Callout>}
      {data && (
        <div className="grid gap-5 xl:grid-cols-3">
          <Card className="xl:col-span-2">
            <CardHeader title="Profit and loss" subtitle="Solid: at expiry. Dashed: today (Black-Scholes, 7% interest rate)." />
            <PayoffChart grid={data.grid} breakevens={data.breakevens} spot={Number(spot)} />
          </Card>
          <Card>
            <div className="grid grid-cols-2 gap-5">
              <Stat label="Max profit" value={data.max_profit === null ? "Unlimited" : inrSigned(data.max_profit)} tone={data.max_profit === null ? "up" : tone(data.max_profit)} />
              <Stat label="Max loss" value={data.max_loss === null ? "Unlimited" : inrSigned(data.max_loss)} tone="down" />
              <Stat label={data.net_premium >= 0 ? "You pay" : "You receive"} value={inr(Math.abs(data.net_premium), 0)} />
              <Stat label="Break-even" value={data.breakevens.length ? data.breakevens.map((b) => num(b, 0)).join(" / ") : "—"} />
            </div>
            <div className="mt-6 border-t border-line pt-4">
              <div className="mb-2 text-[12.5px] font-medium text-ink-3">Position Greeks today</div>
              <dl className="grid grid-cols-2 gap-2 text-[13px]">
                {(["delta", "gamma", "theta", "vega"] as const).map((g) => (
                  <div key={g} className="flex justify-between rounded-lg bg-surface-2 px-3 py-2">
                    <dt className="capitalize text-ink-2">{g}</dt>
                    <dd className="num font-medium text-ink">
                      <Delta value={data.greeks[g]}>{num(data.greeks[g], g === "gamma" ? 4 : 2)}</Delta>
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
            {data.max_loss === null && (
              <Callout tone="danger" className="mt-5" title="Unlimited risk">
                This position can lose more than any amount you set aside if the market moves sharply against it.
              </Callout>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
