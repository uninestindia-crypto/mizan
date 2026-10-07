import { UsersRound } from "lucide-react";
import { openSecondOpinion } from "../../lib/copilot";
import { Button } from "../ui";

/** Opens the Second opinion window for a stock. Used beside a stock's heading. */
export function SecondOpinionButton({ symbol, pickNote }: { symbol: string; pickNote?: string }) {
  const icon = <UsersRound className="size-4" aria-hidden />;
  return (
    <Button variant="secondary" icon={icon} onClick={() => openSecondOpinion(symbol, pickNote)}>
      Get a second opinion
    </Button>
  );
}
