import type { UseQueryResult } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";
import { defaultSelection, type ProviderOption } from "../../lib/copilot";
import { Button, Callout, Spinner, cx } from "../ui";
import { ModelPicker } from "./ModelPicker";
import type { StartChoice } from "./useStartRun";

function NoReadyModels({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const setUp = () => {
    onClose();
    void navigate("/settings/ai");
  };
  return (
    <Callout tone="info" action={<Button onClick={setUp}>Choose an AI</Button>}>
      Set up an AI first: choose Settings, then AI assistants.
    </Callout>
  );
}

function CouldNotCheck({ onRetry }: { onRetry: () => void }) {
  return (
    <Callout tone="danger" action={<Button onClick={onRetry}>Try again</Button>}>
      QuantOS could not check which AI models are ready.
    </Callout>
  );
}

interface PickTestProps {
  note: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

function PickTest({ note, checked, onChange }: PickTestProps) {
  return (
    <label className="flex items-start gap-3 text-[13.5px] text-ink">
      <input
        type="checkbox"
        className="mt-0.5 size-4 accent-brand"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span>
        Also test whether the platform&apos;s own pick sways the models
        <span className="block text-[12.5px] text-ink-3">{note}</span>
      </span>
    </label>
  );
}

const STOPPED_NOTE = "You stopped the last check. Any answers still on their way are ignored.";
const COST_NOTE =
  "Each model is asked again with the facts in a different order, to see whether it changes its mind. " +
  "This takes a minute or two and uses a little of what your AI plan or key allows.";

interface SetupProps {
  models: UseQueryResult<ProviderOption[]>;
  pickNote?: string;
  notice: { stopped: boolean; error: string | null };
  onStart: (choice: StartChoice) => void;
  onClose: () => void;
}

function Choices(props: SetupProps & { list: ProviderOption[] }) {
  const { list, pickNote, notice, onStart, onClose } = props;
  const [picked, setPicked] = useState<string[] | null>(null);
  const [withPick, setWithPick] = useState(false);
  const [chained, setChained] = useState(true);
  const chosen = picked ?? defaultSelection(list);

  const toggle = (id: string) =>
    setPicked(chosen.includes(id) ? chosen.filter((p) => p !== id) : [...chosen, id]);

  const move = (fromIndex: number, toIndex: number) => {
    const next = [...chosen];
    const moved = next[fromIndex];
    if (moved === undefined) return;
    next.splice(fromIndex, 1);
    next.splice(toIndex, 0, moved);
    setPicked(next);
  };

  const modelLabel = (id: string) => list.find((m) => m.id === id)?.label ?? id;

  return (
    <div className="space-y-4">
      {notice.stopped && <Callout tone="info">{STOPPED_NOTE}</Callout>}
      {notice.error && <Callout tone="danger">{notice.error}</Callout>}
      <ModelPicker models={list} picked={chosen} onToggle={toggle} />

      {chosen.length > 0 && (
        <div className="rounded-xl border border-line bg-surface-2/40 p-3.5 space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-[13px] font-semibold text-ink">
              {chained ? "Sequential Review Chain (Priority Order)" : "Models to Ask (Priority Order)"}
            </h4>
            <span className="text-[11px] text-ink-3">
              {chosen.length} {chosen.length === 1 ? "model" : "models"} selected
            </span>
          </div>

          <button
            type="button"
            role="switch"
            aria-checked={chained}
            onClick={() => setChained(!chained)}
            className="flex items-start gap-2.5 text-left cursor-pointer text-[12.5px] text-ink select-none"
          >
            <span
              className={cx(
                "mt-0.5 flex h-4 w-7 shrink-0 items-center rounded-full p-0.5 transition-colors",
                chained ? "bg-brand" : "bg-surface-3"
              )}
            >
              <span
                className={cx(
                  "size-3 rounded-full bg-white transition-transform",
                  chained ? "translate-x-3" : "translate-x-0"
                )}
              />
            </span>
            <div>
              <span className="font-medium">Chained recheck pipeline</span>
              <p className="text-[11.5px] text-ink-3 leading-relaxed">
                Each model rechecks and critiques the previous models&apos; opinions and verdicts against the facts.
              </p>
            </div>
          </button>

          <ul className="space-y-1.5 pt-1">
            {chosen.map((id, index) => (
              <li
                key={id}
                className="flex items-center justify-between rounded-lg border border-line bg-surface px-3 py-2 text-[12.5px]"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-brand/10 font-bold text-[11px] text-brand">
                    {index + 1}
                  </span>
                  <div className="min-w-0">
                    <span className="font-medium text-ink block truncate">{modelLabel(id)}</span>
                    <span className="text-[11px] text-ink-3">
                      {index === 0
                        ? "Stage 1 · Initial Reading & Verdict"
                        : `Stage ${index + 1} · Rechecks Stage ${index === 1 ? "1" : `1–${index}`}`}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <Button
                    size="sm"
                    variant="ghost"
                    className="size-7 p-0"
                    disabled={index === 0}
                    aria-label={`Move ${modelLabel(id)} up`}
                    onClick={() => move(index, index - 1)}
                  >
                    ▲
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="size-7 p-0"
                    disabled={index === chosen.length - 1}
                    aria-label={`Move ${modelLabel(id)} down`}
                    onClick={() => move(index, index + 1)}
                  >
                    ▼
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {pickNote && <PickTest note={pickNote} checked={withPick} onChange={setWithPick} />}
      <p className="text-[12.5px] text-ink-3">{COST_NOTE}</p>
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
        <Button
          disabled={chosen.length === 0}
          onClick={() => onStart({ providers: chosen, withPick: withPick && !!pickNote, chained })}
        >
          Ask the models
        </Button>
      </div>
    </div>
  );
}

/** Choose the models and start. Nothing can be started until at least one AI that is ready is ticked. */
export function SecondOpinionSetup(props: SetupProps) {
  const { models, onClose } = props;
  if (models.isPending) return <Spinner label="Checking which AI models are ready" />;
  if (models.isError) return <CouldNotCheck onRetry={() => void models.refetch()} />;
  if (!models.data.some((m) => m.ready)) return <NoReadyModels onClose={onClose} />;
  return <Choices {...props} list={models.data} />;
}
