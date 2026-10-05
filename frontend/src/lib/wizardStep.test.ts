import { describe, expect, it } from "vitest";
import {
  clampStep,
  clearStep,
  readStep,
  WIZARD_LAST_STEP,
  WIZARD_STEP_KEY,
  writeStep,
} from "./wizardStep";

function createFakeStorage(initial?: Record<string, string>) {
  const map = new Map<string, string>(initial ? Object.entries(initial) : []);
  return {
    getItem: (key: string) => map.get(key) ?? null,
    setItem: (key: string, value: string) => {
      map.set(key, value);
    },
    removeItem: (key: string) => {
      map.delete(key);
    },
  };
}

function createThrowingStorage() {
  return {
    getItem: (_key: string): string | null => {
      throw new Error("Storage blocked");
    },
    setItem: (_key: string, _value: string): void => {
      throw new Error("Storage blocked");
    },
    removeItem: (_key: string): void => {
      throw new Error("Storage blocked");
    },
  };
}

describe("clampStep", () => {
  it("covers 0, 3, 2.5, -1, 4, NaN, \"2\", \"abc\", null, undefined", () => {
    expect(clampStep(0)).toBe(0);
    expect(clampStep(3)).toBe(3);
    expect(clampStep(2.5)).toBe(0);
    expect(clampStep(-1)).toBe(0);
    expect(clampStep(4)).toBe(0);
    expect(clampStep(NaN)).toBe(0);
    expect(clampStep("2")).toBe(2);
    expect(clampStep("abc")).toBe(0);
    expect(clampStep(null)).toBe(0);
    expect(clampStep(undefined)).toBe(0);
  });
});

describe("readStep", () => {
  it("returns 0 with nothing stored", () => {
    const storage = createFakeStorage();
    expect(readStep(storage)).toBe(0);
  });

  it("returns 2 with \"2\" stored", () => {
    const storage = createFakeStorage({ [WIZARD_STEP_KEY]: "2" });
    expect(readStep(storage)).toBe(2);
  });

  it("returns 0 with garbage stored", () => {
    const storage = createFakeStorage({ [WIZARD_STEP_KEY]: "garbage" });
    expect(readStep(storage)).toBe(0);
  });

  it("returns 0 with storage that throws on getItem", () => {
    const storage = createThrowingStorage();
    expect(readStep(storage)).toBe(0);
  });

  it("returns 0 with null storage", () => {
    expect(readStep(null)).toBe(0);
  });
});

describe("writeStep", () => {
  it("round-trips with readStep", () => {
    const storage = createFakeStorage();
    writeStep(2, storage);
    expect(readStep(storage)).toBe(2);
  });

  it("clamps out-of-range steps when writing (99 stores 3; -5 stores 0)", () => {
    const storage = createFakeStorage();
    writeStep(99, storage);
    expect(storage.getItem(WIZARD_STEP_KEY)).toBe("3");
    expect(readStep(storage)).toBe(3);

    writeStep(-5, storage);
    expect(storage.getItem(WIZARD_STEP_KEY)).toBe("0");
    expect(readStep(storage)).toBe(0);
  });

  it("never throws when storage throws", () => {
    const storage = createThrowingStorage();
    expect(() => writeStep(2, storage)).not.toThrow();
  });
});

describe("clearStep", () => {
  it("removes the key from storage", () => {
    const storage = createFakeStorage({ [WIZARD_STEP_KEY]: "2" });
    clearStep(storage);
    expect(storage.getItem(WIZARD_STEP_KEY)).toBeNull();
    expect(readStep(storage)).toBe(0);
  });

  it("never throws when storage throws", () => {
    const storage = createThrowingStorage();
    expect(() => clearStep(storage)).not.toThrow();
  });
});

describe("constants", () => {
  it("defines WIZARD_STEP_KEY and WIZARD_LAST_STEP", () => {
    expect(WIZARD_STEP_KEY).toBe("quantos.welcome.step");
    expect(WIZARD_LAST_STEP).toBe(3);
  });
});

describe("default sessionStorage", () => {
  it("uses window.sessionStorage when storage argument is omitted", () => {
    sessionStorage.clear();
    expect(readStep()).toBe(0);
    writeStep(2);
    expect(sessionStorage.getItem(WIZARD_STEP_KEY)).toBe("2");
    expect(readStep()).toBe(2);
    clearStep();
    expect(sessionStorage.getItem(WIZARD_STEP_KEY)).toBeNull();
    expect(readStep()).toBe(0);
  });
});

