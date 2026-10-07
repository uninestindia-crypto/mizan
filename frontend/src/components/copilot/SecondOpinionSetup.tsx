import type { UseQueryResult } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";
import { defaultSelection, type ProviderOption } from "../../lib/copilot";
import { Button, Callout, Spinner } from "../ui";
import { ModelPicker } from "./ModelPicker";
import type { StartChoice } from "./useStartRun";

function NoReadyModels({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const addKey = () => {
    onClose();
    void navigate("/settings/accounts");
  };
  return (
    <Callout tone="info" action={<Button onClick={addKey}>Add an AI key</Button>}>
      Add at least one AI key to get a second opinion.
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
  "This takes a minute or two and uses a little of your AI key's allowance.";

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
  const chosen = picked ?? defaultSelection(list);
  const toggle = (id: string) => setPicked(chosen.includes(id) ? chosen.filter((p) => p !== id) : [...chosen, id]);
  return (
    <div className="space-y-4">
      {notice.stopped && <Callout tone="info">{STOPPED_NOTE}</Callout>}
      {notice.error && <Callout tone="danger">{notice.error}</Callout>}
      <ModelPicker models={list} picked={chosen} onToggle={toggle} />
      {pickNote && <PickTest note={pickNote} checked={withPick} onChange={setWithPick} />}
      <p className="text-[12.5px] text-ink-3">{COST_NOTE}</p>
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
        <Button
          disabled={chosen.length === 0}
          onClick={() => onStart({ providers: chosen, withPick: withPick && !!pickNote })}
        >
          Ask the models
        </Button>
      </div>
    </div>
  );
}

/** Choose the models and start. Nothing can be started until at least one model with a key is ticked. */
export function SecondOpinionSetup(props: SetupProps) {
  const { models, onClose } = props;
  if (models.isPending) return <Spinner label="Checking which AI models are ready" />;
  if (models.isError) return <CouldNotCheck onRetry={() => void models.refetch()} />;
  if (!models.data.some((m) => m.ready)) return <NoReadyModels onClose={onClose} />;
  return <Choices {...props} list={models.data} />;
}
