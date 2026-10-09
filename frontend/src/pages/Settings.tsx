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
  ShieldCheck,
  Sparkles,
  UserRound,
  Wrench,
  Zap,
} from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import { NavLink, useParams } from "react-router";
import { AsOf } from "../components/common";
import { AgentCliBridge } from "../components/AgentCliBridge";
import { AiSource } from "../components/settings/AiSource";
import { APPS_ANCHOR } from "../lib/aiSource";
import { DataFolderPicker } from "../components/DataFolderPicker";
import { EnvImport } from "../components/EnvImport";
import { UpdateNowButton } from "../components/update/UpdateNowButton";
import { HardwareAcceleratorCard } from "../components/HardwareAcceleratorCard";
import { Badge, Button, Callout, Card, CardHeader, cx, Field, Input, PageHeader, ProgressBar, Segmented, Skeleton, Switch } from "../components/ui";
import { errorMessage } from "../lib/api";
import { MONEY_LIMITS, moneyProblems } from "../lib/rules";
import { date, dateTime, inr, int } from "../lib/format";
import {
  useAiModels,
  useChangelog,
  useCheckUpdate,
  usePaperUpdates,
  useBuildIndex,
  useSecretMutation,
  useSecrets,
  useSetDataFolder,
  useStatus,
  useTestCredential,
  useUpdate,
  useUpdateSettings,
} from "../lib/queries";
import type { ChangelogEntry, Style, Theme } from "../lib/types";

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
  const problems = moneyProblems(capital, risk, daily);
  const invalid = Object.keys(problems).length > 0;
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
        <CardHeader
          title="Mizan Shariah Compliance Mode"
          subtitle="Enable AAOIFI & TASIS Shariah compliance screening, thematic Halal baskets, dividend purification, and equity zakat engine."
        />
        <div className="flex items-center justify-between p-1">
          <div>
            <div className="text-[14px] font-medium text-ink">Shariah Compliant Wealth System</div>
            <div className="text-[12.5px] text-ink-3">
              Shows only Shariah-compliant stocks in your lists, labels every stock with its Shariah
              result, and opens the Mizan Shariah workspace. The same as the mode switch at the top.
            </div>
          </div>
          <Switch
            label="Shariah Mode"
            checked={Boolean(settings.shariah_mode)}
            onChange={(checked: boolean) => update.mutate({ shariah_mode: checked })}
          />
        </div>
      </Card>
      <Card>
        <CardHeader title="Money rules" subtitle="Used for position sizing and as the default capital in the Strategy Lab." />
        <div className="grid gap-5 sm:grid-cols-3">
          <Field label="Capital" htmlFor="st-cap" hint={`At least ${inr(MONEY_LIMITS.capitalMin, 0)}`} error={problems.capital}>
            <Input id="st-cap" prefix="₹" inputMode="numeric" value={capital} onChange={(e) => setCapital(e.target.value.replace(/[^\d.]/g, ""))} />
          </Field>
          <Field label="Risk per trade" htmlFor="st-risk" hint={`Up to ${MONEY_LIMITS.riskMax}%`} error={problems.risk}>
            <Input id="st-risk" suffix="%" inputMode="decimal" value={risk} onChange={(e) => setRisk(e.target.value.replace(/[^\d.]/g, ""))} />
          </Field>
          <Field label="Daily loss limit" htmlFor="st-daily" hint={`Up to ${MONEY_LIMITS.dailyMax}%`} error={problems.daily}>
            <Input id="st-daily" suffix="%" inputMode="decimal" value={daily} onChange={(e) => setDaily(e.target.value.replace(/[^\d.]/g, ""))} />
          </Field>
        </div>
        <SaveBar
          dirty={dirty && !invalid}
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
    { key: "dp_charge_per_sell", label: "DP charge per delivery sell", hint: "Brokers charge about ₹13 to ₹20 (plus GST) each time you sell shares from your demat account. Check your broker's charges page: at ₹0, costs are understated." },
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

/** Whether a reminder is sent when a book has orders waiting, and how to switch it on. */
function OrdersReminderLine() {
  const status = useStatus();
  const reminder = status.data?.orders_reminder;
  if (!reminder) return null;
  return (
    <div className="mt-4 border-t border-line pt-3 text-[13px] text-ink-3">
      <div className="font-medium text-ink-2">Orders reminder</div>
      {reminder.problem ? (
        <p role="alert" className="mt-1 text-down">{reminder.problem}</p>
      ) : reminder.enabled ? (
        <p className="mt-1">
          On. A short message goes to <strong className="text-ink-2">{reminder.host}</strong> once per book after each close with orders
          waiting. It carries a count and the book's name, never a stock, a quantity or a price.
          {reminder.last_error && <span className="text-down"> The last attempt failed: {reminder.last_error}</span>}
        </p>
      ) : (
        <p className="mt-1">
          Off. To be told when a book has orders to place, set <code>QUANTOS_ORDERS_WEBHOOK_URL</code> to a Slack, Discord or ntfy address
          (and <code>QUANTOS_ORDERS_WEBHOOK_FORMAT</code> to <code>slack</code>, <code>discord</code>, <code>ntfy</code> or <code>json</code>) and restart QuantOS. The address stays on this computer.
        </p>
      )}
    </div>
  );
}

function AutoUpdateCard({ enabled }: { enabled: boolean }) {
  const update = useUpdateSettings();
  const updates = usePaperUpdates();
  return (
    <Card>
      <CardHeader title="Paper books" subtitle="Paper books follow the market on real prices, so they need fresh prices each day." />
      <Switch
        checked={enabled}
        onChange={(value) => update.mutate({ auto_update_paper_books: value })}
        label="Update prices automatically after each market close"
      />
      <p className="mt-3 text-[13px] text-ink-3">{updates.data?.message ?? "QuantOS fetches a recent window of prices once a day, only while a paper book is running."}</p>
      {update.isError && <p className="mt-2 text-[13px] text-down">{errorMessage(update.error)}</p>}
      <OrdersReminderLine />
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
        ) : data.download.state === "RUNNING" || job.state === "RUNNING" ? (
          <Callout tone="info" title={data.download.state === "RUNNING" ? "Downloading market data" : "Preparing market data"}>
            {data.download.state === "RUNNING"
              ? "You can leave this page; the download keeps going in the background and connects itself when it finishes."
              : "Building the fast local index. This takes a minute or two."}
          </Callout>
        ) : (
          <Callout tone="warn" title="No market data yet">
            Download it below (about five minutes, free), or choose a folder that already holds QuantOS market data.
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
            disabled={!path || data.download.state === "RUNNING"}
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
      <AutoUpdateCard enabled={data.settings.auto_update_paper_books} />
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

  const handleTest = (provider: string, creds: Record<string, string>, resultKey?: string) => {
    const key = resultKey ?? provider;
    setTestResults((prev) => ({ ...prev, [key]: { testing: true } }));
    testMutation.mutate(
      { provider, credentials: creds },
      {
        onSuccess: (res) => {
          setTestResults((prev) => ({ ...prev, [key]: { testing: false, valid: res.valid, message: res.message } }));
        },
        onError: (err) => {
          setTestResults((prev) => ({ ...prev, [key]: { testing: false, valid: false, message: errorMessage(err) } }));
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
  const upstoxAnalytics = getSecret("UPSTOX_ANALYTICS_TOKEN");
  const upstoxKey = getSecret("UPSTOX_API_KEY");
  const upstoxSecret = getSecret("UPSTOX_API_SECRET");

  const aiProviders = [
    {
      id: "lightning",
      secretName: "LIGHTNING_API_KEY",
      name: "Lightning AI",
      maker: "Lightning AI",
      blurb: "Claude and open models hosted on Lightning AI Cloud",
      placeholder: "sk-lit-...",
      link: "https://lightning.ai",
    },
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
      <Callout tone="info" title="Everything on this page is optional">
        QuantOS works with the market data you downloaded and never places orders with any broker. Add a key only if you want the extra it unlocks, listed on each card.
      </Callout>
      <Callout tone="info">
        Keys and tokens are stored encrypted in Windows Credential Manager for your Windows account. They are never written to a file, never leave this computer, and are sent only to the provider they belong to.
      </Callout>

      <EnvImport />

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
                {upstoxAnalytics?.stored ? (
                  <Badge tone="up">Analytics Active (~1y)</Badge>
                ) : upstoxAnalytics?.active ? (
                  <Badge tone="brand">Analytics (.env)</Badge>
                ) : null}
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

          <div>
            <div className="mb-1 flex items-center justify-between text-[13px] font-medium text-ink">
              <span>Upstox Analytics Token (Long-Lived ~1 Year)</span>
              <span className="text-[11.5px] text-ink-3">Recommended: does not expire daily</span>
            </div>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Input
                  type={showValues["upstox_analytics"] ? "text" : "password"}
                  placeholder={upstoxAnalytics?.stored || upstoxAnalytics?.active ? "•••••••••••••••••••••••• (Active)" : "Paste Upstox analytics token here"}
                  value={drafts["UPSTOX_ANALYTICS_TOKEN"] ?? ""}
                  onChange={(e) => setDrafts((prev) => ({ ...prev, UPSTOX_ANALYTICS_TOKEN: e.target.value }))}
                  className="pr-10 font-mono text-[12.5px]"
                />
                <button
                  type="button"
                  onClick={() => setShowValues((prev) => ({ ...prev, upstox_analytics: !prev.upstox_analytics }))}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-3 hover:text-ink"
                >
                  {showValues["upstox_analytics"] ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
              <Button
                variant="secondary"
                disabled={!(drafts["UPSTOX_ANALYTICS_TOKEN"] || upstoxAnalytics?.active || upstoxAnalytics?.stored)}
                loading={testResults["upstox_analytics"]?.testing}
                onClick={() => handleTest("upstox", { UPSTOX_ANALYTICS_TOKEN: drafts["UPSTOX_ANALYTICS_TOKEN"] || "" }, "upstox_analytics")}
              >
                Test Connection
              </Button>
              <Button
                disabled={!(drafts["UPSTOX_ANALYTICS_TOKEN"] ?? "").trim()}
                loading={mutation.isPending}
                onClick={() => handleSave("UPSTOX_ANALYTICS_TOKEN", drafts["UPSTOX_ANALYTICS_TOKEN"] ?? "")}
              >
                Save
              </Button>
              {upstoxAnalytics?.stored && (
                <Button variant="ghost" size="sm" onClick={() => handleRemove("UPSTOX_ANALYTICS_TOKEN")}>
                  Remove
                </Button>
              )}
            </div>
            {testResults["upstox_analytics"] && !testResults["upstox_analytics"].testing && (
              <div
                className={cx(
                  "mt-2 flex items-center gap-2 rounded-lg px-3 py-1.5 text-[12.5px]",
                  testResults["upstox_analytics"].valid ? "bg-up/10 text-up" : "bg-down/10 text-down"
                )}
              >
                {testResults["upstox_analytics"].valid ? <CheckCircle2 className="size-4 shrink-0" /> : <AlertCircle className="size-4 shrink-0" />}
                <span>{testResults["upstox_analytics"].message}</span>
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
          subtitle="Optional, and not used by anything in QuantOS yet. You can save and test a Zerodha Kite, Angel One, Dhan or Fyers key here for future data connections. QuantOS does not place orders."
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
          subtitle="Optional. These keys power AI assistants across QuantOS. QuantOS reads the newest models straight from each provider, so this list never goes out of date."
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
  return (
    <div className="space-y-6">
      <HardwareAcceleratorCard />
      <AiSource />
      <div id={APPS_ANCHOR} tabIndex={-1} className="scroll-mt-4 outline-none">
        <AgentCliBridge />
      </div>
    </div>
  );
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

function UpdateLine() {
  const update = useUpdate();
  const check = useCheckUpdate();
  const info = update.data;
  let text = "Checking for updates…";
  if (info) {
    if (info.update_available && info.latest) text = `QuantOS ${info.latest} is available.`;
    else if (info.checked) text = "You have the latest version.";
    else text = "Could not check for updates right now.";
  }
  return (
    <div className="mb-4 flex flex-wrap items-center gap-3 text-sm text-ink-2">
      <span>{text}</span>
      {info?.update_available && info.url && (
        <a href={info.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-medium text-brand hover:underline">
          See what is new and download <ExternalLink className="size-3.5" aria-hidden />
        </a>
      )}
      <UpdateNowButton />
      <Button size="sm" variant="ghost" icon={<RefreshCw className="size-3.5" aria-hidden />} loading={check.isPending} onClick={() => check.mutate()}>
        Check now
      </Button>
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
        <CardHeader title="Mizan Quant OS" subtitle={`Version ${status.data?.version ?? ""}`} />
        <UpdateLine />
        <p className="text-sm leading-relaxed text-ink-2">
          Mizan Quant OS is an institutional-grade research, algorithmic backtesting, and Shariah wealth engineering platform for testing trading and investing ideas on real NSE data with exact statutory costs. It is not investment advice,
          it is not registered with SEBI as an investment adviser or research analyst, and it does not place live orders with any broker without explicit governed oversight. Past results,
          including backtests and paper trading, do not guarantee future returns.
        </p>
      </Card>
      <ChangelogCard />
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

function ChangelogCard() {
  const changelogQuery = useChangelog();
  const update = useUpdate();
  const info = update.data;

  const fallbackEntries: ChangelogEntry[] = [
    {
      version: "3.2.0",
      date: "2026-10-09",
      title: "Shariah results from company filings, fundamentals, several accounts, a clearer top bar and one-click updates",
      is_current: true,
      whats_new: [
        "Shariah results now come from each company's own filing wherever QuantOS holds one, with the filing behind every figure and a plain \"out of date\" label when the filing is old. You can read newer filings from inside the app",
        "Fundamentals: a new screen where you set the filters and sorting yourself and compare up to four companies side by side. Each Stock page shows the company's results from its own filings with the formula and the filing behind every figure, and your Portfolio has a Fundamentals tab. Nothing is ranked or called good or bad",
        "Several accounts in your Portfolio: see them together or one at a time, add, edit and remove accounts, and Add to portfolio now asks which account. Each purchase shows how long it has been held, as a fact, with no tax amounts",
        "A top bar that tells you where you are and what needs attention: the screen and its parent, a real search field, whether the market is open, how fresh prices are, whether live prices are on and when an update is waiting",
        "Update and restart: Settings, About can download the new version, check it against the fingerprint published with the release, install it and open QuantOS again. Windows may ask you to confirm",
        "AI apps: install and sign in to Claude Code, Codex and Gemini from one plain card, with no terminal. Choose in Settings which AI answers the Copilot, and every chat is kept on this computer so you can search and carry one on",
      ],
      fixes: [
        "A stock whose two Shariah standards disagree now reads the same result on its badge, its card and the screener tab",
        "The market chip says Market open, Market closed or a holiday when it knows the NSE holiday list, and says Market hours otherwise",
        "Add to portfolio on a stock page no longer files into the first account for people who keep several",
        "\"Coding agents\" is now \"AI apps\", and developer words no longer appear in anything you read",
      ],
      improvements: [
        "Company results for 412 NSE companies ship with the app, so Fundamentals and Shariah screens work on a brand-new laptop with no internet. They are out of date until you read newer filings, and say so",
        "Back and forward buttons sit in the new top bar",
      ],
      unchanged_protections: [
        "Keys stay strictly encrypted in local Windows Credential Manager and are never sent to external servers",
        "Zero unauthorized live-broker order execution — all autonomous decisions strictly sandboxed and verified",
        "Halal results come only from deterministic screening rules applied to a company's own figures, never from an AI model",
        "Company results are facts from filings, not advice, and old data is always labelled",
        "Decimal-exact financial accounting and statutory NSE transaction cost schedules preserved",
      ],
    },
    {
      version: "3.1.0",
      date: "2026-10-08",
      title: "Mizan Quant OS: Quant SLM Engine, Microsoft Qlib Multi-Factor Architecture & Factory-New Installer",
      is_current: false,
      whats_new: [
        "Mizan Quant OS brand unification: combined institutional quantitative trading, factor research, and Mizan Shariah wealth compliance in one unified operating system",
        "Quant SLM: local Small Language Model for ultra-fast, accurate market intelligence, combining deep multi-factor alpha signals, technical indicators, and embedding-gemma-2 / XRIV features",
        "Microsoft Qlib integration: high-performance quantitative alpha factor library, multi-factor models, and automated upstream synchronization pipeline",
        "Factory-new laptop installer: standalone, drive-isolated Inno Setup distribution (MizanQuantOS_v3.0.0_Setup.exe) with bundled runtime and zero C-drive leakage",
        "Upstox live market feeds: low-latency price feeds, quote streams, and portfolio synchronization",
      ],
      fixes: [
        "Enforced strict drive-isolated local execution with zero C: drive path leakage",
        "Corporate actions provider caching with automatic historical symbol alias mapping",
        "Fixed walk-forward validation matrix bounds and purged look-ahead data leakage",
      ],
      improvements: [
        "Institutional multi-factor backtesting performance and real-time risk governor checks",
        "Comprehensive packaging with cryptographic Software Bill of Materials (SBOM) and SHA-256 verification manifests",
      ],
      unchanged_protections: [
        "Keys stay strictly encrypted in local Windows Credential Manager and are never sent to external servers",
        "Zero unauthorized live-broker order execution — all autonomous decisions strictly sandboxed and verified",
        "Halal screening rules remain determined by deterministic algorithmic criteria (DJIM/AAOIFI), never unverified AI hallucination",
        "Decimal-exact financial accounting and statutory NSE transaction cost schedules preserved",
      ],
    },
    {
      version: "2.5.0",
      date: "2026-10-07",
      title: "Copilot Assistant, Independent Second Opinions, Your Own Agents & Live Prices",
      is_current: false,
        whats_new: [
            "Copilot: ask a question from any screen with the Copilot button at the top (or Ctrl+J). It works with no AI key, answering from QuantOS's own data, and takes open-ended questions once you add an AI key in Settings. It can suggest a screen to open and can never place an order",
            "Second opinions: have several AI models read the same facts about a stock, each on its own, and see where they agree, where they differ and why. Agreement between AI models is not evidence that a stock will do well",
            "Agents: create, edit, run and delete your own saved agents on the new Agents screen, with four ready-made ones that need no AI key",
            "Live prices from your Upstox key, read-only: every price says whether it is Live, Delayed, Last close or Not available",
            "News headlines for a stock, with a rough keyword tone that is clearly labelled as rough",
        ],
        fixes: [
            "A key pasted with a space or a line break is refused with a plain message instead of failing later",
            "The Copilot button and panel fit every window width, from a phone-sized window to a wide monitor",
            "Pop-up windows return you to where you were when they close, and form fields are read out with their hints",
        ],
        improvements: [
            "Home shows an End of day label on prices when the market is closed",
            "Danger buttons are easier to read in dark mode",
        ],
        unchanged_protections: [
            "Keys stay in Windows Credential Manager and are sent only to the provider they belong to",
            "QuantOS still never places orders with any broker, and neither can the Copilot",
            "Halal results come only from the QuantOS screener, never from an AI model",
            "Nothing in QuantOS has shown an edge that survives real trading costs, and AI opinions do not change that",
        ],
    },
    {
      version: "2.4.0",
      date: "2026-10-05",
      title: "Import All Your Keys From a .env File, Paper-Book Order Inbox & Health Checks",
      is_current: false,
      whats_new: [
        "Import all your keys at once: choose your .env or .env.local files in Settings, review what was found, and save them in one step",
        "Paper books say when their orders are out of date and offer a copy-ready order ticket",
        "Record what you did with each paper-book order, see what is waiting, and compare your fills",
        "Optional Slack, Discord or ntfy message when a paper book has orders to place; it never carries a stock, quantity or price",
        "Liveness and readiness checks, with an early warning before the NSE holiday list runs out",
      ],
      fixes: [
        "The live trading dashboard now runs inside the desktop app",
        "Honest log times and audit labels in paper-pilot sessions",
        "Fits phone-sized screens and passes colour-contrast checks; Mizan Shariah sample data is labelled honestly",
        "Desktop launch, single-instance lock and shortcut logo fixes",
      ],
      improvements: [
        "Mizan Shariah screens follow the QuantOS design system",
      ],
      unchanged_protections: [
        "Keys stay in Windows Credential Manager and are sent only to the provider they belong to",
        "QuantOS still never places orders with any broker",
        "Existing paper books, portfolios and evidence are kept when you update over an older install",
        "Decimal-exact accounting and statutory NSE cost schedules are unchanged",
      ],
    },
    {
      version: "2.3.0",
      date: "2026-10-05",
      title: "Unified Desktop Studio & Mizan Shariah Wealth Engine",
      is_current: false,
      whats_new: [
        "Unified desktop studio with instant 1-click mode switch between Institutional Quant and Mizan Shariah Wealth Engine",
        "Mizan Shariah screening engine with customizable screening rules (DJIM, AAOIFI)",
        "Automated purification calculation and charity zakat ledger for Islamic wealth compliance",
        "Download and cache official NSE symbol changes with historical alias merging (e.g. HEG → HEGAM)",
        "Integrated portfolio purifier and halal wealth intelligence tools",
      ],
      fixes: [
        "Setup onboarding wizard remembers current step across reloads",
        "Never overwrite saved corporate action authorities with empty results on network timeouts",
      ],
      improvements: [
        "Harmonized Mizan Shariah frontend with Apple-grade QuantOS design system",
        "High-contrast accessible theme toggles and responsive layout refinements",
      ],
      unchanged_protections: [
        "Zero live-broker order routing — all executions strictly paper/shadow simulated",
        "Decimal-exact financial accounting and statutory NSE transaction cost schedules preserved",
        "Full offline self-contained operation without external cloud dependencies or telemetry",
        "Immutable content-addressed evidence store remains write-protected",
      ],
    },
    {
      version: "2.2.0",
      date: "2026-10-04",
      title: "Automated Paper Books & Lightning AI Provider",
      is_current: false,
      whats_new: [
        "Paper books keep themselves up to date automatically after each NSE market close",
        "Native Lightning AI provider support for ultra-low latency model calls",
        "Upstox analytics token integration and Moonshot model architecture",
      ],
      fixes: [
        "Hardened corporate actions provider fallback on connectivity blips",
        "Persistent paper engine state synchronization across app restarts",
      ],
      improvements: [
        "Background auto-updater runs with zero CPU overhead and bounded sleep",
      ],
      unchanged_protections: [
        "Existing paper trading portfolios and historical ledgers preserved without loss",
        "Strict point-in-time bar history constraints maintained",
      ],
    },
    {
      version: "2.1.0",
      date: "2026-10-04",
      title: "In-App Update Checker, Native Paper Trading & AI Hub",
      is_current: false,
      whats_new: [
        "In-app update notifications when new releases are published on GitHub",
        "Quick 'Update market data' keeping full ten-year bar history",
        "Start and follow live paper trading books directly within the desktop UI",
        "Built-in market data downloader for factory-new laptops without pre-existing data",
        "Direct support for Google Gemini, DeepSeek, and Mistral API keys in AI Assistant",
        "Auto-discovery of local market data and browser-based sign-in for AI apps",
      ],
      fixes: [
        "Repaired statutory transaction cost display across order sizes",
        "Chat requests no longer force strict JSON mode and retry safely without refused temperature",
        "Stopped copying saved API keys into plaintext .env file",
      ],
      improvements: [
        "Sub-second market data search and symbol lookup across 3,000+ NSE tickers",
      ],
      unchanged_protections: [
        "Strict local loopback trust boundary — zero remote access and no external telemetry",
        "Purged and embargoed walk-forward validation prevents look-ahead leakage",
      ],
    },
    {
      version: "2.0.1",
      date: "2026-10-03",
      title: "Windows Shell Integration & Multi-Agent Bridge",
      is_current: false,
      whats_new: [
        "Fixed taskbar icon identity and tray integration on Windows x64",
        "Install and sign in to several AI apps with one click",
      ],
      fixes: [
        "Clean exit handling on Windows process shutdowns",
      ],
      improvements: [
        "Optimized asset preloading in WebView2 container",
      ],
      unchanged_protections: [
        "100% backward compatibility with QuantOS v1 evidence store and historical runs",
      ],
    },
    {
      version: "2.0.0",
      date: "2026-10-03",
      title: "QuantOS 2.0 Retail Platform & Native Window Runner",
      is_current: false,
      whats_new: [
        "Complete consumer-grade retail interface (QuantOS 2.0) with Strategy Lab and Market Index",
        "Native Windows desktop runner powered by WebView2 without black terminal popups",
        "Versioned operation API v2 with local trust boundary",
      ],
      fixes: [
        "Fixed journey script execution inside native desktop window container",
      ],
      improvements: [
        "Instant UI responsiveness and clean semantic navigation",
      ],
      unchanged_protections: [
        "Core risk governor, immutable content-addressed evidence store, and Decimal ledger invariants untouched",
      ],
    },
  ];

  const entries: ChangelogEntry[] = changelogQuery.data && changelogQuery.data.length > 0
    ? changelogQuery.data
    : fallbackEntries;

  const [expandedVersions, setExpandedVersions] = useState<Record<string, boolean>>({
    "2.5.0": true,
  });

  const toggleVersion = (ver: string) => {
    setExpandedVersions((prev) => ({
      ...prev,
      [ver]: !prev[ver],
    }));
  };

  return (
    <Card>
      <CardHeader
        title="Changelog & Release Notes"
        subtitle="Detailed record of what was updated, bug fixes, performance improvements, and protected safeguards across releases."
      />

      {info?.update_available && (
        <div className="mb-6 rounded-[var(--radius-control)] border border-brand/30 bg-brand-soft/20 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Sparkles className="size-4 text-brand" aria-hidden />
              <span className="font-semibold text-ink">New Release Available: QuantOS v{info.latest}</span>
              <Badge tone="brand">Update</Badge>
            </div>
            {info.url && (
              <a
                href={info.url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-[var(--radius-control)] bg-brand px-3 py-1.5 text-xs font-medium text-on-brand shadow-sm hover:bg-brand-strong"
              >
                Download update <ExternalLink className="size-3.5" aria-hidden />
              </a>
            )}
          </div>
          {info.notes && (
            <div className="mt-3 rounded border border-line bg-surface p-3 text-xs leading-relaxed text-ink-2 whitespace-pre-wrap font-mono">
              {info.notes}
            </div>
          )}
        </div>
      )}

      <div className="space-y-3">
        {entries.map((entry) => {
          const isExpanded = !!expandedVersions[entry.version];
          return (
            <div
              key={entry.version}
              className="overflow-hidden rounded-[var(--radius-control)] border border-line bg-surface transition-colors hover:border-line-strong"
            >
              <button
                type="button"
                onClick={() => toggleVersion(entry.version)}
                className="flex w-full items-center justify-between gap-4 p-4 text-left transition-colors hover:bg-surface-2/40"
                aria-expanded={isExpanded}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-sm font-bold text-ink">v{entry.version}</span>
                    {entry.is_current && <Badge tone="up">Current Installed</Badge>}
                    <span className="text-xs text-ink-3">· Released {entry.date}</span>
                  </div>
                  <h3 className="mt-1 text-[13.5px] font-medium text-ink">{entry.title}</h3>
                  <div className="mt-2 flex flex-wrap items-center gap-2.5 text-[11px] text-ink-3">
                    <span className="inline-flex items-center gap-1 font-medium text-up">
                      <Sparkles className="size-3" aria-hidden /> {entry.whats_new.length} updated
                    </span>
                    <span>·</span>
                    <span className="inline-flex items-center gap-1 font-medium text-ink-2">
                      <Wrench className="size-3" aria-hidden /> {entry.fixes.length} fixes
                    </span>
                    <span>·</span>
                    <span className="inline-flex items-center gap-1 font-medium text-brand">
                      <Zap className="size-3" aria-hidden /> {entry.improvements.length} improvements
                    </span>
                    <span>·</span>
                    <span className="inline-flex items-center gap-1 font-medium text-ink-3">
                      <ShieldCheck className="size-3" aria-hidden /> {entry.unchanged_protections.length} protected
                    </span>
                  </div>
                </div>
                <div className="shrink-0 text-ink-3">
                  {isExpanded ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
                </div>
              </button>

              {isExpanded && (
                <div className="border-t border-line/60 bg-surface-2/30 p-4 space-y-4 text-xs">
                  {entry.whats_new.length > 0 && (
                    <div>
                      <div className="mb-2 flex items-center gap-1.5 font-semibold text-up">
                        <Sparkles className="size-3.5" aria-hidden />
                        <span>What Was Updated (New Features)</span>
                      </div>
                      <ul className="space-y-1 pl-4 list-disc text-ink-2">
                        {entry.whats_new.map((item, idx) => (
                          <li key={idx} className="leading-relaxed">
                            {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {entry.fixes.length > 0 && (
                    <div>
                      <div className="mb-2 flex items-center gap-1.5 font-semibold text-ink-2">
                        <Wrench className="size-3.5" aria-hidden />
                        <span>Fixes &amp; Corrections</span>
                      </div>
                      <ul className="space-y-1 pl-4 list-disc text-ink-2">
                        {entry.fixes.map((item, idx) => (
                          <li key={idx} className="leading-relaxed">
                            {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {entry.improvements.length > 0 && (
                    <div>
                      <div className="mb-2 flex items-center gap-1.5 font-semibold text-brand">
                        <Zap className="size-3.5" aria-hidden />
                        <span>Performance &amp; UI Polish</span>
                      </div>
                      <ul className="space-y-1 pl-4 list-disc text-ink-2">
                        {entry.improvements.map((item, idx) => (
                          <li key={idx} className="leading-relaxed">
                            {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {entry.unchanged_protections.length > 0 && (
                    <div>
                      <div className="mb-2 flex items-center gap-1.5 font-semibold text-ink-3">
                        <ShieldCheck className="size-3.5" aria-hidden />
                        <span>What Was NOT Changed (Guaranteed Safeguards &amp; Invariants)</span>
                      </div>
                      <ul className="space-y-1 pl-4 list-disc text-ink-3">
                        {entry.unchanged_protections.map((item, idx) => (
                          <li key={idx} className="leading-relaxed">
                            {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

export type { ReactNode };
