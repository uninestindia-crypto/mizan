import { Badge } from "../ui";

const LABEL: Record<string, string> = {
  UNVERIFIED_SAMPLE: "Illustrative sample, not audited",
  VERIFIED_FILING: "Checked against the company's filing",
  STALE: "Out of date, needs a fresh check",
};

const TONE: Record<string, "warn" | "up"> = {
  UNVERIFIED_SAMPLE: "warn",
  STALE: "warn",
  VERIFIED_FILING: "up",
};

/** What a person reads about the data behind a verdict. Anything this does not know is "Not verified". */
export function dataStatusLabel(status: string | null | undefined): string {
  return (status && LABEL[status]) || "Not verified";
}

/** Goes right beside a verdict, never only in a banner, so a verdict is never read without it. */
export function DataStatusBadge({ status }: { status: string | null | undefined }) {
  const tone = (status && TONE[status]) || "neutral";
  return <Badge tone={tone}>{dataStatusLabel(status)}</Badge>;
}
