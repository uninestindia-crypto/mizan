import { Check, X } from "lucide-react";
import { type FormEvent, type KeyboardEvent, useEffect, useId, useRef, useState } from "react";
import { plainFailure } from "../../../lib/copilot";
import type { ChatSummary } from "../../../lib/copilotHistory";
import { cx } from "../../ui";
import type { ChatActions } from "./useChatActions";

/** The longest name the engine accepts. */
export const MAX_NAME = 80;

export const ICON_BUTTON =
  "grid size-8 shrink-0 place-items-center rounded-lg text-ink-3 hover:bg-surface-2 hover:text-ink " +
  "disabled:cursor-not-allowed disabled:opacity-50";

const FIELD =
  "h-9 min-w-0 flex-1 rounded-[var(--radius-control)] border border-line bg-surface px-2.5 text-[13.5px] " +
  "text-ink hover:border-line-strong focus:border-brand focus:outline-none focus:ring-3 focus:ring-brand/15";

interface RenameFormProps {
  chat: ChatSummary;
  rename: ChatActions["rename"];
  onDone: () => void;
}

/** The name being typed, and what saving it did. A refusal comes back as the engine's own sentence. */
function useRenameDraft({ chat, rename, onDone }: RenameFormProps) {
  const [value, setValue] = useState(chat.title);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (value === chat.title) return onDone();
    setBusy(true);
    setError(null);
    try {
      await rename(chat.id, value);
      onDone();
    } catch (failure) {
      setError(plainFailure(failure));
      setBusy(false);
    }
  };
  return { value, setValue, busy, error, save };
}

/** The chat's name, edited where it stands. Enter saves, Escape cancels, and a refusal shows as the engine said it. */
export function RenameForm(props: RenameFormProps) {
  const { onDone } = props;
  const base = useId();
  const errorId = `${base}-error`;
  const field = useRef<HTMLInputElement>(null);
  const { value, setValue, busy, error, save } = useRenameDraft(props);
  useEffect(() => {
    field.current?.focus();
    field.current?.select();
  }, []);

  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    event.stopPropagation();
    onDone();
  };
  return (
    <form onSubmit={(event) => void save(event)} onKeyDown={onKeyDown} className="space-y-1.5 px-3 py-2.5">
      <div className="flex items-center gap-1">
        <label htmlFor={`${base}-name`} className="sr-only">
          Chat name
        </label>
        <input
          id={`${base}-name`}
          ref={field}
          value={value}
          maxLength={MAX_NAME}
          onChange={(event) => setValue(event.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          className={cx(FIELD, error && "border-warn")}
        />
        <button type="submit" disabled={busy} aria-label="Save name" title="Save name" className={ICON_BUTTON}>
          <Check className="size-4" aria-hidden />
        </button>
        <button type="button" onClick={onDone} aria-label="Cancel rename" title="Cancel" className={ICON_BUTTON}>
          <X className="size-4" aria-hidden />
        </button>
      </div>
      {error && (
        <p id={errorId} role="alert" className="text-[12.5px] text-warn">
          {error}
        </p>
      )}
    </form>
  );
}
