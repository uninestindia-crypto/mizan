import { num } from "../../lib/format";
import type { SectorWeight } from "../../lib/fundamentalsTypes";
import { Card, CardHeader } from "../ui";

function Row({ row }: { row: SectorWeight }) {
  const width = Math.max(0, Math.min(100, row.weight_pct));
  return (
    <li className="space-y-1">
      <div className="flex items-baseline justify-between gap-3 text-[13.5px]">
        <span className="min-w-0 truncate text-ink">{row.sector}</span>
        <span className="num shrink-0 text-ink-2">{num(row.weight_pct, 1)}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-3" aria-hidden>
        <div className="h-full rounded-full bg-ink-3" style={{ width: `${width}%` }} />
      </div>
    </li>
  );
}

/** How much of the holdings sits in each industry group, as the engine worked it out. */
export function SectorWeights({ rows }: { rows: SectorWeight[] }) {
  if (rows.length === 0) return null;
  return (
    <Card>
      <CardHeader title="Weight by industry group" subtitle="Each group's share of the value of the holdings in view" />
      <ul aria-label="Weight by industry group" className="space-y-3">
        {rows.map((row) => (
          <Row key={row.sector} row={row} />
        ))}
      </ul>
    </Card>
  );
}
