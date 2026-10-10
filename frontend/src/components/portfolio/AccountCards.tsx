import type { AccountLine } from "../../lib/types";
import { inrCompact, inrSigned, pct } from "../../lib/format";
import { Delta } from "../ui";
import type { AccountChoice } from "./accountQueries";
import { describeAccount, holdingsText } from "./accountText";

/** One card per account across everything held. Pressing a card shows that account alone. */
interface CardsProps {
  accounts: readonly AccountLine[];
  onChoose: (choice: AccountChoice) => void;
}

export function AccountCards({ accounts, onChoose }: CardsProps) {
  return (
    <ul aria-label="Your accounts" className={LIST}>
      {accounts.map((account) => (
        <li key={account.id} className="w-64 shrink-0 snap-start sm:w-auto sm:min-w-0">
          <AccountCard account={account} onChoose={() => onChoose(String(account.id))} />
        </li>
      ))}
    </ul>
  );
}

// On a phone the cards sit in one row that slides sideways, so many accounts do not push the figures far down.
const LIST =
  "-mx-6 flex snap-x gap-3 overflow-x-auto px-6 pb-1 " +
  "sm:mx-0 sm:grid sm:grid-cols-[repeat(auto-fill,minmax(15rem,1fr))] sm:overflow-visible sm:px-0 sm:pb-0";

const CARD =
  "flex h-full w-full flex-col gap-2.5 rounded-[var(--radius-card)] border border-line bg-surface p-3.5 text-left " +
  "shadow-[var(--shadow-card)] transition-colors hover:border-line-strong hover:bg-surface-2/60";

function AccountCard({ account, onChoose }: { account: AccountLine; onChoose: () => void }) {
  const empty = account.holdings === 0;
  return (
    <button type="button" aria-label={`Show only ${account.name}`} onClick={onChoose} className={CARD}>
      <span className="min-w-0">
        <span className="block truncate text-[15px] font-semibold text-ink">{account.name}</span>
        <span className="block truncate text-[12.5px] text-ink-3">{describeAccount(account)}</span>
      </span>
      <span className="num text-lg font-semibold tracking-tight text-ink">{inrCompact(account.value)}</span>
      <span className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 text-[12.5px]">
        {empty ? (
          <span className="text-ink-3">{holdingsText(0)}</span>
        ) : (
          <span>
            <Delta value={account.pnl} strong>
              {inrSigned(account.pnl)}
            </Delta>
            <Delta value={account.pnl} className="ml-1.5">
              {pct(account.pnl_pct)}
            </Delta>
          </span>
        )}
        {!empty && <span className="text-ink-3">{holdingsText(account.holdings)}</span>}
      </span>
      <Share weight={account.weight} />
    </button>
  );
}

function Share({ weight }: { weight: number }) {
  const percent = Math.round(Math.max(0, Math.min(1, weight)) * 100);
  return (
    <span className="block">
      <span className="mb-1 block text-[12px] text-ink-3">{percent}% of everything you hold</span>
      <span className="block h-1.5 overflow-hidden rounded-full bg-surface-3" aria-hidden>
        <span className="block h-full rounded-full bg-brand" style={{ width: `${percent}%` }} />
      </span>
    </span>
  );
}
