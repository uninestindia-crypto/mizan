import { UsersRound } from "lucide-react";
import { openSecondOpinion } from "../../lib/copilot";
import { readyWords, useReadyRuns } from "./readyRuns";

const CHIP_STYLE =
  "relative flex h-8 shrink-0 items-center gap-2 whitespace-nowrap rounded-[var(--radius-control)] border " +
  "border-brand/40 bg-brand-soft px-2.5 text-[12.5px] font-medium text-brand transition-colors hover:border-brand";
const WORDS_STYLE = "hidden @min-[1100px]:inline";

/**
 * A second opinion finished while its window was closed. The sentence is announced politely to a screen reader, and
 * a small button beside the Copilot button reopens the window. Nothing is shown when nothing has finished.
 */
export function SecondOpinionReady() {
  const [first] = useReadyRuns();
  const words = first ? readyWords(first) : "";
  return (
    <>
      <span role="status" className="sr-only">
        {words}
      </span>
      {first && (
        <button
          type="button"
          onClick={() => openSecondOpinion(first.symbol)}
          title={words}
          aria-label={words}
          className={CHIP_STYLE}
        >
          <UsersRound className="size-3.5" aria-hidden />
          <span className={WORDS_STYLE}>
            {first.outcome === "done" ? "Second opinion ready, open it" : "Second opinion stopped, open it"}
          </span>
        </button>
      )}
    </>
  );
}
