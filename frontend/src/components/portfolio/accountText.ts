import { inrCompact } from "../../lib/format";
import type { AccountLine } from "../../lib/types";
import type { AccountChoice } from "./accountQueries";

// The plain words used for accounts on the Portfolio screens, kept in one place so every screen says them alike.

export const ALL_ACCOUNTS = "All accounts";

/** "Asha · Demat account · Zerodha" (the broker only when there is one). */
export function describeAccount(account: Pick<AccountLine, "owner" | "kind" | "broker">): string {
  return [account.owner, account.kind, account.broker].filter(Boolean).join(" · ");
}

/** How many holdings an account has. A holding is one purchase of one stock. */
export function holdingsText(count: number): string {
  if (count === 0) return "No holdings yet";
  return count === 1 ? "1 holding" : `${count} holdings`;
}

export interface SwitchEntry {
  key: AccountChoice;
  name: string;
  /** The kind of account and what it is worth, small, under the name. */
  detail: string;
  /** Everything the entry can be found by when searching. */
  haystack: string;
}

export function switchEntries(accounts: readonly AccountLine[]): SwitchEntry[] {
  const total = accounts.reduce((sum, a) => sum + a.value, 0);
  const all: SwitchEntry = {
    key: "all",
    name: ALL_ACCOUNTS,
    detail: inrCompact(total),
    haystack: ALL_ACCOUNTS.toLowerCase(),
  };
  const each = accounts.map((a) => ({
    key: String(a.id),
    name: a.name,
    detail: `${a.kind} · ${inrCompact(a.value)}`,
    haystack: `${a.name} ${describeAccount(a)}`.toLowerCase(),
  }));
  return [all, ...each];
}

/** Which account (if any) the choice names. */
export function accountFor(accounts: readonly AccountLine[], choice: AccountChoice): AccountLine | undefined {
  return accounts.find((a) => String(a.id) === choice);
}
