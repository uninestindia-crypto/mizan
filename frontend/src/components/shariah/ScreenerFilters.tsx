import { Search } from "lucide-react";
import { Segmented } from "../ui";

export type ScreenerFilter = "ALL" | "COMPLIANT" | "NON_COMPLIANT";

const OPTIONS: { value: ScreenerFilter; label: string }[] = [
  { value: "ALL", label: "All Equities" },
  { value: "COMPLIANT", label: "Compliant Only" },
  { value: "NON_COMPLIANT", label: "Non-Compliant" },
];

const SEARCH_ICON = "pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-3";
const SEARCH =
  "h-10 w-full rounded-[var(--radius-control)] border border-line bg-surface pl-9 pr-3 text-sm text-ink " +
  "placeholder:text-ink-3 focus:border-brand focus:outline-none focus:ring-3 focus:ring-brand/15";

export function ScreenerFilters(props: {
  filter: ScreenerFilter;
  onFilter: (filter: ScreenerFilter) => void;
  query: string;
  onQuery: (query: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <Segmented<ScreenerFilter>
        label="Compliance filter"
        value={props.filter}
        onChange={props.onFilter}
        options={OPTIONS}
      />
      <div className="relative w-full sm:w-72">
        <Search className={SEARCH_ICON} aria-hidden />
        <input
          type="text"
          value={props.query}
          onChange={(e) => props.onQuery(e.target.value)}
          placeholder="Search company or symbol..."
          aria-label="Search company or symbol"
          className={SEARCH}
        />
      </div>
    </div>
  );
}
