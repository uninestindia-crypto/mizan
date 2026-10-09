// The name of the screen a person is on, for the top bar: a title and, for a screen inside another, a way back to the
// one it belongs to ("Settings / AI assistants"). Names match the sidebar's words and each screen's own heading.

export interface ScreenName {
  title: string;
  parent?: { label: string; to: string };
}

const SETTINGS_SECTIONS: Record<string, string> = {
  profile: "Profile & money rules",
  charges: "Broker charges",
  data: "Market data",
  accounts: "Accounts & keys",
  ai: "AI assistants",
  about: "About",
};

const TOOLS: Record<string, string> = {
  costs: "Trade costs",
  "position-size": "Position size",
  options: "Options payoff",
  agents: "AI apps",
};

const LAB: Record<string, string> = { new: "New test", runs: "Test result" };

const PAPER: Record<string, string> = { new: "New paper book" };

const PLAIN: Record<string, string> = {
  "/": "Home",
  "/markets": "Markets",
  "/lab": "Strategy Lab",
  "/portfolio": "Portfolio",
  "/paper": "Paper trading",
  "/agents": "Agents",
  "/shariah": "Mizan Shariah",
  "/settings": "Settings",
  "/tools": "Tools",
};

const PARENTS: Record<string, { label: string; to: string }> = {
  stock: { label: "Markets", to: "/markets" },
  lab: { label: "Strategy Lab", to: "/lab" },
  paper: { label: "Paper trading", to: "/paper" },
  settings: { label: "Settings", to: "/settings/profile" },
  tools: { label: "Tools", to: "/tools/costs" },
};

/** A value from a table by its own key only, so a path piece like "constructor" finds nothing. */
function own<T>(table: Record<string, T>, key: string | undefined): T | undefined {
  return key !== undefined && Object.hasOwn(table, key) ? table[key] : undefined;
}

function decoded(part: string): string {
  try {
    return decodeURIComponent(part);
  } catch {
    return part;
  }
}

/** Inside a group: a title, with the group as its parent. Unknown names fall back to the group's own name. */
function inside(group: string, title: string | undefined, whole: string): ScreenName {
  const parent = own(PARENTS, group);
  if (!title || !parent) return { title: whole };
  return { title, parent };
}

function nested(group: string, rest: string[]): ScreenName {
  const [first = ""] = rest;
  const whole = own(PARENTS, group)?.label ?? "QuantOS";
  if (group === "stock") return inside(group, first ? decoded(first).toUpperCase() : undefined, whole);
  if (group === "settings") return inside(group, own(SETTINGS_SECTIONS, first), whole);
  if (group === "tools") return inside(group, own(TOOLS, first), whole);
  if (group === "lab") return inside(group, own(LAB, first), whole);
  if (group === "paper") return inside(group, first ? (own(PAPER, first) ?? "Paper book") : undefined, whole);
  return { title: whole };
}

export function screenName(pathname: string): ScreenName {
  const clean = pathname.replace(/\/+$/, "") || "/";
  const plain = own(PLAIN, clean);
  if (plain) return { title: plain };
  const [group = "", ...rest] = clean.split("/").filter(Boolean);
  if (!own(PARENTS, group)) return { title: "Page not found" };
  return nested(group, rest);
}
