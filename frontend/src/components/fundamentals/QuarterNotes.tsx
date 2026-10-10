import { date } from "../../lib/format";
import type { ExcludedQuarter, QuarterSeries } from "../../lib/fundamentalsTypes";
import { friendlyDates } from "../../lib/plainDates";
import { excludedWords } from "./format";

function Excluded({ quarters }: { quarters: ExcludedQuarter[] }) {
  if (quarters.length === 0) return null;
  return (
    <section aria-labelledby="fund-excluded" className="space-y-2 rounded-xl border border-line bg-surface-2 p-4">
      <h3 id="fund-excluded" className="text-[14.5px] font-semibold text-ink">
        Quarters left out
      </h3>
      <p className="text-[13px] text-ink-2">
        These quarters were read, but they did not pass QuantOS's own checks, so none of the figures above uses them.
      </p>
      <ul className="space-y-1.5 text-[13px]">
        {quarters.map((q) => (
          <li key={q.period_end} className="text-ink-2">
            <span className="font-medium text-ink">Quarter ended {date(q.period_end)}: </span>
            {excludedWords(q.status)}. {friendlyDates(q.reason)}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Gaps({ gaps }: { gaps: string[] }) {
  if (gaps.length === 0) return null;
  return (
    <p className="text-[13px] text-ink-2">
      <span className="font-medium text-ink">No filing is held for: </span>
      {gaps.map((day) => `quarter ended ${date(day)}`).join(", ")}.
    </p>
  );
}

function Notes({ notes }: { notes: string[] }) {
  if (notes.length === 0) return null;
  return (
    <ul className="list-disc space-y-0.5 pl-5 text-[13px] text-ink-2">
      {notes.map((note) => (
        <li key={note}>{friendlyDates(note)}</li>
      ))}
    </ul>
  );
}

/** What the filings could not give: quarters read but left out (with the reason), quarters missing, and notes. */
export function QuarterNotes({ series }: { series: QuarterSeries }) {
  const left = new Set(series.excluded.map((q) => q.period_end)); // already listed above, with their reason
  return (
    <div className="space-y-3">
      <Excluded quarters={series.excluded} />
      <Gaps gaps={series.gaps.filter((day) => !left.has(day))} />
      <Notes notes={series.notes} />
    </div>
  );
}
