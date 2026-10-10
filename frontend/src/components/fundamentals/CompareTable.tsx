import { Link } from "react-router";
import { date } from "../../lib/format";
import type { CompareAnswer, CompareColumn, CompareRow, CompareValue } from "../../lib/fundamentalsTypes";
import { friendlyDates } from "../../lib/plainDates";
import { Badge } from "../ui";
import { useNarrow } from "../portfolio/useNarrow";
import { DataChip } from "./CompanyChips";
import { basisWords, figureText } from "./format";

function Value({ rowKey, value }: { rowKey: string; value: CompareValue | undefined }) {
  if (!value) return <span className="text-ink-3">—</span>;
  if (!value.available) {
    return (
      <span className="block text-[13px] text-ink-2">
        <span className="font-medium text-ink">Not available.</span> {value.reason}
      </span>
    );
  }
  return (
    <span className="block">
      <span className="num font-medium text-ink">{figureText({ key: rowKey, ...value })}</span>
      {value.approximate && <Badge className="ml-1.5">Approximate</Badge>}
      {value.period && <span className="block text-[12px] text-ink-3">{friendlyDates(value.period)}</span>}
    </span>
  );
}

function CompanyHead({ company }: { company: CompareColumn }) {
  const basis = basisWords(company.basis);
  return (
    <div className="space-y-1">
      <Link to={`/stock/${company.symbol}`} className="text-[14px] font-semibold text-ink hover:underline">
        {company.symbol}
      </Link>
      {company.company_name && <p className="text-[12.5px] font-normal text-ink-2">{company.company_name}</p>}
      <DataChip status={company.data_status} />
      <p className="text-[12px] font-normal text-ink-3">
        {company.latest_quarter ? `Latest quarter ended ${date(company.latest_quarter)}` : "No quarter held"}
        {basis ? ` · ${basis}` : ""}
      </p>
    </div>
  );
}

function HeadRow({ companies }: { companies: CompareColumn[] }) {
  return (
    <tr className="border-b border-line align-top">
      <th scope="col" className="py-2 pr-4 text-left text-[12.5px] font-semibold text-ink-3">
        Figure
      </th>
      {companies.map((c) => (
        <th key={c.symbol} scope="col" className="px-3 py-2 text-left align-top">
          <CompanyHead company={c} />
        </th>
      ))}
    </tr>
  );
}

function BodyRow({ row, companies }: { row: CompareRow; companies: CompareColumn[] }) {
  return (
    <tr className="align-top">
      <th scope="row" className="py-3 pr-4 text-left text-[13px] font-medium text-ink-2">
        {row.label}
      </th>
      {companies.map((c) => (
        <td key={c.symbol} className="px-3 py-3">
          <Value rowKey={row.key} value={row.values[c.symbol]} />
        </td>
      ))}
    </tr>
  );
}

function Wide({ rows, companies }: { rows: CompareRow[]; companies: CompareColumn[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" aria-label="Companies side by side">
        <thead>
          <HeadRow companies={companies} />
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((row) => (
            <BodyRow key={row.key} row={row} companies={companies} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StackedRow({ row, companies }: { row: CompareRow; companies: CompareColumn[] }) {
  return (
    <section aria-label={row.label} className="space-y-1.5 border-t border-line pt-3">
      <h4 className="text-[13px] font-medium text-ink-2">{row.label}</h4>
      <dl className="space-y-1.5">
        {companies.map((c) => (
          <div key={c.symbol} className="flex items-baseline justify-between gap-3">
            <dt className="text-[13px] text-ink-3">{c.symbol}</dt>
            <dd className="min-w-0 text-right">
              <Value rowKey={row.key} value={row.values[c.symbol]} />
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Stacked({ rows, companies }: { rows: CompareRow[]; companies: CompareColumn[] }) {
  return (
    <div className="space-y-4">
      <ul aria-label="The companies" className="space-y-3">
        {companies.map((c) => (
          <li key={c.symbol} className="rounded-xl border border-line p-3">
            <CompanyHead company={c} />
          </li>
        ))}
      </ul>
      {rows.map((row) => (
        <StackedRow key={row.key} row={row} companies={companies} />
      ))}
    </div>
  );
}

/** The companies that could be put in the same lines, side by side (one under another on a narrow screen). */
export function CompareTable({ answer }: { answer: CompareAnswer }) {
  const narrow = useNarrow();
  const companies = answer.companies.filter((c) => c.included);
  if (!answer.comparable || companies.length === 0 || answer.rows.length === 0) return null;
  return narrow ? (
    <Stacked rows={answer.rows} companies={companies} />
  ) : (
    <Wide rows={answer.rows} companies={companies} />
  );
}
