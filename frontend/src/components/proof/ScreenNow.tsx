import { Button, ProgressBar } from "../ui";
import { useScreenNow } from "./useScreenNow";

const TAP = "min-h-10 md:min-h-0";
const UPDATED = "Finished. The screening has been updated.";
const COULD_NOT_USE = "Finished, but this stock could not be screened from it.";

function Working({ screen }: { screen: ReturnType<typeof useScreenNow> }) {
  const known = screen.total > 0;
  return (
    <div className="space-y-2" aria-live="polite">
      <p className="text-[13px] font-medium text-ink">
        Reading the company's filing{known ? `: ${screen.done} of ${screen.total}` : "…"}
      </p>
      {screen.message && <p className="text-[13px] text-ink-2">{screen.message}</p>}
      {known && <ProgressBar value={screen.done / screen.total} label="Reading the company's filing" />}
      <Button variant="secondary" size="sm" onClick={screen.cancel} loading={screen.cancelling} className={TAP}>
        Cancel
      </Button>
    </div>
  );
}

function Ended({ screen }: { screen: ReturnType<typeof useScreenNow> }) {
  const finished = screen.reason ? COULD_NOT_USE : UPDATED;
  const words: Record<string, string> = {
    done: finished,
    cancelled: "Stopped. Nothing was changed.",
    failed: "The filing could not be read.",
    busy: "",
  };
  return (
    <div className="space-y-2" aria-live="polite" role="status">
      <p className="text-[13px] font-medium text-ink">{words[screen.phase]}</p>
      {screen.message && <p className="text-[13px] text-ink-2">{screen.message}</p>}
      {screen.reason && <p className="text-[13px] text-ink-2">{screen.reason}</p>}
      {screen.phase !== "done" && (
        <Button variant="secondary" size="sm" onClick={screen.start} className={TAP}>
          Try again
        </Button>
      )}
    </div>
  );
}

/** One button that has QuantOS read this company's latest filing from NSE, with progress, and a way to stop. */
export function ScreenNow({ symbol }: { symbol: string }) {
  const screen = useScreenNow(symbol);
  if (screen.phase === "idle") {
    return (
      <div className="space-y-2">
        <Button onClick={screen.start} className={TAP}>
          Screen this stock now
        </Button>
        <p className="text-[12.5px] text-ink-3">
          QuantOS reads the company's latest results filing from NSE. It takes a minute and changes nothing else.
        </p>
      </div>
    );
  }
  if (screen.phase === "starting" || screen.phase === "running") return <Working screen={screen} />;
  return <Ended screen={screen} />;
}
