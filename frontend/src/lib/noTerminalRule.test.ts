import { describe, expect, it } from "vitest";

/**
 * The No-Terminal Law (AGENTS.md, agent_context/decisions/20261006-no-terminal-law.md): a trader or investor
 * never has to open a terminal, type a command, edit a file, or set an environment variable. This guard fails when
 * user-facing text in the app adds such an instruction.
 *
 * KNOWN_DEBT lists the lines that already broke the rule on 2026-10-06. It may only shrink: fix a line, then lower
 * its number. Never raise a number and never add a file.
 */
const FORBIDDEN: { name: string; pattern: RegExp }[] = [
  { name: "open in a terminal", pattern: /\b(open|run|type|paste)\b[^.\n]{0,40}\b(in|into) (a |the )?(terminal|console|command prompt)\b/i },
  { name: "terminal window", pattern: /\bterminal (window|session)\b/i },
  { name: "command line", pattern: /\bcommand[- ]line\b/i },
  { name: "PowerShell / cmd", pattern: /\bpowershell\b/i },
  { name: "package manager", pattern: /\b(npm|pip|winget) (install|run)\b/i },
  { name: "environment variable", pattern: /\benvironment variables?\b/i },
  { name: "an UPPER_CASE setting name", pattern: /\bQUANTOS_[A-Z0-9_]{3,}\b/ },
  { name: "edit a file", pattern: /\bedit (the |your |a )?(\.env|config|settings) ?(file)?\b/i },
  { name: "run a command", pattern: /\b(run|type|enter) (this|the following|a|your own) command\b/i },
];

// file (relative to src/) -> { rule name: number of lines allowed }
const KNOWN_DEBT: Record<string, Record<string, number>> = {
  // Settings > Orders reminder tells the person to set two settings by name and restart. Needs a form.
  "pages/Settings.tsx": { "an UPPER_CASE setting name": 2 },
};

const files = import.meta.glob(["../**/*.ts", "../**/*.tsx", "!../**/*.test.ts", "!../**/*.test.tsx"], {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

function userFacingLines(source: string): string[] {
  return source
    .split("\n")
    .filter((line) => {
      const t = line.trim();
      return t && !t.startsWith("//") && !t.startsWith("*") && !t.startsWith("/*") && !t.startsWith("import ");
    })
    .map((line) => line.replace(/\s\/\/.*$/, ""));
}

function violations(): Record<string, Record<string, number>> {
  const found: Record<string, Record<string, number>> = {};
  for (const [path, source] of Object.entries(files)) {
    const file = path.replace(/^\.\.\//, "");
    for (const line of userFacingLines(source)) {
      for (const { name, pattern } of FORBIDDEN) {
        if (pattern.test(line)) {
          found[file] ??= {};
          found[file][name] = (found[file][name] ?? 0) + 1;
        }
      }
    }
  }
  return found;
}

describe("No-Terminal Law", () => {
  it("scans the app's source", () => {
    expect(Object.keys(files).length).toBeGreaterThan(20);
  });

  it("adds no new instruction that needs a terminal, a command, a file edit or an environment variable", () => {
    const found = violations();
    const worse: string[] = [];
    for (const [file, rules] of Object.entries(found)) {
      for (const [rule, count] of Object.entries(rules)) {
        const allowed = KNOWN_DEBT[file]?.[rule] ?? 0;
        if (count > allowed) worse.push(`${file}: "${rule}" on ${count} line(s), ${allowed} allowed`);
      }
    }
    expect(worse, `Users must never be asked to use a terminal or edit files. See agent_context/decisions/20261006-no-terminal-law.md\n${worse.join("\n")}`).toEqual([]);
  });

  it("does not keep debt that has been paid", () => {
    const found = violations();
    const stale: string[] = [];
    for (const [file, rules] of Object.entries(KNOWN_DEBT)) {
      for (const [rule, allowed] of Object.entries(rules)) {
        const count = found[file]?.[rule] ?? 0;
        if (count < allowed) stale.push(`${file}: "${rule}" is now ${count}; lower KNOWN_DEBT from ${allowed}`);
      }
    }
    expect(stale).toEqual([]);
  });
});
