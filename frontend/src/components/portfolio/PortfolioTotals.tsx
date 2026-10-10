import { date, inr, inrCompact, inrSigned, pct, tone } from "../../lib/format";
import type { Portfolio } from "../../lib/types";
import { Callout, Card, Stat } from "../ui";

type Totals = NonNullable<Portfolio["totals"]>;

const NIFTY_HINT =
  "What your holdings are worth compared with putting the same money into NIFTYBEES on each buy date, " +
  "both valued on the last day NIFTY data covers.";
const CHARGES_HINT =
  "STT, exchange, SEBI and GST plus your broker's charges from Settings, " +
  "if you sold everything at the last close today.";

/** The figures for whatever is in view: all accounts together, or one account. */
export function PortfolioTotals({ totals, nifty }: { totals: Totals; nifty: Portfolio["nifty"] }) {
  const beat = nifty ? nifty.holdings_value - nifty.nifty_value : null;
  return (
    <Card>
      <div className="grid grid-cols-2 gap-6 lg:grid-cols-5">
        <Stat label="Current value" value={inrCompact(totals.value)} sub={`Invested ${inrCompact(totals.cost)}`} />
        <Stat label="Total gain" value={inrSigned(totals.pnl)} tone={tone(totals.pnl)} sub={pct(totals.pnl_pct)} />
        <Stat label="Today" value={inrSigned(totals.day_change)} tone={tone(totals.day_change)} />
        <Stat label="Charges to sell all" value={inr(totals.exit_charges, 0)} hint={CHARGES_HINT} />
        <Stat
          label="Versus NIFTY"
          value={beat === null ? "—" : inrSigned(beat)}
          tone={tone(beat)}
          sub={nifty ? `Same money, same days · to ${date(nifty.compare_on)}` : "Needs NIFTY data after your buy dates"}
          hint={NIFTY_HINT}
        />
      </div>
    </Card>
  );
}

export function ConcentrationWarnings({ warnings }: { warnings: readonly string[] }) {
  if (warnings.length === 0) return null;
  return (
    <Callout tone="warn" title="Too much in one place">
      <ul className="list-disc space-y-0.5 pl-4">
        {warnings.map((w) => (
          <li key={w}>{w}</li>
        ))}
      </ul>
      <p className="mt-1.5">
        A single stock that large can undo years of gains if something goes wrong with that company.
      </p>
    </Callout>
  );
}
