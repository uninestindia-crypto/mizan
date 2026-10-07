import { CircleCheck, CircleHelp, CircleX, TriangleAlert } from "lucide-react";
import { Link } from "react-router";
import type { ShariahStatus, Verdict } from "../../lib/shariahStatus";
import { Badge, cx } from "../ui";
import { DATA_STATUS_SHORT, detailSentence, statusSentence, VERDICT_WORD } from "./words";

type Tone = "up" | "down" | "warn" | "neutral";

const LOOK: Record<Verdict, { tone: Tone; icon: typeof CircleCheck }> = {
  COMPLIANT: { tone: "up", icon: CircleCheck },
  NON_COMPLIANT: { tone: "down", icon: CircleX },
  QUESTIONABLE: { tone: "warn", icon: TriangleAlert },
  NOT_SCREENED: { tone: "neutral", icon: CircleHelp },
};

/** Where a badge goes when clicked: the stock's page, with the Shariah screening open. */
export function proofPath(symbol: string): string {
  return `/stock/${encodeURIComponent(symbol)}#shariah-proof`;
}

// On a phone the badge's own box is small; this widens the area that answers a tap to 40 px without moving anything.
const TAP_AREA = "relative before:absolute before:-inset-x-1 before:-inset-y-2.5 before:content-['']";

function Face({ status, compact }: { status: ShariahStatus; compact: boolean }) {
  const { tone, icon: Icon } = LOOK[status.verdict];
  const qualifier = DATA_STATUS_SHORT[status.data_status];
  const size = compact ? "gap-1 px-1.5 py-0 text-[11px]" : "gap-1.5 px-2.5 py-0.5 text-[12.5px]";
  return (
    <Badge tone={tone} className={cx("font-semibold", size)}>
      <Icon className={compact ? "size-3 shrink-0" : "size-3.5 shrink-0"} aria-hidden />
      <span>{VERDICT_WORD[status.verdict]}</span>
      {qualifier && <span className="font-normal">· {qualifier}</span>}
    </Badge>
  );
}

/**
 * The Shariah result for one stock: an icon and words, never colour alone. The data it rests on is in the hover text
 * and in what a screen reader hears. With `symbol` it links to that stock's screening; inside a row that is already a
 * link it is plain text instead, because a link cannot sit inside a link.
 */
export function ShariahBadge({
  status,
  symbol,
  compact = false,
}: {
  status: ShariahStatus | null | undefined;
  /** Makes the badge a link to this stock's screening. Leave out inside something that already links. */
  symbol?: string;
  compact?: boolean;
}) {
  if (!status) return null;
  const hover = statusSentence(status);
  const detail = detailSentence(status);
  if (!symbol) {
    return (
      <span title={hover} className="inline-flex shrink-0">
        <Face status={status} compact={compact} />
        <span className="sr-only">. {detail}</span>
      </span>
    );
  }
  return (
    <Link to={proofPath(symbol)} title={hover} className={cx("inline-flex shrink-0 rounded-full", TAP_AREA)}>
      <Face status={status} compact={compact} />
      <span className="sr-only">
        . {detail} Open the Shariah screening for {symbol}.
      </span>
    </Link>
  );
}
