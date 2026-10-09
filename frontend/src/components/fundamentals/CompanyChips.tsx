import { date } from "../../lib/format";
import type { DataStatus, FactCounts } from "../../lib/fundamentalsTypes";
import { Badge } from "../ui";
import { basisWords, countsText, dataWords } from "./format";

/** How old a company's data is, as a label. Old data is always labelled; fresh data needs no label of its own. */
export function DataChip({ status }: { status: DataStatus }) {
  if (status === "VERIFIED_FILING") return null;
  return <Badge tone={status === "STALE" ? "warn" : "neutral"}>{dataWords(status)}</Badge>;
}

/** "Latest quarter ended 31 Dec 2024 · Consolidated · 8 inside the rule of thumb, 6 facts" */
export function CompanyLine(props: {
  latest: string | null;
  basis?: "consolidated" | "standalone" | null;
  counts: FactCounts;
}) {
  const parts = [
    props.latest ? `Latest quarter ended ${date(props.latest)}` : "No quarter held",
    basisWords(props.basis ?? null),
    countsText(props.counts),
  ];
  return <p className="text-[12.5px] text-ink-3">{parts.filter(Boolean).join(" · ")}</p>;
}
