import { afterEach, describe, expect, it } from "vitest";
import type { ProviderOption } from "./copilot";
import {
  type AiApp,
  type AiChoice,
  type AppId,
  type AppState,
  APPS_ANCHOR,
  appChip,
  appName,
  applyPatch,
  buildPlan,
  groupModels,
  hasAnswerer,
  keyChip,
  settle,
  needsSetup,
  showAppSetup,
  summarise,
  testLine,
  testSubject,
  testTarget,
} from "./aiSource";

const NAMES: Record<AppId, string> = { claude: "Claude Code", codex: "Codex", gemini: "Gemini" };

function app(id: AppId, state: AppState): AiApp {
  const installed = state !== "NOT_INSTALLED";
  return { id, name: NAMES[id], label: `${NAMES[id]} (sign-in)`, state, installed, ready: state === "CONNECTED" };
}

const key = (id: string, ready = true): ProviderOption => ({ id, label: LABELS[id] ?? id, ready });
const LABELS: Record<string, string> = {
  anthropic: "Anthropic (Claude)",
  openai: "OpenAI",
  gemini: "Google Gemini",
  groq: "Groq",
};

const NO_APPS = [app("claude", "NOT_INSTALLED"), app("codex", "NOT_INSTALLED"), app("gemini", "NOT_INSTALLED")];
const NO_KEYS = ["anthropic", "openai", "gemini", "groq"].map((id) => key(id, false));
const withKeys = (...ids: string[]) => NO_KEYS.map((k) => ({ ...k, ready: ids.includes(k.id) }));
const withApps = (...apps: AiApp[]) => NO_APPS.map((blank) => apps.find((a) => a.id === blank.id) ?? blank);

const ANSWERED = "OpenAI answered, so it is ready to use.";
const AUTO: AiChoice = { source: "cli", cli: null, api: null, fallback: true };

interface Case {
  name: string;
  apps: AiApp[];
  keys: ProviderOption[];
  choice?: Partial<AiChoice>;
  says: string;
}

const CASES: Case[] = [
  { name: "nothing is set up", apps: NO_APPS, keys: NO_KEYS, says: "No AI is set up yet." },
  {
    name: "an app only",
    apps: withApps(app("claude", "CONNECTED")),
    keys: NO_KEYS,
    says: "Right now your questions go to Claude Code.",
  },
  {
    name: "a key only",
    apps: NO_APPS,
    keys: withKeys("openai"),
    says: "Right now your questions go to your saved OpenAI key.",
  },
  {
    name: "both, the app chosen",
    apps: withApps(app("claude", "CONNECTED")),
    keys: withKeys("openai"),
    says: "Right now your questions go to Claude Code, with your saved OpenAI key as a backup.",
  },
  {
    name: "both, the key chosen",
    apps: withApps(app("claude", "CONNECTED")),
    keys: withKeys("openai"),
    choice: { source: "api" },
    says: "Right now your questions go to your saved OpenAI key, with Claude Code as a backup.",
  },
  {
    name: "the backup turned off while the other kind is set up",
    apps: withApps(app("claude", "CONNECTED")),
    keys: withKeys("openai"),
    choice: { fallback: false },
    says: "Right now your questions go to Claude Code and nowhere else.",
  },
  {
    name: "the backup turned off and the chosen kind has nothing",
    apps: NO_APPS,
    keys: withKeys("openai"),
    choice: { fallback: false },
    says:
      "No AI app on this computer is ready, and trying the other kind is turned off, " +
      "so your questions have nowhere to go.",
  },
  {
    name: "a key chosen, the backup turned off, and no key saved",
    apps: withApps(app("codex", "CONNECTED")),
    keys: NO_KEYS,
    choice: { source: "api", fallback: false },
    says: "No saved AI key is ready, and trying the other kind is turned off, so your questions have nowhere to go.",
  },
  {
    name: "a favourite app that is not signed in",
    apps: withApps(app("claude", "CONNECTED"), app("codex", "NEEDS_SIGN_IN")),
    keys: withKeys("openai"),
    choice: { cli: "codex" },
    says:
      "Codex is not signed in, so right now your questions go to Claude Code, " +
      "with your saved OpenAI key as a backup.",
  },
  {
    name: "a favourite app that is ready",
    apps: withApps(app("claude", "CONNECTED"), app("codex", "CONNECTED")),
    keys: NO_KEYS,
    choice: { cli: "codex" },
    says: "Right now your questions go to Codex, with Claude Code as a backup.",
  },
  {
    name: "a favourite app that is not installed",
    apps: withApps(app("claude", "CONNECTED")),
    keys: NO_KEYS,
    choice: { cli: "codex" },
    says: "Right now your questions go to Claude Code.",
  },
  {
    name: "two apps and a key, in the fixed order",
    apps: withApps(app("antigravity", "CONNECTED"), app("claude", "CONNECTED")),
    keys: withKeys("groq", "anthropic"),
    says:
      "Right now your questions go to Claude Code, with Antigravity, " +
      "your saved Anthropic (Claude) key and your saved Groq key as backups.",
  },
  {
    name: "a favourite key",
    apps: NO_APPS,
    keys: withKeys("openai", "groq"),
    choice: { source: "api", api: "groq" },
    says: "Right now your questions go to your saved Groq key, with your saved OpenAI key as a backup.",
  },
  {
    name: "an app that cannot say whether it is signed in",
    apps: withApps(app("antigravity", "UNKNOWN")),
    keys: NO_KEYS,
    says: "Right now your questions go to Antigravity (not checked yet).",
  },
  {
    name: "apps that are all signed out and no key",
    apps: withApps(app("claude", "NEEDS_SIGN_IN")),
    keys: NO_KEYS,
    says: "No AI is ready yet. Claude Code is not signed in.",
  },
  {
    name: "two apps signed out and a key saved",
    apps: withApps(app("claude", "NEEDS_SIGN_IN"), app("codex", "NEEDS_SIGN_IN")),
    keys: withKeys("openai"),
    says: "Claude Code and Codex are not signed in, so right now your questions go to your saved OpenAI key.",
  },
];

describe("the sentence that says where a question goes", () => {
  it.each(CASES)("is true when $name", ({ apps, keys, choice, says }) => {
    expect(summarise({ apps, providers: keys }, { ...AUTO, ...choice })).toBe(says);
  });

  it("never uses a developer word", () => {
    const say = ({ apps, keys, choice }: Case) => summarise({ apps, providers: keys }, { ...AUTO, ...choice });
    const text = CASES.map(say).join(" ");
    expect(text).not.toMatch(/\b(API|token|terminal|command|install script|CLI)\b/i);
  });

  it("names Antigravity without the developer's word, even if an older engine still sends it", () => {
    expect(appName({ id: "antigravity", name: "Antigravity CLI" })).toBe("Antigravity");
    expect(appName(app("antigravity", "CONNECTED"))).toBe("Antigravity");
  });
});

describe("whether anything can answer", () => {
  const apps = withApps(app("claude", "CONNECTED"));
  const NO_BACKUP = { ...AUTO, fallback: false };

  const ANSWER_CASES = [
    ["nothing is set up", NO_APPS, NO_KEYS, AUTO, false],
    ["an app is ready", apps, NO_KEYS, AUTO, true],
    ["only a signed-out app exists", withApps(app("claude", "NEEDS_SIGN_IN")), NO_KEYS, AUTO, false],
    ["the chosen kind is empty and the backup is off", NO_APPS, withKeys("openai"), NO_BACKUP, false],
    ["the chosen kind is empty and the backup is on", NO_APPS, withKeys("openai"), AUTO, true],
  ] as const;

  it.each(ANSWER_CASES)("when %s", (_name, installed, keys, choice, expected) => {
    expect(hasAnswerer({ apps: installed, providers: keys }, choice)).toBe(expected);
  });
});

describe("the order questions are asked in", () => {
  const status = {
    apps: withApps(app("claude", "CONNECTED"), app("codex", "CONNECTED")),
    providers: withKeys("openai", "groq"),
  };
  const KEYS_FIRST = { ...AUTO, source: "api" as const };
  const FAVOURITES = { ...AUTO, cli: "codex" as const, api: "groq" };

  const ORDER_CASES = [
    ["the app kind first by default", AUTO, ["cli:claude", "cli:codex", "api:openai", "api:groq"]],
    ["the key kind first when chosen", KEYS_FIRST, ["api:openai", "api:groq", "cli:claude", "cli:codex"]],
    ["the favourites ahead of the rest", FAVOURITES, ["cli:codex", "cli:claude", "api:groq", "api:openai"]],
    ["only the chosen kind when the backup is off", { ...AUTO, fallback: false }, ["cli:claude", "cli:codex"]],
  ] as const;

  it.each(ORDER_CASES)("puts %s", (_name, choice, expected) => {
    expect(buildPlan(status, choice).map((entry) => `${entry.kind}:${entry.id}`)).toEqual(expected);
  });
});

describe("what a click changes", () => {
  const before: AiChoice = { source: "cli", cli: "claude", api: "groq", fallback: true };

  const CLICK_CASES = [
    [{ ai_source: "api" as const }, { ...before, source: "api" as const }],
    [{ ai_cli: "codex" as const }, { ...before, cli: "codex" as const }],
    [{ ai_cli: null }, { ...before, cli: null }],
    [{ ai_api: null }, { ...before, api: null }],
    [{ ai_fallback: false }, { ...before, fallback: false }],
  ] as const;

  it.each(CLICK_CASES)("%j changes only what it names", (patch, expected) => {
    expect(applyPatch(before, patch)).toEqual(expected);
  });
});

describe("changes still on their way", () => {
  const API = { ai_source: "api" as const };
  const CLI = { ai_source: "cli" as const };

  const SETTLE_CASES = [
    ["a finished save is dropped", API, API, {}],
    ["a newer click on the same setting stays", CLI, API, CLI],
    ["another setting stays", { ai_fallback: false }, API, { ai_fallback: false }],
  ] as const;

  it.each(SETTLE_CASES)("%s", (_name, wanted, finished, left) => {
    expect(settle(wanted, finished)).toEqual(left);
  });
});

describe("testing an AI", () => {
  const status = { apps: withApps(app("claude", "CONNECTED")), providers: withKeys("openai") };

  const TARGET_CASES = [
    ["no favourite app", AUTO, null],
    ["a favourite app", { ...AUTO, cli: "codex" as const }, "cli:codex"],
    ["no favourite key", { ...AUTO, source: "api" as const }, null],
    ["a favourite key", { ...AUTO, source: "api" as const, api: "openai" }, "openai"],
  ] as const;

  it.each(TARGET_CASES)("with %s tests %s", (_name, choice, target) => {
    expect(testTarget(choice)).toBe(target);
  });

  const SUBJECT_CASES = [
    [null, "Tests whichever AI your questions go to first."],
    ["cli:claude", "Tests Claude Code (sign-in)."],
    ["openai", "Tests OpenAI."],
  ] as const;

  it.each(SUBJECT_CASES)("says what %s tests", (target, said) => {
    expect(testSubject(status, target)).toBe(said);
  });

  const LINE_CASES = [
    [{ ok: true, who: "OpenAI", message: ANSWERED }, ANSWERED],
    [{ ok: false, who: "Codex", message: "That AI app is not signed in." }, "Codex: That AI app is not signed in."],
    [{ ok: false, who: null, message: "No AI is set up yet." }, "No AI is set up yet."],
  ] as const;

  it.each(LINE_CASES)("shows %j as one line", (result, line) => {
    expect(testLine(result)).toBe(line);
  });
});

describe("the chips", () => {
  const CHIP_CASES = [
    ["CONNECTED", "Ready", "up", false],
    ["NEEDS_SIGN_IN", "Not signed in", "warn", true],
    ["NOT_INSTALLED", "Not installed", "neutral", true],
    ["UNKNOWN", "Not checked yet", "neutral", false],
  ] as const;

  it.each(CHIP_CASES)("%s reads %s", (state, text, tone, setup) => {
    expect(appChip({ state })).toEqual({ text, tone });
    expect(needsSetup({ state })).toBe(setup);
  });

  const KEY_CHIP_CASES = [
    [true, "Key saved"],
    [false, "No key yet"],
  ] as const;

  it.each(KEY_CHIP_CASES)("a key with ready=%s reads %s", (ready, text) => {
    expect(keyChip({ ready }).text).toBe(text);
  });
});

describe("the second-opinion groups", () => {
  it("puts the apps in one group and the keys in the other, each in the engine's order", () => {
    const models: ProviderOption[] = [
      { id: "cli:claude", label: "Claude Code", ready: true },
      { id: "cli:codex", label: "Codex", ready: false },
      { id: "openai", label: "OpenAI", ready: true },
      { id: "groq", label: "Groq", ready: false },
    ];
    const { apps, keys } = groupModels(models);
    expect(apps.map((m) => m.id)).toEqual(["cli:claude", "cli:codex"]);
    expect(keys.map((m) => m.id)).toEqual(["openai", "groq"]);
  });
});

describe("the Set up jump", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  function bridge() {
    document.body.innerHTML = `
      <div id="${APPS_ANCHOR}" tabindex="-1">
        <div class="rounded-xl" data-app-name="Claude Code"><h3>Claude Code</h3><button>Sign in</button></div>
        <div class="rounded-xl" data-app-name="Codex"><h3>Codex</h3><button disabled>Wait</button><button>Install</button></div>
      </div>`;
  }

  it("puts the keyboard on the first button of that app's card", () => {
    bridge();
    showAppSetup("Codex");
    expect(document.activeElement?.textContent).toBe("Install");
  });

  it("falls back to the whole group for an app it cannot find, or none", () => {
    bridge();
    showAppSetup("Gemini");
    expect(document.activeElement?.id).toBe(APPS_ANCHOR);
  });

  it("does nothing when the cards are not on the page", () => {
    expect(() => showAppSetup("Codex")).not.toThrow();
  });
});
