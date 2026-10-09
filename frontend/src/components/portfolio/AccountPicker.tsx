import { Check, ChevronDown, Search } from "lucide-react";
import { type KeyboardEvent, useId, useRef, useState } from "react";
import type { AccountLine } from "../../lib/types";
import { cx } from "../ui";
import type { AccountChoice } from "./accountQueries";
import { type SwitchEntry, switchEntries } from "./accountText";

// For many accounts: one button showing the account in view, and a list under it that can be searched.

const TRIGGER =
  "flex min-h-11 w-full max-w-md items-center justify-between gap-3 rounded-[var(--radius-control)] border " +
  "border-line bg-surface px-3.5 py-2 text-left hover:border-line-strong";
const PANEL =
  "absolute left-0 top-full z-30 mt-1.5 w-full max-w-md rounded-xl border border-line bg-surface p-2 " +
  "shadow-[var(--shadow-pop)]";
const SEARCH =
  "h-10 w-full rounded-[var(--radius-control)] border border-line bg-surface pl-8 pr-3 text-sm text-ink " +
  "placeholder:text-ink-3 focus:border-brand focus:outline-none focus:ring-3 focus:ring-brand/15";

const SEARCH_ICON = "pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-3";

interface PickerProps {
  accounts: readonly AccountLine[];
  choice: AccountChoice;
  onChoose: (choice: AccountChoice) => void;
}

/** What the picker remembers while it is open: the typed words, and which line of the list is lit. */
function usePicker(entries: SwitchEntry[], onChoose: PickerProps["onChoose"]) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [lit, setLit] = useState(0);
  const trigger = useRef<HTMLButtonElement>(null);
  const needle = query.trim().toLowerCase();
  const shown = needle ? entries.filter((e) => e.haystack.includes(needle)) : entries;
  const at = Math.min(lit, Math.max(shown.length - 1, 0));

  const close = (refocus: boolean) => {
    setOpen(false);
    setQuery("");
    setLit(0);
    if (refocus) trigger.current?.focus();
  };
  const pick = (entry: SwitchEntry | undefined) => {
    if (!entry) return;
    onChoose(entry.key);
    close(true);
  };
  const move = (step: number) => setLit((at + step + shown.length) % Math.max(shown.length, 1));
  const onKey = (event: KeyboardEvent) => {
    const keys: Record<string, () => void> = {
      ArrowDown: () => move(1),
      ArrowUp: () => move(-1),
      Enter: () => pick(shown[at]),
      Escape: () => close(true),
    };
    const run = keys[event.key];
    if (!run) return;
    event.preventDefault();
    run();
  };
  return { open, setOpen, query, setQuery, shown, at, trigger, close, pick, onKey };
}

export function AccountPicker({ accounts, choice, onChoose }: PickerProps) {
  const entries = switchEntries(accounts);
  const current = entries.find((e) => e.key === choice) ?? entries[0];
  const picker = usePicker(entries, onChoose);
  const ids = useId();
  return (
    <div
      className="relative"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) picker.close(false);
      }}
    >
      <button
        ref={picker.trigger}
        type="button"
        className={TRIGGER}
        aria-haspopup="listbox"
        aria-expanded={picker.open}
        aria-controls={`${ids}-box`}
        onClick={() => (picker.open ? picker.close(false) : picker.setOpen(true))}
      >
        <span className="min-w-0">
          <span className="block text-[12px] text-ink-3">Account</span>
          <span className="block truncate text-sm font-semibold text-ink">{current?.name}</span>
        </span>
        <ChevronDown className="size-4 shrink-0 text-ink-3" aria-hidden />
      </button>
      {picker.open && <PickerPanel ids={ids} choice={choice} picker={picker} />}
    </div>
  );
}

function PickerPanel(props: { ids: string; choice: AccountChoice; picker: ReturnType<typeof usePicker> }) {
  const { picker, ids } = props;
  return (
    <div id={`${ids}-box`} className={PANEL}>
      <div className="relative mb-1.5">
        <Search className={SEARCH_ICON} aria-hidden />
        <input
          autoFocus
          role="combobox"
          aria-expanded
          aria-controls={`${ids}-list`}
          aria-activedescendant={`${ids}-o${picker.at}`}
          aria-label="Find an account"
          placeholder="Find an account"
          className={SEARCH}
          value={picker.query}
          onChange={(event) => picker.setQuery(event.target.value)}
          onKeyDown={picker.onKey}
        />
      </div>
      <PickerOptions ids={ids} choice={props.choice} picker={picker} />
    </div>
  );
}

function PickerOptions(props: { ids: string; choice: AccountChoice; picker: ReturnType<typeof usePicker> }) {
  const { picker, ids } = props;
  if (picker.shown.length === 0) {
    return (
      <p role="status" className="px-2 py-3 text-[13px] text-ink-2">
        No account matches “{picker.query.trim()}”.
      </p>
    );
  }
  return (
    <ul id={`${ids}-list`} role="listbox" aria-label="Accounts" className="max-h-72 overflow-y-auto">
      {picker.shown.map((entry, index) => (
        <PickerOption
          key={entry.key}
          id={`${ids}-o${index}`}
          entry={entry}
          chosen={entry.key === props.choice}
          lit={index === picker.at}
          onPick={() => picker.pick(entry)}
        />
      ))}
    </ul>
  );
}

function PickerOption(props: { id: string; entry: SwitchEntry; chosen: boolean; lit: boolean; onPick: () => void }) {
  return (
    <li
      id={props.id}
      role="option"
      aria-selected={props.chosen}
      onMouseDown={(event) => event.preventDefault()}
      onClick={props.onPick}
      className={cx(
        "flex cursor-pointer items-center justify-between gap-3 rounded-lg px-2.5 py-2",
        props.lit ? "bg-surface-2" : "hover:bg-surface-2",
      )}
    >
      <span className="min-w-0">
        <span className="block truncate text-sm font-medium text-ink">{props.entry.name}</span>
        <span className="num block truncate text-[12px] text-ink-3">{props.entry.detail}</span>
      </span>
      {props.chosen && <Check className="size-4 shrink-0 text-brand" aria-hidden />}
    </li>
  );
}
