import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { type SecondOpinionRequest, useCopilotModels } from "../../lib/copilot";
import { Finished, Waiting } from "./RunPanels";
import { SecondOpinionSetup } from "./SecondOpinionSetup";
import { type StartChoice, useStartRun } from "./useStartRun";
import type { RunAction, RunState } from "./verifyState";

export const INTRO =
  "Several AI models each read the same facts on their own and never see each other's answers. " +
  "Their opinions are not evidence that a stock will do well.";

const PANEL_STYLE =
  "q-fade-in fixed left-1/2 top-1/2 z-50 flex max-h-[calc(100dvh-2rem)] w-[calc(100vw-2rem)] max-w-2xl " +
  "-translate-x-1/2 -translate-y-1/2 flex-col rounded-2xl border border-line bg-surface shadow-[var(--shadow-pop)]";
// A word with no gaps, such as a pasted address in a model's reason, breaks at the edge instead of widening the window.
const BODY_STYLE = "min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden px-6 py-5 [overflow-wrap:anywhere]";

const CLOSE_STYLE = "rounded-lg p-1 text-ink-3 hover:bg-surface-2 hover:text-ink";

interface DialogProps {
  request: SecondOpinionRequest;
  run: RunState;
  report: (action: RunAction) => void;
  onClose: () => void;
  onClosed: () => void;
}

function Header({ symbol }: { symbol: string }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-line px-6 py-4">
      <div className="min-w-0">
        <DialogPrimitive.Title className="text-lg font-semibold text-ink">
          Second opinion on {symbol}
        </DialogPrimitive.Title>
        <DialogPrimitive.Description className="mt-1 text-sm text-ink-2">{INTRO}</DialogPrimitive.Description>
      </div>
      <DialogPrimitive.Close className={CLOSE_STYLE} aria-label="Close">
        <X className="size-5" aria-hidden />
      </DialogPrimitive.Close>
    </div>
  );
}

/** Whichever step the run is on: set up, waiting, or finished. */
function Body(props: Omit<DialogProps, "onClosed">) {
  const { request, run, report, onClose } = props;
  const models = useCopilotModels();
  const start = useStartRun(request, report);
  const notice = { stopped: run.stopped, error: run.error };
  const begin = (choice: StartChoice) => void start(choice);
  const stop = () => report({ type: "stopped" });
  const again = () => report({ type: "reset" });
  const waiting = run.phase === "starting" || run.phase === "running";
  const finished = run.phase === "done" || run.phase === "failed";
  return (
    <div className={BODY_STYLE}>
      {run.phase === "setup" && (
        <SecondOpinionSetup
          models={models}
          pickNote={request.pickNote}
          notice={notice}
          onStart={begin}
          onClose={onClose}
        />
      )}
      {waiting && <Waiting run={run} onCancel={stop} />}
      {finished && <Finished run={run} models={models.data} onAgain={again} onClose={onClose} />}
    </div>
  );
}

/**
 * The Second opinion window for one stock. Closing it does not stop the run: the caller keeps the run and goes on
 * checking for its answers, so opening the window again for the same stock picks up where it was.
 */
export function SecondOpinionDialog({ onClosed, ...props }: DialogProps) {
  return (
    <DialogPrimitive.Root open onOpenChange={(open) => !open && props.onClose()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]" />
        <DialogPrimitive.Content
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            onClosed();
          }}
          className={`${PANEL_STYLE} min-w-0`}
        >
          <Header symbol={props.request.symbol} />
          <Body {...props} />
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
