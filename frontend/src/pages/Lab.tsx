import { ArrowRight, Clock, ShieldCheck, TriangleAlert } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { DataGate, Illustration, VerdictBadge } from "../components/common";
import { Badge, Card, CardHeader, Delta, EmptyState, PageHeader, Skeleton } from "../components/ui";
import { date, dateTime, int, pct } from "../lib/format";
import { useLabRuns, useTemplates } from "../lib/queries";

export default function Lab() {
  return (
    <>
      <PageHeader
        title="Strategy Lab"
        subtitle="Test a trading or investing rule on real NSE prices before you risk money. Every test pays real charges and is judged against simply holding NIFTY."
      />
      <DataGate>
        <LabHome />
      </DataGate>
    </>
  );
}

function LabHome() {
  const templates = useTemplates();
  const runs = useLabRuns();
  const navigate = useNavigate();
  return (
    <div className="space-y-6">
      <Card className="overflow-hidden">
        <div className="flex flex-col gap-6 md:flex-row md:items-center">
          <div className="grid flex-1 gap-5 sm:grid-cols-3">
            <Principle icon={<ShieldCheck className="size-5" aria-hidden />} title="No peeking" body="Decisions use only past prices and fill at the next day's open." />
            <Principle icon={<Clock className="size-5" aria-hidden />} title="Real costs" body="STT, exchange fees, stamp duty, GST, slippage and your broker's charges." />
            <Principle
              icon={<TriangleAlert className="size-5" aria-hidden />}
              title="Luck counts"
              body={`You have run ${int(templates.data?.runs_so_far ?? 0)} tests. Each one raises the bar for the next.`}
            />
          </div>
          <Illustration name="lab-hero" className="hidden size-36 shrink-0 md:block" />
        </div>
      </Card>

      <section aria-labelledby="templates-heading">
        <h2 id="templates-heading" className="mb-3 text-[15px] font-semibold text-ink">
          Choose a strategy to test
        </h2>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {templates.isPending &&
            Array.from({ length: 5 }, (_, i) => (
              <Card key={i}>
                <Skeleton className="h-32" />
              </Card>
            ))}
          {templates.data?.templates.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => void navigate(`/lab/new/${t.id}`)}
              className="group flex h-full flex-col rounded-[var(--radius-card)] border border-line bg-surface p-5 text-left shadow-[var(--shadow-card)] transition-all hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-[var(--shadow-pop)]"
            >
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-base font-semibold text-ink">{t.name}</h3>
                <Badge>{t.holding_period}</Badge>
              </div>
              <p className="mt-2 text-sm text-ink-2">{t.summary}</p>
              <p className="mt-3 text-[12.5px] text-ink-3">
                <span className="font-medium text-ink-2">Usually fails when: </span>
                {t.fails_when}
              </p>
              <span className="mt-auto flex items-center gap-1 pt-4 text-[13px] font-medium text-brand">
                Set up a test <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden />
              </span>
            </button>
          ))}
        </div>
      </section>

      <Card padded={false}>
        <div className="px-5 pt-5">
          <CardHeader title="Your tests" subtitle="Every test is kept: deleting the bad ones would make the good ones look more convincing than they are." />
        </div>
        {runs.isPending ? (
          <div className="p-5">
            <Skeleton className="h-24" />
          </div>
        ) : (runs.data ?? []).length === 0 ? (
          <EmptyState title="No tests yet" body="Pick a strategy above. Your results will be listed here." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead>
                <tr className="border-y border-line bg-surface-2/60 text-left text-[12px] font-semibold uppercase tracking-wide text-ink-3">
                  <th className="px-5 py-2.5">Strategy</th>
                  <th className="px-3 py-2.5">On</th>
                  <th className="px-3 py-2.5">Period</th>
                  <th className="px-3 py-2.5 text-right">Result</th>
                  <th className="px-3 py-2.5 text-right">NIFTY</th>
                  <th className="px-5 py-2.5">Verdict</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {(runs.data ?? []).map((r) => (
                  <tr key={r.id} className="cursor-pointer transition-colors hover:bg-surface-2" onClick={() => void navigate(`/lab/runs/${r.id}`)}>
                    <td className="px-5 py-3">
                      <Link to={`/lab/runs/${r.id}`} className="font-medium text-ink hover:underline" onClick={(e) => e.stopPropagation()}>
                        {r.template_name}
                      </Link>
                      <div className="text-[12px] text-ink-3">{dateTime(r.created_at)}</div>
                    </td>
                    <td className="max-w-[220px] truncate px-3 py-3 text-ink-2">{r.scope_label}</td>
                    <td className="num px-3 py-3 text-ink-2">
                      {date(r.period_start)} – {date(r.period_end)}
                    </td>
                    <td className="px-3 py-3 text-right">
                      <Delta value={r.strategy_return} strong>
                        {pct(r.strategy_return)}
                      </Delta>
                    </td>
                    <td className="px-3 py-3 text-right">
                      <Delta value={r.benchmark_return}>{pct(r.benchmark_return)}</Delta>
                    </td>
                    <td className="px-5 py-3">
                      <VerdictBadge level={r.verdict_level} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function Principle({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className="flex gap-3">
      <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-brand-soft text-brand">{icon}</span>
      <div>
        <div className="text-sm font-semibold text-ink">{title}</div>
        <div className="mt-0.5 text-[13px] text-ink-2">{body}</div>
      </div>
    </div>
  );
}
