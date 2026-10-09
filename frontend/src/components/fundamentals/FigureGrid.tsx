import type { ReactNode } from "react";

export interface Figure {
  label: string;
  value: ReactNode;
}

/** A row of labelled figures. Plain ink for every figure: nothing is coloured as good or bad. */
export function FigureGrid({ figures }: { figures: Figure[] }) {
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4 xl:grid-cols-7">
      {figures.map((figure) => (
        <div key={figure.label} className="min-w-0">
          <dt className="text-[12px] leading-snug text-ink-3">{figure.label}</dt>
          <dd className="num mt-0.5 text-[14px] font-medium text-ink">{figure.value}</dd>
        </div>
      ))}
    </dl>
  );
}
