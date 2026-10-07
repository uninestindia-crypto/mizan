import { describe, expect, it } from "vitest";

// Every word on the Shariah screen is for a person who has never seen code, and none of it may promise more than the
// app does. This reads the source of the screen's files, skipping comments and imports, and fails when a line says
// something the app cannot stand behind (GOAL.md tripwire 4) or speaks the way a developer would.
const files = import.meta.glob(
  [
    "./*.{ts,tsx}",
    "../../pages/Shariah.tsx",
    "!./**/*.test.*",
    "!./shariahFixtures.ts",
    "!./useShariahAudit.ts",
  ],
  { query: "?raw", import: "default", eager: true },
) as Record<string, string>;

const FORBIDDEN: [string, RegExp][] = [
  ["a promise the app does not keep", /1-Click|Pre-audited|Shipped|100% Shariah|Assumed (CAGR|Sharpe)|Live &/i],
  ["an invitation to trade", /\b(buy|sell|invest now)\b/i],
  ["a claim of an edge", /\b(alpha|outperform\w*|beat the market|guaranteed|proven)\b/i],
  ["a code term", /\b(sha-?256|hash|JSON|backend|terminal|token)s?\b|\bAPI\b/i],
];

// The warning that tells a person not to trade on a verdict is the one place these words belong.
const ALLOWED = /do not buy, sell or avoid/i;

function userFacingLines(source: string): string[] {
  return source.split("\n").filter((line) => {
    const t = line.trim();
    return t && !t.startsWith("//") && !t.startsWith("*") && !t.startsWith("/*") && !t.startsWith("import ");
  });
}

const SCREEN_FILES = Object.entries(files).map(([path, source]) => ({ path, lines: userFacingLines(source) }));

describe("the Shariah screen's words", () => {
  it("reads the screen's files", () => {
    expect(SCREEN_FILES.length).toBeGreaterThan(15);
  });

  it.each(FORBIDDEN)("never says %s", (_name, pattern) => {
    const found = SCREEN_FILES.flatMap(({ path, lines }) =>
      lines.filter((line) => pattern.exec(line) && !ALLOWED.exec(line)).map((line) => `${path}: ${line.trim()}`),
    );
    expect(found).toEqual([]);
  });

  it("keeps the warning that a verdict is not a reason to trade", () => {
    const page = SCREEN_FILES.find(({ path }) => path.endsWith("pages/Shariah.tsx"));
    expect((page?.lines ?? []).join(" ")).toMatch(/Do not buy, sell or avoid a share/);
  });
});
