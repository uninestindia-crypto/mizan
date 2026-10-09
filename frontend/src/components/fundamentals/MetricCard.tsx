import { date } from "../../lib/format";
import type { FundamentalsMetric } from "../../lib/fundamentalsTypes";
import { friendlyDates } from "../../lib/plainDates";
import { Badge } from "../ui";
import { Disclosure } from "./Disclosure";
import { exactRupees, figureText } from "./format";
import { ProofList } from "./ProofList";

function Value({ metric }: { metric: FundamentalsMetric }) {
  if (!metric.available) {
    return (
      <p className="text-[13.5px] text-ink-2">
        <span className="font-medium text-ink">Not available.</span> {metric.reason}
      </p>
    );
  }
  const exact = metric.unit === "INR" ? exactRupees(metric.value) : null;
  return (
    <div>
      <p className="num text-xl font-semibold tracking-tight text-ink">
        {figureText(metric)}
        {metric.approximate && <Badge className="ml-2 align-middle">Approximate</Badge>}
      </p>
      {exact && <p className="num text-[12px] text-ink-3">{exact}</p>}
    </div>
  );
}

function When({ metric }: { metric: FundamentalsMetric }) {
  if (!metric.available) return null;
  const period = metric.period ? friendlyDates(metric.period) : null;
  const text = [period, metric.as_of ? `as of ${date(metric.as_of)}` : null].filter(Boolean).join(", ");
  return text ? <p className="text-[12.5px] text-ink-3">{text}</p> : null;
}

/** One figure from the filings: its plain label, its value and date, how it is worked out, and where to check it. */
export function MetricCard({ metric }: { metric: FundamentalsMetric }) {
  return (
    <li className="space-y-2 rounded-xl border border-line bg-surface p-4" data-metric={metric.key}>
      <h4 className="text-[13.5px] font-medium text-ink-2">{metric.label}</h4>
      <Value metric={metric} />
      <When metric={metric} />
      {metric.note && <p className="text-[12.5px] text-ink-3">{metric.note}</p>}
      <Disclosure title="How this is worked out">
        <div className="space-y-3">
          <p className="text-[13px] text-ink-2">{metric.formula}</p>
          <ProofList inputs={metric.inputs} />
        </div>
      </Disclosure>
    </li>
  );
}
