import { describe, expect, it } from "vitest";

// Every word on the Agents screen and the live price chips is for a person who has never seen code. This reads their
// source, skipping comments and imports, and fails when a line speaks to a trader the way a developer would, or tells
// anyone to trade.
const files = import.meta.glob(
  [
    "../components/agents/*.{ts,tsx}",
    "../components/live/*.{ts,tsx}",
    "../pages/Agents.tsx",
    "./agents.ts",
    "./live.ts",
    "!**/*.test.*",
    "!**/testHarness.tsx",
  ],
  { query: "?raw", import: "default", eager: true },
) as Record<string, string>;

const FORBIDDEN: [string, RegExp][] = [
  ["a trade instruction", /\b(buy|sell|invest now)\b/i],
  ["a terminal", /\bterminal\b/i],
  ["a command", /\bcommands?\b/i],
  ["an environment variable", /\benvironment variables?\b/i],
  ["a settings file", /\.env\b/i],
  ["JSON", /\bJSON\b/],
  ["an API", /\bAPI\b/],
  ["a backend", /\bbackend\b/i],
  ["a token", /\btokens?\b/i],
];

const SKIPPED_STARTS = ["//", "*", "/*", "import "];

function codeLines(source: string): string[] {
  const lines = source.split("\n").map((line) => line.trim());
  return lines.filter((line) => line !== "" && !SKIPPED_STARTS.some((start) => line.startsWith(start)));
}

describe("the words on the Agents screen and the live prices", () => {
  it("reads the screens' own source", () => {
    expect(Object.keys(files).length).toBeGreaterThan(12);
  });

  it("says nothing a developer would say to a developer, and never tells anyone to trade", () => {
    const found: string[] = [];
    for (const [file, source] of Object.entries(files)) {
      for (const line of codeLines(source)) {
        for (const [what, pattern] of FORBIDDEN) if (pattern.test(line)) found.push(`${file}: ${what}: ${line}`);
      }
    }
    expect(found).toEqual([]);
  });
});
