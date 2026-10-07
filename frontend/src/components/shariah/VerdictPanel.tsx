import { ChevronDown } from "lucide-react";
import { useId, useMemo, useState } from "react";
import type { ShariahAudit } from "../../lib/types";
import { cx } from "../ui";
import { DataStatusBadge } from "./dataStatus";
import { StandardSection } from "./StandardSection";
import { buildVerdictView, type VerdictView } from "./verdictModel";

const SUB = "text-[13.5px] font-semibold text-ink";

function SectorSection({ sector }: { sector: VerdictView["sector"] }) {
  return (
    <section aria-label="Business line test" className="space-y-1">
      <h4 className={SUB}>The business-line test</h4>
      <p className="text-[13px] text-ink">{sector.heading}</p>
      {sector.detail && <p className="text-[13px] text-ink-2">{sector.detail}</p>}
    </section>
  );
}

function SourcesSection({ view }: { view: VerdictView }) {
  return (
    <section aria-label="Where the figures come from" className="space-y-1.5">
      <h4 className={SUB}>Where the figures come from</h4>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-[13px]">
        {view.sources.map((row) => (
          <div key={row.label} className="contents">
            <dt className="text-ink-3">{row.label}</dt>
            <dd className="break-words text-ink">{row.value}</dd>
          </div>
        ))}
        <dt className="text-ink-3">Data status</dt>
        <dd>
          <DataStatusBadge status={view.dataStatus} />
        </dd>
      </dl>
      {view.dataNotice && <p className="text-[13px] text-ink-2">{view.dataNotice}</p>}
    </section>
  );
}

function WhenSection({ view }: { view: VerdictView }) {
  if (!view.screenedAt && !view.methodology) return null;
  const rules = view.methodology ? `, using rules version ${view.methodology}` : "";
  return (
    <p className="text-[13px] text-ink-2">
      {view.screenedAt ? `Screened at ${view.screenedAt}` : "Screened"}
      {rules}.
    </p>
  );
}

function NotCoveredSection({ lines }: { lines: string[] }) {
  if (lines.length === 0) return null;
  return (
    <section aria-label="What this result does not cover" className="space-y-1">
      <h4 className={SUB}>What this result does not cover</h4>
      <ul className="list-disc space-y-0.5 pl-5 text-[13px] text-ink-2">
        {lines.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </section>
  );
}

/** Closed until one click. Shows only what the response has: an older response leaves out what it lacks. */
export function VerdictPanel({ audit }: { audit: ShariahAudit }) {
  const [open, setOpen] = useState(false);
  const bodyId = useId();
  const view = useMemo(() => buildVerdictView(audit), [audit]);
  return (
    <div className="rounded-xl border border-line bg-surface-2">
      <h3 className="text-[14px] font-semibold text-ink">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={bodyId}
          onClick={() => setOpen((was) => !was)}
          className="flex w-full items-center justify-between gap-3 rounded-xl px-4 py-3 text-left"
        >
          How this verdict was reached
          <ChevronDown className={cx("size-4 shrink-0 transition-transform", open && "rotate-180")} aria-hidden />
        </button>
      </h3>
      <div id={bodyId} hidden={!open} className="space-y-4 border-t border-line px-4 py-4">
        {view.standards.map((standard) => (
          <StandardSection key={standard.name} standard={standard} />
        ))}
        <SectorSection sector={view.sector} />
        <SourcesSection view={view} />
        <WhenSection view={view} />
        <NotCoveredSection lines={view.notCovered} />
        <p className="text-[13px] font-medium text-ink">A screening aid, not a religious ruling (fatwa)</p>
      </div>
    </div>
  );
}
