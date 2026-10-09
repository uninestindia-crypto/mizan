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
  Search,
  Settings as SettingsIcon,
  ShieldCheck,
  Sun,
} from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router";
import { ageLabel, date, daysSince } from "../lib/format";
import { usePaperOrders, useSearch, useStatus, useUpdateSettings } from "../lib/queries";
import type { Theme } from "../lib/types";
import { CopilotButton } from "./copilot/CopilotButton";
import { CopilotDrawer } from "./copilot/CopilotDrawer";
import { CopilotProvider } from "./copilot/CopilotProvider";
import { SecondOpinionHost } from "./copilot/SecondOpinionHost";
import { SecondOpinionReady } from "./copilot/SecondOpinionReady";
import { Logo } from "./Logo";
import { ModeFilterNote } from "./mode/ModeFilterNote";
import { ModeNotice, PhoneModeButton } from "./mode/ModeSwitch";
import { ShariahBadge } from "./mode/ShariahBadge";
import { useModeFilter } from "./mode/useModeFilter";
import { StatusArea } from "./topbar/StatusArea";
import { TopBar } from "./topbar/TopBar";
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
    // Someone who just used the mode switch stays on it, so they hear which mode they are in.
    const onSwitch = document.activeElement?.closest("[data-mode-switch]");
    if (!onSwitch) document.getElementById("main")?.focus({ preventScroll: true });
    window.scrollTo({ top: 0 });
  }, [location.pathname]);

  return (
    <CopilotProvider>
      <div className="flex h-full">
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2">
          Skip to content
        </a>
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <MobileBar onSearch={() => setPaletteOpen(true)} />
          <TopBar onSearch={() => setPaletteOpen(true)} />
          <ModeNotice />
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

function Sidebar() {
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

function phoneNavStyle({ isActive }: { isActive: boolean }): string {
  const base = "flex h-8 shrink-0 items-center gap-1.5 rounded-full px-3 text-[13px] font-medium";
  return cx(base, isActive ? "bg-brand-soft text-brand" : "text-ink-2 hover:bg-surface-2");
}

type PhoneNavItem = { to: string; label: string; icon: typeof SettingsIcon; end?: boolean };

function PhoneNavLink({ item, waiting }: { item: PhoneNavItem; waiting: number }) {
  const Icon = item.icon;
  return (
    <NavLink to={item.to} end={item.end} className={phoneNavStyle}>
      <Icon className="size-4" aria-hidden />
      {item.label}
      {item.to === "/paper" && <OrdersPill count={waiting} />}
    </NavLink>
  );
}

function PhoneNav() {
  const waiting = useOrdersWaiting();
  const status = useStatus();
  const settings = { to: "/settings", label: "Settings", icon: SettingsIcon, end: false };
  const mizan = { to: "/shariah", label: "Mizan Shariah", icon: ShieldCheck, end: false };
  const items: PhoneNavItem[] = status.data?.settings?.shariah_mode
    ? [...NAV.slice(0, 2), mizan, ...NAV.slice(2), settings]
    : [...NAV, settings];
  return (
    <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-3 pb-2">
      {items.map((item) => (
        <PhoneNavLink key={item.to} item={item} waiting={waiting} />
      ))}
    </nav>
  );
}

function MobileBar({ onSearch }: { onSearch: () => void }) {
  const searchStyle = "rounded-lg p-2 text-ink-2 hover:bg-surface-2";
  return (
    <div className="relative z-20 border-b border-line bg-surface md:hidden">
      <div className="flex h-14 items-center justify-between gap-2 px-4">
        <div className="flex min-w-0 items-center gap-2">
          <Logo className="size-7 shrink-0" />
          <span className="hidden truncate text-[15px] font-semibold min-[380px]:inline">QuantOS</span>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <PhoneModeButton />
          <SecondOpinionReady />
          <CopilotButton compact />
          <StatusArea layout="phone" />
          <button type="button" onClick={onSearch} aria-label="Search stocks" className={searchStyle}>
            <Search className="size-5" aria-hidden />
          </button>
        </div>
      </div>
      <PhoneNav />
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
  const found = results.isPlaceholderData ? [] : (results.data ?? []);
  const filter = useModeFilter(found, "search");
  const stocks = filter.visible;
  const empty = filter.nothingLeft ? "No Shariah-compliant matches." : "No matches.";
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
        <Command.Empty className="px-3 py-6 text-center text-sm text-ink-3">{results.isFetching && query.trim() ? "Searching…" : empty}</Command.Empty>
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
                <span className="flex shrink-0 items-center gap-1.5">
                  <ShariahBadge compact status={filter.statusOf(r.symbol)} />
                  {r.is_etf ? <Badge tone="violet">ETF</Badge> : null}
                </span>
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
      <ModeFilterNote filter={filter} className="border-t border-line px-4 py-2.5" />
    </Command.Dialog>
  );
}
