import type { ReactNode } from "react";
import { Link } from "react-router";
import { cx, Tooltip } from "../ui";
import type { ChipTone } from "./marketHours";
import type { StatusItem } from "./statusItems";

// One thing the top bar says, as a small button or link. Always a word (colour and icon only help), with the longer
// sentence in a tooltip. Focus rings come from the app-wide :focus-visible rule in styles.css.

const CHIP =
  "flex h-8 shrink-0 items-center gap-2 whitespace-nowrap rounded-[var(--radius-control)] border px-2.5 " +
  "text-[12.5px] font-medium transition-colors";

export const TONE: Record<ChipTone, string> = {
  neutral: "border-line bg-surface-2 text-ink-2 hover:border-line-strong hover:text-ink",
  ok: "border-line bg-surface-2 text-ink-2 hover:border-line-strong hover:text-ink",
  warn: "border-warn/40 bg-warn-soft text-ink hover:border-warn",
  brand: "border-brand/40 bg-brand-soft text-brand hover:border-brand",
};

export const ICON_TONE: Record<ChipTone, string> = {
  neutral: "text-ink-3",
  ok: "text-up",
  warn: "text-warn",
  brand: "text-brand",
};

export type OnAction = (item: StatusItem) => void;

interface ControlProps {
  item: StatusItem;
  onAction: OnAction;
  className: string;
  children: ReactNode;
}

/**
 * The link or button behind an item: a screen to go to, or the update window to open. The update button is marked as
 * the bar's trigger, so focus has somewhere to go back to when the update window closes.
 */
export function ItemControl({ item, onAction, className, children }: ControlProps) {
  if (item.to) {
    return (
      <Link to={item.to} className={className}>
        {children}
      </Link>
    );
  }
  return (
    <button type="button" onClick={() => onAction(item)} className={className} data-status-trigger="">
      {children}
    </button>
  );
}

export function Chip({ item, onAction }: { item: StatusItem; onAction: OnAction }) {
  const Icon = item.icon;
  return (
    <Tooltip content={item.detail}>
      <ItemControl item={item} onAction={onAction} className={cx(CHIP, TONE[item.tone])}>
        <Icon className={cx("size-3.5 shrink-0", ICON_TONE[item.tone])} aria-hidden />
        <span>{item.label}</span>
      </ItemControl>
    </Tooltip>
  );
}

/** The chips side by side, as the wide bar shows them. */
export function ChipRow({ items, onAction }: { items: readonly StatusItem[]; onAction: OnAction }) {
  if (items.length === 0) return null;
  return (
    <div role="group" aria-label="Status" className="flex items-center gap-2">
      {items.map((item) => (
        <Chip key={item.id} item={item} onAction={onAction} />
      ))}
    </div>
  );
}
