import { Command } from "cmdk";
import {
  BookOpenCheck,
  Bot,
  Briefcase,
  Calculator,
  CandlestickChart,
  FlaskConical,
  LayoutDashboard,
  Monitor,
  Moon,
  Scale,
  Search,
  Settings as SettingsIcon,
  ShieldCheck,
  Sun,
} from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router";
import { ageLabel, date, daysSince } from "../lib/format";
import { usePaperOrders, useSearch, useStatus, useUpdate, useUpdateSettings } from "../lib/queries";
import type { Theme } from "../lib/types";
import { CopilotButton } from "./copilot/CopilotButton";
import { CopilotDrawer } from "./copilot/CopilotDrawer";
import { CopilotProvider } from "./copilot/CopilotProvider";
import { SecondOpinionHost } from "./copilot/SecondOpinionHost";
import { Logo } from "./Logo";
import { Badge, cx } from "./ui";

const NAV = [
  { to: "/", label: "Home", icon: LayoutDashboard, end: true },
  { to: "/markets", label: "Markets", icon: CandlestickChart },
  { to: "/lab", label: "Strategy Lab", icon: FlaskConical },
  { to: "/portfolio", label: "Portfolio", icon: Briefcase },
  { to: "/paper", label: "Paper trading", icon: BookOpenCheck },
  { to: "/agents", label: "Agents", icon: Bot },
  { to: "/tools", label: "Tools", icon: Calculator },
];

export function Layout({ children }: { children: ReactNode }) {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    document.getElementById("main")?.focus({ preventScroll: true });
    window.scrollTo({ top: 0 });
  }, [location.pathname]);

  return (
    <CopilotProvider>
      <div className="flex h-full">
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2">
          Skip to content
        </a>
        <Sidebar onSearch={() => setPaletteOpen(true)} />
        <div className="flex min-w-0 flex-1 flex-col">
          <MobileBar onSearch={() => setPaletteOpen(true)} />
          <TopHeader onSearch={() => setPaletteOpen(true)} />
          <UpdateNotice />
          <main id="main" tabIndex={-1} className="min-w-0 flex-1 overflow-y-auto outline-none">
            <div className="q-fade-in mx-auto w-full max-w-[1320px] px-6 py-7 lg:px-10" key={location.pathname}>
              {children}
            </div>
          </main>
        </div>
        <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
      </div>
      <CopilotDrawer />
      <SecondOpinionHost />
    </CopilotProvider>
  );
}

/** A new release exists. Says what it is and links to it; installing is the person's decision. */
function UpdateNotice() {
  const update = useUpdate();
  const info = update.data;
  const [dismissed, setDismissed] = useState<string | null>(() => {
    try {
      return localStorage.getItem("quantos.update.dismissed");
    } catch {
      return null;
    }
  });
  if (!info?.update_available || !info.latest || dismissed === info.latest) return null;
  const hide = () => {
    setDismissed(info.latest);
    try {
      localStorage.setItem("quantos.update.dismissed", info.latest ?? "");
    } catch {
      /* the notice just comes back next time */
    }
  };
  return (
    <div role="status" className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-brand/25 bg-brand-soft px-6 py-2.5 text-[13.5px] text-ink lg:px-10">
      <span>
        <strong className="font-semibold">QuantOS {info.latest} is available.</strong> You have {info.current}.
      </span>
      <span className="flex items-center gap-4">
        {info.url && (
          <a href={info.url} target="_blank" rel="noreferrer" className="font-medium text-brand hover:underline">
            See what is new and download
          </a>
        )}
        <button type="button" onClick={hide} className="text-ink-3 hover:text-ink">
          Not now
        </button>
      </span>
    </div>
  );
}

/** How many paper-book orders are waiting for you, shown beside "Paper trading". Nothing when none. */
function useOrdersWaiting(): number {
  const status = useStatus();
  const inbox = usePaperOrders(status.data?.index.ready ?? false);
  return inbox.data?.pending ?? 0;
}

function OrdersPill({ count }: { count: number }) {
  if (count <= 0) return null;
  return (
    <span
      className="ml-auto inline-flex min-w-5 items-center justify-center rounded-full bg-brand px-1.5 text-[11px] font-semibold leading-5 text-on-brand"
      aria-label={`${count} orders waiting`}
    >
      {count}
    </span>
  );
}

function Sidebar({ onSearch }: { onSearch: () => void }) {
  const waiting = useOrdersWaiting();
  const status = useStatus();
  const latest = status.data?.index.latest_session;
  const age = daysSince(latest);
  const stale = age !== null && age > 5;
  return (
    <aside className="hidden w-[248px] shrink-0 flex-col border-r border-line bg-surface md:flex">
      <div className="flex h-16 items-center gap-2.5 px-5">
        <Logo className="size-8" />
        <div className="leading-tight">
          <div className="text-[15px] font-semibold tracking-tight text-ink">QuantOS</div>
          <div className="text-[11px] text-ink-3">Test before you trade</div>
        </div>
      </div>
      <div className="px-3 pb-2">
        <button
          type="button"
          onClick={onSearch}
          className="flex h-9 w-full items-center gap-2 rounded-[var(--radius-control)] border border-line bg-surface-2 px-3 text-[13px] text-ink-3 transition-colors hover:border-line-strong hover:text-ink-2"
        >
          <Search className="size-4" aria-hidden />
          <span className="flex-1 text-left">Search stocks</span>
          <kbd className="rounded border border-line bg-surface px-1.5 font-sans text-[10.5px] text-ink-3">Ctrl K</kbd>
        </button>
      </div>
      <nav aria-label="Main" className="flex-1 space-y-0.5 px-3 py-2">
        {(status.data?.settings?.shariah_mode
          ? [
              ...NAV.slice(0, 2),
              { to: "/shariah", label: "Mizan Shariah", icon: ShieldCheck },
              ...NAV.slice(2),
            ]
          : NAV
        ).map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cx(
                "group flex h-10 items-center gap-3 rounded-[var(--radius-control)] px-3 text-[14px] font-medium transition-colors",
                isActive ? "bg-brand-soft text-brand" : "text-ink-2 hover:bg-surface-2 hover:text-ink",
              )
            }
          >
            <Icon className="size-[18px] shrink-0" aria-hidden />
            {label}
            {to === "/paper" && <OrdersPill count={waiting} />}
          </NavLink>
        ))}
      </nav>
      <div className="space-y-3 border-t border-line p-3">
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            cx(
              "flex h-10 items-center gap-3 rounded-[var(--radius-control)] px-3 text-[14px] font-medium transition-colors",
              isActive ? "bg-brand-soft text-brand" : "text-ink-2 hover:bg-surface-2 hover:text-ink",
            )
          }
        >
          <SettingsIcon className="size-[18px]" aria-hidden />
          Settings
        </NavLink>
        <div className="rounded-[var(--radius-control)] bg-surface-2 px-3 py-2.5">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11.5px] font-medium uppercase tracking-wide text-ink-3">Market data</span>
            {status.data?.download.state === "RUNNING" ? (
              <Badge tone="brand">Downloading</Badge>
            ) : status.data?.index.job.state === "RUNNING" ? (
              <Badge tone="brand">Preparing</Badge>
            ) : status.data?.index.ready ? (
              <Badge tone={stale ? "warn" : "up"}>{stale && age !== null ? ageLabel(age) : "Up to date"}</Badge>
            ) : (
              <Badge tone="warn">No data yet</Badge>
            )}
          </div>
          <div className="num mt-1 text-[12.5px] text-ink-2">{status.data?.download.state === "RUNNING"
              ? `${status.data.download.done} of ${status.data.download.total} stocks`
              : latest
                ? `Last session ${date(latest)}`
                : "Get data in Settings"}</div>
        </div>
        <ThemeToggle />
      </div>
    </aside>
  );
}

function TopHeader({ onSearch }: { onSearch: () => void }) {
  const status = useStatus();
  const updateSettings = useUpdateSettings();
  const location = useLocation();
  const navigate = useNavigate();

  const isShariahActive = location.pathname.startsWith("/shariah");
  const shariahModeEnabled = Boolean(status.data?.settings?.shariah_mode);

  const handleSwitchMode = (mode: "quant" | "shariah") => {
    if (mode === "shariah") {
      if (!shariahModeEnabled) {
        updateSettings.mutate({ shariah_mode: true });
      }
      if (!isShariahActive) {
        void navigate("/shariah");
      }
    } else {
      if (isShariahActive) {
        void navigate("/");
      }
    }
  };

  const latest = status.data?.index.latest_session;

  return (
    <header className="hidden h-14 shrink-0 items-center justify-between border-b border-line bg-surface/90 px-6 backdrop-blur-[6px] md:flex">
      {/* 1-Click Executive Mode Switcher */}
      <div className="flex items-center gap-3">
        <div
          role="radiogroup"
          aria-label="Application Mode"
          className="flex rounded-[var(--radius-control)] border border-line bg-surface-2 p-0.5"
        >
          <button
            type="button"
            role="radio"
            aria-checked={!isShariahActive}
            onClick={() => handleSwitchMode("quant")}
            className={cx(
              "flex h-8 items-center gap-2 rounded-[7px] px-3.5 text-[13px] font-medium transition-all",
              !isShariahActive
                ? "bg-surface text-ink shadow-sm"
                : "text-ink-3 hover:text-ink",
            )}
          >
            <LayoutDashboard className="size-4" aria-hidden />
            <span>Institutional QuantOS</span>
          </button>

          <button
            type="button"
            role="radio"
            aria-checked={isShariahActive}
            onClick={() => handleSwitchMode("shariah")}
            className={cx(
              "flex h-8 items-center gap-2 rounded-[7px] px-3.5 text-[13px] font-medium transition-all",
              isShariahActive
                ? "bg-emerald-700 text-white shadow-sm"
                : "text-ink-3 hover:text-ink",
            )}
          >
            <Scale className="size-4" aria-hidden />
            <span>Mizan Shariah</span>
            {!shariahModeEnabled && !isShariahActive && (
              <span className="ml-1 rounded-full bg-emerald-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-800 dark:text-emerald-200">
                1-Click
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Right Controls: Market Status Badge + Search Trigger */}
      <div className="flex items-center gap-3">
        {status.data && (
          <div className="flex items-center gap-2 rounded-lg border border-line/60 bg-surface-2/60 px-2.5 py-1 text-[12px] text-ink-3">
            <span
              className={cx(
                "size-2 rounded-full",
                status.data.download.state === "RUNNING" || status.data.index.job.state === "RUNNING"
                  ? "bg-amber-500 animate-pulse"
                  : status.data.index.ready
                    ? "bg-emerald-500"
                    : "bg-amber-500",
              )}
            />
            <span>
              {status.data.download.state === "RUNNING"
                ? `Syncing (${status.data.download.done}/${status.data.download.total})`
                : status.data.index.job.state === "RUNNING"
                  ? "Indexing NSE..."
                  : status.data.index.ready
                    ? `NSE: ${latest ? date(latest) : "Ready"}`
                    : "NSE: Local Cache"}
            </span>
          </div>
        )}

        <CopilotButton />

        <button
          type="button"
          onClick={onSearch}
          className="flex h-8 items-center gap-2 rounded-[var(--radius-control)] border border-line bg-surface-2 px-3 text-[12.5px] text-ink-3 transition-colors hover:border-line-strong hover:text-ink"
        >
          <Search className="size-3.5" aria-hidden />
          <span>Search stocks</span>
          <kbd className="rounded border border-line bg-surface px-1.5 font-sans text-[10px] text-ink-3">
            Ctrl K
          </kbd>
        </button>
      </div>
    </header>
  );
}

function MobileBar({ onSearch }: { onSearch: () => void }) {
  const waiting = useOrdersWaiting();
  const status = useStatus();
  const location = useLocation();
  const navigate = useNavigate();
  const updateSettings = useUpdateSettings();
  const isShariah = location.pathname.startsWith("/shariah");
  const shariahModeEnabled = Boolean(status.data?.settings?.shariah_mode);

  const toggleMode = () => {
    if (isShariah) {
      void navigate("/");
    } else {
      if (!shariahModeEnabled) updateSettings.mutate({ shariah_mode: true });
      void navigate("/shariah");
    }
  };

  const navItems = status.data?.settings?.shariah_mode
    ? [
        ...NAV.slice(0, 2),
        { to: "/shariah", label: "Mizan Shariah", icon: ShieldCheck },
        ...NAV.slice(2),
        { to: "/settings", label: "Settings", icon: SettingsIcon, end: false },
      ]
    : [...NAV, { to: "/settings", label: "Settings", icon: SettingsIcon, end: false }];

  return (
    <div className="border-b border-line bg-surface md:hidden">
      <div className="flex h-14 items-center justify-between px-4">
        <div className="flex items-center gap-2">
          <Logo className="size-7" />
          <span className="text-[15px] font-semibold">QuantOS</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={toggleMode}
            aria-label="Switch Mode"
            className={cx(
              "flex h-7 items-center gap-1 rounded-full px-2.5 text-[11.5px] font-medium transition-colors",
              isShariah ? "bg-emerald-700 text-white" : "border border-line bg-surface-2 text-ink-2",
            )}
          >
            {isShariah ? <Scale className="size-3" /> : <LayoutDashboard className="size-3" />}
            <span>{isShariah ? "Shariah" : "Quant"}</span>
          </button>
          <CopilotButton compact />
          <button type="button" onClick={onSearch} aria-label="Search stocks" className="rounded-lg p-2 text-ink-2 hover:bg-surface-2">
            <Search className="size-5" aria-hidden />
          </button>
        </div>
      </div>
      <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-3 pb-2">
        {navItems.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cx(
                "flex h-8 shrink-0 items-center gap-1.5 rounded-full px-3 text-[13px] font-medium",
                isActive ? "bg-brand-soft text-brand" : "text-ink-2 hover:bg-surface-2",
              )
            }
          >
            <Icon className="size-4" aria-hidden />
            {label}
            {to === "/paper" && <OrdersPill count={waiting} />}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

function ThemeToggle() {
  const status = useStatus();
  const update = useUpdateSettings();
  const theme: Theme = status.data?.settings.theme ?? "system";
  const options: { value: Theme; icon: typeof Sun; label: string }[] = [
    { value: "light", icon: Sun, label: "Light" },
    { value: "dark", icon: Moon, label: "Dark" },
    { value: "system", icon: Monitor, label: "System" },
  ];
  return (
    <div role="radiogroup" aria-label="Theme" className="flex rounded-[var(--radius-control)] border border-line p-0.5">
      {options.map(({ value, icon: Icon, label }) => (
        <button
          key={value}
          type="button"
          role="radio"
          aria-checked={theme === value}
          aria-label={label}
          title={label}
          onClick={() => update.mutate({ theme: value })}
          className={cx(
            "flex h-7 flex-1 items-center justify-center rounded-[7px] transition-colors",
            theme === value ? "bg-surface-2 text-ink" : "text-ink-3 hover:text-ink",
          )}
        >
          <Icon className="size-4" aria-hidden />
        </button>
      ))}
    </div>
  );
}

function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const [query, setQuery] = useState("");
  const navigate = useNavigate();
  const results = useSearch(query);
  // The list for the latest keystroke may still be on its way; never offer an earlier query's answer.
  const stocks = results.isPlaceholderData ? [] : (results.data ?? []);
  const pages = [...NAV, { to: "/settings", label: "Settings", icon: SettingsIcon }].filter(
    (n) => !query || n.label.toLowerCase().includes(query.toLowerCase()),
  );
  const [selected, setSelected] = useState("");
  // Highlight the best match so Enter does something without arrowing down first.
  const best = stocks[0] ? `stock-${stocks[0].symbol}` : pages[0] ? `page-${pages[0].to}` : "";
  useEffect(() => setSelected(best), [best]);
  const go = (to: string) => {
    onOpenChange(false);
    setQuery("");
    void navigate(to);
  };
  return (
    <Command.Dialog
      open={open}
      onOpenChange={onOpenChange}
      label="Search stocks and pages"
      shouldFilter={false}
      value={selected}
      onValueChange={setSelected}
      overlayClassName="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]"
      contentClassName="q-fade-in fixed left-1/2 top-[14vh] z-50 w-[calc(100vw-2rem)] max-w-xl -translate-x-1/2 overflow-hidden rounded-2xl border border-line bg-surface shadow-[var(--shadow-pop)]"
    >
      <div className="flex items-center gap-3 border-b border-line px-4">
        <Search className="size-4 text-ink-3" aria-hidden />
        <Command.Input
          value={query}
          onValueChange={setQuery}
          placeholder="Search a stock or ETF, or jump to a page…"
          className="h-14 w-full bg-transparent text-[15px] text-ink outline-none placeholder:text-ink-3"
        />
      </div>
      <Command.List className="max-h-[50vh] overflow-y-auto p-2">
        <Command.Empty className="px-3 py-6 text-center text-sm text-ink-3">{results.isFetching && query.trim() ? "Searching…" : "No matches."}</Command.Empty>
        {stocks.length > 0 && (
          <Command.Group heading="Stocks" className="px-1 text-[11.5px] font-medium uppercase tracking-wide text-ink-3 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5">
            {stocks.map((r) => (
              <Command.Item
                key={r.symbol}
                value={`stock-${r.symbol}`}
                onSelect={() => go(`/stock/${r.symbol}`)}
                className="flex cursor-pointer items-center justify-between rounded-lg px-3 py-2.5 text-sm normal-case tracking-normal text-ink data-[selected=true]:bg-surface-2"
              >
                <span className="flex items-center gap-2">
                  <span className="font-semibold">{r.symbol}</span>
                  <span className="truncate text-ink-3">{r.name}</span>
                </span>
                {r.is_etf ? <Badge tone="violet">ETF</Badge> : null}
              </Command.Item>
            ))}
          </Command.Group>
        )}
        {pages.length > 0 && (
        <Command.Group heading="Pages" className="px-1 text-[11.5px] font-medium uppercase tracking-wide text-ink-3 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5">
          {pages.map(({ to, label, icon: Icon }) => (
              <Command.Item
                key={to}
                value={`page-${to}`}
                onSelect={() => go(to)}
                className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-sm normal-case tracking-normal text-ink data-[selected=true]:bg-surface-2"
              >
                <Icon className="size-4 text-ink-3" aria-hidden />
                {label}
              </Command.Item>
            ))}
        </Command.Group>
        )}
      </Command.List>
    </Command.Dialog>
  );
}
