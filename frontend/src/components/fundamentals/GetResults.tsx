import { Button, ProgressBar } from "../ui";
import { type GetResults as Reading, useGetResults } from "./useGetResults";

const TAP = "min-h-10 md:min-h-0";
const FINISHED = "Finished. The results on this page have been refreshed.";

function Failures({ reading }: { reading: Reading }) {
  // A reason that is the same sentence as the message above it is not said twice.
  const reasons = reading.failures.filter((f) => f.reason !== reading.message);
  if (reasons.length === 0) return null;
  return (
    <ul aria-label="What went wrong" className="list-disc space-y-0.5 pl-5 text-[13px] text-ink-2">
      {reasons.map((f, at) => (
        <li key={`${f.symbol}-${at}`}>
          {f.symbol ? `${f.symbol}: ` : ""}
          {f.reason}
        </li>
      ))}
    </ul>
  );
}

function Working({ reading }: { reading: Reading }) {
  const known = reading.total > 0;
  return (
    <div className="space-y-2" aria-live="polite">
      <p className="text-[13px] font-medium text-ink">
        Reading the company's results{known ? `: filing ${reading.done} of ${reading.total}` : "…"}
      </p>
      {reading.message && <p className="text-[13px] text-ink-2">{reading.message}</p>}
      {known && <ProgressBar value={reading.done / reading.total} label="Reading the company's results" />}
      <Button variant="secondary" size="sm" onClick={reading.cancel} loading={reading.cancelling} className={TAP}>
        Stop reading
      </Button>
      <p className="text-[12.5px] text-ink-3">Filings already read are kept, even if you stop.</p>
    </div>
  );
}

const ENDED: Record<string, string> = {
  done: FINISHED,
  cancelled: "Stopped. Filings already read are kept.",
  failed: "The results could not be read.",
  refused: "QuantOS could not start reading.",
};

function Ended({ reading }: { reading: Reading }) {
  return (
    <div className="space-y-2" role="status" aria-live="polite">
      <p className="text-[13px] font-medium text-ink">{ENDED[reading.phase]}</p>
      {reading.message && <p className="text-[13px] text-ink-2">{reading.message}</p>}
      <Failures reading={reading} />
      <Button variant="secondary" size="sm" onClick={reading.start} className={TAP}>
        {reading.phase === "done" ? "Get them again" : "Try again"}
      </Button>
    </div>
  );
}

/**
 * One button that has QuantOS read this company's latest quarterly results from NSE: with progress, a way to stop,
 * the reasons in plain words when something fails, and the page refreshed when it is done.
 */
export function GetResults({ symbol }: { symbol: string }) {
  const reading = useGetResults(symbol);
  if (reading.phase === "idle") {
    return (
      <div className="space-y-2">
        <Button onClick={reading.start} className={TAP}>
          Get the latest results
        </Button>
        <p className="text-[12.5px] text-ink-3">
          QuantOS reads this company's quarterly results from NSE, one filing at a time, so it can take a while. It
          changes nothing else.
        </p>
      </div>
    );
  }
  if (reading.phase === "starting" || reading.phase === "running") return <Working reading={reading} />;
  return <Ended reading={reading} />;
}
