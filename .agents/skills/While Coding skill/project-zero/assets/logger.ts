/**
 * PROJECT ZERO — STRUCTURED LOGGING (Law 5)
 *
 * Copy to `src/logger.ts`. Zero dependencies, so it works the moment you paste
 * it. If the project later adopts pino/winston/slog, keep the SHAPE: one line,
 * one JSON object, one event, always carrying a correlation id.
 *
 * WHAT THIS PREVENTS
 * `console.log("here", user)` is unusable in an incident. At 3am you need to
 * answer "show me every event for the request that failed", and prose logs
 * cannot answer it at any price. Structured events can, and the cost of
 * emitting them is the same.
 *
 * THE CORRELATION ID IS THE WHOLE POINT
 * One id, generated at the edge, attached to every log line produced while
 * handling that request — including from code five layers deep that knows
 * nothing about HTTP. AsyncLocalStorage does this without threading a context
 * parameter through every function signature.
 */

import { AsyncLocalStorage } from "node:async_hooks";
import { randomUUID } from "node:crypto";

/* ------------------------------------------------------------------- levels */

export const LEVELS = { debug: 10, info: 20, warn: 30, error: 40 } as const;
export type Level = keyof typeof LEVELS;

const threshold = (): number =>
  LEVELS[(process.env.LOG_LEVEL as Level) in LEVELS ? (process.env.LOG_LEVEL as Level) : "info"];

/* -------------------------------------------------------------- request ctx */

interface RequestContext {
  requestId: string;
  [key: string]: unknown;
}

const storage = new AsyncLocalStorage<RequestContext>();

/**
 * Wrap the handling of one request/job/message. Everything logged inside —
 * however deep — carries this context automatically.
 */
export function withRequestContext<T>(fn: () => T, context: Partial<RequestContext> = {}): T {
  return storage.run({ requestId: context.requestId ?? randomUUID(), ...context }, fn);
}

export function currentRequestId(): string | undefined {
  return storage.getStore()?.requestId;
}

/** Add a field to the current context — e.g. userId once authentication resolves. */
export function enrichContext(fields: Record<string, unknown>): void {
  const store = storage.getStore();
  if (store) Object.assign(store, fields);
}

/* --------------------------------------------------------------- redaction */

/**
 * Secrets reach logs by accident, not by intent — someone logs a whole request
 * body and it happens to contain a token. Redact by key name, at write time, so
 * being careless is not the same as leaking.
 */
const SECRET_KEY = /pass(word|wd)?|secret|token|api[-_]?key|authorization|cookie|session|credit|card|cvv|ssn|private[-_]?key/i;
const MAX_DEPTH = 6;

function redact(value: unknown, depth = 0): unknown {
  if (depth > MAX_DEPTH) return "[max depth]";
  if (value === null || typeof value !== "object") return value;
  if (value instanceof Error) return { name: value.name, message: value.message, stack: value.stack };
  if (Array.isArray(value)) return value.map((v) => redact(v, depth + 1));

  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
    out[k] = SECRET_KEY.test(k) ? "[redacted]" : redact(v, depth + 1);
  }
  return out;
}

/* ------------------------------------------------------------------ emitter */

export interface LogFields {
  [key: string]: unknown;
  /** Prefer a stable, greppable event name over a prose message. */
  event?: string;
  err?: unknown;
}

function emit(level: Level, message: string, fields: LogFields = {}): void {
  if (LEVELS[level] < threshold()) return;

  const store = storage.getStore();
  const line = {
    ts: new Date().toISOString(),
    level,
    msg: message,
    ...(store ? redact(store) as Record<string, unknown> : {}),
    ...(redact(fields) as Record<string, unknown>),
  };

  // One line, one JSON object. stderr for warn+ so it survives stdout capture.
  const out = LEVELS[level] >= LEVELS.warn ? process.stderr : process.stdout;
  out.write(JSON.stringify(line) + "\n");
}

export const logger = {
  debug: (msg: string, fields?: LogFields) => emit("debug", msg, fields),
  info: (msg: string, fields?: LogFields) => emit("info", msg, fields),
  warn: (msg: string, fields?: LogFields) => emit("warn", msg, fields),
  error: (msg: string, fields?: LogFields) => emit("error", msg, fields),

  /** A logger with fields bound to every line — e.g. logger.child({ module: "billing" }). */
  child(bound: LogFields) {
    const merge = (f?: LogFields) => ({ ...bound, ...f });
    return {
      debug: (m: string, f?: LogFields) => emit("debug", m, merge(f)),
      info: (m: string, f?: LogFields) => emit("info", m, merge(f)),
      warn: (m: string, f?: LogFields) => emit("warn", m, merge(f)),
      error: (m: string, f?: LogFields) => emit("error", m, merge(f)),
    };
  },
};

/* ------------------------------------------------- health and the one metric
 *
 * Law 8: one health endpoint and one metric, from the first deploy.
 * `/health` must actually CHECK its dependencies. An endpoint that returns 200
 * unconditionally reports that the process is running, which you already knew,
 * and will report healthy throughout an outage.
 * ------------------------------------------------------------------------ */

export type HealthCheck = () => Promise<void>;

const checks = new Map<string, HealthCheck>();

/** Register at startup: registerHealthCheck("database", () => db.query("select 1")) */
export function registerHealthCheck(name: string, check: HealthCheck): void {
  checks.set(name, check);
}

export interface HealthReport {
  status: "ok" | "degraded";
  uptimeSeconds: number;
  checks: Record<string, { status: "ok" | "failed"; ms: number; error?: string }>;
}

export async function health(timeoutMs = 2000): Promise<HealthReport> {
  const results: HealthReport["checks"] = {};

  await Promise.all(
    [...checks.entries()].map(async ([name, check]) => {
      const started = Date.now();
      try {
        // A health check that can hang is worse than none — it turns a degraded
        // dependency into an unresponsive load-balancer probe.
        await Promise.race([
          check(),
          new Promise((_, reject) => setTimeout(() => reject(new Error(`timed out after ${timeoutMs}ms`)), timeoutMs)),
        ]);
        results[name] = { status: "ok", ms: Date.now() - started };
      } catch (e) {
        results[name] = {
          status: "failed",
          ms: Date.now() - started,
          error: e instanceof Error ? e.message : String(e),
        };
      }
    }),
  );

  const failed = Object.values(results).some((r) => r.status === "failed");
  return {
    status: failed ? "degraded" : "ok",
    uptimeSeconds: Math.round(process.uptime()),
    checks: results,
  };
}
