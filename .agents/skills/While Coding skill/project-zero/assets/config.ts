/**
 * PROJECT ZERO — THE CONFIGURATION CONTRACT (Law 3)
 *
 * Copy to `src/config.ts`. Import `config` anywhere. Never read process.env
 * again, anywhere else, for any reason.
 *
 * WHAT THIS PREVENTS
 * The most common production failure in a young service is a missing
 * environment variable discovered by the first user rather than by the process
 * that started without it. Reading `process.env.THING` inline means:
 *   - the set of required variables is unknowable without reading every file
 *   - a typo becomes `undefined`, which becomes "" or NaN, which becomes a bug
 *     three layers away from its cause
 *   - the service boots successfully into a state where it cannot work
 *
 * The contract inverts this. One schema, parsed once, at boot. If anything is
 * missing or malformed the process REFUSES TO START and prints every problem at
 * once — not the first one, all of them, because fixing config one redeploy at
 * a time is how an afternoon disappears.
 *
 * ZERO DEPENDENCIES ON PURPOSE, so it works the moment you paste it. If the
 * project already uses zod/valibot, express the same schema there instead —
 * the library is not the point, the boot-time refusal is.
 */

/* --------------------------------------------------------------- field spec */

type Parsed<T> = { ok: true; value: T } | { ok: false; problem: string };

interface Field<T> {
  parse(raw: string): Parsed<T>;
  /** Shown in error output, e.g. "a positive integer". */
  describe: string;
  /** Secret values are never echoed, even in the summary line. */
  secret?: boolean;
  optional?: boolean;
  default?: T;
}

/* The field vocabulary. All exported: adding a variable to SCHEMA below means
   reaching for one of these, and an unexported helper is one a user cannot use. */

export const str = (opts: { secret?: boolean; min?: number } = {}): Field<string> => ({
  describe: opts.secret ? "a non-empty secret string" : "a non-empty string",
  secret: opts.secret,
  parse: (raw) =>
    raw.length >= (opts.min ?? 1)
      ? { ok: true, value: raw }
      : { ok: false, problem: `must be at least ${opts.min ?? 1} character(s)` },
});

export const int = (opts: { min?: number; max?: number } = {}): Field<number> => ({
  describe: "an integer",
  parse: (raw) => {
    if (!/^-?\d+$/.test(raw.trim())) return { ok: false, problem: `"${raw}" is not an integer` };
    const n = Number(raw);
    if (opts.min !== undefined && n < opts.min) return { ok: false, problem: `must be >= ${opts.min}` };
    if (opts.max !== undefined && n > opts.max) return { ok: false, problem: `must be <= ${opts.max}` };
    return { ok: true, value: n };
  },
});

export const bool = (): Field<boolean> => ({
  describe: "true or false",
  parse: (raw) => {
    const v = raw.trim().toLowerCase();
    if (["1", "true", "yes", "on"].includes(v)) return { ok: true, value: true };
    if (["0", "false", "no", "off"].includes(v)) return { ok: true, value: false };
    return { ok: false, problem: `"${raw}" is not a boolean` };
  },
});

export const url = (opts: { protocols?: string[] } = {}): Field<string> => ({
  describe: opts.protocols ? `a ${opts.protocols.join("/")} URL` : "a URL",
  secret: true, // connection strings usually carry credentials
  parse: (raw) => {
    let u: URL;
    try { u = new URL(raw); } catch { return { ok: false, problem: `"${raw}" is not a valid URL` }; }
    if (opts.protocols && !opts.protocols.includes(u.protocol.replace(":", ""))) {
      return { ok: false, problem: `protocol must be one of ${opts.protocols.join(", ")}` };
    }
    return { ok: true, value: raw };
  },
});

export const oneOf = <const T extends readonly string[]>(values: T): Field<T[number]> => ({
  describe: `one of: ${values.join(", ")}`,
  parse: (raw) =>
    (values as readonly string[]).includes(raw)
      ? { ok: true, value: raw as T[number] }
      : { ok: false, problem: `"${raw}" is not one of ${values.join(", ")}` },
});

/** Mark a field optional, with a default used when the variable is absent. */
export const withDefault = <T>(field: Field<T>, value: T): Field<T> => ({
  ...field,
  optional: true,
  default: value,
});

/* ------------------------------------------------------------- THE SCHEMA
 * This is the contract. Edit THIS, and keep .env.example in sync — the
 * day-zero gate checks that both exist.
 * ------------------------------------------------------------------------ */

const SCHEMA = {
  NODE_ENV: withDefault(oneOf(["development", "test", "production"] as const), "development"),
  PORT: withDefault(int({ min: 1, max: 65535 }), 3000),
  LOG_LEVEL: withDefault(oneOf(["debug", "info", "warn", "error"] as const), "info"),

  // Add the project's real variables below. Every one of them, every time.
  DATABASE_URL: url({ protocols: ["postgres", "postgresql", "mysql", "file"] }),
  // SESSION_SECRET: str({ secret: true, min: 32 }),
} satisfies Record<string, Field<unknown>>;

type Schema = typeof SCHEMA;
type Config = { [K in keyof Schema]: Schema[K] extends Field<infer T> ? T : never };

/* ------------------------------------------------------------------- parse */

export function parseConfig(env: Record<string, string | undefined> = process.env): Config {
  const out = {} as Record<string, unknown>;
  const problems: string[] = [];

  for (const [key, field] of Object.entries(SCHEMA) as [string, Field<unknown>][]) {
    const raw = env[key];

    if (raw === undefined || raw === "") {
      if (field.optional) { out[key] = field.default; continue; }
      problems.push(`  ${key} is required — expected ${field.describe}`);
      continue;
    }

    const result = field.parse(raw);
    if (result.ok) out[key] = result.value;
    // Never echo the offending value for a secret: error output reaches logs.
    else problems.push(`  ${key} ${field.secret ? "is invalid (value hidden)" : result.problem}`);
  }

  if (problems.length > 0) {
    // Collect ALL problems. Fixing config one redeploy at a time is how an
    // afternoon disappears.
    throw new ConfigError(
      `Invalid configuration — ${problems.length} problem(s):\n${problems.join("\n")}\n\n` +
      `Every variable above is declared in src/config.ts and documented in .env.example.`,
    );
  }

  return out as Config;
}

export class ConfigError extends Error {
  readonly code = "CONFIG_INVALID";
  constructor(message: string) {
    super(message);
    this.name = "ConfigError";
  }
}

/**
 * Parsed once, at import time, so an invalid environment kills the process at
 * boot instead of at first request. This top-level throw is deliberate, and it
 * is the entire mechanism behind Law 3.
 *
 * CONSEQUENCE, AND HOW TO TEST AROUND IT
 * Importing anything from this module runs the parse. That is the point — it
 * makes booting-while-misconfigured impossible — but it means tests must either
 * provide a valid environment before importing, or avoid importing `config`.
 *
 * In tests, do not import `config`. Import `parseConfig` and pass an explicit
 * object, which needs no environment at all and lets one test cover many
 * configurations:
 *
 *   const cfg = parseConfig({ DATABASE_URL: "postgres://localhost/test" });
 *
 * If a test genuinely needs the real singleton, set the variables in a setup
 * file that runs before any import (vitest `setupFiles`, jest `globalSetup`).
 */
export const config: Config = parseConfig();

/** Safe to log: secrets are replaced, not omitted, so gaps stay visible. */
export function describeConfig(): Record<string, unknown> {
  const safe: Record<string, unknown> = {};
  for (const [key, field] of Object.entries(SCHEMA) as [string, Field<unknown>][]) {
    safe[key] = field.secret ? "[redacted]" : (config as Record<string, unknown>)[key];
  }
  return safe;
}
