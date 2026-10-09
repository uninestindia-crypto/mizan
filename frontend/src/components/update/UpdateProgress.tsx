import { Loader2 } from "lucide-react";
import { Callout, ProgressBar } from "../ui";
import { type InstallStatus, percentOf, stepWords } from "./updateInstall";

/** A step that is moving: its words, a bar when the engine knows how far along it is, and the percentage beside it. */
function Moving({ status }: { status: InstallStatus }) {
  const percent = percentOf(status);
  return (
    <div className="space-y-2">
      <p role="status" className="flex items-center gap-2 text-[13.5px] text-ink">
        <Loader2 className="size-4 shrink-0 animate-spin text-brand" aria-hidden />
        {stepWords(status)}
      </p>
      {status.state === "downloading" && percent !== null && (
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <ProgressBar value={percent / 100} label="Download progress" />
          </div>
          <span className="num w-10 text-right text-[12.5px] text-ink-2" aria-hidden>
            {percent}%
          </span>
        </div>
      )}
    </div>
  );
}

/**
 * Where an update has got to. Installing is not an error: QuantOS is about to close and open again by itself, so the
 * connection dropping afterwards is expected and nothing here ever reports it.
 */
export function UpdateProgress({ status }: { status: InstallStatus }) {
  if (status.state === "failed") {
    return (
      <Callout tone="danger" title="The update did not finish">
        {stepWords(status)}
      </Callout>
    );
  }
  if (status.state === "installing") {
    return (
      <Callout tone="info">
        <span role="status">{stepWords(status)}</span>
      </Callout>
    );
  }
  if (status.state === "downloading" || status.state === "checking") return <Moving status={status} />;
  return null;
}
