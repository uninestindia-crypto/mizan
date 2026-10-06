import { Badge } from "../ui";
import type { HalalView, RatioView, StandardView } from "./resultModel";

function RatioList({ ratios }: { ratios: readonly RatioView[] }) {
  if (ratios.length === 0) return null;
  return (
    <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-0.5 text-[12.5px]">
      {ratios.map((ratio) => (
        <div key={ratio.name} className="contents">
          <dt className="text-ink-3">{ratio.name}</dt>
          <dd className="num text-right text-ink">{ratio.line}</dd>
        </div>
      ))}
    </dl>
  );
}

function StandardCard({ standard }: { standard: StandardView }) {
  return (
    <li className="space-y-1.5 rounded-lg border border-line bg-surface px-3 py-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2 text-[13.5px]">
        <span className="font-semibold text-ink">{standard.name}</span>
        <Badge>{standard.status}</Badge>
      </div>
      {standard.summary && <p className="text-[13px] text-ink-2">{standard.summary}</p>}
      <RatioList ratios={standard.ratios} />
    </li>
  );
}

function StandardList({ standards }: { standards: readonly StandardView[] }) {
  if (standards.length === 0) return null;
  return (
    <ul className="space-y-2">
      {standards.map((standard) => (
        <StandardCard key={standard.name} standard={standard} />
      ))}
    </ul>
  );
}

function DataStatus({ halal }: { halal: HalalView }) {
  return (
    <p className="text-[12.5px] text-ink-3">
      Data status: <span className="font-medium text-ink-2">{halal.dataStatus}</span>
      {halal.dataNotice ? `. ${halal.dataNotice}` : ""}
    </p>
  );
}

/** The screener's own result. The AI models do not produce or change anything in this block. */
export function HalalPanel({ halal }: { halal: HalalView }) {
  const note = "text-[13px] text-ink-2";
  return (
    <section
      aria-labelledby="second-opinion-halal"
      className="space-y-3 rounded-xl border border-line bg-surface-2 px-4 py-3"
    >
      <h3 id="second-opinion-halal" className="text-[14px] font-semibold text-ink">
        {halal.heading}
      </h3>
      {halal.message && <p className="text-[13.5px] text-ink-2">{halal.message}</p>}
      <StandardList standards={halal.standards} />
      {halal.disagreement && <p className={note}>The two standards disagree: {halal.disagreement}</p>}
      {halal.purification && <p className={note}>Share of income to purify: {halal.purification}</p>}
      <DataStatus halal={halal} />
      {halal.disclaimer && <p className="text-[12.5px] text-ink-3">{halal.disclaimer}</p>}
    </section>
  );
}
