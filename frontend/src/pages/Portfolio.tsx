import { Plus, Users } from "lucide-react";
import { useState } from "react";
import { DataGate } from "../components/common";
import { type LotDraft, HoldingFormDialog, draftFromRow } from "../components/portfolio/HoldingFormDialog";
import { ManageAccountsDialog } from "../components/portfolio/ManageAccountsDialog";
import { PortfolioBody } from "../components/portfolio/PortfolioBody";
import { useAccountChoice } from "../components/portfolio/useAccountChoice";
import { Button, PageHeader } from "../components/ui";
import type { PortfolioRow } from "../lib/types";

const SUBTITLE =
  "What you own, valued at the latest close, with the charges you would pay to sell and a fair comparison with NIFTY.";

export default function Portfolio() {
  const { choice, choose } = useAccountChoice();
  const [form, setForm] = useState<{ open: boolean; initial?: Partial<LotDraft> }>({ open: false });
  const [managing, setManaging] = useState(false);
  const add = () => setForm({ open: true });
  const manage = () => setManaging(true);
  const edit = (row: PortfolioRow) => setForm({ open: true, initial: draftFromRow(row) });
  return (
    <>
      <PageHeader
        title="Portfolio"
        subtitle={SUBTITLE}
        actions={
          <>
            <Button variant="secondary" icon={<Users className="size-4" aria-hidden />} onClick={manage}>
              Manage accounts
            </Button>
            <Button icon={<Plus className="size-4" aria-hidden />} onClick={add}>
              Add holding
            </Button>
          </>
        }
      />
      <DataGate>
        <PortfolioBody choice={choice} choose={choose} onEdit={edit} onAdd={add} />
      </DataGate>
      <HoldingFormDialog
        open={form.open}
        onOpenChange={(open) => setForm({ open })}
        initial={form.initial}
        viewing={choice}
      />
      <ManageAccountsDialog
        open={managing}
        onOpenChange={setManaging}
        onDeleted={(id) => choice === String(id) && choose("all")}
      />
    </>
  );
}
