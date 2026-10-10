import { type KeyboardEvent, useEffect, useId, useRef, useState } from "react";
import { plainFailure } from "../../../lib/copilot";
import { Button } from "../../ui";

interface ConfirmProps {
  /** The question, in plain words. Says what is lost. */
  question: string;
  confirmLabel: string;
  /** Throws when it could not be done; the person then sees why and can keep or try again. */
  onConfirm: () => Promise<void>;
  onKeep: () => void;
}

/**
 * An inline "are you sure". Focus starts on Keep, the safe choice, and Escape keeps. Escape is handled here so that it
 * undoes only this question, not the whole panel.
 */
export function Confirm({ question, confirmLabel, onConfirm, onKeep }: ConfirmProps) {
  const questionId = useId();
  const keep = useRef<HTMLButtonElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => keep.current?.focus(), []);

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
    } catch (failure) {
      setError(plainFailure(failure));
      setBusy(false);
    }
  };
  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    event.stopPropagation();
    onKeep();
  };
  return (
    <div role="group" aria-labelledby={questionId} onKeyDown={onKeyDown} className="space-y-2.5 px-3 py-2.5">
      <p id={questionId} className="text-[13px] text-ink">
        {question}
      </p>
      {error && (
        <p role="alert" className="text-[12.5px] text-warn">
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="danger" onClick={() => void confirm()} loading={busy}>
          {confirmLabel}
        </Button>
        <Button ref={keep} size="sm" variant="secondary" onClick={onKeep} disabled={busy}>
          Keep
        </Button>
      </div>
    </div>
  );
}
