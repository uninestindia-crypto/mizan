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

function AppRows({ apps, choice, name, onPick }: ListProps & { apps: AiApp[] }) {
  return sortApps(apps).map((app) => (
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
      {!apps && (
        <Link to="/settings/accounts" className="inline-block text-[13px] font-medium text-brand hover:underline">
          Add a key under Accounts &amp; keys
        </Link>
      )}
    </fieldset>
  );
}
