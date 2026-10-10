import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { keys } from "../../lib/queries";
import type { Account, AccountDeleted, AccountInput, AccountList, Portfolio } from "../../lib/types";

// The portfolio as seen by account, and the person's accounts. "All accounts" asks the plain portfolio address, so it
// shares its answer with the Home page; one account asks for that account alone.

export type AccountChoice = "all" | string;

export const ACCOUNTS_KEY = ["accounts"] as const;

export function portfolioUrl(choice: AccountChoice): string {
  return choice === "all" ? "/api/v2/portfolio" : `/api/v2/portfolio?account=${encodeURIComponent(choice)}`;
}

export function usePortfolioFor(choice: AccountChoice) {
  const queryKey = choice === "all" ? keys.portfolio : ([...keys.portfolio, "account", choice] as const);
  // While another account loads, the one on screen stays, so the switcher keeps the person's place (and focus).
  return useQuery({ queryKey, queryFn: () => api<Portfolio>(portfolioUrl(choice)), placeholderData: keepPreviousData });
}

export function useAccounts(enabled = true) {
  return useQuery({ queryKey: ACCOUNTS_KEY, queryFn: () => api<AccountList>("/api/v2/accounts"), enabled });
}

function useRefreshAfterChange() {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: ACCOUNTS_KEY });
    void qc.invalidateQueries({ queryKey: keys.portfolio });
  };
}

/** Adds an account, or changes the one with `id`. */
export function useSaveAccount() {
  const refresh = useRefreshAfterChange();
  return useMutation({
    mutationFn: ({ id, input }: { id?: number; input: AccountInput }) =>
      id === undefined
        ? api<Account>("/api/v2/accounts", "POST", input)
        : api<Account>(`/api/v2/accounts/${id}`, "PUT", input),
    onSuccess: refresh,
  });
}

/** Deletes an account. An account that holds stocks needs `moveTo`, the account they go to. */
export function useDeleteAccount() {
  const refresh = useRefreshAfterChange();
  return useMutation({
    mutationFn: ({ id, moveTo }: { id: number; moveTo?: number }) =>
      api<AccountDeleted>(`/api/v2/accounts/${id}${moveTo === undefined ? "" : `?move_to=${moveTo}`}`, "DELETE"),
    onSuccess: refresh,
  });
}
