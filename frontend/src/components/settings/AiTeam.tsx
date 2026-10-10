import { useId } from "react";
import { Select } from "../ui";

export const TEAM_OPTIONS: readonly { value: number; title: string }[] = [
  { value: 1, title: "Just the Copilot" },
  { value: 2, title: "The Copilot and one helper" },
  { value: 3, title: "The Copilot and two helpers" },
];

interface Props {
  value: number;
  onChange: (value: number) => void;
  /** Shown above the choice. */
  label?: string;
  /** A line under the choice, for the place that has room for it. */
  note?: string;
}

/** How many AIs work on a task. Helpers look into separate questions at the same time and cannot change anything. */
export function AiTeam({ value, onChange, label = "Who works on a task", note }: Props) {
  const id = useId();
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-[13.5px] font-semibold text-ink">
        {label}
      </label>
      <Select id={id} value={String(value)} onChange={(e) => onChange(Number(e.target.value))}>
        {TEAM_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.title}
          </option>
        ))}
      </Select>
      {note && <p className="text-[12px] text-ink-3">{note}</p>}
    </div>
  );
}
