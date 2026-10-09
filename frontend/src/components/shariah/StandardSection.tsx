import { Badge } from "../ui";
import { STANDARD_LABEL, STANDARD_TONE } from "./labels";
import type { RatioState, RatioView, StandardView } from "./verdictModel";

const STATE_TONE: Record<RatioState, "up" | "warn" | "down"> = { within: "up", close: "warn", over: "down" };
const STATE_LABEL: Record<RatioState, string> = {
  within: "Within the limit",
  close: "Close to the limit",
  over: "Over the limit",
};

function RatioItem({ ratio }: { ratio: RatioView }) {
  return (
    <li className="space-y-1 break-words rounded-lg border border-line bg-surface px-3 py-2.5 text-[13px]">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold text-ink">{ratio.name}</span>
        <Badge tone={STATE_TONE[ratio.state]}>{STATE_LABEL[ratio.state]}</Badge>
      </div>
      <p className="text-ink-2">{ratio.formula}</p>
      <p className="num text-ink">{ratio.figures}</p>
      <p className="text-ink-2">
        Limit: {ratio.limit}. {ratio.headroom}
      </p>
    </li>
  );
}

/** One standard: its verdict, the one-line reason, and each ratio so a person can redo the sum. */
export function StandardSection({ standard }: { standard: StandardView }) {
  const heading = `${standard.name}: ${STANDARD_LABEL[standard.status]}`;
  return (
    <section aria-label={heading} className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-[13.5px] font-semibold text-ink">{standard.name}</h4>
        <Badge tone={STANDARD_TONE[standard.status]}>{STANDARD_LABEL[standard.status]}</Badge>
      </div>
      <p className="text-[13px] text-ink-2">{standard.reason}</p>
      <ul className="space-y-2">
        {standard.ratios.map((ratio) => (
          <RatioItem key={ratio.key} ratio={ratio} />
        ))}
      </ul>
    </section>
  );
}
