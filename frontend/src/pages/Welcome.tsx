import { Check, Database, LineChart, Scale, ShieldCheck, Sprout, Zap } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useNavigate } from "react-router";
import { Illustration } from "../components/common";
import { DataFolderPicker } from "../components/DataFolderPicker";
import { Logo } from "../components/Logo";
import { Button, Callout, cx, Field, Input, ProgressBar } from "../components/ui";
import { errorMessage } from "../lib/api";
import { MONEY_LIMITS, moneyProblems } from "../lib/rules";
import { inr, int } from "../lib/format";
import { clearStep, readStep, writeStep } from "../lib/wizardStep";
import { useAcceptDisclaimer, useBuildIndex, useSetDataFolder, useStatus, useUpdateSettings } from "../lib/queries";
import type { Style } from "../lib/types";

const STEPS = ["Welcome", "Your style", "Money rules", "Market data"] as const;

export default function Welcome() {
  const status = useStatus();
  const [step, setStep] = useState(() => readStep());
  const navigate = useNavigate();
  const update = useUpdateSettings();

  const goTo = (next: number) => {
    setStep(next);
    writeStep(next);
  };

  const finish = () =>
    update.mutate(
      { onboarding_complete: true },
      {
        onSuccess: () => {
          clearStep();
          void navigate("/", { replace: true });
        },
      },
    );

  if (!status.data) return null;
  const accepted = Boolean(status.data.settings.disclaimer_accepted_at);
  const displayedStep = accepted ? step : 0;

  return (
    <div className="min-h-full bg-bg">
      <div className="mx-auto flex max-w-5xl flex-col px-6 py-8">
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Logo className="size-8" />
            <span className="text-[15px] font-semibold">QuantOS</span>
          </div>
          <ol className="hidden items-center gap-2 sm:flex" aria-label="Setup progress">
            {STEPS.map((label, i) => (
              <li key={label} className="flex items-center gap-2">
                <span
                  className={cx(
                    "flex size-6 items-center justify-center rounded-full text-[12px] font-semibold",
                    i < displayedStep ? "bg-up text-white" : i === displayedStep ? "bg-brand text-on-brand" : "bg-surface-3 text-ink-3",
                  )}
                  aria-current={i === displayedStep ? "step" : undefined}
                >
                  {i < displayedStep ? <Check className="size-3.5" aria-hidden /> : i + 1}
                </span>
                <span className={cx("text-[13px]", i === displayedStep ? "font-medium text-ink" : "text-ink-3")}>{label}</span>
                {i < STEPS.length - 1 && <span className="mx-1 h-px w-6 bg-line-strong" aria-hidden />}
              </li>
            ))}
          </ol>
        </header>
        <main className="mt-10 q-fade-in" key={displayedStep}>
          {displayedStep === 0 && <StepWelcome onNext={() => goTo(1)} accepted={accepted} />}
          {displayedStep === 1 && <StepStyle current={status.data.settings.style} shariahCurrent={status.data.settings.shariah_mode} onNext={() => goTo(2)} onBack={() => goTo(0)} />}
          {displayedStep === 2 && <StepMoney onNext={() => goTo(3)} onBack={() => goTo(1)} />}
          {displayedStep === 3 && <StepData onBack={() => goTo(2)} onFinish={finish} finishing={update.isPending} />}
        </main>
      </div>
    </div>
  );
}

function StepShell({ title, subtitle, children, art, footer }: { title: ReactNode; subtitle: ReactNode; children: ReactNode; art?: ReactNode; footer: ReactNode }) {
  return (
    <div className="grid items-center gap-10 lg:grid-cols-[1.1fr_0.9fr]">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">{title}</h1>
        <p className="mt-3 max-w-xl text-[15px] leading-relaxed text-ink-2">{subtitle}</p>
        <div className="mt-8">{children}</div>
        <div className="mt-8 flex flex-wrap items-center gap-3">{footer}</div>
      </div>
      <div className="hidden justify-center lg:flex">{art}</div>
    </div>
  );
}

function StepWelcome({ onNext, accepted }: { onNext: () => void; accepted: boolean }) {
  const [agree, setAgree] = useState(accepted);
  const accept = useAcceptDisclaimer();
  const points = [
    { icon: LineChart, title: "Real NSE prices", body: "Ten years of daily prices from the NSE, checked for gaps and bad records. QuantOS can download them for you." },
    { icon: Zap, title: "Every rupee of cost", body: "STT, exchange fees, stamp duty, GST and your broker's charges on every trade." },
    { icon: ShieldCheck, title: "Honest answers", body: "Each test is compared with simply holding NIFTY, and adjusted for how many ideas you have tried." },
  ];
  return (
    <StepShell
      title={<>Know before you risk real money.</>}
      subtitle="QuantOS helps you test trading and investing ideas on real market history, see exactly what they cost, and be told plainly whether an idea beat simply holding NIFTY."
      art={<Illustration name="welcome-hero" className="size-80" />}
      footer={
        <>
          <Button
            size="lg"
            disabled={!agree}
            loading={accept.isPending}
            onClick={() => (accepted ? onNext() : accept.mutate(undefined, { onSuccess: onNext }))}
          >
            Get started
          </Button>
          {!agree && <span className="text-[12.5px] text-ink-3">Tick the box below to continue.</span>}
        </>
      }
    >
      <ul className="space-y-4">
        {points.map(({ icon: Icon, title, body }) => (
          <li key={title} className="flex gap-3.5">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-brand-soft text-brand">
              <Icon className="size-5" aria-hidden />
            </span>
            <div>
              <div className="font-semibold text-ink">{title}</div>
              <div className="text-sm text-ink-2">{body}</div>
            </div>
          </li>
        ))}
      </ul>
      <label className="mt-8 flex cursor-pointer gap-3 rounded-xl border border-line bg-surface p-4 text-[13.5px] text-ink-2">
        <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} aria-labelledby="disclaimer-text" className="mt-0.5 size-4 accent-[var(--q-brand)]" />
        <span id="disclaimer-text">
          I understand that QuantOS is a research and practice tool, not investment advice. It is not registered with SEBI as an investment adviser
          or research analyst, and past results do not guarantee future returns.
        </span>
      </label>
    </StepShell>
  );
}

function StepStyle({ current, shariahCurrent, onNext, onBack }: { current: Style | null; shariahCurrent?: boolean; onNext: () => void; onBack: () => void }) {
  const [style, setStyle] = useState<Style | null>(current);
  const [shariah, setShariah] = useState<boolean>(Boolean(shariahCurrent));
  const update = useUpdateSettings();
  const options: { value: Style; icon: typeof Sprout; title: string; body: string }[] = [
    { value: "investor", icon: Sprout, title: "Investor", body: "I hold for months or years and want to know if my portfolio is beating the index." },
    { value: "swing", icon: LineChart, title: "Swing trader", body: "I hold for days to weeks and want to test my rules before trading them." },
    { value: "both", icon: Database, title: "A bit of both", body: "I keep a long-term portfolio and trade a part of my money." },
  ];
  return (
    <StepShell
      title="How do you invest?"
      subtitle="This sets sensible defaults. You can change it any time in Settings."
      art={<Illustration name="lab-hero" className="size-72" />}
      footer={
        <>
          <Button variant="ghost" onClick={onBack}>
            Back
          </Button>
          <Button
            size="lg"
            disabled={!style}
            loading={update.isPending}
            onClick={() => update.mutate({ style, shariah_mode: shariah }, { onSuccess: onNext })}
          >
            Continue
          </Button>
          {!style && <span className="text-[12.5px] text-ink-3">Choose one to continue.</span>}
        </>
      }
    >
      <div role="radiogroup" aria-label="Investing style" className="grid gap-3">
        {options.map(({ value, icon: Icon, title, body }) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={style === value}
            onClick={() => setStyle(value)}
            className={cx(
              "flex items-start gap-4 rounded-2xl border bg-surface p-4 text-left transition-colors",
              style === value ? "border-brand ring-3 ring-brand/15" : "border-line hover:border-line-strong",
            )}
          >
            <span className={cx("flex size-10 shrink-0 items-center justify-center rounded-xl", style === value ? "bg-brand text-on-brand" : "bg-surface-2 text-ink-2")}>
              <Icon className="size-5" aria-hidden />
            </span>
            <span>
              <span className="block font-semibold text-ink">{title}</span>
              <span className="mt-0.5 block text-sm text-ink-2">{body}</span>
            </span>
          </button>
        ))}
      </div>

      <div className="mt-5 rounded-2xl border border-line bg-surface p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className={cx("flex size-10 shrink-0 items-center justify-center rounded-xl", shariah ? "bg-emerald-600 text-white" : "bg-surface-2 text-ink-3")}>
              <Scale className="size-5" aria-hidden />
            </span>
            <div>
              <span className="block font-semibold text-ink">Mizan Shariah Compliance Mode</span>
              <span className="mt-0.5 block text-sm text-ink-2">Apply AAOIFI/TASIS screening, ethical baskets, and zakat tools.</span>
            </div>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={shariah}
            onClick={() => setShariah(!shariah)}
            className={cx(
              "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none",
              shariah ? "bg-emerald-600" : "bg-surface-3"
            )}
          >
            <span
              className={cx(
                "pointer-events-none inline-block size-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out",
                shariah ? "translate-x-5" : "translate-x-0"
              )}
            />
          </button>
        </div>
      </div>
    </StepShell>
  );
}

function StepMoney({ onNext, onBack }: { onNext: () => void; onBack: () => void }) {
  const status = useStatus();
  const money = status.data?.settings.money;
  const [capital, setCapital] = useState(money?.capital ?? "1000000");
  const [risk, setRisk] = useState(money?.risk_per_trade_pct ?? "1");
  const [daily, setDaily] = useState(money?.daily_loss_limit_pct ?? "2");
  const update = useUpdateSettings();
  const capitalValue = Number(capital) || 0;
  const riskAmount = (capitalValue * (Number(risk) || 0)) / 100;
  const dailyAmount = (capitalValue * (Number(daily) || 0)) / 100;
  const problems = moneyProblems(capital, risk, daily);
  const invalid = Object.keys(problems).length > 0;
  return (
    <StepShell
      title="Set your money rules"
      subtitle="Most blow-ups come from risking too much on one idea. QuantOS uses these rules to size positions and to warn you."
      art={<Illustration name="empty-portfolio" className="size-72" />}
      footer={
        <>
          <Button variant="ghost" onClick={onBack}>
            Back
          </Button>
          <Button
            size="lg"
            loading={update.isPending}
            disabled={invalid}
            onClick={() => update.mutate({ money: { capital, risk_per_trade_pct: risk, daily_loss_limit_pct: daily } }, { onSuccess: onNext })}
          >
            Continue
          </Button>
        </>
      }
    >
      <div className="grid gap-5 sm:grid-cols-3">
        <Field label="Money you trade with" htmlFor="capital" hint={`At least ${inr(MONEY_LIMITS.capitalMin, 0)}`} error={problems.capital}>
          <Input id="capital" prefix="₹" inputMode="numeric" value={capital} onChange={(e) => setCapital(e.target.value.replace(/[^\d.]/g, ""))} />
        </Field>
        <Field label="Risk per trade" htmlFor="risk" hint={`Up to ${MONEY_LIMITS.riskMax}%`} error={problems.risk}>
          <Input id="risk" suffix="%" inputMode="decimal" value={risk} onChange={(e) => setRisk(e.target.value.replace(/[^\d.]/g, ""))} />
        </Field>
        <Field label="Daily loss limit" htmlFor="daily" hint={`Up to ${MONEY_LIMITS.dailyMax}%`} error={problems.daily}>
          <Input id="daily" suffix="%" inputMode="decimal" value={daily} onChange={(e) => setDaily(e.target.value.replace(/[^\d.]/g, ""))} />
        </Field>
      </div>
      {update.isError && <Callout tone="danger" className="mt-4">{errorMessage(update.error)}</Callout>}
      {!invalid && (
        <Callout tone="info" className="mt-5" title="What this means">
          With {inr(capitalValue, 0)}, you would risk at most <strong className="text-ink">{inr(riskAmount, 0)}</strong> if a trade hits its stop, and
          stop for the day after losing <strong className="text-ink">{inr(dailyAmount, 0)}</strong>. Many professionals keep risk per trade at 1% or less.
        </Callout>
      )}
    </StepShell>
  );
}

function StepData({ onBack, onFinish, finishing }: { onBack: () => void; onFinish: () => void; finishing: boolean }) {
  const status = useStatus();
  const setFolder = useSetDataFolder();
  const build = useBuildIndex();
  const data = status.data!;
  const [path, setPath] = useState(data.settings.data_folder ?? data.data_folder.candidates[0]?.path ?? "");
  const job = data.index.job;
  const ready = data.index.ready && data.index.matches_folder === true && !data.index.stale && job.state !== "RUNNING";

  const connect = () =>
    setFolder.mutate(path, {
      onSuccess: () => build.mutate(),
    });

  return (
    <StepShell
      title="Connect your market data"
      subtitle="QuantOS looks for your NSE price data on this computer and builds a fast local index. You can change the folder at any time. Nothing is uploaded anywhere."
      art={<Illustration name="empty-data" className="size-72" />}
      footer={
        <>
          <Button variant="ghost" onClick={onBack}>
            Back
          </Button>
          {ready ? (
            <Button size="lg" loading={finishing} onClick={onFinish}>
              Open QuantOS
            </Button>
          ) : (
            <Button size="lg" loading={setFolder.isPending || build.isPending || job.state === "RUNNING"} disabled={!path || data.download.state === "RUNNING"} onClick={connect}>
              {job.state === "RUNNING" ? "Building index" : "Connect and build"}
            </Button>
          )}
          {!ready && (
            <Button variant="ghost" onClick={onFinish}>
              Skip for now
            </Button>
          )}
        </>
      }
    >
      <DataFolderPicker path={path} onPath={setPath} />
      {(setFolder.isError || build.isError) && (
        <Callout tone="danger" className="mt-4">
          {errorMessage(setFolder.error ?? build.error)}
        </Callout>
      )}
      {job.state === "RUNNING" && (
        <div className="mt-6 space-y-2">
          <ProgressBar value={job.progress} label="Building market index" />
          <div className="flex justify-between text-[12.5px] text-ink-3">
            <span>{job.message}</span>
            <span className="num">{Math.round(job.progress * 100)}%</span>
          </div>
        </div>
      )}
      {job.state === "ERROR" && (
        <Callout tone="danger" className="mt-4" title="The index could not be built">
          {job.error}
        </Callout>
      )}
      {ready && (
        <Callout tone="success" className="mt-6" title="Market data connected">
          {int(data.index.symbols ?? 0)} stocks and ETFs indexed, up to the session of {data.index.latest_session}.
        </Callout>
      )}
    </StepShell>
  );
}
