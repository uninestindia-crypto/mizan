import { Check, Database, LineChart, ShieldCheck, Sprout, Zap } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useNavigate } from "react-router";
import { Illustration } from "../components/common";
import { DataFolderPicker } from "../components/DataFolderPicker";
import { Logo } from "../components/Logo";
import { Button, Callout, cx, Field, Input, ProgressBar } from "../components/ui";
import { errorMessage } from "../lib/api";
import { inr, int } from "../lib/format";
import { useAcceptDisclaimer, useBuildIndex, useSetDataFolder, useStatus, useUpdateSettings } from "../lib/queries";
import type { Style } from "../lib/types";

const STEPS = ["Welcome", "Your style", "Money rules", "Market data"] as const;

export default function Welcome() {
  const status = useStatus();
  const [step, setStep] = useState(0);
  const navigate = useNavigate();
  const update = useUpdateSettings();

  const finish = () =>
    update.mutate({ onboarding_complete: true }, { onSuccess: () => void navigate("/", { replace: true }) });

  if (!status.data) return null;
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
                    i < step ? "bg-up text-white" : i === step ? "bg-brand text-on-brand" : "bg-surface-3 text-ink-3",
                  )}
                  aria-current={i === step ? "step" : undefined}
                >
                  {i < step ? <Check className="size-3.5" aria-hidden /> : i + 1}
                </span>
                <span className={cx("text-[13px]", i === step ? "font-medium text-ink" : "text-ink-3")}>{label}</span>
                {i < STEPS.length - 1 && <span className="mx-1 h-px w-6 bg-line-strong" aria-hidden />}
              </li>
            ))}
          </ol>
        </header>
        <main className="mt-10 q-fade-in" key={step}>
          {step === 0 && <StepWelcome onNext={() => setStep(1)} accepted={Boolean(status.data.settings.disclaimer_accepted_at)} />}
          {step === 1 && <StepStyle current={status.data.settings.style} onNext={() => setStep(2)} onBack={() => setStep(0)} />}
          {step === 2 && <StepMoney onNext={() => setStep(3)} onBack={() => setStep(1)} />}
          {step === 3 && <StepData onBack={() => setStep(2)} onFinish={finish} finishing={update.isPending} />}
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
    { icon: LineChart, title: "Real NSE prices", body: "Ten years of daily data for 3,000+ stocks and ETFs, checked for gaps and bad records." },
    { icon: Zap, title: "Every rupee of cost", body: "STT, exchange fees, stamp duty, GST and your broker's charges on every trade." },
    { icon: ShieldCheck, title: "Honest answers", body: "Each test is compared with simply holding NIFTY, and adjusted for how many ideas you have tried." },
  ];
  return (
    <StepShell
      title={<>Know before you risk real money.</>}
      subtitle="QuantOS helps you test trading and investing ideas on real market history, see exactly what they cost, and practise with virtual money first."
      art={<Illustration name="welcome-hero" className="size-80" />}
      footer={
        <Button
          size="lg"
          disabled={!agree}
          loading={accept.isPending}
          onClick={() => (accepted ? onNext() : accept.mutate(undefined, { onSuccess: onNext }))}
        >
          Get started
        </Button>
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

function StepStyle({ current, onNext, onBack }: { current: Style | null; onNext: () => void; onBack: () => void }) {
  const [style, setStyle] = useState<Style | null>(current);
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
          <Button size="lg" disabled={!style} loading={update.isPending} onClick={() => update.mutate({ style }, { onSuccess: onNext })}>
            Continue
          </Button>
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
            onClick={() => update.mutate({ money: { capital, risk_per_trade_pct: risk, daily_loss_limit_pct: daily } }, { onSuccess: onNext })}
          >
            Continue
          </Button>
        </>
      }
    >
      <div className="grid gap-5 sm:grid-cols-3">
        <Field label="Money you trade with" htmlFor="capital">
          <Input id="capital" prefix="₹" inputMode="numeric" value={capital} onChange={(e) => setCapital(e.target.value.replace(/[^\d.]/g, ""))} />
        </Field>
        <Field label="Risk per trade" htmlFor="risk">
          <Input id="risk" suffix="%" inputMode="decimal" value={risk} onChange={(e) => setRisk(e.target.value.replace(/[^\d.]/g, ""))} />
        </Field>
        <Field label="Daily loss limit" htmlFor="daily">
          <Input id="daily" suffix="%" inputMode="decimal" value={daily} onChange={(e) => setDaily(e.target.value.replace(/[^\d.]/g, ""))} />
        </Field>
      </div>
      {update.isError && <Callout tone="danger" className="mt-4">{errorMessage(update.error)}</Callout>}
      <Callout tone="info" className="mt-5" title="What this means">
        With {inr(capitalValue, 0)}, you would risk at most <strong className="text-ink">{inr(riskAmount, 0)}</strong> if a trade hits its stop, and
        stop for the day after losing <strong className="text-ink">{inr(dailyAmount, 0)}</strong>. Many professionals keep risk per trade at 1% or less.
      </Callout>
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
