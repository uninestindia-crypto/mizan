import { Search } from "lucide-react";

// Looks like a search field and opens the app's search window, where the typing happens. The bar is a container, so the
// field shows its words from 1000 px of bar and its key hint from 1100 px; below that it is an icon with the same name.
const FIELD =
  "flex h-9 shrink-0 items-center gap-2 rounded-[var(--radius-control)] border border-line bg-surface-2 px-2.5 " +
  "text-[13px] text-ink-3 transition-colors hover:border-line-strong hover:text-ink-2 " +
  "@min-[1000px]:w-56 @min-[1100px]:w-64";
const WORDS = "sr-only @min-[1000px]:not-sr-only @min-[1000px]:flex-1 @min-[1000px]:truncate @min-[1000px]:text-left";
const KEY_HINT =
  "hidden rounded border border-line bg-surface px-1.5 font-sans text-[10.5px] text-ink-3 @min-[1100px]:inline";

export function SearchField({ onSearch }: { onSearch: () => void }) {
  return (
    <button
      type="button"
      onClick={onSearch}
      aria-keyshortcuts="Control+K"
      title="Search stocks and pages (Ctrl K)"
      className={FIELD}
    >
      <Search className="size-4 shrink-0" aria-hidden />
      <span className={WORDS}>Search stocks, pages…</span>
      <kbd className={KEY_HINT} aria-hidden>
        Ctrl K
      </kbd>
    </button>
  );
}
