import { date } from "../../lib/format";
import { useCompanyFundamentals } from "../../lib/fundamentalsQueries";
import type { CompanyFundamentals, QuarterFacts } from "../../lib/fundamentalsTypes";
import { friendlyDates } from "../../lib/plainDates";
import { errorMessage } from "../../lib/api";
import { Callout, Card, Skeleton } from "../ui";
import { CopyFingerprint } from "../proof/CopyFingerprint";
import { DataNotice } from "./DataNotice";
import { Disclosure } from "./Disclosure";
import { FilingLink } from "./FilingLink";
import { GetResults } from "./GetResults";
import { MetricGroups } from "./MetricGroups";
import { QuarterNotes } from "./QuarterNotes";
import { ScorecardView } from "./ScorecardView";
import { exactRupees, figureText } from "./format";

const TITLE = "Results from the company's own filings";

function LatestQuarter({ quarter, basis }: { quarter: QuarterFacts; basis: string | null }) {
  const rows: [string, string][] = [
    ["Sales in the quarter", figureText({ unit: "INR", value: quarter.revenue_inr })],
    ["Profit in the quarter", figureText({ unit: "INR", value: quarter.net_profit_inr })],
    ["Earnings per share in the quarter", figureText({ unit: "INR per share", value: quarter.eps })],
  ];
  const exact = exactRupees(quarter.revenue_inr);
  return (
    <section aria-labelledby="fund-latest" className="space-y-3 rounded-xl border border-line bg-surface-2 p-4">
      <h3 id="fund-latest" className="text-[14.5px] font-semibold text-ink">
        The latest quarter held
      </h3>
      <p className="text-[13px] text-ink-2">
        {friendlyDates(quarter.period_label)}
        {quarter.filed_on ? `, filed on ${date(quarter.filed_on)}` : ""}
        {quarter.audited === null ? "" : quarter.audited ? ", audited" : ", not audited"}
        {basis ? `. ${basis}.` : "."}
      </p>
      <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-3">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt className="text-[12.5px] text-ink-3">{label}</dt>
            <dd className="num text-[15px] font-semibold text-ink">{value}</dd>
          </div>
        ))}
      </dl>
      {exact && <p className="num text-[12px] text-ink-3">Sales in full: {exact}</p>}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[13px]">
        <FilingLink url={quarter.filing_url}>Open the filing</FilingLink>
        {quarter.sha256 && <CopyFingerprint hash={quarter.sha256} />}
      </div>
    </section>
  );
}

function About({ data }: { data: CompanyFundamentals }) {
  const parts = [data.company_name, data.industry ? `Industry group: ${data.industry}` : null, data.basis.label];
  const line = parts.filter(Boolean).join(" · ");
  return line ? <p className="text-[13px] text-ink-2">{line}</p> : null;
}

function NotCovered({ items }: { items: string[] }) {
  if (items.length === 0) return null;
  return (
    <Disclosure title="What these figures do not cover">
      <ul className="list-disc space-y-1 pl-5 text-ink-2">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </Disclosure>
  );
}

function Results({ data }: { data: CompanyFundamentals }) {
  const held = data.latest_quarter !== null;
  return (
    <div className="space-y-5">
      <About data={data} />
      <DataNotice status={data.data_status} notice={data.data_notice} />
      <GetResults symbol={data.symbol} />
      {held && data.latest_quarter && <LatestQuarter quarter={data.latest_quarter} basis={data.basis.label} />}
      {held && <ScorecardView card={data.scorecard} />}
      {held && <MetricGroups metrics={data.metrics} />}
      <QuarterNotes series={data.series} />
      <NotCovered items={data.not_covered} />
    </div>
  );
}

function Body({ symbol }: { symbol: string }) {
  const found = useCompanyFundamentals(symbol);
  if (found.isPending) {
    return (
      <div className="space-y-3" role="status">
        <Skeleton className="h-16" />
        <p className="text-[13px] text-ink-3">Loading the results from the company's filings...</p>
      </div>
    );
  }
  if (found.isError) {
    return (
      <Callout tone="danger" title="The results could not be loaded">
        {errorMessage(found.error)}
      </Callout>
    );
  }
  return <Results data={found.data} />;
}

/** The long-term facts about one company, from its own filings, with the proof beside each figure. */
export function FundamentalsSection({ symbol }: { symbol: string }) {
  const found = useCompanyFundamentals(symbol);
  return (
    <Card as="section">
      <div id="fundamentals" role="region" aria-labelledby="fund-title" className="scroll-mt-4 space-y-4">
        <div>
          <h2 id="fund-title" className="text-[15px] font-semibold text-ink">
            {TITLE}
          </h2>
          <p className="mt-0.5 text-[13px] text-ink-3">{found.data?.statement ?? ""}</p>
        </div>
        <Body symbol={symbol} />
      </div>
    </Card>
  );
}
