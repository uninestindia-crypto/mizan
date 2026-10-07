// Shared set-up for the Copilot's screen tests: a router, a query client, and a fake engine that answers by route.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, useLocation } from "react-router";
import { vi } from "vitest";
import { api } from "../../lib/api";

function PathProbe() {
  const { pathname } = useLocation();
  return <output data-testid="path">{pathname}</output>;
}

function newClient(): QueryClient {
  const queries = { retry: false, gcTime: 0 };
  return new QueryClient({ defaultOptions: { queries } });
}

export function renderApp(ui: ReactNode, path = "/stock/TCS") {
  const client = newClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        {ui}
        <PathProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

type Route = (body: unknown) => unknown;

/** Answers each call by "METHOD path". A call nobody planned for fails the test loudly. */
export function routeApi(routes: Record<string, Route>) {
  vi.mocked(api).mockImplementation((async (path: string, method: string = "GET", body?: unknown) => {
    const handler = routes[`${method} ${path}`];
    if (!handler) throw new Error(`Unexpected call: ${method} ${path}`);
    return handler(body);
  }) as typeof api);
}

/** Answers every call with one function, for an engine whose paths carry an id or a search. */
export function serveApi(handler: (method: string, path: string, body: unknown) => unknown) {
  vi.mocked(api).mockImplementation((async (path: string, method: string = "GET", body?: unknown) =>
    handler(method, path, body)) as typeof api);
}

export const callsTo = (method: string, path: string) =>
  vi.mocked(api).mock.calls.filter(([p, m = "GET"]) => p === path && m === method);
