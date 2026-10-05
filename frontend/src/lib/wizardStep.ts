export const WIZARD_STEP_KEY = "quantos.welcome.step";
export const WIZARD_LAST_STEP = 3;

function getSessionStorage(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.sessionStorage : null;
  } catch {
    return null;
  }
}

export function clampStep(value: unknown): number {
  if (typeof value !== "number" && typeof value !== "string") {
    return 0;
  }
  if (typeof value === "string" && !value.trim()) {
    return 0;
  }
  const n = Number(value);
  if (!Number.isInteger(n) || n < 0 || n > WIZARD_LAST_STEP) {
    return 0;
  }
  return n === 0 ? 0 : n;
}

export function readStep(storage?: Pick<Storage, "getItem"> | null): number {
  try {
    const s = storage === undefined ? getSessionStorage() : storage;
    if (!s) return 0;
    const raw = s.getItem(WIZARD_STEP_KEY);
    return clampStep(raw);
  } catch {
    return 0;
  }
}

export function writeStep(step: number, storage?: Pick<Storage, "setItem"> | null): void {
  try {
    const s = storage === undefined ? getSessionStorage() : storage;
    if (!s) return;
    const clamped = Math.max(0, Math.min(WIZARD_LAST_STEP, Number.isFinite(step) ? Math.trunc(step) : 0));
    s.setItem(WIZARD_STEP_KEY, String(clamped));
  } catch {
    // never throw
  }
}

export function clearStep(storage?: Pick<Storage, "removeItem"> | null): void {
  try {
    const s = storage === undefined ? getSessionStorage() : storage;
    if (!s) return;
    s.removeItem(WIZARD_STEP_KEY);
  } catch {
    // never throw
  }
}
