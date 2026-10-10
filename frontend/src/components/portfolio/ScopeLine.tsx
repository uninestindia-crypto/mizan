import type { AccountLine } from "../../lib/types";
import type { AccountChoice } from "./accountQueries";
import { ALL_ACCOUNTS, accountFor, describeAccount } from "./accountText";

/**
 * Whose holdings these are: "Showing: All accounts" or "Showing: Asha's Zerodha" with the owner, kind and broker.
 * It follows the choice, not the answer on screen, so it is right the moment another account is picked.
 */
export function ScopeLine({ choice, accounts }: { choice: AccountChoice; accounts: readonly AccountLine[] }) {
  const account = accountFor(accounts, choice);
  const detail = account ? describeAccount(account) : `${accounts.length} accounts`;
  return (
    <p className="text-sm text-ink-2" data-testid="portfolio-scope">
      Showing: <strong className="font-semibold text-ink">{account?.name ?? ALL_ACCOUNTS}</strong>
      <span className="text-ink-3"> · {detail}</span>
    </p>
  );
}
