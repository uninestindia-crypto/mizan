import { Link } from "react-router";
import { int } from "../../lib/format";
import { cx } from "../ui";
import { FilingCoverageLine } from "./FilingCoverageLine";
import type { ModeFilter } from "./useModeFilter";

// On a phone the words are small; the invisible box around them is stretched to 40 px so a tap lands.
const TAP =
  "max-md:relative max-md:before:absolute max-md:before:-inset-x-1 max-md:before:-inset-y-3 " +
  "max-md:before:content-['']";
const LINK_BUTTON = `rounded font-semibold text-brand underline-offset-2 hover:underline ${TAP}`;
const WHY = "Not compliant, questionable or not screened yet.";

function HideControl({ filter }: { filter: ModeFilter<unknown> }) {
  return (
    <button type="button" onClick={() => filter.setShowHidden(!filter.showHidden)} className={LINK_BUTTON}>
      {filter.showHidden ? "Hide them again" : "Show them"}
    </button>
  );
}

function NothingLeft({ filter }: { filter: ModeFilter<unknown> }) {
  const reason = filter.note ? `${filter.note} Every stock here counts as not screened, so all ` : "All ";
  return (
    <div className="space-y-1">
      <p aria-live="polite">
        {reason}
        {int(filter.hiddenCount)} {filter.hiddenCount === 1 ? "stock is" : "stocks are"} hidden, because none of them is
        Shariah-compliant.
      </p>
      <p className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <HideControl filter={filter} />
        <Link to="/shariah" className={LINK_BUTTON}>
          Find Shariah-compliant stocks
        </Link>
      </p>
    </div>
  );
}

function Counts({ filter, extra }: { filter: ModeFilter<unknown>; extra?: string }) {
  if (filter.showHidden) {
    return (
      <p aria-live="polite">
        Showing every stock, including {int(filter.hiddenCount)} that {filter.hiddenCount === 1 ? "is" : "are"} not
        confirmed as Shariah-compliant. <HideControl filter={filter} />
      </p>
    );
  }
  return (
    <>
      <p aria-live="polite">
        Showing only Shariah-compliant stocks. {int(filter.hiddenCount)} hidden. <HideControl filter={filter} />
      </p>
      <p className="text-ink-3">{filter.note ?? WHY}</p>
      {extra && <p className="text-ink-3">{extra}</p>}
    </>
  );
}

/**
 * The one control that goes with a list filtered by Shariah mode: how many are hidden, why, and how to see them.
 * Nothing at all in Institutional mode.
 */
export function ModeFilterNote({
  filter,
  className,
  extra,
  coverage = false,
}: {
  filter: ModeFilter<unknown>;
  className?: string;
  /** One more plain sentence shown while stocks are hidden. */
  extra?: string;
  /** Add the "stocks screened from company filings" line. */
  coverage?: boolean;
}) {
  if (!filter.active) return null;
  const style = cx("space-y-1 text-[12.5px] text-ink-2", className);
  if (filter.state === "loading") {
    return filter.total > 0 ? <p className={style} role="status">Checking Shariah status...</p> : null;
  }
  const covered = coverage ? <FilingCoverageLine className="text-ink-3" /> : null;
  if (filter.hiddenCount === 0) return covered ? <div className={style}>{covered}</div> : null;
  return (
    <div className={style} data-testid="mode-filter-note">
      {filter.nothingLeft ? <NothingLeft filter={filter} /> : <Counts filter={filter} extra={extra} />}
      {covered}
    </div>
  );
}
