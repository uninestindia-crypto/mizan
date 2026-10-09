import { useState } from "react";
import { ApiError, errorMessage } from "../../lib/api";
import type { Portfolio, PortfolioRow } from "../../lib/types";
import { Illustration } from "../common";
import { Button, Callout, Card, cx, EmptyState, Skeleton } from "../ui";
import { AccountCards } from "./AccountCards";
import { AccountSwitcher } from "./AccountSwitcher";
import { type AccountChoice, usePortfolioFor } from "./accountQueries";
import { ConcentrationWarnings, PortfolioTotals } from "./PortfolioTotals";
import { PortfolioTabs, type TabContext } from "./PortfolioTabs";
import { RemoveLotDialog } from "./RemoveLotDialog";
import { ScopeLine } from "./ScopeLine";
import { PORTFOLIO_TABS } from "./tabRegistry";

const EMPTY_ALL =
  "Add your holdings to see your real gain after costs, how concentrated you are, and whether you are beating NIFTY.";

export interface BodyProps {
  choice: AccountChoice;
  choose: (choice: AccountChoice) => void;
  onEdit: (row: PortfolioRow) => void;
  onAdd: () => void;
}

/** Everything under the page heading: which account is in view, the figures, and the holdings. */
export function PortfolioBody({ choice, choose, onEdit, onAdd }: BodyProps) {
  const portfolio = usePortfolioFor(choice);
  const [removing, setRemoving] = useState<PortfolioRow | null>(null);
  if (portfolio.isPending) return <Skeleton className="h-96" />;
  if (portfolio.isError) {
    return <LoadProblem error={portfolio.error} onAll={() => choose("all")} onRetry={portfolio.refetch} />;
  }
  const data = portfolio.data;
  const showAccounts = data.accounts.length > 1;
  const busy = portfolio.isPlaceholderData;
  return (
    <div className="space-y-5">
      {showAccounts && <AccountsHeader data={data} choice={choice} choose={choose} />}
      <div aria-busy={busy} className={cx("space-y-5 transition-opacity", busy && "opacity-60")}>
        <Holdings
          data={data}
          context={{ data, choice, showAccounts, onEdit, onRemove: setRemoving }}
          onAdd={onAdd}
        />
      </div>
      <RemoveLotDialog row={removing} onClose={() => setRemoving(null)} />
    </div>
  );
}

function Holdings({ data, context, onAdd }: { data: Portfolio; context: TabContext; onAdd: () => void }) {
  if (data.holdings.length === 0 || !data.totals) {
    return <NothingHeld scope={data.scope.account} name={data.scope.name} onAdd={onAdd} />;
  }
  return (
    <>
      <PortfolioTotals totals={data.totals} nifty={data.nifty} />
      <ConcentrationWarnings warnings={data.warnings} />
      <PortfolioTabs tabs={PORTFOLIO_TABS} context={context} />
    </>
  );
}

interface HeaderProps {
  data: Portfolio;
  choice: AccountChoice;
  choose: BodyProps["choose"];
}

function AccountsHeader({ data, choice, choose }: HeaderProps) {
  return (
    <div className="space-y-4">
      <ScopeLine choice={choice} accounts={data.accounts} />
      <AccountSwitcher accounts={data.accounts} choice={choice} onChoose={choose} />
      {choice === "all" && <AccountCards accounts={data.accounts} onChoose={choose} />}
    </div>
  );
}

function NothingHeld({ scope, name, onAdd }: { scope: "all" | number; name: string; onAdd: () => void }) {
  const one = scope !== "all";
  return (
    <Card>
      <EmptyState
        art={<Illustration name="empty-portfolio" className="size-44" />}
        title={one ? `Nothing in ${name} yet` : "Track what you own"}
        body={
          one
            ? "No holdings in this account yet. Add your first one."
            : EMPTY_ALL
        }
        action={<Button onClick={onAdd}>Add your first holding</Button>}
      />
    </Card>
  );
}

function LoadProblem(props: { error: unknown; onAll: () => void; onRetry: () => void }) {
  const missing = props.error instanceof ApiError && props.error.code === "ACCOUNT_NOT_FOUND";
  return (
    <Callout
      tone={missing ? "warn" : "danger"}
      title={missing ? undefined : "The portfolio could not be loaded"}
      action={
        <Button variant="secondary" onClick={missing ? props.onAll : props.onRetry}>
          {missing ? "Show all accounts" : "Try again"}
        </Button>
      }
    >
      {errorMessage(props.error)}
    </Callout>
  );
}
