import { BookOpen, Coins, Layers, Scale, ShieldCheck, type LucideIcon } from "lucide-react";
import { cx } from "../ui";

export type ShariahTab = "screener" | "baskets" | "purification" | "zakat" | "academy";

const TABS: { id: ShariahTab; label: string; icon: LucideIcon }[] = [
  { id: "screener", label: "Equities Screener", icon: ShieldCheck },
  { id: "baskets", label: "Thematic Baskets", icon: Layers },
  { id: "purification", label: "Dividend Purification", icon: Coins },
  { id: "zakat", label: "Equity Zakat", icon: Scale },
  { id: "academy", label: "Academy & Demat Guide", icon: BookOpen },
];

const TAB =
  "-mb-px flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors whitespace-nowrap";

export function ShariahTabs({ tab, onTab }: { tab: ShariahTab; onTab: (tab: ShariahTab) => void }) {
  return (
    <nav aria-label="Shariah modules" className="flex gap-1 overflow-x-auto border-b border-line">
      {TABS.map(({ id, label, icon: Icon }) => (
        <button
          key={id}
          type="button"
          onClick={() => onTab(id)}
          className={cx(TAB, tab === id ? "border-brand text-ink" : "border-transparent text-ink-3 hover:text-ink")}
        >
          <Icon className="size-4" />
          {label}
        </button>
      ))}
    </nav>
  );
}
