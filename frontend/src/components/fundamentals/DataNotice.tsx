import type { DataStatus } from "../../lib/fundamentalsTypes";
import { Callout } from "../ui";

/**
 * How old the filing data is, or why there is none, in the engine's own sentence. Old data is labelled as old, and the
 * label is never left out.
 */
export function DataNotice({ status, notice }: { status: DataStatus; notice: string }) {
  if (status === "STALE") {
    return (
      <Callout tone="warn" title="Old data">
        {notice}
      </Callout>
    );
  }
  if (status === "NOT_AVAILABLE") return <Callout tone="info">{notice}</Callout>;
  return <p className="text-[13px] text-ink-2">{notice}</p>;
}
