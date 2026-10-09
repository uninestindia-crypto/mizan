import { ArrowDown, ArrowUp } from "lucide-react";
import { type ReactNode, useId } from "react";
import { Link } from "react-router";
import {
  type AiApp,
  type AppId,
  type AiChoice,
  type AiSettingsPatch,
  type AiStatus,
  type Chip,
  appChip,
  appName,
  keyChip,
  needsSetup,
  showAppSetup,
  sortApps,
  sortKeys,
  UNKNOWN_HINT,
} from "../../lib/aiSource";
import { Badge, Button, cx } from "../ui";

const AUTOMATIC = "Automatic (first one that is ready)";
const ROW = "flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-lg border px-3 py-2 transition-colors";
const RADIO_LABEL = "flex min-w-0 flex-1 cursor-pointer items-center gap-3 text-[13.5px] text-ink";
// On a phone the name sits above its chip, so every row reads the same; from a small tablet up they share a line.
const NAME_AND_CHIP = "flex min-w-0 flex-col items-start gap-1 sm:flex-row sm:items-center sm:gap-3";

interface RowProps {
  id: string | null;
  checked: boolean;
  name: string;
  title: string;
  chip?: Chip;
  hint?: string | null;
  action?: ReactNode;
  onPick: () => void;
}

function Row(props: RowProps) {
  const { id, checked, name, title, chip, hint, action, onPick } = props;
  const border = checked ? "border-brand bg-brand-soft/40" : "border-line bg-surface hover:border-line-strong";
  return (
    <li className={cx(ROW, border)} data-choice={id ?? "automatic"}>
      <label className={RADIO_LABEL}>
        <input type="radio" name={name} className="size-4 shrink-0 accent-brand" checked={checked} onChange={onPick} />
        <span className={NAME_AND_CHIP}>
          <span className="font-medium">{title}</span>
          {chip && <Badge tone={chip.tone}>{chip.text}</Badge>}
        </span>
      </label>
      {action}
      {hint && <p className="basis-full pl-7 text-[12.5px] text-ink-3">{hint}</p>}
    </li>
  );
}

function SetUp({ app }: { app: AiApp }) {
  return (
    <Button
      size="sm"
      variant="secondary"
      aria-label={`Set up ${appName(app)}`}
      onClick={() => showAppSetup(app.name)}
    >
      Set up
    </Button>
  );
}

interface ListProps {
  choice: AiChoice;
  name: string;
  onPick: (id: string | null) => void;
}

function sortedByPriority(apps: AiApp[], priority?: string[]): AiApp[] {
  if (!priority || priority.length === 0) return sortApps(apps);
  const prioritized = priority.map((id) => apps.find((a) => a.id === id)).filter((a): a is AiApp => !!a);
  const rest = apps.filter((a) => !priority.includes(a.id));
  return [...prioritized, ...sortApps(rest)];
}

function AppRows({ apps, choice, name, onPick }: ListProps & { apps: AiApp[] }) {
  return sortedByPriority(apps, choice.cli_priority).map((app) => (
    <Row
      key={app.id}
      id={app.id}
      checked={choice.cli === app.id}
      name={name}
      title={appName(app)}
      chip={appChip(app)}
      hint={app.state === "UNKNOWN" ? UNKNOWN_HINT : null}
      action={needsSetup(app) ? <SetUp app={app} /> : null}
      onPick={() => onPick(app.id)}
    />
  ));
}

function KeyRows({ providers, choice, name, onPick }: ListProps & { providers: AiStatus["providers"] }) {
  return sortKeys(providers).map((provider) => (
    <Row
      key={provider.id}
      id={provider.id}
      checked={choice.api === provider.id}
      name={name}
      title={provider.label}
      chip={keyChip(provider)}
      onPick={() => onPick(provider.id)}
    />
  ));
}

function CliPriorityOrder({
  apps,
  priority,
  onChange,
}: {
  apps: AiApp[];
  priority?: string[];
  onChange: (patch: AiSettingsPatch) => void;
}) {
  const currentOrder = sortedByPriority(apps, priority).map((a) => a.id);

  const move = (fromIndex: number, toIndex: number) => {
    const next = [...currentOrder];
    const moved = next[fromIndex];
    if (moved === undefined) return;
    next.splice(fromIndex, 1);
    next.splice(toIndex, 0, moved);
    onChange({ cli_priority: next });
  };

  if (apps.length <= 1) return null;

  return (
    <div className="mt-4 rounded-xl border border-line bg-surface-2/40 p-3 space-y-2.5">
      <div className="flex items-center justify-between">
        <h4 className="text-[13px] font-semibold text-ink">AI App Priority Order</h4>
        <span className="text-[11px] text-ink-3">Higher priority answers first</span>
      </div>
      <p className="text-[12px] text-ink-3 leading-relaxed">
        QuantOS asks your #1 priority app first. If it cannot answer, is offline, or hits an issue, it automatically falls back down the chain to the next app.
      </p>
      <ul className="space-y-1.5">
        {currentOrder.map((appId, index) => {
          const app = apps.find((a) => a.id === appId);
          if (!app) return null;
          return (
            <li
              key={appId}
              className="flex items-center justify-between rounded-lg border border-line bg-surface px-3 py-1.5 text-[12.5px]"
            >
              <div className="flex items-center gap-2">
                <span className="flex size-5 items-center justify-center rounded-full bg-brand/10 font-bold text-[11px] text-brand">
                  {index + 1}
                </span>
                <span className="font-medium text-ink">{appName(app)}</span>
                <span className="text-[11px] text-ink-3">
                  {index === 0 ? "(Primary)" : `(Fallback #${index})`}
                </span>
              </div>
              <div className="flex items-center gap-1">
                <Button
                  size="sm"
                  variant="ghost"
                  className="size-7 p-0"
                  disabled={index === 0}
                  aria-label={`Move ${appName(app)} up`}
                  onClick={() => move(index, index - 1)}
                >
                  <ArrowUp className="size-3.5" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="size-7 p-0"
                  disabled={index === currentOrder.length - 1}
                  aria-label={`Move ${appName(app)} down`}
                  onClick={() => move(index, index + 1)}
                >
                  <ArrowDown className="size-3.5" />
                </Button>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Which app, or which saved key, to ask first. "Automatic" leaves it to the first one that is ready. */
export function AiSourcePrefer({
  status,
  choice,
  onChange,
}: {
  status: AiStatus;
  choice: AiChoice;
  onChange: (patch: AiSettingsPatch) => void;
}) {
  const name = useId();
  const apps = choice.source === "cli";
  const picked = apps ? choice.cli : choice.api;
  const pick = (id: string | null) => onChange(apps ? { ai_cli: id as AppId | null } : { ai_api: id });
  return (
    <fieldset className="space-y-2">
      <legend className="text-[13.5px] font-semibold text-ink">Prefer</legend>
      <p className="text-[12.5px] text-ink-3">
        {apps ? "Which AI app to ask first." : "Which saved key to ask first."}
      </p>
      <ul className={cx("grid gap-2", !apps && "sm:grid-cols-2")}>
        <Row id={null} checked={picked === null} name={name} title={AUTOMATIC} onPick={() => pick(null)} />
        {apps ? (
          <AppRows apps={status.apps} choice={choice} name={name} onPick={pick} />
        ) : (
          <KeyRows providers={status.providers} choice={choice} name={name} onPick={pick} />
        )}
      </ul>
      {apps && (
        <CliPriorityOrder
          apps={status.apps}
          priority={choice.cli_priority}
          onChange={onChange}
        />
      )}
      {!apps && (
        <Link to="/settings/accounts" className="inline-block text-[13px] font-medium text-brand hover:underline">
          Add a key under Accounts &amp; keys
        </Link>
      )}
    </fieldset>
  );
}
