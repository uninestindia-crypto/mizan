import { Bot, Copy, Database, ExternalLink, Info, KeyRound, Landmark, RefreshCw, UserRound } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import { NavLink, useParams } from "react-router";
import { AsOf } from "../components/common";
import { Badge, Button, Callout, Card, CardHeader, cx, Field, Input, PageHeader, ProgressBar, Segmented, Skeleton } from "../components/ui";
import { errorMessage } from "../lib/api";
import { date, dateTime, inr, int } from "../lib/format";
import { useAiTools, useBuildIndex, useSecretMutation, useSecrets, useSetDataFolder, useStatus, useUpdateSettings } from "../lib/queries";
import type { Secret, Style, Theme } from "../lib/types";

const SECTIONS = [
  { id: "profile", label: "Profile & money rules", icon: UserRound },
  { id: "charges", label: "Broker charges", icon: Landmark },
  { id: "data", label: "Market data", icon: Database },
  { id: "accounts", label: "Accounts & keys", icon: KeyRound },
  { id: "ai", label: "AI assistants", icon: Bot },
  { id: "about", label: "About", icon: Info },
];

export default function Settings() {
  const { section = "profile" } = useParams();
  return (
    <>
      <PageHeader title="Settings" />
      <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
        <nav aria-label="Settings" className="flex gap-1 overflow-x-auto lg:flex-col">
          {SECTIONS.map(({ id, label, icon: Icon }) => (
            <NavLink
              key={id}
              to={`/settings/${id}`}
              className={({ isActive }) =>
                cx(
                  "flex h-10 shrink-0 items-center gap-2.5 rounded-[var(--radius-control)] px-3 text-sm font-medium transition-colors",
                  isActive ? "bg-surface text-ink shadow-[var(--shadow-card)] ring-1 ring-line" : "text-ink-2 hover:bg-surface-2 hover:text-ink",
                )
              }
            >
              <Icon className="size-4" aria-hidden />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="min-w-0 space-y-5">
          {section === "charges" ? (
            <Charges />
          ) : section === "data" ? (
            <DataSection />
          ) : section === "accounts" ? (
            <Accounts />
          ) : section === "ai" ? (
            <AiAssistants />
          ) : section === "about" ? (
            <About />
          ) : (
            <Profile />
          )}
        </div>
      </div>
    </>
  );
}

function SaveBar({ dirty, saving, onSave, error, saved }: { dirty: boolean; saving: boolean; onSave: () => void; error: unknown; saved: boolean }) {
  return (
    <div className="mt-6 flex items-center gap-3">
      <Button onClick={onSave} disabled={!dirty} loading={saving}>
        Save changes
      </Button>
      {saved && !dirty && <span className="text-[13px] text-up">Saved</span>}
      {error ? <span className="text-[13px] text-down">{errorMessage(error)}</span> : null}
    </div>
  );
}

function Profile() {
  const status = useStatus();
  const update = useUpdateSettings();
  const settings = status.data?.settings;
  const [style, setStyle] = useState<Style>(settings?.style ?? "both");
  const [capital, setCapital] = useState(settings?.money.capital ?? "");
  const [risk, setRisk] = useState(settings?.money.risk_per_trade_pct ?? "");
  const [daily, setDaily] = useState(settings?.money.daily_loss_limit_pct ?? "");
  useEffect(() => {
    if (!settings) return;
    setStyle(settings.style ?? "both");
    setCapital(settings.money.capital);
    setRisk(settings.money.risk_per_trade_pct);
    setDaily(settings.money.daily_loss_limit_pct);
  }, [settings]);
  if (!settings) return <Skeleton className="h-64" />;
  const dirty =
    style !== (settings.style ?? "both") || capital !== settings.money.capital || risk !== settings.money.risk_per_trade_pct || daily !== settings.money.daily_loss_limit_pct;
  return (
    <>
      <Card>
        <CardHeader title="How you invest" />
        <Segmented<Style>
          label="Investing style"
          value={style}
          onChange={setStyle}
          options={[
            { value: "investor", label: "Investor" },
            { value: "swing", label: "Swing trader" },
            { value: "both", label: "Both" },
          ]}
        />
      </Card>
      <Card>
        <CardHeader title="Money rules" subtitle="Used for position sizing and as the default capital in the Strategy Lab." />
        <div className="grid gap-5 sm:grid-cols-3">
          <Field label="Capital" htmlFor="st-cap">
            <Input id="st-cap" prefix="₹" inputMode="numeric" value={capital} onChange={(e) => setCapital(e.target.value.replace(/[^\d.]/g, ""))} />
          </Field>
          <Field label="Risk per trade" htmlFor="st-risk" hint="Up to 10%">
            <Input id="st-risk" suffix="%" inputMode="decimal" value={risk} onChange={(e) => setRisk(e.target.value.replace(/[^\d.]/g, ""))} />
          </Field>
          <Field label="Daily loss limit" htmlFor="st-daily" hint="Up to 20%">
            <Input id="st-daily" suffix="%" inputMode="decimal" value={daily} onChange={(e) => setDaily(e.target.value.replace(/[^\d.]/g, ""))} />
          </Field>
        </div>
        <SaveBar
          dirty={dirty}
          saving={update.isPending}
          saved={update.isSuccess}
          error={update.error}
          onSave={() => update.mutate({ style, money: { capital, risk_per_trade_pct: risk, daily_loss_limit_pct: daily } })}
        />
      </Card>
      <Appearance />
    </>
  );
}

function Appearance() {
  const status = useStatus();
  const update = useUpdateSettings();
  return (
    <Card>
      <CardHeader title="Appearance" />
      <Segmented<Theme>
        label="Theme"
        value={status.data?.settings.theme ?? "system"}
        onChange={(theme) => update.mutate({ theme })}
        options={[
          { value: "system", label: "Match Windows" },
          { value: "light", label: "Light" },
          { value: "dark", label: "Dark" },
        ]}
      />
    </Card>
  );
}

function Charges() {
  const status = useStatus();
  const update = useUpdateSettings();
  const broker = status.data?.settings.broker;
  const [draft, setDraft] = useState(broker);
  useEffect(() => setDraft(broker), [broker]);
  if (!broker || !draft) return <Skeleton className="h-64" />;
  const dirty = JSON.stringify(draft) !== JSON.stringify(broker);
  const fields: { key: keyof typeof draft; label: string; hint: string }[] = [
    { key: "delivery_per_order", label: "Delivery brokerage per order", hint: "Many discount brokers charge ₹0 or ₹20." },
    { key: "intraday_per_order", label: "Intraday brokerage per order", hint: "Often ₹20 or 0.03%, whichever is lower." },
    { key: "fno_per_order", label: "F&O brokerage per order", hint: "Often a flat ₹20." },
    { key: "dp_charge_per_sell", label: "DP charge per delivery sell", hint: "Charged by your depository participant each day you sell a stock." },
  ];
  return (
    <Card>
      <CardHeader
        title="Your broker's charges"
        subtitle="Statutory charges (STT, exchange, SEBI, stamp duty, GST) are applied automatically from NSE's dated rules. Add what your broker charges on top; 18% GST is added to these."
      />
      <div className="grid gap-5 sm:grid-cols-2">
        {fields.map((f) => (
          <Field key={f.key} label={f.label} htmlFor={`b-${f.key}`} hint={f.hint}>
            <Input id={`b-${f.key}`} prefix="₹" inputMode="decimal" value={draft[f.key]} onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value.replace(/[^\d.]/g, "") })} />
          </Field>
        ))}
      </div>
      <p className="mt-4 text-[12.5px] text-ink-3">Check your broker's charges page for current rates. Example: ₹20 brokerage + 18% GST = {inr(23.6)} per order.</p>
      <SaveBar dirty={dirty} saving={update.isPending} saved={update.isSuccess} error={update.error} onSave={() => update.mutate({ broker: draft })} />
    </Card>
  );
}

function DataSection() {
  const status = useStatus();
  const setFolder = useSetDataFolder();
  const build = useBuildIndex();
  const data = status.data;
  const [path, setPath] = useState(data?.settings.data_folder ?? "");
  useEffect(() => {
    if (data?.settings.data_folder) setPath(data.settings.data_folder);
  }, [data?.settings.data_folder]);
  if (!data) return <Skeleton className="h-64" />;
  const job = data.index.job;
  return (
    <>
      <Card>
        <CardHeader title="Market data" subtitle="QuantOS reads daily NSE prices from a QuantOS data folder and builds a fast local index from it. Your data never leaves this computer." />
        {data.index.ready ? (
          <div className="grid grid-cols-2 gap-5 sm:grid-cols-4">
            <div>
              <div className="text-[12.5px] text-ink-3">Latest session</div>
              <div className="num mt-1 font-semibold text-ink">{date(data.index.latest_session)}</div>
              <AsOf iso={data.index.latest_session} className="mt-1" />
            </div>
            <div>
              <div className="text-[12.5px] text-ink-3">Stocks and ETFs</div>
              <div className="num mt-1 font-semibold text-ink">{int(data.index.symbols ?? 0)}</div>
            </div>
            <div>
              <div className="text-[12.5px] text-ink-3">Data breaks handled</div>
              <div className="num mt-1 font-semibold text-ink">{int(data.index.flags ?? 0)}</div>
            </div>
            <div>
              <div className="text-[12.5px] text-ink-3">Index built</div>
              <div className="num mt-1 font-semibold text-ink">{dateTime(data.index.built_at)}</div>
            </div>
          </div>
        ) : (
          <Callout tone="warn" title="No market data connected">
            Choose your QuantOS data folder below and build the index.
          </Callout>
        )}
        {data.index.ready && data.index.matches_folder === false && (
          <Callout
            tone="warn"
            className="mt-5"
            title="This index was built from a different folder"
            action={
              <Button size="sm" onClick={() => build.mutate()} loading={job.state === "RUNNING"} disabled={!data.data_folder.valid}>
                Rebuild from current folder
              </Button>
            }
          >
            The screens show data from {data.index.data_folder ?? "another folder"}. Choose your folder below and rebuild to use it.
          </Callout>
        )}
        {data.index.stale && (
          <Callout
            tone="warn"
            className="mt-5"
            title="New market data is available"
            action={
              <Button size="sm" onClick={() => build.mutate()} loading={job.state === "RUNNING"}>
                Update index
              </Button>
            }
          >
            The data folder has changed since the index was built.
          </Callout>
        )}
      </Card>
      <Card>
        <CardHeader title="Data folder" />
        <Field label="Folder path" htmlFor="d-path" hint="The folder that contains evidence\market-cache.">
          <Input id="d-path" value={path} onChange={(e) => setPath(e.target.value)} spellCheck={false} className="font-mono text-[13px]" />
        </Field>
        {data.data_folder.candidates.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {data.data_folder.candidates.map((c) => (
              <button key={c.path} type="button" onClick={() => setPath(c.path)} className="rounded-full border border-line bg-surface-2 px-3 py-1 font-mono text-[12px] text-ink-2 hover:border-line-strong">
                {c.path} · {int(c.datasets)} datasets
              </button>
            ))}
          </div>
        )}
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Button
            icon={<RefreshCw className="size-4" aria-hidden />}
            loading={setFolder.isPending || build.isPending || job.state === "RUNNING"}
            disabled={!path}
            onClick={() => setFolder.mutate(path, { onSuccess: () => build.mutate() })}
          >
            {job.state === "RUNNING" ? "Building index" : data.index.ready ? "Rebuild index" : "Connect and build"}
          </Button>
          {(setFolder.isError || build.isError) && <span className="text-[13px] text-down">{errorMessage(setFolder.error ?? build.error)}</span>}
        </div>
        {job.state === "RUNNING" && (
          <div className="mt-5 space-y-2">
            <ProgressBar value={job.progress} label="Building market index" />
            <div className="flex justify-between text-[12.5px] text-ink-3">
              <span>{job.message}</span>
              <span className="num">{Math.round(job.progress * 100)}%</span>
            </div>
          </div>
        )}
        {job.state === "ERROR" && (
          <Callout tone="danger" className="mt-5" title="The index could not be built">
            {job.error}
          </Callout>
        )}
        {job.state === "DONE" && <p className="mt-4 text-[13px] text-up">{job.message}</p>}
      </Card>
    </>
  );
}

function Accounts() {
  const secrets = useSecrets();
  if (secrets.isPending) return <Skeleton className="h-64" />;
  const data = secrets.data;
  const groups = [...new Set((data?.secrets ?? []).map((s) => s.group))];
  return (
    <>
      {!data?.available && (
        <Callout tone="warn" title="Windows Credential Manager is not available">
          QuantOS can still read keys from a .env file, but cannot store them securely here.
        </Callout>
      )}
      <Callout tone="info">
        Keys are stored in Windows Credential Manager, encrypted for your Windows account. QuantOS never shows a saved key again and never writes it to a file.
      </Callout>
      {groups.map((group) => (
        <Card key={group}>
          <CardHeader title={group} />
          <div className="divide-y divide-line">
            {(data?.secrets ?? [])
              .filter((s) => s.group === group)
              .map((secret) => (
                <SecretRow key={secret.name} secret={secret} available={Boolean(data?.available)} />
              ))}
          </div>
        </Card>
      ))}
    </>
  );
}

function SecretRow({ secret, available }: { secret: Secret; available: boolean }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const mutation = useSecretMutation();
  return (
    <div className="py-4 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-ink">{secret.label}</span>
            {secret.stored ? (
              <Badge tone="up">Stored securely</Badge>
            ) : secret.active ? (
              <Badge tone="brand">From .env</Badge>
            ) : (
              <Badge>Not set</Badge>
            )}
          </div>
          <div className="mt-0.5 text-[12.5px] text-ink-3">{secret.help}</div>
        </div>
        <div className="flex gap-2">
          {secret.stored && (
            <Button variant="ghost" size="sm" loading={mutation.isPending && !editing} onClick={() => mutation.mutate({ name: secret.name, value: null })}>
              Remove
            </Button>
          )}
          <Button variant="secondary" size="sm" disabled={!available} onClick={() => setEditing(!editing)}>
            {secret.stored ? "Replace" : "Add"}
          </Button>
        </div>
      </div>
      {editing && (
        <form
          className="mt-3 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate(
              { name: secret.name, value },
              {
                onSuccess: () => {
                  setEditing(false);
                  setValue("");
                },
              },
            );
          }}
        >
          <Input type="password" autoComplete="off" value={value} onChange={(e) => setValue(e.target.value)} placeholder={`Paste your ${secret.label}`} aria-label={secret.label} autoFocus />
          <Button type="submit" disabled={!value.trim()} loading={mutation.isPending}>
            Save
          </Button>
        </form>
      )}
      {mutation.isError && <p className="mt-2 text-[13px] text-down">{errorMessage(mutation.error)}</p>}
    </div>
  );
}

function AiAssistants() {
  const tools = useAiTools();
  const [copied, setCopied] = useState<string | null>(null);
  const copy = (text: string) => {
    void navigator.clipboard?.writeText(text);
    setCopied(text);
    setTimeout(() => setCopied(null), 1500);
  };
  return (
    <Card>
      <CardHeader
        title="AI assistants"
        subtitle="Command-line AI assistants installed on this computer. Each one signs in with your own account; QuantOS never installs them or signs in for you."
      />
      {tools.isPending ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="divide-y divide-line">
          {(tools.data ?? []).map((t) => (
            <div key={t.command} className="flex flex-wrap items-center justify-between gap-3 py-4 first:pt-0 last:pb-0">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-ink">{t.name}</span>
                  <span className="text-[12.5px] text-ink-3">by {t.maker}</span>
                  {t.installed ? <Badge tone="up">Installed</Badge> : <Badge>Not installed</Badge>}
                </div>
                <div className="mt-0.5 text-[12.5px] text-ink-3">{t.installed ? t.version ?? "Version unknown" : "Needs Node.js. Install from a terminal:"}</div>
              </div>
              <CommandChip text={t.installed ? t.sign_in : t.install} copied={copied} onCopy={copy} label={t.installed ? "Sign in" : "Install"} />
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function CommandChip({ text, copied, onCopy, label }: { text: string; copied: string | null; onCopy: (text: string) => void; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[12px] text-ink-3">{label}</span>
      <code className="rounded-lg border border-line bg-surface-2 px-2.5 py-1.5 font-mono text-[12px] text-ink">{text}</code>
      <button type="button" onClick={() => onCopy(text)} aria-label={`Copy ${text}`} className="rounded-lg p-1.5 text-ink-3 hover:bg-surface-2 hover:text-ink">
        {copied === text ? <span className="text-[12px] text-up">Copied</span> : <Copy className="size-4" aria-hidden />}
      </button>
    </div>
  );
}

function About() {
  const status = useStatus();
  const licences: [string, string][] = [
    ["React, React Router, TanStack Query and Virtual, cmdk, Radix UI, clsx, Tailwind CSS, Vite", "MIT"],
    ["TradingView Lightweight Charts™ — Copyright © TradingView, Inc. (tradingview.com)", "Apache-2.0"],
    ["Lucide icons", "ISC"],
    ["Inter and JetBrains Mono typefaces", "SIL Open Font License 1.1"],
    ["FastAPI, Uvicorn, Pydantic, NumPy, SciPy", "MIT / BSD"],
  ];
  return (
    <>
      <Card>
        <CardHeader title="QuantOS" subtitle={`Version ${status.data?.version ?? ""}`} />
        <p className="text-sm leading-relaxed text-ink-2">
          QuantOS is a research and practice tool for testing trading and investing ideas on real NSE data with exact costs. It is not investment advice,
          it is not registered with SEBI as an investment adviser or research analyst, and it does not place orders with any broker. Past results,
          including backtests and paper trading, do not guarantee future returns.
        </p>
        <a href="/classic" className="mt-4 inline-flex items-center gap-1.5 text-[13px] font-medium text-brand hover:underline">
          Open the classic research console <ExternalLink className="size-3.5" aria-hidden />
        </a>
      </Card>
      <Card>
        <CardHeader title="Open-source software" subtitle="QuantOS is built with these projects." />
        <ul className="divide-y divide-line text-sm">
          {licences.map(([name, licence]) => (
            <li key={name} className="flex items-start justify-between gap-4 py-2.5">
              <span className="text-ink-2">{name}</span>
              <Badge>{licence}</Badge>
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}

export type { ReactNode };
