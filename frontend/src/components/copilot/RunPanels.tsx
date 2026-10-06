import { useMemo } from "react";
import type { ProviderOption } from "../../lib/copilot";
import { Button, Callout, ProgressBar, Spinner } from "../ui";
import { buildResultView } from "./resultModel";
import { ResultView } from "./ResultView";
import { progressFraction, progressLabel, type RunState } from "./verifyState";

/** While the models are answering: how many answers are in, and a way to stop waiting. */
export function Waiting({ run, onCancel }: { run: RunState; onCancel: () => void }) {
  const starting = run.phase === "starting";
  return (
    <div className="space-y-4">
      {starting ? (
        <Spinner label="Starting the check" />
      ) : (
        <>
          <ProgressBar value={progressFraction(run.progress)} label="Answers from the AI models" />
          <p role="status" className="text-[14px] text-ink">
            {progressLabel(run.progress)}
          </p>
        </>
      )}
      <div className="flex justify-end">
        <Button variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

const NO_MODELS: readonly ProviderOption[] = [];

/** The end of a run: the whole result, or a plain reason it did not finish. Either way, a way to go again. */
export function Finished({
  run,
  models,
  onAgain,
}: {
  run: RunState;
  models: readonly ProviderOption[] | undefined;
  onAgain: () => void;
}) {
  const list = models ?? NO_MODELS;
  const view = useMemo(() => (run.result ? buildResultView(run.result, list) : null), [run.result, list]);
  const again = <Button onClick={onAgain}>Try again</Button>;
  return (
    <div className="space-y-6">
      {run.phase === "failed" && (
        <Callout tone="danger" action={again}>
          {run.error}
        </Callout>
      )}
      {view && <ResultView view={view} />}
      {view && (
        <div className="flex justify-end">
          <Button variant="secondary" onClick={onAgain}>
            Run again
          </Button>
        </div>
      )}
    </div>
  );
}
