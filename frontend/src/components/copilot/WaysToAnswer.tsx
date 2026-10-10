import { CheckCircle2, ChevronDown, ChevronUp, SlidersHorizontal } from "lucide-react";
import { useId, useState } from "react";
import { effectiveOrder, orderView, withKept } from "../../lib/aiOrder";
import type { AiStatus, Speed } from "../../lib/aiSource";
import { type AnswerPrefs, isUsual, NO_PREFS, withAi } from "../../lib/answerPrefs";
import { Badge, Button, Select } from "../ui";
import { useAiStatus, useSaveAiChoice } from "../settings/AiSourceQueries";
import { AiSpeed } from "../settings/AiSpeed";
import { ModelFields } from "../settings/ModelFields";
import { useCopilot } from "./CopilotProvider";

const USUAL_ORDER = "My usual order";
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
}

/** Makes what was chosen here the way answers are made from now on: that AI first, with its choices, at this speed. */
function useMakeDefault({ status, prefs, setPrefs }: PanelProps) {
  const save = useSaveAiChoice();
  const make = () => {
    const patch: Parameters<typeof save.mutate>[0] = {};
    if (prefs.speed) patch.ai_defaults = { speed: prefs.speed };
    if (prefs.ai) {
      const rest = effectiveOrder(status, status.ai).filter((entry) => entry.id !== prefs.ai);
      const first = { id: prefs.ai, model: prefs.model, thinking: prefs.thinking };
      patch.ai_order = withKept([first, ...rest], status, status.ai);
    }
    save.mutate(patch, { onSuccess: () => setPrefs(NO_PREFS) });
  };
  return { make, save };
}

function Panel(props: PanelProps) {
  const { status, prefs, setPrefs } = props;
  const which = useId();
  const { make, save } = useMakeDefault(props);
  const speed: Speed = prefs.speed ?? status.defaults?.speed ?? "balanced";
  const ais = askable(status);
  return (
    <div className="space-y-3 rounded-lg border border-line bg-surface-2/60 p-3">
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
      <div className="flex flex-wrap items-center gap-2 pt-1">
        {!isUsual(prefs) && (
          <>
            <Button size="sm" variant="secondary" loading={save.isPending} onClick={make}>
              Make this my usual
            </Button>
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
  const { prefs, setPrefs } = useCopilot();
  const status = useAiStatus();
  if (!status.data) {
    return <p className="text-[12px] text-ink-3">{status.isError ? "QuantOS could not check which AI is ready." : "Looking at your AIs…"}</p>;
  }
  return <Panel status={status.data} prefs={prefs} setPrefs={setPrefs} />;
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
      {open && <Loaded />}
    </div>
  );
}
