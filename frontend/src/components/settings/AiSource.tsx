import { ArrowDown, CheckCircle2 } from "lucide-react";
import { useState } from "react";
import {
  type AiChoice,
  type AiSettingsPatch,
  type AiStatus,
  applyPatch,
  hasAnswerer,
  settle,
  showAppSetup,
  summarise,
  testSubject,
  testTarget,
} from "../../lib/aiSource";
import { ApiError } from "../../lib/api";
import { OFFLINE_MESSAGE } from "../../lib/copilot";
import { Button, Callout, Card, CardHeader, Skeleton, Switch } from "../ui";
import { AiSourceChoice } from "./AiSourceChoice";
import { AiSourcePrefer } from "./AiSourcePrefer";
import { useAiStatus, useRefreshWhenAppsChange, useSaveAiChoice, useTestAi } from "./AiSourceQueries";
import { AiSourceTest } from "./AiSourceTest";

const FALLBACK_NOTE =
  "Your question is only ever sent to an AI you have set up. Turn this off to keep it to one kind.";

function saveFailure(error: unknown): string {
  if (error instanceof ApiError && error.code === "ENGINE_OFFLINE") return OFFLINE_MESSAGE;
  return "That choice could not be saved, so nothing was changed. Please try again.";
}

/** Where questions go right now. "Saved" sits beside it, where the eye already is, once a change goes through. */
function Summary({ status, choice, saved }: { status: AiStatus; choice: AiChoice; saved: boolean }) {
  const mark = (
    <span className="inline-flex items-center gap-1 text-[12.5px] font-medium text-up">
      <CheckCircle2 className="size-3.5" aria-hidden /> Saved
    </span>
  );
  return (
    <Callout tone={hasAnswerer(status, choice) ? "success" : "warn"} action={saved ? mark : undefined}>
      <span className="text-ink">{summarise(status, choice)}</span>
    </Callout>
  );
}

function Fallback({ checked, onChange }: { checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <div className="space-y-1">
      <Switch checked={checked} onChange={onChange} label="If that AI can't answer, try the other kind" />
      <p className="pl-11 text-[12.5px] text-ink-3">{FALLBACK_NOTE}</p>
    </div>
  );
}

function Loaded({ status }: { status: AiStatus }) {
  const save = useSaveAiChoice();
  const test = useTestAi();
  // A click answers at once: until the save is done the screen shows the choice as it will be. If the save fails the
  // change is dropped, and the screen shows what is really saved.
  const [wanted, setWanted] = useState<AiSettingsPatch>({});
  const choice = applyPatch(status.ai, wanted);
  const change = (patch: AiSettingsPatch) => {
    test.reset();
    setWanted((before) => ({ ...before, ...patch }));
    void save.mutateAsync(patch).then(
      () => setWanted((before) => settle(before, patch)),
      () => setWanted((before) => settle(before, patch)),
    );
  };
  const target = testTarget(choice);
  return (
    <div className="space-y-5">
      <Summary status={status} choice={choice} saved={save.isSuccess} />
      {save.isError && <Callout tone="danger">{saveFailure(save.error)}</Callout>}
      <AiSourceChoice value={choice.source} onChange={(ai_source) => change({ ai_source })} />
      <AiSourcePrefer status={status} choice={choice} onChange={change} />
      <Fallback checked={choice.fallback} onChange={(ai_fallback) => change({ ai_fallback })} />
      <AiSourceTest run={test} subject={testSubject(status, target)} target={target} />
      <button
        type="button"
        onClick={() => showAppSetup(null)}
        className="inline-flex items-center gap-1 text-[13px] font-medium text-brand hover:underline"
      >
        Install or sign in below <ArrowDown className="size-3.5" aria-hidden />
      </button>
    </div>
  );
}

function Body({ status }: { status: ReturnType<typeof useAiStatus> }) {
  if (status.data) return <Loaded status={status.data} />;
  if (!status.isError) return <Skeleton className="h-64" />;
  return (
    <Callout tone="danger" action={<Button onClick={() => void status.refetch()}>Try again</Button>}>
      QuantOS could not check which AI is ready.
    </Callout>
  );
}

/** Settings, then AI assistants: which AI answers every AI feature, with the AI app on this computer as the default. */
export function AiSource() {
  const status = useAiStatus();
  useRefreshWhenAppsChange();
  return (
    <Card>
      <CardHeader
        title="Which AI should answer your questions?"
        subtitle="The Copilot and your agents answer with this AI."
      />
      <Body status={status} />
    </Card>
  );
}
