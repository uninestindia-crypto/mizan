import { type KeyboardEvent, type ReactNode, useId, useRef, useState } from "react";
import type { Portfolio, PortfolioRow } from "../../lib/types";
import { cx } from "../ui";
import type { AccountChoice } from "./accountQueries";

/** What every tab is given about the portfolio being viewed. */
export interface TabContext {
  data: Portfolio;
  choice: AccountChoice;
  /** More than one account exists, so screens say which account each stock is in. */
  showAccounts: boolean;
  onEdit: (row: PortfolioRow) => void;
  onRemove: (row: PortfolioRow) => void;
}

/**
 * One tab of the Portfolio. To add a tab, add a line to the list in `tabRegistry.tsx`: an id that never changes,
 * the name people read, and what to show. Nothing else needs to change.
 */
export interface PortfolioTab {
  id: string;
  label: string;
  render: (context: TabContext) => ReactNode;
}

/**
 * The tabs of the Portfolio. With one tab there is nothing to choose, so it shows the tab alone, with no row of tabs.
 */
export function PortfolioTabs({ tabs, context }: { tabs: readonly PortfolioTab[]; context: TabContext }) {
  const [selected, setSelected] = useState(tabs[0]?.id);
  const current = tabs.find((t) => t.id === selected) ?? tabs[0];
  const ids = useId();
  if (!current) return null;
  return (
    <div className="space-y-4">
      {tabs.length > 1 && <TabRow tabs={tabs} current={current.id} ids={ids} onSelect={setSelected} />}
      <div role={tabs.length > 1 ? "tabpanel" : undefined} id={`${ids}-panel`} aria-labelledby={`${ids}-${current.id}`}>
        {current.render(context)}
      </div>
    </div>
  );
}

const STEPS: Record<string, number> = { ArrowRight: 1, ArrowLeft: -1 };

/** The tab an arrow key moves to from the tab at `index`, wrapping round; undefined for any other key. */
export function neighbour(tabs: readonly PortfolioTab[], index: number, key: string): PortfolioTab | undefined {
  const step = STEPS[key];
  return step === undefined ? undefined : tabs[(index + step + tabs.length) % tabs.length];
}

function TabRow(props: {
  tabs: readonly PortfolioTab[];
  current: string;
  ids: string;
  onSelect: (id: string) => void;
}) {
  const buttons = useRef<Record<string, HTMLButtonElement | null>>({});
  const move = (event: KeyboardEvent, index: number) => {
    const next = neighbour(props.tabs, index, event.key);
    if (!next) return;
    event.preventDefault();
    props.onSelect(next.id);
    buttons.current[next.id]?.focus();
  };
  const refFor = (id: string) => (node: HTMLButtonElement | null) => {
    buttons.current[id] = node;
  };
  return (
    <div role="tablist" aria-label="Portfolio sections" className="flex gap-1 border-b border-line">
      {props.tabs.map((tab, index) => (
        <TabButton
          key={tab.id}
          tab={tab}
          ids={props.ids}
          active={tab.id === props.current}
          buttonRef={refFor(tab.id)}
          onSelect={() => props.onSelect(tab.id)}
          onKeyDown={(event) => move(event, index)}
        />
      ))}
    </div>
  );
}

function TabButton(props: {
  tab: PortfolioTab;
  ids: string;
  active: boolean;
  buttonRef: (node: HTMLButtonElement | null) => void;
  onSelect: () => void;
  onKeyDown: (event: KeyboardEvent) => void;
}) {
  return (
    <button
      ref={props.buttonRef}
      id={`${props.ids}-${props.tab.id}`}
      type="button"
      role="tab"
      aria-selected={props.active}
      aria-controls={`${props.ids}-panel`}
      tabIndex={props.active ? 0 : -1}
      onClick={props.onSelect}
      onKeyDown={props.onKeyDown}
      className={cx(
        "-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
        props.active ? "border-brand text-brand" : "border-transparent text-ink-3 hover:text-ink",
      )}
    >
      {props.tab.label}
    </button>
  );
}
