import { type KeyboardEvent, useRef } from "react";
import type { AccountLine } from "../../lib/types";
import { cx } from "../ui";
import type { AccountChoice } from "./accountQueries";
import { type SwitchEntry, switchEntries } from "./accountText";
import { AccountPicker } from "./AccountPicker";

/** Up to this many accounts sit side by side as buttons; more are chosen from a list that can be searched. */
export const MAX_SIDE_BY_SIDE = 6;

interface SwitcherProps {
  accounts: readonly AccountLine[];
  choice: AccountChoice;
  onChoose: (choice: AccountChoice) => void;
}

/** Which account the Portfolio shows: "All accounts" or one of them. */
export function AccountSwitcher(props: SwitcherProps) {
  if (props.accounts.length > MAX_SIDE_BY_SIDE) return <AccountPicker {...props} />;
  return <AccountButtons {...props} />;
}

// On a phone the buttons sit in one row that slides sideways, so they do not push the holdings off the screen.
const ROW = "-mx-6 flex gap-2 overflow-x-auto px-6 pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0";

const ARROWS: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };

function AccountButtons({ accounts, choice, onChoose }: SwitcherProps) {
  const entries = switchEntries(accounts);
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  const refAt = (index: number) => (node: HTMLButtonElement | null) => {
    buttons.current[index] = node;
  };
  const selected = Math.max(
    entries.findIndex((e) => e.key === choice),
    0,
  );
  const move = (event: KeyboardEvent, from: number) => {
    const step = ARROWS[event.key];
    if (step === undefined) return;
    event.preventDefault();
    const to = (from + step + entries.length) % entries.length;
    buttons.current[to]?.focus();
    onChoose(entries[to]!.key);
  };

  return (
    <div role="radiogroup" aria-label="Choose an account" className={ROW}>
      {entries.map((entry, index) => (
        <AccountButton
          key={entry.key}
          entry={entry}
          checked={index === selected}
          onPick={() => onChoose(entry.key)}
          onKeyDown={(event) => move(event, index)}
          buttonRef={refAt(index)}
        />
      ))}
    </div>
  );
}

function AccountButton(props: {
  entry: SwitchEntry;
  checked: boolean;
  onPick: () => void;
  onKeyDown: (event: KeyboardEvent) => void;
  buttonRef: (node: HTMLButtonElement | null) => void;
}) {
  return (
    <button
      ref={props.buttonRef}
      type="button"
      role="radio"
      aria-checked={props.checked}
      tabIndex={props.checked ? 0 : -1}
      onClick={props.onPick}
      onKeyDown={props.onKeyDown}
      className={cx(
        "min-h-11 max-w-full shrink-0 rounded-[var(--radius-control)] border px-3.5 py-1.5 text-left transition-colors",
        props.checked
          ? "border-brand bg-brand-soft"
          : "border-line bg-surface hover:border-line-strong hover:bg-surface-2",
      )}
    >
      <span className={cx("block truncate text-sm font-semibold", props.checked ? "text-brand" : "text-ink")}>
        {props.entry.name}
      </span>
      <span className="num block truncate text-[12px] text-ink-3">{props.entry.detail}</span>
    </button>
  );
}
