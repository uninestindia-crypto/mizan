import { Activity, ChevronDown } from "lucide-react";
import {
  type FocusEvent,
  type KeyboardEvent,
  type RefObject,
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";
import { cx } from "../ui";
import { ICON_TONE, ItemControl, type OnAction, TONE } from "./Chip";
import { attentionLabels, headline, type StatusItem } from "./statusItems";

const BUTTON =
  "relative flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-[var(--radius-control)] border px-2.5 " +
  "text-[12.5px] font-medium transition-colors";
const COMPACT =
  "size-10 justify-center rounded-lg border-transparent bg-transparent px-0 text-ink-2 hover:bg-surface-2";
const PANEL = "q-fade-in absolute z-30 rounded-2xl border border-line bg-surface p-1.5 shadow-[var(--shadow-pop)]";
const ROW = "flex w-full items-start gap-3 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-surface-2";
const DOT = "absolute -right-0.5 -top-0.5 size-2.5 rounded-full border-2 border-surface bg-brand";
const DOT_WHEN_NARROW = "hidden @max-[639px]:block";
const UNDER_BUTTON = "right-0 top-full mt-2 w-80 max-w-[calc(100vw-2rem)]";
const ACROSS_BAR = "inset-x-3 top-full mt-1";

interface Props {
  items: readonly StatusItem[];
  onAction: OnAction;
  /** "bar": the panel spans the bar it sits in (the phone). "button": a panel under the button (a wide window). */
  anchor?: "bar" | "button";
  /** Icon only, for the phone, where the button is one of four small ones. */
  compact?: boolean;
}

interface RowProps {
  item: StatusItem;
  onAction: OnAction;
  close: () => void;
}

function Row({ item, onAction, close }: RowProps) {
  const Icon = item.icon;
  const pick = (picked: StatusItem) => {
    close();
    onAction(picked);
  };
  return (
    <li>
      <ItemControl item={item} onAction={pick} className={ROW}>
        <Icon className={cx("mt-0.5 size-4 shrink-0", ICON_TONE[item.tone])} aria-hidden />
        <span className="min-w-0">
          <span className="block text-[13.5px] font-medium text-ink">{item.label}</span>
          <span className="mt-0.5 block text-[12.5px] leading-snug text-ink-2">{item.detail}</span>
        </span>
      </ItemControl>
    </li>
  );
}

interface ListProps {
  items: readonly StatusItem[];
  id: string;
  placement: string;
  onAction: OnAction;
  close: () => void;
}

function StatusList(props: ListProps) {
  const { items, id, placement, onAction, close } = props;
  return (
    <div id={id} role="group" aria-label="Market, prices and updates" className={cx(PANEL, placement)}>
      <ul className="space-y-0.5">
        {items.map((item) => (
          <Row key={item.id} item={item} onAction={onAction} close={close} />
        ))}
      </ul>
    </div>
  );
}

function useOutsideClick(open: boolean, close: () => void, box: RefObject<HTMLDivElement | null>) {
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      if (!box.current?.contains(event.target as Node)) close();
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open, close, box]);
}

/** Open or closed. Closes on Escape (handing focus back to the button), on a click elsewhere, and when Tab leaves. */
function usePopover() {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useOutsideClick(open, close, box);
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "Escape" || !open) return;
    event.stopPropagation();
    close();
    button.current?.focus();
  };
  const onBlur = (event: FocusEvent<HTMLDivElement>) => {
    const next = event.relatedTarget;
    if (next instanceof Node && !box.current?.contains(next)) close();
  };
  return { open, toggle: () => setOpen((was) => !was), close, box, button, onKeyDown, onBlur };
}

interface ButtonProps {
  item: StatusItem;
  /** The labels of everything that may need doing. */
  attention: readonly string[];
  open: boolean;
  panelId: string;
  compact: boolean;
  onClick: () => void;
}

/** The name a screen reader hears: "Status", what the button says, and anything else that may need doing. */
function buttonName(item: StatusItem, attention: readonly string[]): string {
  const others = attention.filter((label) => label !== item.label);
  return ["Status", item.label, ...others].join(". ");
}

function ButtonFace({ item, compact }: { item: StatusItem; compact: boolean }) {
  const Icon = item.icon;
  if (compact) return <Activity className="size-5" aria-hidden />;
  return (
    <>
      <Icon className={cx("size-3.5", ICON_TONE[item.tone])} aria-hidden />
      <span className="hidden @min-[640px]:inline @min-[1000px]:hidden">Status</span>
      <span className="hidden @min-[1000px]:inline">{item.label}</span>
      <ChevronDown className="hidden size-3 text-ink-3 @min-[640px]:block" aria-hidden />
    </>
  );
}

const StatusButton = ({ ref, ...p }: ButtonProps & { ref: RefObject<HTMLButtonElement | null> }) => (
  <button
    ref={ref}
    type="button"
    data-status-trigger=""
    aria-expanded={p.open}
    aria-controls={p.panelId}
    aria-label={buttonName(p.item, p.attention)}
    title={p.item.label}
    onClick={p.onClick}
    className={cx(BUTTON, p.compact ? COMPACT : TONE[p.item.tone])}
  >
    <ButtonFace item={p.item} compact={p.compact} />
    {p.attention.length > 0 && <span className={cx(DOT, p.compact ? "block" : DOT_WHEN_NARROW)} aria-hidden />}
  </button>
);

/**
 * The narrow bar's one "Status" button. It speaks for the most important item (an update, then old prices, then the
 * market) and opens a short list of the same items the wide bar shows as chips. A dot says something may need doing
 * where the words are hidden, and the same thing is in the button's name so the dot is never the only cue.
 */
export function StatusPopover({ items, onAction, anchor = "button", compact = false }: Props) {
  const pop = usePopover();
  const panelId = useId();
  const lead = headline(items);
  if (!lead) return null;
  const placement = anchor === "bar" ? ACROSS_BAR : UNDER_BUTTON;
  return (
    <div
      ref={pop.box}
      onKeyDown={pop.onKeyDown}
      onBlur={pop.onBlur}
      className={anchor === "button" ? "relative" : undefined}
    >
      <StatusButton
        ref={pop.button}
        item={lead}
        attention={attentionLabels(items)}
        open={pop.open}
        panelId={panelId}
        compact={compact}
        onClick={pop.toggle}
      />
      {pop.open && (
        <StatusList items={items} id={panelId} placement={placement} onAction={onAction} close={pop.close} />
      )}
    </div>
  );
}
