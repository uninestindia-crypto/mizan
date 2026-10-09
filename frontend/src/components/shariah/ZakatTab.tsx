import { useState } from "react";
import { useZakatCalculate } from "../../lib/shariah";
import { Button, Card, CardHeader, Field, Input, cx } from "../ui";
import { ZakatResult } from "./ZakatResult";

const clean = (value: string) => value.replace(/[^\d.]/g, "");

const METHODS = [
  { id: "TRADER_QUICK", title: "Active Trader (100%)", body: "Full portfolio Net Asset Value (Lunar year)" },
  {
    id: "INVESTOR_NET_WORKING_CAPITAL",
    title: "Long-term Investor",
    body: "Zakatable net working assets only (~25-30%)",
  },
];

const CHOICE = "rounded-[var(--radius-control)] border p-3.5 text-left transition-colors";
const CHOSEN = "border-brand bg-brand-soft ring-1 ring-brand text-ink";
const OTHER = "border-line bg-surface text-ink-2 hover:border-line-strong hover:bg-surface-2";

function MethodChoice({ chosen, onPick }: { chosen: string; onPick: (id: string) => void }) {
  return (
    <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
      {METHODS.map((m) => (
        <button
          key={m.id}
          type="button"
          onClick={() => onPick(m.id)}
          className={cx(CHOICE, chosen === m.id ? CHOSEN : OTHER)}
        >
          <div className="text-sm font-semibold text-ink">{m.title}</div>
          <div className="mt-0.5 text-xs text-ink-3">{m.body}</div>
        </button>
      ))}
    </div>
  );
}

export function ZakatTab() {
  const [value, setValue] = useState("500000");
  const [method, setMethod] = useState("TRADER_QUICK");
  const calc = useZakatCalculate();
  const calculate = () => calc.mutate({ portfolio_value: parseFloat(value) || 0, calculation_method: method });

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card>
        <CardHeader
          title="Equity Zakat Calculator"
          subtitle="Calibrated to the Indian Silver Nisab standard (₹53,550.00) with AAOIFI standards."
        />
        <div className="space-y-4">
          <Field label="Portfolio Value (INR)" htmlFor="z-val">
            <Input
              id="z-val"
              prefix="₹"
              inputMode="decimal"
              value={value}
              onChange={(e) => setValue(clean(e.target.value))}
            />
          </Field>
          <Field label="Calculation Method" htmlFor="z-method">
            <MethodChoice chosen={method} onPick={setMethod} />
          </Field>
          <Button size="md" variant="primary" loading={calc.isPending} onClick={calculate} className="mt-2 w-full">
            Calculate Zakat Due
          </Button>
        </div>
      </Card>
      <ZakatResult data={calc.data} />
    </div>
  );
}
