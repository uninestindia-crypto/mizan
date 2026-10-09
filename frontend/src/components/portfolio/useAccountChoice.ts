import { useCallback, useEffect } from "react";
import { useSearchParams } from "react-router";
import type { AccountChoice } from "./accountQueries";

// Which account the Portfolio shows. The address (?account=) decides, so a link or a reload lands on the same view.
// With no account in the address, the last choice on this computer is used. The page works the same if the browser
// blocks storage.

const STORE = "quantos.portfolio.account";
const PARAM = "account";

function readRemembered(): string | null {
  try {
    return localStorage.getItem(STORE);
  } catch {
    return null;
  }
}

function remember(choice: AccountChoice): void {
  try {
    localStorage.setItem(STORE, choice);
  } catch {
    /* the choice lasts for this visit only */
  }
}

export interface AccountChoiceState {
  choice: AccountChoice;
  choose: (next: AccountChoice) => void;
}

export function useAccountChoice(): AccountChoiceState {
  const [params, setParams] = useSearchParams();
  const fromAddress = params.get(PARAM);
  const choice = fromAddress || readRemembered() || "all";

  const choose = useCallback(
    (next: AccountChoice) => {
      remember(next);
      setParams(
        (before) => {
          const after = new URLSearchParams(before);
          after.set(PARAM, next);
          return after;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  // A remembered choice becomes part of the address, so the link in the bar is the link to this view.
  useEffect(() => {
    if (!fromAddress && choice !== "all") choose(choice);
  }, [fromAddress, choice, choose]);

  return { choice, choose };
}
