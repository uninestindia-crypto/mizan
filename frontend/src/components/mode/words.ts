import { date } from "../../lib/format";
import type { DataStatus, ShariahStatus, Verdict } from "../../lib/shariahStatus";

// The words a person reads for a Shariah result. Never "certified", "approved" or "guaranteed", and "not screened yet"
// is never worded as "not halal".

export const VERDICT_WORD: Record<Verdict, string> = {
  COMPLIANT: "Compliant",
  NON_COMPLIANT: "Not compliant",
  QUESTIONABLE: "Questionable",
  NOT_SCREENED: "Not screened",
};

/** The short word after the verdict for results that rest on weaker data. A filing-backed result needs none. */
export const DATA_STATUS_SHORT: Partial<Record<DataStatus, string>> = {
  STALE: "old filing",
  UNVERIFIED_SAMPLE: "sample",
};

/** What the result rests on, in a sentence, with the filing's date when it has one. */
export function dataStatusSentence(status: DataStatus, asOf: string | null): string {
  const when = asOf ? `, ${date(asOf)}` : "";
  if (status === "VERIFIED_FILING") return `Screened from the company's own filing${when}`;
  if (status === "STALE") return `Based on an old filing${when}`;
  if (status === "UNVERIFIED_SAMPLE") return "Illustrative sample, not from a filing";
  return "Not screened yet";
}

/** What the result rests on and why, without repeating the verdict word. */
export function detailSentence(status: ShariahStatus): string {
  const base = `${dataStatusSentence(status.data_status, status.as_of)}.`;
  return status.short ? `${base} ${status.short}` : base;
}

/** The hover text: the verdict, what it rests on, and the reason. */
export function statusSentence(status: ShariahStatus): string {
  return `${VERDICT_WORD[status.verdict]}. ${detailSentence(status)}`;
}
