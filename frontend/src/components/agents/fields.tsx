import { clsx } from "clsx";
import type { ReactNode, TextareaHTMLAttributes } from "react";

// Small form pieces the agent form shares. They match the look of the app's own Input.

const textAreaClass =
  "min-h-[5.5rem] w-full resize-y rounded-[var(--radius-control)] border bg-surface px-3 py-2 text-sm text-ink " +
  "placeholder:text-ink-3 transition-colors hover:border-line-strong focus:border-brand focus:outline-none " +
  "focus:ring-3 focus:ring-brand/15 disabled:opacity-60";

type TextAreaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean };

export function TextArea({ invalid, className, ...rest }: TextAreaProps) {
  const border = invalid ? "border-down" : "border-line";
  return <textarea aria-invalid={invalid || undefined} className={clsx(textAreaClass, border, className)} {...rest} />;
}

/** Red border for a field with a problem, in addition to the message under it. */
export function invalidClass(invalid: boolean): string | undefined {
  return invalid ? "border-down hover:border-down" : undefined;
}

/** Each message on its own line, exactly as written; undefined when there are none, so the field's hint stays. */
export function problemText(list: string[]): ReactNode {
  if (list.length === 0) return undefined;
  return list.map((message) => (
    <span key={message} className="block">
      {message}
    </span>
  ));
}

interface GroupProps {
  legend: string;
  hint?: ReactNode;
  error?: ReactNode;
  children: ReactNode;
}

/** A group of controls (the ticks, the steps) with a heading, a hint and the problems for the whole group. */
export function FieldGroup({ legend, hint, error, children }: GroupProps) {
  return (
    <fieldset className="min-w-0 space-y-2">
      <legend className="text-[13px] font-medium text-ink-2">{legend}</legend>
      {hint && <p className="text-[12.5px] text-ink-3">{hint}</p>}
      {children}
      {error && <p className="text-[12.5px] text-down">{error}</p>}
    </fieldset>
  );
}

const BADGE_CLASS =
  "num flex size-6 shrink-0 items-center justify-center rounded-full bg-surface-2 text-[12px] font-semibold text-ink-2";

/** The round number beside a step. The list around it already says the order, so it is hidden from screen readers. */
export function NumberBadge({ number, className }: { number: number; className?: string }) {
  return (
    <span className={clsx(BADGE_CLASS, className)} aria-hidden>
      {number}
    </span>
  );
}
