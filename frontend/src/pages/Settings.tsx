import {
  AlertCircle,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Database,
  ExternalLink,
  Eye,
  EyeOff,
  Info,
  KeyRound,
  Landmark,
  RefreshCw,
  Sparkles,
  UserRound,
  Zap,
} from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import { NavLink, useParams } from "react-router";
import { AsOf } from "../components/common";
import { AgentCliBridge } from "../components/AgentCliBridge";
import { DataFolderPicker } from "../components/DataFolderPicker";
import { Badge, Button, Callout, Card, CardHeader, cx, Field, Input, PageHeader, ProgressBar, Segmented, Skeleton } from "../components/ui";
import { errorMessage } from "../lib/api";
import { date, dateTime, inr, int } from "../lib/format";
import {
  useAiModels,
  useBuildIndex,
  useSecretMutation,
  useSecrets,
  useSetDataFolder,
  useStatus,
  useTestCredential,
  useUpdateSettings,
} from "../lib/queries";
import type { Style, Theme } from "../lib/types";

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
            QuantOS is searching for it. Pick the folder below and build the index.
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
        <DataFolderPicker path={path} onPath={setPath} />
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
  const testMutation = useTestCredential();
  const mutation = useSecretMutation();
  const [testResults, setTestResults] = useState<Record<string, { testing: boolean; valid?: boolean; message?: string }>>({});
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [showValues, setShowValues] = useState<Record<string, boolean>>({});
  const [expandedBroker, setExpandedBroker] = useState<string | null>(null);

  if (secrets.isPending) return <Skeleton className="h-64" />;
  const data = secrets.data;
  const allSecrets = data?.secrets ?? [];

  const getSecret = (name: string) => allSecrets.find((s) => s.name === name);

  const handleTest = (provider: string, creds: Record<string, string>) => {
    setTestResults((prev) => ({ ...prev, [provider]: { testing: true } }));
    testMutation.mutate(
      { provider, credentials: creds },
      {
        onSuccess: (res) => {
          setTestResults((prev) => ({ ...prev, [provider]: { testing: false, valid: res.valid, message: res.message } }));
        },
        onError: (err) => {
          setTestResults((prev) => ({ ...prev, [provider]: { testing: false, valid: false, message: errorMessage(err) } }));
        },
      }
    );
  };

  const handleSave = (name: string, value: string) => {
    if (!value.trim()) return;
    mutation.mutate(
      { name, value: value.trim() },
      {
        onSuccess: () => {
          setDrafts((prev) => ({ ...prev, [name]: "" }));
        },
      }
    );
  };

  const handleRemove = (name: string) => {
    mutation.mutate({ name, value: null });
  };

  const upstoxToken = getSecret("UPSTOX_ACCESS_TOKEN");
  const upstoxKey = getSecret("UPSTOX_API_KEY");
  const upstoxSecret = getSecret("UPSTOX_API_SECRET");

  const aiProviders = [
    {
      id: "anthropic",
      secretName: "ANTHROPIC_API_KEY",
      name: "Anthropic Claude",
      maker: "Anthropic",
      blurb: "Claude models: Opus, Sonnet and Haiku",
      placeholder: "sk-ant-api03-...",
      link: "https://console.anthropic.com/settings/keys",
    },
    {
      id: "openai",
      secretName: "OPENAI_API_KEY",
      name: "OpenAI",
      maker: "OpenAI",
      blurb: "GPT models from OpenAI",
      placeholder: "sk-proj-...",
      link: "https://platform.openai.com/api-keys",
    },
    {
      id: "gemini",
      secretName: "GEMINI_API_KEY",
      name: "Google Gemini",
      maker: "Google AI",
      blurb: "Gemini models: Pro and Flash",
      placeholder: "AIzaSy...",
      link: "https://aistudio.google.com/app/apikey",
    },
    {
      id: "openrouter",
      secretName: "OPENROUTER_API_KEY",
      name: "OpenRouter",
      maker: "OpenRouter",
      blurb: "One key for hundreds of models",
      placeholder: "sk-or-v1-...",
      link: "https://openrouter.ai/keys",
    },
    {
      id: "groq",
      secretName: "GROQ_API_KEY",
      name: "Groq Cloud",
      maker: "Groq",
      blurb: "Fast open models such as Llama",
      placeholder: "gsk_...",
      link: "https://console.groq.com/keys",
    },
    {
      id: "deepseek",
      secretName: "DEEPSEEK_API_KEY",
      name: "DeepSeek",
      maker: "DeepSeek",
      blurb: "DeepSeek chat and reasoning models",
      placeholder: "sk-...",
      link: "https://platform.deepseek.com/api_keys",
    },
    {
      id: "mistral",
      secretName: "MISTRAL_API_KEY",
      name: "Mistral AI",
      maker: "Mistral",
      blurb: "Mistral models",
      placeholder: "...",
      link: "https://console.mistral.ai/api-keys/",
    },
  ];

  return (
    <>
      {!data?.available && (
        <Callout tone="warn" title="Windows Credential Manager is not available">
          QuantOS can still read keys from your root .env file, but cannot store them encrypted in Windows Credential Manager.
        </Callout>
      )}
      <Callout tone="info">
        Keys and tokens are stored encrypted in Windows Credential Manager for your Windows account. They are never written to a file, never leave this computer, and are sent only to the provider they belong to.
      </Callout>

      {/* 1. Upstox V3 Highlight Card */}
      <Card className="border-brand/40 bg-gradient-to-b from-brand/5 to-transparent">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-brand/10 text-brand">
              <Zap className="size-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-semibold text-ink">Upstox V3</span>
                <Badge tone="brand">Default Market Data Provider</Badge>
                {upstoxToken?.stored ? (
                  <Badge tone="up">Stored Securely</Badge>
                ) : upstoxToken?.active ? (
                  <Badge tone="brand">From .env</Badge>
                ) : (
                  <Badge>No Token</Badge>
                )}
              </div>
              <div className="text-[12.5px] text-ink-3">Daily market feeds, real-time quotes, and historical 1m/daily bars.</div>
            </div>
          </div>
          <a
            href="https://service.upstox.com/developer/apps"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-[12px] font-medium text-brand hover:underline"
          >
            Upstox Developer Portal <ExternalLink className="size-3" />
          </a>
        </div>

        <div className="mt-4 space-y-4">
          <div>
            <div className="mb-1 flex items-center justify-between text-[13px] font-medium text-ink">
              <span>Upstox Access Token</span>
              <span className="text-[11.5px] text-ink-3">Expires daily around 3:30 AM IST</span>
            </div>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Input
                  type={showValues["upstox_token"] ? "text" : "password"}
                  placeholder={upstoxToken?.stored || upstoxToken?.active ? "•••••••••••••••••••••••• (Active)" : "Paste Upstox access token here"}
                  value={drafts["UPSTOX_ACCESS_TOKEN"] ?? ""}
                  onChange={(e) => setDrafts((prev) => ({ ...prev, UPSTOX_ACCESS_TOKEN: e.target.value }))}
                  className="pr-10 font-mono text-[12.5px]"
                />
                <button
                  type="button"
                  onClick={() => setShowValues((prev) => ({ ...prev, upstox_token: !prev.upstox_token }))}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-3 hover:text-ink"
                >
                  {showValues["upstox_token"] ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
              <Button
                variant="secondary"
                disabled={!(drafts["UPSTOX_ACCESS_TOKEN"] || upstoxToken?.active || upstoxToken?.stored)}
                loading={testResults["upstox"]?.testing}
                onClick={() => handleTest("upstox", { UPSTOX_ACCESS_TOKEN: drafts["UPSTOX_ACCESS_TOKEN"] || "" })}
              >
                Test Connection
              </Button>
              <Button
                disabled={!(drafts["UPSTOX_ACCESS_TOKEN"] ?? "").trim()}
                loading={mutation.isPending}
                onClick={() => handleSave("UPSTOX_ACCESS_TOKEN", drafts["UPSTOX_ACCESS_TOKEN"] ?? "")}
              >
                Save
              </Button>
              {upstoxToken?.stored && (
                <Button variant="ghost" size="sm" onClick={() => handleRemove("UPSTOX_ACCESS_TOKEN")}>
                  Remove
                </Button>
              )}
            </div>
            {testResults["upstox"] && !testResults["upstox"].testing && (
              <div
                className={cx(
                  "mt-2 flex items-center gap-2 rounded-lg px-3 py-1.5 text-[12.5px]",
                  testResults["upstox"].valid ? "bg-up/10 text-up" : "bg-down/10 text-down"
                )}
              >
                {testResults["upstox"].valid ? <CheckCircle2 className="size-4 shrink-0" /> : <AlertCircle className="size-4 shrink-0" />}
                <span>{testResults["upstox"].message}</span>
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 gap-3 pt-2 md:grid-cols-2">
            <div>
              <label className="mb-1 block text-[12px] font-medium text-ink-2">API Key (Optional)</label>
              <div className="flex gap-2">
                <Input
                  type="password"
                  placeholder={upstoxKey?.stored || upstoxKey?.active ? "••••••••" : "Paste API Key"}
                  value={drafts["UPSTOX_API_KEY"] ?? ""}
                  onChange={(e) => setDrafts((prev) => ({ ...prev, UPSTOX_API_KEY: e.target.value }))}
                  className="font-mono text-[12px]"
                />
                <Button size="sm" disabled={!(drafts["UPSTOX_API_KEY"] ?? "").trim()} onClick={() => handleSave("UPSTOX_API_KEY", drafts["UPSTOX_API_KEY"] ?? "")}>
                  Save
                </Button>
              </div>
            </div>
            <div>
              <label className="mb-1 block text-[12px] font-medium text-ink-2">API Secret (Optional)</label>
              <div className="flex gap-2">
                <Input
                  type="password"
                  placeholder={upstoxSecret?.stored || upstoxSecret?.active ? "••••••••" : "Paste API Secret"}
                  value={drafts["UPSTOX_API_SECRET"] ?? ""}
                  onChange={(e) => setDrafts((prev) => ({ ...prev, UPSTOX_API_SECRET: e.target.value }))}
                  className="font-mono text-[12px]"
                />
                <Button size="sm" disabled={!(drafts["UPSTOX_API_SECRET"] ?? "").trim()} onClick={() => handleSave("UPSTOX_API_SECRET", drafts["UPSTOX_API_SECRET"] ?? "")}>
                  Save
                </Button>
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* 2. Indian Broker Integrations (Zerodha, Angel One, Dhan, Fyers) */}
      <Card>
        <CardHeader
          title="Indian Broker Integrations"
          subtitle="One-click paste and test for Zerodha Kite, Angel One SmartAPI, Dhan, and Fyers."
        />
        <div className="divide-y divide-line">
          {/* Zerodha Kite */}
          <div className="py-3">
            <button
              type="button"
              onClick={() => setExpandedBroker(expandedBroker === "kite" ? null : "kite")}
              className="flex w-full items-center justify-between text-left text-sm font-medium text-ink hover:text-brand"
            >
              <div className="flex items-center gap-2">
                <span>Zerodha Kite Connect</span>
                {getSecret("KITE_ACCESS_TOKEN")?.stored || getSecret("KITE_ACCESS_TOKEN")?.active ? (
                  <Badge tone="up">Active</Badge>
                ) : (
                  <Badge>Not set</Badge>
                )}
              </div>
              {expandedBroker === "kite" ? <ChevronUp className="size-4 text-ink-3" /> : <ChevronDown className="size-4 text-ink-3" />}
            </button>
            {expandedBroker === "kite" && (
              <div className="mt-3 space-y-3 pl-2">
                <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                  <Input
                    placeholder="KITE_API_KEY"
                    value={drafts["KITE_API_KEY"] ?? ""}
                    onChange={(e) => setDrafts((prev) => ({ ...prev, KITE_API_KEY: e.target.value }))}
                    className="font-mono text-[12px]"
                  />
                  <Input
                    type="password"
                    placeholder="KITE_ACCESS_TOKEN"
                    value={drafts["KITE_ACCESS_TOKEN"] ?? ""}
                    onChange={(e) => setDrafts((prev) => ({ ...prev, KITE_ACCESS_TOKEN: e.target.value }))}
                    className="font-mono text-[12px]"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    loading={testResults["kite"]?.testing}
                    onClick={() => handleTest("kite", { KITE_API_KEY: drafts["KITE_API_KEY"] ?? "", KITE_ACCESS_TOKEN: drafts["KITE_ACCESS_TOKEN"] ?? "" })}
                  >
                    Test Connection
                  </Button>
                  <Button
                    size="sm"
                    disabled={!drafts["KITE_ACCESS_TOKEN"]?.trim()}
                    onClick={() => {
                      if (drafts["KITE_API_KEY"]) handleSave("KITE_API_KEY", drafts["KITE_API_KEY"]);
                      if (drafts["KITE_ACCESS_TOKEN"]) handleSave("KITE_ACCESS_TOKEN", drafts["KITE_ACCESS_TOKEN"]);
                    }}
                  >
                    Save Keys
                  </Button>
                </div>
                {testResults["kite"] && !testResults["kite"].testing && (
                  <div className={cx("mt-2 rounded-lg px-3 py-1.5 text-[12px]", testResults["kite"].valid ? "bg-up/10 text-up" : "bg-down/10 text-down")}>
                    {testResults["kite"].message}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Angel One */}
          <div className="py-3">
            <button
              type="button"
              onClick={() => setExpandedBroker(expandedBroker === "angel" ? null : "angel")}
              className="flex w-full items-center justify-between text-left text-sm font-medium text-ink hover:text-brand"
            >
              <div className="flex items-center gap-2">
                <span>Angel One SmartAPI</span>
                {getSecret("ANGEL_API_KEY")?.stored || getSecret("ANGEL_API_KEY")?.active ? (
                  <Badge tone="up">Active</Badge>
                ) : (
                  <Badge>Not set</Badge>
                )}
              </div>
              {expandedBroker === "angel" ? <ChevronUp className="size-4 text-ink-3" /> : <ChevronDown className="size-4 text-ink-3" />}
            </button>
            {expandedBroker === "angel" && (
              <div className="mt-3 space-y-3 pl-2">
                <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                  <Input placeholder="ANGEL_API_KEY" value={drafts["ANGEL_API_KEY"] ?? ""} onChange={(e) => setDrafts((prev) => ({ ...prev, ANGEL_API_KEY: e.target.value }))} className="font-mono text-[12px]" />
                  <Input placeholder="ANGEL_CLIENT_CODE" value={drafts["ANGEL_CLIENT_CODE"] ?? ""} onChange={(e) => setDrafts((prev) => ({ ...prev, ANGEL_CLIENT_CODE: e.target.value }))} className="font-mono text-[12px]" />
                  <Input type="password" placeholder="ANGEL_PIN" value={drafts["ANGEL_PIN"] ?? ""} onChange={(e) => setDrafts((prev) => ({ ...prev, ANGEL_PIN: e.target.value }))} className="font-mono text-[12px]" />
                  <Input type="password" placeholder="ANGEL_TOTP_KEY (2FA Secret)" value={drafts["ANGEL_TOTP_KEY"] ?? ""} onChange={(e) => setDrafts((prev) => ({ ...prev, ANGEL_TOTP_KEY: e.target.value }))} className="font-mono text-[12px]" />
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    onClick={() => {
                      if (drafts["ANGEL_API_KEY"]) handleSave("ANGEL_API_KEY", drafts["ANGEL_API_KEY"]);
                      if (drafts["ANGEL_CLIENT_CODE"]) handleSave("ANGEL_CLIENT_CODE", drafts["ANGEL_CLIENT_CODE"]);
                      if (drafts["ANGEL_PIN"]) handleSave("ANGEL_PIN", drafts["ANGEL_PIN"]);
                      if (drafts["ANGEL_TOTP_KEY"]) handleSave("ANGEL_TOTP_KEY", drafts["ANGEL_TOTP_KEY"]);
                    }}
                  >
                    Save Angel Keys
                  </Button>
                </div>
              </div>
            )}
          </div>

          {/* Dhan */}
          <div className="py-3">
            <button
              type="button"
              onClick={() => setExpandedBroker(expandedBroker === "dhan" ? null : "dhan")}
              className="flex w-full items-center justify-between text-left text-sm font-medium text-ink hover:text-brand"
            >
              <div className="flex items-center gap-2">
                <span>Dhan API</span>
                {getSecret("DHAN_ACCESS_TOKEN")?.stored || getSecret("DHAN_ACCESS_TOKEN")?.active ? (
                  <Badge tone="up">Active</Badge>
                ) : (
                  <Badge>Not set</Badge>
                )}
              </div>
              {expandedBroker === "dhan" ? <ChevronUp className="size-4 text-ink-3" /> : <ChevronDown className="size-4 text-ink-3" />}
            </button>
            {expandedBroker === "dhan" && (
              <div className="mt-3 space-y-3 pl-2">
                <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                  <Input placeholder="DHAN_CLIENT_ID" value={drafts["DHAN_CLIENT_ID"] ?? ""} onChange={(e) => setDrafts((prev) => ({ ...prev, DHAN_CLIENT_ID: e.target.value }))} className="font-mono text-[12px]" />
                  <Input type="password" placeholder="DHAN_ACCESS_TOKEN" value={drafts["DHAN_ACCESS_TOKEN"] ?? ""} onChange={(e) => setDrafts((prev) => ({ ...prev, DHAN_ACCESS_TOKEN: e.target.value }))} className="font-mono text-[12px]" />
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    loading={testResults["dhan"]?.testing}
                    onClick={() => handleTest("dhan", { DHAN_CLIENT_ID: drafts["DHAN_CLIENT_ID"] ?? "", DHAN_ACCESS_TOKEN: drafts["DHAN_ACCESS_TOKEN"] ?? "" })}
                  >
                    Test Connection
                  </Button>
                  <Button
                    size="sm"
                    disabled={!drafts["DHAN_ACCESS_TOKEN"]?.trim()}
                    onClick={() => {
                      if (drafts["DHAN_CLIENT_ID"]) handleSave("DHAN_CLIENT_ID", drafts["DHAN_CLIENT_ID"]);
                      if (drafts["DHAN_ACCESS_TOKEN"]) handleSave("DHAN_ACCESS_TOKEN", drafts["DHAN_ACCESS_TOKEN"]);
                    }}
                  >
                    Save Dhan Keys
                  </Button>
                </div>
                {testResults["dhan"] && !testResults["dhan"].testing && (
                  <div className={cx("mt-2 rounded-lg px-3 py-1.5 text-[12px]", testResults["dhan"].valid ? "bg-up/10 text-up" : "bg-down/10 text-down")}>
                    {testResults["dhan"].message}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Fyers */}
          <div className="py-3">
            <button
              type="button"
              onClick={() => setExpandedBroker(expandedBroker === "fyers" ? null : "fyers")}
              className="flex w-full items-center justify-between text-left text-sm font-medium text-ink hover:text-brand"
            >
              <div className="flex items-center gap-2">
                <span>Fyers API v3</span>
                {getSecret("FYERS_ACCESS_TOKEN")?.stored || getSecret("FYERS_ACCESS_TOKEN")?.active ? (
                  <Badge tone="up">Active</Badge>
                ) : (
                  <Badge>Not set</Badge>
                )}
              </div>
              {expandedBroker === "fyers" ? <ChevronUp className="size-4 text-ink-3" /> : <ChevronDown className="size-4 text-ink-3" />}
            </button>
            {expandedBroker === "fyers" && (
              <div className="mt-3 space-y-3 pl-2">
                <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                  <Input placeholder="FYERS_APP_ID" value={drafts["FYERS_APP_ID"] ?? ""} onChange={(e) => setDrafts((prev) => ({ ...prev, FYERS_APP_ID: e.target.value }))} className="font-mono text-[12px]" />
                  <Input type="password" placeholder="FYERS_ACCESS_TOKEN" value={drafts["FYERS_ACCESS_TOKEN"] ?? ""} onChange={(e) => setDrafts((prev) => ({ ...prev, FYERS_ACCESS_TOKEN: e.target.value }))} className="font-mono text-[12px]" />
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    loading={testResults["fyers"]?.testing}
                    onClick={() => handleTest("fyers", { FYERS_APP_ID: drafts["FYERS_APP_ID"] ?? "", FYERS_ACCESS_TOKEN: drafts["FYERS_ACCESS_TOKEN"] ?? "" })}
                  >
                    Test Connection
                  </Button>
                  <Button
                    size="sm"
                    disabled={!drafts["FYERS_ACCESS_TOKEN"]?.trim()}
                    onClick={() => {
                      if (drafts["FYERS_APP_ID"]) handleSave("FYERS_APP_ID", drafts["FYERS_APP_ID"]);
                      if (drafts["FYERS_ACCESS_TOKEN"]) handleSave("FYERS_ACCESS_TOKEN", drafts["FYERS_ACCESS_TOKEN"]);
                    }}
                  >
                    Save Fyers Keys
                  </Button>
                </div>
                {testResults["fyers"] && !testResults["fyers"].testing && (
                  <div className={cx("mt-2 rounded-lg px-3 py-1.5 text-[12px]", testResults["fyers"].valid ? "bg-up/10 text-up" : "bg-down/10 text-down")}>
                    {testResults["fyers"].message}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* 3. 1-Click AI Cloud Providers Grid */}
      <Card>
        <CardHeader
          title="AI Cloud Providers"
          subtitle="Paste a key and test it. QuantOS reads the newest models straight from each provider, so this list never goes out of date."
        />
        <div className="grid grid-cols-1 gap-4 pt-2 md:grid-cols-2">
          {aiProviders.map((prov) => {
            const secret = getSecret(prov.secretName);
            const isStored = secret?.stored;
            const isActive = secret?.active;
            const draft = drafts[prov.secretName] ?? "";
            const test = testResults[prov.id];
            const isVisible = showValues[prov.id];

            return (
              <div key={prov.id} className="flex flex-col justify-between rounded-xl border border-line bg-surface p-4 shadow-[var(--shadow-card)]">
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Sparkles className="size-4 text-brand" />
                      <span className="font-semibold text-ink">{prov.name}</span>
                    </div>
                    {isStored ? (
                      <Badge tone="up">Stored</Badge>
                    ) : isActive ? (
                      <Badge tone="brand">.env</Badge>
                    ) : (
                      <Badge>Not Set</Badge>
                    )}
                  </div>
                  <div className="mt-1 text-[11.5px] text-ink-3">{prov.blurb}</div>
                  <ProviderModels provider={prov.id} connected={Boolean(isStored || isActive)} refreshKey={test?.valid ? "ok" : "idle"} />

                  <div className="relative mt-3">
                    <Input
                      type={isVisible ? "text" : "password"}
                      placeholder={isStored || isActive ? "••••••••••••••••••••" : prov.placeholder}
                      value={draft}
                      onChange={(e) => setDrafts((prev) => ({ ...prev, [prov.secretName]: e.target.value }))}
                      className="pr-9 font-mono text-[12px]"
                    />
                    <button
                      type="button"
                      onClick={() => setShowValues((prev) => ({ ...prev, [prov.id]: !prev[prov.id] }))}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-3 hover:text-ink"
                    >
                      {isVisible ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
                    </button>
                  </div>

                  {test && !test.testing && (
                    <div className={cx("mt-2 rounded-lg px-2.5 py-1 text-[11.5px]", test.valid ? "bg-up/10 text-up" : "bg-down/10 text-down")}>
                      {test.message}
                    </div>
                  )}
                </div>

                <div className="mt-4 flex items-center justify-between gap-2 border-t border-line/60 pt-3">
                  <a href={prov.link} target="_blank" rel="noreferrer" className="text-[11.5px] text-ink-3 hover:text-brand hover:underline">
                    Get Key
                  </a>
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="secondary"
                      loading={test?.testing}
                      disabled={!(draft.trim() || isActive || isStored)}
                      onClick={() => handleTest(prov.id, { [prov.secretName]: draft.trim() })}
                    >
                      Test
                    </Button>
                    <Button
                      size="sm"
                      disabled={!draft.trim()}
                      loading={mutation.isPending}
                      onClick={() => handleSave(prov.secretName, draft)}
                    >
                      Save
                    </Button>
                    {isStored && (
                      <Button size="sm" variant="ghost" onClick={() => handleRemove(prov.secretName)}>
                        Remove
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </Card>
    </>
  );
}

function AiAssistants() {
  return <AgentCliBridge />;
}

/** The newest models this key can use, read live from the provider. */
function ProviderModels({ provider, connected, refreshKey }: { provider: string; connected: boolean; refreshKey: string }) {
  const models = useAiModels(provider, connected);
  const refetch = models.refetch;
  useEffect(() => {
    if (connected && refreshKey === "ok") void refetch();
  }, [connected, refreshKey, refetch]);
  if (!connected) return null;
  if (models.isPending) return <div className="mt-2 text-[11.5px] text-ink-3">Reading the newest models…</div>;
  if (models.isError) return <div className="mt-2 text-[11.5px] text-ink-3">{errorMessage(models.error)}</div>;
  if (models.data.newest.length === 0) return null;
  return (
    <div className="mt-2 text-[11.5px] text-ink-2">
      <span className="text-ink-3">Newest on your key: </span>
      {models.data.newest.map((m) => m.name).join(" · ")}
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
