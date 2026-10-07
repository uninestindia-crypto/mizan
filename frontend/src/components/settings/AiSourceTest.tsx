import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { UseMutationResult } from "@tanstack/react-query";
import { type AiTestResult, testLine } from "../../lib/aiSource";
import { plainFailure } from "../../lib/copilot";
import { Button, Spinner } from "../ui";

type TestRun = UseMutationResult<AiTestResult, Error, string | null>;

const WAIT_NOTE = "This can take up to a minute while the AI app starts.";

function Outcome({ run }: { run: TestRun }) {
  if (run.isPending) return <Spinner label={WAIT_NOTE} />;
  if (run.isError) {
    return (
      <p role="status" className="flex items-start gap-2 text-[13px] text-warn">
        <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
        <span>{plainFailure(run.error)}</span>
      </p>
    );
  }
  if (!run.data) return null;
  const Icon = run.data.ok ? CheckCircle2 : AlertTriangle;
  return (
    <p role="status" className={`flex items-start gap-2 text-[13px] ${run.data.ok ? "text-up" : "text-warn"}`}>
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span className="text-ink">{testLine(run.data)}</span>
    </p>
  );
}

interface TestProps {
  run: TestRun;
  subject: string;
  target: string | null;
}

/** One small question to the AI, so a person can see that it works. Never a pop-up: the answer sits here. */
export function AiSourceTest({ run, subject, target }: TestProps) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <Button variant="secondary" disabled={run.isPending} onClick={() => run.mutate(target)}>
          Test this AI
        </Button>
        <span className="text-[12.5px] text-ink-3">{subject}</span>
      </div>
      <Outcome run={run} />
    </div>
  );
}
