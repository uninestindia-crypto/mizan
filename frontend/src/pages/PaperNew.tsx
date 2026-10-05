import { ArrowLeft, Play } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { DataGate, SymbolChips, SymbolSearch } from "../components/common";
import {
  Button,
  Callout,
  Card,
  CardHeader,
  cx,
  Field,
  HelpTip,
  Input,
  PageHeader,
  Segmented,
  Select,
  Skeleton,
  Switch,
} from "../components/ui";
import { errorMessage } from "../lib/api";
import { inr } from "../lib/format";
import { useLabRun, useStartPaperBook, useStatus, useTemplates } from "../lib/queries";
import type { LabResult, PaperBookInput, Template, Templates } from "../lib/types";

export default function PaperNew() {
  return (
    <DataGate>
      <PaperNewPage />
    </DataGate>
  );
}

function PaperNewPage() {
  const [search] = useSearchParams();
  const from = (search.get("from") ?? "").trim();
  const templates = useTemplates();

  if (templates.isPending) return <Skeleton className="h-96" />;
  if (templates.isError || !templates.data || templates.data.templates.length === 0) {
    return (
      <Card>
        <div className="p-6 text-center text-sm text-ink-3">
          Could not load strategy templates. Make sure market data is indexed.
        </div>
      </Card>
    );
  }

  if (from) {
    return <PaperNewPrefilled from={from} templates={templates.data} />;
  }

  return <PaperNewForm templates={templates.data} />;
}

function PaperNewPrefilled({ from, templates }: { from: string; templates: Templates }) {
  const run = useLabRun(from);
  if (run.isPending) return <Skeleton className="h-96" />;
  return <PaperNewForm templates={templates} prefillRun={run.data} />;
}

function makeDefaultName(
  templateName: string,
  scope: "stocks" | "universe",
  symbols: string[],
  universeId: string,
  universes: { id: string; label: string }[],
): string {
  let target = "";
  if (scope === "stocks") {
    if (symbols.length > 0) {
      target = ` · ${symbols.join(", ")}`;
    }
  } else {
    const u = universes.find((item) => item.id === universeId);
    if (u) {
      target = ` · ${u.label}`;
    }
  }
  return `${templateName}${target}`.slice(0, 60);
}

const MIN_CAPITAL = 10_000;

function PaperNewForm({ templates, prefillRun }: { templates: Templates; prefillRun?: LabResult }) {
  const status = useStatus();
  const navigate = useNavigate();
  const startBook = useStartPaperBook();

  const initialTemplate = useMemo(() => {
    if (prefillRun) {
      const match = templates.templates.find((t) => t.id === prefillRun.template.id);
      if (match) return match;
    }
    return templates.templates[0]!;
  }, [prefillRun, templates.templates]);

  const [selectedTemplate, setSelectedTemplate] = useState<Template>(initialTemplate);

  const [scope, setScope] = useState<"stocks" | "universe">(() => {
    if (prefillRun) {
      const kind = prefillRun.scope.kind;
      if (initialTemplate.scopes.includes(kind)) return kind;
    }
    return initialTemplate.scopes.includes("stocks") ? "stocks" : "universe";
  });

  const [symbols, setSymbols] = useState<string[]>(() => {
    if (prefillRun?.scope.requested) {
      return prefillRun.scope.requested.slice(0, 20);
    }
    return [];
  });

  const [universe, setUniverse] = useState<string>(() => {
    if (prefillRun?.scope.universe) {
      return prefillRun.scope.universe;
    }
    return templates.universes[0]?.id ?? "liquid";
  });

  const [params, setParams] = useState<Record<string, number | boolean>>(() => {
    const defaults = Object.fromEntries(initialTemplate.params.map((p) => [p.name, p.default])) as Record<string, number | boolean>;
    if (prefillRun && prefillRun.template.id === initialTemplate.id) {
      return { ...defaults, ...prefillRun.params };
    }
    return defaults;
  });

  const [capital, setCapital] = useState<string>(() => {
    if (prefillRun) return String(prefillRun.capital);
    return status.data?.settings.money.capital ?? "1000000";
  });

  const [slippage, setSlippage] = useState("5");

  const [nameTouched, setNameTouched] = useState(false);
  const [name, setName] = useState<string>(() => {
    return makeDefaultName(initialTemplate.name, scope, symbols, universe, templates.universes);
  });

  useEffect(() => {
    if (!prefillRun && status.data?.settings.money.capital && capital === "1000000") {
      setCapital(status.data.settings.money.capital);
    }
  }, [status.data?.settings.money.capital]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!nameTouched) {
      setName(makeDefaultName(selectedTemplate.name, scope, symbols, universe, templates.universes));
    }
  }, [nameTouched, selectedTemplate.name, scope, symbols, universe, templates.universes]);

  const handleSelectTemplate = (t: Template) => {
    setSelectedTemplate(t);
    const defaults = Object.fromEntries(t.params.map((p) => [p.name, p.default])) as Record<string, number | boolean>;
    setParams(defaults);
    if (!t.scopes.includes(scope)) {
      setScope(t.scopes.includes("stocks") ? "stocks" : "universe");
    }
  };

  const capitalValue = Number(capital);
  const trimmedName = name.trim();
  const blocking =
    !trimmedName
      ? "Enter a name for this paper book."
      : scope === "stocks" && symbols.length === 0
        ? "Add at least one stock."
        : !capital || capitalValue < MIN_CAPITAL
          ? `Starting money must be at least ${inr(MIN_CAPITAL, 0)}.`
          : null;

  const submitting = useRef(false);

  const submit = () => {
    if (submitting.current || Boolean(blocking)) return;
    submitting.current = true;

    const payload: PaperBookInput = {
      name: trimmedName,
      template_id: selectedTemplate.id,
      params,
      scope,
      symbols: scope === "stocks" ? symbols : [],
      universe: scope === "universe" ? universe : null,
      capital: capital || "1000000",
      slippage_bps: slippage || "5",
    };

    startBook.mutate(payload, {
      onSuccess: (book) => void navigate(`/paper/${book.id}`),
      onSettled: () => {
        submitting.current = false;
      },
    });
  };

  const canBothScopes = selectedTemplate.scopes.includes("stocks") && selectedTemplate.scopes.includes("universe");

  return (
    <div className="space-y-5">
      <Link to="/paper" className="inline-flex items-center gap-1 text-[13px] font-medium text-ink-3 hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden /> Paper trading
      </Link>
      <PageHeader
        eyebrow="New paper book"
        title="Start a paper book"
        subtitle="Follow a strategy rule forward in time with virtual money on real prices. It never places real orders."
      />

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          {/* 1. Choose a rule */}
          <Card>
            <CardHeader
              title="Choose a rule"
              subtitle="Pick a strategy rule to follow. Each rule decides what to hold using only prices up to that session's close."
            />
            <div role="radiogroup" aria-label="Choose a rule" className="grid gap-3 sm:grid-cols-2">
              {templates.templates.map((t) => {
                const selected = t.id === selectedTemplate.id;
                return (
                  <button
                    key={t.id}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => handleSelectTemplate(t)}
                    className={cx(
                      "flex flex-col items-start rounded-2xl border bg-surface p-4 text-left transition-colors",
                      selected ? "border-brand ring-3 ring-brand/15" : "border-line hover:border-line-strong",
                    )}
                  >
                    <span className="font-semibold text-ink">{t.name}</span>
                    <span className="mt-1 text-[13px] text-ink-3">{t.summary}</span>
                  </button>
                );
              })}
            </div>
          </Card>

          {/* 2. Settings */}
          {selectedTemplate.params.length > 0 && (
            <Card>
              <CardHeader title="Settings" subtitle="The settings this rule follows on every session." />
              <div className="grid gap-5 sm:grid-cols-2">
                {selectedTemplate.params.map((p) =>
                  p.kind === "bool" ? (
                    <div key={p.name} className="flex flex-col justify-end gap-1.5">
                      <Switch
                        checked={Boolean(params[p.name] ?? p.default)}
                        onChange={(v) => setParams({ ...params, [p.name]: v })}
                        label={p.label}
                      />
                      <p className="text-[12.5px] text-ink-3">{p.help}</p>
                    </div>
                  ) : (
                    <Field key={p.name} label={p.label} htmlFor={`p-${p.name}`} hint={`${p.help} ${p.min}–${p.max}.`}>
                      <Input
                        id={`p-${p.name}`}
                        type="number"
                        min={p.min}
                        max={p.max}
                        value={String(params[p.name] ?? p.default)}
                        onChange={(e) => setParams({ ...params, [p.name]: Math.round(Number(e.target.value)) })}
                      />
                    </Field>
                  ),
                )}
              </div>
            </Card>
          )}

          {/* 3. What should it trade? */}
          <Card>
            <CardHeader title="What should it trade?" />
            {canBothScopes && (
              <div className="mb-4">
                <Segmented
                  label="What should it trade?"
                  value={scope}
                  onChange={setScope}
                  options={[
                    { value: "stocks", label: "Stocks you pick" },
                    { value: "universe", label: "A whole list" },
                  ]}
                />
              </div>
            )}
            {scope === "stocks" ? (
              <div className="space-y-3">
                <SymbolSearch
                  onPick={(s) => setSymbols((list) => (list.includes(s) || list.length >= 20 ? list : [...list, s]))}
                  exclude={symbols}
                />
                <SymbolChips symbols={symbols} onRemove={(s) => setSymbols((list) => list.filter((x) => x !== s))} />
                <p className="text-[12.5px] text-ink-3">Choose 1 to 20 stocks or ETFs. The money is split equally between them.</p>
              </div>
            ) : (
              <Field
                label="A whole list"
                htmlFor="universe"
                hint="QuantOS runs the rule across this list at every session's close."
              >
                <Select id="universe" value={universe} onChange={(e) => setUniverse(e.target.value)}>
                  {templates.universes.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.label}
                    </option>
                  ))}
                </Select>
              </Field>
            )}
          </Card>

          {/* 4. Money and name */}
          <Card>
            <CardHeader title="Money and name" />
            <div className="grid gap-5 sm:grid-cols-2">
              <Field
                label="Starting capital"
                htmlFor="capital"
                hint={`${inr(Number(capital) || 0, 0)} · minimum ${inr(MIN_CAPITAL, 0)}`}
              >
                <Input
                  id="capital"
                  prefix="₹"
                  inputMode="numeric"
                  value={capital}
                  onChange={(e) => setCapital(e.target.value.replace(/[^\d.]/g, ""))}
                />
              </Field>
              <Field
                label={
                  <span className="inline-flex items-center gap-1">
                    Slippage{" "}
                    <HelpTip text="Extra price paid on every fill because you cannot always trade at the exact open. 5 basis points = 0.05%." />
                  </span>
                }
                htmlFor="slippage"
                hint="5 basis points = 0.05%"
              >
                <Input
                  id="slippage"
                  suffix="bps"
                  inputMode="numeric"
                  value={slippage}
                  onChange={(e) => setSlippage(e.target.value.replace(/\D/g, ""))}
                />
              </Field>
              <div className="sm:col-span-2">
                <Field label="Book name" htmlFor="name" hint="Up to 60 characters to help you recognise this book later.">
                  <Input
                    id="name"
                    maxLength={60}
                    value={name}
                    onChange={(e) => {
                      setName(e.target.value.slice(0, 60));
                      setNameTouched(true);
                    }}
                  />
                </Field>
              </div>
            </div>
          </Card>
        </div>

        {/* Sticky side card */}
        <div className="space-y-5">
          <Card className="lg:sticky lg:top-6">
            <CardHeader title="What will happen" />
            <ul className="space-y-2.5 text-[13.5px] text-ink-2">
              <li className="flex gap-2">
                <span className="text-ink-3">•</span>
                <span>It starts at the latest session in your market data.</span>
              </li>
              <li className="flex gap-2">
                <span className="text-ink-3">•</span>
                <span>Its first decision uses only prices up to that close.</span>
              </li>
              <li className="flex gap-2">
                <span className="text-ink-3">•</span>
                <span>Orders fill at the next session's real open with exact NSE charges and slippage.</span>
              </li>
              <li className="flex gap-2">
                <span className="text-ink-3">•</span>
                <span>It moves forward as new prices arrive. QuantOS fetches them itself after each market close (you can turn that off in Settings).</span>
              </li>
              <li className="flex gap-2">
                <span className="text-ink-3">•</span>
                <span>You can stop it but never delete it, because deleting failures would flatter the rest.</span>
              </li>
              <li className="flex gap-2">
                <span className="text-ink-3">•</span>
                <span>A few weeks of results cannot show skill.</span>
              </li>
            </ul>

            <div className="mt-6 space-y-3">
              {startBook.isError && (
                <Callout tone="danger">
                  {errorMessage(startBook.error)}
                </Callout>
              )}
              {blocking && <p className="text-[13px] text-ink-3">{blocking}</p>}
              <Button
                size="lg"
                className="w-full"
                icon={<Play className="size-4" aria-hidden />}
                disabled={Boolean(blocking)}
                loading={startBook.isPending}
                onClick={submit}
              >
                {startBook.isPending ? "Starting paper book…" : "Start paper book"}
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
