import { ArrowLeft, FlaskConical, Play } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { DataGate, SymbolChips, SymbolSearch } from "../components/common";
import { Button, Callout, Card, CardHeader, EmptyState, Field, HelpTip, Input, PageHeader, Segmented, Select, Skeleton, Switch } from "../components/ui";
import { ApiError, errorMessage } from "../lib/api";
import { date, inr } from "../lib/format";
import { useRunLab, useStatus, useTemplates } from "../lib/queries";
import type { Template } from "../lib/types";

export default function LabNew() {
  return (
    <DataGate>
      <LabNewPage />
    </DataGate>
  );
}

function LabNewPage() {
  const { templateId = "" } = useParams();
  const templates = useTemplates();
  if (templates.isPending) return <Skeleton className="h-96" />;
  const template = templates.data?.templates.find((t) => t.id === templateId);
  if (!template || !templates.data) {
    return (
      <EmptyState
        title="Unknown strategy"
        action={
          <Link to="/lab">
            <Button variant="secondary">Back to the lab</Button>
          </Link>
        }
      />
    );
  }
  return <Configure template={template} universes={templates.data.universes} coveredFrom={templates.data.costs_covered_from} />;
}

const MIN_CAPITAL = 10_000;

function Configure({ template, universes, coveredFrom }: { template: Template; universes: { id: string; label: string }[]; coveredFrom: string }) {
  const [search] = useSearchParams();
  const status = useStatus();
  const navigate = useNavigate();
  const run = useRunLab();
  const canUniverse = template.scopes.includes("universe");
  const canStocks = template.scopes.includes("stocks");
  const initialSymbols = useMemo(() => (search.get("symbols") ?? "").split(",").map((s) => s.trim().toUpperCase()).filter(Boolean).slice(0, 20), [search]);
  const [scope, setScope] = useState<"stocks" | "universe">(canUniverse && initialSymbols.length === 0 ? "universe" : "stocks");
  const [symbols, setSymbols] = useState<string[]>(initialSymbols);
  const [universe, setUniverse] = useState(universes[0]?.id ?? "liquid");
  const [params, setParams] = useState<Record<string, number | boolean>>(() => {
    const defaults = Object.fromEntries(template.params.map((p) => [p.name, p.default])) as Record<string, number | boolean>;
    try {
      // "Test again with changes" passes the previous settings along.
      const previous = JSON.parse(search.get("params") ?? "{}") as Record<string, number | boolean>;
      for (const name of Object.keys(defaults)) {
        const value = previous[name];
        if (value !== undefined) defaults[name] = value;
      }
    } catch {
      /* ignore a malformed link */
    }
    return defaults;
  });
  const [start, setStart] = useState(search.get("start") || coveredFrom);
  const [end, setEnd] = useState(search.get("end") ?? "");
  const [capital, setCapital] = useState(search.get("capital") ?? status.data?.settings.money.capital ?? "1000000");
  const [slippage, setSlippage] = useState(search.get("slippage") ?? "5");
  // A double-click lands before React re-renders the button as busy; without this each click saved a test,
  // and every saved test makes the next verdict harder to pass.
  const submitting = useRef(false);

  useEffect(() => {
    if (status.data && !search.get("capital")) setCapital(status.data.settings.money.capital);
  }, [status.data?.settings.money.capital]); // eslint-disable-line react-hooks/exhaustive-deps

  const capitalValue = Number(capital);
  const blocking =
    scope === "stocks" && symbols.length === 0
      ? "Add at least one stock."
      : !capital || capitalValue < MIN_CAPITAL
        ? `Starting money must be at least ${inr(MIN_CAPITAL, 0)}.`
        : null;
  const refusedSymbol = run.error instanceof ApiError && run.error.code === "LAB_REFUSED" ? /^([A-Z0-9&-]+)(?:'s)? /.exec(run.error.message)?.[1] : undefined;

  const submit = (override?: string[]) => {
    if (submitting.current) return;
    submitting.current = true;
    run.mutate(
      {
        template_id: template.id,
        params,
        scope,
        symbols: override ?? symbols,
        universe: scope === "universe" ? universe : null,
        start: start || null,
        end: end || null,
        capital: capital || null,
        slippage_bps: slippage || "5",
      },
      {
        onSuccess: (result) => void navigate(`/lab/runs/${result.id}`),
        onSettled: () => {
          submitting.current = false;
        },
      },
    );
  };

  return (
    <div className="space-y-5">
      <Link to="/lab" className="inline-flex items-center gap-1 text-[13px] font-medium text-ink-3 hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden /> Strategy Lab
      </Link>
      <PageHeader eyebrow="New test" title={template.name} subtitle={template.how_it_works} />
      <div className="grid gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <Card>
            <CardHeader title="What to test it on" />
            {canUniverse && canStocks && (
              <div className="mb-4">
                <Segmented
                  label="Scope"
                  value={scope}
                  onChange={setScope}
                  options={[
                    { value: "universe", label: "A whole universe" },
                    { value: "stocks", label: "Stocks I pick" },
                  ]}
                />
              </div>
            )}
            {scope === "stocks" ? (
              <div className="space-y-3">
                <SymbolSearch onPick={(s) => setSymbols((list) => (list.includes(s) || list.length >= 20 ? list : [...list, s]))} exclude={symbols} />
                <SymbolChips symbols={symbols} onRemove={(s) => setSymbols((list) => list.filter((x) => x !== s))} />
                <p className="text-[12.5px] text-ink-3">Up to 20 stocks or ETFs. The money is split equally between them.</p>
              </div>
            ) : (
              <Field label="Universe" htmlFor="universe" hint="Stocks listed today only, so companies that failed are missing. QuantOS judges universe tests against owning the whole list.">
                <Select id="universe" value={universe} onChange={(e) => setUniverse(e.target.value)}>
                  {universes.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.label}
                    </option>
                  ))}
                </Select>
              </Field>
            )}
          </Card>
          {template.params.length > 0 && (
            <Card>
              <CardHeader title="Settings" subtitle="Changing settings until the result looks good is how backtests fool people. Each run counts." />
              <div className="grid gap-5 sm:grid-cols-2">
                {template.params.map((p) =>
                  p.kind === "bool" ? (
                    <div key={p.name} className="flex flex-col justify-end gap-1.5">
                      <Switch checked={Boolean(params[p.name])} onChange={(v) => setParams({ ...params, [p.name]: v })} label={p.label} />
                      <p className="text-[12.5px] text-ink-3">{p.help}</p>
                    </div>
                  ) : (
                    <Field key={p.name} label={p.label} htmlFor={`p-${p.name}`} hint={`${p.help} ${p.min}–${p.max}.`}>
                      <Input
                        id={`p-${p.name}`}
                        type="number"
                        min={p.min}
                        max={p.max}
                        value={String(params[p.name])}
                        onChange={(e) => setParams({ ...params, [p.name]: Math.round(Number(e.target.value)) })}
                      />
                    </Field>
                  ),
                )}
              </div>
            </Card>
          )}
          <Card>
            <CardHeader title="Money and period" />
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Starting capital" htmlFor="capital" hint={`${inr(Number(capital) || 0, 0)} · at least ${inr(MIN_CAPITAL, 0)}`}>
                <Input id="capital" prefix="₹" inputMode="numeric" value={capital} onChange={(e) => setCapital(e.target.value.replace(/[^\d.]/g, ""))} />
              </Field>
              <Field label={<span className="inline-flex items-center gap-1">Slippage <HelpTip text="Extra price paid on every fill because you cannot always trade at the exact open. 5 basis points = 0.05%." /></span>} htmlFor="slippage">
                <Input id="slippage" suffix="bps" inputMode="numeric" value={slippage} onChange={(e) => setSlippage(e.target.value.replace(/\D/g, ""))} />
              </Field>
              <Field
                label="Start"
                htmlFor="start"
                hint={`Tests start no earlier than ${date(coveredFrom)}, when exact NSE charges begin.`}
                error={start && start < coveredFrom ? `That is before ${date(coveredFrom)}, so the test will start on ${date(coveredFrom)}.` : undefined}
              >
                <Input id="start" type="date" min={coveredFrom} value={start} onChange={(e) => setStart(e.target.value)} />
              </Field>
              <Field label="End (optional)" htmlFor="end" hint="Defaults to the last day NIFTY data covers.">
                <Input id="end" type="date" min={start} value={end} onChange={(e) => setEnd(e.target.value)} />
              </Field>
            </div>
          </Card>
        </div>
        <div className="space-y-5">
          <Card className="lg:sticky lg:top-6">
            <div className="flex items-center gap-3">
              <span className="flex size-10 items-center justify-center rounded-xl bg-brand-soft text-brand">
                <FlaskConical className="size-5" aria-hidden />
              </span>
              <div>
                <div className="font-semibold text-ink">{template.name}</div>
                <div className="text-[12.5px] text-ink-3">Holding period: {template.holding_period}</div>
              </div>
            </div>
            <p className="mt-4 text-[13.5px] text-ink-2">
              <span className="font-medium text-ink">Usually fails when: </span>
              {template.fails_when}
            </p>
            <div className="mt-5 space-y-3">
              {run.isError && (
                <Callout
                  tone="danger"
                  title="The lab refused this test"
                  action={
                    refusedSymbol && symbols.includes(refusedSymbol) && symbols.length > 1 ? (
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => {
                          const next = symbols.filter((s) => s !== refusedSymbol);
                          setSymbols(next);
                          submit(next);
                        }}
                      >
                        Remove {refusedSymbol} and run
                      </Button>
                    ) : undefined
                  }
                >
                  {errorMessage(run.error)}
                </Callout>
              )}
              {blocking && <p className="text-[13px] text-ink-3">{blocking}</p>}
              <Button size="lg" className="w-full" icon={<Play className="size-4" aria-hidden />} disabled={Boolean(blocking)} loading={run.isPending} onClick={() => submit()}>
                {run.isPending ? "Testing on real NSE data…" : "Run test"}
              </Button>
              <p className="text-center text-[12px] text-ink-3">This will be test #{(status.data?.lab_runs ?? 0) + 1}.</p>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
