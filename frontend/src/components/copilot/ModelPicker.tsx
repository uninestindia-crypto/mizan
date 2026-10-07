import type { ProviderOption } from "../../lib/copilot";
import { cx } from "../ui";

const ROW_STYLE = "flex items-center gap-3 rounded-lg border border-line px-3 py-2 text-[13.5px]";
const CROSS_CHECK_NOTE = "Models from different companies give a better cross-check than several from one company.";

function ModelRow({ model, picked, onToggle }: { model: ProviderOption; picked: boolean; onToggle: () => void }) {
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
      {!model.ready && <span className="text-[12.5px]">No key added yet</span>}
    </label>
  );
}

/** The AI models to ask. Only a model with a saved key can be ticked; the others say what is missing. */
export function ModelPicker({
  models,
  picked,
  onToggle,
}: {
  models: readonly ProviderOption[];
  picked: readonly string[];
  onToggle: (id: string) => void;
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-[13.5px] font-medium text-ink">Which AI models should read it?</legend>
      <ul className="space-y-1.5">
        {models.map((model) => (
          <li key={model.id}>
            <ModelRow model={model} picked={picked.includes(model.id)} onToggle={() => onToggle(model.id)} />
          </li>
        ))}
      </ul>
      <p className="text-[12.5px] text-ink-3">{CROSS_CHECK_NOTE}</p>
    </fieldset>
  );
}
