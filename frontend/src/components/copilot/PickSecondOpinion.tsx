import { UsersRound } from "lucide-react";
import { openSecondOpinion } from "../../lib/copilot";
import { Button } from "../ui";

/** A small button beside a stock the platform's own rules chose: opens the Second opinion window with the pick note. */
export function PickSecondOpinion({ symbol, note }: { symbol: string; note: string }) {
  return (
    <Button
      variant="secondary"
      size="sm"
      icon={<UsersRound className="size-3.5" aria-hidden />}
      aria-label={`Get a second opinion on ${symbol}`}
      onClick={() => openSecondOpinion(symbol, note)}
    >
      Second opinion
    </Button>
  );
}
