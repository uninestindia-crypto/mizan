import { CheckCircle2, ChevronDown, ChevronUp, SlidersHorizontal } from "lucide-react";
import { useId, useState } from "react";
import { effectiveOrder, orderView, withKept } from "../../lib/aiOrder";
import type { AiStatus, Speed } from "../../lib/aiSource";
import { afterSaving, type AnswerPrefs, isSavable, isUsual, NO_PREFS, withAi } from "../../lib/answerPrefs";
import { Badge, Button, Select } from "../ui";
import { useAiStatus, useSaveAiChoice } from "../settings/AiSourceQueries";
import { AiSpeed } from "../settings/AiSpeed";
import { AiTeam } from "../settings/AiTeam";
import { ModelFields } from "../settings/ModelFields";
import { useCopilot } from "./CopilotProvider";
import type { ChatMode } from "./useChatSession";

const USUAL_ORDER = "My usual order";
const THE_COPILOT = "The Copilot, with my usual AIs";
const FIELD = "block text-[12px] font-medium text-ink-2";

/** The AIs that can be asked for by name: the ones on the list first, then the ones that are ready but not on it. */
function askable(status: AiStatus) {
  const view = orderView(status, status.ai);
  return [...view.listed.map((item) => item.candidate), ...view.addable];
}

interface PanelProps {
  status: AiStatus;
  prefs: AnswerPrefs;
  setPrefs: (prefs: AnswerPrefs) => void;
  mode: ChatMode;
}

/** Makes what was chosen here the way answers are made from now on: that AI first, with its choices, at this speed. */
function useMakeDefault({ status, prefs, setPrefs }: PanelProps) {
  const save = useSaveAiChoice();
  const make = () => {
    const patch: Parameters<typeof save.mutate>[0] = {};
    if (prefs.speed || prefs.helpers) {
      patch.ai_defaults = {
        ...(prefs.speed ? { speed: prefs.speed } : {}),
        ...(prefs.helpers ? { helpers: prefs.helpers } : {}),
      };
    }
    if (prefs.ai && !prefs.runner) {
      const rest = effectiveOrder(status, status.ai).filter((entry) => entry.id !== prefs.ai);
      const first = { id: prefs.ai, model: prefs.model, thinking: prefs.thinking };
      patch.ai_order = withKept([first, ...rest], status, status.ai);
    }
    save.mutate(patch, { onSuccess: () => setPrefs(afterSaving(prefs)) });
  };
  return { make, save };
}

/** The AI apps that can do a whole task themselves, with the name a person knows them by. */
function taskApps(status: AiStatus) {
  return (status.agent_apps ?? []).map((id) => ({ id, name: status.apps.find((app) => `cli:${app.id}` === id)?.name ?? id }));
}

/** In agent mode: the Copilot works through the task itself, or one of the person's AI apps does the work. */
function WhoDoesTheWork({ status, prefs, setPrefs }: Omit<PanelProps, "mode">) {
  const who = useId();
  const apps = taskApps(status);
  if (apps.length === 0) return null;
  const chosen = apps.find((app) => app.id === prefs.runner);
  const pick = (id: string) => setPrefs(id ? { ...withAi(prefs, id), runner: id } : { ...withAi(prefs, null), runner: null });
  return (
    <div className="space-y-1.5">
      <label className={FIELD} htmlFor={who}>
        Who does the work
      </label>
      <Select id={who} value={chosen?.id ?? ""} onChange={(e) => pick(e.target.value)}>
        <option value="">{THE_COPILOT}</option>
        {apps.map((app) => (
          <option key={app.id} value={app.id}>
            {app.name}
          </option>
        ))}
      </Select>
      {chosen && (
        <p className="text-[11.5px] text-ink-3">
          {chosen.name} does the whole task itself. It can only use the same lookups as the Copilot, it cannot see your files, and it asks you before it
          changes anything.
        </p>
      )}
    </div>
  );
}

function Panel(props: PanelProps) {
  const { status, prefs, setPrefs, mode } = props;
  const which = useId();
  const { make, save } = useMakeDefault(props);
  const speed: Speed = prefs.speed ?? status.defaults?.speed ?? "balanced";
  const ais = askable(status);
  const doing = mode === "agent" ? taskApps(status).find((app) => app.id === prefs.runner) : undefined;
  return (
    <div className="space-y-3 rounded-lg border border-line bg-surface-2/60 p-3">
      {mode === "agent" && <WhoDoesTheWork status={status} prefs={prefs} setPrefs={setPrefs} />}
      {!doing && (
        <>
          <label className={FIELD} htmlFor={which}>
            Which AI
          </label>
          <Select id={which} value={prefs.ai ?? ""} onChange={(e) => setPrefs(withAi(prefs, e.target.value || null))}>
            <option value="">{USUAL_ORDER}</option>
            {ais.map((ai) => (
              <option key={ai.id} value={ai.id}>
                {ai.name}
              </option>
            ))}
          </Select>
        </>
      )}
      {prefs.ai ? (
        <ModelFields
          key={prefs.ai}
          id={prefs.ai}
          chosen={prefs}
          onPick={(model, thinking) => setPrefs({ ...prefs, model, thinking })}
        />
      ) : (
        <p className="text-[11.5px] text-ink-3">Pick an AI to choose its model and how hard it thinks.</p>
      )}
      <AiSpeed compact legend="Speed" value={speed} onChange={(value) => setPrefs({ ...prefs, speed: value })} />
      {mode === "agent" && !doing && (
        <AiTeam
          label="Who works on the task"
          value={prefs.helpers ?? status.defaults?.helpers ?? 1}
          onChange={(helpers) => setPrefs({ ...prefs, helpers })}
          note="Helpers look into separate questions at the same time, each on its own. They cannot change anything."
        />
      )}
      <div className="flex flex-wrap items-center gap-2 pt-1">
        {!isUsual(prefs) && (
          <>
            {isSavable(prefs) && (
              <Button size="sm" variant="secondary" loading={save.isPending} onClick={make}>
                Make this my usual
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={() => setPrefs(NO_PREFS)}>
              Back to my usual
            </Button>
          </>
        )}
        {save.isSuccess && (
          <span className="inline-flex items-center gap-1 text-[12px] font-medium text-up">
            <CheckCircle2 className="size-3.5" aria-hidden /> Saved
          </span>
        )}
        {save.isError && <span className="text-[12px] text-warn">That could not be saved. Please try again.</span>}
      </div>
    </div>
  );
}

function Loaded() {
  const { prefs, setPrefs, mode } = useCopilot();
  const status = useAiStatus();
  if (!status.data) {
    return <p className="text-[12px] text-ink-3">{status.isError ? "QuantOS could not check which AI is ready." : "Looking at your AIs…"}</p>;
  }
  return <Panel status={status.data} prefs={prefs} setPrefs={setPrefs} mode={mode} />;
}

/**
 * One message can ask to be answered in a different way than Settings says: by another AI, with another model, thinking
 * harder or less, quicker or more carefully. Nothing here changes what the Copilot may do, only how it answers.
 */
export function WaysToAnswer() {
  const { prefs } = useCopilot();
  const [open, setOpen] = useState(false);
  const Chevron = open ? ChevronUp : ChevronDown;
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen((before) => !before)}
          className="inline-flex items-center gap-1.5 text-[12.5px] font-medium text-ink-2 hover:text-ink"
        >
          <SlidersHorizontal className="size-3.5" aria-hidden />
          Ways to answer
          {!isUsual(prefs) && <Badge tone="brand">Changed</Badge>}
          <Chevron className="size-3.5" aria-hidden />
        </button>
        <ModeSwitch />
      </div>
      {open && <Loaded />}
    </div>
  );
}

const MODES: readonly { value: ChatMode; title: string }[] = [
  { value: "chat", title: "Chat" },
  { value: "agent", title: "Agent" },
];

/** Chat answers a question. Agent works through a task in steps and asks before it changes anything. */
function ModeSwitch() {
  const { mode, setMode, thinking } = useCopilot();
  const name = useId();
  return (
    <fieldset className="m-0 border-0 p-0" disabled={thinking}>
      <legend className="sr-only">Chat or task</legend>
      <div className="inline-flex rounded-lg border border-line p-0.5">
        {MODES.map((option) => {
          const on = option.value === mode;
          return (
            <label
              key={option.value}
              title={option.value === "agent" ? "Works through a task step by step and asks you before it changes anything" : "Answers a question"}
              className={`cursor-pointer rounded-md px-2.5 py-1 text-[12px] font-medium ${on ? "bg-brand text-white" : "text-ink-2 hover:text-ink"}`}
            >
              <input type="radio" name={name} className="sr-only" checked={on} onChange={() => setMode(option.value)} />
              {option.title}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
