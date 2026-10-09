import type { ChangeEvent, FormEvent } from "react";
import type { ScreenParams } from "../../lib/fundamentalsTypes";
import { Button, Field, Input, Select } from "../ui";
import {
  EMPTY_PARAMS,
  FILTER_FIELDS,
  type FilterField,
  ORDER_CHOICES,
  SECTOR_FIELD,
  SORT_CHOICES,
} from "./screenWords";

interface FormProps {
  draft: ScreenParams;
  onChange: (next: ScreenParams) => void;
  onRun: () => void;
  running: boolean;
}

/** A number box accepts digits, a minus sign and a decimal point, and nothing else. */
const numeric = (text: string): string => text.replace(/[^\d.-]/g, "");

interface NumberFieldProps {
  field: FilterField;
  draft: ScreenParams;
  onChange: FormProps["onChange"];
}

function NumberField({ field, draft, onChange }: NumberFieldProps) {
  const id = `f-${field.name}`;
  const change = (e: ChangeEvent<HTMLInputElement>) => onChange({ ...draft, [field.name]: numeric(e.target.value) });
  return (
    <Field label={field.label} htmlFor={id} hint={field.hint}>
      <Input id={id} inputMode="decimal" suffix={field.unit} value={draft[field.name]} onChange={change} />
    </Field>
  );
}

function SortFields({ draft, onChange }: Pick<FormProps, "draft" | "onChange">) {
  return (
    <div className="grid gap-4 sm:grid-cols-[2fr_1fr_1fr]">
      <Field label="Sort by" htmlFor="f-sort">
        <Select id="f-sort" value={draft.sort} onChange={(e) => onChange({ ...draft, sort: e.target.value })}>
          {SORT_CHOICES.map((choice) => (
            <option key={choice.value} value={choice.value}>
              {choice.label}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Order" htmlFor="f-order">
        <Select
          id="f-order"
          value={draft.order}
          onChange={(e) => onChange({ ...draft, order: e.target.value === "desc" ? "desc" : "asc" })}
        >
          {ORDER_CHOICES.map((choice) => (
            <option key={choice.value} value={choice.value}>
              {choice.label}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Show up to" htmlFor="f-limit" hint="From 1 to 100 companies.">
        <Input
          id="f-limit"
          inputMode="numeric"
          value={draft.limit}
          onChange={(e) => onChange({ ...draft, limit: e.target.value.replace(/\D/g, "") })}
        />
      </Field>
    </div>
  );
}

/** The filters a person chooses. An empty box leaves that filter out; nothing is chosen for them. */
export function ScreenForm(props: FormProps) {
  const { draft, onChange } = props;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    props.onRun();
  };
  return (
    <form onSubmit={submit} className="space-y-5" aria-label="Choose your filters">
      <p className="text-[13px] text-ink-2">
        Leave a box empty to leave that filter out. QuantOS applies only the filters you fill in.
      </p>
      <div className="grid gap-4 lg:grid-cols-2 lg:[&_label]:min-h-10">
        {FILTER_FIELDS.map((field) => (
          <NumberField key={field.name} field={field} draft={draft} onChange={onChange} />
        ))}
        <Field label={SECTOR_FIELD.label} htmlFor="f-sector" hint={SECTOR_FIELD.hint}>
          <Input id="f-sector" value={draft.sector} onChange={(e) => onChange({ ...draft, sector: e.target.value })} />
        </Field>
      </div>
      <SortFields draft={draft} onChange={onChange} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" loading={props.running}>
          Show companies
        </Button>
        <Button type="button" variant="secondary" onClick={() => onChange(EMPTY_PARAMS)}>
          Clear the filters
        </Button>
      </div>
    </form>
  );
}
