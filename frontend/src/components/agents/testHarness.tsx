import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, useLocation } from "react-router";
import { vi } from "vitest";
import { api } from "../../lib/api";

// Shared by the Agents and live price tests. They replace the engine with a table of answers and look at what was asked.

type Answer = unknown | ((body: unknown) => unknown);

/** Answers each "METHOD /path" from the table (a function gets the body and may throw). Anything else is refused. */
export function routeApi(table: Record<string, Answer>): void {
  vi.mocked(api).mockImplementation((async (path: string, method = "GET", body?: unknown) => {
    const answer = table[`${method} ${path}`];
    if (answer === undefined) throw new Error(`No answer set for ${method} ${path}`);
    return typeof answer === "function" ? (answer as (b: unknown) => unknown)(body) : answer;
  }) as never);
}

export function callsTo(method: string, path: string): unknown[] {
  return vi
    .mocked(api)
    .mock.calls.filter(([p, m = "GET"]) => p === path && m === method)
    .map(([, , body]) => body);
}

export function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function Where() {
  return <span data-testid="where">{useLocation().pathname}</span>;
}

const QUIET = { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } };

export function newClient(): QueryClient {
  return new QueryClient({ defaultOptions: QUIET });
}

export function renderApp(ui: ReactElement, client: QueryClient = newClient(), path = "/start") {
  const tree = (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        {ui}
        <Where />
      </MemoryRouter>
    </QueryClientProvider>
  );
  return { client, ...render(tree) };
}
