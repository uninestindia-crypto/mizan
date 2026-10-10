import { errorMessage } from "../../lib/api";
import { anyLevels, appOptions, keyOptions, levelsFor, type ModelOption, savedChoice, selectionOf } from "../../lib/aiOrder";
import { CLI_PREFIX } from "../../lib/aiSource";
import { useAiModels, useCliCapabilities } from "../../lib/queries";
import { thinkingWords } from "../../lib/thinking";
import { Select } from "../ui";

const AUTOMATIC_MODEL = "Automatic (the newest)";
const USUAL_LEVEL = "Its usual";
const FIELD = "block text-[12px] font-medium text-ink-2";

/** What is known about the models of one AI: the options, whether they are still loading, and why not. */
interface Models {
  options: ModelOption[];
  levels: string[];
  loading: boolean;
  problem: string | null;
}

function useAppModels(id: string): Models {
  const caps = useCliCapabilities(id.slice(CLI_PREFIX.length), true);
  const note = caps.data && caps.data.models.length === 0 ? caps.data.note : null;
  return {
    options: appOptions(caps.data),
    levels: anyLevels(caps.data, null),
    loading: caps.isLoading,
    problem: caps.isError ? errorMessage(caps.error) : note,
  };
}

function useKeyModels(id: string): Models {
  const found = useAiModels(id, true);
  return {
    options: keyOptions(id, found.data),
    levels: anyLevels(undefined, id),
    loading: found.isLoading,
    problem: found.isError ? errorMessage(found.error) : null,
  };
}

export interface Chosen {
  model: string | null;
  thinking: string | null;
}

interface FieldsProps {
  models: Models;
  chosen: Chosen;
  onPick: (model: string | null, thinking: string | null) => void;
}

/** The two choices for one AI: which model, and how hard it thinks. Both start on "the AI's own choice". */
function Fields({ models, chosen, onPick }: FieldsProps) {
  const selection = selectionOf(models.options, { id: "", ...chosen });
  const levels = levelsFor(selection, models.levels);
  const tiers = selection.option?.variants ? Object.keys(selection.option.variants) : [];
  const shownLevels = tiers.length > 0 ? tiers : levels;
  const pickModel = (value: string) => {
    const option = models.options.find((o) => o.value === value) ?? null;
    const available = option ? option.levels : models.levels;
    const keep = selection.level && available.includes(selection.level) ? selection.level : null;
    const saved = savedChoice(option, keep);
    onPick(saved.model, saved.thinking);
  };
  const pickLevel = (value: string) => {
    const saved = savedChoice(selection.option, value || null);
    onPick(saved.model ?? selection.unlisted, saved.thinking);
  };
  const modelValue = selection.option?.value ?? selection.unlisted ?? "";
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <label className={FIELD}>
        Model
        <Select value={modelValue} onChange={(e) => pickModel(e.target.value)} className="mt-1" disabled={models.loading}>
          <option value="">{AUTOMATIC_MODEL}</option>
          {selection.unlisted && <option value={selection.unlisted}>{selection.unlisted} (chosen earlier)</option>}
          {models.options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.name}
              {option.newest ? " · newest" : ""}
            </option>
          ))}
        </Select>
      </label>
      {shownLevels.length > 0 && (
        <label className={FIELD}>
          How hard it thinks
          <Select value={selection.level ?? ""} onChange={(e) => pickLevel(e.target.value)} className="mt-1">
            {tiers.length === 0 && <option value="">{USUAL_LEVEL}</option>}
            {shownLevels.map((level) => (
              <option key={level} value={level}>
                {thinkingWords(level)}
              </option>
            ))}
          </Select>
        </label>
      )}
    </div>
  );
}

function Shown({ models, chosen, onPick }: FieldsProps) {
  return (
    <div className="space-y-2">
      {models.loading && <p className="text-[12px] text-ink-3">Reading this AI's models…</p>}
      {models.problem && <p className="text-[12px] text-ink-3">{models.problem}</p>}
      <Fields models={models} chosen={chosen} onPick={onPick} />
    </div>
  );
}

function AppFields(props: Omit<FieldsProps, "models"> & { id: string }) {
  return <Shown models={useAppModels(props.id)} chosen={props.chosen} onPick={props.onPick} />;
}

function KeyFields(props: Omit<FieldsProps, "models"> & { id: string }) {
  return <Shown models={useKeyModels(props.id)} chosen={props.chosen} onPick={props.onPick} />;
}

interface Props {
  /** The AI by its id in the order: "cli:claude" for an app, the provider's name for a saved key. */
  id: string;
  chosen: Chosen;
  onPick: (model: string | null, thinking: string | null) => void;
}

/** The model and thinking level of one AI, read live from the app or the provider. Shared by Settings and the Copilot. */
export function ModelFields({ id, chosen, onPick }: Props) {
  return id.startsWith(CLI_PREFIX) ? (
    <AppFields id={id} chosen={chosen} onPick={onPick} />
  ) : (
    <KeyFields id={id} chosen={chosen} onPick={onPick} />
  );
}
