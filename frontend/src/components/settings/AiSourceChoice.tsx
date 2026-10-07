import { useId } from "react";
import { Link } from "react-router";
import type { AiKind } from "../../lib/aiSource";
import { Badge, cx } from "../ui";

interface Option {
  value: AiKind;
  title: string;
  body: string;
  recommended: boolean;
}

const OPTIONS: Option[] = [
  {
    value: "cli",
    title: "The AI app on this computer",
    body: "Uses the Claude Code, Codex or Gemini app you are already signed in to. No key needed.",
    recommended: true,
  },
  {
    value: "api",
    title: "An AI key I saved",
    body: "Uses a key you added under Accounts & keys.",
    recommended: false,
  },
];

const CARD = "flex flex-col gap-2 rounded-xl border p-4 transition-colors";
const CARD_FOCUS = "has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-brand/40";

interface CardProps {
  option: Option;
  checked: boolean;
  name: string;
  onPick: () => void;
}

function ChoiceCard({ option, checked, name, onPick }: CardProps) {
  const id = useId();
  const state = checked ? "border-brand bg-brand-soft/50" : "border-line bg-surface hover:border-line-strong";
  return (
    <div className={cx(CARD, CARD_FOCUS, state)}>
      <label className="flex cursor-pointer items-start gap-3">
        <input
          type="radio"
          name={name}
          className="mt-1 size-4 shrink-0 accent-brand"
          checked={checked}
          onChange={onPick}
          aria-labelledby={`${id}-title`}
          aria-describedby={`${id}-body`}
        />
        <span className="min-w-0">
          <span id={`${id}-title`} className="flex flex-wrap items-center gap-2 text-[14.5px] font-semibold text-ink">
            {option.title}
            {option.recommended && <Badge tone="brand">Recommended</Badge>}
          </span>
          <span id={`${id}-body`} className="mt-1 block text-[13px] leading-relaxed text-ink-2">
            {option.body}
          </span>
        </span>
      </label>
      {option.value === "api" && (
        <Link to="/settings/accounts" className="ml-7 text-[13px] font-medium text-brand hover:underline">
          Open Accounts &amp; keys
        </Link>
      )}
    </div>
  );
}

/** The two kinds of AI, as large choices. Choosing one is saved at once by the caller. */
export function AiSourceChoice({ value, onChange }: { value: AiKind; onChange: (value: AiKind) => void }) {
  const name = useId();
  return (
    <fieldset>
      <legend className="sr-only">Where your answers come from</legend>
      <div className="grid gap-3 sm:grid-cols-2">
        {OPTIONS.map((option) => (
          <ChoiceCard
            key={option.value}
            option={option}
            checked={option.value === value}
            name={name}
            onPick={() => onChange(option.value)}
          />
        ))}
      </div>
    </fieldset>
  );
}
