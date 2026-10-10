import { ArrowDown, CheckCircle2 } from "lucide-react";
import { useEffect, useState } from "react";
import { orderView } from "../../lib/aiOrder";
import {
  type AiChoice,
  type AiSettingsPatch,
  type AiStatus,
  applyPatch,
  hasAnswerer,
  settle,
  showAppSetup,
  summarise,
  type TestTarget,
  testSubject,
  testTarget,
  unconfirmed,
} from "../../lib/aiSource";
import { ApiError } from "../../lib/api";
import { OFFLINE_MESSAGE } from "../../lib/copilot";
import { Button, Callout, Card, CardHeader, Skeleton, Switch } from "../ui";
import { AiOrder } from "./AiOrder";
import { useAiStatus, useRefreshWhenAppsChange, useSaveAiChoice, useTestAi } from "./AiSourceQueries";
import { AiSourceTest } from "./AiSourceTest";
import { AiSpeed } from "./AiSpeed";
import { AiTeam } from "./AiTeam";

const FALLBACK_NOTE =
  "Your question is only ever sent to an AI you have set up. Turn this off to ask only the first one on your list.";

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
      <Switch checked={checked} onChange={onChange} label="If an AI can't answer, try the next one on my list" />
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
  // A change is carried until the engine's own answer shows it, so a quick second click starts from the new list.
  useEffect(() => {
    setWanted((before) => unconfirmed(before, status));
  }, [status]);
  const change = (patch: AiSettingsPatch) => {
    test.reset();
    setWanted((before) => ({
      ...before,
      ...patch,
      ...(patch.ai_defaults ? { ai_defaults: { ...before.ai_defaults, ...patch.ai_defaults } } : {}),
    }));
    // A save that fails drops the change, and the screen shows what is really saved.
    void save.mutateAsync(patch).catch(() => setWanted((before) => settle(before, patch)));
  };
  const view = orderView(status, choice);
  const target: TestTarget = choice.order && choice.order.length > 0 ? (view.listed[0]?.entry ?? null) : testTarget(choice);
  const speed = wanted.ai_defaults?.speed ?? status.defaults?.speed ?? "balanced";
  const helpers = wanted.ai_defaults?.helpers ?? status.defaults?.helpers ?? 1;
  return (
    <div className="space-y-5">
      <Summary status={status} choice={choice} saved={save.isSuccess} />
      {save.isError && <Callout tone="danger">{saveFailure(save.error)}</Callout>}
      <AiOrder status={status} choice={choice} onChange={change} />
      <Fallback checked={choice.fallback} onChange={(ai_fallback) => change({ ai_fallback })} />
      <AiSpeed value={speed} onChange={(value) => change({ ai_defaults: { speed: value } })} />
      <AiTeam
        value={helpers}
        onChange={(value) => change({ ai_defaults: { helpers: value } })}
        label="Who works on a task in agent mode"
        note="Helpers look into separate questions at the same time, each on its own. They cannot change anything."
      />
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
