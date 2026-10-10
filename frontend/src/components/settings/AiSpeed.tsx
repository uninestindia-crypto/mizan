import { useId } from "react";
import type { Speed } from "../../lib/aiSource";
import { cx } from "../ui";

interface Option {
  value: Speed;
  title: string;
  body: string;
}

export const SPEED_OPTIONS: readonly Option[] = [
  { value: "quick", title: "Quick", body: "Short answers. Looks up a little, thinks lightly." },
  { value: "balanced", title: "Balanced", body: "The usual way. A good mix of speed and care." },
  { value: "careful", title: "Careful", body: "Looks things up more and thinks harder. Takes longer." },
];

interface Props {
  value: Speed;
  onChange: (value: Speed) => void;
  /** A name for the group of choices when the screen has more than one. */
  legend?: string;
  /** Short choices on one line with only the chosen one explained, for a narrow place such as the Copilot. */
  compact?: boolean;
}

/** How fast or how careful answers should be. This is a setting of this app, not a feature of any one AI. */
export function AiSpeed({ value, onChange, legend = "How answers are made", compact = false }: Props) {
  const name = useId();
  if (compact) {
    const chosen = SPEED_OPTIONS.find((option) => option.value === value);
    return (
      <fieldset className="space-y-1.5">
        <legend className="text-[12px] font-medium text-ink-2">{legend}</legend>
        <div className="flex gap-1.5">
          {SPEED_OPTIONS.map((option) => {
            const checked = option.value === value;
            const state = checked ? "border-brand bg-brand-soft/50 text-ink" : "border-line bg-surface text-ink-2 hover:border-line-strong";
            return (
              <label key={option.value} className={cx("flex flex-1 cursor-pointer items-center justify-center gap-1.5 rounded-lg border px-2 py-1.5 text-[12.5px] font-medium", state)}>
                <input type="radio" name={name} className="sr-only" checked={checked} onChange={() => onChange(option.value)} />
                {option.title}
              </label>
            );
          })}
        </div>
        {chosen && <p className="text-[11.5px] text-ink-3">{chosen.body}</p>}
      </fieldset>
    );
  }
  return (
    <fieldset className="space-y-2">
      <legend className="text-[13.5px] font-semibold text-ink">{legend}</legend>
      <div className="grid gap-2 sm:grid-cols-3">
        {SPEED_OPTIONS.map((option) => {
          const checked = option.value === value;
          const state = checked ? "border-brand bg-brand-soft/50" : "border-line bg-surface hover:border-line-strong";
          return (
            <label key={option.value} className={cx("flex cursor-pointer items-start gap-2.5 rounded-lg border p-3", state)}>
              <input type="radio" name={name} className="mt-0.5 size-4 shrink-0 accent-brand" checked={checked} onChange={() => onChange(option.value)} />
              <span className="min-w-0">
                <span className="block text-[13.5px] font-semibold text-ink">{option.title}</span>
                <span className="mt-0.5 block text-[12px] leading-snug text-ink-3">{option.body}</span>
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
