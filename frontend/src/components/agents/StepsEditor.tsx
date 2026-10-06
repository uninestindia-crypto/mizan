import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import { addStep, LIMITS, moveStep, removeStep, setStep, stepHasProblem } from "../../lib/agents";
import { Button } from "../ui";
import { NumberBadge, TextArea } from "./fields";

export const STEPS_HELP =
  "Write each step as a request, in your own words. " + "Use {symbol} where the stock's name should go.";

interface RowProps {
  index: number;
  steps: string[];
  invalid: boolean;
  onChange: (steps: string[]) => void;
}

function StepButtons({ index, steps, onChange }: Omit<RowProps, "invalid">) {
  const number = index + 1;
  const icon = (Icon: typeof ArrowUp) => <Icon className="size-3.5" aria-hidden />;
  return (
    <div className="flex flex-wrap gap-1">
      <Button type="button" variant="ghost" size="sm" icon={icon(ArrowUp)} disabled={index === 0}
        aria-label={`Move step ${number} up`} onClick={() => onChange(moveStep(steps, index, -1))}>
        Move up
      </Button>
      <Button type="button" variant="ghost" size="sm" icon={icon(ArrowDown)} disabled={index === steps.length - 1}
        aria-label={`Move step ${number} down`} onClick={() => onChange(moveStep(steps, index, 1))}>
        Move down
      </Button>
      <Button type="button" variant="ghost" size="sm" icon={icon(Trash2)}
        aria-label={`Remove step ${number}`} onClick={() => onChange(removeStep(steps, index))}>
        Remove
      </Button>
    </div>
  );
}

function StepRow({ index, steps, invalid, onChange }: RowProps) {
  return (
    <li className="flex gap-3">
      <NumberBadge number={index + 1} className="mt-2" />
      <div className="min-w-0 flex-1 space-y-1.5">
        <TextArea
          aria-label={`Step ${index + 1}`}
          rows={2}
          invalid={invalid}
          value={steps[index] ?? ""}
          onChange={(e) => onChange(setStep(steps, index, e.target.value))}
        />
        <StepButtons index={index} steps={steps} onChange={onChange} />
      </div>
    </li>
  );
}

interface Props {
  steps: string[];
  messages: string[];
  onChange: (steps: string[]) => void;
}

/** The steps an agent follows, in order. Each is one request written in the person's own words. */
export function StepsEditor({ steps, messages, onChange }: Props) {
  const full = steps.length >= LIMITS.steps;
  return (
    <div className="space-y-3">
      <ol className="space-y-3">
        {steps.map((_, index) => (
          <StepRow
            key={index}
            index={index}
            steps={steps}
            invalid={stepHasProblem(messages, index + 1)}
            onChange={onChange}
          />
        ))}
      </ol>
      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" variant="secondary" size="sm" icon={<Plus className="size-4" aria-hidden />}
          disabled={full} onClick={() => onChange(addStep(steps))}>
          Add step
        </Button>
        {full && <span className="text-[12.5px] text-ink-3">That is the most steps an agent can have.</span>}
      </div>
    </div>
  );
}
