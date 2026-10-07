import { useRef, useState } from "react";
import { int } from "../../lib/format";
import type { ShariahCompliance } from "../../lib/types";
import { ScreenerFilters, type ScreenerFilter } from "./ScreenerFilters";
import { ScreenerTable } from "./ScreenerTable";
import { StockResultCard } from "./StockResultCard";

function matches(item: ShariahCompliance, query: string, filter: ScreenerFilter): boolean {
  const q = query.toLowerCase();
  const found = item.symbol.toLowerCase().includes(q) || item.company_name.toLowerCase().includes(q);
  return found && (filter === "ALL" || item.compliance_status === filter);
}

export function ScreenerTab({ summary }: { summary: ShariahCompliance[] }) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<ScreenerFilter>("ALL");
  const [chosen, setChosen] = useState<string | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const shown = summary.filter((item) => matches(item, query, filter));

  const open = (ticker: string, from: HTMLElement) => {
    opener.current = from;
    setChosen(ticker);
  };
  const close = () => {
    setChosen(null);
    opener.current?.focus();
  };

  return (
    <div className="space-y-4">
      {chosen && <StockResultCard key={chosen} ticker={chosen} onClose={close} />}
      <ScreenerFilters filter={filter} onFilter={setFilter} query={query} onQuery={setQuery} />
      <ScreenerTable items={shown} onOpen={open} />
      <p className="text-[12.5px] text-ink-3">
        {int(shown.length)} of {int(summary.length)} sample equities shown, screened against AAOIFI Standard No. 21 and
        TASIS thresholds using the sample figures above.
      </p>
    </div>
  );
}
