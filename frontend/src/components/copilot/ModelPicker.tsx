import { useId } from "react";
import type { ProviderOption } from "../../lib/copilot";
import { groupModels } from "../../lib/aiSource";
import { Badge, cx } from "../ui";

const ROW_STYLE = "flex items-center gap-3 rounded-lg border border-line px-3 py-2 text-[13.5px]";
const CROSS_CHECK_NOTE =
  "Models from different companies give a better cross-check than several from one company.";
const NOT_READY = { apps: "Not set up yet", keys: "No key added yet" };

type Group = keyof typeof NOT_READY;

interface RowProps {
  model: ProviderOption;
  group: Group;
  picked: boolean;
  onToggle: () => void;
}

function ModelRow({ model, group, picked, onToggle }: RowProps) {
  const style = model.ready ? "cursor-pointer text-ink hover:bg-surface-2" : "cursor-not-allowed text-ink-3";
  return (
    <label className={cx(ROW_STYLE, style)}>
      <input
        type="checkbox"
        className="size-4 accent-brand"
        checked={model.ready && picked}
        disabled={!model.ready}
        onChange={onToggle}
      />
      <span className="flex-1">{model.label}</span>
      {model.ready ? <Badge tone="up">Ready</Badge> : <span className="text-[12.5px]">{NOT_READY[group]}</span>}
    </label>
  );
}

interface ListProps {
  title: string;
  group: Group;
  models: readonly ProviderOption[];
  chosen: { picked: readonly string[]; onToggle: (id: string) => void };
}

function ModelList({ title, group, models, chosen }: ListProps) {
  const { picked, onToggle } = chosen;
  const heading = useId();
  if (models.length === 0) return null;
  return (
    <div role="group" aria-labelledby={heading} className="space-y-1.5">
      <h4 id={heading} className="text-[12.5px] font-semibold uppercase tracking-wide text-ink-3">
        {title}
      </h4>
      <ul className="space-y-1.5">
        {models.map((model) => (
          <li key={model.id}>
            <ModelRow
              model={model}
              group={group}
              picked={picked.includes(model.id)}
              onToggle={() => onToggle(model.id)}
            />
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * The AIs to ask, in two groups: the AI apps on this computer, then the keys the person saved. Only an AI that is
 * ready can be ticked; the others say what is missing.
 */
export function ModelPicker({
  models,
  picked,
  onToggle,
}: {
  models: readonly ProviderOption[];
  picked: readonly string[];
  onToggle: (id: string) => void;
}) {
  const { apps, keys } = groupModels(models);
  const chosen = { picked, onToggle };
  return (
    <fieldset className="space-y-3">
      <legend className="text-[13.5px] font-medium text-ink">Which AI models should read it?</legend>
      <ModelList title="AI apps on this computer" group="apps" models={apps} chosen={chosen} />
      <ModelList title="AI keys you saved" group="keys" models={keys} chosen={chosen} />
      <p className="text-[12.5px] text-ink-3">{CROSS_CHECK_NOTE}</p>
    </fieldset>
  );
}
