/**
 * PROJECT ZERO — THE ERROR TAXONOMY (Law 4)
 *
 * Copy to `src/errors.ts`. Throw these. Never `throw new Error("...")` again.
 *
 * WHAT THIS PREVENTS
 * When errors are strings, the only way for a caller to react differently to
 * "the user sent bad input" and "the payment provider is down" is to match on
 * the message text. That coupling is invisible, untested, and breaks the moment
 * someone improves the wording. Within a year every layer is string-matching,
 * and nobody can change a message without breaking a retry loop.
 *
 * The taxonomy answers three questions at the throw site, where the answers are
 * actually known, and carries them to every caller:
 *
 *   1. WHOSE FAULT IS IT?     → status 4xx (theirs) or 5xx (ours)
 *   2. SHOULD IT BE RETRIED?  → `retryable`
 *   3. WHAT MAY THE CLIENT SEE? → `toClientJSON()`, which cannot leak internals
 *
 * THE RULE ABOUT MESSAGES
 * `message` is for humans reading logs and may change freely. `code` is the
 * API — it is stable, machine-readable, and callers may branch on it. Never
 * branch on `message`.
 */

/* -------------------------------------------------------------------- codes */

/**
 * Stable, machine-readable, and part of your public contract. Add to this
 * union; never repurpose an existing member, because a client somewhere is
 * branching on it.
 */
export const ERROR_CODES = [
  "VALIDATION_FAILED",
  "UNAUTHENTICATED",
  "FORBIDDEN",
  "NOT_FOUND",
  "CONFLICT",
  "RATE_LIMITED",
  "UPSTREAM_FAILED",
  "TIMEOUT",
  "INTERNAL",
] as const;

export type ErrorCode = (typeof ERROR_CODES)[number];

/* ---------------------------------------------------------------- base type */

export interface AppErrorOptions {
  /** Structured detail for logs. Never rendered to a client. */
  context?: Record<string, unknown>;
  /** The underlying error, preserved for the stack trace. */
  cause?: unknown;
}

export abstract class AppError extends Error {
  abstract readonly code: ErrorCode;
  /** HTTP status. 4xx means the caller can fix it; 5xx means we must. */
  abstract readonly status: number;
  /** Whether an identical retry could plausibly succeed. */
  abstract readonly retryable: boolean;

  readonly context: Record<string, unknown>;

  constructor(message: string, options: AppErrorOptions = {}) {
    super(message, { cause: options.cause });
    this.name = new.target.name;
    this.context = options.context ?? {};
    // Without this, `instanceof` breaks when targeting ES5.
    Object.setPrototypeOf(this, new.target.prototype);
    Error.captureStackTrace?.(this, new.target);
  }

  /**
   * The ONLY thing that may cross the network boundary.
   *
   * 5xx messages are replaced with a fixed string, because our internal message
   * ("connection refused to pg-primary-3.internal:5432") is a gift to an
   * attacker and meaningless to a user. 4xx messages pass through: the caller
   * caused it, so the caller needs to know what to change.
   */
  toClientJSON(requestId?: string): {
    error: { code: ErrorCode; message: string; requestId?: string };
  } {
    const safe = this.status >= 500;
    return {
      error: {
        code: this.code,
        message: safe ? "An internal error occurred." : this.message,
        ...(requestId ? { requestId } : {}),
      },
    };
  }

  /** Everything, for logs only. */
  toLogJSON(): Record<string, unknown> {
    return {
      name: this.name,
      code: this.code,
      status: this.status,
      retryable: this.retryable,
      message: this.message,
      context: this.context,
      stack: this.stack,
      cause: this.cause instanceof Error ? { name: this.cause.name, message: this.cause.message } : this.cause,
    };
  }
}

/* --------------------------------------------------------- the concrete set */

/* NOTE ON STYLE: these classes declare their fields explicitly rather than
   using TypeScript parameter properties (`constructor(readonly x: T)`).
   Parameter properties are one of the few TS features that cannot be erased by
   type-stripping alone, so they break Node's native `--experimental-strip-types`
   and any strip-only loader. Written this way, this file runs anywhere. */

/** The caller sent something we cannot accept. Name the field. */
export class ValidationError extends AppError {
  readonly code = "VALIDATION_FAILED";
  readonly status = 422;
  readonly retryable = false;
  readonly fields: Record<string, string>;
  constructor(message: string, fields: Record<string, string> = {}, options?: AppErrorOptions) {
    super(message, { ...options, context: { ...options?.context, fields } });
    this.fields = fields;
  }
  override toClientJSON(requestId?: string) {
    const base = super.toClientJSON(requestId);
    // Field-level detail is the whole point of a validation error.
    return { ...base, error: { ...base.error, fields: this.fields } };
  }
}

/** We do not know who you are. */
export class UnauthenticatedError extends AppError {
  readonly code = "UNAUTHENTICATED";
  readonly status = 401;
  readonly retryable = false;
}

/** We know who you are, and you may not do this. */
export class ForbiddenError extends AppError {
  readonly code = "FORBIDDEN";
  readonly status = 403;
  readonly retryable = false;
}

/** Deliberately indistinguishable from Forbidden where existence is itself a secret. */
export class NotFoundError extends AppError {
  readonly code = "NOT_FOUND";
  readonly status = 404;
  readonly retryable = false;
}

/** The request conflicts with current state: duplicate, version mismatch, already-used. */
export class ConflictError extends AppError {
  readonly code = "CONFLICT";
  readonly status = 409;
  readonly retryable = false;
}

/** Slow down. `retryAfterSeconds` becomes the Retry-After header. */
export class RateLimitError extends AppError {
  readonly code = "RATE_LIMITED";
  readonly status = 429;
  readonly retryable = true;
  readonly retryAfterSeconds: number;
  constructor(message: string, retryAfterSeconds = 60, options?: AppErrorOptions) {
    super(message, options);
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

/** A dependency failed. Ours to fix, and usually worth retrying. */
export class UpstreamError extends AppError {
  readonly code = "UPSTREAM_FAILED";
  readonly status = 502;
  readonly retryable = true;
  readonly service: string;
  constructor(message: string, service: string, options?: AppErrorOptions) {
    super(message, { ...options, context: { ...options?.context, service } });
    this.service = service;
  }
}

/** A dependency did not answer in time. Distinct from UpstreamError because the
 *  work may still be in flight — never retry a non-idempotent call on this. */
export class TimeoutError extends AppError {
  readonly code = "TIMEOUT";
  readonly status = 504;
  readonly retryable = true;
  readonly timeoutMs: number;
  constructor(message: string, timeoutMs: number, options?: AppErrorOptions) {
    super(message, { ...options, context: { ...options?.context, timeoutMs } });
    this.timeoutMs = timeoutMs;
  }
}

/** The fallback. Every one of these is a bug worth an alert. */
export class InternalError extends AppError {
  readonly code = "INTERNAL";
  readonly status = 500;
  readonly retryable = false;
}

/* ----------------------------------------------------------------- helpers */

export function isAppError(e: unknown): e is AppError {
  return e instanceof AppError;
}

export function isRetryable(e: unknown): boolean {
  return isAppError(e) && e.retryable;
}

/**
 * Convert anything thrown into a known error. Use this at every boundary
 * (HTTP handler, job runner, queue consumer) so an unexpected throw becomes a
 * 500 with a stack in the logs rather than a crashed process or a leaked
 * internal message.
 */
export function toAppError(e: unknown): AppError {
  if (isAppError(e)) return e;
  if (e instanceof Error) return new InternalError(e.message, { cause: e });
  return new InternalError("Unknown error", { context: { thrown: String(e) } });
}
