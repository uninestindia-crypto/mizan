import { int, num, pct } from "../lib/format";
import type { LabRanges as Ranges } from "../lib/types";

type Bounds = { low: number | null; high: number | null };

const ROWS: { label: string; get: (r: Ranges) => Bounds; format: (v: number) => string }[] = [
  { label: "Per year (CAGR)", get: (r) => r.cagr, format: (v) => pct(v) },
  { label: "Worst fall", get: (r) => r.max_drawdown, format: (v) => pct(v) },
  { label: "Sharpe ratio", get: (r) => r.sharpe, format: (v) => num(v, 2) },
];

/**
 * How much of a Lab result could be luck of the particular days: the middle 90 of 100 reshuffles of the same days. It
 * sits beside the verdict and never changes it.
 */
export function LabRanges({ ranges }: { ranges: Ranges | null | undefined }) {
  if (!ranges) return null;
  return (
    <section className="mt-5 border-t border-line pt-4" aria-label="How much of this could be luck">
      <h3 className="text-[13px] font-semibold text-ink">How much of this could be luck</h3>
      <p className="mt-0.5 text-[12.5px] text-ink-3">
        The middle {int(Math.round(ranges.level * 100))} of 100 reshuffles of the same {int(ranges.sessions)} days
      </p>
      <dl className="mt-3 space-y-1.5 text-sm">
        {ROWS.map((row) => {
          const { low, high } = row.get(ranges);
          return (
            <div key={row.label} className="flex items-baseline justify-between gap-4">
              <dt className="text-ink-2">{row.label}</dt>
              <dd className="num text-right text-ink">
                {low === null || high === null ? "Not enough movement to say" : `${row.format(low)} to ${row.format(high)}`}
              </dd>
            </div>
          );
        })}
      </dl>
      <p className="mt-3 text-[12.5px] text-ink-3">{ranges.note}</p>
    </section>
  );
}
