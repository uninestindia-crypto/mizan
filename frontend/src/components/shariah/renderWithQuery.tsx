import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";

const QUIET = { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } };

/** Renders a screen with a fresh query client that never retries and keeps nothing between tests. */
export function renderWithQuery(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: QUIET });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return render(ui, { wrapper });
}
